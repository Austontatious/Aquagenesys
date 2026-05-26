# Aquagenesys Bioluminescent Reef Renderer v0.1 Polish

Date: 2026-05-26

## Scope

This pass polishes the existing Canvas reef renderer. It does not change simulation mechanics, ecology, reproduction, morphology truth, behavior, lineage story, recovery logic, skill evidence, `/api/frame`, or `/api/state`.

## Renderer Decision

The reef renderer is now the default because it is stable and visibly better than the classic field renderer. The fallback is still available:

- Default reef renderer: `/`
- Explicit reef renderer: `/?renderer=reef-v0`
- Classic fallback: `/?renderer=classic`
- Legacy fallback alias: `/?renderer=legacy`
- Forced low quality: `/?reefQuality=low`
- Missing-background fallback: `/?reefBg=missing`

## Visual Changes

- Rebuilt `reef-bg.webp` as a richer dark navy/cyan/violet reef background with light shafts, layered silhouettes, and restrained luminous coral/anemone accents.
- Added a cheap foreground reef/anemone layer in Canvas so the tank still reads as an intentional reef even if the image asset fails or the sim is idle.
- Reduced prototype/debug feel by softening field veil speckles and removing the hard grid fallback.
- Improved organism readability with stronger eye marks, side fins, lateral glow, head/mouth cues, armor/spine accents, appendage tip glow, and more controlled halos.
- Tuned depth and LOD: foreground organisms remain sharper and richer; far organisms are dimmer and simpler.
- Fixed narrow/mobile renderer backing size so the canvas no longer leaves a transparent right-side band.
- Added cache-busting query suffixes on static scripts so the polished renderer loads reliably after deployment.

## Screenshot Artifacts

- Before reef desktop: `reports/visual/reef_renderer_v0_polish_2026-05-26/before/desktop_reef_v0_before.png`
- Before selected: `reports/visual/reef_renderer_v0_polish_2026-05-26/before/selected_reef_v0_before.png`
- Before mobile: `reports/visual/reef_renderer_v0_polish_2026-05-26/before/mobile_reef_v0_before.png`
- Classic fallback: `reports/visual/reef_renderer_v0_polish_2026-05-26/after/fallback.png`
- After desktop: `reports/visual/reef_renderer_v0_polish_2026-05-26/after/desktop.png`
- After selected: `reports/visual/reef_renderer_v0_polish_2026-05-26/after/selected.png`
- After mobile: `reports/visual/reef_renderer_v0_polish_2026-05-26/after/mobile.png`
- Idle/loading: `reports/visual/reef_renderer_v0_polish_2026-05-26/after/idle.png`

## Visual Self-Review

- The tank now reads as a dark bioluminescent reef rather than a placeholder grid/prototype.
- It is materially better than the previous reef-v0 screenshot: richer background, stronger reef composition, fewer debug-like dots, more controlled glow, and better organism contrast.
- It is materially better than the classic renderer for the intended observatory mood.
- Idle/loading state is nonblank and intentional: reef background, ambient particles, and reef accents render before ecology frames arrive.
- Organisms remain readable against the reef background.
- Foreground organisms are visibly closer and more detailed; far organisms are smaller/dimmer.
- Glow is present and tasteful, though creature art remains deliberately simple Canvas primitives.
- Mobile/narrow viewport avoids horizontal overflow and no longer has the transparent right-side canvas band.
- Selected organism UI remains coherent; hover/select/ctrl-click compare continue to work.

## Browser Smoke And Performance

Runtime: `http://127.0.0.1:8776/`, PID `579998`, seed `4101`, local reset before final smoke.

- Desktop reef default: 38 organisms visible; `quality=high`; average render cost `2.44ms`, p95 `2.6ms`; cache warm `22705` hits / `49` misses; no console errors; no failed requests; overflow `0`.
- Desktop screenshot capture: 38 organisms visible; depth tiers included `background`, `midwater`, and `foreground`; selected organism panel updated.
- Mobile `390x844`: 38 organisms visible; `quality=high`; average render cost `2.15ms`, p95 `2.3ms`; overflow `0`; backing canvas fixed to `390x523`.
- Forced low quality: 38 organisms visible; `quality=low`; average render cost `1.57ms`, p95 `1.8ms`; overflow `0`.
- Missing-background fallback: background asset disabled; fallback remained nonblank; `background_failed=true`; console errors `0`.
- Idle/loading smoke: API fetches held pending; no ecology frame known; canvas nonblank; `background_ready=true`; console errors `0`.
- Classic fallback: `?renderer=classic` kept old renderer active and did not instantiate `window.aquagenesysReefRenderer`.

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

- Creature art remains Canvas primitive art, not final concept-art-level fauna.
- The reef background is still procedural placeholder art, though substantially more polished.
- Reef depth remains visual-only and client-side.
- The dashboard/sidebar layout was intentionally not redesigned toward the concept art shell in this pass.

## Recommended Next Step

Add a selected-organism portrait renderer using the same morphology descriptor so the sidebar can show a larger, prettier organism view without affecting tank FPS.
