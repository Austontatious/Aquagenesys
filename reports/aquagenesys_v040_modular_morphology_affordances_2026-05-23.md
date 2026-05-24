# Aquagenesys v0.4.0 Modular Morphology Affordances

Date: 2026-05-23

## Initial State

- Branch: `main`
- Starting HEAD: `79161d8d00036543ea538fecb1cc85239c5a076b`
- Working tree at start: dirty with a validated but uncommitted v0.3.x/v10 skill-use evidence layer
- Baseline before v0.4.0 morphology: `/api/frame aquagenesys.frame.v3`, `/api/state aquagenesys.state.v10`, lineage story `aquagenesys.lineage_story.v2`

## Summary

v0.4.0 upgrades the biological genome from fish-variant traits into modular aquatic morphology loci. Genes now create body modules, modules are interpreted into primitive physical affordances, affordances impose costs and viability pressure, and the renderer/UI/story layers expose the same body facts without turning labels into behavior classes.

The core patch spine is:

```text
modular genes
-> affordances
-> costs
-> visible bodies
-> ecological selection
-> grounded explanation
```

## Morphology Architecture

New module:

- `aquagenesys/agents/morphology.py`

New schemas:

- morphology: `aquagenesys.morphology.v1`
- affordances: `aquagenesys.morphology_affordances.v1`

Morphology modules:

- body scaffold: mass, axis length/depth, surface area, soft tissue, reserves
- head/mouth: head mass ratio, mouth position, aperture, force, suction, gut, filter surface
- appendage apparatus: count, length, flexibility, strength, propulsion surface
- armor/skin: armor density, spine density, vulnerability, mucous barrier
- chemical apparatus: gland capacity, delivery, toxin resistance, self toxicity
- sensory surface: sensory area, chemical sensitivity, motion sensitivity, visual acuity
- development: stability, mutation volatility, growth cost, juvenile fragility, reproduction cost, oxygen demand

## Affordance Interpreter

`interpret_morphology()` maps loci into primitive affordances and costs:

- reach, grip, strike impulse
- bite force, suction force, filter rate, scrape rate
- armor protection, tissue vulnerability
- toxin payload, delivery, resistance, self cost
- sensory range, chemical sense, motion sense
- drag, thrust modifier, turn penalty
- oxygen cost, metabolic burden, growth cost, reproduction cost, juvenile fragility
- feeding throughput, predation risk modifier, viability index

The interpreter does not emit behavior strategies such as predator, grazer, or species class. Human-readable labels are derived afterward for explanation only.

## Cost And Viability Model

Weird bodies pay visible and mechanical costs:

- large heads increase bite force but add drag, oxygen demand, turn penalty, juvenile fragility, and reproduction burden
- appendage amplification increases reach and grip but increases drag, growth cost, vulnerability, and oxygen demand
- armor increases protection but adds drag, metabolic cost, oxygen demand, and reproduction cost
- chemical glands increase payload and deterrence but add self toxicity, metabolic burden, growth cost, and reproduction cost
- soft bodies grow cheaply and can be flexible, but increase tissue vulnerability and predation risk
- bulk filter forms can remain viable when throughput and reserves offset their mass and oxygen costs

The model avoids hard banning weirdness except through bounded values and physical cost pressure.

## Inheritance And Mutation

`FishGenome` now includes `morphology: MorphologyGenome`. Founder genomes derive morphology from legacy fish traits, so existing fishlike organisms remain compatible.

Offspring inherit morphology through the existing reproduction path. Mutation now includes ordinary drift plus rare module-level shifts:

- appendage amplification/reduction
- head specialization
- filter specialization
- armor amplification
- chemical duplication
- soft-body shift
- sensory expansion
- developmental instability

Every morphology has a deterministic `morphology_hash`, and hash changes track inherited morphology changes in genealogy/story outputs.

## Rendering Changes

The canvas renderer uses compact phenotype morphology hints:

- head scale and mouth shape from head/mouth loci
- body proportions from body scaffold loci
- appendage count/length/flexibility/strength from appendage loci
- armor plates and spines from armor/skin loci
- chemical glow markers from chemical apparatus and toxin payload

`/api/frame` remains lightweight and does not include full morphology state.

## API And Schemas

- `/api/state`: `aquagenesys.state.v11`
- `/api/state.morphology`: `aquagenesys.morphology.v1`
- `/api/state.lineage_story`: `aquagenesys.lineage_story.v3`
- `/api/frame`: `aquagenesys.frame.v3`
- dashboard: `aquagenesys.dashboard.v2`
- genealogy: `aquagenesys.genealogy.v1`

State morphology payload includes:

- per-organism morphology hash
- loci summaries
- compact affordances
- observational labels
- aggregate morphology counts, average viability, average drag, average feeding throughput, high-cost count, low-viability count, and top labels

## Dashboard And Story Integration

The observatory now exposes morphology:

- aggregate morphology panel
- selected-fish morphology label
- selected-fish affordance chips
- selected-fish cost chips
- genealogy capability metadata
- lineage story morphology evidence and cautious persistence language

Story claims are bounded. The story can report that a morphology was observed in survivors or persisted through a window; it does not claim causal survival from labels alone.

## Example Morphologies

Generated deterministic interpreter examples:

- `morph_40ca843ff4e2`: generalized/force-mouthed aquatic body plan, bite force `0.391`, drag `0.276`, viability `0.621`
- `morph_67504c25cc32`: large-headed bite specialist, bite force `0.925`, oxygen cost `0.543`, viability `0.646`
- `morph_43a569388566`: tiny-headed bulk filterer / bulk-bodied filter grazer, filter rate `0.834`, feeding throughput `0.750`, viability `0.744`
- `morph_72634e75f7aa`: appendage-rich soft-bodied organism, reach `0.890`, grip `0.677`, predation risk modifier `1.252`, viability `0.529`
- `morph_5eddf174c37f`: chemical-defense specialist, toxin payload `0.647`, predation risk modifier `0.843`, viability `0.574`

## Tests And Evals

Added:

- `tests/test_morphology_affordances.py`

Coverage categories:

- morphology construction, bounds, and stable hashes
- affordance interpreter directionality
- cost and viability tradeoffs
- inheritance and mutation through reproduction
- rendering data from morphology loci
- `/api/state` morphology exposure and `/api/frame` bloat guard
- ecology cost and feeding interaction smoke

Updated:

- state schema expectations to `aquagenesys.state.v11`
- lineage story schema expectations to `aquagenesys.lineage_story.v3`
- eval schema gates to require morphology on the baseline case

## Validation Status

Targeted validation already passed during implementation:

```text
python3 -m pytest -q tests/test_morphology_affordances.py
# 7 passed

python3 -m pytest -q tests/test_aquagenesys_v03.py tests/test_life_history_egg_bank.py tests/test_genealogy_explorer.py tests/test_lineage_story_renderer.py tests/test_observatory_dashboard.py tests/test_skill_evidence_tracking.py
# 38 passed

python3 evals/runner.py --check
# pass

python3 -m pytest -q tests/test_codex_standards.py --noconftest
# 9 passed

node --check aquagenesys/web/static/app.js
# pass
```

Full validation completed:

```text
python3 -m pytest -q tests
# 64 passed

python3 evals/runner.py --check
# pass

python3 evals/runner.py
# pass; wrote eval results to evals/last_results.json

python3 evals/recovery_assays.py --json
# pass; recovery_rate=1.0, no_god_mode_reseed=true, mechanics_tuning_recommended=false

make lint
# pass

python3 -m pytest -q tests/test_codex_standards.py --noconftest
# 9 passed

node --check aquagenesys/web/static/app.js
# pass
```

Browser smoke on `127.0.0.1:8774` loaded `Aquagenesys v0.4.0`, returned `/api/state aquagenesys.state.v11`, showed morphology/recovery/genealogy/story panels, rendered a nonblank canvas, updated the selected fish morphology panel, opened compare mode with Ctrl-click, showed morphology frame signals such as filter-slot mouths, larger heads, armor density, appendage count, and chemical markers, and produced no console warnings or errors. A 390px mobile viewport had no horizontal overflow.

## Limitations

- The behavior layer can see affordances but does not yet perform full affordance-aware action selection.
- Labels remain simple deterministic summaries, not species or strategy classes.
- Morphology selection pressure is coupled through existing simple ecology mechanics rather than a richer niche model.
- No carrier-vs-non-carrier morphology denominators are added yet.
- No evidence-governed skill promotion/decay/suppression is added in this patch.

## Deferred To v0.4.1+

- affordance-aware behavior selection
- evidence-governed skill inheritance
- lineage fitness denominators
- niche/diversity/anti-convergence tracking
- optional model-generated durable behavior priors
