# 0004 Stage 4 Aquatic Ecosystem And Local Web UI

## Problem

Aquagenesys needed a fourth stage for larger free-moving aquatic life and a preferred local browser interface without replacing the existing Python simulation core or pygame UI.

## Options Considered

- Extend `World` with another explicit environment stage and lightweight aquatic agents.
- Build a separate web-only simulator model.
- Move rendering to a richer frontend/game engine now.

## Decision

Stage 4 is implemented inside the existing Python `World` as `aquatic_ecosystem`. Aquatic organisms are promoted from mature Stage 3 organisms by configurable thresholds and remain traceable to their origin organism and lineage. The local web UI is a FastAPI app serving a single canvas frontend and polling `/api/state` against the same `World` object.

## Rationale

Keeping Stage 4 in the core preserves the existing headless, pygame, metrics, history, and test paths. A polling FastAPI interface is simpler than adding a realtime frontend stack and is enough for local visualization/control. Rule-based aquatic movement, feeding, predation, reproduction, and death keep the behavior inspectable and deterministic enough for tests.

## Consequences

- Stage 4 coexists with cells, colonies, and Stage 3 organisms.
- Stage 4 can regress to Stage 3 when aquatic reproduction/support fails.
- Metrics and exports now include aquatic population, lineage counts, aggression/defense/speed/body-size averages, predation, reproduction, death causes, trophic pressure, biodiversity, and dominant aquatic lineage.
- The web app adds FastAPI/Uvicorn dependencies and a local browser path: `python -m dirty_puddle.web.app --host 127.0.0.1 --port 8765`.

## Explicit Deferrals

- No neural controllers or complex brains.
- No multiplayer/network exposure; local host remains the default.
- No Parquet export or web persistence yet.
- No Godot/webgl frontend yet; canvas is enough for the current sprint.
