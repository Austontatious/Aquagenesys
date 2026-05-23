# ADR 0014: v0.3.7 Recovery Assays and Observability

## Status

Accepted.

## Context

The v0.3.4 egg bank and v0.3.6 observatory made recovery visible in live runs, but the project still depended too much on visual inspection. A prior run appeared to be collapsing, then recovered after continued runtime and a hard refresh. That meant the correct next step was measurement and explanation, not blindly loosening reproductive gates.

## Decision

v0.3.7 adds deterministic seeded recovery assays and a recovery evidence section in the observatory. The assays cover bottleneck recovery, egg-bank resilience, reproduction gates, density and crowding sanity, resource rebound, behavior policy payoff, and optional AI deliberation.

The dashboard schema moves to `aquagenesys.dashboard.v2` and `/api/state` moves to `aquagenesys.state.v7`. `/api/frame` remains `aquagenesys.frame.v3` and does not carry dashboard payloads.

The public viewer label changes from "Lexi deliberation" to "AI deliberation" because the UI should explain the capability without requiring knowledge of the local model name. The backend can still use Lexi/Qwen-compatible endpoints internally.

## Recovery Model

Recovery remains ecological rather than god-mode:

```text
population pressure changes
-> egg bank or survivor traits preserve possible lineage continuity
-> resource rebound may open a recovery window
-> behavior policy affects whether organisms exploit that window
-> extinction remains possible when adults and viable eggs are gone
```

The assays explicitly check that debug founder reseeding is not used, egg-bank recovery does not create instant adults, and AI deliberation is optional.

## Tuning Policy

No mechanics were tuned in this pass. The seeded assays demonstrated recoverable bottleneck and egg-bank paths, explainable gate failures, sane local-vs-global crowding behavior, resource rebound opportunity, and measurable behavior-policy effects. Future tuning should be driven by assay failures, not by a single dramatic screenshot.

## Consequences

- Recovery and extinction are now explainable in reports and UI.
- The narrator can state recovery phase and evidence using deterministic templates.
- The viewer exposes recovery phase, mechanism, egg-bank contribution, resource rebound, crowding state, gate pressure, and dominant policy.
- The assay output gives a machine-readable record for future tuning passes.
- This pass still does not build the full lineage/policy genealogy explorer; that is reserved for v0.3.8.
