from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.agents import BehaviorInstructionGenome, TaughtSkill
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def _sim(seed: int = 741) -> AquagenesysSimulation:
    return AquagenesysSimulation(
        SimulationConfig(
            seed=seed,
            width=34,
            height=22,
            initial_population=2,
            max_population=30,
            deliberation_enabled=False,
            archive_every_ticks=0,
        )
    )


def _skill(parent, *, ttl_generations: int = 4) -> TaughtSkill:
    return TaughtSkill(
        skill_id="lineage-safe-forage",
        source_parent_id=parent.fish_id,
        source_lineage_id=parent.lineage_id,
        created_tick=0,
        generation_created=parent.generation,
        skill_type="forage",
        trigger="low_energy",
        action_bias="safe_food",
        confidence=0.82,
        energy_cost_bias=-0.05,
        risk_bias=-0.05,
        memory_bias="prefer_energy_gain",
        ttl_generations=ttl_generations,
        decay=0.10,
        rationale_tag="test_lineage_evidence",
    )


def _parent_with_skill(sim: AquagenesysSimulation) -> tuple[object, TaughtSkill]:
    parent = sim.fish[0]
    parent.instruction_genome = BehaviorInstructionGenome(
        risk_posture="cautious",
        forage_strategy="safe_food",
        energy_strategy="conserve",
        teaching_style="opportunistic",
        allowed_skill_slots=3,
    ).normalized()
    skill = _skill(parent)
    parent.taught_skills = [skill]
    return parent, skill


def _add_evidence(sim: AquagenesysSimulation, parent, skill: TaughtSkill, labels: list[str]) -> None:
    for offset, label in enumerate(labels, start=1):
        sim.tick = offset
        sim._record_skill_evidence(
            event_type="skill_outcome_observed",
            fish=parent,
            skill=skill,
            source="self",
            parent_id=parent.fish_id,
            context="hunger_or_food_opportunity",
            action="forage",
            immediate_outcome="fed" if label == "helped_possible" else "stress_cost",
            outcome_score=0.25 if label == "helped_possible" else -0.35,
            evidence_strength="moderate",
            effect_label=label,
            detail=f"Deterministic governance test evidence: {label}.",
        )


def _decision_for(skill: TaughtSkill, decisions: list[dict[str, object]]) -> dict[str, object]:
    return next(item for item in decisions if item["skill_hash"] == skill.skill_hash)


def _make_reproductive(parent, mate, sim: AquagenesysSimulation) -> None:
    parent.genome = replace(parent.genome, reproduction_rate=0.97, dormancy_bias=0.90, mutation_load=0.03)
    parent.age = parent.life_history.maturity_age_ticks + 12
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


def _good_perception(sim: AquagenesysSimulation, parent):
    perception = sim._sense(parent)
    perception.reproduction_score = 0.95
    perception.resource_score = 0.92
    perception.crowding = 0.0
    return perception


def test_insufficient_skill_evidence_is_not_inherited() -> None:
    sim = _sim(741)
    parent, skill = _parent_with_skill(sim)
    _instruction, inherited, _patch, decisions = sim._offspring_instruction_seed(
        parent,
        child_generation=parent.generation + 1,
        parthenogenetic=False,
    )
    decision = _decision_for(skill, decisions)
    assert inherited == []
    assert decision["status"] == "suppressed_insufficient_evidence"
    assert decision["confidence"] < 0.56
    assert "two recent positive" in decision["reason"]
    sim.close()


def test_positive_lineage_evidence_makes_skill_inheritable() -> None:
    sim = _sim(742)
    parent, skill = _parent_with_skill(sim)
    _add_evidence(sim, parent, skill, ["helped_possible", "helped_possible"])
    _instruction, inherited, _patch, decisions = sim._offspring_instruction_seed(
        parent,
        child_generation=parent.generation + 1,
        parthenogenetic=False,
    )
    decision = _decision_for(skill, decisions)
    assert [item.skill_hash for item in inherited] == [skill.skill_hash]
    assert decision["status"] == "inherited"
    assert decision["positive_evidence_count"] == 2
    assert decision["confidence"] >= 0.56
    sim.close()


def test_stale_and_negative_evidence_are_suppressed() -> None:
    stale = _sim(743)
    parent, skill = _parent_with_skill(stale)
    _add_evidence(stale, parent, skill, ["helped_possible", "helped_possible"])
    stale.tick = 900
    _instruction, inherited, _patch, decisions = stale._offspring_instruction_seed(
        parent,
        child_generation=parent.generation + 1,
        parthenogenetic=False,
    )
    assert inherited == []
    assert _decision_for(skill, decisions)["status"] == "suppressed_stale_evidence"
    stale.close()

    noisy = _sim(744)
    parent, skill = _parent_with_skill(noisy)
    _add_evidence(noisy, parent, skill, ["helped_possible", "harmed_possible"])
    _instruction, inherited, _patch, decisions = noisy._offspring_instruction_seed(
        parent,
        child_generation=parent.generation + 1,
        parthenogenetic=False,
    )
    decision = _decision_for(skill, decisions)
    assert inherited == []
    assert decision["status"] == "suppressed_negative_outcome"
    assert decision["negative_evidence_count"] == 1
    noisy.close()


def test_offspring_payload_explains_skill_inheritance_status() -> None:
    sim = _sim(745)
    sim.rng = LowRandom(745)
    parent, skill = _parent_with_skill(sim)
    mate = sim.fish[1]
    _add_evidence(sim, parent, skill, ["helped_possible", "helped_possible"])
    _make_reproductive(parent, mate, sim)
    result = sim._maybe_reproduce(parent, _good_perception(sim, parent))
    assert result.eggs or result.newborns
    target = result.eggs[0] if result.eggs else result.newborns[0]
    payload = target.payload()
    decision = _decision_for(skill, payload["skill_inheritance"])
    assert target.taught_skills
    assert decision["status"] == "inherited"
    assert decision["confidence"] >= 0.56
    assert decision["reason"]
    sim.close()


def test_api_state_exposes_governance_without_frame_bloat() -> None:
    sim = _sim(746)
    sim.rng = LowRandom(746)
    parent, skill = _parent_with_skill(sim)
    mate = sim.fish[1]
    _add_evidence(sim, parent, skill, ["helped_possible", "helped_possible"])
    _make_reproductive(parent, mate, sim)
    result = sim._maybe_reproduce(parent, _good_perception(sim, parent))
    assert result.eggs
    sim.eggs = result.eggs
    state = sim.state()
    frame = sim.frame_state()
    assert state["schema"] == "aquagenesys.state.v13"
    assert state["telemetry"]["skill_evidence"]["summary"]["inherited_skill_hints"] >= 1
    assert state["telemetry"]["instruction"]["skills_inherited_by_evidence"] >= 1
    assert state["eggs"][0]["skill_inheritance"][0]["status"] == "inherited"
    assert "skill_evidence" not in frame
    assert "skill_inheritance" not in frame["fish"][0]
    sim.close()


def test_lineage_story_suppresses_unsupported_skill_without_overclaiming() -> None:
    sim = _sim(747)
    sim.rng = LowRandom(747)
    parent, _skill = _parent_with_skill(sim)
    mate = sim.fish[1]
    _make_reproductive(parent, mate, sim)
    result = sim._maybe_reproduce(parent, _good_perception(sim, parent))
    assert result.eggs or result.newborns
    sim.eggs = result.eggs
    sim.fish.extend(result.newborns)
    story = sim.state()["lineage_story"]
    target_lineage = (result.eggs[0].lineage_id if result.eggs else result.newborns[0].lineage_id)
    lineage_story = next(item for item in story["lineage_stories"] if item["lineage_id"] == target_lineage)
    answer_text = " ".join(lineage_story["answers"].values()).lower()
    assert story["schema"] == "aquagenesys.lineage_story.v5"
    assert "not inherited because" in answer_text or "suppressed" in answer_text
    for banned in ("caused", "guaranteed", "proved", "learned intelligently"):
        assert banned not in answer_text
    sim.close()
