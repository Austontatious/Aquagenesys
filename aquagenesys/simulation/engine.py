from __future__ import annotations

from collections import Counter, deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from math import atan2, cos, hypot, sin
from pathlib import Path
from random import Random
from typing import Any, Sequence

from aquagenesys.agents import Action, FishAgent, FishDeliberationController, FishDeliberationResult, FishGenome, Perception
from aquagenesys.agents.behavior import BEHAVIOR_SCHEMA, behavior_state_payload, build_behavior_decision, summarize_behavior_payload
from aquagenesys.agents.fish import clamp, unit, wrap_angle
from aquagenesys.agents.instructions import (
    BehaviorInstructionGenome,
    InstructionPatchDecision,
    TaughtSkill,
    inherit_taught_skills,
    rule_generated_patch,
    stable_hash,
    validate_instruction_patch,
)
from aquagenesys.agents.morphology import MORPHOLOGY_SCHEMA, morphology_state_payload
from aquagenesys.environment.puddle import EnvironmentConfig, PuddleEnvironment
from aquagenesys.simulation.dashboard import build_observatory_dashboard
from aquagenesys.simulation.egg import EggEntity
from aquagenesys.simulation.genealogy import build_genealogy
from aquagenesys.simulation.lineage_story import build_lineage_story
from aquagenesys.simulation.skill_evidence import (
    SkillUseEvidence,
    aggregate_skill_evidence,
    classify_skill_outcome,
    matched_skills_for_action,
    skill_identity,
    skill_source,
)
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
    instruction_inheritance_enabled: bool = True
    model_teaching_enabled: bool = False
    debug_founder_reseed_enabled: bool = False
    debug_founder_reseed_min_population: int = 8
    debug_founder_reseed_after_ticks: int = 80


@dataclass
class ReproductionResult:
    newborns: list[FishAgent]
    eggs: list[EggEntity]
    reason: str
    mode: str = "none"


class AquagenesysSimulation:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.speed = 1
        self._initial_seed = self.config.seed
        self._run_sequence = 0
        self._controller: FishDeliberationController | None = None
        self._model_executor: ThreadPoolExecutor | None = None
        self._pending_model_calls: dict[int, Future[FishDeliberationResult]] = {}
        self.reset()

    def reset(self) -> None:
        self._cancel_pending_model_calls()
        self.rng = Random(self._initial_seed)
        self._run_sequence += 1
        self.run_id = f"seed-{self._initial_seed}-run-{self._run_sequence}"
        self.tick = 0
        self.next_fish_id = 1
        self.next_egg_id = 1
        self.next_lineage_id = 1
        self.low_population_ticks = 0
        self.dead_puddle = False
        self.biosphere_state = "active"
        self._dormant_announced = False
        self.decision_log: deque[dict[str, Any]] = deque(maxlen=36)
        self.events: deque[dict[str, Any]] = deque(maxlen=36)
        self.reproduction_log: deque[dict[str, Any]] = deque(maxlen=48)
        self.instruction_log: deque[dict[str, Any]] = deque(maxlen=64)
        self.skill_evidence_log: deque[dict[str, Any]] = deque(maxlen=160)
        self.births = 0
        self.births_reproduction = 0
        self.births_hatched = 0
        self.births_reseed_debug = 0
        self.eggs_laid = 0
        self.eggs_hatched = 0
        self.egg_deaths = 0
        self.egg_deaths_by_cause: Counter[str] = Counter()
        self.reproduction_gate_reasons: Counter[str] = Counter()
        self.instruction_patches_proposed = 0
        self.instruction_patches_accepted = 0
        self.instruction_patches_rejected = 0
        self.teaching_events = 0
        self.instruction_inheritance_events = 0
        self.instruction_rejection_reasons: Counter[str] = Counter()
        self.agent_code_snapshots = 0
        self.dead_agent_summaries: dict[int, dict[str, Any]] = {}
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
        self._completed_model_results_this_tick = 0
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
            lifecycle_path=archive_root / "lifecycle_events.jsonl",
        )
        self.fish: list[FishAgent] = []
        self.eggs: list[EggEntity] = []
        self._seed_founders(self.config.initial_population)
        self.archive.write_lifecycle_event(
            {
                "run_id": self.run_id,
                "tick": self.tick,
                "event_type": "run_start",
                "initial_population": self.config.initial_population,
                "seed": self._initial_seed,
                "archive_every_ticks": self.config.archive_every_ticks,
                "instruction_inheritance_enabled": self.config.instruction_inheritance_enabled,
                "model_teaching_enabled": self.config.model_teaching_enabled,
            }
        )
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
                    fish.genome.morphology_hash,
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

    def propose_offspring_instruction_patch(self, fish_id: int, proposal: dict[str, Any]) -> InstructionPatchDecision:
        fish = self._fish_by_id(fish_id)
        if fish is None:
            patch_id = stable_hash({"fish_id": fish_id, "proposal": proposal}, length=16)
            return InstructionPatchDecision(False, "fish_not_found", patch_id)
        return self._validate_and_record_instruction_patch(fish, proposal)

    def run(self, ticks: int) -> None:
        for _ in range(max(0, ticks)):
            self.step()

    def step(self) -> None:
        self.tick += 1
        self.environment.update()
        completed_deliberations = self._poll_model_results()
        hatchlings = self._update_eggs()
        if hatchlings:
            remaining = max(0, self.config.max_population - len(self.fish))
            self.fish.extend(hatchlings[:remaining])
            for child in hatchlings[remaining:]:
                self._recycle_dead(child, "density_limit")
        for signal in self.environment.event_signals:
            self._event(str(signal["kind"]), value=signal.get("value"))
        if not self.fish:
            self._debug_reseed_if_needed()
            if not self.fish:
                self._handle_no_adults()
            self._archive_if_due()
            return

        self.environment.apply_population_pressure((fish.x, fish.y, fish.radius) for fish in self.fish)
        deliberations_used = completed_deliberations
        self._queued_deliberations_this_tick = 0
        deaths: dict[int, str] = {}
        newborns: list[FishAgent] = []
        new_eggs: list[EggEntity] = []
        shuffled = list(self.fish)
        self.rng.shuffle(shuffled)
        for fish in shuffled:
            if fish.fish_id in deaths:
                continue
            perception = self._sense(fish)
            fish.update_internal_state(perception)
            before_energy = fish.energy
            before_health = fish.health
            before_hunger = fish.hunger
            before_stress = fish.stress
            before_fear = fish.fear
            before_reproductive_drive = fish.reproductive_drive
            action = self._select_action(fish, perception, deliberations_used)
            if action.source == "model":
                deliberations_used += 1
            skill_matches = matched_skills_for_action(fish, perception, action)
            outcome = self._apply_action(fish, action, perception, deaths)
            if skill_matches:
                self._record_skill_use_outcomes(
                    fish,
                    perception,
                    action,
                    outcome,
                    before={
                        "energy": before_energy,
                        "health": before_health,
                        "hunger": before_hunger,
                        "stress": before_stress,
                        "fear": before_fear,
                        "reproductive_drive": before_reproductive_drive,
                    },
                    matches=skill_matches,
                )
            fish.record_outcome(
                self.tick,
                action,
                outcome=outcome,
                delta_energy=fish.energy - before_energy,
                delta_health=fish.health - before_health,
            )
            self._record_decision(fish, action, outcome)
            result = self._maybe_reproduce(fish, perception)
            if result.newborns:
                newborns.extend(result.newborns)
            if result.eggs:
                new_eggs.extend(result.eggs)
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
        if new_eggs:
            self.eggs.extend(new_eggs)
        self._debug_reseed_if_needed()
        if not self.fish:
            self._handle_no_adults()
        else:
            self.dead_puddle = False
            self.biosphere_state = "active"
        self._archive_if_due()

    def _seed_founders(self, count: int, *, birth_kind: str | None = None) -> None:
        archetypes = ("silt_grazer", "glass_filter", "mud_stalker", "reed_sprinter")
        for index in range(count):
            archetype = archetypes[index % len(archetypes)]
            lineage_id = self.next_lineage_id
            self.next_lineage_id += 1
            genome = FishGenome.founder(self.rng, lineage_id=lineage_id, archetype=archetype)
            instruction_genome = BehaviorInstructionGenome.founder(self.rng, biological_genome=genome)
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
                instruction_genome=instruction_genome,
                model_budget=self.config.fish_model_budget,
            )
            if abs(fish.vx) + abs(fish.vy) > 0.001:
                fish.heading = atan2(fish.vy, fish.vx)
                fish.locomotion_speed = hypot(fish.vx, fish.vy)
            self.next_fish_id += 1
            self.fish.append(fish)
            self._record_agent_code_snapshot(fish, event_type="founder_birth")
            if birth_kind == "debug_reseed":
                self.births += 1
                self.births_reseed_debug += 1
            elif birth_kind == "reproduction":
                self.births += 1
                self.births_reproduction += 1
        if count > 0:
            self.dead_puddle = False
            self.biosphere_state = "active"
            self._dormant_announced = False

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
            oxygen_need=fish.effective_oxygen_need,
            ph_preference=fish.genome.ph_preference,
            temperature_preference=fish.genome.temperature_preference,
            turbidity_tolerance=fish.genome.turbidity_tolerance,
            toxin_tolerance=fish.effective_toxin_tolerance,
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
            nearest_shelter=self._best_field_vector(fish, "shelter", prefer_high=True, radius=fish.effective_sensory_range),
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
        affordances = fish.morphology_affordances
        field = "food"
        if affordances.filter_rate > max(0.58, affordances.scrape_rate, affordances.bite_force):
            field = "plankton"
        elif fish.genome.metabolism == "filter":
            field = "plankton"
        elif fish.genome.metabolism == "scavenger" or (affordances.reach > 0.62 and affordances.grip > 0.50):
            field = "decomposition"
        return self._best_field_vector(fish, field, prefer_high=True, radius=fish.effective_sensory_range)

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
        sensory_radius = fish.effective_sensory_range
        fish_affordances = fish.morphology_affordances
        for other in self.fish:
            if other.fish_id == fish.fish_id:
                continue
            distance = hypot(other.x - fish.x, other.y - fish.y)
            if distance > max(3.0, sensory_radius * 1.6):
                continue
            count += 1
            dx, dy = unit(other.x - fish.x, other.y - fish.y)
            compatible_mate = other.species_id == fish.species_id or other.genome.metabolism == fish.genome.metabolism
            if compatible_mate and distance < nearest_mate[2]:
                nearest_mate = (dx, dy, distance)
            if other.radius < fish.radius * (0.76 + fish_affordances.reach * 0.10) and distance < nearest_prey[2]:
                nearest_prey = (dx, dy, distance)
            other_affordances = other.morphology_affordances
            threat_score = other.genome.aggression + other.radius * 0.04 + other_affordances.bite_force * 0.28 + other_affordances.toxin_payload * other_affordances.toxin_delivery * 0.18
            self_defense = fish.genome.aggression + fish.radius * 0.03 + fish_affordances.armor_protection * 0.20 + fish_affordances.toxin_payload * fish_affordances.toxin_delivery * 0.12
            if threat_score > self_defense and distance < nearest_threat[2]:
                nearest_threat = (dx, dy, distance)
        return {
            "mate": nearest_mate,
            "prey": nearest_prey,
            "threat": nearest_threat,
            "count": (0.0, 0.0, float(count)),
        }

    def _select_action(self, fish: FishAgent, perception: Perception, deliberations_used: int) -> Action:
        decision = build_behavior_decision(
            fish,
            perception,
            self.rng,
            biosphere_state=self.biosphere_state,
            population=len(self.fish),
        )
        reflex = fish.reflex_action(perception)
        if reflex is not None:
            self._store_behavior_rationale(fish, decision.payload(), reflex, override="reflex override")
            return reflex
        habit = decision.to_action()
        self._store_behavior_rationale(fish, decision.payload(), habit)
        if fish.model_intent is not None and fish.model_intent_ttl > 0:
            intent = fish.model_intent.normalized()
            model_action = Action(
                intent.kind,
                intent.dx,
                intent.dy,
                intent.intensity,
                "model",
                f"{intent.reason} ttl={fish.model_intent_ttl}",
                intent.confidence,
            ).normalized()
            self._store_behavior_rationale(fish, decision.payload(), model_action, override="model intent override")
            return model_action
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

    def _store_behavior_rationale(self, fish: FishAgent, rationale: dict[str, Any], action: Action, *, override: str = "") -> None:
        payload = dict(rationale)
        payload["schema"] = BEHAVIOR_SCHEMA
        payload["current_action"] = action.kind
        payload["action_reason"] = action.reason
        payload["source"] = action.source
        if override:
            warnings = list(payload.get("mismatch_warnings", []))
            warnings.append(override)
            payload["mismatch_warnings"] = warnings[:6]
        fish.last_behavior_rationale = payload

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

    def _poll_model_results(self) -> int:
        self._completed_model_results_this_tick = 0
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
                self._completed_model_results_this_tick += 1
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
            self._completed_model_results_this_tick += 1
            self._event("model_deliberation_failed", fish_id=fish_id, error=self.last_model_error)
        return self._completed_model_results_this_tick

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
        affordances = fish.morphology_affordances
        thrust = (0.78 + fish.genome.tail_length * 0.13 - fish.genome.body_depth * 0.04) * affordances.thrust_modifier
        maneuver = 0.78 + fish.genome.fin_span * 0.13 + fish.genome.tail_length * 0.03 - affordances.turn_penalty * 0.14
        drag = 0.78 + affordances.drag * 0.42 + fish.genome.body_depth * 0.04 + fish.genome.body_size * 0.03
        speed_cap = fish.genome.max_speed * thrust * (0.48 + fish.health * 0.36 + max(0.0, 1.0 - fish.hunger) * 0.16)
        intensity = action.intensity
        if action.kind == "rest":
            intensity *= 0.18
        if action.kind in {"anchor_feed", "chemical_defense"}:
            intensity *= 0.22
        if action.kind == "filter_feed":
            intensity *= 0.42
        if action.kind in {"flee", "escape"}:
            intensity *= 1.25
        desired_dx = action.dx * max(0.05, intensity) + current_x * 0.40
        desired_dy = action.dy * max(0.05, intensity) + current_y * 0.40
        desired_magnitude = hypot(desired_dx, desired_dy)
        if desired_magnitude > 0.025:
            desired_heading = atan2(desired_dy, desired_dx)
        elif abs(fish.vx) + abs(fish.vy) > 0.015:
            desired_heading = atan2(fish.vy, fish.vx)
        else:
            desired_heading = fish.heading
        turn_delta = wrap_angle(desired_heading - fish.heading)
        turn_capacity = max(0.06, (0.10 + fish.genome.turning * 0.24 + fish.genome.fin_span * 0.06 + maneuver * 0.03) - affordances.turn_penalty * 0.08)
        applied_turn = max(-turn_capacity, min(turn_capacity, turn_delta))
        heading = wrap_angle(fish.heading + fish.turn_rate * 0.48 + applied_turn * 0.52)
        forward_x = cos(heading)
        forward_y = sin(heading)
        side_x = -forward_y
        side_y = forward_x
        current_forward = fish.vx * forward_x + fish.vy * forward_y
        current_lateral = fish.vx * side_x + fish.vy * side_y
        target_speed = speed_cap * clamp(0.18 + intensity * 0.86, 0.0, 1.18)
        acceleration = (target_speed - current_forward) * (0.16 + fish.genome.max_speed * 0.07 + fish.genome.tail_length * 0.04 + affordances.thrust_modifier * 0.04)
        forward_speed = current_forward + acceleration
        lateral_speed = current_lateral * (0.55 - min(0.16, fish.genome.fin_span * 0.08))
        fish.vx = forward_x * forward_speed + side_x * lateral_speed + current_x * 0.34
        fish.vy = forward_y * forward_speed + side_y * lateral_speed + current_y * 0.34
        magnitude = hypot(fish.vx, fish.vy)
        if magnitude > speed_cap:
            fish.vx = fish.vx / magnitude * speed_cap
            fish.vy = fish.vy / magnitude * speed_cap
        fish.x += fish.vx
        fish.y += fish.vy
        fish.x, fish.y, fish.vx, fish.vy = self.environment.keep_in_bounds(fish.x, fish.y, fish.vx, fish.vy)
        actual_speed = hypot(fish.vx, fish.vy)
        fish.update_locomotion_state(speed=actual_speed, target_speed=target_speed, turn_delta=applied_turn)

        moved = abs(fish.vx) + abs(fish.vy)
        basal = 0.058 + fish.genome.body_size * 0.018 + affordances.metabolic_burden * 0.036 + affordances.oxygen_cost * 0.018
        fish.energy -= basal + moved * (0.092 + fish.genome.body_size * 0.014 + affordances.drag * 0.030) * drag
        fish.energy -= perception.stress * 0.10
        fish.health = clamp(
            fish.health
            - perception.stress * 0.006
            - max(0.0, 0.28 - affordances.viability_index) * 0.0025
            + max(0.0, perception.sample["oxygen"] - fish.effective_oxygen_need) * 0.002
        )
        self.environment.consume("oxygen", fish.x, fish.y, 0.0013 + fish.effective_oxygen_need * 0.0024 + affordances.oxygen_cost * 0.0009)
        self.environment.add("waste", fish.x, fish.y, 0.0016 + fish.genome.body_size * 0.0010 + affordances.metabolic_burden * 0.0012)

        outcome = "moved"
        if action.kind in {"forage", "eat", "school", "explore", "filter_feed", "graze", "scavenge", "anchor_feed"}:
            gain = self._feed_from_environment(fish, action.kind)
            if gain > 0.18:
                outcome = "fed"
        if action.kind in {"hunt", "strike"}:
            hunted = self._try_hunt(fish, deaths)
            if hunted:
                outcome = "successful_hunt"
        if action.kind == "chemical_defense":
            toxin_effect = affordances.toxin_payload * affordances.toxin_delivery
            fish.energy -= 0.08 + affordances.metabolic_burden * 0.05 + toxin_effect * 0.12
            fish.health = clamp(fish.health - affordances.toxin_self_cost * 0.010)
            fish.fear = clamp(fish.fear - toxin_effect * 0.10)
            fish.stress = clamp(fish.stress - toxin_effect * 0.040 + affordances.toxin_self_cost * 0.010)
            outcome = "chemical_defense"
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

    def _feed_from_environment(self, fish: FishAgent, action_kind: str = "forage") -> float:
        affordances = fish.morphology_affordances
        metabolism = fish.genome.metabolism
        if action_kind == "filter_feed":
            field = "plankton"
            multiplier = 6.8 + affordances.filter_rate * 4.8 + affordances.suction_force * 1.4
            bite_amount = 0.012 + affordances.filter_rate * 0.024
        elif action_kind == "scavenge":
            field = "decomposition"
            multiplier = 5.0 + affordances.reach * 2.0 + affordances.grip * 2.4
            bite_amount = 0.010 + affordances.reach * 0.012 + affordances.grip * 0.014
        elif action_kind == "graze":
            field = "food"
            multiplier = 5.6 + affordances.scrape_rate * 3.3 + affordances.feeding_throughput * 0.9
            bite_amount = 0.012 + affordances.scrape_rate * 0.018
        elif action_kind == "anchor_feed":
            field = "decomposition" if affordances.reach > 0.62 and affordances.grip > 0.48 else "plankton" if affordances.filter_rate > affordances.scrape_rate else "food"
            multiplier = 4.9 + max(affordances.reach, affordances.filter_rate, affordances.scrape_rate) * 3.0
            bite_amount = 0.010 + max(affordances.reach, affordances.filter_rate, affordances.scrape_rate) * 0.012
        elif affordances.filter_rate > max(0.58, affordances.scrape_rate, affordances.bite_force):
            field = "plankton"
            multiplier = 6.7 + affordances.filter_rate * 4.2 + affordances.suction_force * 1.2
            bite_amount = 0.014 + affordances.filter_rate * 0.022
        elif metabolism == "filter":
            field = "plankton"
            multiplier = 7.0 + affordances.filter_rate * 3.0
            bite_amount = 0.015 + affordances.filter_rate * 0.018
        elif metabolism == "scavenger" or (affordances.reach > 0.62 and affordances.grip > 0.48):
            field = "decomposition"
            multiplier = 5.2 + affordances.reach * 1.8 + affordances.grip * 2.2
            bite_amount = 0.012 + affordances.reach * 0.010 + affordances.grip * 0.012
        elif metabolism == "predator":
            field = "food"
            multiplier = 3.2 + affordances.bite_force * 2.2 + affordances.suction_force * 0.7
            bite_amount = 0.010 + affordances.bite_force * 0.014
        else:
            field = "food"
            multiplier = 5.8 + max(affordances.scrape_rate, affordances.filter_rate) * 2.5 + affordances.feeding_throughput * 1.2
            bite_amount = 0.014 + affordances.feeding_throughput * 0.018
        taken = self.environment.consume(field, fish.x, fish.y, bite_amount + fish.genome.body_size * 0.008)
        nutrient_taken = self.environment.consume("nutrients", fish.x, fish.y, 0.003 + affordances.scrape_rate * 0.004 + fish.genome.body_size * 0.002)
        gain = taken * multiplier + nutrient_taken * 2.5
        fish.energy = min(96.0, fish.energy + gain)
        fish.hunger = clamp(fish.hunger - gain * (0.018 + affordances.feeding_throughput * 0.010))
        return gain

    def _try_hunt(self, hunter: FishAgent, deaths: dict[int, str]) -> bool:
        hunter_affordances = hunter.morphology_affordances
        candidates = [
            fish
            for fish in self.fish
            if fish.fish_id != hunter.fish_id
            and fish.fish_id not in deaths
            and fish.radius < hunter.radius * (0.84 + hunter_affordances.bite_force * 0.10 + hunter_affordances.reach * 0.06)
            and hypot(fish.x - hunter.x, fish.y - hunter.y) < hunter.radius + fish.radius + 1.1 + hunter_affordances.reach * 1.4
        ]
        if not candidates:
            return False
        target = min(candidates, key=lambda item: hypot(item.x - hunter.x, item.y - hunter.y))
        target_affordances = target.morphology_affordances
        attack = (
            hunter.genome.aggression
            + hunter.energy * 0.005
            + hunter.genome.body_size * 0.12
            + hunter_affordances.bite_force * 0.40
            + hunter_affordances.strike_impulse * 0.25
            + hunter_affordances.toxin_payload * hunter_affordances.toxin_delivery * 0.18
            + hunter_affordances.reach * 0.08
            - hunter_affordances.drag * 0.08
        )
        defense = (
            target.genome.max_speed * 0.34
            + target.health * 0.28
            + target.genome.risk_tolerance * 0.12
            + target_affordances.armor_protection * 0.44
            + target_affordances.thrust_modifier * 0.08
            + max(0.0, 1.0 - target_affordances.predation_risk_modifier) * 0.18
        )
        if attack * self.rng.uniform(0.70, 1.35) <= defense * self.rng.uniform(0.70, 1.25):
            hunter.energy -= 0.28 + hunter_affordances.metabolic_burden * 0.12
            toxin_contact = target_affordances.toxin_payload * target_affordances.toxin_delivery * max(0.0, 1.0 - hunter_affordances.toxin_resistance)
            if toxin_contact > 0.05:
                hunter.health = clamp(hunter.health - toxin_contact * 0.035)
            return False
        deaths[target.fish_id] = "predation"
        hunter.energy = min(110.0, hunter.energy + max(4.0, target.energy * 0.54))
        hunter.hunger = clamp(hunter.hunger - 0.34)
        hunter.fear = clamp(hunter.fear + 0.08)
        toxin_contact = target_affordances.toxin_payload * target_affordances.toxin_delivery * max(0.0, 1.0 - hunter_affordances.toxin_resistance)
        if toxin_contact > 0.05:
            hunter.health = clamp(hunter.health - toxin_contact * 0.055)
        return True

    def _maybe_reproduce(self, parent: FishAgent, perception: Perception) -> ReproductionResult:
        gate = self._reproduction_gate(parent, perception)
        if gate != "ready":
            self._record_reproduction_gate(parent, gate, perception)
            return ReproductionResult([], [], gate)

        life = parent.life_history
        has_mate = self._mate_contact(parent, perception)
        parthenogenetic = False
        if not has_mate:
            if not self._parthenogenesis_triggered(parent, perception):
                self._record_reproduction_gate(parent, "parthenogenesis_failed_rng", perception, mode="parthenogenesis")
                return ReproductionResult([], [], "parthenogenesis_failed_rng", mode="parthenogenesis")
            parthenogenetic = True
        mode = "parthenogenesis" if parthenogenetic else "paired"
        chance = parent.genome.reproduction_rate * perception.reproduction_score * 0.085
        chance += max(0.0, parent.reproductive_drive - 0.34) * 0.070
        chance += max(0.0, 10 - len(self.fish)) * 0.0035
        if parthenogenetic:
            chance *= 0.36 + parent.life_history.parthenogenesis_alleles * 0.22
        if self.rng.random() > clamp(chance, 0.006, 0.34):
            reason = "parthenogenesis_failed_rng" if parthenogenetic else "reproduction_failed_rng"
            self._record_reproduction_gate(parent, reason, perception, mode=mode, chance=chance)
            return ReproductionResult([], [], reason, mode=mode)

        affordances = parent.morphology_affordances
        reserve = 18.0 + parent.genome.body_size * 5.0 + affordances.reproduction_cost * 4.5 + affordances.metabolic_burden * 2.0
        available = max(0.0, parent.energy - reserve)
        reproductive_energy = min(parent.energy - 22.0, available * life.offspring_investment)
        if parthenogenetic:
            reproductive_energy *= 0.74
        if reproductive_energy < 4.8:
            self._record_reproduction_gate(parent, "clutch_energy_too_low", perception, mode=mode)
            return ReproductionResult([], [], "clutch_energy_too_low", mode=mode)

        env_quality = clamp(perception.reproduction_score * 0.62 + parent.health * 0.22 + parent.energy / 110.0 * 0.16 - parent.stress * 0.14)
        clutch_target = max(1, int(round(life.base_clutch_size * (0.45 + env_quality * 0.82 - affordances.reproduction_cost * 0.10 - affordances.juvenile_fragility * 0.06))))
        energy_limited = max(1, int(reproductive_energy / 4.2))
        clutch_count = max(1, min(life.base_clutch_size + 3, clutch_target, energy_limited))
        energy_per = reproductive_energy / clutch_count
        if energy_per < 3.2:
            self._record_reproduction_gate(parent, "clutch_energy_too_low", perception, mode=mode)
            return ReproductionResult([], [], "clutch_energy_too_low", mode=mode)

        newborns: list[FishAgent] = []
        eggs: list[EggEntity] = []
        parent.energy -= reproductive_energy + 2.2 + affordances.reproduction_cost * 1.6
        parent.reproductive_drive = 0.08 if not parthenogenetic else 0.02
        parent.reproduction_cooldown = life.reproduction_interval_ticks + (24 if parthenogenetic else 0)
        parent.last_reproduction_tick = self.tick

        for index in range(clutch_count):
            lineage_id = parent.lineage_id
            if not parthenogenetic and self.rng.random() < 0.036 + max(0.0, parent.stress - 0.42) * 0.04:
                lineage_id = self.next_lineage_id
                self.next_lineage_id += 1
                self._event("lineage_split", parent=parent.fish_id, lineage=lineage_id)
            genome = parent.genome.mutated(self.rng, lineage_id=None if lineage_id == parent.lineage_id else lineage_id)
            if parthenogenetic:
                genome = genome.mutated(self.rng)
            instruction_genome, taught_skills, patch_decision = self._offspring_instruction_seed(
                parent,
                child_generation=parent.generation + 1,
                parthenogenetic=parthenogenetic,
            )
            if self._should_lay_egg(parent, perception, life, parthenogenetic, index):
                eggs.append(
                    self._create_egg(
                        parent,
                        genome,
                        instruction_genome,
                        taught_skills,
                        perception,
                        energy_per,
                        parthenogenetic=parthenogenetic,
                        patch_decision=patch_decision,
                    )
                )
            elif len(self.fish) + len(newborns) < self.config.max_population:
                newborns.append(
                    self._create_child(
                        parent,
                        genome,
                        instruction_genome,
                        taught_skills,
                        perception,
                        energy_per,
                        parthenogenetic=parthenogenetic,
                        patch_decision=patch_decision,
                    )
                )

        if not newborns and not eggs:
            self._record_reproduction_gate(parent, "clutch_energy_too_low", perception, mode=mode)
            return ReproductionResult([], [], "clutch_energy_too_low", mode=mode)

        self.births += len(newborns)
        self.births_reproduction += len(newborns)
        self.eggs_laid += len(eggs)
        reason = "egg_bank_deposited" if eggs and not newborns else "mixed_brood" if eggs else "live_birth"
        parent.last_reproduction_gate = reason
        self._record_reproduction_gate(
            parent,
            reason,
            perception,
            mode=mode,
            offspring_count=len(newborns),
            egg_count=len(eggs),
            energy_cost=reproductive_energy,
        )
        self._record_skill_reproduction_after_use(
            parent,
            reason=reason,
            offspring_count=len(newborns),
            egg_count=len(eggs),
        )
        if newborns:
            for child in newborns:
                self._event("birth", parent=parent.fish_id, child=child.fish_id, lineage=child.lineage_id, mode=mode)
                self._archive_lifecycle_event(
                    "live_birth",
                    fish=parent,
                    child=child,
                    perception=perception,
                    offspring_count=len(newborns),
                    egg_count=len(eggs),
                    reproduction_gate_result=reason,
                )
        if eggs:
            self._event("egg_clutch", parent=parent.fish_id, eggs=len(eggs), lineage=parent.lineage_id, mode=mode)
            for egg in eggs:
                self._archive_lifecycle_event(
                    "egg_laid",
                    fish=parent,
                    egg=egg,
                    perception=perception,
                    offspring_count=len(newborns),
                    egg_count=len(eggs),
                    reproduction_gate_result=reason,
                )
        return ReproductionResult(newborns, eggs, reason, mode=mode)

    def _reproduction_gate(self, parent: FishAgent, perception: Perception) -> str:
        if len(self.fish) >= self.config.max_population:
            return "overcrowded"
        life = parent.life_history
        if parent.age < life.maturity_age_ticks:
            return "not_mature"
        if parent.age > life.fertility_end_age_ticks:
            return "too_old_or_low_fertility"
        if parent.reproduction_cooldown > 0:
            return "cooldown"
        if parent.energy < 24.0 + parent.genome.body_size * 5.0 + parent.morphology_affordances.reproduction_cost * 5.0:
            return "low_energy"
        if parent.health < 0.35:
            return "low_health"
        drive_threshold = 0.08 if parent.age > life.senescence_start_ticks else 0.12
        if parent.reproductive_drive < drive_threshold:
            return "reproductive_drive_too_low"
        if perception.reproduction_score < 0.38:
            return "bad_environment"
        if perception.crowding > 0.90:
            return "overcrowded"
        if self._mate_contact(parent, perception):
            return "ready"
        if parent.life_history.parthenogenesis_alleles <= 0:
            return "parthenogenesis_not_available"
        if not self._parthenogenesis_pressure(parent, perception):
            return "parthenogenesis_trigger_not_met"
        return "ready"

    def _mate_contact(self, parent: FishAgent, perception: Perception) -> bool:
        sensory_range = parent.effective_sensory_range
        if perception.nearest_mate[2] < max(14.0, sensory_range * 1.9):
            return True
        for other in self.fish:
            if other.fish_id == parent.fish_id:
                continue
            if other.genome.metabolism != parent.genome.metabolism:
                continue
            if hypot(other.x - parent.x, other.y - parent.y) <= sensory_range * 2.2:
                return True
        return False

    def _parthenogenesis_pressure(self, parent: FishAgent, perception: Perception) -> bool:
        life = parent.life_history
        no_contact = not self._mate_contact(parent, perception)
        low_lineage = self._lineage_population(parent.lineage_id) <= 1
        low_adults = len(self.fish) <= 3
        late_fertility = parent.age >= int(life.senescence_start_ticks * 0.82)
        healthy_enough = parent.energy > 50.0 and parent.health > 0.58
        repeated_failure = parent.last_reproduction_gate in {"parthenogenesis_trigger_not_met", "parthenogenesis_failed_rng", "no_mate"}
        return healthy_enough and no_contact and (low_lineage or low_adults or late_fertility or repeated_failure)

    def _parthenogenesis_triggered(self, parent: FishAgent, perception: Perception) -> bool:
        if parent.life_history.parthenogenesis_alleles <= 0:
            return False
        if not self._parthenogenesis_pressure(parent, perception):
            return False
        allele = parent.life_history.parthenogenesis_alleles
        chance = 0.012 + allele * 0.048 + parent.life_history.parthenogenesis_bias * 0.10
        if allele == 1 and parent.age < int(parent.life_history.senescence_start_ticks * 0.86):
            chance *= 0.35
        if allele >= 3:
            chance *= 1.38
        return self.rng.random() < clamp(chance, 0.004, 0.42)

    def _should_lay_egg(
        self,
        parent: FishAgent,
        perception: Perception,
        life: object,
        parthenogenetic: bool,
        index: int,
    ) -> bool:
        egg_probability = 0.62
        if getattr(life, "brood_strategy", "") == "guarded_brood":
            egg_probability = 0.44
        elif getattr(life, "brood_strategy", "") == "egg_clutch":
            egg_probability = 0.82
        egg_probability += getattr(life, "dormancy_bias", 0.0) * 0.16
        egg_probability -= max(0.0, perception.reproduction_score - 0.72) * 0.12
        if parthenogenetic:
            egg_probability += 0.18
        if index > 0:
            egg_probability += 0.06
        return self.rng.random() < clamp(egg_probability, 0.22, 0.96)

    def _create_child(
        self,
        parent: FishAgent,
        genome: FishGenome,
        instruction_genome: BehaviorInstructionGenome,
        taught_skills: list[TaughtSkill],
        perception: Perception,
        energy_per: float,
        *,
        parthenogenetic: bool,
        patch_decision: InstructionPatchDecision | None = None,
    ) -> FishAgent:
        dx = self.rng.uniform(-1.0, 1.0)
        dy = self.rng.uniform(-1.0, 1.0)
        dx, dy = unit(dx, dy)
        viability = self._offspring_viability(parent, perception, energy_per, parthenogenetic=parthenogenetic, genome=genome)
        child = FishAgent(
            fish_id=self.next_fish_id,
            species_id=genome.species_id,
            lineage_id=genome.lineage_id,
            genome=genome,
            x=clamp(parent.x + dx * (parent.radius + 1.3), 0.8, self.config.width - 1.8),
            y=clamp(parent.y + dy * (parent.radius + 1.3), 0.8, self.config.height - 1.8),
            vx=parent.vx * 0.20 + dx * 0.10,
            vy=parent.vy * 0.20 + dy * 0.10,
            energy=max(16.0, min(44.0, 16.0 + energy_per * 2.4)),
            hunger=0.38,
            fear=parent.fear * 0.62,
            stress=parent.stress * 0.55,
            health=clamp(0.44 + viability * 0.52),
            reproductive_drive=0.01,
            generation=parent.generation + 1,
            parent_ids=(parent.fish_id,),
            instruction_genome=instruction_genome,
            taught_skills=taught_skills,
            instruction_inherited_from=parent.instruction_genome.policy_hash,
            accepted_instruction_patch_ids=list(instruction_genome.accepted_patch_ids),
            rejected_instruction_patch_ids=list(instruction_genome.rejected_patch_ids),
            model_budget=max(1, self.config.fish_model_budget - 1),
            heading=parent.heading,
            swim_phase=parent.swim_phase,
            locomotion_speed=hypot(parent.vx, parent.vy),
        )
        self.next_fish_id += 1
        self._record_instruction_inheritance(parent, child=child, patch_decision=patch_decision, delivery="live_birth")
        self._record_agent_code_snapshot(child, event_type="live_birth_code_snapshot", parent=parent)
        return child

    def _create_egg(
        self,
        parent: FishAgent,
        genome: FishGenome,
        instruction_genome: BehaviorInstructionGenome,
        taught_skills: list[TaughtSkill],
        perception: Perception,
        energy_per: float,
        *,
        parthenogenetic: bool,
        patch_decision: InstructionPatchDecision | None = None,
    ) -> EggEntity:
        life = genome.life_history()
        dx = self.rng.uniform(-1.0, 1.0)
        dy = self.rng.uniform(-1.0, 1.0)
        dx, dy = unit(dx, dy)
        viability = self._offspring_viability(parent, perception, energy_per, parthenogenetic=parthenogenetic, genome=genome)
        dormant = self.rng.random() < clamp(life.dormancy_bias * 0.38 + max(0.0, 0.54 - perception.reproduction_score) * 0.32)
        egg = EggEntity(
            egg_id=self.next_egg_id,
            parent_ids=(parent.fish_id,),
            lineage_id=genome.lineage_id,
            species_id=genome.species_id,
            genome=genome,
            instruction_genome=instruction_genome,
            taught_skills=taught_skills,
            instruction_inherited_from=parent.instruction_genome.policy_hash,
            generation=parent.generation + 1,
            created_tick=self.tick,
            age_ticks=0,
            gestation_ticks=max(42, int(life.maturity_age_ticks * 0.18 + self.rng.randint(18, 84))),
            viability=viability,
            energy_investment=energy_per,
            x=clamp(parent.x + dx * (parent.radius + 0.9), 0.8, self.config.width - 1.8),
            y=clamp(parent.y + dy * (parent.radius + 0.9), 0.8, self.config.height - 1.8),
            dormant=dormant,
            dormancy_strategy=life.egg_strategy,
            hatch_sensitivity=life.hatch_sensitivity,
            decay_rate=1.0 / max(220.0, life.egg_viability_ticks),
            parthenogenetic=parthenogenetic,
            state="dormant" if dormant else "gestating",
        )
        self.next_egg_id += 1
        self._record_instruction_inheritance(parent, egg=egg, patch_decision=patch_decision, delivery="egg")
        return egg

    def _offspring_viability(
        self,
        parent: FishAgent,
        perception: Perception,
        energy_per: float,
        *,
        parthenogenetic: bool,
        genome: FishGenome | None = None,
    ) -> float:
        life = parent.life_history
        offspring_affordances = (genome or parent.genome).morphology_affordances()
        viability = 0.28 + min(0.34, energy_per / 26.0) + perception.reproduction_score * 0.25 + parent.health * 0.16
        viability -= parent.stress * 0.16
        viability -= life.mutation_load * 0.12
        viability -= offspring_affordances.juvenile_fragility * 0.12
        viability -= offspring_affordances.growth_cost * 0.05
        viability -= max(0.0, 0.42 - offspring_affordances.viability_index) * 0.26
        if parthenogenetic:
            viability -= 0.10 + life.parthenogenesis_alleles * 0.015
        return clamp(viability, 0.08, 0.98)

    def _offspring_instruction_seed(
        self,
        parent: FishAgent,
        *,
        child_generation: int,
        parthenogenetic: bool,
    ) -> tuple[BehaviorInstructionGenome, list[TaughtSkill], InstructionPatchDecision | None]:
        if not self.config.instruction_inheritance_enabled:
            return BehaviorInstructionGenome(), [], None
        parent_hash = parent.instruction_genome.policy_hash
        instruction = parent.instruction_genome.mutated(self.rng, parent_hash=parent_hash)
        if parthenogenetic:
            instruction = instruction.mutated(self.rng, parent_hash=parent_hash)
        taught_skills = inherit_taught_skills(
            parent.taught_skills,
            current_generation=child_generation,
            allowed_slots=instruction.allowed_skill_slots,
            rng=self.rng,
        )
        patch_decision: InstructionPatchDecision | None = None
        proposal = rule_generated_patch(
            parent,
            tick=self.tick,
            lineage_population=self._lineage_population(parent.lineage_id),
            adult_population=len(self.fish),
        )
        if proposal is not None:
            patch_decision = self._validate_and_record_instruction_patch(parent, proposal)
            if patch_decision.accepted and patch_decision.skill is not None:
                if len(taught_skills) < instruction.allowed_skill_slots:
                    taught_skills.append(patch_decision.skill)
                taught_skills = taught_skills[: instruction.allowed_skill_slots]
                instruction = instruction.with_skill_bias(patch_decision.skill).with_patch_result(
                    patch_decision.patch_id,
                    accepted=True,
                )
            else:
                instruction = instruction.with_patch_result(patch_decision.patch_id, accepted=False)
        return instruction.normalized(), taught_skills, patch_decision

    def _validate_and_record_instruction_patch(self, parent: FishAgent, proposal: dict[str, Any]) -> InstructionPatchDecision:
        self.instruction_patches_proposed += 1
        decision = validate_instruction_patch(
            proposal,
            parent_id=parent.fish_id,
            lineage_id=parent.lineage_id,
            generation=parent.generation,
            created_tick=self.tick,
            allowed_skill_slots=max(0, parent.instruction_genome.allowed_skill_slots - len(parent.taught_skills)),
        )
        if decision.accepted:
            self.instruction_patches_accepted += 1
            self.teaching_events += 1
            parent.accepted_instruction_patch_ids.append(decision.patch_id)
            parent.instruction_genome = parent.instruction_genome.with_patch_result(decision.patch_id, accepted=True)
            if decision.skill is not None and len(parent.taught_skills) < parent.instruction_genome.allowed_skill_slots:
                parent.taught_skills.append(decision.skill)
            self._event("instruction_patch_accepted", fish_id=parent.fish_id, patch_id=decision.patch_id, skill=decision.skill.skill_type if decision.skill else "")
            event_type = "instruction_patch_acceptance"
        else:
            self.instruction_patches_rejected += 1
            self.instruction_rejection_reasons[decision.reason] += 1
            parent.rejected_instruction_patch_ids.append(decision.patch_id)
            parent.instruction_genome = parent.instruction_genome.with_patch_result(decision.patch_id, accepted=False)
            self._event("instruction_patch_rejected", fish_id=parent.fish_id, patch_id=decision.patch_id, reason=decision.reason)
            event_type = "instruction_patch_rejection"
        self._record_instruction_event(
            event_type,
            fish=parent,
            patch_decision=decision,
            proposal=proposal,
        )
        return decision

    def _record_instruction_inheritance(
        self,
        parent: FishAgent,
        *,
        child: FishAgent | None = None,
        egg: EggEntity | None = None,
        patch_decision: InstructionPatchDecision | None,
        delivery: str,
    ) -> None:
        self.instruction_inheritance_events += 1
        target_policy = child.instruction_genome if child is not None else egg.instruction_genome if egg is not None else parent.instruction_genome
        target_skills = child.taught_skills if child is not None else egg.taught_skills if egg is not None else []
        target_id = child.fish_id if child is not None else None
        egg_id = egg.egg_id if egg is not None else None
        entry = {
            "tick": self.tick,
            "event_type": "offspring_instruction_inheritance",
            "parent_id": parent.fish_id,
            "child_id": target_id,
            "egg_id": egg_id,
            "lineage_id": parent.lineage_id,
            "delivery": delivery,
            "parent_policy_hash": parent.instruction_genome.policy_hash,
            "offspring_policy_hash": target_policy.policy_hash,
            "offspring_policy_label": target_policy.policy_label,
            "skill_count": len(target_skills),
            "skill_hashes": [skill.skill_hash for skill in target_skills],
            "skills": [skill.payload(compact=True) for skill in target_skills],
            "patch_id": patch_decision.patch_id if patch_decision else "",
            "patch_accepted": patch_decision.accepted if patch_decision else None,
            "patch_reason": patch_decision.reason if patch_decision else "",
        }
        self.instruction_log.append(entry)
        self._record_instruction_event("offspring_instruction_inheritance", fish=parent, child=child, egg=egg, patch_decision=patch_decision, extra=entry)
        taught_now_hash = patch_decision.skill.skill_hash if patch_decision and patch_decision.accepted and patch_decision.skill else ""
        for skill in target_skills:
            target_fish = child if child is not None else None
            self._record_skill_evidence(
                event_type="skill_inherited",
                fish=target_fish,
                skill=skill,
                source="taught" if skill.skill_hash == taught_now_hash else "inherited",
                parent_id=parent.fish_id,
                child_id=target_id,
                egg_id=egg_id,
                lineage_id=(child.lineage_id if child is not None else egg.lineage_id if egg is not None else parent.lineage_id),
                generation=(child.generation if child is not None else egg.generation if egg is not None else parent.generation),
                delivery=delivery,
                context="offspring_instruction_inheritance",
                immediate_outcome=delivery,
                evidence_strength="weak",
                effect_label="insufficient_evidence",
                detail="Offspring received a bounded taught skill; use and outcome are tracked separately.",
            )

    def _record_instruction_event(
        self,
        event_type: str,
        *,
        fish: FishAgent | None = None,
        child: FishAgent | None = None,
        egg: EggEntity | None = None,
        patch_decision: InstructionPatchDecision | None = None,
        proposal: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        source = fish or child
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "tick": self.tick,
            "event_type": event_type,
            "fish_id": source.fish_id if source is not None else None,
            "child_id": child.fish_id if child is not None else None,
            "egg_id": egg.egg_id if egg is not None else None,
            "lineage_id": (egg.lineage_id if egg is not None else source.lineage_id if source is not None else None),
            "species_id": (egg.species_id if egg is not None else source.species_id if source is not None else None),
            "instruction_policy_hash": (
                egg.instruction_genome.policy_hash if egg is not None else source.instruction_genome.policy_hash if source is not None else ""
            ),
            "instruction_policy_label": (
                egg.instruction_genome.policy_label if egg is not None else source.instruction_genome.policy_label if source is not None else ""
            ),
            "patch_decision": patch_decision.payload() if patch_decision is not None else None,
            "proposal": proposal,
        }
        if extra:
            payload.update(extra)
        self.archive.write_lifecycle_event(payload)

    def _record_skill_use_outcomes(
        self,
        fish: FishAgent,
        perception: Perception,
        action: Action,
        outcome: str,
        *,
        before: dict[str, float],
        matches: list[dict[str, Any]],
    ) -> None:
        deltas = {
            "energy": fish.energy - before["energy"],
            "health": fish.health - before["health"],
            "hunger": fish.hunger - before["hunger"],
            "stress": fish.stress - before["stress"],
            "fear": fish.fear - before["fear"],
            "reproductive_drive": fish.reproductive_drive - before["reproductive_drive"],
        }
        for match in matches[:3]:
            skill = match["skill"]
            effect_label, outcome_score, evidence_strength, detail = classify_skill_outcome(skill, action, outcome, deltas)
            self._record_skill_evidence(
                event_type="skill_outcome_observed",
                fish=fish,
                skill=skill,
                source=skill_source(skill, fish),
                parent_id=getattr(skill, "source_parent_id", None),
                context=str(match.get("context", "")),
                action=action.kind,
                immediate_outcome=outcome,
                outcome_score=outcome_score,
                evidence_strength=evidence_strength,
                effect_label=effect_label,
                context_tags=match.get("context_tags", ()),
                affordance_tags=match.get("affordance_tags", ()),
                detail=(
                    f"{detail}; deltas energy={deltas['energy']:.3f}, hunger={deltas['hunger']:.3f}, "
                    f"stress={deltas['stress']:.3f}, health={deltas['health']:.3f}"
                ),
            )

    def _record_skill_reproduction_after_use(
        self,
        parent: FishAgent,
        *,
        reason: str,
        offspring_count: int,
        egg_count: int,
    ) -> None:
        total_descendants = offspring_count + egg_count
        if total_descendants <= 0:
            return
        for skill in parent.taught_skills:
            if not self._recent_skill_use(parent.fish_id, skill.skill_hash, window=720):
                continue
            self._record_skill_evidence(
                event_type="skill_descendant_outcome",
                fish=parent,
                skill=skill,
                source=skill_source(skill, parent),
                parent_id=getattr(skill, "source_parent_id", None),
                context="carrier_reproduced_after_observed_use",
                action="reproduce",
                immediate_outcome=reason,
                outcome_score=float(total_descendants),
                evidence_strength="moderate",
                effect_label="helped_possible",
                detail=(
                    f"Skill carrier reproduced after prior observed skill use: "
                    f"{offspring_count} live offspring and {egg_count} eggs. This is temporal association, not proof of causality."
                ),
                reproduction_after_use=True,
            )

    def _record_skill_death_after_use(self, fish: FishAgent, cause: str) -> None:
        for skill in fish.taught_skills:
            recent_use = self._recent_skill_use(fish.fish_id, skill.skill_hash, window=48)
            if not recent_use:
                continue
            risky_cause = cause in {"starvation", "environment", "shock", "predation"}
            self._record_skill_evidence(
                event_type="skill_descendant_outcome",
                fish=fish,
                skill=skill,
                source=skill_source(skill, fish),
                parent_id=getattr(skill, "source_parent_id", None),
                context="carrier_died_after_observed_use",
                action=str(recent_use.get("action", "")),
                immediate_outcome=f"death:{cause}",
                outcome_score=-1.0 if risky_cause else 0.0,
                evidence_strength="weak",
                effect_label="harmed_possible" if risky_cause else "unclear",
                detail="Skill carrier died after a recent observed use; the run cannot isolate whether the skill contributed.",
            )

    def _recent_skill_use(self, fish_id: int, skill_hash: str, *, window: int) -> dict[str, Any] | None:
        for event in reversed(self.skill_evidence_log):
            if event.get("event_type") != "skill_outcome_observed":
                continue
            if event.get("fish_id") != fish_id or event.get("skill_hash") != skill_hash:
                continue
            if self.tick - int(event.get("tick", self.tick) or self.tick) <= window:
                return event
            return None
        return None

    def _record_skill_evidence(
        self,
        *,
        event_type: str,
        skill: TaughtSkill,
        fish: FishAgent | None = None,
        source: str = "unknown",
        parent_id: int | None = None,
        child_id: int | None = None,
        egg_id: int | None = None,
        lineage_id: int | None = None,
        generation: int | None = None,
        context: str = "",
        action: str = "",
        immediate_outcome: str = "",
        outcome_score: float | None = None,
        evidence_strength: str = "weak",
        effect_label: str = "insufficient_evidence",
        delivery: str = "",
        detail: str = "",
        reproduction_after_use: bool = False,
        context_tags: Sequence[str] | None = None,
        affordance_tags: Sequence[str] | None = None,
    ) -> None:
        identity = skill_identity(skill)
        event = SkillUseEvidence(
            event_type=event_type,
            tick=self.tick,
            fish_id=fish.fish_id if fish is not None else child_id,
            lineage_id=int(lineage_id if lineage_id is not None else fish.lineage_id if fish is not None else getattr(skill, "source_lineage_id", 0) or 0),
            skill_id=identity["skill_id"],
            skill_hash=identity["skill_hash"],
            skill_name=identity["skill_name"],
            skill_type=identity["skill_type"],
            source=source,
            parent_id=parent_id,
            child_id=child_id,
            egg_id=egg_id,
            generation=int(generation if generation is not None else fish.generation if fish is not None else 0),
            context=context,
            action=action,
            immediate_outcome=immediate_outcome,
            outcome_score=outcome_score,
            evidence_strength=evidence_strength,
            effect_label=effect_label,
            delivery=delivery,
            detail=detail,
            reproduction_after_use=reproduction_after_use,
            context_tags=tuple(context_tags or ()),
            affordance_tags=tuple(affordance_tags or ()),
        ).payload()
        self.skill_evidence_log.append(event)
        self.archive.write_lifecycle_event(
            {
                "run_id": self.run_id,
                **event,
                "event_type": event_type,
                "claim_boundary": "observational_association_not_causal_proof",
            }
        )

    def _biological_genome_hash(self, genome: FishGenome) -> str:
        payload = genome.payload()
        payload.pop("phenotype", None)
        payload.pop("life_history", None)
        return stable_hash(payload, length=16)

    def _phenotype_hash(self, genome: FishGenome) -> str:
        return stable_hash(genome.phenotype_payload(compact=True), length=16)

    def _agent_code_snapshot_payload(
        self,
        fish: FishAgent,
        *,
        event_type: str,
        parent: FishAgent | None = None,
        egg: EggEntity | None = None,
        death_cause: str = "",
    ) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "tick": self.tick,
            "event_type": event_type,
            "fish_id": fish.fish_id,
            "lineage_id": fish.lineage_id,
            "species_id": fish.species_id,
            "generation": fish.generation,
            "parent_ids": list(fish.parent_ids),
            "parent_policy_hash": parent.instruction_genome.policy_hash if parent is not None else fish.instruction_inherited_from,
            "egg_id": egg.egg_id if egg is not None else None,
            "biological_genome_hash": self._biological_genome_hash(fish.genome),
            "phenotype_hash": self._phenotype_hash(fish.genome),
            "morphology_hash": fish.genome.morphology_hash,
            "morphology_labels": fish.genome.morphology_labels(),
            "instruction_policy_hash": fish.instruction_genome.policy_hash,
            "instruction_policy_hash_short": fish.instruction_genome.policy_hash_short,
            "instruction_policy_label": fish.instruction_genome.policy_label,
            "behavior_rationale": {
                "current_action": (fish.last_behavior_rationale or {}).get("current_action", ""),
                "action_reason": (fish.last_behavior_rationale or {}).get("action_reason", ""),
                "candidate_summary": list((fish.last_behavior_rationale or {}).get("candidate_summary", []))[:3],
                "context_tags": list((fish.last_behavior_rationale or {}).get("context_tags", []))[:8],
                "affordance_tags": list((fish.last_behavior_rationale or {}).get("affordance_tags", []))[:8],
                "policy_influence": list((fish.last_behavior_rationale or {}).get("policy_influence", []))[:5],
                "skill_influence": list((fish.last_behavior_rationale or {}).get("skill_influence", []))[:5],
                "mismatch_warnings": list((fish.last_behavior_rationale or {}).get("mismatch_warnings", []))[:4],
            },
            "taught_skill_hashes": [skill.skill_hash for skill in fish.taught_skills],
            "accepted_instruction_patch_ids": list(fish.accepted_instruction_patch_ids[-8:]),
            "rejected_instruction_patch_ids": list(fish.rejected_instruction_patch_ids[-8:]),
            "created_tick": self.tick if event_type != "death_code_snapshot" else None,
            "death_tick": self.tick if event_type == "death_code_snapshot" else None,
            "death_cause": death_cause,
            "summary_stats": {
                "age": fish.age,
                "energy": round(fish.energy, 3),
                "health": round(fish.health, 3),
                "recent_outcomes": list(fish.recent_outcomes[-5:]),
                "memory_summary": fish.memory.summary(),
            },
        }

    def _record_agent_code_snapshot(
        self,
        fish: FishAgent,
        *,
        event_type: str,
        parent: FishAgent | None = None,
        egg: EggEntity | None = None,
        death_cause: str = "",
    ) -> None:
        payload = self._agent_code_snapshot_payload(fish, event_type=event_type, parent=parent, egg=egg, death_cause=death_cause)
        self.agent_code_snapshots += 1
        if event_type == "death_code_snapshot":
            self.dead_agent_summaries[fish.fish_id] = {
                "fish_id": fish.fish_id,
                "lineage_id": fish.lineage_id,
                "species_id": fish.species_id,
                "generation": fish.generation,
                "parent_ids": list(fish.parent_ids),
                "death_tick": self.tick,
                "death_cause": death_cause,
                "biological_genome_hash": payload["biological_genome_hash"],
                "phenotype_hash": payload["phenotype_hash"],
                "morphology_hash": payload["morphology_hash"],
                "morphology_labels": payload["morphology_labels"],
                "instruction_policy_hash": payload["instruction_policy_hash"],
                "instruction_policy_label": payload["instruction_policy_label"],
                "behavior_rationale": payload["behavior_rationale"],
                "taught_skill_hashes": payload["taught_skill_hashes"],
                "accepted_instruction_patch_ids": payload["accepted_instruction_patch_ids"],
                "rejected_instruction_patch_ids": payload["rejected_instruction_patch_ids"],
                "archetype": fish.genome.archetype,
                "metabolism": fish.genome.metabolism,
                "body_shape": fish.genome.body_shape,
                "tail_shape": fish.genome.tail_shape,
                "summary_stats": payload["summary_stats"],
            }
            if len(self.dead_agent_summaries) > 320:
                oldest = sorted(self.dead_agent_summaries)[:64]
                for fish_id in oldest:
                    self.dead_agent_summaries.pop(fish_id, None)
        self.archive.write_lifecycle_event(payload)

    def _lineage_population(self, lineage_id: int) -> int:
        return sum(1 for fish in self.fish if fish.lineage_id == lineage_id)

    def _death_cause(self, fish: FishAgent) -> str | None:
        if fish.energy <= 0.0:
            return "starvation"
        if fish.health <= 0.0:
            return "environment"
        affordances = fish.morphology_affordances
        if affordances.viability_index < 0.18 and self.rng.random() < (0.18 - affordances.viability_index) * 0.010:
            return "developmental_failure"
        life = fish.life_history
        if fish.age > life.expected_lifespan_ticks and self.rng.random() < 0.010:
            return "age"
        if fish.age > life.senescence_start_ticks and self.rng.random() < 0.0018 + max(0, fish.age - life.senescence_start_ticks) / 240000.0:
            return "age"
        if fish.stress > 0.84 and self.rng.random() < (fish.stress - 0.80) * 0.06:
            return "shock"
        return None

    def _update_eggs(self) -> list[FishAgent]:
        hatchlings: list[FishAgent] = []
        active: list[EggEntity] = []
        for egg in self.eggs:
            if not egg.viable:
                continue
            egg.age_ticks += 1
            sample = self.environment.sample(egg.x, egg.y)
            life = egg.genome.life_history()
            affordances = egg.genome.morphology_affordances()
            stress = sample.stress_score(
                oxygen_need=(egg.genome.oxygen_need + affordances.oxygen_cost * 0.08) * 0.82,
                ph_preference=egg.genome.ph_preference,
                temperature_preference=egg.genome.temperature_preference,
                turbidity_tolerance=egg.genome.turbidity_tolerance * 1.12,
                toxin_tolerance=clamp(egg.genome.toxin_tolerance + affordances.toxin_resistance * 0.10 - affordances.toxin_self_cost * 0.04, 0.02, 1.35),
            )
            decay = egg.decay_rate * (life.dormancy_decay_modifier if egg.dormant else 1.0)
            egg.viability = clamp(
                egg.viability
                - decay
                - stress * 0.010
                - max(0.0, sample.toxins - 0.34) * 0.018
                - affordances.juvenile_fragility * 0.0008
                - max(0.0, 0.34 - affordances.viability_index) * 0.0015
            )
            if egg.age_ticks > life.egg_viability_ticks and not egg.dormant:
                egg.viability = clamp(egg.viability - 0.010)
            if sample.toxins > 0.72 or sample.oxygen < 0.14:
                egg.mark_dead("egg_died_environment")
                self._record_egg_death(egg, sample.payload())
                continue
            if egg.viability <= 0.0:
                egg.mark_dead("egg_died_decay")
                self._record_egg_death(egg, sample.payload())
                continue
            if not egg.dormant and egg.age_ticks > egg.gestation_ticks * 2 and sample.reproduction < 0.30:
                egg.mark_dormant()
                self._event("egg_entered_dormancy", egg_id=egg.egg_id, lineage=egg.lineage_id)
            if self._egg_should_hatch(egg, sample):
                hatchling = self._hatch_egg(egg, sample.payload())
                egg.mark_hatched()
                hatchlings.append(hatchling)
                continue
            active.append(egg)
        self.eggs = active
        return hatchlings

    def _egg_should_hatch(self, egg: EggEntity, sample: object) -> bool:
        if egg.age_ticks < egg.gestation_ticks:
            return False
        hatch_score = clamp(
            sample.reproduction * 0.44
            + sample.oxygen * 0.18
            + sample.food * 0.14
            + sample.plankton * 0.10
            - sample.toxins * 0.28
            - sample.population_pressure * 0.16
        )
        if hatch_score < 0.38:
            if egg.dormant:
                return False
            return self.rng.random() < 0.006
        low_density_bonus = 1.0
        if len(self.fish) == 0:
            low_density_bonus = 1.7
        elif len(self.fish) < 6:
            low_density_bonus = 1.35
        lineage_bonus = 1.25 if self._lineage_population(egg.lineage_id) <= 1 else 1.0
        dormant_penalty = 0.46 if egg.dormant else 1.0
        chance = (0.018 + hatch_score * 0.055) * egg.hatch_sensitivity * low_density_bonus * lineage_bonus * dormant_penalty
        return self.rng.random() < clamp(chance, 0.004, 0.22)

    def _hatch_egg(self, egg: EggEntity, local_environment_sample: dict[str, float]) -> FishAgent:
        dx = self.rng.uniform(-1.0, 1.0)
        dy = self.rng.uniform(-1.0, 1.0)
        dx, dy = unit(dx, dy)
        affordances = egg.genome.morphology_affordances()
        child = FishAgent(
            fish_id=self.next_fish_id,
            species_id=egg.species_id,
            lineage_id=egg.lineage_id,
            genome=egg.genome,
            x=clamp(egg.x + dx * 1.4, 0.8, self.config.width - 1.8),
            y=clamp(egg.y + dy * 1.4, 0.8, self.config.height - 1.8),
            vx=dx * 0.08,
            vy=dy * 0.08,
            energy=max(14.0, min(42.0, 12.0 + egg.energy_investment * 2.2)),
            hunger=0.42,
            fear=0.12,
            stress=0.10,
            health=clamp(0.34 + egg.viability * 0.50 + affordances.viability_index * 0.10 - affordances.juvenile_fragility * 0.08),
            reproductive_drive=0.01,
            generation=egg.generation,
            parent_ids=egg.parent_ids,
            instruction_genome=egg.instruction_genome,
            taught_skills=list(egg.taught_skills),
            instruction_inherited_from=egg.instruction_inherited_from,
            accepted_instruction_patch_ids=list(egg.instruction_genome.accepted_patch_ids),
            rejected_instruction_patch_ids=list(egg.instruction_genome.rejected_patch_ids),
            model_budget=max(1, self.config.fish_model_budget - 1),
        )
        self.next_fish_id += 1
        self.births += 1
        self.births_hatched += 1
        self.births_reproduction += 1
        self.eggs_hatched += 1
        for skill in child.taught_skills:
            self._record_skill_evidence(
                event_type="skill_inherited",
                fish=child,
                skill=skill,
                source="inherited",
                parent_id=egg.parent_ids[0] if egg.parent_ids else getattr(skill, "source_parent_id", None),
                egg_id=egg.egg_id,
                child_id=child.fish_id,
                delivery="egg_hatch",
                context="egg_hatched_with_inherited_skill",
                detail="Egg hatch preserved the bounded taught skill into a live descendant.",
            )
        if self.biosphere_state == "dormant":
            self.recovery_events += 1
            self.last_recovery_kind = "egg_hatch"
        self.dead_puddle = False
        self.biosphere_state = "active"
        self._event("egg_hatched", egg_id=egg.egg_id, child=child.fish_id, lineage=egg.lineage_id)
        self._record_agent_code_snapshot(child, event_type="egg_hatch_code_snapshot", egg=egg)
        self._archive_lifecycle_event(
            "egg_hatched",
            child=child,
            egg=egg,
            local_environment_sample=local_environment_sample,
            reproduction_gate_result="egg_hatched",
        )
        return child

    def _record_egg_death(self, egg: EggEntity, local_environment_sample: dict[str, float]) -> None:
        self.egg_deaths += 1
        self.egg_deaths_by_cause[egg.death_cause] += 1
        self._event("egg_died", egg_id=egg.egg_id, cause=egg.death_cause, lineage=egg.lineage_id)
        self._archive_lifecycle_event(
            egg.death_cause,
            egg=egg,
            local_environment_sample=local_environment_sample,
            reproduction_gate_result=egg.death_cause,
        )

    def _record_reproduction_gate(
        self,
        fish: FishAgent,
        reason: str,
        perception: Perception,
        *,
        mode: str = "none",
        chance: float | None = None,
        offspring_count: int = 0,
        egg_count: int = 0,
        energy_cost: float = 0.0,
    ) -> None:
        fish.last_reproduction_gate = reason
        self.reproduction_gate_reasons[reason] += 1
        entry = {
            "tick": self.tick,
            "fish_id": fish.fish_id,
            "lineage": fish.lineage_id,
            "species_id": fish.species_id,
            "reason": reason,
            "mode": mode,
            "maturity_state": fish.maturity_state,
            "fertility_state": fish.fertility_state,
            "age": fish.age,
            "energy": round(fish.energy, 2),
            "health": round(fish.health, 3),
            "reproductive_drive": round(fish.reproductive_drive, 3),
            "reproduction_score": round(perception.reproduction_score, 3),
            "offspring_count": offspring_count,
            "egg_count": egg_count,
            "energy_cost": round(energy_cost, 3),
        }
        if chance is not None:
            entry["chance"] = round(chance, 4)
        self.reproduction_log.append(entry)

    def _archive_lifecycle_event(
        self,
        event_type: str,
        *,
        fish: FishAgent | None = None,
        child: FishAgent | None = None,
        egg: EggEntity | None = None,
        perception: Perception | None = None,
        local_environment_sample: dict[str, float] | None = None,
        reproduction_gate_result: str = "",
        death_cause: str = "",
        offspring_count: int = 0,
        egg_count: int = 0,
    ) -> None:
        source = fish or child
        sample = local_environment_sample or (perception.sample if perception is not None else None)
        payload: dict[str, object] = {
            "run_id": self.run_id,
            "tick": self.tick,
            "event_type": event_type,
            "fish_id": source.fish_id if source is not None else None,
            "egg_id": egg.egg_id if egg is not None else None,
            "child_id": child.fish_id if child is not None else None,
            "lineage_id": (egg.lineage_id if egg is not None else source.lineage_id if source is not None else None),
            "species_id": (egg.species_id if egg is not None else source.species_id if source is not None else None),
            "age": source.age if source is not None else None,
            "energy": round(source.energy, 3) if source is not None else None,
            "health": round(source.health, 3) if source is not None else None,
            "reproductive_drive": round(source.reproductive_drive, 3) if source is not None else None,
            "maturity_state": source.maturity_state if source is not None else None,
            "fertility_state": source.fertility_state if source is not None else None,
            "life_history": (source.life_history.payload() if source is not None else egg.genome.life_history().payload() if egg is not None else None),
            "biological_genome_hash": (
                self._biological_genome_hash(source.genome)
                if source is not None
                else self._biological_genome_hash(egg.genome)
                if egg is not None
                else None
            ),
            "phenotype_hash": (
                self._phenotype_hash(source.genome) if source is not None else self._phenotype_hash(egg.genome) if egg is not None else None
            ),
            "morphology_hash": (
                source.genome.morphology_hash if source is not None else egg.genome.morphology_hash if egg is not None else None
            ),
            "morphology_labels": (
                source.genome.morphology_labels() if source is not None else egg.genome.morphology_labels() if egg is not None else []
            ),
            "instruction_policy_hash": (
                source.instruction_genome.policy_hash
                if source is not None
                else egg.instruction_genome.policy_hash
                if egg is not None
                else None
            ),
            "instruction_policy_label": (
                source.instruction_genome.policy_label
                if source is not None
                else egg.instruction_genome.policy_label
                if egg is not None
                else None
            ),
            "taught_skill_hashes": (
                [skill.skill_hash for skill in source.taught_skills]
                if source is not None
                else [skill.skill_hash for skill in egg.taught_skills]
                if egg is not None
                else []
            ),
            "local_environment_sample": sample,
            "reproduction_gate_result": reproduction_gate_result,
            "offspring_count": offspring_count,
            "egg_count": egg_count,
            "death_cause": death_cause,
        }
        self.archive.write_lifecycle_event(payload)

    def _recycle_dead(self, fish: FishAgent, cause: str) -> None:
        fish.alive = False
        self.deaths_by_cause[cause] += 1
        self.environment.add_detritus(fish.x, fish.y, min(0.78, 0.12 + fish.energy * 0.004 + fish.radius * 0.030))
        self._event("death", fish_id=fish.fish_id, cause=cause, lineage=fish.lineage_id)
        self._record_skill_death_after_use(fish, cause)
        self._archive_lifecycle_event("death", fish=fish, death_cause=cause)
        self._record_agent_code_snapshot(fish, event_type="death_code_snapshot", death_cause=cause)

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

    def _handle_no_adults(self) -> None:
        if self.viable_egg_count() > 0:
            self.dead_puddle = False
            self.biosphere_state = "dormant"
            if not self._dormant_announced:
                self._event("dormant_biosphere", viable_eggs=self.viable_egg_count())
                self._dormant_announced = True
            return
        self._handle_extinction()

    def _handle_extinction(self) -> None:
        if self.dead_puddle:
            return
        self.dead_puddle = True
        self.biosphere_state = "extinct"
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
        if self.reproduction_gate_reasons:
            reason, count = self.reproduction_gate_reasons.most_common(1)[0]
            if count > 8 and reason in {
                "not_mature",
                "too_old_or_low_fertility",
                "low_energy",
                "reproductive_drive_too_low",
                "parthenogenesis_not_available",
                "parthenogenesis_failed_rng",
                "clutch_energy_too_low",
            }:
                return "reproduction_gate_failure"
        return "agent_lifecycle_pressure"

    def _record_decision(self, fish: FishAgent, action: Action, outcome: str) -> None:
        behavior = fish.last_behavior_rationale or {}
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
                "context_tags": list(behavior.get("context_tags", []))[:8],
                "affordance_tags": list(behavior.get("affordance_tags", []))[:8],
                "policy_influence": list(behavior.get("policy_influence", []))[:5],
                "skill_influence": list(behavior.get("skill_influence", []))[:5],
                "mismatch_warnings": list(behavior.get("mismatch_warnings", []))[:4],
            }
        )

    def _event(self, kind: str, **payload: object) -> None:
        self.events.append({"tick": self.tick, "kind": kind, **payload})

    def _archive_if_due(self) -> None:
        if self.config.archive_every_ticks <= 0:
            return
        if self.tick % self.config.archive_every_ticks != 0:
            return
        self.archive.write_snapshot(tick=self.tick, fish=self.fish, eggs=self.eggs, run_id=self.run_id)
        self.archive.write_decisions(tick=self.tick, fish=self.fish, run_id=self.run_id)

    def viable_egg_count(self) -> int:
        return sum(1 for egg in self.eggs if egg.viable)

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

    def _skill_evidence_payload(self) -> dict[str, Any]:
        return aggregate_skill_evidence(
            events=list(self.skill_evidence_log),
            fish=self.fish,
            eggs=self.eggs,
            tick=self.tick,
        )

    def _morphology_payload(self) -> dict[str, Any]:
        organisms = [
            morphology_state_payload(organism_id=fish.fish_id, lineage_id=fish.lineage_id, morphology=fish.genome.morphology)
            for fish in self.fish
        ]
        labels = Counter(label for item in organisms for label in item["labels"])
        viability_values = [float(item["affordances"]["viability_index"]) for item in organisms]
        drag_values = [float(item["affordances"]["drag"]) for item in organisms]
        throughput_values = [float(item["affordances"]["feeding_throughput"]) for item in organisms]
        return {
            "schema": MORPHOLOGY_SCHEMA,
            "summary": {
                "organisms": len(organisms),
                "distinct_morphologies": len({item["morphology_hash"] for item in organisms}),
                "average_viability_index": round(sum(viability_values) / max(1, len(viability_values)), 3),
                "average_drag": round(sum(drag_values) / max(1, len(drag_values)), 3),
                "average_feeding_throughput": round(sum(throughput_values) / max(1, len(throughput_values)), 3),
                "high_cost_count": sum(1 for item in organisms if float(item["affordances"]["metabolic_burden"]) >= 0.58 or float(item["affordances"]["oxygen_cost"]) >= 0.58),
                "low_viability_count": sum(1 for item in organisms if float(item["affordances"]["viability_index"]) < 0.42),
                "top_labels": [{"label": label, "count": count} for label, count in labels.most_common(8)],
            },
            "organisms": organisms,
        }

    def _behavior_payload(self) -> dict[str, Any]:
        organisms = [
            behavior_state_payload(
                organism_id=fish.fish_id,
                lineage_id=fish.lineage_id,
                rationale=fish.last_behavior_rationale,
            )
            for fish in self.fish
        ]
        return {
            "schema": BEHAVIOR_SCHEMA,
            "summary": summarize_behavior_payload(organisms),
            "organisms": organisms,
        }

    def telemetry(self) -> dict[str, Any]:
        population = len(self.fish)
        egg_count = len(self.eggs)
        viable_egg_count = self.viable_egg_count()
        dormant_egg_count = sum(1 for egg in self.eggs if egg.viable and egg.dormant)
        lineage_count = len({fish.lineage_id for fish in self.fish} | {egg.lineage_id for egg in self.eggs if egg.viable})
        actions = Counter(entry["action"] for entry in self.decision_log)
        sources = Counter(entry["source"] for entry in self.decision_log)
        species = Counter(fish.species_id for fish in self.fish)
        metabolism = Counter(fish.genome.metabolism for fish in self.fish)
        morphology_payload = self._morphology_payload()
        behavior_payload = self._behavior_payload()
        policy_variants = Counter(fish.instruction_genome.policy_label for fish in self.fish)
        policy_hashes = Counter(fish.instruction_genome.policy_hash_short for fish in self.fish)
        viability_score, viable_cells = self.environmental_viability()
        return {
            "tick": self.tick,
            "run_id": self.run_id,
            "biosphere_state": self.biosphere_state,
            "adult_population": population,
            "population": population,
            "egg_count": egg_count,
            "viable_egg_count": viable_egg_count,
            "dormant_egg_count": dormant_egg_count,
            "lineage_count": lineage_count,
            "births": self.births,
            "births_reproduction": self.births_reproduction,
            "births_hatched": self.births_hatched,
            "births_reseed_debug": self.births_reseed_debug,
            "eggs_laid": self.eggs_laid,
            "eggs_hatched": self.eggs_hatched,
            "egg_deaths": self.egg_deaths,
            "egg_deaths_by_cause": dict(self.egg_deaths_by_cause),
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
            "morphology": morphology_payload["summary"],
            "behavior": behavior_payload["summary"],
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
            "recent_reproduction_events": list(reversed(self.reproduction_log))[:16],
            "reproduction_gate_reasons": dict(self.reproduction_gate_reasons.most_common(12)),
            "instruction": {
                "inheritance_enabled": self.config.instruction_inheritance_enabled,
                "model_teaching_enabled": self.config.model_teaching_enabled,
                "patches_proposed": self.instruction_patches_proposed,
                "patches_accepted": self.instruction_patches_accepted,
                "patches_rejected": self.instruction_patches_rejected,
                "teaching_events": self.teaching_events,
                "inheritance_events": self.instruction_inheritance_events,
                "agent_code_snapshots": self.agent_code_snapshots,
                "dead_agent_summaries": len(self.dead_agent_summaries),
                "policy_variants_alive": len(policy_hashes),
                "top_policy_variants": [
                    {"label": label, "count": count} for label, count in policy_variants.most_common(8)
                ],
                "rejection_reasons": dict(self.instruction_rejection_reasons.most_common(8)),
                "recent_events": list(reversed(self.instruction_log))[:16],
            },
            "skill_evidence": self._skill_evidence_payload(),
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
                "lifecycle_path": str(self.archive.lifecycle_path) if self.archive.lifecycle_path else "",
                "every_ticks": self.config.archive_every_ticks,
            },
        }

    def state(self) -> dict[str, Any]:
        telemetry = self.telemetry()
        dashboard = self.dashboard(telemetry)
        genealogy = self.genealogy(telemetry)
        morphology = self._morphology_payload()
        behavior = self._behavior_payload()
        return {
            "schema": "aquagenesys.state.v12",
            "tick": self.tick,
            "run_id": self.run_id,
            "config": {
                "seed": self._initial_seed,
                "speed": self.speed,
                "max_population": self.config.max_population,
                "deliberation_enabled": self.config.deliberation_enabled,
                "deliberation_interval_ticks": self.config.deliberation_interval_ticks,
                "fish_model_budget": self.config.fish_model_budget,
                "model_intent_ttl": self.config.model_intent_ttl,
                "ecology_update_interval": self.config.ecology_update_interval,
                "instruction_inheritance_enabled": self.config.instruction_inheritance_enabled,
                "model_teaching_enabled": self.config.model_teaching_enabled,
            },
            "environment": self.environment.payload(),
            "fish": [fish.payload() for fish in self.fish],
            "eggs": [egg.payload() for egg in self.eggs],
            "organisms": [fish.payload() for fish in self.fish],
            "morphology": morphology,
            "behavior": behavior,
            "telemetry": telemetry,
            "dashboard": dashboard,
            "genealogy": genealogy,
            "lineage_story": self.lineage_story(telemetry, dashboard=dashboard, genealogy=genealogy),
        }

    def dashboard(self, telemetry: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_observatory_dashboard(
            tick=self.tick,
            run_id=self.run_id,
            telemetry=telemetry or self.telemetry(),
            fish=self.fish,
            eggs=self.eggs,
            events=self.events,
            reproduction_log=self.reproduction_log,
            instruction_log=self.instruction_log,
            decision_log=self.decision_log,
            dead_agent_summaries=self.dead_agent_summaries,
            field_averages=self.environment.averages(),
        )

    def genealogy(self, telemetry: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_genealogy(
            tick=self.tick,
            run_id=self.run_id,
            fish=self.fish,
            eggs=self.eggs,
            dead_agent_summaries=self.dead_agent_summaries,
            instruction_log=self.instruction_log,
            reproduction_log=self.reproduction_log,
            events=self.events,
            telemetry=telemetry or self.telemetry(),
        )

    def lineage_story(
        self,
        telemetry: dict[str, Any] | None = None,
        *,
        dashboard: dict[str, Any] | None = None,
        genealogy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_telemetry = telemetry or self.telemetry()
        current_dashboard = dashboard or self.dashboard(current_telemetry)
        current_genealogy = genealogy or self.genealogy(current_telemetry)
        return build_lineage_story(
            tick=self.tick,
            run_id=self.run_id,
            telemetry=current_telemetry,
            dashboard=current_dashboard,
            genealogy=current_genealogy,
            events=self.events,
            reproduction_log=self.reproduction_log,
            instruction_log=self.instruction_log,
            dead_agent_summaries=self.dead_agent_summaries,
        )

    def frame_state(self) -> dict[str, Any]:
        return {
            "schema": "aquagenesys.frame.v3",
            "tick": self.tick,
            "run_id": self.run_id,
            "config": {
                "seed": self._initial_seed,
                "speed": self.speed,
                "deliberation_enabled": self.config.deliberation_enabled,
                "instruction_inheritance_enabled": self.config.instruction_inheritance_enabled,
                "model_teaching_enabled": self.config.model_teaching_enabled,
            },
            "environment": {
                "width": self.environment.width,
                "height": self.environment.height,
                "signature": list(self.environment.signature),
            },
            "fish": [fish.frame_payload() for fish in self.fish],
            "eggs": [egg.payload(compact=True) for egg in self.eggs[:160]],
            "telemetry": {
                "tick": self.tick,
                "run_id": self.run_id,
                "biosphere_state": self.biosphere_state,
                "adult_population": len(self.fish),
                "population": len(self.fish),
                "egg_count": len(self.eggs),
                "viable_egg_count": self.viable_egg_count(),
                "dormant_egg_count": sum(1 for egg in self.eggs if egg.viable and egg.dormant),
                "lineage_count": len({fish.lineage_id for fish in self.fish} | {egg.lineage_id for egg in self.eggs if egg.viable}),
                "births": self.births,
                "eggs_laid": self.eggs_laid,
                "eggs_hatched": self.eggs_hatched,
                "egg_deaths": self.egg_deaths,
                "dead_puddle": self.dead_puddle,
                "average_health": round(sum(fish.health for fish in self.fish) / max(1, len(self.fish)), 3),
                "average_stress": round(sum(fish.stress for fish in self.fish) / max(1, len(self.fish)), 3),
                "reproduction_gate_reasons": dict(self.reproduction_gate_reasons.most_common(8)),
                "decision_sources": dict(Counter(entry["source"] for entry in self.decision_log)),
                "agent_decisions": list(reversed(self.decision_log))[:8],
                "recent_events": list(reversed(self.events))[:8],
                "recent_reproduction_events": list(reversed(self.reproduction_log))[:8],
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
                "instruction": {
                    "inheritance_enabled": self.config.instruction_inheritance_enabled,
                    "model_teaching_enabled": self.config.model_teaching_enabled,
                    "patches_proposed": self.instruction_patches_proposed,
                    "patches_accepted": self.instruction_patches_accepted,
                    "patches_rejected": self.instruction_patches_rejected,
                    "teaching_events": self.teaching_events,
                    "inheritance_events": self.instruction_inheritance_events,
                    "policy_variants_alive": len(
                        {fish.instruction_genome.policy_hash_short for fish in self.fish}
                    ),
                    "rejection_reasons": dict(self.instruction_rejection_reasons.most_common(5)),
                    "recent_events": list(reversed(self.instruction_log))[:6],
                },
            },
        }
