# ADR 0010: v0.3.3 Biomechanical Locomotion

## Problem

v0.3.2 made fish visually distinct, but motion still came mostly from per-tick velocity changes and canvas interpolation. Fish could visibly rotate or redirect too abruptly for organisms that now have tails, fins, and body phenotypes.

## Options Considered

- Keep the existing velocity-only movement and add more canvas animation.
- Add a full articulated body simulation.
- Add bounded locomotion state to fish agents and use it for both movement mechanics and rendering.

## Decision

Add stateful locomotion fields to `FishAgent`: heading, turn rate, swim phase, tail beat, body wave, locomotion speed, and stride.

Update movement application so fish actions produce a desired heading and target speed. The simulation eases heading through a genome/phenotype-bounded turn capacity, applies smoothed acceleration, damps lateral slip, and then updates swim phase and body wave from actual speed and turn rate.

Expose compact locomotion payloads in `/api/state` and `/api/frame`. The browser interpolates heading and swim phase between frame snapshots, draws body bend and tail beats from locomotion state, and shows speed/turn in the inspector.

## Rationale

This keeps the CPU simulation authoritative while making motion legible and biomechanically tied to inherited phenotype traits. Tail length, fin span, body depth, max speed, and turning now contribute to both movement outcomes and rendered motion without adding heavyweight physics.

## Consequences

- Fish turns are smoother and less frame-snapped.
- Tail beat, body wave, and wake effects are derived from simulation state instead of only browser time.
- The compact frame payload grows slightly to carry locomotion fields.

## Explicit Deferrals

- No full skeletal constraints or multi-segment body dynamics.
- No collision avoidance steering beyond existing environment bounds/obstacles.
- No WebSocket/SSE or background simulation loop changes.
- No major new behavior policy or biology expansion.
