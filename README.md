# Aquagenesys v0.3.1

Aquagenesys v0.3.1 is a real-time dirty-puddle artificial ecology. The CPU owns the puddle chemistry and physics; fish are bounded local agents that mostly act through reflexes and habits, with sparse deliberation routed to the local Lexi vLLM service when budget and pressure allow.

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

## v0.3.1 Architecture

- `aquagenesys.environment.PuddleEnvironment` owns deterministic 2D world fields: temperature, oxygen, pH, turbidity, nutrients, light, currents, shelter, substrate, obstacles, food, plankton, waste, toxins, decomposition, reproduction support, population pressure, and ecological balance.
- `aquagenesys.agents.FishAgent` owns fish identity, body state, position, energy, hunger, fear, stress, health, reproductive drive, perception, memory, recent outcomes, model-call budget, and genome strategy.
- `aquagenesys.agents.FishDeliberationController` uses `core.llm.LLMClient` and `prompts/tasks/fish_deliberation_v0.3.md`; environment ticks never depend on model calls.
- Model deliberation runs out of the viewer request path. Successful model actions become short-lived fish intents with a TTL; failures remain visible in model telemetry and events.
- Heavy puddle field evolution runs at a bounded ecology cadence so fish movement can keep ticking between full chemistry/diffusion passes.
- Fish state and memory snapshots are externalized as JSONL under `/tmp/aquagenesys-v03` by default.
- The FastAPI viewer exposes `/api/state`, compact `/api/frame`, and `/api/control`. The browser polls `/api/frame` for fish motion, interpolates between snapshots with `requestAnimationFrame`, and keeps `/api/state` at a lower cadence for full environment fields.
- Hover or click a fish in the viewer to inspect stable id, lineage, generation, species, archetype, body state, decision source, active model intent, and energy.

Per fish tick:

```text
1. Sense local environment
2. Update internal state
3. Run reflex rules
4. Run habit policy
5. Optionally deliberate through Lexi if budget and pressure allow
6. Select action
7. Apply action to fish and environment
8. Record outcome to memory/archive
```

## Validation

```bash
python -m pytest -q tests
python evals/runner.py --check
python evals/runner.py
make lint
```

## Configuration

Runtime settings are centralized in `core/config.py` and may be provided with `AQUAGENESYS_*` variables. See `.env.example` for the full surface.
