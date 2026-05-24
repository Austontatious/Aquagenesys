from __future__ import annotations

from collections import Counter
from math import hypot
from typing import Any, Iterable, Sequence


def build_observatory_dashboard(
    *,
    tick: int,
    run_id: str,
    telemetry: dict[str, Any],
    fish: Sequence[Any],
    eggs: Sequence[Any],
    events: Iterable[dict[str, Any]],
    reproduction_log: Iterable[dict[str, Any]],
    instruction_log: Iterable[dict[str, Any]],
    decision_log: Iterable[dict[str, Any]],
    dead_agent_summaries: dict[int, dict[str, Any]],
    field_averages: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build a compact, deterministic dashboard for the observatory UI."""

    recent_events = list(events)
    recent_reproduction = list(reproduction_log)
    recent_instruction = list(instruction_log)
    recent_decisions = list(decision_log)
    lineages = _lineage_summary(fish, eggs)
    morphology = _morphology_summary(telemetry, fish)
    policies = _policy_summary(fish)
    teaching = _teaching_summary(telemetry, recent_instruction)
    skill_evidence = _skill_evidence_summary(telemetry)
    diagnostics = _diagnostics_summary(telemetry)
    population = _population_summary(telemetry, recent_events)
    timeline = _timeline(recent_events, recent_reproduction, recent_instruction, recent_decisions)
    recovery = _recovery_summary(
        telemetry=telemetry,
        population=population,
        lineages=lineages,
        policies=policies,
        diagnostics=diagnostics,
        timeline=timeline,
        field_averages=field_averages or {},
    )
    narrator = _narrator(telemetry, population, lineages, morphology, policies, teaching, diagnostics, timeline, recovery)
    return {
        "schema": "aquagenesys.dashboard.v2",
        "tick": tick,
        "run_id": run_id,
        "narrator": narrator,
        "recovery": recovery,
        "population": population,
        "lineages": lineages,
        "morphology": morphology,
        "policies": policies,
        "teaching": teaching,
        "skill_evidence": skill_evidence,
        "events": timeline,
        "diagnostics": diagnostics,
        "focus_hints": _focus_hints(fish, eggs),
        "archive": {
            "dead_agent_summaries": len(dead_agent_summaries),
            "agent_code_snapshots": telemetry.get("instruction", {}).get("agent_code_snapshots", 0),
        },
    }


def _recovery_summary(
    *,
    telemetry: dict[str, Any],
    population: dict[str, Any],
    lineages: dict[str, Any],
    policies: dict[str, Any],
    diagnostics: dict[str, Any],
    timeline: list[dict[str, Any]],
    field_averages: dict[str, float],
) -> dict[str, Any]:
    adults = population["adults"]
    viable = population["viable_eggs"]
    dormant = population["dormant_eggs"]
    recent_births = population["recent_births"]
    recent_deaths = population["recent_deaths"]
    state = population["biosphere_state"]
    resource_score = round(
        float(field_averages.get("food", 0.0)) * 0.36
        + float(field_averages.get("plankton", 0.0)) * 0.30
        + float(field_averages.get("nutrients", 0.0)) * 0.18
        + float(field_averages.get("balance", 0.0)) * 0.16,
        4,
    )
    crowding = float(field_averages.get("population_pressure", 0.0))
    balance = float(field_averages.get("balance", 0.0))
    phase = "stable"
    if state == "extinct":
        phase = "extinct"
    elif state == "dormant":
        phase = "dormant"
    elif adults <= 3 and viable <= 1:
        phase = "bottleneck"
    elif recent_births > 0 and viable > 0 and recent_births >= recent_deaths:
        phase = "recovering"
    elif balance > 0.62 and resource_score > 0.42 and adults <= 8:
        phase = "rebound"
    elif population["trend"] == "declining":
        phase = "declining"

    if recent_births > recent_deaths:
        adult_trend = "recovering"
    elif recent_deaths > recent_births:
        adult_trend = "declining"
    elif adults <= 3:
        adult_trend = "bottlenecked"
    else:
        adult_trend = "stable"

    if viable == 0:
        egg_trend = "absent"
    elif dormant > 0:
        egg_trend = "dormant reserve"
    elif recent_births > 0:
        egg_trend = "hatching"
    else:
        egg_trend = "viable reserve"

    gate = diagnostics["gate_failures"][0]["reason"] if diagnostics["gate_failures"] else "none"
    resource_state = "resource bloom" if balance > 0.64 else "resource opportunity" if resource_score > 0.42 else "resource limited"
    crowding_state = "locally crowded" if crowding > 0.18 else "low pressure"
    dominant_policy = (policies.get("dominant") or {}).get("label", "none")
    mechanism = "none"
    if phase == "dormant":
        mechanism = "egg bank preserves lineage continuity"
    elif recent_births > 0:
        mechanism = "recent births or hatches"
    elif viable > 0:
        mechanism = "viable egg reserve"
    elif resource_score > 0.42:
        mechanism = "resource rebound opportunity"
    elif adults > 0:
        mechanism = "adult survivor persistence"
    evidence = [
        f"adults={adults}",
        f"viable_eggs={viable}",
        f"dormant_eggs={dormant}",
        f"recent_births={recent_births}",
        f"recent_deaths={recent_deaths}",
        f"top_gate={gate.replace('_', ' ')}",
        f"resource={resource_state}",
        f"crowding={crowding_state}",
    ]
    recent_recovery_events = [
        item
        for item in timeline
        if item["title"] in {"birth", "egg clutch", "egg hatched", "dormant biosphere", "resource bloom"}
        or item["type"] in {"reproduction", "ecology"}
    ][:6]
    return {
        "phase": phase,
        "adult_trend": adult_trend,
        "egg_trend": egg_trend,
        "lineage_survival": lineages["diversity"],
        "dominant_policy": dominant_policy,
        "egg_bank_contribution": "strong" if viable >= max(4, adults // 2) else "moderate" if viable else "none",
        "resource_rebound": resource_state,
        "crowding_state": crowding_state,
        "gate_pressure": gate,
        "mechanism": mechanism,
        "resource_score": resource_score,
        "recent_recovery_events": recent_recovery_events,
        "evidence": evidence,
    }


def _population_summary(telemetry: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    adults = int(telemetry.get("adult_population", telemetry.get("population", 0)) or 0)
    eggs = int(telemetry.get("egg_count", 0) or 0)
    viable = int(telemetry.get("viable_egg_count", 0) or 0)
    dormant = int(telemetry.get("dormant_egg_count", 0) or 0)
    recent_births = sum(1 for event in events if event.get("kind") in {"birth", "egg_hatched"})
    recent_deaths = sum(1 for event in events if event.get("kind") in {"death", "egg_died"})
    trend = "stable"
    if adults == 0 and viable > 0:
        trend = "dormant"
    elif recent_births > recent_deaths + 1:
        trend = "recovering"
    elif recent_deaths > recent_births + 1:
        trend = "declining"
    elif adults <= 4 and viable == 0:
        trend = "at risk"

    gate_reasons = telemetry.get("reproduction_gate_reasons", {}) or {}
    top_gate = next(iter(gate_reasons), "")
    if top_gate in {"not_mature", "too_old_or_low_fertility"}:
        pressure = "lifecycle constrained"
    elif top_gate in {"low_energy", "reproductive_drive_too_low", "clutch_energy_too_low"}:
        pressure = "energy constrained"
    elif top_gate in {"bad_environment", "overcrowded"}:
        pressure = "environment constrained"
    elif adults == 0 and viable > 0:
        pressure = "waiting on egg bank"
    else:
        pressure = "open"

    if viable == 0:
        resilience = "none"
    elif viable >= max(4, adults // 2):
        resilience = "strong"
    elif dormant > 0 or viable >= max(2, adults // 5):
        resilience = "moderate"
    else:
        resilience = "weak"

    return {
        "biosphere_state": telemetry.get("biosphere_state", "active"),
        "adults": adults,
        "eggs": eggs,
        "viable_eggs": viable,
        "dormant_eggs": dormant,
        "births": int(telemetry.get("births", 0) or 0),
        "eggs_laid": int(telemetry.get("eggs_laid", 0) or 0),
        "eggs_hatched": int(telemetry.get("eggs_hatched", 0) or 0),
        "deaths": sum(int(count) for count in (telemetry.get("deaths_by_cause", {}) or {}).values()),
        "lineages": int(telemetry.get("lineage_count", 0) or 0),
        "policies": int(telemetry.get("instruction", {}).get("policy_variants_alive", 0) or 0),
        "trend": trend,
        "reproduction_pressure": pressure,
        "egg_bank_resilience": resilience,
        "recent_births": recent_births,
        "recent_deaths": recent_deaths,
    }


def _lineage_summary(fish: Sequence[Any], eggs: Sequence[Any]) -> dict[str, Any]:
    adult_counts: Counter[int] = Counter(getattr(item, "lineage_id", 0) for item in fish)
    egg_counts: Counter[int] = Counter(getattr(item, "lineage_id", 0) for item in eggs if getattr(item, "viable", False))
    rows: list[dict[str, Any]] = []
    for lineage_id, adult_count in adult_counts.most_common(10):
        lineage_fish = [item for item in fish if getattr(item, "lineage_id", None) == lineage_id]
        policy_counts = Counter(item.instruction_genome.policy_label for item in lineage_fish)
        species_counts = Counter(getattr(item, "species_id", "unknown") for item in lineage_fish)
        generations = [int(getattr(item, "generation", 0)) for item in lineage_fish]
        rows.append(
            {
                "lineage_id": lineage_id,
                "adults": adult_count,
                "viable_eggs": egg_counts.get(lineage_id, 0),
                "species_id": species_counts.most_common(1)[0][0] if species_counts else "unknown",
                "policy_label": policy_counts.most_common(1)[0][0] if policy_counts else "unknown",
                "generation_min": min(generations) if generations else 0,
                "generation_max": max(generations) if generations else 0,
            }
        )
    dormant_lineages = sorted({getattr(item, "lineage_id", 0) for item in eggs if getattr(item, "viable", False)} - set(adult_counts))
    diversity = "none"
    if len(adult_counts) >= 8:
        diversity = "broad"
    elif len(adult_counts) >= 3:
        diversity = "moderate"
    elif adult_counts:
        diversity = "narrow"
    elif dormant_lineages:
        diversity = "dormant"
    return {
        "active_count": len(adult_counts),
        "egg_lineage_count": len(egg_counts),
        "diversity": diversity,
        "dominant": rows[0] if rows else None,
        "top": rows,
        "dormant_lineages": dormant_lineages[:8],
    }


def _morphology_summary(telemetry: dict[str, Any], fish: Sequence[Any]) -> dict[str, Any]:
    telemetry_summary = telemetry.get("morphology", {}) or {}
    label_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for item in fish:
        affordances = item.morphology_affordances
        labels = item.genome.morphology_labels()
        label = labels[0] if labels else "generalized aquatic body plan"
        label_counts[label] += 1
        rows.append(
            {
                "fish_id": item.fish_id,
                "lineage_id": item.lineage_id,
                "morphology_hash": item.genome.morphology_hash,
                "label": label,
                "viability_index": round(affordances.viability_index, 3),
                "feeding_throughput": round(affordances.feeding_throughput, 3),
                "drag": round(affordances.drag, 3),
                "oxygen_cost": round(affordances.oxygen_cost, 3),
                "primary_affordances": _primary_affordances(affordances),
                "primary_costs": _primary_costs(affordances),
            }
        )
    rows.sort(key=lambda row: (row["viability_index"], -row["drag"], row["fish_id"]))
    return {
        "schema": "aquagenesys.morphology_dashboard.v1",
        "summary": telemetry_summary,
        "top_labels": [{"label": label, "count": count} for label, count in label_counts.most_common(8)],
        "notable": rows[:8],
        "claim_boundary": "Morphology labels are observational summaries; primitive affordances and costs drive mechanics.",
    }


def _primary_affordances(affordances: Any) -> list[str]:
    values = {
        "reach": affordances.reach,
        "grip": affordances.grip,
        "bite force": affordances.bite_force,
        "suction": affordances.suction_force,
        "filtering": affordances.filter_rate,
        "armor": affordances.armor_protection,
        "toxin payload": affordances.toxin_payload,
        "sensory range": affordances.sensory_range,
    }
    return [label for label, _value in sorted(values.items(), key=lambda item: item[1], reverse=True)[:3]]


def _primary_costs(affordances: Any) -> list[str]:
    values = {
        "drag": affordances.drag,
        "oxygen": affordances.oxygen_cost,
        "growth": affordances.growth_cost,
        "reproduction": affordances.reproduction_cost,
        "juvenile fragility": affordances.juvenile_fragility,
        "self-toxicity": affordances.toxin_self_cost,
    }
    return [label for label, value in sorted(values.items(), key=lambda item: item[1], reverse=True)[:3] if value >= 0.22]


def _policy_summary(fish: Sequence[Any]) -> dict[str, Any]:
    labels: Counter[str] = Counter(item.instruction_genome.policy_label for item in fish)
    hashes: Counter[str] = Counter(item.instruction_genome.policy_hash_short for item in fish)
    risk: Counter[str] = Counter(item.instruction_genome.risk_posture for item in fish)
    forage: Counter[str] = Counter(item.instruction_genome.forage_strategy for item in fish)
    energy: Counter[str] = Counter(item.instruction_genome.energy_strategy for item in fish)
    rows = [
        {
            "label": label,
            "count": count,
            "share": round(count / max(1, len(fish)), 3),
        }
        for label, count in labels.most_common(8)
    ]
    return {
        "active_count": len(hashes),
        "families": rows,
        "dominant": rows[0] if rows else None,
        "risk_mix": [{"label": key, "count": value} for key, value in risk.most_common()],
        "forage_mix": [{"label": key, "count": value} for key, value in forage.most_common(5)],
        "energy_mix": [{"label": key, "count": value} for key, value in energy.most_common(5)],
    }


def _teaching_summary(telemetry: dict[str, Any], instruction_log: list[dict[str, Any]]) -> dict[str, Any]:
    instruction = telemetry.get("instruction", {}) or {}
    delivery = Counter(str(item.get("delivery", "unknown")) for item in instruction_log if item.get("event_type") == "offspring_instruction_inheritance")
    survived = [
        {
            "tick": item.get("tick"),
            "parent_id": item.get("parent_id"),
            "child_id": item.get("child_id"),
            "egg_id": item.get("egg_id"),
            "delivery": item.get("delivery"),
            "policy_label": item.get("offspring_policy_label", ""),
            "skill_count": item.get("skill_count", 0),
        }
        for item in reversed(instruction_log)
        if item.get("event_type") == "offspring_instruction_inheritance"
    ][:8]
    return {
        "inheritance_enabled": bool(instruction.get("inheritance_enabled", False)),
        "model_teaching_enabled": bool(instruction.get("model_teaching_enabled", False)),
        "events": int(instruction.get("teaching_events", 0) or 0),
        "inheritance_events": int(instruction.get("inheritance_events", 0) or 0),
        "patches_proposed": int(instruction.get("patches_proposed", 0) or 0),
        "patches_accepted": int(instruction.get("patches_accepted", 0) or 0),
        "patches_rejected": int(instruction.get("patches_rejected", 0) or 0),
        "delivery_mix": [{"label": key, "count": value} for key, value in delivery.most_common(4)],
        "recent_surviving": survived,
    }


def _skill_evidence_summary(telemetry: dict[str, Any]) -> dict[str, Any]:
    evidence = telemetry.get("skill_evidence", {}) or {}
    summary = evidence.get("summary", {}) or {}
    aggregates = list(evidence.get("aggregates", []) or [])[:8]
    recent_events = list(evidence.get("recent_events", []) or [])[:8]
    uses = int(summary.get("observed_uses", 0) or 0)
    carriers = int(summary.get("carriers", 0) or 0)
    if uses:
        headline = (
            f"{uses} inherited-behavior uses observed across {carriers} visible carriers; "
            f"{summary.get('helped_possible', 0)} helped possible, {summary.get('harmed_possible', 0)} harmed possible, "
            f"{summary.get('unclear', 0)} unclear."
        )
    elif carriers:
        headline = f"{carriers} visible descendants carry taught skills; no use has been observed yet."
    else:
        headline = "No inherited behavior evidence has been recorded yet."
    return {
        "schema": evidence.get("schema", "aquagenesys.skill_evidence.v1"),
        "headline": headline,
        "summary": summary,
        "aggregates": aggregates,
        "recent_events": recent_events,
        "claim_boundary": summary.get(
            "claim_boundary",
            "Skill evidence is observational. It suggests possible effects but does not prove causality.",
        ),
    }


def _diagnostics_summary(telemetry: dict[str, Any]) -> dict[str, Any]:
    gates = [
        {"reason": str(reason), "count": int(count)}
        for reason, count in (telemetry.get("reproduction_gate_reasons", {}) or {}).items()
    ][:8]
    rejections = [
        {"reason": str(reason), "count": int(count)}
        for reason, count in (telemetry.get("instruction", {}).get("rejection_reasons", {}) or {}).items()
    ][:8]
    model = telemetry.get("model", {}) or {}
    return {
        "gate_failures": gates,
        "patch_rejections": rejections,
        "model": {
            "enabled": bool(model.get("enabled", False)),
            "calls": int(model.get("calls", 0) or 0),
            "pending": int(model.get("pending", 0) or 0),
            "failures": int(model.get("failures", 0) or 0),
            "last_error": model.get("last_error", ""),
        },
    }


def _timeline(
    events: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
    instruction_log: list[dict[str, Any]],
    decision_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events[-14:]:
        kind = str(event.get("kind", "event"))
        rows.append(
            {
                "tick": event.get("tick", 0),
                "type": _event_type(kind),
                "title": kind.replace("_", " "),
                "detail": _event_detail(event),
                "fish_id": event.get("fish_id") or event.get("parent") or event.get("child"),
                "lineage_id": event.get("lineage"),
                "severity": _event_severity(kind),
            }
        )
    for item in reproduction_log[-8:]:
        reason = str(item.get("reason", "reproduction"))
        if reason in {"not_mature", "cooldown"}:
            continue
        rows.append(
            {
                "tick": item.get("tick", 0),
                "type": "reproduction",
                "title": reason.replace("_", " "),
                "detail": _reproduction_detail(item),
                "fish_id": item.get("fish_id"),
                "lineage_id": item.get("lineage"),
                "severity": "info" if item.get("egg_count") or item.get("offspring_count") else "warn",
            }
        )
    for item in instruction_log[-8:]:
        rows.append(
            {
                "tick": item.get("tick", 0),
                "type": "instruction",
                "title": str(item.get("event_type", "instruction")).replace("_", " "),
                "detail": item.get("offspring_policy_label") or item.get("patch_reason") or item.get("patch_id") or "",
                "fish_id": item.get("parent_id"),
                "lineage_id": item.get("lineage_id"),
                "severity": "warn" if item.get("patch_accepted") is False else "info",
            }
        )
    for item in decision_log[-6:]:
        rows.append(
            {
                "tick": item.get("tick", 0),
                "type": "behavior",
                "title": f"#{item.get('fish_id')} {item.get('action')}",
                "detail": f"{item.get('source')}: {item.get('outcome')}",
                "fish_id": item.get("fish_id"),
                "lineage_id": None,
                "severity": "info",
            }
        )
    rows.sort(key=lambda item: int(item.get("tick", 0) or 0), reverse=True)
    return rows[:22]


def _narrator(
    telemetry: dict[str, Any],
    population: dict[str, Any],
    lineages: dict[str, Any],
    morphology: dict[str, Any],
    policies: dict[str, Any],
    teaching: dict[str, Any],
    diagnostics: dict[str, Any],
    timeline: list[dict[str, Any]],
    recovery: dict[str, Any],
) -> dict[str, Any]:
    adults = population["adults"]
    viable = population["viable_eggs"]
    state = population["biosphere_state"]
    if state == "dormant":
        headline = f"No adults are active, but {viable} viable eggs keep the puddle dormant rather than extinct."
    elif state == "extinct":
        headline = "The puddle is biologically extinct; chemistry continues but no viable adults or eggs remain."
    elif recovery["phase"] in {"recovering", "rebound"}:
        headline = f"The puddle is {recovery['phase']}: {adults} adults are supported by {recovery['mechanism']}."
    elif recovery["phase"] == "bottleneck":
        headline = f"The puddle is bottlenecked: {adults} adults remain and egg-bank contribution is {recovery['egg_bank_contribution']}."
    elif population["trend"] == "declining":
        headline = f"The active puddle is under pressure: {adults} adults remain and recent losses outnumber recoveries."
    else:
        headline = f"The active puddle has {adults} adults, {viable} viable eggs, and {lineages['active_count']} active lineages."

    points: list[str] = []
    resilience = population["egg_bank_resilience"]
    points.append(f"Egg bank resilience is {resilience}: {viable} viable eggs, {population['dormant_eggs']} dormant.")
    points.append(
        f"Recovery evidence: phase {recovery['phase']}, {recovery['resource_rebound']}, {recovery['crowding_state']}, gate pressure {str(recovery['gate_pressure']).replace('_', ' ')}."
    )
    dominant_lineage = lineages.get("dominant")
    if dominant_lineage:
        points.append(
            f"Lineage {dominant_lineage['lineage_id']} currently leads with {dominant_lineage['adults']} adults and policy {dominant_lineage['policy_label']}."
        )
    elif lineages.get("dormant_lineages"):
        points.append(f"Dormant lineage traces remain in eggs: {', '.join(str(item) for item in lineages['dormant_lineages'][:4])}.")
    morphology_label = (morphology.get("top_labels") or [{}])[0].get("label")
    if morphology_label:
        morph_summary = morphology.get("summary", {}) or {}
        points.append(
            f"Morphology mix is led by {morphology_label}; average viability {morph_summary.get('average_viability_index', '-')}, drag {morph_summary.get('average_drag', '-')}."
        )
    dominant_policy = policies.get("dominant")
    if dominant_policy:
        points.append(
            f"{dominant_policy['label']} is the most common policy family at {dominant_policy['count']} adults."
        )
    points.append(
        f"Reproduction pressure is {population['reproduction_pressure']}; top gate failures are {', '.join(item['reason'].replace('_', ' ') for item in diagnostics['gate_failures'][:3]) or 'not dominant'}."
    )
    if teaching["inheritance_events"] or teaching["patches_rejected"]:
        points.append(
            f"Instruction inheritance has {teaching['inheritance_events']} deliveries, {teaching['patches_accepted']} accepted patches, and {teaching['patches_rejected']} rejected patches."
        )
    recent = [item for item in timeline if item["type"] in {"ecology", "reproduction", "instruction"}][:2]
    for item in recent:
        detail = f": {item['detail']}" if item.get("detail") else ""
        points.append(f"Recent {item['type']} event at tick {item['tick']}: {item['title']}{detail}.")
    return {
        "headline": headline,
        "points": points[:6],
        "signals": {
            "biosphere_state": state,
            "trend": population["trend"],
            "resilience": resilience,
            "lineage_diversity": lineages["diversity"],
            "policy_variants": policies["active_count"],
        },
    }


def _focus_hints(fish: Sequence[Any], eggs: Sequence[Any]) -> dict[str, Any]:
    lineage_adults: Counter[int] = Counter(getattr(item, "lineage_id", 0) for item in fish)
    lineage_eggs: Counter[int] = Counter(getattr(item, "lineage_id", 0) for item in eggs if getattr(item, "viable", False))
    nearest: dict[int, dict[str, Any]] = {}
    for item in fish:
        best = None
        best_distance = 9999.0
        for other in fish:
            if other is item:
                continue
            distance = hypot(float(getattr(item, "x", 0.0)) - float(getattr(other, "x", 0.0)), float(getattr(item, "y", 0.0)) - float(getattr(other, "y", 0.0)))
            if distance < best_distance:
                best = other
                best_distance = distance
        if best is not None and best_distance <= 8.0:
            nearest[getattr(item, "fish_id", 0)] = {
                "fish_id": getattr(best, "fish_id", 0),
                "distance": round(best_distance, 2),
                "same_lineage": getattr(item, "lineage_id", None) == getattr(best, "lineage_id", None),
                "same_policy": item.instruction_genome.policy_hash_short == best.instruction_genome.policy_hash_short,
            }
    return {
        "lineage_adults": {str(key): value for key, value in lineage_adults.items()},
        "lineage_viable_eggs": {str(key): value for key, value in lineage_eggs.items()},
        "nearby": nearest,
    }


def _event_type(kind: str) -> str:
    if kind in {"birth", "egg_clutch", "egg_hatched", "egg_died", "egg_entered_dormancy", "dormant_biosphere", "extinction"}:
        return "reproduction" if kind in {"birth", "egg_clutch", "egg_hatched"} else "ecology"
    if kind.startswith("instruction_"):
        return "instruction"
    if kind.startswith("model_"):
        return "model"
    return "ecology"


def _event_severity(kind: str) -> str:
    if kind in {"death", "egg_died", "extinction", "instruction_patch_rejected", "model_deliberation_failed"}:
        return "warn"
    if kind in {"birth", "egg_clutch", "egg_hatched", "instruction_patch_accepted"}:
        return "good"
    return "info"


def _event_detail(event: dict[str, Any]) -> str:
    kind = event.get("kind")
    if kind == "birth":
        return f"child #{event.get('child')} from parent #{event.get('parent')}"
    if kind == "egg_clutch":
        return f"{event.get('eggs')} eggs from parent #{event.get('parent')}"
    if kind == "egg_hatched":
        return f"egg {event.get('egg_id')} hatched as #{event.get('child')}"
    if kind == "egg_died":
        return str(event.get("cause", "egg died"))
    if kind == "death":
        return f"#{event.get('fish_id')} died: {event.get('cause', 'unknown')}"
    if kind == "dormant_biosphere":
        return f"{event.get('viable_eggs')} viable eggs remain"
    if kind == "instruction_patch_rejected":
        return str(event.get("reason", "rejected"))
    if kind == "instruction_patch_accepted":
        return str(event.get("skill", "accepted"))
    if "value" in event:
        return str(event["value"])
    return ""


def _reproduction_detail(item: dict[str, Any]) -> str:
    if item.get("egg_count"):
        return f"{item['egg_count']} eggs, cost {item.get('energy_cost', 0)}"
    if item.get("offspring_count"):
        return f"{item['offspring_count']} offspring, cost {item.get('energy_cost', 0)}"
    return f"#{item.get('fish_id')} {item.get('fertility_state', '')}".strip()
