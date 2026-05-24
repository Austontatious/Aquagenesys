from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


SCHEMA = "aquagenesys.skill_evidence.v1"
EFFECT_LABELS = {"helped_possible", "harmed_possible", "unclear", "insufficient_evidence"}
STRENGTHS = ("insufficient_evidence", "weak", "moderate", "strong")
MAX_AGGREGATES = 12
MAX_RECENT_EVENTS = 24


@dataclass(frozen=True)
class SkillUseEvidence:
    event_type: str
    tick: int
    fish_id: int | None
    lineage_id: int
    skill_id: str
    skill_hash: str
    skill_name: str
    skill_type: str
    source: str
    parent_id: int | None = None
    child_id: int | None = None
    egg_id: int | None = None
    generation: int = 0
    context: str = ""
    action: str = ""
    immediate_outcome: str = ""
    outcome_score: float | None = None
    evidence_strength: str = "weak"
    effect_label: str = "insufficient_evidence"
    delivery: str = ""
    detail: str = ""
    survival_ticks_after_use: int = 0
    reproduction_after_use: bool = False
    context_tags: tuple[str, ...] = ()
    affordance_tags: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_type": self.event_type,
            "tick": self.tick,
            "fish_id": self.fish_id,
            "lineage_id": self.lineage_id,
            "skill_id": self.skill_id,
            "skill_hash": self.skill_hash,
            "skill_name": self.skill_name,
            "skill_type": self.skill_type,
            "source": self.source,
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "egg_id": self.egg_id,
            "generation": self.generation,
            "context": self.context,
            "action": self.action,
            "immediate_outcome": self.immediate_outcome,
            "outcome_score": round(self.outcome_score, 4) if self.outcome_score is not None else None,
            "evidence_strength": self.evidence_strength if self.evidence_strength in STRENGTHS else "weak",
            "effect_label": self.effect_label if self.effect_label in EFFECT_LABELS else "insufficient_evidence",
            "delivery": self.delivery,
            "detail": self.detail,
            "survival_ticks_after_use": self.survival_ticks_after_use,
            "reproduction_after_use": self.reproduction_after_use,
            "context_tags": list(self.context_tags[:10]),
            "affordance_tags": list(self.affordance_tags[:10]),
        }
        return payload


def skill_name(skill: Any) -> str:
    skill_type = str(getattr(skill, "skill_type", "unknown") or "unknown")
    action_bias = str(getattr(skill, "action_bias", "unknown") or "unknown")
    return f"{skill_type}:{action_bias}"


def skill_identity(skill: Any) -> dict[str, str]:
    return {
        "skill_id": str(getattr(skill, "skill_id", "") or getattr(skill, "skill_hash", "")),
        "skill_hash": str(getattr(skill, "skill_hash", "")),
        "skill_name": skill_name(skill),
        "skill_type": str(getattr(skill, "skill_type", "unknown") or "unknown"),
    }


def skill_source(skill: Any, fish: Any | None = None, *, taught_now: bool = False) -> str:
    if taught_now:
        return "taught"
    if fish is not None and int(getattr(skill, "source_parent_id", 0) or 0) == int(getattr(fish, "fish_id", -1) or -1):
        return "self"
    if int(getattr(skill, "source_parent_id", 0) or 0) > 0:
        return "inherited"
    return "unknown"


def matched_skills_for_action(fish: Any, perception: Any, action: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for skill in getattr(fish, "taught_skills", []) or []:
        match = _skill_action_context(skill, fish, perception, action)
        if match is not None:
            matches.append({"skill": skill, **match})
    return matches


def classify_skill_outcome(skill: Any, action: Any, outcome: str, deltas: dict[str, float]) -> tuple[str, float, str, str]:
    skill_type = str(getattr(skill, "skill_type", "unknown") or "unknown")
    energy_delta = float(deltas.get("energy", 0.0))
    health_delta = float(deltas.get("health", 0.0))
    hunger_delta = float(deltas.get("hunger", 0.0))
    stress_delta = float(deltas.get("stress", 0.0))
    fear_delta = float(deltas.get("fear", 0.0))
    action_kind = str(getattr(action, "kind", "unknown"))

    if skill_type == "forage":
        score = (-hunger_delta * 2.0) + (energy_delta * 0.08) - (stress_delta * 0.45)
        if outcome in {"fed", "successful_hunt"} or hunger_delta < -0.025 or energy_delta > 0.20:
            return "helped_possible", score, _strength(score, moderate_floor=0.03), "food or energy improved after skill-matched foraging"
        if energy_delta < -0.75 or health_delta < -0.025 or stress_delta > 0.08:
            return "harmed_possible", score, "weak", "skill-matched foraging was followed by cost or stress"
        return "unclear", score, "weak", "foraging prior was expressed, but the immediate result was ambiguous"

    if skill_type == "threat":
        score = (-stress_delta * 1.2) + (-fear_delta * 0.8) + (health_delta * 1.4)
        if outcome == "sheltered" or stress_delta < -0.020 or fear_delta < -0.035:
            return "helped_possible", score, _strength(score, moderate_floor=0.025), "stress or fear improved after skill-matched avoidance"
        if health_delta < -0.025 or stress_delta > 0.050:
            return "harmed_possible", score, "weak", "avoidance prior was followed by worse stress or health"
        return "unclear", score, "weak", "avoidance prior was expressed, but the immediate result was ambiguous"

    if skill_type == "energy":
        score = (energy_delta * 0.08) - stress_delta + (health_delta * 0.8)
        if outcome == "rested" or (energy_delta > -0.12 and stress_delta < 0.0):
            return "helped_possible", score, "weak", "energy prior was followed by rest or lower stress"
        if energy_delta < -0.90 or health_delta < -0.025:
            return "harmed_possible", score, "weak", "energy prior was followed by notable cost"
        return "unclear", score, "weak", "energy prior was expressed, but the immediate result was ambiguous"

    if skill_type == "reproduce":
        score = float(deltas.get("reproductive_drive", 0.0)) + (energy_delta * 0.02)
        if action_kind == "court":
            return "unclear", score, "weak", "reproductive prior was expressed; reproduction outcome is tracked separately"
        return "insufficient_evidence", score, "insufficient_evidence", "reproductive prior was not tied to a visible action"

    score = (energy_delta * 0.04) - (stress_delta * 0.5) + (health_delta * 0.8)
    if energy_delta > 0.25 or stress_delta < -0.030:
        return "helped_possible", score, "weak", "skill-matched behavior was followed by a small immediate improvement"
    if energy_delta < -0.90 or stress_delta > 0.060 or health_delta < -0.025:
        return "harmed_possible", score, "weak", "skill-matched behavior was followed by cost or stress"
    return "unclear", score, "weak", "skill-matched behavior was expressed, but the immediate result was ambiguous"


def aggregate_skill_evidence(
    *,
    events: Iterable[dict[str, Any]],
    fish: Sequence[Any],
    eggs: Sequence[Any],
    tick: int,
) -> dict[str, Any]:
    event_rows = list(events)
    aggregates: dict[tuple[int, str], dict[str, Any]] = {}
    user_sets: dict[tuple[int, str], set[int]] = defaultdict(set)
    offspring_sets: dict[tuple[int, str], set[str]] = defaultdict(set)
    latest_use_by_fish: dict[tuple[int, str], dict[str, Any]] = {}
    live_fish_ids = {int(getattr(item, "fish_id", 0) or 0) for item in fish}

    def row_for(lineage_id: int, skill_hash: str, seed: dict[str, Any]) -> dict[str, Any]:
        key = (lineage_id, skill_hash)
        if key not in aggregates:
            aggregates[key] = {
                "lineage_id": lineage_id,
                "skill_id": seed.get("skill_id", ""),
                "skill_hash": skill_hash,
                "skill_name": seed.get("skill_name", skill_hash[:8]),
                "skill_type": seed.get("skill_type", "unknown"),
                "source": seed.get("source", "unknown"),
                "parent_id": seed.get("parent_id"),
                "carriers_count": 0,
                "live_carriers_count": 0,
                "egg_carriers_count": 0,
                "users_count": 0,
                "uses_count": 0,
                "offspring_carriers_count": 0,
                "survival_ticks_after_use": 0,
                "reproduction_after_use_count": 0,
                "helped_possible_count": 0,
                "harmed_possible_count": 0,
                "unclear_count": 0,
                "insufficient_evidence_count": 0,
                "last_seen_tick": 0,
                "latest_relevant_event": "",
                "latest_context": "",
                "latest_outcome": "",
                "evidence_strength": "insufficient_evidence",
                "interpretation": "No evidence recorded yet.",
            }
        return aggregates[key]

    for item in fish:
        lineage_id = int(getattr(item, "lineage_id", 0) or 0)
        for skill in getattr(item, "taught_skills", []) or []:
            identity = skill_identity(skill)
            row = row_for(lineage_id, identity["skill_hash"], {**identity, "source": skill_source(skill, item), "parent_id": getattr(skill, "source_parent_id", None)})
            row["carriers_count"] += 1
            row["live_carriers_count"] += 1

    for egg in eggs:
        if not getattr(egg, "viable", False):
            continue
        lineage_id = int(getattr(egg, "lineage_id", 0) or 0)
        for skill in getattr(egg, "taught_skills", []) or []:
            identity = skill_identity(skill)
            row = row_for(lineage_id, identity["skill_hash"], {**identity, "source": "inherited", "parent_id": getattr(skill, "source_parent_id", None)})
            row["carriers_count"] += 1
            row["egg_carriers_count"] += 1

    for event in event_rows:
        skill_hash = str(event.get("skill_hash", ""))
        if not skill_hash:
            continue
        lineage_id = int(event.get("lineage_id", 0) or 0)
        row = row_for(lineage_id, skill_hash, event)
        event_tick = int(event.get("tick", 0) or 0)
        if event_tick >= int(row.get("last_seen_tick", 0) or 0):
            row["last_seen_tick"] = event_tick
            row["latest_relevant_event"] = event.get("event_type", "")
            row["latest_context"] = event.get("context", "")
            row["latest_outcome"] = event.get("immediate_outcome", "")
        event_type = str(event.get("event_type", ""))
        if event_type == "skill_inherited":
            target = event.get("child_id") or f"egg:{event.get('egg_id')}"
            offspring_sets[(lineage_id, skill_hash)].add(str(target))
        elif event_type == "skill_outcome_observed":
            row["uses_count"] += 1
            fish_id = event.get("fish_id")
            if fish_id is not None:
                user_sets[(lineage_id, skill_hash)].add(int(fish_id))
                latest_use_by_fish[(int(fish_id), skill_hash)] = event
            label = str(event.get("effect_label", "insufficient_evidence"))
            if label == "helped_possible":
                row["helped_possible_count"] += 1
            elif label == "harmed_possible":
                row["harmed_possible_count"] += 1
            elif label == "unclear":
                row["unclear_count"] += 1
            else:
                row["insufficient_evidence_count"] += 1
        elif event_type == "skill_descendant_outcome":
            if event.get("reproduction_after_use"):
                row["reproduction_after_use_count"] += 1
            label = str(event.get("effect_label", "insufficient_evidence"))
            if label == "helped_possible":
                row["helped_possible_count"] += 1
            elif label == "harmed_possible":
                row["harmed_possible_count"] += 1
            elif label == "unclear":
                row["unclear_count"] += 1
            else:
                row["insufficient_evidence_count"] += 1

    for key, users in user_sets.items():
        aggregates[key]["users_count"] = len(users)
    for key, offspring in offspring_sets.items():
        aggregates[key]["offspring_carriers_count"] = len(offspring)

    for (fish_id, skill_hash), event in latest_use_by_fish.items():
        if fish_id not in live_fish_ids:
            continue
        lineage_id = int(event.get("lineage_id", 0) or 0)
        row = aggregates.get((lineage_id, skill_hash))
        if row is not None:
            row["survival_ticks_after_use"] += max(0, tick - int(event.get("tick", tick) or tick))

    rows = list(aggregates.values())
    for row in rows:
        if row["helped_possible_count"] or row["harmed_possible_count"]:
            row["evidence_strength"] = "moderate" if row["uses_count"] >= 1 else "weak"
        elif row["uses_count"] or row["offspring_carriers_count"]:
            row["evidence_strength"] = "weak"
        row["interpretation"] = _interpretation(row)
    rows.sort(
        key=lambda row: (
            int(row.get("uses_count", 0) or 0),
            int(row.get("carriers_count", 0) or 0),
            int(row.get("offspring_carriers_count", 0) or 0),
            int(row.get("last_seen_tick", 0) or 0),
        ),
        reverse=True,
    )
    label_counts = Counter(str(event.get("effect_label", "insufficient_evidence")) for event in event_rows if event.get("event_type") in {"skill_outcome_observed", "skill_descendant_outcome"})
    return {
        "schema": SCHEMA,
        "events_recorded": len(event_rows),
        "recent_events": list(reversed(event_rows))[:MAX_RECENT_EVENTS],
        "aggregates": rows[:MAX_AGGREGATES],
        "summary": {
            "skills_with_evidence": len(rows),
            "observed_uses": sum(int(row.get("uses_count", 0) or 0) for row in rows),
            "carriers": sum(int(row.get("carriers_count", 0) or 0) for row in rows),
            "offspring_carriers": sum(int(row.get("offspring_carriers_count", 0) or 0) for row in rows),
            "helped_possible": label_counts.get("helped_possible", 0),
            "harmed_possible": label_counts.get("harmed_possible", 0),
            "unclear": label_counts.get("unclear", 0),
            "insufficient_evidence": label_counts.get("insufficient_evidence", 0),
            "claim_boundary": "Skill evidence is observational. It suggests possible effects but does not prove causality.",
        },
    }


def _skill_action_context(skill: Any, fish: Any, perception: Any, action: Any) -> dict[str, Any] | None:
    skill_type = str(getattr(skill, "skill_type", "unknown") or "unknown")
    action_kind = str(getattr(action, "kind", "unknown") or "unknown")
    action_reason = str(getattr(action, "reason", "")).lower()
    action_source = str(getattr(action, "source", "")).lower()
    behavior = getattr(fish, "last_behavior_rationale", {}) or {}
    context_tags = tuple(str(tag) for tag in behavior.get("context_tags", [])[:10])
    affordance_tags = tuple(str(tag) for tag in behavior.get("affordance_tags", [])[:10])
    skill_label = skill_name(skill)
    behavior_expresses_skill = skill_label in set(str(item) for item in behavior.get("skill_influence", []))
    if action_source == "reflex" and "instruction" not in action_reason:
        return None
    if not _policy_expresses_skill(skill, fish) and "instruction" not in action_reason and not behavior_expresses_skill:
        return None

    sensory_range = float(getattr(getattr(fish, "genome", None), "sensory_range", 8.0) or 8.0)
    if skill_type == "forage":
        food_near = float(getattr(perception, "nearest_food", (0.0, 0.0, 999.0))[2]) <= sensory_range * 1.7
        context = bool(getattr(fish, "hunger", 0.0) > 0.42 or getattr(perception, "resource_score", 0.0) > 0.54 or food_near)
        if context and action_kind in {"forage", "eat", "hunt", "strike", "filter_feed", "graze", "scavenge", "anchor_feed"}:
            return {
                "context": "hunger_or_food_opportunity",
                "action_match": "forage_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    elif skill_type == "threat":
        threat_near = float(getattr(perception, "nearest_threat", (0.0, 0.0, 999.0))[2]) <= sensory_range * 1.5
        context = bool(getattr(fish, "fear", 0.0) > 0.34 or getattr(fish, "stress", 0.0) > 0.34 or getattr(perception, "stress", 0.0) > 0.34 or threat_near)
        if context and action_kind in {"shelter", "flee", "escape", "chemical_defense"}:
            return {
                "context": "fear_stress_or_threat",
                "action_match": "avoidance_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    elif skill_type == "social":
        if getattr(perception, "neighbor_count", 0) > 0 and action_kind == "school":
            return {
                "context": "nearby_organisms",
                "action_match": "social_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    elif skill_type == "explore":
        context = bool(getattr(perception, "resource_score", 0.0) < 0.68 and getattr(fish, "stress", 0.0) < 0.58)
        if context and action_kind == "explore":
            return {
                "context": "low_pressure_search",
                "action_match": "exploration_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    elif skill_type == "reproduce":
        context = bool(getattr(fish, "reproductive_drive", 0.0) > 0.50 or getattr(perception, "reproduction_score", 0.0) > 0.50)
        if context and action_kind == "court":
            return {
                "context": "fertile_or_reproductive_water",
                "action_match": "reproduction_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    elif skill_type == "energy":
        context = bool(getattr(fish, "energy", 100.0) < 58.0 or getattr(fish, "stress", 0.0) > 0.28)
        if context and action_kind in {"rest", "shelter", "anchor_feed", "filter_feed"}:
            return {
                "context": "energy_or_stress_management",
                "action_match": "energy_path",
                "context_tags": context_tags,
                "affordance_tags": affordance_tags,
            }
    return None


def _policy_expresses_skill(skill: Any, fish: Any) -> bool:
    instruction = getattr(fish, "instruction_genome", None)
    if instruction is None:
        return False
    skill_type = str(getattr(skill, "skill_type", "unknown") or "unknown")
    action_bias = str(getattr(skill, "action_bias", "") or "")
    field_name = {
        "forage": "forage_strategy",
        "threat": "threat_strategy",
        "social": "social_strategy",
        "explore": "exploration_strategy",
        "reproduce": "reproduction_strategy",
        "energy": "energy_strategy",
    }.get(skill_type)
    return bool(field_name and getattr(instruction, field_name, "") == action_bias)


def _strength(score: float, *, moderate_floor: float) -> str:
    if abs(score) >= moderate_floor:
        return "moderate"
    return "weak"


def _interpretation(row: dict[str, Any]) -> str:
    name = str(row.get("skill_name", "skill"))
    carriers = int(row.get("carriers_count", 0) or 0)
    uses = int(row.get("uses_count", 0) or 0)
    helped = int(row.get("helped_possible_count", 0) or 0)
    harmed = int(row.get("harmed_possible_count", 0) or 0)
    unclear = int(row.get("unclear_count", 0) or 0)
    if uses <= 0:
        return f"{name} is carried by {carriers} visible descendants; no use has been observed yet."
    return (
        f"{name} is carried by {carriers} visible descendants and was observed {uses} times; "
        f"{helped} helped possible, {harmed} harmed possible, {unclear} unclear. This is observational, not causal proof."
    )
