# ADR 0018: v0.4.1 Affordance-Aware Agentic Behavior

## Status

Accepted for v0.4.1.

## Context

v0.4.0 made body plans mechanically meaningful through modular morphology loci and primitive affordances. The behavior loop still treated organisms mostly as equivalent actors after those costs and capacities were computed.

v0.4.1 adds the first behavior modernization step: organisms choose among bounded biological actions using local context, physiology, morphology affordances, inherited instruction priors, and taught-skill hints.

This does not introduce shell, filesystem, network, code editing, arbitrary tools, model-controlled ticks, durable model-authored strategy code, or direct fitness scoring.

## Decision

Add `aquagenesys.agents.behavior` with:

- `ActionCandidate`: compact, inspectable candidate action with reason, context tags, affordance tags, expected cost, expected risk, expected upside, confidence, score, policy influence, skill influence, and mismatch warnings.
- `BehaviorDecision`: sorted candidate set plus selected action rationale.
- `derive_context_tags`: bounded local tags such as `scarcity`, `bloom`, `low_oxygen`, `predator_near`, `near_detritus`, `recovery`, and `local_resource_patch`.
- `derive_affordance_tags`: body tags such as `high_filter`, `high_suction`, `high_bite`, `high_reach`, `high_armor`, `high_toxin`, `high_drag`, `high_oxygen_cost`, `soft_body`, `bulk_body`, and `small_body`.
- `build_behavior_decision`: deterministic scoring that combines body affordance, body cost, context, instruction policy, and taught-skill hint.

The selector remains simple and local. It produces normal `Action` values consumed by existing ecology mechanics. Ecology still determines consequences.

## Action Surface

v0.4.1 keeps actions biological and mechanically bounded:

- low-movement feeding: `filter_feed`, `graze`, `scavenge`, `anchor_feed`
- general feeding and movement: `forage`, `explore`, `school`
- bite/chase actions: `strike`, `hunt`
- threat actions: `flee`, `shelter`, `chemical_defense`
- lifecycle action: `court`
- recovery action: `rest`

The list is intentionally small. Labels such as "predator" or "grazer" are not behavior classes.

## Scoring Model

Candidate score is a compact weighted combination:

```text
upside
+ inherited policy adjustment
+ taught skill hint
- expected movement/metabolic cost
- expected risk
```

Morphology affects both upside and cost:

- filter/suction bodies favor `filter_feed` in blooms and penalize bite attempts when bite is weak
- bite/strike bodies favor `strike` and `hunt` when prey is nearby
- reach/grip bodies favor `scavenge` and `anchor_feed`
- armor lowers flee urgency under moderate threat
- soft vulnerable bodies increase shelter/flee pressure
- toxin payload enables `chemical_defense`, but self-toxicity and metabolic costs remain visible
- high drag and oxygen cost penalize long chase, flee, and exploration

Inherited priors can help or hurt. For example, `high_yield_patch` reinforces chase-like choices on fast bite bodies but creates mismatch warnings on high-drag filter bodies.

## State And Observability

`/api/state` moves to `aquagenesys.state.v12` and includes top-level behavior state:

- schema `aquagenesys.behavior.v1`
- compact per-organism current action and reason
- top candidate summary
- context tags
- affordance tags
- policy influence
- skill influence
- mismatch warnings

`/api/frame` remains `aquagenesys.frame.v3` and does not include the behavior rationale payload.

The dashboard adds `aquagenesys.behavior_dashboard.v1`, and the selected-fish inspector shows action rationale, candidate scores, tags, policy/skill influence, and mismatch warnings.

Lineage story moves to `aquagenesys.lineage_story.v4` so deterministic stories can include cautious behavior language such as "associated with high filter affordance" rather than causal claims.

## Skill Evidence Compatibility

Skill evidence remains observational. v0.4.1 extends skill-use events with context and affordance tags but keeps existing labels:

- `helped_possible`
- `harmed_possible`
- `unclear`
- `insufficient_evidence`

No evidence-governed promotion, decay, suppression, context gating, or fitness denominator logic is implemented in v0.4.1.

## Consequences

Organisms now attempt different actions based on body plan before ecology evaluates the result. Weird morphology can create different possible actions, movement costs, risk postures, and observed behavior distributions.

The architecture remains:

```text
body affordance
-> candidate actions
-> cost/risk/upside scoring
-> inherited prior influence
-> bounded action choice
-> ecology evaluates
-> evidence recorded for future governance
```

## Deferred

- v0.4.2: evidence-governed skill inheritance
- v0.4.3: lineage fitness denominators
- v0.4.4: niche/diversity and anti-convergence tracking
- v0.4.5: optional model-generated behavior priors as validated hypotheses
