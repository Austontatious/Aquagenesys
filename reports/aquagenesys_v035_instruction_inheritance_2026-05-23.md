# Aquagenesys v0.3.5 Instruction Inheritance Report

## Initial State

- Branch: `main`
- Starting HEAD: `185260c feat: add life-history reproduction and egg bank`
- Remote: `origin/main` aligned with local `main` before work.
- Working tree before work: clean.
- Runtime before work: tmux session `aquagenesys-v034` on `0.0.0.0:8770`; `/api/frame` responded with `aquagenesys.frame.v2`.
- Ports `8771` and `8772` were not running before work.

## Behavior And Memory Audit

- Reflex behavior was driven by fish health, local stress, risk tolerance, fear, hunger, and food proximity.
- Habit behavior was driven by metabolism, hunger, prey/mate/resource/shelter proximity, reproductive drive, stress, fear, sociality, and curiosity.
- Model deliberation was driven by per-fish budget, cooldown, global enable flag, uncertainty from recent outcomes, hunger/fear/stress/reproductive pressure, and a modulo tick cadence.
- Biological genome already contained behavior-adjacent numeric traits: risk tolerance, sociality, aggression, curiosity, deliberation chance, memory span, reproduction rate, metabolism, sensory range, and tolerance values.
- Existing archetype existed as `FishGenome.archetype`, but there was no separate behavior/instruction genome or per-fish prompt/instruction object.
- Offspring inherited biological genome only. Lifetime memory was individual-local and archived in summaries; no memory or behavior skills were inherited.
- Dead fish retained compact archive records and recent memory summaries, but no durable code-lineage hash existed before v0.3.5.

## Model Prompt Audit

- Current prompt file: `prompts/tasks/fish_deliberation_v0.3.md`.
- Current context schema before work: `aquagenesys.fish_context.v1`.
- Lexi received allowed actions, fish body state, energy, hunger, fear, stress, health, reproductive drive, age, model budget, biological genome, memory summary, last decision, and local perception.
- v0.3.5 adds compact `instruction_genome` and `taught_skills` to that context.
- Model output remains schema-constrained to one JSON action. Invalid JSON, invalid action, timeout, or request errors still become nonblocking failure telemetry.

## Reproduction Path Audit

- Live children were created in `_create_child`.
- Eggs were created in `_create_egg`.
- Eggs hatched into fish in `_hatch_egg`.
- v0.3.5 mixes/mutates instruction seed inside `_offspring_instruction_seed`, called during brood creation before live child or egg creation.
- Eggs now carry the instruction seed until hatching.

## Implemented v0.3.5

- Added `aquagenesys/agents/instructions.py`.
- Added bounded `BehaviorInstructionGenome`.
- Added bounded `TaughtSkill`.
- Added instruction patch validation with forbidden capability rejection, enum validation, text length caps, complexity caps, numeric clamps, and skill slot caps.
- Added rule-generated parent teaching proposals for recent feeding success, shelter survival, lineage bottlenecks, and high-energy exploration.
- Added inherited and mutated instruction seeds for live offspring, eggs, parthenogenetic offspring, and hatchlings.
- Added modest instruction effects to habit/reflex behavior:
  - cautious policies shelter earlier and prefer safe food
  - bold/high-yield policies tolerate more risk and movement intensity
  - energy-saver policies rest or reduce movement intensity
  - kin/social policies bias schooling
  - exploration policies bias exploratory direction and intensity
- Instruction policy does not alter body physics constants, speed caps, reproduction gates, or death rules.

## API / UI / Archive

- `/api/state` schema is now `aquagenesys.state.v5`.
- `/api/frame` schema is now `aquagenesys.frame.v3`.
- `/api/frame` exposes only compact instruction fields: policy hash short, policy label, strategy labels, skill count, and patch counts.
- `/api/state` exposes full instruction genome and taught skills.
- Viewer title is `Aquagenesys v0.3.5`.
- Fish inspector now shows policy hash/label, strategy summary, teaching style, skill count, and accepted/rejected patch counts.
- Telemetry now exposes instruction patches proposed/accepted/rejected, teaching events, inheritance events, policy variants alive, rejection reasons, and recent instruction events.
- Lifecycle archive records include biological genome hash, phenotype hash, instruction policy hash, taught skill hashes, and run id.
- Compact `agent_code_snapshot` records are emitted at founder birth, live birth, egg hatch, and death.

## Sandbox / Eval Results

- Safe inheritance eval: accepted bounded safe-foraging instruction patch and produced inheritance telemetry.
- Bad teaching eval: accepted bounded burst-style energy bias while physics/energy rules remained unchanged.
- Forbidden patch eval: rejected shell/filesystem/teleport/death-disable text and left behavior unaffected.
- Archive trace eval: emitted compact code-lineage and instruction trace records.
- Model-disabled evals passed; live Lexi success is not required.

## Validation

- `python3 -m pytest -q tests/test_instruction_inheritance.py tests/test_life_history_egg_bank.py tests/test_aquagenesys_v03.py`: 35 passed during implementation.
- `python3 evals/runner.py --check`: passed during implementation.
- `python3 evals/runner.py`: passed during implementation.
- `python3 -m pytest -q tests`: 44 passed.
- `python3 evals/runner.py --check`: passed.
- `python3 evals/runner.py`: passed.
- `make lint`: passed.
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`: 9 passed.
- `node --check aquagenesys/web/static/app.js`: passed.
- Browser smoke on `http://127.0.0.1:8772`: v0.3.5 loaded, canvas nonblank, instruction metrics visible, fish inspector showed policy/strategy/teaching fields, no new JavaScript console errors, and mobile viewport had no horizontal overflow.

## Known Limitations

- Instruction inheritance is single-parent in this pass.
- Model-generated teaching remains disabled by default and is not used by tests.
- Taught skills are structured tactical hints, not natural-language programs.
- No full lineage tree UI yet.
- Mate compatibility remains heuristic.

## Recommended Next Patch

v0.3.6 should add behavior/evolution observability and a lineage trace viewer: click a fish, see parent/egg lineage, biological genome hash changes, instruction policy hash changes, taught skill acquisition/loss, survival outcomes, and reproduction outcomes.
