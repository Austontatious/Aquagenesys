# Aquagenesys v0.3.6 Ecology Observatory UX Report

## Initial State

- Branch: `main`
- Starting HEAD: `ec0a144 feat: add bounded offspring instruction inheritance`
- Working tree: clean at task start
- Remote alignment: `main...origin/main`
- Runtime at start: `aquagenesys-v035` on `0.0.0.0:8770`, PID `310877`
- API at start: `/api/frame` `aquagenesys.frame.v3`, `/api/state` `aquagenesys.state.v5`
- Alternate viewers: none observed on `8771` or `8772`

## UX Problems Addressed

The v0.3.5 sidebar had become a raw telemetry dump. Long lists for decisions, events, reproduction, gates, instruction events, patch rejections, species, and deaths were stacked beside the puddle, while the area below the canvas was unused.

## Implemented v0.3.6

- Updated package/UI/docs/evals to Aquagenesys `v0.3.6`.
- Added `aquagenesys/simulation/dashboard.py` with `aquagenesys.dashboard.v1`.
- Moved `/api/state` to `aquagenesys.state.v6`.
- Kept `/api/frame` at `aquagenesys.frame.v3` and left dashboard payload out of the fast path.
- Reworked the viewer layout:
  - puddle remains primary
  - right sidebar is fish-focused
  - below-puddle observatory now carries ecosystem summaries
- Added deterministic ecology narrator grounded in telemetry, lineage/policy summaries, reproduction pressure, egg-bank state, and recent events.
- Added lifecycle dashboard cards, interpretation labels, and small local sparklines.
- Added lineage, policy, teaching, timeline, gate-failure, patch-rejection, and model diagnostics panels below the puddle.
- Added ctrl/cmd-click fish comparison with relationship summaries.
- Added timeline click-to-focus behavior for live fish references.

## Sidebar Redesign

The sidebar now contains controls, a focused fish inspector, and optional compare mode. Hovering a fish previews it. Clicking pins focus. Ctrl/cmd-clicking another fish compares policy, lifecycle, phenotype/body, current state, action, and relationship signals such as same lineage, shared policy, feeding role, and proximity.

## Dashboard And Narrator

The dashboard object is generated server-side so the frontend does not reverse-engineer raw logs. Narrator text is deterministic and grounded; it does not call Lexi or any external model.

Dashboard sections:

- `population`
- `lineages`
- `policies`
- `teaching`
- `events`
- `diagnostics`
- `focus_hints`

## Validation

Validation was run after implementation:

- `python3 -m pytest -q tests` -> `47 passed`
- `python3 evals/runner.py --check` -> pass, 6 case files
- `python3 evals/runner.py` -> pass
- `make lint` -> pass
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest` -> `9 passed`
- `node --check aquagenesys/web/static/app.js` -> pass
- Browser smoke against `http://127.0.0.1:8770/` -> v0.3.6 loaded, canvas nonblank, narrator/dashboard visible, inspector works, ctrl-click compare works, no JavaScript console errors, mobile no horizontal overflow

## Known Limitations

- No full genealogy tree yet.
- The narrator is intentionally template/rule based and compact.
- Timeline filtering is not interactive yet.
- Compare mode uses available state and proximity hints; it does not infer hidden social contracts.

## Recommended Next Patch

v0.3.7 should add a deeper lineage/policy genealogy explorer: select a lineage, show ancestor/descendant policy hashes, taught skill survival, hatch/death outcomes, and compact archive trace links.
