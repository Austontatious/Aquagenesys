# Aquagenesys v0.3.4 Life-History Egg Bank Report

## Initial State

- Branch: `main`
- Starting HEAD: `d2d2783 Add Aquagenesys v0.3.3 biomechanical locomotion`
- Remote baseline: `origin/main` at `ba8072c Initial Aquagenesys v0.3.1`
- Commit boundary: v0.3.2 is committed as `197688c`; v0.3.3 is committed as `d2d2783`; no uncommitted work was present before v0.3.4.
- Runtime before work: tmux session `aquagenesys-v033`; port `127.0.0.1:8770` served v0.3.3 with `/api/frame` responding and population `0`.

## Reproduction Audit Findings

- Before v0.3.4, reproduction spawned one live fish immediately in `_maybe_reproduce`.
- No egg, embryo, dormant egg, or propagule entity existed.
- Parent death could not preserve offspring because no independent egg records existed.
- Parent IDs and generation already existed on live children.
- Lineage and species were tracked; lineage split updated species ID through genome mutation.
- Reproduction gates were energy, health, reproductive drive, local reproduction score, crowding, and RNG.
- Final healthy singleton had no modeled recovery path other than winning direct reproduction RNG before age death.
- Age death used a body-size threshold plus stochastic death chance.
- Reproduction failure reasons were not archived or exposed as structured gate telemetry.
- Archive JSONL files were append-only and could mix multiple runs without `run_id`.

## Implemented v0.3.4

- Added `LifeHistoryProfile` in `aquagenesys/agents/life_history.py`.
- Added heritable genome traits: dormancy bias, egg viability horizon, parthenogenesis alleles, parthenogenesis bias, and mutation load.
- Added maturity, fertility, senescence, lifespan, reproduction interval, clutch size, offspring investment, brood strategy, egg strategy, dormancy, and parthenogenesis payloads.
- Replaced single-offspring reproduction with energy-costed brood/clutch reproduction.
- Added `EggEntity` in `aquagenesys/simulation/egg.py`.
- Eggs persist independently of adults, hatch under suitable local chemistry, enter dormancy, decay, or die under hostile conditions.
- Added dormant biosphere state: adult population `0` plus viable eggs is `biosphere_state=dormant`, not true extinction.
- True extinction now requires no adults and no viable eggs.
- Added rare recessive-ish parthenogenesis behavior. Zero-allele singletons cannot reproduce; allele-bearing isolated mature fish can attempt bounded clonal egg deposition with viability/mutation tradeoffs.
- Strengthened detritus/nutrient rebound using the existing decomposition field as detritus.
- Added reproduction gate telemetry and lifecycle events.
- Added `run_id` to state, memory, and lifecycle archive records.
- Added current-run segmentation helper `segment_jsonl_runs`.

## API / UI

- `/api/state` schema is now `aquagenesys.state.v4`.
- `/api/frame` schema is now `aquagenesys.frame.v2`.
- `/api/frame` remains lightweight and includes compact egg records and lifecycle aggregate metrics.
- Viewer title is `Aquagenesys v0.3.4`.
- Viewer metrics now show adults, eggs, viable eggs, dormant eggs, births, hatched eggs, lineages, reproduction gate failures, and recent reproduction events.
- Fish inspector now shows maturity/fertility state, clutch size, reproduction cooldown, last reproduction gate, dormancy bias, and parthenogenesis alleles.
- Eggs render as subtle substrate specks/clutches.

## Validation

- `python3 -m pytest -q tests`: 35 passed.
- `python3 evals/runner.py --check`: passed.
- `python3 evals/runner.py`: passed.
- `make lint`: passed.
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: 9 passed.
- `node --check aquagenesys/web/static/app.js`: passed.
- Browser smoke on `http://127.0.0.1:8771`: v0.3.4 loaded, canvas nonblank, lifecycle metrics visible, fish inspector click worked, no JavaScript console errors, and mobile viewport had no horizontal overflow.

## Collapse / Eval Notes

- The v0.3.3 collapse was lifecycle attrition: adults went extinct despite healthy water.
- v0.3.4 adds lifecycle events with `run_id`, active egg counts, dormant state, gate reasons, and hatch/recovery counters so future collapse analysis can distinguish poisoned puddle, starvation, lifecycle attrition, reproduction gate failure, dormant egg bank, true extinction, and archive contamination.
- Deterministic smoke confirmed egg deposition and hatching occur in a short no-deliberation run without direct rescue spawning.

## Known Limitations

- Mate compatibility is still heuristic and metabolism-based, not a full sexual genetics model.
- Eggs model dormancy/viability but not detailed embryology.
- Parthenogenesis tradeoffs are represented through viability and mutation load, not a full immune/diversity system.
- The viewer shows aggregate lineage counts, not a full lineage tree.
- Existing live process on `8770` still serves the pre-work v0.3.3 session. A separate v0.3.4 smoke server is running in tmux session `aquagenesys-v034` on `8771`.

## v0.3.5 Roadmap

Next patch should add bounded agent instruction inheritance and offspring teaching. Parent agents may influence offspring behavior priors under system validation and mutation, but they should not edit runtime code. Morphology, energy, and environment must still decide whether a taught behavior is survivable.

## Recommended Next Patch

Run a longer headless stability sweep across multiple seeds, then tune life-history constants with report artifacts rather than eyeballing one live viewer run.
