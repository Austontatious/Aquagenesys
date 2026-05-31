# ADR 0019: v0.4.2 Evidence-Governed Skill Inheritance

Status: Accepted for v0.4.2.

## Context

v0.4.1 recorded taught-skill use and descendant outcomes as observational evidence, but offspring could still receive a taught skill because the parent carried it or because a new patch was accepted. That made the recursive-agent metaphor weaker: hints could persist by declaration rather than by lineage-local support.

## Decision

v0.4.2 routes taught-skill inheritance through a deterministic evidence gate. Each candidate skill now receives a governance decision with:

- status: `inherited`, `eligible`, `suppressed_insufficient_evidence`, `suppressed_stale_evidence`, `suppressed_negative_outcome`, `suppressed_slot_limit`, or `observed_only`
- confidence
- evidence count, positive count, negative count, unclear count, reproduction-after-use count
- source parent and lineage
- reason code and plain-English reason

The gate requires at least two recent positive lineage-local observations and minimum confidence before a skill can be inherited. Stale, expired, weak, or negative evidence suppresses the hint. Newly accepted patches remain visible as accepted teaching events, but they are `observed_only` until use/outcome evidence supports inheritance.

## Consequences

- `/api/state` moves to `aquagenesys.state.v13`.
- `telemetry.skill_evidence` moves to `aquagenesys.skill_evidence.v2`.
- `lineage_story` moves to `aquagenesys.lineage_story.v5`.
- Selected fish and full egg payloads include `skill_inheritance` decisions.
- `/api/frame` remains compact and does not include skill governance payloads.
- Lineage stories may say a hint was preserved after supporting evidence or suppressed because evidence was weak/stale/negative. They avoid causal claims.

This does not prove that a skill caused survival or reproduction. It makes inheritance accountable to deterministic, inspectable evidence.
