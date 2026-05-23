# Aquagenesys v0.3.8 Lineage / Policy Genealogy Explorer

## Initial State

- Starting HEAD: `dcefd81` (`test: add recovery assays and observability`)
- Branch: `main`
- v0.3.7 was already committed before this work started.
- Working tree was clean after the v0.3.7 commit.

## Implementation

v0.3.8 adds a bounded genealogy explorer:

- `/api/state` moved to `aquagenesys.state.v8`.
- `/api/state.genealogy` uses `aquagenesys.genealogy.v1`.
- `/api/frame` remains `aquagenesys.frame.v3` and does not include genealogy.
- Genealogy nodes cover live adults, viable eggs, dormant eggs, and sampled compact dead ancestors.
- Nodes include parent ids, generation, lineage, biological genome hash, phenotype hash, instruction policy hash, policy label, taught-skill count, patch counts, lifecycle state, and recovery role.
- Dead ancestors retain compact summaries only, not full runtime memory.
- The below-puddle observatory now includes biology track, behavior track, selected-lineage path, policy inheritance trail, and recovery role cards.
- Compare mode now surfaces parent/child, sibling, matching biology, and matching policy relationship hints when the compact genealogy state supports them.

## Bounded Contract

The endpoint caps nodes and edges and samples dead ancestors. It avoids raw prompt logs, tool access, unbounded memory, full runtime programs, and full genome dumps.

## Validation

- `python3 -m pytest -q tests`: 51 passed
- `python3 evals/runner.py --check`: pass
- `python3 evals/runner.py`: pass
- `python3 evals/recovery_assays.py --json`: pass, mechanics tuning not recommended
- `make lint`: pass
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: 9 passed
- `node --check aquagenesys/web/static/app.js`: pass
- Playwright smoke: v0.3.8 loaded, genealogy explorer visible, recovery evidence visible, no console warnings/errors, mobile viewport had no horizontal overflow in the accessibility snapshot.

## Known Limitations

- The genealogy explorer is a selected-lineage/card view, not a full interactive graph.
- Dead ancestor history is sampled and compact by design.
- Shared-ancestor/cousin detection is still shallow; direct parent/child and sibling relationships are covered.

## Recommended Next Patch

v0.3.9 should add a richer selected-lineage drilldown or a compact graph/path renderer after observing how the bounded genealogy payload behaves in live runs.
