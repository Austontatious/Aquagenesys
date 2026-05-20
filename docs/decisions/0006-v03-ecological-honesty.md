# ADR 0006: v0.3 Ecological Honesty

## Problem
Aquagenesys v0.2 could recover from low population or extinction by injecting fresh founder organisms. That kept the viewer lively, but it made population recovery ambiguous and ecologically dishonest.

## Options Considered
- Keep automatic founder reseed for watchability.
- Disable hidden reseed and allow dead puddles.
- Add a full dormant cyst/spore lifecycle immediately.

## Decision
Disable founder reseed by default and allow true extinction. Keep reset as the only normal path that creates a fresh founder population. Retain founder reseed only behind `debug_founder_reseed_enabled`, with explicit telemetry labels.

## Rationale
The simulation should not create animals invisibly after initial seed/reset. Recovery must either come from reproduction, a modeled dormant state, or an explicitly labeled debug mechanism.

## Consequences
Default runs can become dead puddles. The environment continues evolving after extinction, and telemetry reports dead-puddle state, viability score, viable cell count, extinction count, recovery counters, and collapse-cause guess. Dormant propagules are deferred rather than faked.

## Explicit Deferrals
- No dormant propagule lifecycle in v0.3.
- No selected-organism UI inspection.
- No automated environment retuning beyond small default/cost adjustments.
