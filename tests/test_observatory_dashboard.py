from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def test_state_includes_grounded_observatory_dashboard() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=401, width=34, height=22, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(8)
    state = sim.state()
    dashboard = state["dashboard"]
    telemetry = state["telemetry"]
    assert state["schema"] == "aquagenesys.state.v13"
    assert dashboard["schema"] == "aquagenesys.dashboard.v2"
    assert dashboard["population"]["adults"] == telemetry["adult_population"]
    assert dashboard["population"]["lineages"] == telemetry["lineage_count"]
    assert dashboard["narrator"]["headline"]
    assert dashboard["recovery"]["phase"]
    assert dashboard["recovery"]["evidence"]
    assert str(telemetry["adult_population"]) in dashboard["narrator"]["headline"]
    assert dashboard["lineages"]["top"]
    assert dashboard["policies"]["families"]
    assert dashboard["events"]
    sim.close()


def test_dormant_dashboard_narrates_viable_egg_bank() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=402, width=30, height=20, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(7)
    parent = sim.fish[0]
    parent.genome = replace(
        parent.genome,
        parthenogenesis_alleles=2,
        parthenogenesis_bias=0.28,
        dormancy_bias=0.88,
        reproduction_rate=0.94,
        mutation_load=0.04,
    )
    parent.age = parent.life_history.senescence_start_ticks
    parent.energy = 96.0
    parent.health = 0.96
    parent.stress = 0.02
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    perception = sim._sense(parent)
    perception.reproduction_score = 0.92
    perception.resource_score = 0.88
    perception.crowding = 0.0
    eggs = sim._maybe_reproduce(parent, perception).eggs
    assert eggs
    sim.eggs = [eggs[0]]
    sim.fish = []
    sim.step()
    dashboard = sim.state()["dashboard"]
    assert dashboard["population"]["biosphere_state"] == "dormant"
    assert dashboard["population"]["viable_eggs"] > 0
    assert dashboard["recovery"]["phase"] == "dormant"
    assert dashboard["recovery"]["mechanism"] == "egg bank preserves lineage continuity"
    assert "viable eggs" in dashboard["narrator"]["headline"]
    assert dashboard["lineages"]["diversity"] == "dormant"
    sim.close()


def test_frame_contract_stays_lightweight_after_dashboard_addition() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=403, width=34, height=22, initial_population=10, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(4)
    state = sim.state()
    frame = sim.frame_state()
    assert frame["schema"] == "aquagenesys.frame.v3"
    assert "dashboard" not in frame
    assert "fields" not in frame["environment"]
    assert len(str(frame)) < len(str(state)) * 0.55
    sim.close()
