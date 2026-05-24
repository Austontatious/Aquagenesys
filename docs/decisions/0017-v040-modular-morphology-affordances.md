# ADR 0017: v0.4.0 Modular Morphology Affordances

## Status

Accepted.

## Context

Earlier Aquagenesys genomes mostly expressed fish-variant traits: size, color, speed, fins, metabolism, and bounded instruction priors. That made lineages observable, heritable, and selectable, but most visible diversity still read as fish variants rather than materially different aquatic body plans.

v0.4.0 upgrades the biological genome with modular morphology loci. The intent is to preserve the existing architecture while making body plans mechanically meaningful:

```text
genes -> morphology modules -> primitive affordances -> costs -> visible bodies -> ecological selection
```

This is deliberately not the full behavior rewrite. Behavior remains mostly existing reflex, habit, and optional deliberation logic. The new layer answers what an organism can physically sense, attempt, survive, and pay for.

## Decision

Add `aquagenesys.agents.morphology` as a deterministic genotype-to-affordance interpreter. `FishGenome` now owns a `MorphologyGenome`, and every organism has a stable `morphology_hash`.

Morphology modules are grouped by body function:

- body scaffold: mass, axis, depth, surface area, soft tissue, reserves
- head/mouth: head mass ratio, mouth position, aperture, force, suction, gut capacity, filter surface
- appendage apparatus: count, length, flexibility, strength, propulsion surface
- armor/skin: armor density, spine density, tissue vulnerability, mucous barrier
- chemical apparatus: gland capacity, delivery efficiency, toxin resistance, self toxicity
- sensory surface: sensory area, chemical sensitivity, motion sensitivity, visual acuity
- development: stability, volatility, growth cost, juvenile fragility, reproduction cost, oxygen demand

The interpreter emits `MorphologyAffordances` with schema `aquagenesys.morphology_affordances.v1`. Outputs are primitive physical affordances and costs such as reach, grip, bite force, suction force, filter rate, armor protection, toxin payload, sensory range, drag, oxygen cost, metabolic burden, reproduction cost, juvenile fragility, feeding throughput, predation risk modifier, and viability index.

Observational labels are derived after interpretation for UI and story explanation. They are not species classes and do not drive behavior.

## API

`/api/state` moves to `aquagenesys.state.v11`. The state payload includes top-level `morphology` with schema `aquagenesys.morphology.v1`, per-organism loci summaries, compact affordances, labels, and aggregate morphology telemetry.

`/api/frame` remains `aquagenesys.frame.v3`. It does not include the full morphology state payload. It only carries compact phenotype morphology render hints already attached to each fish phenotype.

Lineage story moves to `aquagenesys.lineage_story.v3` so stories can include cautious morphology evidence.

## Mechanics

The simulation now uses primitive affordances where existing mechanics already had a simple hook:

- sensory range can extend sensing and neighbor/resource search
- drag, thrust, oxygen cost, and metabolic burden affect movement and stress costs
- filter, suction, scrape, reach, grip, and bite affordances affect local feeding access
- bite, strike, reach, armor, toxin, and predation risk affect simple predation outcomes
- growth cost, reproduction cost, juvenile fragility, oxygen cost, and viability affect life history, eggs, hatching, reproduction gates, and rare developmental failure

These hooks do not create behavior classes. A body may be physically good at filtering, biting, gripping, or chemical defense, but action choice is still handled by the current behavior layer.

## Rendering And Observability

Phenotype rendering now reads the same morphology that drives mechanics:

- head scale and mouth shape from head/mouth loci
- body proportions from body scaffold loci
- appendage count, length, flexibility, and strength from appendage loci
- armor plates and spines from armor/skin loci
- chemical markers from chemical gland and toxin payload

The observatory dashboard adds morphology summaries, notable body plans, affordance/cost chips for selected fish, and morphology language in genealogy and lineage story payloads.

Story language remains evidence-bounded. It may say a morphology was observed in survivors, persisted in a lineage, or was associated with higher costs. It does not claim morphology caused survival unless the state has direct evidence.

## Safety

The morphology system does not add hand-authored monster species, runtime code editing, organism tool access, rescue spawning, immortal organisms, free food, arbitrary adults, or LLM control over the simulation tick.

Weird forms are produced by inherited morphology loci and mutation. They pay costs through drag, oxygen demand, growth burden, reproduction burden, fragility, self toxicity, and viability pressure.

## Consequences

Aquagenesys can now produce visibly and mechanically different aquatic body plans while keeping old fish genomes compatible. The behavior layer can inspect affordances, but full affordance-aware decision-making remains deferred.

## Limits

v0.4.0 is still a scaffold:

- no full affordance-aware planner
- no evidence-governed skill promotion or suppression
- no lineage carrier-vs-non-carrier denominators for morphology
- no explicit niche diversity controller
- no model-generated behavior priors

Those belong in later patches, starting with v0.4.1.
