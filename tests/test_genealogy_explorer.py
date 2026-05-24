from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def test_state_exposes_bounded_genealogy_without_frame_bloat() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=901, width=34, height=22, initial_population=6, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(4)
    state = sim.state()
    frame = sim.frame_state()
    genealogy = state["genealogy"]
    assert state["schema"] == "aquagenesys.state.v12"
    assert genealogy["schema"] == "aquagenesys.genealogy.v1"
    assert genealogy["summary"]["live_adults"] == state["telemetry"]["adult_population"]
    assert genealogy["nodes"]
    assert genealogy["lineages"]
    assert genealogy["thesis"] == "Instruction changes intent. Biology controls capability. Ecology decides what persists."
    assert "genealogy" not in frame
    assert len(str(frame)) < len(str(state)) * 0.55
    sim.close()


def test_genealogy_tracks_parent_child_and_policy_inheritance() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=902, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(902)
    parent = sim.fish[0]
    mate = sim.fish[1]
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    parent.genome = replace(parent.genome, reproduction_rate=0.96, dormancy_bias=0.88, mutation_load=0.03)
    parent.age = parent.life_history.maturity_age_ticks + 12
    parent.energy = 96.0
    parent.health = 0.96
    parent.stress = 0.02
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    perception = sim._sense(parent)
    perception.reproduction_score = 0.94
    perception.resource_score = 0.90
    perception.crowding = 0.0
    result = sim._maybe_reproduce(parent, perception)
    sim.eggs.extend(result.eggs)
    sim.fish.extend(result.newborns)
    genealogy = sim.genealogy(sim.telemetry())
    assert genealogy["edges"]
    assert any(edge["parent_fish_id"] == parent.fish_id for edge in genealogy["edges"])
    assert genealogy["policy_inheritance"]["recent_inheritance"]
    offspring_nodes = [node for node in genealogy["nodes"] if parent.fish_id in node.get("parent_ids", [])]
    assert offspring_nodes
    assert all(node["biology"]["genome_hash"] for node in offspring_nodes)
    assert all(node["behavior"]["policy_hash_short"] for node in offspring_nodes)
    sim.close()


def test_genealogy_includes_compact_dead_ancestor_snapshot() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=903, width=24, height=18, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    fish = sim.fish[0]
    fish.parent_ids = (77,)
    sim._recycle_dead(fish, "test_death")
    genealogy = sim.genealogy(sim.telemetry())
    dead_nodes = [node for node in genealogy["nodes"] if node["state"] == "dead"]
    assert dead_nodes
    assert dead_nodes[0]["parent_ids"] == [77]
    assert dead_nodes[0]["behavior"]["policy_hash_short"]
    assert "events" not in sim.dead_agent_summaries[fish.fish_id]
    sim.close()
