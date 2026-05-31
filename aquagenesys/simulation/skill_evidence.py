from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


SCHEMA = "aquagenesys.skill_evidence.v2"
GOVERNANCE_SCHEMA = "aquagenesys.skill_inheritance_governance.v1"
EFFECT_LABELS = {"helped_possible", "harmed_possible", "unclear", "insufficient_evidence"}
STRENGTHS = ("insufficient_evidence", "weak", "moderate", "strong")
GOVERNANCE_STATUSES = {
    "eligible",
    "inherited",
    "suppressed_insufficient_evidence",
    "suppressed_stale_evidence",
    "suppressed_negative_outcome",
    "suppressed_slot_limit",
    "observed_only",
}
MAX_AGGREGATES = 12
MAX_RECENT_EVENTS = 24
MIN_GOVERNING_EVIDENCE = 2
MAX_GOVERNING_EVIDENCE_AGE = 720
MIN_GOVERNING_CONFIDENCE = 0.56


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


@dataclass(frozen=True)
class SkillInheritanceDecision:
    skill: Any
    status: str
    confidence: float
    evidence_count: int
    positive_evidence_count: int
    negative_evidence_count: int
    unclear_evidence_count: int
    reproduction_after_use_count: int
    last_seen_tick: int
    stale: bool
    reason_code: str
    reason: str
    source_parent_id: int | None
    source_lineage_id: int
    evidence_scope: str = "lineage_local"
    evidence_mode: str = "inheritance_governing"
    basis: tuple[dict[str, Any], ...] = ()

    @property
    def inherited(self) -> bool:
        return self.status == "inherited"

    @property
    def eligible(self) -> bool:
        return self.status in {"eligible", "inherited"}

    def with_status(self, status: str, *, reason_code: str, reason: str) -> "SkillInheritanceDecision":
        return SkillInheritanceDecision(
            skill=self.skill,
            status=status if status in GOVERNANCE_STATUSES else "suppressed_insufficient_evidence",
            confidence=self.confidence,
            evidence_count=self.evidence_count,
            positive_evidence_count=self.positive_evidence_count,
            negative_evidence_count=self.negative_evidence_count,
            unclear_evidence_count=self.unclear_evidence_count,
            reproduction_after_use_count=self.reproduction_after_use_count,
            last_seen_tick=self.last_seen_tick,
            stale=self.stale,
            reason_code=reason_code,
            reason=reason,
            source_parent_id=self.source_parent_id,
            source_lineage_id=self.source_lineage_id,
            evidence_scope=self.evidence_scope,
            evidence_mode=self.evidence_mode,
            basis=self.basis,
        )

    def payload(self, *, compact: bool = False) -> dict[str, Any]:
        identity = skill_identity(self.skill)
        payload: dict[str, Any] = {
            "schema": GOVERNANCE_SCHEMA,
            "skill_id": identity["skill_id"],
            "skill_hash": identity["skill_hash"],
            "skill_name": identity["skill_name"],
            "skill_type": identity["skill_type"],
            "status": self.status,
            "inherited": self.inherited,
            "eligible": self.eligible,
            "confidence": round(self.confidence, 3),
            "evidence_count": self.evidence_count,
            "positive_evidence_count": self.positive_evidence_count,
            "negative_evidence_count": self.negative_evidence_count,
            "unclear_evidence_count": self.unclear_evidence_count,
            "reproduction_after_use_count": self.reproduction_after_use_count,
            "last_seen_tick": self.last_seen_tick,
            "stale": self.stale,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "source_parent_id": self.source_parent_id,
            "source_lineage_id": self.source_lineage_id,
            "evidence_scope": self.evidence_scope,
            "evidence_mode": self.evidence_mode,
            "claim_boundary": "Evidence governs inheritance eligibility; it is still observational and not causal proof.",
        }
        if not compact:
            payload["skill"] = self.skill.payload(compact=True) if hasattr(self.skill, "payload") else identity
            payload["evidence_basis"] = list(self.basis[:4])
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


def evaluate_skill_inheritance(
    skill: Any,
    *,
    events: Iterable[dict[str, Any]],
    current_tick: int,
    current_generation: int,
    parent_id: int | None,
    lineage_id: int,
    source: str = "parent",
) -> SkillInheritanceDecision:
    identity = skill_identity(skill)
    skill_hash = identity["skill_hash"]
    source_parent_id = int(getattr(skill, "source_parent_id", 0) or 0) or parent_id
    source_lineage_id = int(getattr(skill, "source_lineage_id", 0) or 0) or lineage_id
    expired = bool(getattr(skill, "expired_for_generation", lambda _generation: False)(current_generation))
    relevant = [
        row
        for row in events
        if _governing_event_matches(
            row,
            skill_hash=skill_hash,
            lineage_id=lineage_id,
            source_lineage_id=source_lineage_id,
            parent_id=parent_id,
        )
    ]
    positive = sum(1 for row in relevant if row.get("effect_label") == "helped_possible")
    negative = sum(1 for row in relevant if row.get("effect_label") == "harmed_possible")
    unclear = sum(1 for row in relevant if row.get("effect_label") == "unclear")
    reproduction_after_use = sum(1 for row in relevant if row.get("reproduction_after_use"))
    evidence_count = positive + negative + unclear
    last_seen = max((int(row.get("tick", 0) or 0) for row in relevant), default=0)
    stale = bool(relevant and current_tick - last_seen > MAX_GOVERNING_EVIDENCE_AGE)
    confidence = _governance_confidence(
        evidence_count=evidence_count,
        positive=positive,
        negative=negative,
        unclear=unclear,
        reproduction_after_use=reproduction_after_use,
        last_seen_tick=last_seen,
        current_tick=current_tick,
    )
    basis = tuple(_governance_basis(row) for row in sorted(relevant, key=lambda item: int(item.get("tick", 0) or 0), reverse=True)[:4])

    if expired or stale:
        return SkillInheritanceDecision(
            skill=skill,
            status="suppressed_stale_evidence",
            confidence=confidence,
            evidence_count=evidence_count,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            unclear_evidence_count=unclear,
            reproduction_after_use_count=reproduction_after_use,
            last_seen_tick=last_seen,
            stale=True,
            reason_code="stale_or_expired",
            reason="The skill hint is outside its generation TTL or its supporting observations are stale.",
            source_parent_id=source_parent_id,
            source_lineage_id=source_lineage_id,
            basis=basis,
        )
    if negative > 0 and negative >= positive:
        return SkillInheritanceDecision(
            skill=skill,
            status="suppressed_negative_outcome",
            confidence=confidence,
            evidence_count=evidence_count,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            unclear_evidence_count=unclear,
            reproduction_after_use_count=reproduction_after_use,
            last_seen_tick=last_seen,
            stale=False,
            reason_code="negative_outcome_pressure",
            reason="Observed harmed-possible outcomes meet or exceed positive support.",
            source_parent_id=source_parent_id,
            source_lineage_id=source_lineage_id,
            basis=basis,
        )
    if evidence_count < MIN_GOVERNING_EVIDENCE or positive < MIN_GOVERNING_EVIDENCE:
        status = "observed_only" if source == "new_patch" and evidence_count <= 0 else "suppressed_insufficient_evidence"
        return SkillInheritanceDecision(
            skill=skill,
            status=status,
            confidence=confidence,
            evidence_count=evidence_count,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            unclear_evidence_count=unclear,
            reproduction_after_use_count=reproduction_after_use,
            last_seen_tick=last_seen,
            stale=False,
            reason_code="insufficient_positive_evidence",
            reason="At least two recent positive lineage-local observations are required before inheritance.",
            source_parent_id=source_parent_id,
            source_lineage_id=source_lineage_id,
            basis=basis,
        )
    if confidence < MIN_GOVERNING_CONFIDENCE:
        return SkillInheritanceDecision(
            skill=skill,
            status="suppressed_insufficient_evidence",
            confidence=confidence,
            evidence_count=evidence_count,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            unclear_evidence_count=unclear,
            reproduction_after_use_count=reproduction_after_use,
            last_seen_tick=last_seen,
            stale=False,
            reason_code="confidence_below_threshold",
            reason="Evidence exists, but confidence is below the deterministic inheritance threshold.",
            source_parent_id=source_parent_id,
            source_lineage_id=source_lineage_id,
            basis=basis,
        )
    return SkillInheritanceDecision(
        skill=skill,
        status="eligible",
        confidence=confidence,
        evidence_count=evidence_count,
        positive_evidence_count=positive,
        negative_evidence_count=negative,
        unclear_evidence_count=unclear,
        reproduction_after_use_count=reproduction_after_use,
        last_seen_tick=last_seen,
        stale=False,
        reason_code="evidence_threshold_met",
        reason="Recent lineage-local evidence meets the inheritance gate.",
        source_parent_id=source_parent_id,
        source_lineage_id=source_lineage_id,
        basis=basis,
    )


def govern_taught_skill_inheritance(
    parent_skills: Sequence[Any],
    *,
    events: Iterable[dict[str, Any]],
    current_tick: int,
    current_generation: int,
    allowed_slots: int,
    parent_id: int | None,
    lineage_id: int,
) -> tuple[list[Any], list[SkillInheritanceDecision]]:
    event_rows = list(events)
    evaluated = [
        evaluate_skill_inheritance(
            skill,
            events=event_rows,
            current_tick=current_tick,
            current_generation=current_generation,
            parent_id=parent_id,
            lineage_id=lineage_id,
        )
        for skill in parent_skills
    ]
    eligible = [decision for decision in evaluated if decision.status == "eligible"]
    eligible.sort(
        key=lambda decision: (
            decision.confidence,
            decision.positive_evidence_count,
            decision.reproduction_after_use_count,
            decision.last_seen_tick,
        ),
        reverse=True,
    )
    selected = {decision.skill.skill_hash for decision in eligible[: max(0, allowed_slots)]}
    inherited: list[Any] = []
    decisions: list[SkillInheritanceDecision] = []
    for decision in evaluated:
        if decision.skill.skill_hash in selected:
            inherited.append(decision.skill)
            decisions.append(
                decision.with_status(
                    "inherited",
                    reason_code="evidence_threshold_met",
                    reason="Inherited because recent lineage-local evidence meets the deterministic gate.",
                )
            )
        elif decision.status == "eligible":
            decisions.append(
                decision.with_status(
                    "suppressed_slot_limit",
                    reason_code="skill_slot_limit",
                    reason="Evidence was sufficient, but offspring skill slots were already filled by stronger hints.",
                )
            )
        else:
            decisions.append(decision)
    decisions.sort(
        key=lambda decision: (
            1 if decision.status == "inherited" else 0,
            decision.confidence,
            decision.positive_evidence_count,
            decision.last_seen_tick,
        ),
        reverse=True,
    )
    inherited.sort(key=lambda skill: getattr(skill, "confidence", 0.0), reverse=True)
    return inherited[: max(0, allowed_slots)], decisions


def _governing_event_matches(
    event: dict[str, Any],
    *,
    skill_hash: str,
    lineage_id: int,
    source_lineage_id: int,
    parent_id: int | None,
) -> bool:
    if event.get("event_type") not in {"skill_outcome_observed", "skill_descendant_outcome"}:
        return False
    if str(event.get("skill_hash", "")) != skill_hash:
        return False
    event_lineage = int(event.get("lineage_id", 0) or 0)
    if event_lineage in {lineage_id, source_lineage_id}:
        return True
    if parent_id is not None and int(event.get("fish_id", 0) or 0) == int(parent_id):
        return True
    return False


def _governance_confidence(
    *,
    evidence_count: int,
    positive: int,
    negative: int,
    unclear: int,
    reproduction_after_use: int,
    last_seen_tick: int,
    current_tick: int,
) -> float:
    if evidence_count <= 0:
        return 0.0
    age = max(0, current_tick - last_seen_tick)
    age_penalty = min(0.22, age / max(1, MAX_GOVERNING_EVIDENCE_AGE) * 0.22)
    confidence = (
        0.28
        + min(positive, 5) * 0.15
        + min(reproduction_after_use, 2) * 0.12
        - min(negative, 4) * 0.22
        - min(unclear, 4) * 0.025
        - age_penalty
    )
    if evidence_count < MIN_GOVERNING_EVIDENCE or positive < MIN_GOVERNING_EVIDENCE:
        confidence = min(confidence, MIN_GOVERNING_CONFIDENCE - 0.05)
    if negative:
        confidence = min(confidence, 0.64 - negative * 0.10)
    return round(max(0.0, min(0.86, confidence)), 3)


def _governance_basis(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": int(event.get("tick", 0) or 0),
        "event_type": str(event.get("event_type", "")),
        "effect_label": str(event.get("effect_label", "insufficient_evidence")),
        "context": str(event.get("context", "")),
        "action": str(event.get("action", "")),
        "immediate_outcome": str(event.get("immediate_outcome", "")),
        "reproduction_after_use": bool(event.get("reproduction_after_use", False)),
    }


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
                "inheritance_governance_count": 0,
                "inherited_hint_count": 0,
                "suppressed_hint_count": 0,
                "governance_status_counts": {},
                "latest_governance_status": "",
                "governance_confidence": 0.0,
                "suppression_reason": "",
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
        elif event_type == "skill_inheritance_governance":
            status = str(event.get("status", event.get("inheritance_status", "")) or "")
            if status not in GOVERNANCE_STATUSES:
                status = "suppressed_insufficient_evidence"
            row["inheritance_governance_count"] += 1
            row["latest_governance_status"] = status
            row["governance_confidence"] = round(float(event.get("confidence", 0.0) or 0.0), 3)
            row["suppression_reason"] = str(event.get("reason", "") or "")
            status_counts = row["governance_status_counts"]
            status_counts[status] = int(status_counts.get(status, 0) or 0) + 1
            if status == "inherited":
                row["inherited_hint_count"] += 1
            elif status.startswith("suppressed") or status == "observed_only":
                row["suppressed_hint_count"] += 1

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
    governance_counts = Counter(
        str(event.get("status", event.get("inheritance_status", "")) or "")
        for event in event_rows
        if event.get("event_type") == "skill_inheritance_governance"
    )
    suppressed_count = sum(
        count
        for status, count in governance_counts.items()
        if status.startswith("suppressed") or status == "observed_only"
    )
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
            "inheritance_governance_events": sum(governance_counts.values()),
            "eligible_skill_hints": governance_counts.get("eligible", 0) + governance_counts.get("inherited", 0),
            "inherited_skill_hints": governance_counts.get("inherited", 0),
            "suppressed_skill_hints": suppressed_count,
            "observed_only_skill_hints": governance_counts.get("observed_only", 0),
            "governance_status_counts": dict(governance_counts),
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
    governance_status = str(row.get("latest_governance_status", "") or "")
    if governance_status == "inherited":
        return (
            f"{name} passed the inheritance gate with confidence {row.get('governance_confidence', 0.0)}; "
            f"observed evidence shows {helped} helped possible, {harmed} harmed possible, {unclear} unclear."
        )
    if governance_status.startswith("suppressed") or governance_status == "observed_only":
        reason = str(row.get("suppression_reason", "") or "evidence did not meet the inheritance gate")
        return f"{name} was evaluated for inheritance and not preserved: {reason}"
    if uses <= 0:
        return f"{name} is carried by {carriers} visible descendants; no use has been observed yet."
    return (
        f"{name} is carried by {carriers} visible descendants and was observed {uses} times; "
        f"{helped} helped possible, {harmed} harmed possible, {unclear} unclear. This is observational, not causal proof."
    )
