from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable


SCHEMA = "aquagenesys.lineage_story.v1"
THESIS = "Instruction changes intent. Biology controls capability. Ecology decides what persists."
QUESTIONS = (
    "Who survived?",
    "What did they inherit?",
    "What changed?",
    "What did they try?",
    "What killed the others?",
    "Why did this lineage persist?",
)
MAX_STORIES = 6
MAX_EVIDENCE = 6


def build_lineage_story(
    *,
    tick: int,
    run_id: str,
    telemetry: dict[str, Any],
    dashboard: dict[str, Any],
    genealogy: dict[str, Any],
    events: Iterable[dict[str, Any]],
    reproduction_log: Iterable[dict[str, Any]],
    instruction_log: Iterable[dict[str, Any]],
    dead_agent_summaries: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Render bounded, deterministic lineage stories from existing evidence."""

    nodes = list(genealogy.get("nodes", []))
    lineages = list(genealogy.get("lineages", []))
    recent_events = list(events)
    recent_reproduction = list(reproduction_log)
    recent_instruction = list(instruction_log)
    story_lineages = _rank_story_lineages(lineages, nodes)
    stories = [
        _lineage_story(
            lineage=lineage,
            nodes=[node for node in nodes if node.get("lineage_id") == lineage["lineage_id"]],
            telemetry=telemetry,
            dashboard=dashboard,
            genealogy=genealogy,
            events=recent_events,
            reproduction_log=recent_reproduction,
            instruction_log=recent_instruction,
            dead_agent_summaries=dead_agent_summaries,
        )
        for lineage in story_lineages[:MAX_STORIES]
    ]
    primary = stories[0] if stories else _empty_story(telemetry, dashboard)
    return {
        "schema": SCHEMA,
        "tick": tick,
        "run_id": run_id,
        "thesis": THESIS,
        "bounded": {
            "max_stories": MAX_STORIES,
            "max_evidence_per_answer": MAX_EVIDENCE,
            "source": "deterministic state renderer",
            "model_dependency": False,
        },
        "summary": {
            "primary_lineage_id": primary.get("lineage_id"),
            "story_count": len(stories),
            "questions_answered": list(QUESTIONS),
            "biosphere_state": telemetry.get("biosphere_state", "active"),
            "recovery_phase": dashboard.get("recovery", {}).get("phase", "unknown"),
            "dominant_policy": (dashboard.get("policies", {}).get("dominant") or {}).get("label", "none"),
            "death_causes": _top_death_causes(telemetry, dead_agent_summaries),
        },
        "questions": _question_cards(primary),
        "lineage_stories": stories,
        "global_story": _global_story(telemetry, dashboard, genealogy, recent_events, dead_agent_summaries),
    }


def _rank_story_lineages(lineages: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if lineages:
        return sorted(
            lineages,
            key=lambda row: (
                int(row.get("live_adults", 0) or 0) > 0,
                int(row.get("viable_eggs", 0) or 0) > 0,
                int(row.get("live_adults", 0) or 0),
                int(row.get("viable_eggs", 0) or 0),
                int(row.get("generation_max", 0) or 0),
                int(row.get("nodes", 0) or 0),
            ),
            reverse=True,
        )
    by_lineage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        lineage = node.get("lineage_id")
        if lineage is not None:
            by_lineage[int(lineage)].append(node)
    rows = []
    for lineage_id, lineage_nodes in by_lineage.items():
        states = Counter(node.get("state", "unknown") for node in lineage_nodes)
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
                "dominant_policy": "unknown",
                "status": "active" if states.get("live", 0) else "dormant" if states.get("gestating", 0) or states.get("dormant", 0) else "archived",
            }
        )
    return _rank_story_lineages(rows, nodes) if rows else []


def _lineage_story(
    *,
    lineage: dict[str, Any],
    nodes: list[dict[str, Any]],
    telemetry: dict[str, Any],
    dashboard: dict[str, Any],
    genealogy: dict[str, Any],
    events: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
    instruction_log: list[dict[str, Any]],
    dead_agent_summaries: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    lineage_id = int(lineage["lineage_id"])
    lineage_nodes = sorted(nodes, key=lambda node: (int(node.get("generation", 0) or 0), _node_sort_id(node)))
    living = [node for node in lineage_nodes if node.get("state") == "live"]
    eggs = [node for node in lineage_nodes if node.get("state") in {"gestating", "dormant"}]
    dead = [node for node in lineage_nodes if node.get("state") == "dead"]
    active = living + eggs
    earliest = lineage_nodes[0] if lineage_nodes else None
    latest = _latest_active_node(active) or (lineage_nodes[-1] if lineage_nodes else None)
    lineage_events = [event for event in events if int(event.get("lineage", -1) or -1) == lineage_id]
    lineage_repro = [row for row in reproduction_log if int(row.get("lineage", -1) or -1) == lineage_id]
    lineage_instruction = [row for row in instruction_log if int(row.get("lineage_id", -1) or -1) == lineage_id]
    death_causes = _lineage_death_causes(lineage_id, dead, dead_agent_summaries)
    answers = {
        "who_survived": _who_survived(lineage, living, eggs),
        "inherited": _inherited(latest),
        "changed": _changed(earliest, latest, lineage),
        "tried": _tried(lineage_events, lineage_repro, lineage_instruction),
        "losses": _losses(death_causes, dead, telemetry),
        "persisted": _persisted(lineage, latest, dashboard, genealogy, lineage_events, lineage_repro),
    }
    title = _story_title(lineage, latest, dashboard)
    headline = _story_headline(lineage, answers, dashboard)
    return {
        "lineage_id": lineage_id,
        "title": title,
        "headline": headline,
        "status": lineage.get("status", "unknown"),
        "metrics": {
            "live_adults": int(lineage.get("live_adults", 0) or 0),
            "viable_eggs": int(lineage.get("viable_eggs", 0) or 0),
            "dormant_eggs": int(lineage.get("dormant_eggs", 0) or 0),
            "dead_sample": int(lineage.get("dead_sample", 0) or len(dead)),
            "generation_min": int(lineage.get("generation_min", 0) or 0),
            "generation_max": int(lineage.get("generation_max", 0) or 0),
        },
        "answers": answers,
        "biology_track": _biology_track(earliest, latest),
        "behavior_track": _behavior_track(earliest, latest, lineage_instruction),
        "attempts": _attempts(lineage_events, lineage_repro, lineage_instruction),
        "losses": [{"cause": cause, "count": count} for cause, count in death_causes.most_common(6)],
        "evidence": _story_evidence(lineage, latest, lineage_events, lineage_repro, lineage_instruction, death_causes),
        "node_ids": [str(node.get("node_id")) for node in lineage_nodes[-16:]],
    }


def _empty_story(telemetry: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state = telemetry.get("biosphere_state", "unknown")
    phase = dashboard.get("recovery", {}).get("phase", "unknown")
    return {
        "lineage_id": None,
        "title": "No lineage story available yet",
        "headline": f"The renderer is waiting for lineage evidence; biosphere={state}, phase={phase}.",
        "status": state,
        "metrics": {},
        "answers": {
            "who_survived": "No live adults, viable eggs, or sampled ancestors are available in the bounded genealogy window.",
            "inherited": "No compact biology or instruction inheritance evidence is available yet.",
            "changed": "No lineage generation span is available yet.",
            "tried": "No reproduction or teaching attempts are visible yet.",
            "losses": "No sampled deaths are visible yet.",
            "persisted": "No persistence mechanism is visible yet.",
        },
        "biology_track": [],
        "behavior_track": [],
        "attempts": [],
        "losses": [],
        "evidence": [],
        "node_ids": [],
    }


def _question_cards(story: dict[str, Any]) -> list[dict[str, Any]]:
    answers = story.get("answers", {})
    keys = ("who_survived", "inherited", "changed", "tried", "losses", "persisted")
    return [
        {
            "question": question,
            "answer_key": key,
            "answer": str(answers.get(key, "")),
            "lineage_id": story.get("lineage_id"),
            "evidence": list(story.get("evidence", []))[:MAX_EVIDENCE],
        }
        for question, key in zip(QUESTIONS, keys, strict=True)
    ]


def _global_story(
    telemetry: dict[str, Any],
    dashboard: dict[str, Any],
    genealogy: dict[str, Any],
    events: list[dict[str, Any]],
    dead_agent_summaries: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    recovery = dashboard.get("recovery", {})
    recent = Counter(str(event.get("kind", "event")) for event in events[-48:])
    return {
        "biosphere_state": telemetry.get("biosphere_state", "active"),
        "recovery_phase": recovery.get("phase", "unknown"),
        "recovery_mechanism": recovery.get("mechanism", "unknown"),
        "active_lineages": telemetry.get("lineage_count", 0),
        "genealogy_nodes": genealogy.get("summary", {}).get("nodes", 0),
        "recent_event_mix": [{"kind": kind, "count": count} for kind, count in recent.most_common(8)],
        "death_causes": _top_death_causes(telemetry, dead_agent_summaries),
    }


def _who_survived(lineage: dict[str, Any], living: list[dict[str, Any]], eggs: list[dict[str, Any]]) -> str:
    adults = int(lineage.get("live_adults", len(living)) or 0)
    viable = int(lineage.get("viable_eggs", len(eggs)) or 0)
    dormant = int(lineage.get("dormant_eggs", sum(1 for node in eggs if node.get("state") == "dormant")) or 0)
    status = lineage.get("status", "unknown")
    examples = [node_label(node) for node in (living + eggs)[:3]]
    suffix = f" Visible survivors: {', '.join(examples)}." if examples else ""
    return f"Lineage L{lineage.get('lineage_id')} is {status}: {adults} adults, {viable} viable eggs, {dormant} dormant eggs.{suffix}"


def _inherited(node: dict[str, Any] | None) -> str:
    if not node:
        return "No active or sampled node is available for inheritance evidence."
    biology = node.get("biology", {})
    behavior = node.get("behavior", {})
    capability = node.get("capability", {})
    return (
        f"It carries biology {biology.get('signature', '-')}, {capability.get('archetype', 'unknown')} "
        f"{capability.get('body', 'body')} body, {capability.get('egg_strategy', 'egg')} egg strategy, "
        f"and policy {behavior.get('policy_hash_short', '-')} ({behavior.get('policy_label', 'unknown')})."
    )


def _changed(earliest: dict[str, Any] | None, latest: dict[str, Any] | None, lineage: dict[str, Any]) -> str:
    if not earliest or not latest:
        return "The bounded genealogy sample does not yet show a before/after comparison."
    changes: list[str] = []
    if earliest.get("biology", {}).get("genome_hash") != latest.get("biology", {}).get("genome_hash"):
        changes.append("compact genome hash changed")
    if earliest.get("biology", {}).get("phenotype_hash") != latest.get("biology", {}).get("phenotype_hash"):
        changes.append("phenotype signature changed")
    if earliest.get("behavior", {}).get("policy_hash_short") != latest.get("behavior", {}).get("policy_hash_short"):
        changes.append(
            f"policy shifted from {earliest.get('behavior', {}).get('policy_hash_short', '-')} to {latest.get('behavior', {}).get('policy_hash_short', '-')}"
        )
    span = f"G{lineage.get('generation_min', earliest.get('generation', 0))} to G{lineage.get('generation_max', latest.get('generation', 0))}"
    if not changes:
        changes.append("no compact biology or policy change is visible in this bounded sample")
    return f"Across {span}, " + "; ".join(changes) + "."


def _tried(events: list[dict[str, Any]], reproduction_log: list[dict[str, Any]], instruction_log: list[dict[str, Any]]) -> str:
    event_counts = Counter(str(event.get("kind", "event")) for event in events)
    successes = event_counts.get("egg_clutch", 0) + event_counts.get("birth", 0) + event_counts.get("egg_hatched", 0)
    inherited = sum(1 for row in instruction_log if row.get("event_type") == "offspring_instruction_inheritance")
    accepted = sum(1 for row in instruction_log if row.get("event_type") == "instruction_patch_acceptance" or row.get("patch_accepted") is True)
    gates = Counter(str(row.get("reason", "unknown")) for row in reproduction_log if row.get("reason") not in {"not_mature", "cooldown"})
    gate_text = ", ".join(reason.replace("_", " ") for reason, _ in gates.most_common(3)) or "no notable blocked gates"
    return f"It tried {successes} visible reproductive recovery events, {inherited} instruction inheritances, {accepted} accepted teaching patches; blocked gates include {gate_text}."


def _losses(death_causes: Counter[str], dead: list[dict[str, Any]], telemetry: dict[str, Any]) -> str:
    if death_causes:
        causes = ", ".join(f"{cause.replace('_', ' ')} x{count}" for cause, count in death_causes.most_common(3))
        return f"Sampled losses in or near this lineage show {causes}."
    deaths = telemetry.get("deaths_by_cause", {}) or {}
    if deaths:
        causes = ", ".join(f"{str(cause).replace('_', ' ')} x{count}" for cause, count in Counter(deaths).most_common(3))
        return f"No lineage-local sampled deaths are visible; global deaths include {causes}."
    if dead:
        return f"{len(dead)} dead ancestors are sampled, but their death causes are not available in the compact node."
    return "No sampled deaths are visible for this lineage yet."


def _persisted(
    lineage: dict[str, Any],
    latest: dict[str, Any] | None,
    dashboard: dict[str, Any],
    genealogy: dict[str, Any],
    events: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
) -> str:
    recovery = dashboard.get("recovery", {})
    contribution = _lineage_recovery_contribution(lineage.get("lineage_id"), genealogy)
    behavior = latest.get("behavior", {}) if latest else {}
    capability = latest.get("capability", {}) if latest else {}
    recent_hatches = sum(1 for event in events if event.get("kind") == "egg_hatched")
    recent_clutches = sum(1 for event in events if event.get("kind") == "egg_clutch")
    gate = recovery.get("gate_pressure", "none")
    parts = [
        f"persistence role={contribution.get('role', 'unknown')}",
        f"policy={behavior.get('policy_label', lineage.get('dominant_policy', 'unknown'))}",
        f"body={capability.get('body', 'unknown')}",
        f"egg strategy={capability.get('egg_strategy', 'unknown')}",
        f"recovery phase={recovery.get('phase', 'unknown')}",
    ]
    if recent_hatches or recent_clutches:
        parts.append(f"recent hatches/clutches={recent_hatches}/{recent_clutches}")
    if reproduction_log:
        parts.append(f"gate pressure={str(gate).replace('_', ' ')}")
    return "It persisted through " + "; ".join(parts) + "."


def _biology_track(earliest: dict[str, Any] | None, latest: dict[str, Any] | None) -> list[dict[str, str]]:
    if not earliest and not latest:
        return []
    rows = []
    for label, node in (("earliest", earliest), ("current", latest)):
        if node:
            rows.append(
                {
                    "label": label,
                    "node": node_label(node),
                    "signature": str(node.get("biology", {}).get("signature", "-")),
                    "body": str(node.get("capability", {}).get("body", "unknown")),
                    "life_history": str(node.get("capability", {}).get("life_history", "unknown")),
                    "egg_strategy": str(node.get("capability", {}).get("egg_strategy", "unknown")),
                }
            )
    return rows


def _behavior_track(
    earliest: dict[str, Any] | None,
    latest: dict[str, Any] | None,
    instruction_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, node in (("earliest", earliest), ("current", latest)):
        if not node:
            continue
        behavior = node.get("behavior", {})
        rows.append(
            {
                "label": label,
                "node": node_label(node),
                "policy_hash_short": behavior.get("policy_hash_short", "-"),
                "policy_label": behavior.get("policy_label", "unknown"),
                "risk_posture": behavior.get("risk_posture", "unknown"),
                "forage_strategy": behavior.get("forage_strategy", "unknown"),
                "energy_strategy": behavior.get("energy_strategy", "unknown"),
                "taught_skill_count": behavior.get("taught_skill_count", 0),
            }
        )
    inherited = [
        {
            "label": "teaching",
            "node": f"P{row.get('parent_id')} -> {row.get('child_id') or 'egg ' + str(row.get('egg_id'))}",
            "policy_hash_short": str(row.get("offspring_policy_hash", ""))[:8],
            "policy_label": row.get("offspring_policy_label", "unknown"),
            "risk_posture": "inherited",
            "forage_strategy": str(row.get("delivery", "unknown")),
            "energy_strategy": "bounded",
            "taught_skill_count": row.get("skill_count", 0),
        }
        for row in reversed(instruction_log)
        if row.get("event_type") == "offspring_instruction_inheritance"
    ][:3]
    return (rows + inherited)[:6]


def _attempts(
    events: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
    instruction_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in reversed(events[-18:]):
        kind = str(event.get("kind", "event"))
        if kind in {"egg_clutch", "birth", "egg_hatched", "egg_entered_dormancy", "instruction_patch_accepted", "instruction_patch_rejected"}:
            rows.append({"tick": event.get("tick", 0), "kind": kind, "detail": _event_detail(event)})
    for row in reversed(reproduction_log[-12:]):
        reason = str(row.get("reason", "reproduction"))
        if reason not in {"not_mature", "cooldown"}:
            rows.append({"tick": row.get("tick", 0), "kind": reason, "detail": _reproduction_detail(row)})
    for row in reversed(instruction_log[-12:]):
        rows.append(
            {
                "tick": row.get("tick", 0),
                "kind": str(row.get("event_type", "instruction")),
                "detail": row.get("offspring_policy_label") or row.get("patch_reason") or row.get("patch_id") or "",
            }
        )
    rows.sort(key=lambda item: int(item.get("tick", 0) or 0), reverse=True)
    return rows[:10]


def _story_evidence(
    lineage: dict[str, Any],
    latest: dict[str, Any] | None,
    events: list[dict[str, Any]],
    reproduction_log: list[dict[str, Any]],
    instruction_log: list[dict[str, Any]],
    death_causes: Counter[str],
) -> list[str]:
    evidence = [
        f"L{lineage.get('lineage_id')} adults={lineage.get('live_adults', 0)} eggs={lineage.get('viable_eggs', 0)}",
        f"status={lineage.get('status', 'unknown')}",
    ]
    if latest:
        evidence.append(f"node={node_label(latest)} policy={latest.get('behavior', {}).get('policy_hash_short', '-')}")
    if events:
        evidence.append(f"recent_events={', '.join(str(event.get('kind')) for event in events[-3:])}")
    if reproduction_log:
        gates = Counter(str(row.get("reason", "unknown")) for row in reproduction_log)
        evidence.append("top_repro_gate=" + gates.most_common(1)[0][0].replace("_", " "))
    if instruction_log:
        evidence.append(f"instruction_events={len(instruction_log)}")
    if death_causes:
        evidence.append("losses=" + ", ".join(f"{cause}:{count}" for cause, count in death_causes.most_common(2)))
    return evidence[:MAX_EVIDENCE]


def _lineage_death_causes(
    lineage_id: int,
    dead_nodes: list[dict[str, Any]],
    dead_agent_summaries: dict[int, dict[str, Any]],
) -> Counter[str]:
    causes: Counter[str] = Counter()
    node_fish_ids = {int(node.get("fish_id")) for node in dead_nodes if node.get("fish_id") is not None}
    for node in dead_nodes:
        cause = node.get("outcome", {}).get("death_cause")
        if cause:
            causes[str(cause)] += 1
    for summary in dead_agent_summaries.values():
        fish_id = int(summary.get("fish_id", -1) or -1)
        if fish_id in node_fish_ids:
            continue
        if int(summary.get("lineage_id", -1) or -1) == lineage_id and summary.get("death_cause"):
            causes[str(summary["death_cause"])] += 1
    return causes


def _top_death_causes(telemetry: dict[str, Any], dead_agent_summaries: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    causes: Counter[str] = Counter()
    causes.update({str(key): int(value) for key, value in (telemetry.get("deaths_by_cause", {}) or {}).items()})
    if not causes:
        for summary in dead_agent_summaries.values():
            if summary.get("death_cause"):
                causes[str(summary["death_cause"])] += 1
    return [{"cause": cause, "count": count} for cause, count in causes.most_common(8)]


def _latest_active_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not nodes:
        return None
    return sorted(nodes, key=lambda node: (int(node.get("generation", 0) or 0), _node_sort_id(node)))[-1]


def _node_sort_id(node: dict[str, Any]) -> int:
    return int(node.get("fish_id") or node.get("egg_id") or 0)


def _lineage_recovery_contribution(lineage_id: Any, genealogy: dict[str, Any]) -> dict[str, Any]:
    for row in genealogy.get("recovery_contributions", {}).get("lineages", []):
        if row.get("lineage_id") == lineage_id:
            return row
    return {}


def _story_title(lineage: dict[str, Any], latest: dict[str, Any] | None, dashboard: dict[str, Any]) -> str:
    policy = latest.get("behavior", {}).get("policy_label") if latest else lineage.get("dominant_policy")
    phase = dashboard.get("recovery", {}).get("phase", "active")
    return f"Lineage L{lineage.get('lineage_id')} - {str(policy or 'unknown').replace('_', ' ')} during {str(phase).replace('_', ' ')}"


def _story_headline(lineage: dict[str, Any], answers: dict[str, str], dashboard: dict[str, Any]) -> str:
    adults = lineage.get("live_adults", 0)
    eggs = lineage.get("viable_eggs", 0)
    mechanism = dashboard.get("recovery", {}).get("mechanism", "ecological selection")
    return f"L{lineage.get('lineage_id')} has {adults} adults and {eggs} eggs; current evidence points to {mechanism}."


def node_label(node: dict[str, Any]) -> str:
    if node.get("entity") == "egg":
        return f"egg {node.get('egg_id')} L{node.get('lineage_id')}"
    if node.get("state") == "dead":
        return f"dead #{node.get('fish_id')} L{node.get('lineage_id')}"
    return f"fish #{node.get('fish_id')} L{node.get('lineage_id')}"


def _event_detail(event: dict[str, Any]) -> str:
    kind = event.get("kind")
    if kind == "birth":
        return f"child #{event.get('child')} from parent #{event.get('parent')}"
    if kind == "egg_clutch":
        return f"{event.get('eggs')} eggs from parent #{event.get('parent')}"
    if kind == "egg_hatched":
        return f"egg {event.get('egg_id')} hatched as #{event.get('child')}"
    if kind == "egg_entered_dormancy":
        return f"egg {event.get('egg_id')} entered dormancy"
    if kind in {"instruction_patch_accepted", "instruction_patch_rejected"}:
        return str(event.get("skill") or event.get("reason") or "")
    return str(event.get("cause") or event.get("value") or "")


def _reproduction_detail(item: dict[str, Any]) -> str:
    if item.get("egg_count"):
        return f"{item['egg_count']} eggs, cost {item.get('energy_cost', 0)}"
    if item.get("offspring_count"):
        return f"{item['offspring_count']} offspring, cost {item.get('energy_cost', 0)}"
    return f"#{item.get('fish_id')} {item.get('fertility_state', '')}".strip()
