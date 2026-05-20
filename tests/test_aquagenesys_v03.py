from __future__ import annotations

from dataclasses import dataclass
import json
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
    assert state["schema"] == "aquagenesys.state.v3"
    assert state["fish"]
    assert state["telemetry"]["population"] > 0
    assert state["telemetry"]["agent_decisions"]
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
    assert frame["schema"] == "aquagenesys.frame.v1"
    assert "fields" not in frame["environment"]
    assert frame["fish"][0]["decision"]
    assert frame["fish"][0]["genome"]["archetype"]
    assert len(json.dumps(frame)) < len(json.dumps(state)) * 0.55
    sim.close()


def test_frame_endpoint_does_not_return_full_environment_grid() -> None:
    app = create_app(
        SimulationConfig(seed=53, width=28, height=18, initial_population=6, deliberation_enabled=False, archive_every_ticks=0)
    )
    with TestClient(app) as client:
        frame = client.get("/api/frame").json()
        state = client.get("/api/state").json()
    assert frame["schema"] == "aquagenesys.frame.v1"
    assert "fields" not in frame["environment"]
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
