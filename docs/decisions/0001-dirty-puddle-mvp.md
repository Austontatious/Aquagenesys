# ADR 0001: Dirty Puddle MVP Architecture

## Problem

Aquagenesys needs a first playable artificial life simulator with cells, fields, mutation, reproduction, death, lineage tracking, and live visualization without adding unnecessary frontend or engine complexity.

## Options Considered

- Pure Python simulation core with pygame visualization.
- Numpy-first simulation core with pygame visualization.
- Browser or Godot frontend backed by a Python simulation server.

## Decision

Use a pure Python simulation core under `dirty_puddle/sim` and keep pygame isolated under `dirty_puddle/ui`. Configs are flat YAML-style files parsed by the core to avoid a dependency beyond pygame for the MVP.

Define explicit performance tiers instead of shrinking the simulator concept:

- `demo_small`: fast pygame-visible mode for immediate interaction.
- `default_live`: balanced pygame mode with meaningful ecology.
- `rich_ecology`: larger, slower mode for unattended runs.
- `headless_longrun`: optimized non-visual mode for 100k+ tick runs; it prioritizes horizon length over maximum population.

## Rationale

The user requested Python + pygame first and explicitly asked not to get fancy. Keeping pygame out of the core makes long-run tests headless and preserves a clear path to later numpy acceleration or alternate frontends.

## Consequences

Live pygame modes may use fewer cells than unattended headless runs. The core remains grid-size and population configurable, and richer configs remain first-class.

Field cadence, metrics cadence, integer occupancy keys, and precomputed neighbor lists are allowed conservative optimizations because they do not change mutation, reproduction, stress, or death rules. Field update intervals approximate continuous regeneration by scaling nutrient regen across the interval; that cadence is documented in config.

## Explicit Deferrals

- JSON or Parquet run exports.
- Numpy field and occupancy acceleration.
- Web or Godot frontend.
