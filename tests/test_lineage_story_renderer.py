from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def _force_reproduction(sim: AquagenesysSimulation) -> int:
    sim.rng = LowRandom(991)
    parent = sim.fish[0]
    mate = sim.fish[1]
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    parent.genome = replace(parent.genome, reproduction_rate=0.97, dormancy_bias=0.88, mutation_load=0.03)
    parent.age = parent.life_history.maturity_age_ticks + 16
    parent.energy = 96.0
    parent.health = 0.97
    parent.stress = 0.02
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    perception = sim._sense(parent)
    perception.reproduction_score = 0.95
    perception.resource_score = 0.92
    perception.crowding = 0.0
    result = sim._maybe_reproduce(parent, perception)
    sim.eggs.extend(result.eggs)
    sim.fish.extend(result.newborns)
    return parent.lineage_id


def test_state_exposes_lineage_story_without_frame_bloat() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=990, width=34, height=22, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(6)
    state = sim.state()
    frame = sim.frame_state()
    story = state["lineage_story"]
    assert state["schema"] == "aquagenesys.state.v13"
    assert story["schema"] == "aquagenesys.lineage_story.v5"
    assert story["bounded"]["model_dependency"] is False
    assert story["summary"]["questions_answered"] == [
        "Who survived?",
        "What did they inherit?",
        "What changed?",
        "What did they try?",
        "What killed the others?",
        "Why did this lineage persist?",
    ]
    assert len(story["questions"]) == 6
    assert all(item["answer"] for item in story["questions"])
    assert "lineage_story" not in frame
    assert len(str(frame)) < len(str(state)) * 0.55
    sim.close()


def test_lineage_story_is_grounded_in_inheritance_attempts_and_losses() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=991, width=34, height=22, initial_population=3, max_population=28, deliberation_enabled=False, archive_every_ticks=0)
    )
    lineage_id = _force_reproduction(sim)
    victim = next(fish for fish in sim.fish if fish.lineage_id == lineage_id)
    sim._recycle_dead(victim, "test_attrition")
    story = sim.state()["lineage_story"]
    lineage_story = next(item for item in story["lineage_stories"] if item["lineage_id"] == lineage_id)
    answer_text = " ".join(lineage_story["answers"].values())
    assert f"L{lineage_id}" in lineage_story["answers"]["who_survived"]
    assert "policy" in lineage_story["answers"]["inherited"]
    assert "instruction inheritances" in lineage_story["answers"]["tried"]
    assert "test attrition" in answer_text
    assert any(item["cause"] == "test_attrition" for item in lineage_story["losses"])
    assert lineage_story["biology_track"]
    assert lineage_story["behavior_track"]
    assert lineage_story["attempts"]
    sim.close()


def test_lineage_story_renderer_is_deterministic_for_same_state() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=992, width=34, height=22, initial_population=6, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(8)
    telemetry = sim.telemetry()
    dashboard = sim.dashboard(telemetry)
    genealogy = sim.genealogy(telemetry)
    first = sim.lineage_story(telemetry, dashboard=dashboard, genealogy=genealogy)
    second = sim.lineage_story(telemetry, dashboard=dashboard, genealogy=genealogy)
    assert first == second
    assert first["summary"]["story_count"] <= first["bounded"]["max_stories"]
    sim.close()
