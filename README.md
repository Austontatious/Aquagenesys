# Aquagenesys v0.3.9

Aquagenesys v0.3.9 is a real-time dirty-puddle artificial ecology with recovery assays, an ecology observatory UI, a lineage/policy genealogy explorer, and a deterministic lineage story renderer. The CPU owns the puddle chemistry and physics; fish are bounded local agents that mostly act through reflexes and habits, with sparse AI deliberation routed to the local Lexi/Qwen-compatible endpoint when budget and pressure allow.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m aquagenesys.web.app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

The default model endpoint is OpenAI-compatible Lexi on `http://127.0.0.1:8008/v1` with model name `Lexi`. Disable model calls for deterministic local runs with:

```bash
python -m aquagenesys.web.app --no-deliberation
```

## v0.3.9 Architecture

- `aquagenesys.environment.PuddleEnvironment` owns deterministic 2D world fields: temperature, oxygen, pH, turbidity, nutrients, light, currents, shelter, substrate, obstacles, food, plankton, waste, toxins, decomposition/detritus, reproduction support, population pressure, and ecological balance.
- `aquagenesys.agents.FishAgent` owns fish identity, body state, position, energy, hunger, fear, stress, health, reproductive drive, maturity/fertility state, memory, recent outcomes, model-call budget, and genome strategy.
- `aquagenesys.agents.FishGenome` owns inherited procedural phenotype and life-history traits, including dormancy bias, egg viability horizon, parthenogenesis alleles, parthenogenesis bias, and mutation load.
- `aquagenesys.agents.instructions.BehaviorInstructionGenome` owns bounded behavioral priors: risk posture, forage/threat/social/reproduction/exploration/energy strategies, teaching style, memory bias, model deliberation bias, skill slots, and mutation rate.
- `aquagenesys.agents.instructions.TaughtSkill` represents bounded parent-transmitted behavior hints. Skills are structured, short-lived by generation TTL, schema-validated, and cannot request shell, file, network, repo, server, tool, code-editing, teleport, death-disabling, or energy-bypass behavior.
- `aquagenesys.agents.life_history.LifeHistoryProfile` derives maturity age, fertility window, expected lifespan, reproduction interval, clutch size, offspring investment, brood strategy, egg strategy, dormancy behavior, and clonal reproduction pressure from genome/phenotype.
- `aquagenesys.simulation.egg.EggEntity` represents independent eggs/embryos. Eggs carry both biological genome and instruction seed, persist after parent death, may enter dormancy, decay under hostile chemistry, and hatch under suitable low-pressure conditions.
- `aquagenesys.agents.FishAgent` also owns smoothed locomotion state: heading, turn rate, swim phase, tail beat, body wave, stride, and current speed.
- `aquagenesys.agents.FishDeliberationController` uses `core.llm.LLMClient` and `prompts/tasks/fish_deliberation_v0.3.md`; environment ticks never depend on model calls.
- Model deliberation runs out of the viewer request path. Successful model actions become short-lived fish intents with a TTL; failures remain visible in model telemetry and events.

## Instruction Inheritance

Parent organisms can influence offspring behavior priors, but only through bounded schemas:

```text
parent strategy + taught skill proposal
-> schema validation and capability checks
-> clamped instruction genome / skill seed
-> offspring behavior bias
-> physics, energy, and ecology decide survivability
```

Instruction inheritance is enabled by default with `AQUAGENESYS_INSTRUCTION_INHERITANCE_ENABLED=true`. Model-generated teaching remains disabled by default with `AQUAGENESYS_MODEL_TEACHING_ENABLED=false`; the system does not require live Lexi success for instruction inheritance.

Instruction policy affects behavior modestly:

- cautious policies shelter earlier and prefer safe food
- bold policies tolerate more risk and can burn more energy
- kin-schooling policies bias school behavior
- energy-saver policies rest or reduce movement intensity
- novelty-seeking policies explore more when conditions allow

Instruction policy does not alter body mechanics, speed caps, energy accounting, reproduction rules, or death rules.

## Reproduction Model

Reproduction is no longer a single direct spawn. Mature fish pay energy into a brood. Life-history traits determine clutch size, reproduction cooldown, offspring investment, and whether the brood becomes live juveniles, eggs, or a mixed clutch. Normal reproduction requires mate contact with a compatible local organism. Offspring and eggs inherit biological genome plus a bounded instruction seed.

Some genomes carry a rare facultative parthenogenesis locus. A singleton fish without alleles cannot magically reproduce. A mature, healthy, mate-isolated fish with alleles may attempt an emergency clonal egg clutch, but the attempt is stochastic, energy-costed, usually egg-based, and carries viability/mutation-load penalties.

The egg bank is organic resilience, not rescue spawning:

```text
adult crash -> viable eggs remain -> biosphere_state=dormant
good chemistry + low pressure -> eggs may hatch
adults restored -> biosphere_state=active
no adults + no viable eggs -> biosphere_state=extinct
```

Deaths and waste now feed local decomposition/detritus, nutrients, food, and plankton. Moderate detritus can support rebound; excessive waste can still depress oxygen or increase toxins.

## Viewer

The FastAPI viewer exposes `/api/state`, compact `/api/frame`, and `/api/control`. The browser polls `/api/frame` for lightweight movement and lifecycle metrics, interpolates fish motion with `requestAnimationFrame`, and keeps `/api/state` at a lower cadence for full environment fields.

v0.3.9 keeps the ecology observatory layout, recovery evidence, and genealogy explorer, then adds a lineage story renderer:

- the puddle canvas remains the dominant visual surface
- the right sidebar focuses on hovered/selected fish and optional two-fish comparison
- the below-puddle observatory shows the ecology narrator, population/lifecycle dashboard, lineage/policy/teaching summaries, event timeline, and diagnostics
- the recovery evidence panel explains whether the puddle is stable, declining, bottlenecked, dormant, rebounding, recovering, or extinct
- the genealogy explorer shows biology and behavior inheritance side by side for selected lineages
- the lineage story renderer answers who survived, what they inherited, what changed, what they tried, what killed others, and why the lineage persisted
- the AI deliberation control describes bounded AI reflections without requiring the viewer to know the internal Lexi/Qwen runtime name
- `/api/state` includes a dashboard-friendly `aquagenesys.dashboard.v2` object
- `/api/state` includes a bounded `aquagenesys.genealogy.v1` object
- `/api/state` includes a bounded `aquagenesys.lineage_story.v1` object
- `/api/frame` remains compact and does not carry dashboard payloads

Hover a fish for a quick preview. Click to focus one fish. Ctrl-click or command-click a second fish to compare body, lifecycle, policy, strategy, teaching history, current action, and relationship signals such as shared lineage, shared policy, feeding role, and proximity.

The ecology narrator is deterministic and grounded in current state. It summarizes population pressure, egg-bank resilience, recovery phase, resource rebound, dominant lineages, policy prevalence, teaching activity, and recent events without model calls or freeform fiction.

The genealogy explorer is deliberately bounded. It sends compact live-adult, egg, and sampled-dead-ancestor nodes with parent links, biological signatures, phenotype hashes, instruction policy hashes, taught-skill counts, patch counts, and recovery roles. It does not send raw runtime memory or unbounded genome dumps.

The lineage story renderer is also bounded and rule-based. It does not call a model. It composes short evidence-backed story cards from genealogy nodes, recovery dashboard signals, recent events, reproduction gates, instruction inheritance records, and compact dead-agent summaries. It is intended to make the recursive-agent thesis legible without reading JSONL logs:

```text
Who survived?
What did they inherit?
What changed?
What did they try?
What killed the others?
Why did this lineage persist?
```

## Recovery Assays

v0.3.7 adds programmatic seeded recovery assays under `evals/recovery_assays.py`. These measure bottleneck recovery, egg-bank resilience, reproduction gates, density/crowding sanity, resource rebound, behavior-policy payoff, and optional AI deliberation. They are intended to prevent tuning from being driven by one dramatic visual run.

Run them directly with:

```bash
python evals/recovery_assays.py --json
python evals/recovery_assays.py --write-report --report-date 2026-05-23
```

The current assay contract explicitly checks that recovery does not use debug founder reseeding, egg-bank recovery does not create instant adults, low global population is not treated as global overcrowding, behavior policies change choices without changing physical capability, and live Lexi/Qwen success is not required.

Per fish tick:

```text
1. Sense local environment
2. Update internal state and lifecycle timers
3. Run reflex rules
4. Run habit policy
5. Optionally deliberate through Lexi if budget and pressure allow
6. Select action
7. Apply action to fish and environment
8. Attempt energy-costed reproduction if gates pass
9. Validate and inherit bounded offspring instruction seeds when reproduction succeeds
10. Update eggs/embryos and hatch viable eggs
11. Record outcome, lifecycle, and compact code-lineage snapshots to archive
```

## Archives

Fish state, memory, eggs, lifecycle events, instruction patch decisions, teaching events, offspring instruction inheritance, and compact agent code snapshots are externalized as JSONL under `/tmp/aquagenesys-v03` by default. Records include `run_id` so append-only archives can be segmented without mixing older runs.

Useful files:

- `fish_state.jsonl`
- `fish_memory.jsonl`
- `lifecycle_events.jsonl`

## Validation

```bash
python -m pytest -q tests
python evals/runner.py --check
python evals/runner.py
make lint
node --check aquagenesys/web/static/app.js
```

## Configuration

Runtime settings are centralized in `core/config.py` and may be provided with `AQUAGENESYS_*` variables. See `.env.example` for the full surface.

## Known Limitations

Aquagenesys still uses compact compatibility heuristics for mate contact rather than a full sexual genetics model. Eggs model viability and dormancy but not detailed embryology. Instruction inheritance is structured and compact rather than a full natural-language agent-program evolution system. v0.3.9 adds bounded genealogy and story surfaces, but not a full interactive graph database, complete species tree, or model-written narrative.
