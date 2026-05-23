# Aquagenesys v0.3.7 Recovery Assays and Observability

## Summary

- Schema: `aquagenesys.recovery_assays.v1`
- Seed count: `6`
- Bottleneck recovery rate: `1.0`
- Bottleneck extinction rate: `0.0`
- Egg-bank recovered lineages: `[4, 5, 6, 7, 8, 9, 10, 11]`
- Resource rebound opportunity: `True`
- Behavior effect size: `0.2096`
- AI dependency: `False`

## Evidence

{
  "ai_optional": true,
  "behavior_has_payoff": true,
  "egg_bank_preserves_lineages": true,
  "gates_are_explainable": true,
  "low_global_population_is_not_global_overcrowding": true,
  "mechanics_tuning_recommended": false,
  "recovery_possible": true,
  "resource_rebound_window_seen": true
}

## Tuning Decision

No simulation mechanics were tuned in v0.3.7. The seeded assays show recoverable bottleneck and egg-bank paths, and failures remain explainable through reproduction gates, crowding, resource quality, or absence of viable eggs.

## Limitations

- These are deterministic seeded assays, not a full Monte Carlo ecology study.
- Behavior payoff is measured through controlled action-selection and short-run energy effects.
- AI deliberation uses a deterministic fake controller; live Lexi/Qwen success is not required.
