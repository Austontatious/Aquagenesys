# Aquagenesys Procedural Creature Portrait Grammar v0.2

Date: 2026-05-26

## Scope

This pass adds a selected-organism portrait renderer for the existing static Canvas frontend. It does not change simulation mechanics, ecology, reproduction, morphology truth, behavior, lineage story, recovery logic, skill evidence, `/api/frame`, or `/api/state`.

## Integration

- Added `aquagenesys/web/static/creature_portrait.js` as a no-build browser module.
- Added a selected organism portrait canvas to the focused-fish sidebar.
- Loaded the portrait module between `renderer_canvas.js` and `app.js`.
- `app.js` initializes `window.aquagenesysCreaturePortrait` when the module is available.
- Portrait rendering is signature-gated and layout-gated, so `updateInspector()` may run every frame but the portrait does not redraw every frame.
- Classic renderer fallback remains available through `/?renderer=classic`.

## Creature Grammar

The portrait path maps existing fish fields into a deterministic descriptor:

- seed from fish id, species, lineage, generation, and morphology hash
- phenotype/morphology proportions
- head and mouth scale
- tail/fin style
- appendage, frill, barbel, armor, and spine signals
- translucency, iridescence, chemical marker, palette, and surface pattern
- subtle condition overlays from health, energy, stress, and hunger

Implemented visual archetypes:

- `reef_fish`
- `ribbon_swimmer`
- `jelly_floater`
- `armored_filter_feeder`
- `frilled_symbiont`
- `schooling_minnow`
- `eel_glider`
- `spiral_drifter`
- `spined_crawler`
- `translucent_exotic`

These are visual archetypes selected from morphology and affordance hints, not species classes or behavior drivers.

## Visual Artifacts

- Desktop no selection: `reports/visual/creature_portrait_v02_2026-05-26/desktop_no_selection.png`
- Desktop selected portrait: `reports/visual/creature_portrait_v02_2026-05-26/desktop_selected.png`
- Mobile selected portrait: `reports/visual/creature_portrait_v02_2026-05-26/mobile_selected.png`
- Classic fallback: `reports/visual/creature_portrait_v02_2026-05-26/classic_fallback.png`
- Low-quality compare smoke: `reports/visual/creature_portrait_v02_2026-05-26/low_quality_compare.png`
- Synthetic archetype sample grid: `reports/visual/creature_portrait_v02_2026-05-26/archetype_grid.png`

## Visual Self-Review

- The selected portrait reads as a larger, prettier organism view in the sidebar.
- It is more detailed than the tank organism while staying consistent with the dark bioluminescent reef look.
- The archetype sample grid shows variety beyond jelly/floater forms.
- Portrait organisms remain readable against the dark reef-panel background.
- The sidebar remains usable and the selected fish stats are intact.
- Mobile layout remains narrow but coherent, with zero horizontal overflow in smoke checks.
- Creature art is still procedural Canvas art, not final concept-art-level fauna.

## Browser Smoke And Performance

Runtime: `http://127.0.0.1:8776/`.

- Desktop reef default after reset: 38 visible organisms; `quality=high`; tank average render cost `2.58ms`, p95 `3.7ms`; portrait render `1.2ms`; no per-frame portrait redraw; overflow `0`.
- Desktop selected state: portrait visible; example selected organism rendered as `ribbon_swimmer`.
- Mobile `390x844`: portrait visible; tank average render cost `2.19ms`, p95 `3.0ms`; portrait render `0.5ms`; overflow `0`.
- Forced low quality: `quality=low`; tank average render cost `1.21ms`, p95 `1.7ms`; ctrl-click compare remained visible; overflow `0`.
- Classic fallback: `window.aquagenesysReefRenderer` absent, canvas nonblank, portrait module still loaded safely.
- Console errors: `0`.

## Validation

- `node --check aquagenesys/web/static/app.js`: passed
- `node --check aquagenesys/web/static/renderer_canvas.js`: passed
- `node --check aquagenesys/web/static/creature_portrait.js`: passed
- `python3 -m pytest -q tests/test_reef_renderer_static.py`: `6 passed`
- `python3 -m pytest -q tests`: `77 passed`
- `python3 evals/runner.py --check`: passed
- `python3 evals/runner.py`: passed
- `make lint`: passed
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: `9 passed`
- `python3 evals/recovery_assays.py --json`: passed; `recovery_rate=1.0`, `no_god_mode_reseed=true`

## Known Limitations

- Portraits are static in this pass.
- The grammar is intentionally simple Canvas geometry, not final creature illustration.
- The portrait classifier uses available render/morphology hints only; no new backend depth, behavior, or species data was added.
- Sidebar shell layout is unchanged, so mobile remains long-form rather than redesigned.

## Recommended Next Step

Tune the main tank organism grammar toward the portrait grammar so selected organisms and in-tank silhouettes feel more closely related without raising tank render cost.
