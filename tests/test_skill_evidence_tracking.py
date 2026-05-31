from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.agents import Action, BehaviorInstructionGenome, TaughtSkill
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def _make_skill_carrying_child(sim: AquagenesysSimulation):
    sim.rng = LowRandom(701)
    parent = sim.fish[0]
    mate = sim.fish[1]
    parent.instruction_genome = BehaviorInstructionGenome(
        risk_posture="cautious",
        forage_strategy="safe_food",
        energy_strategy="conserve",
        teaching_style="opportunistic",
        allowed_skill_slots=3,
    ).normalized()
    skill = TaughtSkill(
        skill_id="safe-forage-demo",
        source_parent_id=parent.fish_id,
        source_lineage_id=parent.lineage_id,
        created_tick=0,
        generation_created=parent.generation,
        skill_type="forage",
        trigger="low_energy",
        action_bias="safe_food",
        confidence=0.78,
        energy_cost_bias=-0.05,
        risk_bias=-0.05,
        memory_bias="prefer_energy_gain",
        ttl_generations=4,
        decay=0.12,
        rationale_tag="test_supported_skill",
    )
    parent.taught_skills = [skill]
    for tick in (1, 2):
        sim.tick = tick
        sim._record_skill_evidence(
            event_type="skill_outcome_observed",
            fish=parent,
            skill=skill,
            source="self",
            parent_id=parent.fish_id,
            context="hunger_or_food_opportunity",
            action="forage",
            immediate_outcome="fed",
            outcome_score=0.25,
            evidence_strength="moderate",
            effect_label="helped_possible",
            detail="Test setup records repeated positive skill observations.",
        )
    parent.genome = replace(parent.genome, reproduction_rate=0.97, dormancy_bias=0.90, mutation_load=0.03)
    parent.age = parent.life_history.maturity_age_ticks + 14
    parent.energy = 96.0
    parent.health = 0.97
    parent.stress = 0.02
    parent.fear = 0.02
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    parent.x = sim.config.width / 2
    parent.y = sim.config.height / 2
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    parent.memory.record(1, Action("forage", 1, 0, 0.5, "habit", "test"), outcome="fed", delta_energy=1.0, delta_health=0.0)
    parent.memory.record(2, Action("forage", 1, 0, 0.5, "habit", "test"), outcome="fed", delta_energy=1.0, delta_health=0.0)
    perception = sim._sense(parent)
    perception.reproduction_score = 0.95
    perception.resource_score = 0.92
    perception.crowding = 0.0
    result = sim._maybe_reproduce(parent, perception)
    assert result.eggs
    egg = result.eggs[0]
    child = sim._hatch_egg(egg, sim.environment.sample(egg.x, egg.y).payload())
    assert child.taught_skills
    sim.fish = [child]
    sim.eggs = []
    return parent, child


def _set_food_patch(sim: AquagenesysSimulation, fish) -> None:
    ix = int(round(fish.x))
    iy = int(round(fish.y))
    for yy in range(max(0, iy - 3), min(sim.environment.height, iy + 4)):
        for xx in range(max(0, ix - 3), min(sim.environment.width, ix + 4)):
            sim.environment.fields["food"][yy][xx] = 1.0
            sim.environment.fields["plankton"][yy][xx] = 0.8
            sim.environment.fields["nutrients"][yy][xx] = 0.8
            sim.environment.fields["oxygen"][yy][xx] = 0.9
            sim.environment.fields["shelter"][yy][xx] = 0.6
            sim.environment.fields["toxins"][yy][xx] = 0.0
            sim.environment.fields["reproduction"][yy][xx] = 0.85


def test_skill_inheritance_is_recorded_and_aggregated() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=701, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    _parent, child = _make_skill_carrying_child(sim)
    state = sim.state()
    evidence = state["telemetry"]["skill_evidence"]
    assert state["schema"] == "aquagenesys.state.v13"
    assert evidence["schema"] == "aquagenesys.skill_evidence.v2"
    assert any(event["event_type"] == "skill_inherited" and event["child_id"] == child.fish_id for event in evidence["recent_events"])
    assert any(event["event_type"] == "skill_inheritance_governance" and event["status"] == "inherited" for event in evidence["recent_events"])
    aggregate = next(
        row
        for row in evidence["aggregates"]
        if row["skill_hash"] == child.taught_skills[0].skill_hash and row["carriers_count"] >= 1
    )
    assert aggregate["carriers_count"] >= 1
    assert aggregate["offspring_carriers_count"] >= 1
    assert state["dashboard"]["skill_evidence"]["aggregates"]
    assert state["genealogy"]["skill_evidence"]["aggregates"]
    assert "skill_evidence" not in sim.frame_state()
    sim.close()


def test_skill_use_outcome_and_descendant_reproduction_are_tracked() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=702, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    _parent, child = _make_skill_carrying_child(sim)
    child.hunger = 0.66
    child.energy = 44.0
    child.health = 0.92
    child.stress = 0.04
    child.fear = 0.04
    _set_food_patch(sim, child)
    sim.step()
    evidence = sim.telemetry()["skill_evidence"]
    use_event = next(event for event in evidence["recent_events"] if event["event_type"] == "skill_outcome_observed")
    assert use_event["fish_id"] == child.fish_id
    assert use_event["context"] == "hunger_or_food_opportunity"
    assert use_event["action"] in {"forage", "filter_feed", "graze", "scavenge", "anchor_feed", "hunt", "strike"}
    assert use_event["context_tags"] or use_event["affordance_tags"]
    assert use_event["effect_label"] == "helped_possible"
    aggregate = next(row for row in evidence["aggregates"] if row["skill_hash"] == child.taught_skills[0].skill_hash)
    assert aggregate["users_count"] >= 1
    assert aggregate["uses_count"] >= 1
    assert aggregate["helped_possible_count"] >= 1
    assert aggregate["survival_ticks_after_use"] >= 0

    child.age = child.life_history.maturity_age_ticks + 10
    child.energy = 98.0
    child.health = 0.96
    child.reproductive_drive = 0.99
    child.reproduction_cooldown = 0
    mate_sim = AquagenesysSimulation(SimulationConfig(seed=703, width=34, height=22, initial_population=1, deliberation_enabled=False, archive_every_ticks=0))
    mate = mate_sim.fish[0]
    mate.genome = replace(mate.genome, metabolism=child.genome.metabolism)
    mate.x = child.x + 1.0
    mate.y = child.y + 1.0
    sim.fish.append(mate)
    sim.rng = LowRandom(704)
    perception = sim._sense(child)
    perception.reproduction_score = 0.95
    perception.resource_score = 0.92
    perception.crowding = 0.0
    result = sim._maybe_reproduce(child, perception)
    assert result.eggs or result.newborns
    aggregate = next(row for row in sim.telemetry()["skill_evidence"]["aggregates"] if row["skill_hash"] == child.taught_skills[0].skill_hash)
    assert aggregate["reproduction_after_use_count"] >= 1
    mate_sim.close()
    sim.close()


def test_lineage_story_reports_skill_evidence_without_causal_overclaim() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=704, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    _parent, child = _make_skill_carrying_child(sim)
    child.hunger = 0.66
    child.energy = 44.0
    child.health = 0.92
    child.stress = 0.04
    child.fear = 0.04
    _set_food_patch(sim, child)
    sim.step()
    story = sim.state()["lineage_story"]
    lineage_story = next(item for item in story["lineage_stories"] if item["lineage_id"] == child.lineage_id)
    answer_text = " ".join(lineage_story["answers"].values())
    assert story["schema"] == "aquagenesys.lineage_story.v5"
    assert lineage_story["skill_evidence"]["aggregates"]
    assert "Skill inheritance gate" in answer_text
    assert "observational" in answer_text
    assert "caused success" not in answer_text.lower()
    sim.close()
