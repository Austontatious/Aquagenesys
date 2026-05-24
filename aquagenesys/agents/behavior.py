from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random
from typing import Any

from aquagenesys.agents.fish import Action, FishAgent, Perception, clamp


BEHAVIOR_SCHEMA = "aquagenesys.behavior.v1"


def _round(value: float) -> float:
    return round(float(value), 3)


def _skill_name(skill: Any) -> str:
    skill_type = str(getattr(skill, "skill_type", "skill") or "skill")
    action_bias = str(getattr(skill, "action_bias", "") or "")
    return f"{skill_type}:{action_bias}" if action_bias else skill_type


@dataclass(frozen=True)
class ActionCandidate:
    action: str
    dx: float
    dy: float
    intensity: float
    reason: str
    context_tags: tuple[str, ...]
    affordance_tags: tuple[str, ...]
    expected_cost: float
    expected_risk: float
    expected_upside: float
    confidence: float
    score: float
    policy_influence: tuple[str, ...] = ()
    skill_influence: tuple[str, ...] = ()
    mismatch_warnings: tuple[str, ...] = ()

    def to_action(self) -> Action:
        return Action(
            self.action,
            self.dx,
            self.dy,
            self.intensity,
            "affordance",
            self.reason,
            self.confidence,
        ).normalized()

    def payload(self, *, compact: bool = False) -> dict[str, Any]:
        payload = {
            "action": self.action,
            "score": _round(self.score),
            "cost": _round(self.expected_cost),
            "risk": _round(self.expected_risk),
            "upside": _round(self.expected_upside),
            "confidence": _round(self.confidence),
            "context_tags": list(self.context_tags[:8]),
            "affordance_tags": list(self.affordance_tags[:8]),
            "policy_influence": list(self.policy_influence[:5]),
            "skill_influence": list(self.skill_influence[:5]),
            "mismatch_warnings": list(self.mismatch_warnings[:4]),
            "reason": self.reason,
        }
        if not compact:
            payload.update({"dx": _round(self.dx), "dy": _round(self.dy), "intensity": _round(self.intensity)})
        return payload


@dataclass(frozen=True)
class BehaviorDecision:
    schema: str
    current_action: str
    action_reason: str
    candidates: tuple[ActionCandidate, ...]
    context_tags: tuple[str, ...]
    affordance_tags: tuple[str, ...]
    policy_influence: tuple[str, ...]
    skill_influence: tuple[str, ...]
    mismatch_warnings: tuple[str, ...]

    @property
    def selected(self) -> ActionCandidate:
        return self.candidates[0]

    def to_action(self) -> Action:
        return self.selected.to_action()

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "current_action": self.current_action,
            "action_reason": self.action_reason,
            "candidate_summary": [candidate.payload(compact=True) for candidate in self.candidates[:5]],
            "context_tags": list(self.context_tags[:10]),
            "affordance_tags": list(self.affordance_tags[:10]),
            "policy_influence": list(self.policy_influence[:8]),
            "skill_influence": list(self.skill_influence[:8]),
            "mismatch_warnings": list(self.mismatch_warnings[:6]),
        }


def derive_context_tags(fish: FishAgent, perception: Perception, *, biosphere_state: str = "active", population: int | None = None) -> tuple[str, ...]:
    sample = perception.sample
    tags: list[str] = []
    if perception.resource_score < 0.28:
        tags.append("scarcity")
    if sample.get("plankton", 0.0) >= 0.58 or (sample.get("nutrients", 0.0) >= 0.62 and sample.get("plankton", 0.0) >= 0.42):
        tags.append("bloom")
    if perception.crowding >= 0.30 or perception.neighbor_count >= 8:
        tags.append("crowded")
    if sample.get("oxygen", 0.0) < min(0.42, fish.effective_oxygen_need):
        tags.append("low_oxygen")
    if sample.get("toxins", 0.0) > max(0.34, fish.effective_toxin_tolerance * 0.72):
        tags.append("high_toxin")
    if perception.nearest_threat[2] < fish.effective_sensory_range:
        tags.append("predator_near")
    if perception.nearest_prey[2] < fish.effective_sensory_range:
        tags.append("prey_near")
    if perception.nearest_mate[2] < fish.effective_sensory_range * 1.2:
        tags.append("mate_near")
    if fish.energy < 42.0 or fish.hunger > 0.64:
        tags.append("low_energy")
    if fish.stress > 0.44 or perception.stress > 0.50:
        tags.append("high_stress")
    if biosphere_state == "dormant" or (population is not None and population <= 4):
        tags.append("bottleneck")
    if biosphere_state == "recovering":
        tags.append("recovery")
    if sample.get("decomposition", 0.0) >= 0.34:
        tags.append("near_detritus")
    if sample.get("shelter", 0.0) >= 0.38 or perception.nearest_shelter[2] < fish.effective_sensory_range * 0.55:
        tags.append("near_shelter")
    if perception.resource_score >= 0.46 or max(sample.get("food", 0.0), sample.get("plankton", 0.0), sample.get("decomposition", 0.0)) >= 0.44:
        tags.append("local_resource_patch")
    if sample.get("shelter", 0.0) < 0.18 and perception.crowding < 0.16:
        tags.append("open_water")
    return tuple(dict.fromkeys(tags))


def derive_affordance_tags(fish: FishAgent) -> tuple[str, ...]:
    affordances = fish.morphology_affordances
    body = fish.genome.morphology.body
    tags: list[str] = []
    if affordances.filter_rate >= 0.58:
        tags.append("high_filter")
    if affordances.suction_force >= 0.58:
        tags.append("high_suction")
    if affordances.bite_force >= 0.58:
        tags.append("high_bite")
    if affordances.reach >= 0.58:
        tags.append("high_reach")
    if affordances.armor_protection >= 0.50:
        tags.append("high_armor")
    if affordances.toxin_payload >= 0.30 and affordances.toxin_delivery >= 0.18:
        tags.append("high_toxin")
    if affordances.sensory_range >= 0.58:
        tags.append("high_sensory")
    if affordances.drag >= 0.46:
        tags.append("high_drag")
    if affordances.oxygen_cost >= 0.46 or affordances.metabolic_burden >= 0.48:
        tags.append("high_oxygen_cost")
    if affordances.tissue_vulnerability >= 0.58 and affordances.armor_protection < 0.34:
        tags.append("soft_body")
    if body.body_mass >= 0.78:
        tags.append("bulk_body")
    if body.body_mass <= 0.36:
        tags.append("small_body")
    return tuple(dict.fromkeys(tags))


def build_behavior_decision(
    fish: FishAgent,
    perception: Perception,
    rng: Random,
    *,
    biosphere_state: str = "active",
    population: int | None = None,
) -> BehaviorDecision:
    affordances = fish.morphology_affordances
    context = derive_context_tags(fish, perception, biosphere_state=biosphere_state, population=population)
    aff_tags = derive_affordance_tags(fish)
    sample = perception.sample
    threat_pressure = _proximity_pressure(perception.nearest_threat[2], fish.effective_sensory_range)
    prey_pressure = _proximity_pressure(perception.nearest_prey[2], fish.effective_sensory_range)
    mate_pressure = _proximity_pressure(perception.nearest_mate[2], fish.effective_sensory_range * 1.2)
    resource_pressure = clamp(fish.hunger * 0.48 + perception.resource_score * 0.36 + max(sample.get("food", 0.0), sample.get("plankton", 0.0)) * 0.16)
    movement_burden = clamp(affordances.drag * 0.34 + affordances.oxygen_cost * 0.30 + affordances.metabolic_burden * 0.24)
    candidates: list[ActionCandidate] = []

    def add(action: str, dx: float, dy: float, intensity: float, reason: str, upside: float, cost: float, risk: float) -> None:
        policy_score, policy_tags = _policy_adjustment(fish, action, context, aff_tags)
        skill_score, skill_tags = _skill_adjustment(fish, action)
        warnings = _mismatch_warnings(fish, action, context, aff_tags)
        score = clamp(upside + policy_score + skill_score - cost * 0.78 - risk * 0.86, -0.45, 1.45)
        confidence = clamp(0.34 + score * 0.36 + len(policy_tags) * 0.018 + len(skill_tags) * 0.018, 0.18, 0.92)
        candidates.append(
            ActionCandidate(
                action=action,
                dx=dx,
                dy=dy,
                intensity=clamp(intensity),
                reason=reason,
                context_tags=context,
                affordance_tags=aff_tags,
                expected_cost=clamp(cost),
                expected_risk=clamp(risk),
                expected_upside=clamp(upside),
                confidence=confidence,
                score=score,
                policy_influence=policy_tags,
                skill_influence=skill_tags,
                mismatch_warnings=warnings,
            )
        )

    food_dx, food_dy = perception.vector_for("food")
    prey_dx, prey_dy = perception.vector_for("prey")
    shelter_dx, shelter_dy = perception.vector_for("shelter")
    threat_dx, threat_dy = perception.vector_for("threat")
    mate_dx, mate_dy = perception.vector_for("mate")

    add(
        "filter_feed",
        food_dx,
        food_dy,
        0.32 + fish.hunger * 0.24,
        _reason("filter feed", ("high_filter" in aff_tags or "bloom" in context), "filter/suction body and plankton opportunity"),
        resource_pressure * 0.42 + affordances.filter_rate * 0.36 + affordances.suction_force * 0.12 + sample.get("plankton", 0.0) * 0.16,
        movement_burden * 0.34 + affordances.oxygen_cost * 0.16,
        threat_pressure * max(0.18, affordances.predation_risk_modifier - 0.55),
    )
    add(
        "graze",
        food_dx,
        food_dy,
        0.38 + fish.hunger * 0.22,
        "scrape/gut affordance fits local food",
        resource_pressure * 0.36 + affordances.scrape_rate * 0.30 + sample.get("food", 0.0) * 0.18 + sample.get("nutrients", 0.0) * 0.08,
        movement_burden * 0.42 + affordances.drag * 0.08,
        threat_pressure * max(0.20, affordances.predation_risk_modifier - 0.62),
    )
    add(
        "scavenge",
        food_dx,
        food_dy,
        0.30 + fish.hunger * 0.18,
        "reach/grip body can exploit nearby detritus",
        fish.hunger * 0.28 + affordances.reach * 0.22 + affordances.grip * 0.20 + sample.get("decomposition", 0.0) * 0.28,
        movement_burden * 0.30 + affordances.tissue_vulnerability * 0.08,
        threat_pressure * max(0.22, affordances.predation_risk_modifier - 0.58),
    )
    add(
        "anchor_feed",
        food_dx * 0.24,
        food_dy * 0.24,
        0.18 + fish.hunger * 0.12,
        "low-movement feeding fits reach or drag burden",
        fish.hunger * 0.24 + perception.resource_score * 0.22 + affordances.reach * 0.16 + max(affordances.filter_rate, affordances.scrape_rate) * 0.18,
        movement_burden * 0.16 + affordances.oxygen_cost * 0.10,
        threat_pressure * max(0.16, affordances.predation_risk_modifier - 0.70),
    )
    add(
        "forage",
        food_dx,
        food_dy,
        0.46 + fish.hunger * 0.24,
        "general foraging from physiology and resource gradient",
        resource_pressure * 0.48 + affordances.feeding_throughput * 0.22,
        movement_burden * 0.50 + affordances.drag * 0.10,
        threat_pressure * max(0.22, affordances.predation_risk_modifier - 0.62),
    )
    add(
        "strike",
        prey_dx,
        prey_dy,
        0.44 + fish.hunger * 0.26,
        "bite/strike affordance makes nearby prey plausible",
        fish.hunger * 0.36 + prey_pressure * 0.30 + affordances.bite_force * 0.30 + affordances.strike_impulse * 0.20,
        movement_burden * 0.54 + max(0.0, perception.nearest_prey[2] / max(1.0, fish.effective_sensory_range) - 0.35) * 0.18,
        affordances.tissue_vulnerability * 0.20 + threat_pressure * 0.14 + max(0.0, 0.50 - affordances.armor_protection) * 0.08,
    )
    add(
        "hunt",
        prey_dx,
        prey_dy,
        0.52 + fish.hunger * 0.30,
        "chase is considered when prey and bite affordances align",
        fish.hunger * 0.34 + prey_pressure * 0.24 + affordances.bite_force * 0.22 + fish.genome.max_speed * 0.10,
        movement_burden * 0.78 + affordances.drag * 0.16,
        affordances.tissue_vulnerability * 0.22 + max(0.0, 0.44 - affordances.armor_protection) * 0.12,
    )
    add(
        "chemical_defense",
        threat_dx * 0.18,
        threat_dy * 0.18,
        0.24,
        "chemical payload can deter a nearby threat but has self-cost",
        threat_pressure * 0.34 + affordances.toxin_payload * affordances.toxin_delivery * 0.46,
        affordances.toxin_self_cost * 0.42 + affordances.metabolic_burden * 0.18,
        max(0.0, threat_pressure - affordances.toxin_payload * 0.22),
    )
    flee_urgency = threat_pressure * (1.0 + affordances.tissue_vulnerability * 0.28 - affordances.armor_protection * 0.34)
    add(
        "flee",
        threat_dx,
        threat_dy,
        0.44 + flee_urgency * 0.42,
        "threat avoidance weighted by armor and tissue vulnerability",
        flee_urgency,
        movement_burden * 0.76 + affordances.drag * 0.12,
        max(0.0, threat_pressure - affordances.armor_protection * 0.22),
    )
    add(
        "shelter",
        shelter_dx,
        shelter_dy,
        0.34 + max(fish.stress, fish.fear) * 0.28,
        "shelter reduces stress or threat exposure",
        max(fish.stress, fish.fear, perception.stress) * 0.34 + threat_pressure * 0.18 + sample.get("shelter", 0.0) * 0.12,
        movement_burden * 0.34,
        max(0.02, threat_pressure * 0.30 - sample.get("shelter", 0.0) * 0.08),
    )
    add(
        "rest",
        shelter_dx * 0.14,
        shelter_dy * 0.14,
        0.16,
        "energy conservation favored by cost burden or low energy",
        max(0.0, 58.0 - fish.energy) / 80.0 + movement_burden * 0.22 + fish.stress * 0.12,
        0.06 + affordances.metabolic_burden * 0.12,
        threat_pressure * max(0.20, affordances.predation_risk_modifier - 0.58),
    )
    add(
        "court",
        mate_dx,
        mate_dy,
        0.34 + fish.reproductive_drive * 0.18,
        "reproductive drive and nearby mate make courtship plausible",
        fish.reproductive_drive * 0.44 + perception.reproduction_score * 0.18 + mate_pressure * 0.22,
        movement_burden * 0.38 + affordances.reproduction_cost * 0.18,
        threat_pressure * 0.16 + perception.crowding * 0.10,
    )
    add(
        "school",
        mate_dx,
        mate_dy,
        0.24 + fish.genome.sociality * 0.12,
        "social proximity can reduce local risk",
        fish.genome.sociality * 0.20 + perception.neighbor_count * 0.012 + threat_pressure * 0.12,
        movement_burden * 0.24,
        max(0.0, perception.crowding - 0.32) * 0.18,
    )
    explore_dx = perception.gradients["current"][0] * 0.55 + rng.uniform(-0.45, 0.45)
    explore_dy = perception.gradients["current"][1] * 0.55 + rng.uniform(-0.45, 0.45)
    add(
        "explore",
        explore_dx,
        explore_dy,
        0.22 + fish.genome.curiosity * 0.18 + affordances.sensory_range * 0.08,
        "low-pressure exploration uses sensory range and curiosity",
        fish.genome.curiosity * 0.22 + affordances.sensory_range * 0.16 + (0.12 if "open_water" in context else 0.0),
        movement_burden * 0.44 + affordances.oxygen_cost * 0.08,
        threat_pressure * 0.24 + max(0.0, fish.stress - 0.34) * 0.12,
    )

    candidates.sort(key=lambda candidate: (candidate.score, candidate.expected_upside, -candidate.expected_cost), reverse=True)
    selected = candidates[0]
    policy = tuple(dict.fromkeys(tag for candidate in candidates[:3] for tag in candidate.policy_influence))
    skills = tuple(dict.fromkeys(tag for candidate in candidates[:3] for tag in candidate.skill_influence))
    warnings = tuple(dict.fromkeys(tag for candidate in candidates[:3] for tag in candidate.mismatch_warnings))
    return BehaviorDecision(
        schema=BEHAVIOR_SCHEMA,
        current_action=selected.action,
        action_reason=selected.reason,
        candidates=tuple(candidates),
        context_tags=context,
        affordance_tags=aff_tags,
        policy_influence=policy,
        skill_influence=skills,
        mismatch_warnings=warnings,
    )


def behavior_state_payload(*, organism_id: int, lineage_id: int, rationale: dict[str, Any] | None) -> dict[str, Any]:
    data = rationale or {}
    return {
        "id": f"fish-{organism_id}",
        "lineage_id": f"L{lineage_id}",
        "schema": BEHAVIOR_SCHEMA,
        "current_action": data.get("current_action", "drift"),
        "action_reason": data.get("action_reason", "no behavior decision recorded yet"),
        "candidate_summary": list(data.get("candidate_summary", []))[:5],
        "policy_influence": list(data.get("policy_influence", []))[:6],
        "skill_influence": list(data.get("skill_influence", []))[:6],
        "context_tags": list(data.get("context_tags", []))[:10],
        "affordance_tags": list(data.get("affordance_tags", []))[:10],
        "mismatch_warnings": list(data.get("mismatch_warnings", []))[:6],
    }


def summarize_behavior_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = Counter(str(row.get("current_action", "unknown")) for row in rows)
    contexts = Counter(tag for row in rows for tag in row.get("context_tags", []))
    affordances = Counter(tag for row in rows for tag in row.get("affordance_tags", []))
    warnings = Counter(warning for row in rows for warning in row.get("mismatch_warnings", []))
    return {
        "organisms": len(rows),
        "top_actions": [{"action": action, "count": count} for action, count in actions.most_common(8)],
        "top_context_tags": [{"tag": tag, "count": count} for tag, count in contexts.most_common(8)],
        "top_affordance_tags": [{"tag": tag, "count": count} for tag, count in affordances.most_common(8)],
        "mismatch_warning_count": sum(warnings.values()),
        "top_mismatch_warnings": [{"warning": warning, "count": count} for warning, count in warnings.most_common(6)],
    }


def _proximity_pressure(distance: float, radius: float) -> float:
    if distance >= 998.0:
        return 0.0
    return clamp(1.0 - distance / max(1.0, radius))


def _reason(label: str, condition: bool, detail: str) -> str:
    return detail if condition else f"{label} remains possible but not dominant"


def _policy_adjustment(fish: FishAgent, action: str, context: tuple[str, ...], aff_tags: tuple[str, ...]) -> tuple[float, tuple[str, ...]]:
    instruction = fish.instruction_genome
    score = 0.0
    labels: list[str] = []
    if instruction.risk_posture == "cautious":
        if action in {"shelter", "flee", "chemical_defense"}:
            score += 0.07
            labels.append("cautious risk posture")
        if action in {"hunt", "strike", "explore"}:
            score -= 0.08
            labels.append("cautious posture penalizes risky motion")
    elif instruction.risk_posture == "bold":
        if action in {"hunt", "strike", "explore"}:
            score += 0.08
            labels.append("bold risk posture")
        if action in {"shelter", "flee"} and "high_armor" in aff_tags:
            score -= 0.04
            labels.append("armor makes bold posture less evasive")
    if instruction.forage_strategy == "safe_food" and action in {"filter_feed", "graze", "forage", "anchor_feed"}:
        score += 0.05 if "near_shelter" in context else 0.02
        labels.append("safe food prior")
    elif instruction.forage_strategy == "high_yield_patch" and action in {"forage", "hunt", "strike", "explore"}:
        score += 0.07
        labels.append("high-yield patch prior")
    elif instruction.forage_strategy == "opportunistic_scavenge" and action in {"scavenge", "anchor_feed", "graze"}:
        score += 0.08
        labels.append("opportunistic scavenge prior")
    elif instruction.forage_strategy == "follow_success_memory" and action in {"filter_feed", "graze", "scavenge", "forage"} and "fed" in fish.recent_outcomes[-4:]:
        score += 0.07
        labels.append("recent success prior")
    if instruction.energy_strategy == "conserve":
        if action in {"rest", "shelter", "anchor_feed", "filter_feed"}:
            score += 0.07
            labels.append("energy saver prior")
        if action in {"hunt", "strike", "flee", "explore"} and ("high_drag" in aff_tags or "high_oxygen_cost" in aff_tags):
            score -= 0.10
            labels.append("energy saver penalizes high-cost movement")
    elif instruction.energy_strategy == "burst_then_recover":
        if action in {"hunt", "strike", "flee"}:
            score += 0.06
            labels.append("burst movement prior")
        if action == "rest" and fish.energy < 44.0:
            score += 0.04
            labels.append("burst recovery prior")
    if instruction.exploration_strategy == "novelty_seek" and action == "explore" and "high_oxygen_cost" not in aff_tags:
        score += 0.06
        labels.append("novelty-seeking prior")
    if instruction.threat_strategy in {"hide", "freeze"} and action == "shelter":
        score += 0.06
        labels.append("hide/freeze threat prior")
    elif instruction.threat_strategy == "flee_fast" and action == "flee":
        score += 0.06
        labels.append("fast-flee threat prior")
    return score, tuple(dict.fromkeys(labels))


def _skill_adjustment(fish: FishAgent, action: str) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    labels: list[str] = []
    for skill in fish.taught_skills[:4]:
        skill_type = str(getattr(skill, "skill_type", "") or "")
        action_bias = str(getattr(skill, "action_bias", "") or "")
        confidence = clamp(float(getattr(skill, "confidence", 0.35) or 0.35))
        matches = False
        if skill_type == "forage":
            matches = action in {"forage", "filter_feed", "graze", "scavenge", "anchor_feed"} and action_bias in {
                "nearest_food",
                "safe_food",
                "high_yield_patch",
                "opportunistic_scavenge",
                "follow_success_memory",
            }
        elif skill_type == "threat":
            matches = action in {"flee", "shelter", "chemical_defense"}
        elif skill_type == "energy":
            matches = action in {"rest", "anchor_feed", "filter_feed", "shelter"}
        elif skill_type == "social":
            matches = action in {"school", "court"}
        elif skill_type == "explore":
            matches = action == "explore"
        elif skill_type == "reproduce":
            matches = action == "court"
        if matches:
            score += 0.035 + confidence * 0.045
            labels.append(_skill_name(skill))
    return score, tuple(dict.fromkeys(labels))


def _mismatch_warnings(fish: FishAgent, action: str, context: tuple[str, ...], aff_tags: tuple[str, ...]) -> tuple[str, ...]:
    affordances = fish.morphology_affordances
    instruction = fish.instruction_genome
    warnings: list[str] = []
    if action in {"hunt", "strike", "flee", "explore"} and ("high_drag" in aff_tags or "high_oxygen_cost" in aff_tags):
        warnings.append("high movement policy conflicts with drag or oxygen cost")
    if action in {"hunt", "strike"} and affordances.bite_force < 0.42:
        warnings.append("low bite force makes strike behavior costly")
    if action == "chemical_defense" and affordances.toxin_self_cost >= 0.30:
        warnings.append("self-toxicity limits chemical defense")
    if instruction.forage_strategy == "high_yield_patch" and ("high_drag" in aff_tags or "high_oxygen_cost" in aff_tags):
        warnings.append("high-yield prior conflicts with costly body plan")
    if instruction.risk_posture == "bold" and "soft_body" in aff_tags and "predator_near" in context:
        warnings.append("bold posture conflicts with soft vulnerable body")
    if action == "filter_feed" and affordances.filter_rate < 0.34:
        warnings.append("low filter affordance weakens filter-feeding attempt")
    return tuple(dict.fromkeys(warnings))
