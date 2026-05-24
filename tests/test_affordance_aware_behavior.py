from __future__ import annotations

from dataclasses import replace
from random import Random

from aquagenesys.agents import BehaviorInstructionGenome, FishAgent, FishGenome, Perception
from aquagenesys.agents.behavior import build_behavior_decision, derive_affordance_tags, derive_context_tags
from aquagenesys.agents.instructions import TaughtSkill
from aquagenesys.agents.morphology import (
    AppendageLoci,
    ArmorSkinLoci,
    BodyScaffoldLoci,
    HeadMouthLoci,
    MorphologyGenome,
    SensoryLoci,
)
from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig
from aquagenesys.simulation.skill_evidence import matched_skills_for_action


def _perception(**overrides: object) -> Perception:
    sample = {
        "food": 0.72,
        "plankton": 0.72,
        "nutrients": 0.68,
        "oxygen": 0.86,
        "toxins": 0.02,
        "decomposition": 0.18,
        "shelter": 0.34,
        "reproduction": 0.24,
        "balance": 0.54,
    }
    sample.update(overrides.pop("sample", {}) or {})
    data = {
        "sample": sample,
        "gradients": {"food": (1.0, 0.0), "shelter": (0.0, 1.0), "current": (0.1, 0.0)},
        "nearest_food": (1.0, 0.0, 3.0),
        "nearest_shelter": (0.0, 1.0, 5.0),
        "nearest_mate": (0.0, 0.0, 999.0),
        "nearest_prey": (1.0, 0.0, 999.0),
        "nearest_threat": (0.0, 0.0, 999.0),
        "neighbor_count": 0,
        "crowding": 0.0,
        "stress": 0.10,
        "resource_score": 0.82,
        "reproduction_score": 0.10,
        "edge_vector": (0.0, 0.0),
    }
    data.update(overrides)
    return Perception(**data)


def _fish(
    morphology: MorphologyGenome,
    instruction: BehaviorInstructionGenome | None = None,
    *,
    fish_id: int = 1,
    energy: float = 55.0,
    hunger: float = 0.68,
) -> FishAgent:
    genome = FishGenome.founder(Random(100 + fish_id), lineage_id=1, archetype="glass_filter")
    genome = replace(genome, morphology=morphology, max_speed=0.82, aggression=0.70, sensory_range=10.0)
    return FishAgent(
        fish_id=fish_id,
        species_id=f"test-{fish_id}",
        lineage_id=1,
        genome=genome,
        x=12.0,
        y=10.0,
        vx=0.0,
        vy=0.0,
        energy=energy,
        hunger=hunger,
        fear=0.10,
        stress=0.10,
        health=0.92,
        reproductive_drive=0.10,
        instruction_genome=instruction or BehaviorInstructionGenome(),
    )


def _candidate(decision, action: str):
    return next(item for item in decision.candidates if item.action == action)


def test_affordance_scoring_prefers_filter_and_bite_actions_by_body_context() -> None:
    base = MorphologyGenome.balanced()
    filter_body = replace(
        base,
        head_mouth=HeadMouthLoci(
            head_mass_ratio=0.18,
            mouth_position="filter_slot",
            mouth_aperture=0.40,
            mouth_force=0.10,
            mouth_suction=1.0,
            gut_capacity=0.90,
            filter_surface_area=1.0,
        ),
        development=replace(base.development, oxygen_demand=0.34),
    )
    filter_fish = _fish(filter_body, BehaviorInstructionGenome(forage_strategy="safe_food", energy_strategy="conserve"))
    bloom = _perception(sample={"plankton": 0.94, "nutrients": 0.90, "food": 0.40}, resource_score=0.88)
    filter_decision = build_behavior_decision(filter_fish, bloom, Random(1), biosphere_state="active", population=8)
    assert filter_decision.selected.action == "filter_feed"
    assert _candidate(filter_decision, "filter_feed").score > _candidate(filter_decision, "strike").score
    assert "high_filter" in filter_decision.affordance_tags

    bite_body = replace(
        base,
        body=replace(base.body, body_mass=0.65, body_length=0.75),
        head_mouth=HeadMouthLoci(
            head_mass_ratio=1.0,
            mouth_position="terminal",
            mouth_aperture=1.0,
            mouth_force=1.0,
            mouth_suction=0.10,
            gut_capacity=0.60,
            filter_surface_area=0.10,
        ),
        appendage=replace(base.appendage, propulsion_surface=0.90),
        sensory=SensoryLoci(0.90, 0.90, 0.90, 0.90),
        development=replace(base.development, oxygen_demand=0.35),
    )
    bite_fish = _fish(
        bite_body,
        BehaviorInstructionGenome(risk_posture="bold", forage_strategy="high_yield_patch", energy_strategy="burst_then_recover"),
    )
    prey_context = _perception(nearest_prey=(1.0, 0.0, 3.0), sample={"food": 0.30, "plankton": 0.10}, resource_score=0.40)
    bite_decision = build_behavior_decision(bite_fish, prey_context, Random(2), biosphere_state="active", population=8)
    assert bite_decision.selected.action in {"strike", "hunt"}
    assert _candidate(bite_decision, "strike").score > _candidate(bite_decision, "filter_feed").score
    assert "high_bite" in bite_decision.affordance_tags


def test_threat_and_drag_costs_change_candidate_ranking() -> None:
    base = MorphologyGenome.balanced()
    soft_body = replace(
        base,
        body=replace(base.body, soft_tissue_ratio=1.0),
        armor_skin=ArmorSkinLoci(armor_density=0.02, spine_density=0.0, tissue_vulnerability=1.0, mucous_barrier=0.05),
    )
    armored_body = replace(
        base,
        body=replace(base.body, body_mass=0.85),
        armor_skin=ArmorSkinLoci(armor_density=1.0, spine_density=0.80, tissue_vulnerability=0.10, mucous_barrier=0.60),
    )
    threat_context = _perception(
        nearest_threat=(1.0, 0.0, 1.0),
        nearest_shelter=(0.0, 1.0, 2.0),
        sample={"food": 0.10, "plankton": 0.10, "shelter": 0.80},
        resource_score=0.10,
        stress=0.80,
    )
    soft_fish = _fish(soft_body, BehaviorInstructionGenome(risk_posture="cautious", threat_strategy="hide"), energy=40.0, hunger=0.40)
    soft_fish.fear = 0.70
    soft_fish.stress = 0.70
    armored_fish = _fish(armored_body, BehaviorInstructionGenome(risk_posture="cautious", threat_strategy="hide"), energy=40.0, hunger=0.40)
    armored_fish.fear = 0.70
    armored_fish.stress = 0.70
    soft_decision = build_behavior_decision(soft_fish, threat_context, Random(3), population=8)
    armor_decision = build_behavior_decision(armored_fish, threat_context, Random(3), population=8)
    assert soft_decision.selected.action in {"shelter", "flee"}
    assert _candidate(soft_decision, "flee").expected_risk > _candidate(armor_decision, "flee").expected_risk
    assert "soft_body" in soft_decision.affordance_tags
    assert "high_armor" in armor_decision.affordance_tags

    appendage_body = replace(
        base,
        appendage=AppendageLoci(appendage_count=12, appendage_length=1.10, appendage_flexibility=0.90, appendage_strength=0.80, propulsion_surface=0.10),
        development=replace(base.development, oxygen_demand=0.82),
    )
    appendage_fish = _fish(appendage_body, BehaviorInstructionGenome(forage_strategy="opportunistic_scavenge", energy_strategy="conserve"))
    detritus = _perception(sample={"decomposition": 0.82, "food": 0.30, "plankton": 0.12}, resource_score=0.55)
    appendage_decision = build_behavior_decision(appendage_fish, detritus, Random(4), population=8)
    assert appendage_decision.selected.action in {"scavenge", "anchor_feed"}
    assert _candidate(appendage_decision, "hunt").expected_cost > _candidate(appendage_decision, "anchor_feed").expected_cost
    assert {"high_reach", "high_drag", "high_oxygen_cost"}.issubset(set(appendage_decision.affordance_tags))


def test_policy_body_interaction_changes_same_policy_outcome() -> None:
    base = MorphologyGenome.balanced()
    policy = BehaviorInstructionGenome(risk_posture="bold", forage_strategy="high_yield_patch", energy_strategy="burst_then_recover")
    bite_body = replace(
        base,
        head_mouth=replace(base.head_mouth, head_mass_ratio=0.98, mouth_force=1.0, mouth_aperture=1.0, filter_surface_area=0.08),
        sensory=SensoryLoci(0.90, 0.90, 0.90, 0.90),
    )
    filter_drag_body = replace(
        base,
        head_mouth=replace(base.head_mouth, mouth_position="filter_slot", mouth_suction=1.0, filter_surface_area=1.0, mouth_force=0.08, gut_capacity=0.90),
        body=BodyScaffoldLoci(body_mass=1.0, body_length=0.70, body_depth=0.86, body_axis_length=0.70, body_axis_depth=0.86, surface_area=0.84, soft_tissue_ratio=0.46, reserve_capacity=0.82),
        development=replace(base.development, oxygen_demand=0.86),
    )
    prey_context = _perception(nearest_prey=(1.0, 0.0, 2.5), sample={"food": 0.42, "plankton": 0.82}, resource_score=0.72)
    bite_decision = build_behavior_decision(_fish(bite_body, policy, fish_id=2), prey_context, Random(5), population=8)
    filter_decision = build_behavior_decision(_fish(filter_drag_body, policy, fish_id=3), prey_context, Random(5), population=8)
    assert bite_decision.selected.action in {"strike", "hunt"}
    assert filter_decision.selected.action in {"filter_feed", "anchor_feed", "forage"}
    assert _candidate(filter_decision, "hunt").score < _candidate(bite_decision, "hunt").score
    assert "high-yield prior conflicts with costly body plan" in filter_decision.mismatch_warnings

    energy_saver = BehaviorInstructionGenome(forage_strategy="safe_food", energy_strategy="conserve")
    conserved = build_behavior_decision(_fish(filter_drag_body, energy_saver, fish_id=4), prey_context, Random(6), population=8)
    assert conserved.selected.action in {"filter_feed", "anchor_feed"}
    assert any("energy saver" in item for item in conserved.policy_influence)


def test_context_tags_and_affordance_tags_are_recorded() -> None:
    base = MorphologyGenome.balanced()
    tagged_body = replace(
        base,
        head_mouth=replace(base.head_mouth, mouth_position="filter_slot", mouth_suction=1.0, filter_surface_area=1.0, mouth_force=0.08),
        armor_skin=replace(base.armor_skin, armor_density=0.92),
        chemical=replace(base.chemical, chemical_gland_capacity=0.78, chemical_delivery_efficiency=0.72),
        development=replace(base.development, oxygen_demand=0.92),
    )
    fish = _fish(tagged_body)
    context = _perception(
        sample={"plankton": 0.88, "nutrients": 0.90, "oxygen": 0.18, "toxins": 0.72, "decomposition": 0.56, "shelter": 0.62},
        nearest_threat=(1.0, 0.0, 2.0),
        nearest_prey=(1.0, 0.0, 4.0),
        nearest_mate=(1.0, 0.0, 4.0),
        neighbor_count=9,
        crowding=0.38,
        resource_score=0.20,
        stress=0.62,
    )
    context_tags = set(derive_context_tags(fish, context, biosphere_state="recovering", population=3))
    affordance_tags = set(derive_affordance_tags(fish))
    assert {"scarcity", "bloom", "crowded", "low_oxygen", "high_toxin", "predator_near", "prey_near", "mate_near", "bottleneck", "recovery", "near_detritus", "near_shelter"}.issubset(context_tags)
    assert {"high_filter", "high_suction", "high_armor", "high_toxin", "high_oxygen_cost"}.issubset(affordance_tags)


def test_skill_evidence_can_carry_behavior_context_without_causal_overclaim() -> None:
    base = MorphologyGenome.balanced()
    filter_body = replace(base, head_mouth=replace(base.head_mouth, mouth_position="filter_slot", mouth_suction=1.0, filter_surface_area=1.0, mouth_force=0.08))
    fish = _fish(filter_body, BehaviorInstructionGenome(forage_strategy="safe_food", energy_strategy="conserve"))
    skill = TaughtSkill(
        skill_id="test-skill",
        source_parent_id=99,
        source_lineage_id=1,
        created_tick=1,
        generation_created=0,
        skill_type="forage",
        trigger="hunger",
        action_bias="safe_food",
        confidence=0.80,
        energy_cost_bias=-0.10,
        risk_bias=-0.10,
        memory_bias="prefer_safe_outcomes",
        ttl_generations=3,
        decay=0.05,
    )
    fish.taught_skills = [skill]
    context = _perception(sample={"plankton": 0.92, "food": 0.38}, resource_score=0.86)
    decision = build_behavior_decision(fish, context, Random(7), population=8)
    fish.last_behavior_rationale = decision.payload()
    matches = matched_skills_for_action(fish, context, decision.to_action())
    assert matches
    assert "bloom" in matches[0]["context_tags"]
    assert "high_filter" in matches[0]["affordance_tags"]

    sim = AquagenesysSimulation(SimulationConfig(seed=714, width=24, height=18, initial_population=0, deliberation_enabled=False, archive_every_ticks=0))
    sim.fish = [fish]
    sim._record_skill_evidence(
        event_type="skill_outcome_observed",
        fish=fish,
        skill=skill,
        source="inherited",
        context=matches[0]["context"],
        action=decision.selected.action,
        immediate_outcome="fed",
        outcome_score=0.1,
        evidence_strength="weak",
        effect_label="helped_possible",
        context_tags=matches[0]["context_tags"],
        affordance_tags=matches[0]["affordance_tags"],
        detail="observed bounded context only",
    )
    event = sim.telemetry()["skill_evidence"]["recent_events"][0]
    assert event["effect_label"] == "helped_possible"
    assert event["context_tags"]
    assert event["affordance_tags"]
    assert "caused" not in sim.telemetry()["skill_evidence"]["summary"]["claim_boundary"].lower()
    sim.close()


def test_state_exposes_bounded_behavior_rationale_without_frame_bloat() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=741, width=34, height=22, initial_population=8, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(4)
    state = sim.state()
    frame = sim.frame_state()
    assert state["schema"] == "aquagenesys.state.v12"
    assert state["behavior"]["schema"] == "aquagenesys.behavior.v1"
    assert state["behavior"]["organisms"]
    first = state["behavior"]["organisms"][0]
    assert first["current_action"]
    assert first["candidate_summary"]
    assert "behavior" not in frame
    assert "behavior" not in frame["fish"][0]
    assert frame["schema"] == "aquagenesys.frame.v3"
    assert len(str(frame)) < len(str(state)) * 0.55
    sim.close()


def test_seeded_ecology_smoke_produces_affordance_action_differences() -> None:
    sim = AquagenesysSimulation(
        SimulationConfig(seed=742, width=34, height=22, initial_population=12, deliberation_enabled=False, archive_every_ticks=0)
    )
    sim.run(12)
    state = sim.state()
    actions = [row["action"] for row in state["telemetry"]["agent_decisions"]]
    behavior = state["behavior"]["summary"]
    assert behavior["top_actions"]
    assert any(action in {"filter_feed", "graze", "scavenge", "anchor_feed", "strike", "hunt", "forage"} for action in actions)
    assert any(row["candidate_summary"] for row in state["behavior"]["organisms"])
    assert state["telemetry"]["decision_sources"].get("affordance", 0) >= 1
    sim.close()
