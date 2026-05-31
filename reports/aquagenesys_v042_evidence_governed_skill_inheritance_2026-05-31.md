# Aquagenesys v0.4.2 Evidence-Governed Skill Inheritance Report

Date: 2026-05-31

## Summary

v0.4.2 turns v0.4.1 observational skill evidence into a deterministic inheritance gate. A taught skill is no longer heritable just because a parent carries it. Offspring receive only supported skill hints, and every evaluated hint carries a status, confidence, evidence basis, source lineage, and reason.

## Answers

- Evidence-supported skills become eligible: yes. Two recent positive lineage-local observations are required before a skill can pass.
- Weak or noisy skills are suppressed: yes. Insufficient, stale, expired, and negative evidence produce explicit suppression statuses.
- God-mode inheritance is avoided: yes. Newly accepted teaching patches are `observed_only` until later observed use supports inheritance.
- Inheritance reasons are visible: yes. `/api/state` selected organism/egg payloads and telemetry include confidence, counts, status, and reason.
- Recovery remains separate: yes. Egg-bank recovery and no-debug-reseed behavior are unchanged by the governance gate.
- v0.4.1 behavior is preserved where intended: yes. Behavior scoring, morphology affordances, compact `/api/frame`, optional AI deliberation, lineage story rendering, and recovery assays remain in place.

## Implementation Notes

- `aquagenesys/simulation/skill_evidence.py` adds the governance schema and deterministic gate.
- `aquagenesys/simulation/engine.py` applies the gate during reproduction and records governance events.
- `aquagenesys/agents/fish.py` and `aquagenesys/simulation/egg.py` expose selected/full payload governance state.
- `aquagenesys/simulation/lineage_story.py` now mentions preserved or suppressed skill inheritance with cautious language.
- `aquagenesys/web/static/app.js` and `index.html` add the selected-organism skill inheritance display.
- `evals/cases/skill_governance_case.json` and `evals/runner.py` add v0.4.2 governance checks.

## Validation Targets

The standard validation suite for this pass is:

```bash
python3 -m pytest -q tests
python3 evals/runner.py --check
python3 evals/runner.py
python3 evals/recovery_assays.py --json
make lint
node --check aquagenesys/web/static/app.js
node --check aquagenesys/web/static/renderer_canvas.js
node --check aquagenesys/web/static/creature_portrait.js
```

Final run results are recorded in the task handoff/final report.
