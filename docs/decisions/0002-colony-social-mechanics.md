# ADR 0002: Colony And Social Mechanics

## Problem

Sprint 2 needs adhesion, emergent colony formation, cooperation, cheating, and lineage-level metrics without replacing the existing Python simulation core.

## Options Considered

- Spawn colonies as explicit agents.
- Infer colonies dynamically from adjacent adhesive cells.
- Add a separate social simulation layer with its own scheduler.

## Decision

Colonies are dynamic connected components inferred from nearby adhesive, compatible cells. Cells keep individual genomes and energy budgets; cooperation and cheating act through local public-good effects inside those emergent colonies.

## Rationale

Dynamic colony inference keeps the simulator inspectable and avoids manually spawned groups. It also makes split/merge behavior a consequence of movement, reproduction, and death.

## Consequences

Colony IDs are stable by member overlap but colonies are not permanent entities. Cheating is not hard-coded to lose; selfish cells contribute less, receive public-good benefits, and reduce adhesion reliability.

## Explicit Deferrals

- Spatial acceleration for large cooperation radii.
- Persistent colony genealogy.
- Exporting full per-tick colony history to JSON or Parquet.
