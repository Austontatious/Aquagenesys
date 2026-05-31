from __future__ import annotations

from dataclasses import dataclass, replace
import json
from math import pi
import time

from fastapi.testclient import TestClient

from aquagenesys.agents import Action, FishDeliberationResult
from aquagenesys.web.app import create_app
from aquagenesys.environment.puddle import EnvironmentConfig, PuddleEnvironment
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


def test_environment_owns_required_dirty_puddle_fields_without_models() -> None:
    env = PuddleEnvironment(EnvironmentConfig(seed=7, width=34, height=22))
    expected = {
        "temperature",
        "oxygen",
        "ph",
        "turbidity",
        "nutrients",
        "light",
        "current_x",
        "current_y",
        "shelter",
        "substrate",
        "food",
        "plankton",
        "waste",
        "toxins",
        "decomposition",
        "population_pressure",
        "reproduction",
        "balance",
    }
    assert expected.issubset(env.fields)
    before = env.signature
    env.update()
    assert env.tick == 1
    assert env.signature != before


def test_simulation_runs_fish_agent_loop_and_observable_decisions() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=11,
            width=42,
            height=28,
            initial_population=18,
            max_population=50,
            deliberation_enabled=False,
            archive_every_ticks=0,
        )
    )
    starting_signature = sim._reset_signature()
    sim.run(24)
    state = sim.state()
    assert state["schema"] == "aquagenesys.state.v13"
    assert state["fish"]
    assert state["telemetry"]["population"] > 0
    assert state["telemetry"]["agent_decisions"]
    assert state["dashboard"]["schema"] == "aquagenesys.dashboard.v2"
    assert state["dashboard"]["narrator"]["headline"]
    assert state["lineage_story"]["schema"] == "aquagenesys.lineage_story.v5"
    assert state["lineage_story"]["questions"]
    assert state["telemetry"]["model"]["calls"] == 0
    assert sim._reset_signature() != starting_signature


def test_reset_restores_seeded_start_condition() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=13, width=34, height=24, initial_population=12, deliberation_enabled=False)
    )
    initial = sim.initial_signature
    sim.run(10)
    assert sim._reset_signature() != initial
    sim.reset()
    assert sim.initial_signature == initial
    assert sim._reset_signature() == initial


def test_dead_puddle_does_not_spawn_founders_by_default() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=17,
            width=26,
            height=18,
            initial_population=0,
            deliberation_enabled=False,
            debug_founder_reseed_enabled=False,
        )
    )
    sim.run(5)
    telemetry = sim.state()["telemetry"]
    assert telemetry["dead_puddle"] is True
    assert telemetry["extinction_events"] == 1
    assert telemetry["births_reseed_debug"] == 0
    assert telemetry["population"] == 0


def test_randomize_environment_changes_chemistry_without_spawning_life() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=19, width=26, height=18, initial_population=0, deliberation_enabled=False)
    )
    sim.step()
    before = sim.environment.signature
    sim.randomize_environment()
    after = sim.environment.signature
    assert after != before
    assert len(sim.fish) == 0
    assert sim.state()["telemetry"]["births_reseed_debug"] == 0


@dataclass
class FakeController:
    action: Action

    def deliberate_context(self, *args: object, **kwargs: object) -> FishDeliberationResult:
        return FishDeliberationResult(action=self.action, called=True, ok=True, latency_ms=3, raw_text="{}")


def test_sparse_model_deliberation_uses_controller_when_budget_allows(monkeypatch) -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=23,
            width=34,
            height=22,
            initial_population=6,
            max_population=20,
            deliberation_enabled=True,
            deliberation_interval_ticks=1,
            global_deliberations_per_tick=1,
            fish_model_budget=1,
            archive_every_ticks=0,
        )
    )
    for fish in sim.fish:
        fish.genome = replace(fish.genome, aggression=0.0)
        fish.hunger = 0.10
        fish.energy = 80.0
    monkeypatch.setattr(
        "aquagenesys.agents.fish.FishAgent.should_deliberate",
        lambda self, perception, rng, *, global_enabled: global_enabled,
    )
    sim._controller = FakeController(Action("shelter", 0.0, 1.0, 0.7, "model", "test model action", 0.8))
    sim.step()
    time.sleep(0.02)
    sim.step()
    telemetry = sim.state()["telemetry"]
    assert telemetry["model"]["calls"] == 1
    assert telemetry["model"]["successes"] == 1
    assert telemetry["model"]["intents_applied"] == 1
    assert telemetry["decision_sources"]["model"] >= 1
    sim.close()


@dataclass
class SlowFakeController:
    action: Action
    delay: float = 0.35

    def deliberate_context(self, *args: object, **kwargs: object) -> FishDeliberationResult:
        time.sleep(self.delay)
        return FishDeliberationResult(action=self.action, called=True, ok=True, latency_ms=int(self.delay * 1000), raw_text="{}")


def test_model_deliberation_is_nonblocking_and_becomes_ttl_intent(monkeypatch) -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=43,
            width=24,
            height=16,
            initial_population=4,
            max_population=12,
            deliberation_enabled=True,
            deliberation_interval_ticks=1,
            global_deliberations_per_tick=1,
            fish_model_budget=1,
            model_intent_ttl=4,
            archive_every_ticks=0,
        )
    )
    for fish in sim.fish:
        fish.genome = replace(fish.genome, aggression=0.0)
        fish.hunger = 0.10
        fish.energy = 80.0
    monkeypatch.setattr(
        "aquagenesys.agents.fish.FishAgent.should_deliberate",
        lambda self, perception, rng, *, global_enabled: global_enabled,
    )
    sim._controller = SlowFakeController(Action("rest", 0.0, 0.0, 0.2, "model", "slow model intent", 0.8))
    started = time.perf_counter()
    sim.step()
    elapsed = time.perf_counter() - started
    telemetry = sim.state()["telemetry"]
    assert elapsed < 0.25
    assert telemetry["model"]["calls"] == 1
    assert telemetry["model"]["pending"] == 1
    time.sleep(0.45)
    sim.step()
    telemetry = sim.state()["telemetry"]
    assert telemetry["model"]["successes"] == 1
    assert telemetry["model"]["intents_applied"] == 1
    assert telemetry["decision_sources"].get("model", 0) >= 1
    assert any(fish["active_intent"] for fish in sim.frame_state()["fish"])
    sim.close()


def test_frame_state_is_compact_and_observable() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=47, width=30, height=20, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(2)
    state = sim.state()
    frame = sim.frame_state()
    assert frame["schema"] == "aquagenesys.frame.v3"
    assert "fields" not in frame["environment"]
    assert frame["fish"][0]["decision"]
    assert frame["fish"][0]["genome"]["archetype"]
    assert frame["fish"][0]["instruction"]["policy_hash_short"]
    assert frame["fish"][0]["phenotype"]["shape"]
    assert frame["fish"][0]["phenotype"]["pattern"]
    assert len(json.dumps(frame)) < len(json.dumps(state)) * 0.55
    sim.close()


def test_procedural_phenotypes_are_distinct_and_mechanically_exposed() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=61, width=34, height=22, initial_population=12, deliberation_enabled=False, archive_every_ticks=0)
    )
    state = sim.state()
    phenotypes = [fish["phenotype"] for fish in state["fish"]]
    signatures = {(item["shape"], item["tail"], item["fins"], item["pattern"]) for item in phenotypes}
    assert len(signatures) >= 4
    for fish in state["fish"][:6]:
        phenotype = fish["phenotype"]
        mechanics = phenotype["mechanics"]
        assert phenotype["body_length"] > 1.0
        assert phenotype["tail_length"] > 0.4
        assert mechanics["thrust"] > 0.0
        assert mechanics["maneuver"] > 0.0
        assert mechanics["drag"] > 0.0
    sim.close()


def test_phenotype_survives_mutation_and_frame_contract() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=67, width=34, height=22, initial_population=4, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = sim.fish[0]
    child_genome = parent.genome.mutated(sim.rng)
    child_payload = child_genome.payload()
    frame = sim.frame_state()
    assert child_payload["phenotype"]["shape"]
    assert child_payload["phenotype"]["primary_color"].startswith("#")
    assert "mechanics" not in frame["fish"][0]["phenotype"]
    assert frame["fish"][0]["phenotype"]["accent_color"].startswith("#")
    sim.close()


def test_locomotion_payload_is_exposed_and_bounded() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=71, width=34, height=22, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(4)
    state_fish = sim.state()["fish"][0]
    frame_fish = sim.frame_state()["fish"][0]
    for payload in (state_fish["locomotion"], frame_fish["locomotion"]):
        assert -pi <= payload["heading"] <= pi
        assert 0.0 <= payload["swim_phase"] <= pi * 2
        assert 0.0 <= payload["tail_beat"] <= 1.0
        assert 0.0 <= payload["body_wave"] <= 1.0
        assert payload["speed"] >= 0.0
        assert payload["stride"] >= 0.0
    sim.close()


def test_locomotion_turns_are_smoothed_not_snapped() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=73, width=30, height=20, initial_population=4, deliberation_enabled=False, archive_every_ticks=0)
    )
    fish = sim.fish[0]
    fish.heading = 0.0
    fish.turn_rate = 0.0
    fish.vx = max(0.2, fish.genome.max_speed * 0.4)
    fish.vy = 0.0
    perception = sim._sense(fish)
    sim._apply_action(fish, Action("explore", 0.0, 1.0, 1.0, "habit", "test turn"), perception, {})
    assert 0.0 < fish.heading < pi / 2
    assert abs(fish.turn_rate) < pi / 2
    assert fish.tail_beat > 0.0
    assert fish.body_wave > 0.0
    sim.close()


def test_frame_endpoint_does_not_return_full_environment_grid() -> None:
    app = create_app(
        SimulationConfig(seed=53, width=28, height=18, initial_population=6, deliberation_enabled=False, archive_every_ticks=0)
    )
    with TestClient(app) as client:
        frame = client.get("/api/frame").json()
        state = client.get("/api/state").json()
    assert frame["schema"] == "aquagenesys.frame.v3"
    assert "fields" not in frame["environment"]
    assert "lineage_story" not in frame
    assert "fields" in state["environment"]


def test_frame_endpoint_advances_at_most_one_tick_per_request() -> None:
    app = create_app(
        SimulationConfig(seed=57, width=28, height=18, initial_population=6, deliberation_enabled=False, archive_every_ticks=0)
    )
    runtime = app.state.runtime
    runtime.last_advance -= 10.0
    before = runtime.simulation.tick
    with TestClient(app) as client:
        frame = client.get("/api/frame").json()
    assert frame["tick"] <= before + 1


def test_public_demo_controls_allow_speed_but_block_unsafe_mutations() -> None:
    app = create_app(
        SimulationConfig(seed=58, width=28, height=18, initial_population=6, deliberation_enabled=False, archive_every_ticks=0),
        public_demo=True,
    )
    with TestClient(app) as client:
        speed_state = client.post("/api/control", json={"speed": 2}).json()
        reset_state = client.post("/api/control", json={"action": "reset"}).json()
        reset = client.post("/api/control", json={"action": "reset"})
        randomize = client.post("/api/control", json={"action": "randomize_environment"})
        deliberation = client.post("/api/control", json={"deliberation_enabled": True})
        state = client.get("/api/state").json()
    assert speed_state["config"]["speed"] == 2
    assert reset_state["config"]["speed"] == 2
    assert reset.status_code == 200
    assert randomize.status_code == 403
    assert deliberation.status_code == 403
    assert state["config"]["deliberation_enabled"] is False


def test_runtime_auto_resets_after_true_extinction_when_enabled() -> None:
    app = create_app(
        SimulationConfig(seed=59, width=28, height=18, initial_population=6, deliberation_enabled=False, archive_every_ticks=0),
        auto_reset_on_extinction=True,
        auto_reset_extinction_ticks=0,
    )
    runtime = app.state.runtime
    runtime.simulation.fish.clear()
    runtime.simulation.eggs.clear()
    with TestClient(app) as client:
        state = client.get("/api/state").json()
    assert state["run_id"] == "seed-59-run-2"
    assert state["telemetry"]["dead_puddle"] is False
    assert state["telemetry"]["population"] == 6


def test_fish_state_and_memory_are_externalized_to_jsonl(tmp_path) -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=29,
            width=30,
            height=20,
            initial_population=5,
            deliberation_enabled=False,
            archive_dir=str(tmp_path),
            archive_every_ticks=1,
        )
    )
    sim.step()
    state_path = tmp_path / "fish_state.jsonl"
    memory_path = tmp_path / "fish_memory.jsonl"
    assert state_path.exists()
    assert memory_path.exists()
    assert '"genome"' in state_path.read_text(encoding="utf-8")
    assert '"decision"' in memory_path.read_text(encoding="utf-8")


def test_debug_reseed_is_explicit_when_enabled() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(
            seed=31,
            width=24,
            height=18,
            initial_population=1,
            deliberation_enabled=False,
            debug_founder_reseed_enabled=True,
            debug_founder_reseed_min_population=4,
            debug_founder_reseed_after_ticks=2,
        )
    )
    sim.fish = []
    sim.run(2)
    telemetry = sim.state()["telemetry"]
    assert telemetry["births_reseed_debug"] == 4
    assert telemetry["recovery_events"] == 1
    assert telemetry["last_recovery_kind"] == "debug_reseed"
