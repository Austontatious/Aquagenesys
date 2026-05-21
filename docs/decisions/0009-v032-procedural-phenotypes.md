# ADR 0009: v0.3.2 Procedural Phenotype Rendering

## Problem

The v0.3.1 viewer made fish movement smoother and identity inspectable, but the animals still read as similar colored ovals. Inherited differences existed in the genome, yet most of those differences were not visually legible at presentation distance.

## Options Considered

- Hand-author sprite assets per archetype.
- Add a full biological morphology system.
- Add a compact procedural phenotype contract derived from existing fish genomes and render it directly on canvas.

## Decision

Add inherited phenotype traits to `FishGenome`: body shape, tail shape, fin shape, pattern type, body depth, tail length, fin span, pattern density, pattern contrast, iridescence, camouflage, eye scale, barbel length, and mild color drift across mutation.

Expose phenotype data in full fish state and compact frame payloads. The browser canvas uses those values to draw body outlines, tails, fins, countershading, stripes, saddles, speckles, iridescent highlights, eyes, and barbels. The inspector shows phenotype labels and visible trait values.

Make phenotype mechanically meaningful without expanding biology scope:

- body depth affects radius and drag
- tail length affects thrust
- fin span affects maneuvering
- existing inherited color and metabolism still influence presentation and behavior

## Rationale

This keeps v0.3.2 close to the stable v0.3.1 architecture. The environment remains CPU-owned, fish logic remains bounded, and model calls remain sparse and nonblocking. Procedural canvas rendering avoids static asset management while making lineage, mutation, and archetype differences visible in the live viewer.

## Consequences

- `/api/frame` has a slightly larger fish payload because it includes render-critical phenotype data.
- Fish are more visually identifiable across hover/click inspection and across generations.
- Phenotype traits now affect movement cost and capability, so visuals are tied to simulation mechanics.

## Explicit Deferrals

- No full skeletal anatomy or fluid simulation.
- No sprite pipeline or external art dependency.
- No advanced speciation/tree-of-life UI.
- No WebSocket/SSE transport changes.
