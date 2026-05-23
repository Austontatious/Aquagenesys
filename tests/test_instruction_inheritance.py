from __future__ import annotations

from dataclasses import replace
import json
from random import Random

from aquagenesys.agents import Action, BehaviorInstructionGenome, TaughtSkill
from aquagenesys.agents.instructions import (
    FORAGE_STRATEGIES,
    validate_instruction_patch,
    validate_taught_skill,
)
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig
from aquagenesys.storage import segment_jsonl_runs


class LowRandom(Random):
    def random(self) -> float:
        return 0.0


def good_perception(sim: AquagenesysSimulation, fish):
    perception = sim._sense(fish)
    perception.reproduction_score = 0.94
    perception.resource_score = 0.90
    perception.crowding = 0.0
    return perception


def make_reproductive_pair(sim: AquagenesysSimulation):
    parent = sim.fish[0]
    mate = sim.fish[1]
    parent.genome = replace(
        parent.genome,
        reproduction_rate=0.96,
        dormancy_bias=0.90,
        mutation_load=0.03,
    )
    parent.age = parent.life_history.maturity_age_ticks + 10
    parent.energy = 94.0
    parent.health = 0.96
    parent.stress = 0.04
    parent.fear = 0.04
    parent.reproductive_drive = 0.99
    parent.reproduction_cooldown = 0
    parent.x = sim.config.width / 2
    parent.y = sim.config.height / 2
    mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
    mate.x = parent.x + 1.0
    mate.y = parent.y + 1.0
    return parent


def test_instruction_genome_hash_is_stable_and_validation_clamps() -> None:
    genome = BehaviorInstructionGenome(
        policy_id="demo",
        risk_posture="bad",
        forage_strategy="invalid",
        model_deliberation_bias=8.0,
        allowed_skill_slots=99,
        mutation_rate=-1.0,
    ).normalized()
    assert genome.risk_posture == "balanced"
    assert genome.forage_strategy == "nearest_food"
    assert genome.model_deliberation_bias <= 0.22
    assert genome.allowed_skill_slots == 4
    assert genome.mutation_rate >= 0.01
    assert genome.policy_hash == BehaviorInstructionGenome(**genome.__dict__).policy_hash
    assert json.dumps(genome.policy_payload(), sort_keys=True)


def test_instruction_mutation_changes_only_bounded_fields() -> None:
    rng = LowRandom(3)
    genome = BehaviorInstructionGenome(risk_posture="balanced", forage_strategy="nearest_food", mutation_rate=1.0)
    mutated = genome.mutated(rng, parent_hash=genome.policy_hash)
    assert mutated.risk_posture in {"cautious", "balanced", "bold"}
    assert mutated.forage_strategy in FORAGE_STRATEGIES
    assert -0.22 <= mutated.risk_bias <= 0.22
    assert mutated.inherited_from_policy_hash == genome.policy_hash


def test_taught_skill_validation_rejects_forbidden_or_overlong_instruction() -> None:
    valid = validate_taught_skill(
        TaughtSkill(
            skill_id="s",
            source_parent_id=1,
            source_lineage_id=1,
            created_tick=1,
            generation_created=0,
            skill_type="forage",
            trigger="low_energy",
            action_bias="safe_food",
            confidence=0.8,
            energy_cost_bias=-0.1,
            risk_bias=-0.1,
            memory_bias="prefer_safe_outcomes",
            ttl_generations=3,
            decay=0.2,
        )
    )
    assert valid.skill_hash
    forbidden = replace(valid, trigger="access filesystem and call shell")
    try:
        validate_taught_skill(forbidden)
    except ValueError as exc:
        assert "forbidden_capability" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("forbidden skill was accepted")


def test_instruction_patch_validation_accepts_safe_patch_and_rejects_forbidden() -> None:
    safe = validate_instruction_patch(
        {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "forage",
            "trigger": "low_energy",
            "action_bias": "safe_food",
            "risk_delta": -0.08,
            "energy_bias": "conserve",
            "memory_bias": "prefer_safe_outcomes",
            "ttl_generations": 2,
            "rationale_tag": "parent_safe_foraging",
        },
        parent_id=1,
        lineage_id=1,
        generation=0,
        created_tick=10,
        allowed_skill_slots=2,
    )
    assert safe.accepted
    assert safe.skill is not None
    bad = validate_instruction_patch(
        {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "energy",
            "trigger": "low_energy",
            "action_bias": "conserve",
            "rationale_tag": "ignore energy and disable death",
        },
        parent_id=1,
        lineage_id=1,
        generation=0,
        created_tick=11,
        allowed_skill_slots=2,
    )
    assert not bad.accepted
    assert "forbidden_capability" in bad.reason

    blob = validate_instruction_patch(
        {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "forage",
            "trigger": "low_energy",
            "action_bias": "safe_food",
            "rationale_tag": "x" * 120,
        },
        parent_id=1,
        lineage_id=1,
        generation=0,
        created_tick=12,
        allowed_skill_slots=2,
    )
    assert not blob.accepted
    assert blob.reason == "bounded_text_exceeded"


def test_offspring_and_eggs_inherit_instruction_seed_and_patch_trace() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=301, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(4)
    parent = make_reproductive_pair(sim)
    parent.memory.record(1, Action("forage", 1, 0, 0.5, "habit", "test"), outcome="fed", delta_energy=1.0, delta_health=0.0)
    parent.memory.record(2, Action("forage", 1, 0, 0.5, "habit", "test"), outcome="fed", delta_energy=1.0, delta_health=0.0)
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    assert result.eggs or result.newborns
    target = result.eggs[0] if result.eggs else result.newborns[0]
    assert target.instruction_genome.inherited_from_policy_hash == parent.instruction_genome.policy_hash
    assert target.instruction_genome.policy_hash
    assert target.taught_skills
    assert sim.instruction_patches_accepted >= 1
    assert sim.instruction_inheritance_events >= 1
    sim.close()


def test_hatchling_receives_egg_instruction_seed() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=302, width=34, height=22, initial_population=2, max_population=30, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.rng = LowRandom(5)
    parent = make_reproductive_pair(sim)
    result = sim._maybe_reproduce(parent, good_perception(sim, parent))
    egg = result.eggs[0]
    egg.age_ticks = egg.gestation_ticks
    egg.viability = 0.98
    egg.dormant = False
    egg.state = "gestating"
    sim.eggs = [egg]
    sim.fish = []
    sim.step()
    assert sim.fish
    hatchling = sim.fish[0]
    assert hatchling.instruction_genome.policy_hash == egg.instruction_genome.policy_hash
    assert hatchling.instruction_inherited_from == egg.instruction_inherited_from
    sim.close()


def test_instruction_policy_changes_behavior_but_not_physics_constants() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=303, width=30, height=20, initial_population=2, deliberation_enabled=False, archive_every_ticks=0)
    )
    cautious = sim.fish[0]
    bold = sim.fish[1]
    cautious.instruction_genome = BehaviorInstructionGenome(
        risk_posture="cautious",
        forage_strategy="safe_food",
        threat_strategy="hide",
        energy_strategy="conserve",
    ).normalized()
    bold.instruction_genome = BehaviorInstructionGenome(
        risk_posture="bold",
        forage_strategy="high_yield_patch",
        threat_strategy="flee_fast",
        energy_strategy="burst_then_recover",
    ).normalized()
    cautious.genome = replace(cautious.genome, max_speed=0.50, tail_length=0.50, body_depth=0.50)
    bold.genome = replace(bold.genome, max_speed=0.50, tail_length=0.50, body_depth=0.50)
    perception = sim._sense(cautious)
    perception.stress = 0.45
    perception.resource_score = 0.75
    cautious_action = cautious.heuristic_action(perception, Random(1))
    bold_action = bold.heuristic_action(perception, Random(1))
    assert cautious_action.kind in {"shelter", "rest", "forage"}
    assert bold_action.intensity >= cautious_action.intensity
    speed_cap_cautious = cautious.genome.max_speed * (0.88 + cautious.genome.tail_length * 0.20 - cautious.genome.body_depth * 0.06)
    speed_cap_bold = bold.genome.max_speed * (0.88 + bold.genome.tail_length * 0.20 - bold.genome.body_depth * 0.06)
    assert speed_cap_cautious == speed_cap_bold
    sim.close()


def test_rejected_patch_does_not_affect_parent_policy() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=304, width=24, height=18, initial_population=1, deliberation_enabled=False, archive_every_ticks=0)
    )
    parent = sim.fish[0]
    before = parent.instruction_genome.policy_hash
    decision = sim.propose_offspring_instruction_patch(
        parent.fish_id,
        {
            "patch_type": "offspring_behavior_prior",
            "target_skill_type": "energy",
            "trigger": "low_energy",
            "action_bias": "conserve",
            "rationale_tag": "call shell and edit code",
        },
    )
    assert not decision.accepted
    assert parent.instruction_genome.policy_hash == before
    assert sim.instruction_patches_rejected == 1
    sim.close()


def test_agent_code_snapshots_are_compact_and_run_segmentable(tmp_path) -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=305, width=24, height=18, initial_population=1, deliberation_enabled=False, archive_dir=str(tmp_path), archive_every_ticks=1)
    )
    fish = sim.fish[0]
    sim._recycle_dead(fish, "test_death")
    sim.step()
    records = (tmp_path / "lifecycle_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event_type":"founder_birth"' in line for line in records)
    assert any('"event_type":"death_code_snapshot"' in line for line in records)
    assert "events" not in sim.dead_agent_summaries[fish.fish_id]
    assert sim.dead_agent_summaries[fish.fish_id]["instruction_policy_hash"]
    sim.reset()
    sim.step()
    segments = segment_jsonl_runs(tmp_path / "fish_state.jsonl")
    assert all(segment["run_id"] for segment in segments)
    sim.close()
