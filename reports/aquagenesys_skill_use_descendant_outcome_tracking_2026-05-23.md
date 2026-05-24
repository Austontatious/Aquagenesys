# Aquagenesys Skill-Use and Descendant-Outcome Tracking

Date: 2026-05-23

## Summary

This patch adds the first evidence layer connecting taught/inherited behavior to observed use and descendant outcomes. It does not make fish smarter, add tools, enable code editing, or rely on model teaching. It records when a bounded taught skill is inherited, when a fish expresses that skill in a relevant behavior context, what happened immediately afterward, and whether a later descendant outcome such as reproduction or death followed observed use.

The new evidence is intentionally observational. The supported claim is: "this inherited behavior was used and was followed by helped_possible, harmed_possible, or unclear outcomes." The unsupported claim remains: "this skill caused success."

## What Was Implemented

New module:

- `aquagenesys/simulation/skill_evidence.py`
  - `SkillUseEvidence`
  - `matched_skills_for_action`
  - `classify_skill_outcome`
  - `aggregate_skill_evidence`

Engine wiring:

- `aquagenesys/simulation/engine.py`
  - Records `skill_inherited` during offspring instruction inheritance.
  - Records hatch-time inherited skill preservation when eggs become live descendants.
  - Observes skill use after the behavior decision and action application in the per-fish tick loop.
  - Records `skill_descendant_outcome` when a skill carrier reproduces after observed use.
  - Records weak death-after-use outcome evidence when a skill carrier dies soon after observed use.
  - Archives skill evidence as lifecycle events with an explicit non-causal claim boundary.

State and observability:

- `/api/state` schema is now `aquagenesys.state.v10`.
- `/api/frame` remains `aquagenesys.frame.v3` and does not include genealogy, lineage story, dashboard, or skill evidence payloads.
- `telemetry.skill_evidence` exposes compact v1 evidence:
  - recent events
  - lineage/skill aggregates
  - helped/harmed/unclear counters
  - carrier/user/use counts
  - reproduction-after-use counts
  - claim boundary text

Dashboard/story surfaces:

- `aquagenesys/simulation/dashboard.py` adds `dashboard.skill_evidence`.
- `aquagenesys/simulation/genealogy.py` adds `genealogy.skill_evidence`.
- `aquagenesys/simulation/lineage_story.py` is now `aquagenesys.lineage_story.v2` and includes lineage-local skill evidence in answers and story payloads.
- `aquagenesys/web/static/index.html`, `app.js`, and `styles.css` add an "Inherited Behavior Evidence" panel.

## Evidence Events

Implemented event types:

- `skill_inherited`: an offspring or egg received a bounded taught skill.
- `skill_outcome_observed`: a fish carried a taught skill, a relevant context matched, the action path expressed that skill, and an immediate outcome was observed.
- `skill_descendant_outcome`: a skill carrier reproduced or died after a recent observed use.

Pure reflex actions are not counted as skill use unless their reason is instruction-biased. Habit actions can count when the current instruction policy expresses the skill's action bias.

## Aggregation

Lineage/skill aggregates include:

- `skill_id`
- `skill_hash`
- `lineage_id`
- `carriers_count`
- `users_count`
- `uses_count`
- `offspring_carriers_count`
- `survival_ticks_after_use`
- `reproduction_after_use_count`
- `helped_possible_count`
- `harmed_possible_count`
- `unclear_count`
- `last_seen_tick`
- `evidence_strength`
- `interpretation`

Labels are deliberately cautious:

- `helped_possible`
- `harmed_possible`
- `unclear`
- `insufficient_evidence`

## What The System Can Now Claim

Aquagenesys can now answer:

- Which bounded taught skill was inherited.
- Which child/egg/hatchling inherited it.
- Whether that skill was later observed in a relevant context.
- Which action expressed the skill.
- What immediate outcome followed.
- Whether later reproduction or death followed observed use.
- How many carriers, users, and uses are visible in the bounded evidence window.
- Whether the observed effect is helped_possible, harmed_possible, unclear, or insufficient evidence.

## What The System Still Cannot Claim

Aquagenesys still cannot claim:

- The skill caused survival or reproduction.
- A counterfactual fish without the skill would have failed.
- A taught skill was globally optimal.
- A lineage improved because of one skill alone.
- Skill evidence is complete across all archived history. The state/dashboard views are bounded windows.

## Example Lineage Story Excerpt

From a deterministic test scenario with a taught foraging prior:

> Inherited behavior evidence: forage:safe_food was observed in use; lineage totals show 1 carriers, 1 uses, 1 helped possible, 0 harmed possible, and 0 unclear.

The same story includes the explicit boundary:

> Claim boundary: this suggests possible effects, but this run does not prove causality.

Example aggregate:

```json
{
  "skill_name": "forage:safe_food",
  "carriers_count": 1,
  "users_count": 1,
  "uses_count": 1,
  "helped_possible_count": 1,
  "harmed_possible_count": 0,
  "unclear_count": 0,
  "latest_relevant_event": "skill_outcome_observed",
  "latest_context": "hunger_or_food_opportunity",
  "latest_outcome": "fed",
  "evidence_strength": "moderate"
}
```

## Tests Added Or Updated

Added:

- `tests/test_skill_evidence_tracking.py`

Updated:

- State schema expectations to `aquagenesys.state.v10`.
- Lineage story schema expectations to `aquagenesys.lineage_story.v2`.
- Eval case schema expectations.
- Eval lineage story schema gate.

## Validation Run

Passed:

- `python3 -m pytest -q tests`
- `python3 evals/runner.py --check`
- `python3 evals/runner.py`
- `python3 evals/recovery_assays.py --json`
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`
- `node --check aquagenesys/web/static/app.js`

JSON report validation is expected for `reports/aquagenesys_skill_use_descendant_outcome_tracking_2026-05-23.json`.

## Limitations

- The action-use detector is rule-based and conservative, not causal inference.
- Immediate outcomes are measured by local deltas such as hunger, energy, stress, fear, health, and action outcome.
- Descendant outcome attribution is temporal: reproduction/death after recent observed use.
- The bounded dashboard and lineage story can miss older evidence outside the in-memory window.
- The implementation does not yet compare matched fish against controls or counterfactual policies.

## Recommended Next Step

Add an explicit lineage fitness panel for skill-bearing vs non-skill-bearing descendants in the same run, with denominators and uncertainty. That is the smallest next step toward comparing Aquagenesys ecology-as-evaluator evidence with benchmark-evaluator systems.
