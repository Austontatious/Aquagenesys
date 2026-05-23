# ADR 0013: v0.3.6 Ecology Observatory UX

## Problem

By v0.3.5, Aquagenesys had real simulation depth: procedural phenotype, locomotion smoothing, life-history reproduction, egg banks, parthenogenesis, bounded instruction inheritance, teaching telemetry, and archive traces. The viewer still exposed much of that depth as long raw lists in the right sidebar. The puddle remained visually alive, but the UI made it hard to connect visible fish to lineage, behavior, reproduction, and teaching dynamics.

## Options Considered

1. Keep the existing sidebar and add more sections.
2. Replace the viewer with a graph-first lineage UI.
3. Move ecosystem observability below the puddle, keep the canvas primary, and narrow the sidebar to focused fish inspection.

## Decision

v0.3.6 adopts an ecology observatory layout:

- top/center: puddle canvas remains primary
- right sidebar: controls, hovered/selected fish inspector, and optional two-fish comparison
- below puddle: narrator, lifecycle metrics, lineage/policy/teaching observatory, timeline, and diagnostics

The backend adds a structured `/api/state` dashboard payload with schema `aquagenesys.dashboard.v1`. `/api/frame` remains lightweight and does not include the dashboard.

## Rationale

The viewer needs to make existing mechanics legible without adding new biology. Sidebar-only telemetry does not scale because ecosystem summaries, event timelines, and lineage/policy trends need horizontal and vertical space. A below-puddle observatory uses otherwise wasted page space while keeping the right sidebar tied to the fish under inspection.

The narrator is rule-based and grounded in state fields. It summarizes adults, eggs, dormant/viable egg bank, lineage diversity, dominant policy family, reproduction gate pressure, teaching activity, and recent events. It does not call a model and does not invent unsupported ecological story.

Compare mode matters because Aquagenesys is now partly about inherited behavior. Seeing two fish side by side makes policy drift, lineage relation, phenotype differences, and strategy tradeoffs visible without reading JSONL archives.

## Consequences

- `/api/state` moves to `aquagenesys.state.v6`.
- `/api/state` includes `dashboard.schema == aquagenesys.dashboard.v1`.
- `/api/frame` stays at `aquagenesys.frame.v3`.
- The sidebar is no longer a raw telemetry dump.
- Event, gate-failure, model, lineage, policy, and teaching observability remain available below the puddle.
- The UI now supports hover preview, click focus, and ctrl/cmd-click compare.

## Explicit Deferrals

- Full lineage tree / genealogy graph.
- Interactive policy survival charts beyond compact summaries.
- Model-generated narrator.
- Public demo packaging.
- Major new simulation biology.
