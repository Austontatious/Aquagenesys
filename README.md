# Aquagenesys v0.4.2

Aquagenesys is a real-time artificial aquatic ecology built as a recursive agentic workflow sandbox. It renders a dirty-puddle / bioluminescent reef ecosystem where bounded organisms forage, shelter, hunt, court, reproduce, die, leave eggs, recover from bottlenecks, inherit behavior hints, and accumulate evidence under environmental pressure.

This is an active research prototype and local demo surface. The goal is not realistic fish biology. The goal is to make agent workflow evolution legible: behavior, morphology, evidence, lineage, and environment all participate in the loop.

## Inspiration and attribution

Aquagenesys was inspired by Dr. Daniel Hulme's 2003 master's thesis project, ALIS - Artificial Life Intelligence Simulator - a virtual fish tank exploring artificial life and intelligence. This project is an homage to that idea, not a copy, continuation, or reverse-engineering of ALIS. I do not have access to ALIS source code or implementation details, and Aquagenesys was built independently as a modern recursive agentic workflow sandbox: a bounded artificial ecology where agents survive, reproduce, inherit behavior hints, accumulate evidence, and evolve under environmental pressure.

## What this is

Aquagenesys is a working local simulation and viewer for experimenting with bounded agentic systems. Organisms act as small local agents with survival and reproduction pressure. The puddle environment supplies constraints, affordances, resource gradients, failure modes, recovery paths, and lineage history. The system is less about making realistic fish and more about exploring how agent workflows can evolve when behavior, morphology, evidence, and environment are all part of the same feedback loop.

## Recursive agent metaphor

Aquagenesys uses an artificial ecology to make a bounded recursive-agent loop visible:

- Fish / organism = agent.
- Morphology = capability surface.
- Behaviors = bounded tools/actions.
- Behavior selector = harness/orchestration layer.
- Puddle/ecology = evaluator/environment.
- Skill and lineage evidence = memory.
- Inheritance = recursive improvement channel.
- Lineage persistence = long-horizon success signal.

In real agent systems, the boundary between agent and harness is often blurry. Aquagenesys makes that boundary visible by splitting each organism into a capability surface, a bounded action set, and a behavior-selection layer. The fish is the agent; the behavior selector is the harness-like layer that mediates between goals, affordances, and environmental pressure.

Tool discovery is modeled as affordance-mediated action discovery. The global behavior library is bounded, but each organism's morphology and state determine which actions are viable, useful, or worth selecting. "Tools" means bounded biological actions such as graze, hunt, shelter, court, rest, scavenge, chemical defense, and filter-feed.

Aquagenesys does not claim open-ended self-modifying intelligence. The organisms do not rewrite arbitrary source code or invent unbounded new tools. Recursive improvement is modeled as a constrained loop: actions produce outcomes, outcomes become evidence, evidence affects inheritance or behavior priors, and descendants are tested again by the environment.

## What this is not

- It is not a biological realism simulator.
- It is not an implementation, reconstruction, continuation, or reverse-engineering of ALIS.
- It does not depend on LLM calls to keep the ecology alive.
- It does not claim that organisms are cognitively rich planners.
- It does not claim open-ended tool creation or arbitrary source-code rewriting.
- Current behavior is a bounded scorer over biological actions, not a full autonomous planning system.
- Skill evidence remains observational, but v0.4.2 uses deterministic evidence gates to decide which taught hints become heritable.

## Current capabilities

- Dirty-puddle / reef ecology with oxygen, pH, food, plankton, toxins, shelter, currents, waste, and decomposition.
- Adults, eggs, dormancy, hatching, death, extinction, and egg-bank recovery.
- Biological genomes with inherited traits and life-history strategy.
- Modular morphology affordances for body plans, feeding, movement, armor, toxins, sensory range, costs, and viability.
- Affordance-aware behavior that scores biological actions against local context.
- Bounded behavior/action library exposed as viable or low-viability tools per organism.
- Bounded instruction inheritance and taught behavior hints.
- Evidence-governed skill inheritance with confidence, evidence counts, and suppression reasons.
- Skill-use and descendant-outcome evidence tracking.
- Genealogy explorer for biology and behavior inheritance.
- Deterministic lineage story renderer that explains survival, inheritance, attempts, losses, and persistence without model calls.
- Optional bounded AI deliberation through the canonical `core.llm` interface; model output becomes short-lived intent and never controls the tick loop directly.
- FastAPI local viewer with compact `/api/frame`, full `/api/state`, and `/api/control`.
- Canvas reef UI with selected-organism portrait rendering.

## Demo quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m aquagenesys.web.app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

For deterministic local runs without model calls:

```bash
python -m aquagenesys.web.app --host 127.0.0.1 --port 8765 --no-deliberation
```

Useful local endpoints:

- `GET /api/state` - full ecology, organism, dashboard, genealogy, morphology, behavior, and lineage-story state.
- `GET /api/frame` - compact render/update payload for the Canvas viewer.
- `POST /api/control` - reset, speed, randomize, and AI deliberation controls.

The default optional model endpoint is OpenAI-compatible Lexi on `http://127.0.0.1:8008/v1` with model name `Lexi`. The simulation remains functional when that endpoint is absent or deliberation is disabled.

## Run public demo container

The demo container runs Aquagenesys as a local appliance suitable for Cloudflare Tunnel. It binds only to localhost and defaults to no-deliberation mode:

```bash
scripts/run_demo_container.sh
```

Default mapping:

```text
127.0.0.1:8782 -> container:8765
```

If `8782` is occupied, the script chooses the next free port from `8783`, `8784`, or `8785` and prints the selected origin. The compose file keeps Lexi/vLLM configured as an internal container-to-host route at `http://host.docker.internal:8008/v1`, but deliberation is off by default and port `8008` is not exposed by Docker.

For controlled Lexi/vLLM testing, restart the same container route with bounded AI deliberation enabled:

```bash
scripts/run_demo_container.sh --deliberation
```

This changes only the container launch mode. It still binds Aquagenesys to localhost, keeps model teaching disabled, and does not expose port `8008`.
The demo container gives Lexi up to 30 seconds per bounded deliberation call.

Useful commands:

```bash
docker compose -f docker-compose.demo.yml build
docker compose -f docker-compose.demo.yml up -d
scripts/stop_demo_container.sh
```

Cloudflare Tunnel origin target:

```bash
cloudflared tunnel --url http://127.0.0.1:8782
```

For a named tunnel, use service origin `http://127.0.0.1:8782` or the fallback port printed by the run script. Do not point Cloudflare at the container IP, host public IP, port `8008`, SSH, Docker, or any model endpoint.

Public-demo mode sets `AQUAGENESYS_PUBLIC_DEMO=true`. In that mode `/`, static assets, `/api/frame`, and `/api/state` remain reachable. `/api/control` allows speed changes but blocks reset, environment randomization, and AI-deliberation toggling with `403`. Cloudflare Access is still recommended for narrow sharing.

## What to watch for in the demo

- Watch organisms forage, shelter, hunt, court, reproduce, and die.
- Click an organism to inspect its morphology, affordances, behavior rationale, physiology, lineage, skill-inheritance status, and portrait.
- Compare organisms and notice that morphology changes what actions are cheap, plausible, or risky.
- Watch lineage persistence, extinction, egg-bank reserves, and dormant recovery.
- Look for skill hints that are inherited with confidence and for weak hints that are suppressed with reasons.
- Observe that the ecology can recover without debug founder reseeding.
- Treat optional AI deliberation as bounded and nonblocking; it is visible in telemetry but not required for survival.
- Read the lineage story cards for cautious, evidence-backed explanations of what persisted and what failed.

## Architecture

The CPU owns the puddle chemistry and physics. Fish are bounded local agents that mostly act through reflexes and affordance-aware behavior, with sparse optional AI deliberation routed through the local OpenAI-compatible endpoint when budget and pressure allow.

- `aquagenesys.environment.PuddleEnvironment` owns deterministic 2D world fields: temperature, oxygen, pH, turbidity, nutrients, light, currents, shelter, substrate, obstacles, food, plankton, waste, toxins, decomposition/detritus, reproduction support, population pressure, and ecological balance.
- `aquagenesys.agents.FishAgent` owns fish identity, body state, position, energy, hunger, fear, stress, health, reproductive drive, maturity/fertility state, memory, recent outcomes, model-call budget, and genome strategy.
- `aquagenesys.agents.FishGenome` owns inherited phenotype, life-history traits, and modular morphology.
- `aquagenesys.agents.morphology.MorphologyGenome` maps inherited body loci into primitive affordances and costs.
- `aquagenesys.agents.behavior` turns local perception, morphology affordances, physiology, inherited priors, and taught skills into bounded action candidates.
- `aquagenesys.agents.instructions.BehaviorInstructionGenome` owns bounded behavioral priors and taught skills. Skills are structured, short-lived by generation TTL, schema-validated, and cannot request shell, file, network, repo, server, tool, code-editing, teleport, death-disabling, or energy-bypass behavior.
- `aquagenesys.simulation.egg.EggEntity` represents independent eggs/embryos. Eggs carry both biological genome and instruction seed, persist after parent death, may enter dormancy, decay under hostile chemistry, and hatch under suitable low-pressure conditions.
- `aquagenesys.agents.FishDeliberationController` uses `core.llm.LLMClient` and `prompts/tasks/fish_deliberation_v0.3.md`; environment ticks never depend on model calls.
- `aquagenesys.web.app` serves the FastAPI API and static Canvas viewer.

Per fish tick:

```text
1. Sense local environment
2. Update internal state and lifecycle timers
3. Build affordance-aware behavior candidates
4. Let urgent reflexes override when needed
5. Optionally queue nonblocking AI deliberation when budget and pressure allow
6. Select action
7. Apply action to fish and environment
8. Attempt energy-costed reproduction if gates pass
9. Validate and inherit bounded offspring instruction seeds when reproduction succeeds
10. Update eggs/embryos and hatch viable eggs
11. Record outcome, lifecycle, behavior evidence, and compact lineage snapshots
```

## Instruction inheritance

Parent organisms can influence offspring behavior priors, but only through bounded schemas:

```text
parent strategy + taught skill proposal
-> schema validation and capability checks
-> evidence gate for taught skill inheritance
-> clamped instruction genome / supported skill seed
-> bounded offspring behavior bias
-> physics, energy, and ecology decide survivability
```

Instruction inheritance is enabled by default with `AQUAGENESYS_INSTRUCTION_INHERITANCE_ENABLED=true`. Model-generated teaching remains disabled by default with `AQUAGENESYS_MODEL_TEACHING_ENABLED=false`; the system does not require live Lexi success for instruction inheritance.

In v0.4.2, taught skills are not durable just because a parent carries them. Offspring inheritance records include a status, confidence, evidence counts, source lineage, and reason. Recent positive lineage-local evidence can preserve a hint; insufficient, stale, noisy, or negative evidence suppresses it.

Live LLM deliberation is action-only in the default path. The deliberation prompt can see compact taught-skill context, and a successful model intent can indirectly contribute to normal skill-use evidence if it executes an already skill-matched action, but it does not author durable skill patches or make inheritance decisions.

Instruction policy affects behavior modestly:

- cautious policies shelter earlier and prefer safe food
- bold policies tolerate more risk and can burn more energy
- kin-schooling policies bias school behavior
- energy-saver policies rest or reduce movement intensity
- novelty-seeking policies explore more when conditions allow

Instruction policy does not alter body mechanics, speed caps, energy accounting, reproduction rules, or death rules.

## Reproduction and recovery

Reproduction is not a single direct spawn. Mature fish pay energy into a brood. Life-history traits determine clutch size, reproduction cooldown, offspring investment, and whether the brood becomes live juveniles, eggs, or a mixed clutch. Normal reproduction requires mate contact with a compatible local organism. Offspring and eggs inherit biological genome plus a bounded instruction seed.

Some genomes carry a rare facultative parthenogenesis locus. A singleton fish without alleles cannot magically reproduce. A mature, healthy, mate-isolated fish with alleles may attempt an emergency clonal egg clutch, but the attempt is stochastic, energy-costed, usually egg-based, and carries viability/mutation-load penalties.

The egg bank is organic resilience, not rescue spawning:

```text
adult crash -> viable eggs remain -> biosphere_state=dormant
good chemistry + low pressure -> eggs may hatch
adults restored -> biosphere_state=active
no adults + no viable eggs -> biosphere_state=extinct
```

Deaths and waste feed local decomposition/detritus, nutrients, food, and plankton. Moderate detritus can support rebound; excessive waste can still depress oxygen or increase toxins.

## Viewer

The FastAPI viewer exposes `/api/state`, compact `/api/frame`, and `/api/control`. The browser polls `/api/frame` for lightweight movement and lifecycle metrics, interpolates fish motion with `requestAnimationFrame`, and keeps `/api/state` at a lower cadence for full environment fields.

- The puddle canvas remains the dominant visual surface.
- The right sidebar focuses on hovered/selected fish and optional two-fish comparison.
- The below-puddle observatory shows the ecology narrator, population/lifecycle dashboard, recovery evidence, morphology affordances, affordance-aware behavior, lineage/policy/teaching summaries, inherited behavior evidence, event timeline, and diagnostics.
- The genealogy explorer shows biology and behavior inheritance side by side for selected lineages.
- The lineage story renderer answers who survived, what they inherited, what changed, what they tried, what killed others, and why the lineage persisted.
- The AI deliberation control describes bounded AI reflections without requiring the viewer to know the internal Lexi/Qwen runtime name.
- `/api/state` includes dashboard, morphology, behavior, genealogy, and lineage story payloads.
- `/api/frame` remains compact and does not carry dashboard/story payloads.

Hover a fish for a quick preview. Click to focus one fish. Ctrl-click or command-click a second fish to compare body, lifecycle, policy, strategy, teaching history, current action, and relationship signals such as shared lineage, shared policy, feeding role, and proximity.

## Recovery assays

Programmatic seeded recovery assays live under `evals/recovery_assays.py`. They measure bottleneck recovery, egg-bank resilience, reproduction gates, density/crowding sanity, resource rebound, behavior-policy payoff, and optional AI deliberation.

Run them directly with:

```bash
python evals/recovery_assays.py --json
```

The assay contract checks that recovery does not use debug founder reseeding, egg-bank recovery does not create instant adults, low global population is not treated as global overcrowding, behavior policies change choices without changing physical capability, and live Lexi/Qwen success is not required.

## Archives

Fish state, memory, eggs, lifecycle events, instruction patch decisions, teaching events, offspring instruction inheritance, skill evidence, and compact agent code snapshots are externalized as JSONL under `/tmp/aquagenesys-v03` by default. Records include `run_id` so append-only archives can be segmented without mixing older runs.

Useful files:

- `fish_state.jsonl`
- `fish_memory.jsonl`
- `lifecycle_events.jsonl`

## Validation

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

## Documentation

- `docs/README.md` is the documentation index.
- `docs/decisions/` contains chronological architecture decisions.
- `reports/README.md` indexes generated implementation and validation reports.
- `reports/repo_cleanup_2026-05-28.md` records the latest conservative repository cleanup.

## Configuration

Runtime settings are centralized in `core/config.py` and may be provided with `AQUAGENESYS_*` variables. See `.env.example` for the full surface.

## Known limitations

- Behavior is a bounded heuristic scorer, not a general planner.
- Skill evidence is observational and does not prove causality; v0.4.2 uses it as a bounded inheritance gate, not as a causal claim.
- The system does not implement full sexual genetics or detailed embryology.
- Procedural art is polished enough for demo use but not final concept art.
- The ecology is designed for agentic systems metaphor and experimentation, not biological realism.
- There is no full interactive graph database, complete species tree, or model-written narrative.
- No explicit license file is currently included; treat the repository as view-only until a license is selected.
