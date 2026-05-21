from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from random import Random
from typing import Any

from aquagenesys.agents import Action, FishAgent, FishDeliberationController, FishDeliberationResult, FishGenome, Perception
from aquagenesys.agents.fish import clamp, unit
from aquagenesys.environment.puddle import EnvironmentConfig, PuddleEnvironment
from aquagenesys.storage import FishArchive


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 42
    width: int = 96
    height: int = 60
    initial_population: int = 42
    max_population: int = 140
    deliberation_enabled: bool = True
    deliberation_interval_ticks: int = 36
    global_deliberations_per_tick: int = 1
    fish_model_budget: int = 3
    model_intent_ttl: int = 14
    max_inflight_model_calls: int = 1
    ecology_update_interval: int = 4
    llm_base_url: str = "http://127.0.0.1:8008/v1"
    llm_api_key: str = ""
    llm_model: str = "Lexi"
    llm_timeout_seconds: float = 1.8
    llm_max_retries: int = 0
    llm_temperature: float = 0.1
    llm_max_tokens: int = 140
    trace_backend: str = "noop"
    trace_jsonl_path: str = "/tmp/aquagenesys-v03/llm-trace.jsonl"
    archive_dir: str = "/tmp/aquagenesys-v03"
    archive_every_ticks: int = 25
    debug_founder_reseed_enabled: bool = False
    debug_founder_reseed_min_population: int = 8
    debug_founder_reseed_after_ticks: int = 80


class AquagenesysSimulation:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.speed = 1
        self._initial_seed = self.config.seed
        self._controller: FishDeliberationController | None = None
        self._model_executor: ThreadPoolExecutor | None = None
        self._pending_model_calls: dict[int, Future[FishDeliberationResult]] = {}
        self.reset()

    def reset(self) -> None:
        self._cancel_pending_model_calls()
        self.rng = Random(self._initial_seed)
        self.tick = 0
        self.next_fish_id = 1
        self.next_lineage_id = 1
        self.low_population_ticks = 0
        self.dead_puddle = False
        self.decision_log: deque[dict[str, Any]] = deque(maxlen=36)
        self.events: deque[dict[str, Any]] = deque(maxlen=36)
        self.births = 0
        self.births_reproduction = 0
        self.births_reseed_debug = 0
        self.deaths_by_cause: Counter[str] = Counter()
        self.extinction_events = 0
        self.recovery_events = 0
        self.last_recovery_kind = "none"
        self.collapse_cause_guess = "none"
        self.model_calls = 0
        self.model_queued = 0
        self.model_successes = 0
        self.model_failures = 0
        self.model_skipped_budget = 0
        self.model_skipped_pending = 0
        self.model_intents_applied = 0
        self.last_model_error = ""
        self._queued_deliberations_this_tick = 0
        self.environment = PuddleEnvironment(
            EnvironmentConfig(
                width=self.config.width,
                height=self.config.height,
                seed=self._initial_seed,
                ecology_update_interval=self.config.ecology_update_interval,
            )
        )
        archive_root = Path(self.config.archive_dir)
        self.archive = FishArchive(
            state_path=archive_root / "fish_state.jsonl",
            memory_path=archive_root / "fish_memory.jsonl",
        )
        self.fish: list[FishAgent] = []
        self._seed_founders(self.config.initial_population)
        self.initial_signature = self._reset_signature()

    def _reset_signature(self) -> tuple[object, ...]:
        return (
            self.environment.signature,
            tuple(
                (
                    fish.lineage_id,
                    round(fish.x, 3),
                    round(fish.y, 3),
                    fish.genome.metabolism,
                    round(fish.energy, 3),
                )
                for fish in self.fish[:12]
            ),
        )

    def set_speed(self, value: int) -> None:
        self.speed = max(1, min(16, int(value)))

    def set_deliberation_enabled(self, value: bool) -> None:
        self.config = SimulationConfig(**{**self.config.__dict__, "deliberation_enabled": bool(value)})
        self._event("deliberation_toggle", enabled=self.config.deliberation_enabled)

    def randomize_environment(self) -> None:
        seed = self.rng.randint(1, 2_000_000_000)
        self.environment.randomize(seed)
        self._event("environment_randomized", seed=seed)

    def run(self, ticks: int) -> None:
        for _ in range(max(0, ticks)):
            self.step()

    def step(self) -> None:
        self.tick += 1
        self.environment.update()
        self._poll_model_results()
        for signal in self.environment.event_signals:
            self._event(str(signal["kind"]), value=signal.get("value"))
        if not self.fish:
            self._debug_reseed_if_needed()
            if not self.fish:
                self._handle_extinction()
            self._archive_if_due()
            return

        self.environment.apply_population_pressure((fish.x, fish.y, fish.radius) for fish in self.fish)
        deliberations_used = 0
        self._queued_deliberations_this_tick = 0
        deaths: dict[int, str] = {}
        newborns: list[FishAgent] = []
        shuffled = list(self.fish)
        self.rng.shuffle(shuffled)
        for fish in shuffled:
            if fish.fish_id in deaths:
                continue
            perception = self._sense(fish)
            fish.update_internal_state(perception)
            before_energy = fish.energy
            before_health = fish.health
            action = self._select_action(fish, perception, deliberations_used)
            if action.source == "model":
                deliberations_used += 1
            outcome = self._apply_action(fish, action, perception, deaths)
            fish.record_outcome(
                self.tick,
                action,
                outcome=outcome,
                delta_energy=fish.energy - before_energy,
                delta_health=fish.health - before_health,
            )
            self._record_decision(fish, action, outcome)
            child = self._maybe_reproduce(fish, perception)
            if child is not None:
                newborns.append(child)
            cause = self._death_cause(fish)
            if cause is not None:
                deaths[fish.fish_id] = cause

        survivors: list[FishAgent] = []
        for fish in self.fish:
            cause = deaths.get(fish.fish_id)
            if cause:
                self._recycle_dead(fish, cause)
            else:
                survivors.append(fish)
        self.fish = survivors
        if newborns:
            remaining = max(0, self.config.max_population - len(self.fish))
            self.fish.extend(newborns[:remaining])
            if len(newborns) > remaining:
                for child in newborns[remaining:]:
                    self._recycle_dead(child, "density_limit")
        self._debug_reseed_if_needed()
        if not self.fish:
            self._handle_extinction()
        self._archive_if_due()

    def _seed_founders(self, count: int, *, birth_kind: str | None = None) -> None:
        archetypes = ("silt_grazer", "glass_filter", "mud_stalker", "reed_sprinter")
        for index in range(count):
            archetype = archetypes[index % len(archetypes)]
            lineage_id = self.next_lineage_id
            self.next_lineage_id += 1
            genome = FishGenome.founder(self.rng, lineage_id=lineage_id, archetype=archetype)
            x, y = self._spawn_position(archetype)
            fish = FishAgent(
                fish_id=self.next_fish_id,
                species_id=genome.species_id,
                lineage_id=lineage_id,
                genome=genome,
                x=x,
                y=y,
                vx=self.rng.uniform(-0.16, 0.16),
                vy=self.rng.uniform(-0.16, 0.16),
                energy=self.rng.uniform(48.0, 68.0),
                hunger=self.rng.uniform(0.18, 0.46),
                fear=self.rng.uniform(0.08, 0.28),
                stress=self.rng.uniform(0.08, 0.24),
                health=self.rng.uniform(0.76, 0.98),
                reproductive_drive=self.rng.uniform(0.05, 0.22),
                model_budget=self.config.fish_model_budget,
            )
            self.next_fish_id += 1
            self.fish.append(fish)
            if birth_kind == "debug_reseed":
                self.births += 1
                self.births_reseed_debug += 1
            elif birth_kind == "reproduction":
                self.births += 1
                self.births_reproduction += 1
        if count > 0:
            self.dead_puddle = False

    def _spawn_position(self, archetype: str) -> tuple[float, float]:
        for _ in range(200):
            if archetype == "glass_filter":
                x = self.rng.uniform(4.0, self.config.width - 5.0)
                y = self.rng.uniform(3.0, self.config.height * 0.42)
            elif archetype == "mud_stalker":
                x = self.rng.uniform(4.0, self.config.width - 5.0)
                y = self.rng.uniform(self.config.height * 0.45, self.config.height - 4.0)
            else:
                x = self.rng.uniform(4.0, self.config.width - 5.0)
                y = self.rng.uniform(4.0, self.config.height - 5.0)
            if not self.environment.is_obstacle(x, y):
                return (x, y)
        return (self.config.width / 2.0, self.config.height / 2.0)

    def _sense(self, fish: FishAgent) -> Perception:
        sample = self.environment.sample(fish.x, fish.y)
        stress = sample.stress_score(
            oxygen_need=fish.genome.oxygen_need,
            ph_preference=fish.genome.ph_preference,
            temperature_preference=fish.genome.temperature_preference,
            turbidity_tolerance=fish.genome.turbidity_tolerance,
            toxin_tolerance=fish.genome.toxin_tolerance,
        )
        gradients = {
            "food": self.environment.gradient(fish.x, fish.y, "food"),
            "plankton": self.environment.gradient(fish.x, fish.y, "plankton"),
            "oxygen": self.environment.gradient(fish.x, fish.y, "oxygen"),
            "shelter": self.environment.gradient(fish.x, fish.y, "shelter"),
            "stress": self._stress_gradient(fish),
            "current": self.environment.current_at(fish.x, fish.y),
        }
        neighbors = self._neighbor_vectors(fish)
        edge_vector = self._edge_vector(fish)
        return Perception(
            sample=sample.payload(),
            gradients=gradients,
            nearest_food=self._best_resource_vector(fish),
            nearest_shelter=self._best_field_vector(fish, "shelter", prefer_high=True, radius=fish.genome.sensory_range),
            nearest_mate=neighbors["mate"],
            nearest_prey=neighbors["prey"],
            nearest_threat=neighbors["threat"],
            neighbor_count=int(neighbors["count"][2]),
            crowding=sample.population_pressure,
            stress=stress,
            resource_score=sample.resource_score(),
            reproduction_score=sample.reproduction,
            edge_vector=edge_vector,
        )

    def _stress_gradient(self, fish: FishAgent) -> tuple[float, float]:
        oxygen_dx, oxygen_dy = self.environment.gradient(fish.x, fish.y, "oxygen")
        toxin_dx, toxin_dy = self.environment.gradient(fish.x, fish.y, "toxins")
        turb_dx, turb_dy = self.environment.gradient(fish.x, fish.y, "turbidity")
        pressure_dx, pressure_dy = self.environment.gradient(fish.x, fish.y, "population_pressure")
        return (
            toxin_dx * 0.80 + turb_dx * 0.30 + pressure_dx * 0.25 - oxygen_dx * 0.55,
            toxin_dy * 0.80 + turb_dy * 0.30 + pressure_dy * 0.25 - oxygen_dy * 0.55,
        )

    def _edge_vector(self, fish: FishAgent) -> tuple[float, float]:
        margin = 7.0
        dx = 0.0
        dy = 0.0
        if fish.x < margin:
            dx += (margin - fish.x) / margin
        elif fish.x > self.config.width - margin:
            dx -= (fish.x - (self.config.width - margin)) / margin
        if fish.y < margin:
            dy += (margin - fish.y) / margin
        elif fish.y > self.config.height - margin:
            dy -= (fish.y - (self.config.height - margin)) / margin
        return unit(dx, dy)

    def _best_resource_vector(self, fish: FishAgent) -> tuple[float, float, float]:
        field = "food"
        if fish.genome.metabolism == "filter":
            field = "plankton"
        elif fish.genome.metabolism == "scavenger":
            field = "decomposition"
        return self._best_field_vector(fish, field, prefer_high=True, radius=fish.genome.sensory_range)

    def _best_field_vector(self, fish: FishAgent, field_name: str, *, prefer_high: bool, radius: float) -> tuple[float, float, float]:
        ix = int(round(fish.x))
        iy = int(round(fish.y))
        best_value = -1.0 if prefer_high else 2.0
        best: tuple[float, float, float] = (0.0, 0.0, radius * 2.0)
        step = 2
        grid = self.environment.fields[field_name]
        r = max(2, int(radius))
        for yy in range(max(0, iy - r), min(self.environment.height, iy + r + 1), step):
            for xx in range(max(0, ix - r), min(self.environment.width, ix + r + 1), step):
                distance = hypot(xx - fish.x, yy - fish.y)
                if distance > radius or self.environment.fields["obstacle"][yy][xx] >= 0.75:
                    continue
                value = grid[yy][xx] - distance * 0.006
                if (prefer_high and value > best_value) or (not prefer_high and value < best_value):
                    best_value = value
                    dx, dy = unit(xx - fish.x, yy - fish.y)
                    best = (dx, dy, distance)
        return best

    def _neighbor_vectors(self, fish: FishAgent) -> dict[str, tuple[float, float, float]]:
        nearest_mate = (0.0, 0.0, 999.0)
        nearest_prey = (0.0, 0.0, 999.0)
        nearest_threat = (0.0, 0.0, 999.0)
        count = 0
        for other in self.fish:
            if other.fish_id == fish.fish_id:
                continue
            distance = hypot(other.x - fish.x, other.y - fish.y)
            if distance > max(3.0, fish.genome.sensory_range * 1.6):
                continue
            count += 1
            dx, dy = unit(other.x - fish.x, other.y - fish.y)
            if other.species_id == fish.species_id and distance < nearest_mate[2]:
                nearest_mate = (dx, dy, distance)
            if other.radius < fish.radius * 0.82 and distance < nearest_prey[2]:
                nearest_prey = (dx, dy, distance)
            threat_score = other.genome.aggression + other.radius * 0.06
            if threat_score > fish.genome.aggression + fish.radius * 0.04 and distance < nearest_threat[2]:
                nearest_threat = (dx, dy, distance)
        return {
            "mate": nearest_mate,
            "prey": nearest_prey,
            "threat": nearest_threat,
            "count": (0.0, 0.0, float(count)),
        }

    def _select_action(self, fish: FishAgent, perception: Perception, deliberations_used: int) -> Action:
        reflex = fish.reflex_action(perception)
        if reflex is not None:
            return reflex
        habit = fish.heuristic_action(perception, self.rng)
        if fish.model_intent is not None and fish.model_intent_ttl > 0:
            intent = fish.model_intent.normalized()
            return Action(
                intent.kind,
                intent.dx,
                intent.dy,
                intent.intensity,
                "model",
                f"{intent.reason} ttl={fish.model_intent_ttl}",
                intent.confidence,
            ).normalized()
        if deliberations_used + self._queued_deliberations_this_tick >= self.config.global_deliberations_per_tick:
            return habit
        if fish.model_pending or fish.fish_id in self._pending_model_calls:
            self.model_skipped_pending += 1
            return habit
        if not fish.should_deliberate(perception, self.rng, global_enabled=self.config.deliberation_enabled):
            return habit
        if self.tick % max(1, self.config.deliberation_interval_ticks) != fish.fish_id % max(1, self.config.deliberation_interval_ticks):
            return habit
        self._queue_deliberation(fish, perception)
        return habit

    def _deliberation_controller(self) -> FishDeliberationController:
        if self._controller is None:
            self._controller = FishDeliberationController(
                base_url=self.config.llm_base_url,
                api_key=self.config.llm_api_key,
                model=self.config.llm_model,
                timeout_seconds=self.config.llm_timeout_seconds,
                max_retries=self.config.llm_max_retries,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
                trace_backend=self.config.trace_backend,
                trace_jsonl_path=self.config.trace_jsonl_path,
            )
        return self._controller

    def _queue_deliberation(self, fish: FishAgent, perception: Perception) -> None:
        if fish.model_budget <= 0:
            self.model_skipped_budget += 1
            return
        if len(self._pending_model_calls) >= self.config.max_inflight_model_calls:
            self.model_skipped_pending += 1
            return
        controller = self._deliberation_controller()
        context = FishDeliberationController.build_context(fish=fish, perception=perception, tick=self.tick)
        future = self._model_executor_for_calls().submit(
            controller.deliberate_context,
            context,
            fish_id=fish.fish_id,
            tick=self.tick,
        )
        self._pending_model_calls[fish.fish_id] = future
        fish.model_budget -= 1
        fish.deliberation_cooldown = self.config.deliberation_interval_ticks
        fish.model_pending = True
        self.model_calls += 1
        self.model_queued += 1
        self._queued_deliberations_this_tick += 1
        self._event("model_deliberation_queued", fish_id=fish.fish_id, pending=len(self._pending_model_calls))

    def _model_executor_for_calls(self) -> ThreadPoolExecutor:
        if self._model_executor is None:
            self._model_executor = ThreadPoolExecutor(
                max_workers=max(1, self.config.max_inflight_model_calls),
                thread_name_prefix="aquagenesys-model",
            )
        return self._model_executor

    def _poll_model_results(self) -> None:
        completed: list[tuple[int, Future[FishDeliberationResult]]] = []
        for fish_id, future in self._pending_model_calls.items():
            if future.done():
                completed.append((fish_id, future))
        for fish_id, future in completed:
            self._pending_model_calls.pop(fish_id, None)
            fish = self._fish_by_id(fish_id)
            if fish is not None:
                fish.clear_model_pending()
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - defensive boundary around worker thread
                result = FishDeliberationResult(action=None, called=True, ok=False, error=str(exc)[:240])
            if result.ok and result.action is not None and fish is not None:
                action = result.action
                if fish.last_perception is not None:
                    action = self._adapt_model_action(action, fish.last_perception)
                fish.set_model_intent(action, ttl=self.config.model_intent_ttl)
                self.model_successes += 1
                self.model_intents_applied += 1
                self._event(
                    "model_deliberation",
                    fish_id=fish_id,
                    action=action.kind,
                    latency_ms=result.latency_ms,
                    ttl=self.config.model_intent_ttl,
                )
                continue
            self.model_failures += 1
            self.last_model_error = result.error or "invalid_action"
            self._event("model_deliberation_failed", fish_id=fish_id, error=self.last_model_error)

    def _fish_by_id(self, fish_id: int) -> FishAgent | None:
        for fish in self.fish:
            if fish.fish_id == fish_id:
                return fish
        return None

    def _cancel_pending_model_calls(self) -> None:
        for future in self._pending_model_calls.values():
            future.cancel()
        self._pending_model_calls.clear()
        if self._model_executor is not None:
            self._model_executor.shutdown(wait=False, cancel_futures=True)
            self._model_executor = None

    def close(self) -> None:
        self._cancel_pending_model_calls()

    def _adapt_model_action(self, action: Action, perception: Perception) -> Action:
        if abs(action.dx) + abs(action.dy) > 0.05:
            return action.normalized()
        dx, dy = perception.vector_for("food" if action.kind in {"forage", "eat"} else action.kind)
        if action.kind == "hunt":
            dx, dy = perception.vector_for("prey")
        elif action.kind == "flee":
            dx, dy = perception.vector_for("threat")
        elif action.kind == "shelter":
            dx, dy = perception.vector_for("shelter")
        elif action.kind == "court":
            dx, dy = perception.vector_for("mate")
        return Action(action.kind, dx, dy, action.intensity, action.source, action.reason, action.confidence).normalized()

    def _apply_action(self, fish: FishAgent, action: Action, perception: Perception, deaths: dict[int, str]) -> str:
        action = action.normalized()
        current_x, current_y = self.environment.current_at(fish.x, fish.y)
        thrust = 0.88 + fish.genome.tail_length * 0.20 - fish.genome.body_depth * 0.06
        maneuver = 0.86 + fish.genome.fin_span * 0.18 + fish.genome.tail_length * 0.04
        drag = 0.88 + fish.genome.body_depth * 0.11 + fish.genome.body_size * 0.05
        speed = fish.genome.max_speed * thrust * (0.48 + fish.health * 0.36 + max(0.0, 1.0 - fish.hunger) * 0.16)
        intensity = action.intensity
        if action.kind == "rest":
            intensity *= 0.18
        if action.kind in {"flee", "escape"}:
            intensity *= 1.25
        fish.vx = fish.vx * (0.54 + fish.genome.turning * 0.14) + action.dx * fish.genome.turning * maneuver * intensity * 0.34 + current_x
        fish.vy = fish.vy * (0.54 + fish.genome.turning * 0.14) + action.dy * fish.genome.turning * maneuver * intensity * 0.34 + current_y
        magnitude = hypot(fish.vx, fish.vy)
        if magnitude > speed:
            fish.vx = fish.vx / magnitude * speed
            fish.vy = fish.vy / magnitude * speed
        fish.x += fish.vx
        fish.y += fish.vy
        fish.x, fish.y, fish.vx, fish.vy = self.environment.keep_in_bounds(fish.x, fish.y, fish.vx, fish.vy)

        moved = abs(fish.vx) + abs(fish.vy)
        basal = 0.070 + fish.genome.body_size * 0.025
        fish.energy -= basal + moved * (0.105 + fish.genome.body_size * 0.018) * drag
        fish.energy -= perception.stress * 0.10
        fish.health = clamp(fish.health - perception.stress * 0.006 + max(0.0, perception.sample["oxygen"] - fish.genome.oxygen_need) * 0.002)
        self.environment.consume("oxygen", fish.x, fish.y, 0.0015 + fish.genome.oxygen_need * 0.002)
        self.environment.add("waste", fish.x, fish.y, 0.0018 + fish.genome.body_size * 0.0012)

        outcome = "moved"
        if action.kind in {"forage", "eat", "school", "explore"}:
            gain = self._feed_from_environment(fish)
            if gain > 0.18:
                outcome = "fed"
        if action.kind == "hunt":
            hunted = self._try_hunt(fish, deaths)
            if hunted:
                outcome = "successful_hunt"
        if action.kind == "shelter":
            shelter = self.environment.sample(fish.x, fish.y).shelter
            fish.fear = clamp(fish.fear - shelter * 0.060)
            fish.stress = clamp(fish.stress - shelter * 0.040)
            outcome = "sheltered" if shelter > 0.38 else outcome
        if action.kind == "rest":
            fish.energy = min(82.0, fish.energy + 0.06)
            fish.stress = clamp(fish.stress - 0.012)
            outcome = "rested"
        return outcome

    def _feed_from_environment(self, fish: FishAgent) -> float:
        metabolism = fish.genome.metabolism
        if metabolism == "filter":
            field = "plankton"
            multiplier = 9.5
        elif metabolism == "scavenger":
            field = "decomposition"
            multiplier = 7.0
        elif metabolism == "predator":
            field = "food"
            multiplier = 4.2
        else:
            field = "food"
            multiplier = 7.8
        taken = self.environment.consume(field, fish.x, fish.y, 0.020 + fish.genome.body_size * 0.016)
        nutrient_taken = self.environment.consume("nutrients", fish.x, fish.y, 0.004 + fish.genome.body_size * 0.004)
        gain = taken * multiplier + nutrient_taken * 2.5
        fish.energy = min(96.0, fish.energy + gain)
        fish.hunger = clamp(fish.hunger - gain * 0.026)
        return gain

    def _try_hunt(self, hunter: FishAgent, deaths: dict[int, str]) -> bool:
        candidates = [
            fish
            for fish in self.fish
            if fish.fish_id != hunter.fish_id
            and fish.fish_id not in deaths
            and fish.radius < hunter.radius * 0.92
            and hypot(fish.x - hunter.x, fish.y - hunter.y) < hunter.radius + fish.radius + 1.8
        ]
        if not candidates:
            return False
        target = min(candidates, key=lambda item: hypot(item.x - hunter.x, item.y - hunter.y))
        attack = hunter.genome.aggression + hunter.energy * 0.006 + hunter.genome.body_size * 0.20
        defense = target.genome.max_speed * 0.48 + target.health * 0.32 + target.genome.risk_tolerance * 0.14
        if attack * self.rng.uniform(0.70, 1.35) <= defense * self.rng.uniform(0.70, 1.25):
            hunter.energy -= 0.32
            return False
        deaths[target.fish_id] = "predation"
        hunter.energy = min(110.0, hunter.energy + max(4.0, target.energy * 0.54))
        hunter.hunger = clamp(hunter.hunger - 0.34)
        hunter.fear = clamp(hunter.fear + 0.08)
        return True

    def _maybe_reproduce(self, parent: FishAgent, perception: Perception) -> FishAgent | None:
        if len(self.fish) >= self.config.max_population:
            return None
        if parent.energy < 64.0 or parent.health < 0.58 or parent.reproductive_drive < 0.74:
            return None
        if perception.reproduction_score < 0.42 or perception.crowding > 0.76:
            return None
        chance = parent.genome.reproduction_rate * perception.reproduction_score * 0.035
        if self.rng.random() > chance:
            return None
        lineage_id = parent.lineage_id
        if self.rng.random() < 0.045 + max(0.0, parent.stress - 0.42) * 0.05:
            lineage_id = self.next_lineage_id
            self.next_lineage_id += 1
            self._event("lineage_split", parent=parent.fish_id, lineage=lineage_id)
        genome = parent.genome.mutated(self.rng, lineage_id=None if lineage_id == parent.lineage_id else lineage_id)
        dx = self.rng.uniform(-1.0, 1.0)
        dy = self.rng.uniform(-1.0, 1.0)
        dx, dy = unit(dx, dy)
        child = FishAgent(
            fish_id=self.next_fish_id,
            species_id=genome.species_id,
            lineage_id=genome.lineage_id,
            genome=genome,
            x=clamp(parent.x + dx * (parent.radius + 1.3), 0.8, self.config.width - 1.8),
            y=clamp(parent.y + dy * (parent.radius + 1.3), 0.8, self.config.height - 1.8),
            vx=parent.vx * 0.24 + dx * 0.12,
            vy=parent.vy * 0.24 + dy * 0.12,
            energy=34.0 + self.rng.uniform(0.0, 8.0),
            hunger=0.34,
            fear=parent.fear * 0.60,
            stress=parent.stress * 0.50,
            health=clamp(parent.health * 0.92 + 0.05),
            reproductive_drive=0.02,
            generation=parent.generation + 1,
            parent_ids=(parent.fish_id,),
            model_budget=max(1, self.config.fish_model_budget - 1),
        )
        self.next_fish_id += 1
        parent.energy -= 18.0
        parent.reproductive_drive = 0.12
        self.births += 1
        self.births_reproduction += 1
        self._event("birth", parent=parent.fish_id, child=child.fish_id, lineage=child.lineage_id)
        return child

    def _death_cause(self, fish: FishAgent) -> str | None:
        if fish.energy <= 0.0:
            return "starvation"
        if fish.health <= 0.0:
            return "environment"
        if fish.age > 1600 + int(fish.genome.body_size * 260) and self.rng.random() < 0.012:
            return "age"
        if fish.stress > 0.84 and self.rng.random() < (fish.stress - 0.80) * 0.06:
            return "shock"
        return None

    def _recycle_dead(self, fish: FishAgent, cause: str) -> None:
        fish.alive = False
        self.deaths_by_cause[cause] += 1
        self.environment.add("nutrients", fish.x, fish.y, min(0.75, 0.09 + fish.energy * 0.004 + fish.radius * 0.020))
        self.environment.add("decomposition", fish.x, fish.y, min(0.55, 0.08 + fish.radius * 0.026))
        self.environment.add("waste", fish.x, fish.y, 0.030)
        self._event("death", fish_id=fish.fish_id, cause=cause, lineage=fish.lineage_id)

    def _debug_reseed_if_needed(self) -> None:
        if not self.config.debug_founder_reseed_enabled:
            self.low_population_ticks = 0
            return
        if len(self.fish) >= self.config.debug_founder_reseed_min_population:
            self.low_population_ticks = 0
            return
        self.low_population_ticks += 1
        if self.low_population_ticks >= self.config.debug_founder_reseed_after_ticks:
            count = self.config.debug_founder_reseed_min_population
            self.recovery_events += 1
            self.last_recovery_kind = "debug_reseed"
            self._event("debug_founder_reseed", population=len(self.fish), count=count)
            self._seed_founders(count, birth_kind="debug_reseed")
            self.low_population_ticks = 0

    def _handle_extinction(self) -> None:
        if self.dead_puddle:
            return
        self.dead_puddle = True
        self.extinction_events += 1
        self.collapse_cause_guess = self._collapse_cause_guess()
        self._event("extinction", cause_guess=self.collapse_cause_guess)

    def _collapse_cause_guess(self) -> str:
        averages = self.environment.averages()
        if averages["oxygen"] < 0.18:
            return "oxygen_crash"
        if averages["food"] < 0.14 and averages["plankton"] < 0.14:
            return "resource_starvation"
        if averages["toxins"] > 0.48:
            return "toxin_accumulation"
        if averages["population_pressure"] > 0.62:
            return "crowding_pressure"
        if abs(averages["ph"] - 0.52) > 0.26:
            return "ph_shift"
        return "agent_lifecycle_pressure"

    def _record_decision(self, fish: FishAgent, action: Action, outcome: str) -> None:
        self.decision_log.append(
            {
                "tick": self.tick,
                "fish_id": fish.fish_id,
                "species_id": fish.species_id,
                "body_state": fish.body_state,
                "action": action.kind,
                "source": action.source,
                "reason": action.reason,
                "outcome": outcome,
                "energy": round(fish.energy, 2),
                "health": round(fish.health, 3),
                "budget": fish.model_budget,
            }
        )

    def _event(self, kind: str, **payload: object) -> None:
        self.events.append({"tick": self.tick, "kind": kind, **payload})

    def _archive_if_due(self) -> None:
        if self.config.archive_every_ticks <= 0:
            return
        if self.tick % self.config.archive_every_ticks != 0:
            return
        self.archive.write_snapshot(tick=self.tick, fish=self.fish)
        self.archive.write_decisions(tick=self.tick, fish=self.fish)

    def environmental_viability(self) -> tuple[float, int]:
        averages = self.environment.averages()
        total_score = 0.0
        viable = 0
        total_cells = self.environment.width * self.environment.height
        for y in range(self.environment.height):
            for x in range(self.environment.width):
                oxygen = self.environment.fields["oxygen"][y][x]
                food = self.environment.fields["food"][y][x]
                plankton = self.environment.fields["plankton"][y][x]
                toxins = self.environment.fields["toxins"][y][x]
                ph = self.environment.fields["ph"][y][x]
                pressure = self.environment.fields["population_pressure"][y][x]
                score = clamp(oxygen * 0.30 + food * 0.24 + plankton * 0.18 + averages["balance"] * 0.18 - toxins * 0.22 - abs(ph - 0.52) * 0.24 - pressure * 0.08)
                total_score += score
                if score >= 0.42:
                    viable += 1
        return total_score / max(1, total_cells), viable

    def telemetry(self) -> dict[str, Any]:
        population = len(self.fish)
        actions = Counter(entry["action"] for entry in self.decision_log)
        sources = Counter(entry["source"] for entry in self.decision_log)
        species = Counter(fish.species_id for fish in self.fish)
        metabolism = Counter(fish.genome.metabolism for fish in self.fish)
        viability_score, viable_cells = self.environmental_viability()
        return {
            "tick": self.tick,
            "population": population,
            "births": self.births,
            "births_reproduction": self.births_reproduction,
            "births_reseed_debug": self.births_reseed_debug,
            "deaths_by_cause": dict(self.deaths_by_cause),
            "extinction_events": self.extinction_events,
            "dead_puddle": self.dead_puddle,
            "recovery_events": self.recovery_events,
            "last_recovery_kind": self.last_recovery_kind,
            "collapse_cause_guess": self.collapse_cause_guess,
            "average_energy": round(sum(fish.energy for fish in self.fish) / max(1, population), 3),
            "average_hunger": round(sum(fish.hunger for fish in self.fish) / max(1, population), 3),
            "average_stress": round(sum(fish.stress for fish in self.fish) / max(1, population), 3),
            "average_health": round(sum(fish.health for fish in self.fish) / max(1, population), 3),
            "average_reproductive_drive": round(sum(fish.reproductive_drive for fish in self.fish) / max(1, population), 3),
            "dominant_metabolism": metabolism.most_common(1)[0][0] if metabolism else "none",
            "metabolism_counts": dict(metabolism),
            "species_clusters": [
                {
                    "label": f"S{index}",
                    "species_id": item[0],
                    "size": item[1],
                    "metabolism": next((fish.genome.metabolism for fish in self.fish if fish.species_id == item[0]), "unknown"),
                }
                for index, item in enumerate(species.most_common(8), start=1)
            ],
            "dominant_actions": [{"action": action, "count": count} for action, count in actions.most_common(8)],
            "decision_sources": dict(sources),
            "agent_decisions": list(reversed(self.decision_log))[:16],
            "recent_events": list(reversed(self.events))[:16],
            "model": {
                "enabled": self.config.deliberation_enabled,
                "base_url": self.config.llm_base_url,
                "model": self.config.llm_model,
                "calls": self.model_calls,
                "queued": self.model_queued,
                "successes": self.model_successes,
                "failures": self.model_failures,
                "pending": len(self._pending_model_calls),
                "skipped_budget": self.model_skipped_budget,
                "skipped_pending": self.model_skipped_pending,
                "intents_applied": self.model_intents_applied,
                "last_error": self.last_model_error,
            },
            "environmental_viability_score": round(viability_score, 4),
            "viable_cells_count": viable_cells,
            "archive": {
                "state_path": str(self.archive.state_path),
                "memory_path": str(self.archive.memory_path),
                "every_ticks": self.config.archive_every_ticks,
            },
        }

    def state(self) -> dict[str, Any]:
        return {
            "schema": "aquagenesys.state.v3",
            "tick": self.tick,
            "config": {
                "seed": self._initial_seed,
                "speed": self.speed,
                "max_population": self.config.max_population,
                "deliberation_enabled": self.config.deliberation_enabled,
                "deliberation_interval_ticks": self.config.deliberation_interval_ticks,
                "fish_model_budget": self.config.fish_model_budget,
                "model_intent_ttl": self.config.model_intent_ttl,
                "ecology_update_interval": self.config.ecology_update_interval,
            },
            "environment": self.environment.payload(),
            "fish": [fish.payload() for fish in self.fish],
            "organisms": [fish.payload() for fish in self.fish],
            "telemetry": self.telemetry(),
        }

    def frame_state(self) -> dict[str, Any]:
        return {
            "schema": "aquagenesys.frame.v1",
            "tick": self.tick,
            "config": {
                "seed": self._initial_seed,
                "speed": self.speed,
                "deliberation_enabled": self.config.deliberation_enabled,
            },
            "environment": {
                "width": self.environment.width,
                "height": self.environment.height,
                "signature": list(self.environment.signature),
            },
            "fish": [fish.frame_payload() for fish in self.fish],
            "telemetry": {
                "tick": self.tick,
                "population": len(self.fish),
                "dead_puddle": self.dead_puddle,
                "average_health": round(sum(fish.health for fish in self.fish) / max(1, len(self.fish)), 3),
                "average_stress": round(sum(fish.stress for fish in self.fish) / max(1, len(self.fish)), 3),
                "decision_sources": dict(Counter(entry["source"] for entry in self.decision_log)),
                "agent_decisions": list(reversed(self.decision_log))[:8],
                "recent_events": list(reversed(self.events))[:8],
                "model": {
                    "enabled": self.config.deliberation_enabled,
                    "model": self.config.llm_model,
                    "calls": self.model_calls,
                    "queued": self.model_queued,
                    "successes": self.model_successes,
                    "failures": self.model_failures,
                    "pending": len(self._pending_model_calls),
                    "intents_applied": self.model_intents_applied,
                    "last_error": self.last_model_error,
                },
            },
        }
