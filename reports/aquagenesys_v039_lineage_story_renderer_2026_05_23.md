# Aquagenesys v0.3.9 Lineage Story Renderer

## Initial State

- Branch: `main`
- Starting HEAD: `1d1f5e0`
- Working tree at start: clean
- Runtime before work: `aquagenesys-v038` on port `8770`, PID `2728757`
- Baseline schemas: `/api/frame aquagenesys.frame.v3`, `/api/state aquagenesys.state.v8`, dashboard `aquagenesys.dashboard.v2`, genealogy `aquagenesys.genealogy.v1`

## Implementation

v0.3.9 adds `aquagenesys.simulation.lineage_story.build_lineage_story`, a deterministic renderer that turns existing genealogy and observability data into bounded story cards. The new `/api/state.lineage_story` payload uses schema `aquagenesys.lineage_story.v1`; `/api/state` moved to `aquagenesys.state.v9`; `/api/frame` remains unchanged.

The renderer answers:

- Who survived?
- What did they inherit?
- What changed?
- What did they try?
- What killed the others?
- Why did this lineage persist?

Evidence sources:

- live, egg, dormant egg, and sampled dead genealogy nodes
- recovery dashboard phase/mechanism/gate pressure
- recent reproduction and hatch events
- reproduction gate logs
- instruction inheritance and patch records
- compact dead-agent summaries and death causes

## UI

The observatory now includes a Lineage Story panel below the genealogy explorer. It follows the selected or hovered fish lineage when available, otherwise the primary surviving lineage. It renders six question cards plus compact biology, behavior, attempt, and loss tracks.

## API Contract

- `/api/state`: `aquagenesys.state.v9`
- `/api/state.lineage_story`: `aquagenesys.lineage_story.v1`
- `/api/dashboard`: unchanged inside state as `aquagenesys.dashboard.v2`
- `/api/genealogy`: unchanged inside state as `aquagenesys.genealogy.v1`
- `/api/frame`: unchanged as `aquagenesys.frame.v3`; no story payload is included

## Safety

The story renderer is deterministic and model-free. It does not tune recovery, add rescue spawning, alter reproduction, alter behavior selection, or hide extinction. It summarizes bounded evidence already produced by the simulation.

## Validation Status

Targeted validation during implementation:

```text
python3 -m pytest -q tests/test_lineage_story_renderer.py tests/test_genealogy_explorer.py tests/test_observatory_dashboard.py
# 9 passed

node --check aquagenesys/web/static/app.js
# pass

python3 -m py_compile aquagenesys/simulation/lineage_story.py aquagenesys/simulation/engine.py
# pass
```

Full validation is recorded in the final task response after the v0.3.9 commit.

Full validation completed:

```text
python3 -m pytest -q tests
# 54 passed

python3 evals/runner.py --check
# pass

python3 evals/runner.py
# pass

python3 evals/recovery_assays.py --json
# pass; recovery remains possible, no mechanics tuning recommended

make lint
# pass

python3 -m pytest -q tests/test_codex_standards.py --noconftest
# 9 passed

node --check aquagenesys/web/static/app.js
# pass
```

Browser smoke on `127.0.0.1:8773` loaded `Aquagenesys v0.3.9`, showed the Lineage Story region, rendered the canvas/observatory, and had no console warnings or errors before the temporary server was stopped. A 390px mobile viewport snapshot showed no horizontal overflow.

## Known Limitations

- Story depth is bounded by current in-memory genealogy and sampled dead summaries.
- It is not a full graph database or complete species tree.
- Deep ancestor relationship inference remains shallow.
- The narrative is intentionally deterministic and compact, not model-written prose.

## Recommended Next Patch

v0.4.0 should focus on public demo hardening and portfolio narrative: launch/runbook polish, durable demo scenarios, screenshots/video capture, and a concise explanation of the recursive-agent architecture.
