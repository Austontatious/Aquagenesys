# Aquagenesys v0.4.1 Affordance-Aware Agentic Behavior

## Summary

v0.4.1 adds a bounded action-candidate layer that makes organisms choose actions using their modular morphology affordances, local context, physiology, inherited instruction policy, and taught-skill hints.

The behavior layer remains simple and biological. It does not add shell access, filesystem access, network access, code editing, arbitrary tools, model-controlled ticks, direct fitness scoring, or guaranteed survival.

## Architecture

New module:

- `aquagenesys/agents/behavior.py`

Core objects:

- `ActionCandidate`: action, reason, context tags, affordance tags, expected cost, expected risk, expected upside, confidence, score, policy influence, skill influence, and mismatch warnings.
- `BehaviorDecision`: selected candidate plus bounded candidate summary.

The runtime path is:

```text
MorphologyAffordances + physiology + Perception + instruction priors + taught skills
-> ActionCandidate scores
-> selected Action
-> existing ecology mechanics
-> decision log / state / story evidence
```

## Action Candidates

The v0.4.1 action surface is intentionally compact:

- `filter_feed`
- `graze`
- `scavenge`
- `anchor_feed`
- `forage`
- `strike`
- `hunt`
- `chemical_defense`
- `flee`
- `shelter`
- `rest`
- `court`
- `school`
- `explore`

These are biological actions, not external tools and not species classes.

## Affordance Scoring

Examples implemented:

- high filter and suction increase `filter_feed` value in bloom/resource contexts
- high bite and sensory range increase `strike`/`hunt` value when prey is nearby
- high reach and grip increase `scavenge` and `anchor_feed`
- high armor lowers flee urgency under moderate threat
- soft vulnerable tissue increases threat avoidance pressure
- toxin payload enables `chemical_defense`, with self-toxicity and metabolic cost
- high drag, high oxygen cost, and high metabolic burden penalize long chase/flee/explore actions

Policy can now conflict with body. For example, a high-yield policy on a high-drag filter body records a mismatch warning rather than becoming a free strategy.

## Context And Affordance Tags

Context tags:

- `scarcity`
- `bloom`
- `crowded`
- `low_oxygen`
- `high_toxin`
- `predator_near`
- `prey_near`
- `mate_near`
- `low_energy`
- `high_stress`
- `bottleneck`
- `recovery`
- `near_detritus`
- `near_shelter`
- `local_resource_patch`
- `open_water`

Affordance tags:

- `high_filter`
- `high_suction`
- `high_bite`
- `high_reach`
- `high_armor`
- `high_toxin`
- `high_sensory`
- `high_drag`
- `high_oxygen_cost`
- `soft_body`
- `bulk_body`
- `small_body`

These tags are included in behavior state and skill evidence events for future v0.4.2 governance.

## State/API

Schema changes:

- `/api/state`: `aquagenesys.state.v12`
- behavior state: `aquagenesys.behavior.v1`
- dashboard behavior panel: `aquagenesys.behavior_dashboard.v1`
- lineage story: `aquagenesys.lineage_story.v4`
- `/api/frame`: remains `aquagenesys.frame.v3`

`/api/state.behavior` exposes bounded per-organism rationale:

- current action
- action reason
- top candidates
- context tags
- affordance tags
- policy influence
- skill influence
- mismatch warnings

`/api/frame` remains lightweight and does not include the behavior rationale payload.

## Dashboard And Story

The dashboard now includes an affordance-aware behavior observatory with top actions, top context tags, top affordance tags, mismatch warnings, and notable organisms.

The focused fish inspector now shows:

- behavior rationale
- top candidate scores
- context and affordance tags
- policy/skill influence
- mismatch warnings

Genealogy and lineage story carry compact behavior traces. Story language remains cautious: behavior is described as associated with body affordances and local context, not as proven causal optimization.

## Skill Evidence Compatibility

Skill evidence events can now carry action context tags and affordance tags. Existing effect labels remain observational:

- `helped_possible`
- `harmed_possible`
- `unclear`
- `insufficient_evidence`

v0.4.1 does not implement skill promotion, decay, suppression, context gating, or denominator comparisons.

## Seeded Examples

Targeted seeded behavior examples:

- filter-bloom body selected `filter_feed`; top candidate score `0.882`; tags `high_filter`, `high_suction`, `bloom`
- bite-prey body selected `strike`; top candidate score `0.919`; tags `high_bite`, `high_sensory`, `prey_near`
- appendage-detritus body selected `scavenge`; top candidate score `0.738`; tags `high_reach`, `high_drag`, `high_oxygen_cost`, `near_detritus`

Seed `741`, 16 ticks, 12 founders:

- state schema: `aquagenesys.state.v12`
- behavior schema: `aquagenesys.behavior.v1`
- lineage story schema: `aquagenesys.lineage_story.v4`
- decision sources: `affordance=28`, `reflex=8`
- recent top actions: `shelter=22`, `flee=7`, `court=4`, `filter_feed=2`, `school=1`
- observed mismatch warnings: high-yield/costly-body conflict and reflex overrides

## Tests And Evidence

New targeted tests cover:

- affordance-to-action scoring
- threat/drag cost tradeoffs
- policy/body interaction
- context tag and affordance tag generation
- skill evidence compatibility
- bounded state/API behavior payload
- seeded ecology smoke

Regression tests update expected schemas to state v12 and lineage story v4.

Validation completed:

- `python3 -m pytest -q tests`: 71 passed
- `python3 -m pytest -q tests/test_affordance_aware_behavior.py`: 7 passed
- `python3 evals/runner.py --check`: passed
- `python3 evals/runner.py`: passed
- `python3 evals/recovery_assays.py --json`: passed, recovery rate 1.0, no god-mode reseed true
- `make lint`: passed
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: 9 passed
- `node --check aquagenesys/web/static/app.js`: passed

Browser smoke on `127.0.0.1:8775` loaded `Aquagenesys v0.4.1`, returned `/api/state aquagenesys.state.v12`, showed behavior/morphology/recovery/genealogy/story panels, rendered a nonblank canvas, updated selected-fish behavior rationale and candidate display, opened compare mode with Ctrl-click, and reported no console warnings or errors. A 390px mobile viewport had no horizontal overflow.

## Limitations

- The selector is still a bounded scorer, not a planner.
- Candidate estimates are local heuristics, not proven outcome predictions.
- Skill evidence is observational only.
- Existing predation/resource mechanics are reused rather than rewritten.
- The model-deliberation path remains optional and nonblocking.

## Deferred

- v0.4.2: evidence-governed skill inheritance
- v0.4.3: lineage fitness denominators
- v0.4.4: niche/diversity and anti-convergence tracking
- v0.4.5: optional model-generated behavior priors
