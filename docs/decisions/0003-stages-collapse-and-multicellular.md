# ADR 0003: Stages, Collapse, And Simple Multicellular Life

## Problem

The simulator needs to support bloom, collapse, recovery, stagnation, regression, and re-emergence instead of guaranteeing upward progress.

## Options Considered

- Keep stages implicit and infer them only from population.
- Add explicit stages with promotion/regression rules.
- Replace the cell simulation with a higher-level ecosystem model.

## Decision

Add explicit environment stages while preserving the existing cell and colony simulation. Stage 3 organisms are simple larger agents derived from stable colonies. Environment health and support score drive promotion, regression, and dirty-puddle collapse.

## Rationale

Explicit stages make long-running history understandable and testable. Keeping organisms simple avoids turning the project into a complex biology simulator.

## Consequences

The world can move up and down the stage ladder. Collapse degrades unsupported lifeforms but preserves event history and surviving cells/spores. Run history and event logs are exportable for unattended runs.

## Explicit Deferrals

- Complex neural control for organisms.
- Persistent organism phylogeny beyond origin lineage/colony.
- Fish tank ecosystem mechanics.
