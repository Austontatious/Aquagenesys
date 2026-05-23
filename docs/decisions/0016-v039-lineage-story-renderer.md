# ADR 0016: v0.3.9 Lineage Story Renderer

## Status

Accepted.

## Context

v0.3.8 made lineage and policy genealogy available, but the viewer still expected users to connect many small facts themselves. The recursive-agent story needs a more direct answer to: who survived, what they inherited, what changed, what they tried, what killed others, and why this lineage persisted.

## Decision

v0.3.9 adds a deterministic lineage story renderer under `/api/state.lineage_story` with schema `aquagenesys.lineage_story.v1`. `/api/state` moves to `aquagenesys.state.v9`; `/api/frame` remains `aquagenesys.frame.v3` and does not include story payloads.

The renderer is rule-based and grounded in existing evidence:

- bounded genealogy nodes for live adults, eggs, dormant eggs, and sampled dead ancestors
- recovery dashboard phase/mechanism/gate pressure
- reproduction events and gate logs
- instruction inheritance and patch records
- compact dead-agent summaries and death causes

The UI adds a below-puddle Lineage Story panel. It picks the focused fish lineage when available, otherwise the primary surviving lineage, and renders six evidence-backed cards:

- Who survived?
- What did they inherit?
- What changed?
- What did they try?
- What killed the others?
- Why did this lineage persist?

## Safety

The story renderer does not call a model and does not produce freeform fiction. It is a deterministic state summarizer. It does not alter simulation mechanics, recovery odds, model deliberation, reproduction gates, or fish behavior. It carries bounded text and compact evidence only in `/api/state`.

## Consequences

The viewer now has a narrative layer that supports the portfolio story without hiding ecological failure. The story can say a lineage is dormant, bottlenecked, recovering, or extinct based on state evidence. It also reinforces the project thesis:

```text
Instruction changes intent. Biology controls capability. Ecology decides what persists.
```

## Limits

The renderer only sees bounded in-memory genealogy and sampled dead summaries, not a full graph database. Deep shared-ancestor reasoning, full species-tree reconstruction, and long-run historical narratives remain future work.
