# ADR 0005: Aquagenesys v0.2 Prototype Rebuild

## Problem
Aquagenesys v0.1 evolved through the `dirty_puddle` simulator and later stage layers. The v0.2 task calls for a clean one-shot prototype centered on primitive gene tokens, a puddle environment, abstract aquatic organisms, telemetry, and a basic browser viewer.

## Options Considered
- Extend `dirty_puddle` and keep the stage model.
- Create a separate `aquagenesys` package while leaving v0.1 files inactive.
- Build the whole prototype in browser JavaScript only.

## Decision
Create a fresh Python package named `aquagenesys` with subpackages for `gene_drive`, `environment`, `organism`, `simulation`, `telemetry`, and `web`. The local viewer is a FastAPI app serving a small canvas frontend.

## Rationale
The requested module boundaries are easier to read and test as a new package than as another layer on the v0.1 stage model. Keeping Python for the simulation matches the existing repo orientation and lets tests exercise the same engine used by the web API.

## Consequences
The v0.1 `dirty_puddle` files remain in the tree as inactive historical code, but package metadata, Make targets, standards scan roots, tests, and README now point at v0.2. The prototype favors legibility and watchability over biological realism or large-scale performance.

## Explicit Deferrals
- No persisted save/load format.
- No lineage tree export.
- Species clusters are phenotype-vector buckets, not formal speciation.
- Environmental chemistry is deliberately compact and grid-local.
