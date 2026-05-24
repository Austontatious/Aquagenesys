# Aquagenesys Bioluminescent Reef Renderer v0.1

Date: 2026-05-24

## Scope

This pass adds a Canvas-first reef renderer prototype behind a URL flag. It does not change simulation mechanics, ecology, morphology truth, behavior, lineage story, or `/api/frame`.

## Files Changed

- `aquagenesys/web/static/renderer_canvas.js`
- `aquagenesys/web/static/app.js`
- `aquagenesys/web/static/index.html`
- `aquagenesys/web/static/assets/reef-bg.webp`
- `aquagenesys/web/static/assets/README.md`
- `tests/test_reef_renderer_static.py`

## Renderer Flag

- Default: existing canvas renderer remains active.
- Reef prototype: `http://127.0.0.1:8776/?renderer=reef-v0`
- Forced low quality: `?renderer=reef-v0&reefQuality=low`
- Background fallback smoke: `?renderer=reef-v0&reefBg=missing`
- Cache disable escape hatch: `?renderer=reef-v0&reefCache=off`
- Adaptive quality disable escape hatch: `?renderer=reef-v0&reefAdaptive=off`

## Architecture

- New bounded renderer module: `window.AquagenesysReefRenderer.init(canvas, options)`.
- `app.js` keeps ownership of frame polling, state polling, hover, select, ctrl/cmd-click compare, and sidebar updates.
- The reef renderer owns drawing, renderer-local hit testing, visual depth, simple LOD, organism visual cache, adaptive quality stats, and ambient particles.
- `renderer_canvas.js` exposes `resize`, `updateFrame`, `updateEnvironment`, `render`, `hitTest`, `getRenderedFish`, `setSelection`, `getPerfStats`, and `destroy`.

## Visual Design

- Adds a small procedural bioluminescent reef background asset at `/static/assets/reef-bg.webp`.
- Falls back to a dark gradient/grid when the image source is missing or disabled.
- Adds deterministic client-side visual depth from fish identity plus y-position.
- Renders background organisms first and foreground organisms last.
- Uses depth only as camera/proximity detail, not health, lineage, generation, intelligence, or ecological importance.
- Uses existing `fish.phenotype.morphology` hints for body scale, head/mouth marks, appendages, armor/spines, chemical markers, sensory frills, and eye marks.

## Performance Guardrails

- Caps DPR by quality tier.
- Tracks rAF cadence and render frame cost.
- Provides quality tiers: `high`, `medium`, `low`, `minimum`.
- Reduces ambient particles, appendage/frill detail, background detail, and DPR cap as quality drops.
- Caches static organism body canvases by render signature, with OffscreenCanvas when available and regular canvas fallback.

## Browser Smoke

Runtime used: `http://127.0.0.1:8776/`, seed `4101`, PID `3479112`.

- Default renderer, flag absent: canvas nonblank, `window.aquagenesysReefRenderer` absent, click select worked, horizontal overflow `0`, console errors `0`.
- Reef renderer: canvas nonblank, background loaded, 38 organisms visible, depth tiers observed (`background`, `midwater`, `foreground`), click select worked, ctrl-click compare worked, console errors `0`.
- Reef desktop-ish measurement: `quality=high`, render cost about `2.12 ms` average and `2.70 ms` p95, cache warm (`3449` hits / `39` misses), headless rAF cadence about `15 fps`.
- Forced low quality: `quality=low`, render cost about `0.83 ms` average and `1.80 ms` p95, 38 organisms visible, horizontal overflow `0`.
- Missing-background fallback: `background_failed=true`, canvas nonblank, horizontal overflow `0`, console errors `0`.
- Mobile/narrow viewport `390x844`: canvas nonblank, click select worked, horizontal overflow `0`, `quality=high`, render cost about `1.45 ms` average and `1.70 ms` p95, headless rAF cadence about `53 fps`.

## Validation

- `python3 -m pytest -q tests`: `74 passed`
- `python3 evals/runner.py --check`: passed
- `python3 evals/runner.py`: passed
- `make lint`: passed
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: `9 passed`
- `node --check aquagenesys/web/static/app.js`: passed
- `node --check aquagenesys/web/static/renderer_canvas.js`: passed
- `python3 evals/recovery_assays.py --json`: passed; `recovery_rate=1.0`, `no_god_mode_reseed=true`

## Known Limitations

- This is still Canvas 2D, not PixiJS/WebGL.
- The background is procedural placeholder art, not final reef art.
- Organism art is intentionally simple and built from cheap primitives.
- Depth is deterministic client-side presentation only; simulation truth has no z/depth.
- Adaptive quality currently responds to renderer cost and exposes rAF cadence, but it is not a full device capability profiler.
- The selected-organism portrait prototype was intentionally skipped to keep this pass bounded.

## Recommended Next Step

Promote the renderer boundary into a more explicit module contract, then add a small selected-organism portrait using the same morphology descriptor without touching tank FPS.
