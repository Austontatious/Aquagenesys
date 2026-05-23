# Aquagenesys v0.3.4

Aquagenesys v0.3.4 is a real-time dirty-puddle artificial ecology. The CPU owns the puddle chemistry and physics; fish are bounded local agents that mostly act through reflexes and habits, with sparse deliberation routed to the local Lexi vLLM service when budget and pressure allow.

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

## v0.3.4 Architecture

- `aquagenesys.environment.PuddleEnvironment` owns deterministic 2D world fields: temperature, oxygen, pH, turbidity, nutrients, light, currents, shelter, substrate, obstacles, food, plankton, waste, toxins, decomposition/detritus, reproduction support, population pressure, and ecological balance.
- `aquagenesys.agents.FishAgent` owns fish identity, body state, position, energy, hunger, fear, stress, health, reproductive drive, maturity/fertility state, memory, recent outcomes, model-call budget, and genome strategy.
- `aquagenesys.agents.FishGenome` owns inherited procedural phenotype and life-history traits, including dormancy bias, egg viability horizon, parthenogenesis alleles, parthenogenesis bias, and mutation load.
- `aquagenesys.agents.life_history.LifeHistoryProfile` derives maturity age, fertility window, expected lifespan, reproduction interval, clutch size, offspring investment, brood strategy, egg strategy, dormancy behavior, and clonal reproduction pressure from genome/phenotype.
- `aquagenesys.simulation.egg.EggEntity` represents independent eggs/embryos. Eggs persist after parent death, may enter dormancy, decay under hostile chemistry, and hatch under suitable low-pressure conditions.
- `aquagenesys.agents.FishAgent` also owns smoothed locomotion state: heading, turn rate, swim phase, tail beat, body wave, stride, and current speed.
- `aquagenesys.agents.FishDeliberationController` uses `core.llm.LLMClient` and `prompts/tasks/fish_deliberation_v0.3.md`; environment ticks never depend on model calls.
- Model deliberation runs out of the viewer request path. Successful model actions become short-lived fish intents with a TTL; failures remain visible in model telemetry and events.

## Reproduction Model

Reproduction is no longer a single direct spawn. Mature fish pay energy into a brood. Life-history traits determine clutch size, reproduction cooldown, offspring investment, and whether the brood becomes live juveniles, eggs, or a mixed clutch. Normal reproduction requires mate contact with a compatible local organism.

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

The side panel shows adults, eggs, viable eggs, dormant eggs, births, hatched eggs, lineages, reproduction gate failures, and recent lifecycle events. Hover or click a fish to inspect stable id, lineage, generation, species, archetype, phenotype, locomotion, maturity/fertility state, life-history summary, egg-bank traits, parthenogenesis alleles, reproduction cooldown, and last reproduction gate.

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
9. Update eggs/embryos and hatch viable eggs
10. Record outcome to memory/archive
```

## Archives

Fish state, memory, eggs, and lifecycle events are externalized as JSONL under `/tmp/aquagenesys-v03` by default. Records include `run_id` so append-only archives can be segmented without mixing older runs.

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

Aquagenesys still uses compact compatibility heuristics for mate contact rather than a full sexual genetics model. Eggs model viability and dormancy but not detailed embryology. v0.3.5 is reserved for bounded offspring instruction inheritance: parents may influence offspring behavior priors, but agents will not edit their own runtime code.
