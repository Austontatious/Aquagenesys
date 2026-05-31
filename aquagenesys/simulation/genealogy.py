from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Sequence

from aquagenesys.agents.instructions import stable_hash


MAX_NODES = 140
MAX_EDGES = 180
MAX_LINEAGES = 12


def build_genealogy(
    *,
    tick: int,
    run_id: str,
    fish: Sequence[Any],
    eggs: Sequence[Any],
    dead_agent_summaries: dict[int, dict[str, Any]],
    instruction_log: Iterable[dict[str, Any]],
    reproduction_log: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    adult_nodes = [_fish_node(item) for item in fish]
    egg_nodes = [_egg_node(item) for item in eggs if getattr(item, "viable", False)]
    dead_nodes = [_dead_node(item) for item in sorted(dead_agent_summaries.values(), key=lambda row: int(row.get("death_tick", 0)), reverse=True)[:48]]
    nodes = (adult_nodes + egg_nodes + dead_nodes)[:MAX_NODES]
    edges = _edges(nodes)
    lineages = _lineages(nodes)
    policies = _policy_inheritance(nodes, list(instruction_log))
    recovery = _recovery_contributions(nodes, list(reproduction_log), list(events), telemetry)
    skill_evidence = _skill_evidence(telemetry)
    return {
        "schema": "aquagenesys.genealogy.v1",
        "tick": tick,
        "run_id": run_id,
        "bounded": {
            "max_nodes": MAX_NODES,
            "max_edges": MAX_EDGES,
            "dead_nodes_sampled": min(48, len(dead_agent_summaries)),
        },
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "live_adults": len(adult_nodes),
            "viable_eggs": len(egg_nodes),
            "dead_ancestors_sampled": len(dead_nodes),
            "lineages": len(lineages),
            "policy_families": policies["active_policy_count"],
        },
        "lineages": lineages,
        "nodes": nodes,
        "edges": edges,
        "policy_inheritance": policies,
        "recovery_contributions": recovery,
        "skill_evidence": skill_evidence,
        "thesis": "Instruction changes intent. Biology controls capability. Ecology decides what persists.",
    }


def _fish_node(fish: Any) -> dict[str, Any]:
    genome = fish.genome
    instruction = fish.instruction_genome
    life = fish.life_history
    return {
        "node_id": f"fish:{fish.fish_id}",
        "entity": "adult",
        "state": "live",
        "fish_id": fish.fish_id,
        "egg_id": None,
        "lineage_id": fish.lineage_id,
        "species_id": fish.species_id,
        "generation": fish.generation,
        "parent_ids": list(fish.parent_ids),
        "biology": _biology_signature(genome),
        "behavior": _behavior_signature(
            instruction,
            len(fish.taught_skills),
            fish.accepted_instruction_patch_ids,
            fish.rejected_instruction_patch_ids,
            getattr(fish, "last_behavior_rationale", {}) or {},
        ),
        "capability": {
            "archetype": genome.archetype,
            "metabolism": genome.metabolism,
            "morphology_hash": genome.morphology_hash,
            "morphology_label": genome.morphology_labels()[0],
            "affordances": genome.morphology_affordances().compact_payload(),
            "body": genome.body_shape,
            "tail": genome.tail_shape,
            "max_speed": round(genome.max_speed, 3),
            "body_size": round(genome.body_size, 3),
            "life_history": life.brood_strategy,
            "egg_strategy": life.egg_strategy,
        },
        "outcome": {
            "role": "survivor",
            "energy": round(fish.energy, 2),
            "health": round(fish.health, 3),
            "fertility_state": fish.fertility_state,
            "reproduction_gate": fish.last_reproduction_gate,
        },
    }


def _egg_node(egg: Any) -> dict[str, Any]:
    genome = egg.genome
    instruction = egg.instruction_genome
    life = genome.life_history()
    return {
        "node_id": f"egg:{egg.egg_id}",
        "entity": "egg",
        "state": "dormant" if egg.dormant else "gestating",
        "fish_id": None,
        "egg_id": egg.egg_id,
        "lineage_id": egg.lineage_id,
        "species_id": egg.species_id,
        "generation": egg.generation,
        "parent_ids": list(egg.parent_ids),
        "biology": _biology_signature(genome),
        "behavior": _behavior_signature(instruction, len(egg.taught_skills), instruction.accepted_patch_ids, instruction.rejected_patch_ids),
        "capability": {
            "archetype": genome.archetype,
            "metabolism": genome.metabolism,
            "morphology_hash": genome.morphology_hash,
            "morphology_label": genome.morphology_labels()[0],
            "affordances": genome.morphology_affordances().compact_payload(),
            "body": genome.body_shape,
            "tail": genome.tail_shape,
            "max_speed": round(genome.max_speed, 3),
            "body_size": round(genome.body_size, 3),
            "life_history": life.brood_strategy,
            "egg_strategy": egg.dormancy_strategy,
        },
        "outcome": {
            "role": "egg_bank",
            "viability": round(egg.viability, 3),
            "dormant": egg.dormant,
            "parthenogenetic": egg.parthenogenetic,
            "age_ticks": egg.age_ticks,
            "gestation_ticks": egg.gestation_ticks,
        },
    }


def _dead_node(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": f"dead:{summary.get('fish_id')}",
        "entity": "adult",
        "state": "dead",
        "fish_id": summary.get("fish_id"),
        "egg_id": None,
        "lineage_id": summary.get("lineage_id"),
        "species_id": summary.get("species_id", "unknown"),
        "generation": summary.get("generation", 0),
        "parent_ids": list(summary.get("parent_ids", [])),
        "biology": {
            "genome_hash": str(summary.get("biological_genome_hash", ""))[:12],
            "phenotype_hash": str(summary.get("phenotype_hash", ""))[:12],
            "morphology_hash": str(summary.get("morphology_hash", ""))[:18],
            "signature": str(summary.get("biological_genome_hash", ""))[:8],
        },
        "behavior": {
            "policy_hash": str(summary.get("instruction_policy_hash", ""))[:12],
            "policy_hash_short": str(summary.get("instruction_policy_hash", ""))[:8],
            "policy_label": summary.get("instruction_policy_label", "unknown"),
            "taught_skill_count": len(summary.get("taught_skill_hashes", [])),
            "accepted_patch_count": len(summary.get("accepted_instruction_patch_ids", [])),
            "rejected_patch_count": len(summary.get("rejected_instruction_patch_ids", [])),
            "current_action": (summary.get("behavior_rationale") or {}).get("current_action", ""),
            "top_candidate": ((summary.get("behavior_rationale") or {}).get("candidate_summary") or [{}])[0].get("action", ""),
            "context_tags": list((summary.get("behavior_rationale") or {}).get("context_tags", []))[:6],
            "affordance_tags": list((summary.get("behavior_rationale") or {}).get("affordance_tags", []))[:6],
            "mismatch_warnings": list((summary.get("behavior_rationale") or {}).get("mismatch_warnings", []))[:4],
        },
        "capability": {
            "archetype": summary.get("archetype", "unknown"),
            "metabolism": summary.get("metabolism", "unknown"),
            "morphology_hash": str(summary.get("morphology_hash", ""))[:18],
            "morphology_label": (summary.get("morphology_labels") or ["archived morphology"])[0],
            "body": summary.get("body_shape", "unknown"),
            "tail": summary.get("tail_shape", "unknown"),
            "max_speed": None,
            "body_size": None,
            "life_history": "archived",
            "egg_strategy": "archived",
        },
        "outcome": {
            "role": "ancestor",
            "death_tick": summary.get("death_tick"),
            "death_cause": summary.get("death_cause", ""),
            "summary_stats": summary.get("summary_stats", {}),
        },
    }


def _biology_signature(genome: Any) -> dict[str, str]:
    payload = genome.payload()
    phenotype = genome.phenotype_payload(compact=True)
    payload.pop("phenotype", None)
    payload.pop("life_history", None)
    genome_hash = stable_hash(payload, length=16)
    phenotype_hash = stable_hash(phenotype, length=16)
    return {
        "genome_hash": genome_hash,
        "phenotype_hash": phenotype_hash,
        "morphology_hash": genome.morphology_hash,
        "morphology_label": genome.morphology_labels()[0],
        "signature": f"{genome.metabolism[:3]}-{genome.body_shape[:3]}-{genome.morphology_hash[-6:]}",
    }


def _behavior_signature(
    instruction: Any,
    taught_skill_count: int,
    accepted_patch_ids: Sequence[str],
    rejected_patch_ids: Sequence[str],
    rationale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    behavior = rationale or {}
    top_candidate = (behavior.get("candidate_summary") or [{}])[0]
    return {
        "policy_hash": instruction.policy_hash,
        "policy_hash_short": instruction.policy_hash_short,
        "policy_label": instruction.policy_label,
        "risk_posture": instruction.risk_posture,
        "forage_strategy": instruction.forage_strategy,
        "threat_strategy": instruction.threat_strategy,
        "social_strategy": instruction.social_strategy,
        "exploration_strategy": instruction.exploration_strategy,
        "energy_strategy": instruction.energy_strategy,
        "teaching_style": instruction.teaching_style,
        "taught_skill_count": taught_skill_count,
        "accepted_patch_count": len(accepted_patch_ids),
        "rejected_patch_count": len(rejected_patch_ids),
        "current_action": behavior.get("current_action", ""),
        "action_reason": behavior.get("action_reason", ""),
        "top_candidate": top_candidate.get("action", behavior.get("current_action", "")),
        "top_candidate_score": top_candidate.get("score", 0),
        "context_tags": list(behavior.get("context_tags", []))[:6],
        "affordance_tags": list(behavior.get("affordance_tags", []))[:6],
        "policy_influence": list(behavior.get("policy_influence", []))[:4],
        "skill_influence": list(behavior.get("skill_influence", []))[:4],
        "mismatch_warnings": list(behavior.get("mismatch_warnings", []))[:4],
    }


def _edges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_fish_ids = {node["fish_id"] for node in nodes if node.get("fish_id") is not None}
    rows: list[dict[str, Any]] = []
    for node in nodes:
        child_id = node["node_id"]
        for parent_id in node.get("parent_ids", []):
            rows.append(
                {
                    "from": f"fish:{parent_id}" if parent_id in known_fish_ids else f"ancestor:{parent_id}",
                    "to": child_id,
                    "parent_fish_id": parent_id,
                    "child_fish_id": node.get("fish_id"),
                    "child_egg_id": node.get("egg_id"),
                    "lineage_id": node.get("lineage_id"),
                    "type": "egg_deposition" if node.get("entity") == "egg" else "offspring",
                    "generation": node.get("generation", 0),
                    "policy_hash_short": node.get("behavior", {}).get("policy_hash_short", ""),
                }
            )
    return rows[:MAX_EDGES]


def _lineages(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_lineage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        lineage = node.get("lineage_id")
        if lineage is not None:
            by_lineage[int(lineage)].append(node)
    rows: list[dict[str, Any]] = []
    for lineage_id, lineage_nodes in by_lineage.items():
        states = Counter(node["state"] for node in lineage_nodes)
        policies = Counter(node["behavior"].get("policy_label", "unknown") for node in lineage_nodes if node["state"] != "dead")
        generations = [int(node.get("generation", 0) or 0) for node in lineage_nodes]
        rows.append(
            {
                "lineage_id": lineage_id,
                "nodes": len(lineage_nodes),
                "live_adults": states.get("live", 0),
                "viable_eggs": states.get("gestating", 0) + states.get("dormant", 0),
                "dormant_eggs": states.get("dormant", 0),
                "dead_sample": states.get("dead", 0),
                "generation_min": min(generations) if generations else 0,
                "generation_max": max(generations) if generations else 0,
                "dominant_policy": policies.most_common(1)[0][0] if policies else "none",
                "status": "active" if states.get("live", 0) else "dormant" if states.get("dormant", 0) or states.get("gestating", 0) else "archived",
            }
        )
    rows.sort(key=lambda row: (row["live_adults"], row["viable_eggs"], row["nodes"]), reverse=True)
    return rows[:MAX_LINEAGES]


def _policy_inheritance(nodes: list[dict[str, Any]], instruction_log: list[dict[str, Any]]) -> dict[str, Any]:
    active = [node for node in nodes if node["state"] in {"live", "gestating", "dormant"}]
    families = Counter(node["behavior"].get("policy_label", "unknown") for node in active)
    hashes = Counter(node["behavior"].get("policy_hash_short", "") for node in active)
    recent = [
        {
            "tick": item.get("tick"),
            "parent_id": item.get("parent_id"),
            "child_id": item.get("child_id"),
            "egg_id": item.get("egg_id"),
            "lineage_id": item.get("lineage_id"),
            "delivery": item.get("delivery"),
            "policy_label": item.get("offspring_policy_label", ""),
            "skill_hashes": list(item.get("skill_hashes", []))[:4],
            "skill_count": int(item.get("skill_count", 0) or 0),
            "patch_accepted": item.get("patch_accepted"),
            "patch_reason": item.get("patch_reason", ""),
        }
        for item in reversed(instruction_log)
        if item.get("event_type") == "offspring_instruction_inheritance"
    ][:12]
    return {
        "active_policy_count": len([key for key in hashes if key]),
        "families": [{"label": label, "count": count} for label, count in families.most_common(8)],
        "recent_inheritance": recent,
        "accepted_patch_nodes": sum(node["behavior"].get("accepted_patch_count", 0) for node in nodes),
        "rejected_patch_nodes": sum(node["behavior"].get("rejected_patch_count", 0) for node in nodes),
    }


def _skill_evidence(telemetry: dict[str, Any]) -> dict[str, Any]:
    evidence = telemetry.get("skill_evidence", {}) or {}
    return {
        "schema": evidence.get("schema", "aquagenesys.skill_evidence.v2"),
        "summary": evidence.get("summary", {}),
        "aggregates": list(evidence.get("aggregates", []) or [])[:MAX_LINEAGES],
        "recent_events": list(evidence.get("recent_events", []) or [])[:12],
    }


def _recovery_contributions(
    nodes: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
    events: list[dict[str, Any]],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    event_lineages = Counter(int(event.get("lineage", 0)) for event in events if event.get("kind") in {"egg_hatched", "birth", "egg_clutch"} and event.get("lineage"))
    egg_lineages = Counter(node["lineage_id"] for node in nodes if node["state"] in {"gestating", "dormant"})
    survivor_lineages = Counter(node["lineage_id"] for node in nodes if node["state"] == "live")
    gates = Counter(str(item.get("reason", "unknown")) for item in reproduction_log[-32:])
    top = sorted(set(event_lineages) | set(egg_lineages) | set(survivor_lineages))[:MAX_LINEAGES]
    return {
        "biosphere_state": telemetry.get("biosphere_state", "active"),
        "last_recovery_kind": telemetry.get("last_recovery_kind", "none"),
        "lineages": [
            {
                "lineage_id": lineage,
                "recent_recovery_events": event_lineages.get(lineage, 0),
                "live_adults": survivor_lineages.get(lineage, 0),
                "viable_eggs": egg_lineages.get(lineage, 0),
                "role": "egg-bank recovery" if egg_lineages.get(lineage, 0) else "adult survivor" if survivor_lineages.get(lineage, 0) else "event trace",
            }
            for lineage in top
        ],
        "top_reproduction_gates": [{"reason": reason, "count": count} for reason, count in gates.most_common(6)],
    }
