# Aquagenesys Agent Mechanics Explainer

Scope: code-grounded explanation of the current Aquagenesys/Dirty Puddle agent system in `/mnt/data/Aquagenesys`.

Version note: the handoff remembered v0.3.8 as current and v0.3.9 as next. The local repo is already at `79161d8 feat: add lineage story renderer`, the web app title is v0.3.9, `/api/state` is `aquagenesys.state.v9`, `/api/frame` is `aquagenesys.frame.v3`, dashboard is `aquagenesys.dashboard.v2`, genealogy is `aquagenesys.genealogy.v1`, and lineage story is `aquagenesys.lineage_story.v1`.

No external papers were used for this report. The comparison section uses only the conceptual anchors requested in the prompt.

## 1. Executive Summary

Aquagenesys currently implements a bounded embodied fish-agent ecology. An "agent" is a `FishAgent` dataclass with a biological genome, a behavior instruction genome, local physiological state, short recent memory, optional short-lived model intent, and lineage metadata. Agents do not own the world. The CPU simulation owns water chemistry, resources, population pressure, eggs, death, reproduction, and telemetry.

The real self-improvement loop is not a single LLM self-editing loop. It is a layered ecological inheritance loop:

1. A fish senses local chemistry, food/plankton, shelter, neighbors, prey/threats, crowding, reproduction quality, and edge/current vectors.
2. It updates hunger, stress, fear, health, age, and reproductive drive.
3. It chooses an action through reflex rules first, then habit/instruction rules, then optional short-lived model intent if one has completed.
4. The action changes position, energy, hunger, health, consumed resources, waste, oxygen, predation, and sometimes reproduction.
5. Reproduction creates live offspring or eggs carrying a mutated biological genome and a mutated behavior instruction genome.
6. Parent experience can produce bounded taught skills that bias offspring instruction genomes.
7. Eggs and adults survive or die under ecological constraints. Survivors and egg banks determine which genes and policies remain visible.

The strongest implemented self-improvement mechanisms are genetic evolution, instruction/policy inheritance, bounded parent-child teaching, ecological selection, and egg-bank recovery. The weakest parts are individual learning, causal attribution from taught skill to survival, multi-parent inheritance, explicit fitness scoring, and long-horizon evidence that a policy lineage improved rather than merely persisted.

## 2. What Counts as an Agent in Aquagenesys

### Aquagenesys agent definition

- Entity: `FishAgent` in `aquagenesys/agents/fish.py:546`.
- State: identity, lineage, generation, parent ids, genome, instruction genome, taught skills, position/velocity, energy, hunger, fear, stress, health, reproductive drive, age, reproduction cooldown, model budget/pending/intent, memory, recent outcomes, last perception, last decision, locomotion, and alive flag.
- Sensors: `Perception` in `aquagenesys/agents/fish.py:460`, produced by `AquagenesysSimulation._sense` in `aquagenesys/simulation/engine.py:337`.
- Drives: hunger, fear, stress, health, reproductive drive, energy, maturity/fertility state, memory of recent outcomes, and instruction-genome priors.
- Actions: `forage`, `eat`, `hunt`, `flee`, `shelter`, `court`, `school`, `explore`, `rest`, `escape`; model deliberation is restricted to the same allowed action set in `aquagenesys/agents/deliberation.py:13`.
- Memory: `FishMemory` stores recent action/outcome/energy/health deltas and is trimmed to `genome.memory_span`; see `aquagenesys/agents/fish.py:510`.
- Policy: reflex rules plus `heuristic_action`, parameterized by `BehaviorInstructionGenome`; optional model actions become short-lived `model_intent`.
- Environmental effects: movement, oxygen consumption, waste production, resource/plankton/nutrient consumption, predation deaths, detritus on death, reproduction, eggs, dormant eggs, hatchlings, and population pressure.
- Persistence: in-memory across ticks; snapshots and lifecycle events are externalized to JSONL by `FishArchive` in `aquagenesys/storage/archive.py:17`.

### Core organism structure

The active organism/fish data structure is `FishAgent`:

- Identity: `fish_id`, `species_id`, `lineage_id`, `generation`, `parent_ids`.
- Biological body: `genome: FishGenome`.
- Behavioral inheritance: `instruction_genome: BehaviorInstructionGenome`, `taught_skills`, `instruction_inherited_from`, accepted/rejected patch ids.
- Runtime physiology: `x`, `y`, `vx`, `vy`, `energy`, `hunger`, `fear`, `stress`, `health`, `reproductive_drive`, `age`.
- Runtime deliberation: `model_budget`, `deliberation_cooldown`, `model_intent`, `model_intent_ttl`, `last_model_decision`, `model_pending`.
- Runtime memory: `FishMemory.events`, `recent_outcomes`, `last_perception`, `last_decision`.
- Runtime biomechanics: `heading`, `turn_rate`, `swim_phase`, `tail_beat`, `body_wave`, `locomotion_speed`, `stride`.
- Lifecycle: `reproduction_cooldown`, `last_reproduction_tick`, `last_reproduction_gate`, `alive`.

Persistent across ticks in the simulation: identity, genome, instruction genome, taught skills, position, velocity, physiological state, age, reproduction state, memory, recent outcomes, model budget/cooldown/pending/intent, locomotion state, and alive state.

Transient or short-lived runtime state: current `Perception`, current action decision, model futures in `_pending_model_calls`, `model_intent_ttl`, recent event deques, and telemetry counters. `last_perception` and `last_decision` persist only as recent state for inspection and context, not as durable learned policy.

Persisted to disk: snapshots of fish/eggs, decisions, lifecycle events, compact code-lineage snapshots, and dead-agent summaries are appended under the configured archive directory, default `/tmp/aquagenesys-v03`; see `aquagenesys/storage/archive.py:17`.

### API exposure

`/api/state` returns full state from `AquagenesysSimulation.state` in `aquagenesys/simulation/engine.py:1733`. It includes full environment fields, full fish payloads, eggs, telemetry, dashboard, genealogy, and lineage story.

`/api/frame` returns compact frame state from `AquagenesysSimulation.frame_state` in `aquagenesys/simulation/engine.py:1813`. It excludes full environment fields, genealogy, and lineage story.

Fish fields exposed in `/api/state`: full `FishAgent.payload`, including full genome, life history, full instruction genome, taught skills, memory summary/recent memory, perception, decision, phenotype with mechanics, locomotion, and model intent.

Fish fields exposed in `/api/frame`: compact `FishAgent.frame_payload`, including identity, position, physiology, compact life history, compact genome, compact instruction, compact phenotype, locomotion, decision, active/model intent, and recent outcomes.

Egg fields exposed in `/api/state`: full `EggEntity.payload`, including biological genome, instruction genome, taught skills, phenotype, hatch sensitivity, decay, and created tick.

Egg fields exposed in `/api/frame`: compact egg payload only.

## 3. Organism State and Decision Loop

### One organism tick

One simulation tick is implemented in `AquagenesysSimulation.step` in `aquagenesys/simulation/engine.py:199`.

1. Increment simulation tick.
2. Update the environment fields with diffusion, resource cycles, waste/decomposition, oxygen, nutrients, plankton, food, toxins, turbidity, pH, population pressure decay, reproduction score, balance, and environment events.
3. Poll completed model deliberation futures. Successful model results become bounded short-lived `model_intent`; failures become telemetry.
4. Update eggs before adults. Eggs age, decay, enter dormancy, die, or hatch.
5. If no adults remain, debug reseed is considered only if explicitly enabled, then dormant/extinct handling runs.
6. Apply adult population pressure to the environment.
7. Shuffle fish order.
8. For each fish, build `Perception`.
9. Update internal state: age, cooldowns, hunger, stress, fear, reproductive drive, health.
10. Select action: reflex action if urgent, otherwise habit action, optionally replaced by a completed model intent. If gates allow, queue a future model deliberation but keep the habit action for the current tick.
11. Apply action: update movement/locomotion, energy, health, oxygen consumption, waste, feeding, hunting, shelter/rest effects.
12. Record memory and decision telemetry.
13. Attempt reproduction through explicit gates. Successful reproduction creates live children and/or eggs.
14. Check death cause.
15. After all fish are processed, recycle deaths into detritus/nutrients/waste and compact dead summaries.
16. Add newborns and eggs, enforcing max population.
17. Handle no-adult dormant/extinct state.
18. Archive snapshots/decisions when due.

### Decision sources

Decision order for each fish:

1. `FishAgent.reflex_action`: hard survival-biased rules for critical health, hostile chemistry, fear/threat, and near-starvation.
2. `FishAgent.heuristic_action`: rule policy parameterized by instruction genome and current drives.
3. Existing `model_intent`: if a previous model call has completed and TTL remains, it replaces the habit action.
4. Optional future model queue: if deliberation gates pass, a nonblocking future is queued for later ticks.

This means current decisions are mixed:

- Deterministic/rule-based: reflex and most habit logic.
- Stochastic: fish order shuffle, exploration vectors, reproduction chance, mutation, parthenogenesis trigger, hunting rolls, egg hatch rolls.
- Inherited: biological genome and instruction genome shape behavior.
- Model-assisted: optional sparse model calls, but only as bounded actions and only if they complete before TTL use.
- Not online-learned in the strong sense: no weights, rules, or instruction genome are updated from individual reward during ordinary action selection. Individual recent outcomes influence some rules.

### Drive effects

Hunger:

- Rises each tick with a body-size term and drops with feeding.
- Near starvation triggers reflex `eat`.
- Moderate hunger biases `forage`; metabolism determines whether food, plankton, decomposition, or hunting is relevant.
- Hunger contributes to body state and health loss when high.

Fear and stress:

- Stress blends local environmental stress into internal state.
- Fear is driven by nearby threats and stress.
- High fear triggers `shelter` or `flee` depending on instruction `threat_strategy` and `risk_posture`.
- Stress directly costs energy/health and can cause shock death.

Fertility and reproduction:

- `reproductive_drive` rises only when resources, health, and fertility state allow.
- Instruction `reproduction_strategy` adds small bias.
- `court` is selected only when drive, reproduction score, and mate proximity are favorable.
- Actual reproduction is gated by age, cooldown, energy, health, drive, reproduction score, crowding, mate contact, or parthenogenesis pressure.

Age and lifecycle:

- Age increments each tick.
- `LifeHistoryProfile` derives juvenile/mature/senescent and immature/fertile/late/too-old states.
- Age can block reproduction and eventually cause stochastic age death.

Nearby organisms:

- Nearby compatible fish influence `nearest_mate` and schooling/courtship.
- Smaller nearby fish can be prey for predators.
- More aggressive/larger nearby fish can be threats.
- Population pressure affects stress and reproduction score.

Food, algae/plankton, detritus, nutrients:

- There is no separate field named algae. The closest implemented lower-trophic fields are `plankton`, `food`, `nutrients`, `decomposition`, and `waste`.
- Filter feeders target `plankton`; scavengers target `decomposition`; predators may hunt and also can consume `food`; grazers/omnivores consume `food`.
- Death adds detritus through `add_detritus`, increasing decomposition, nutrients, and waste.

Oxygen, temperature, and environment:

- `CellSample.stress_score` combines oxygen deficit, pH mismatch, temperature mismatch, turbidity excess, toxins, and crowding.
- Fish consume oxygen and add waste.
- Environmental stress reduces health and energy.
- Egg survival and hatching also depend on oxygen, toxins, food/plankton, reproduction score, and population pressure.

### Compact diagram

```text
environment state
    |
    v
organism sensors / local context
    |
    v
internal state / drives
    |
    v
reflex rules -> habit policy + instruction genome -> optional model intent
    |
    v
action: move/feed/hunt/shelter/rest/court/school/explore
    |
    v
environment update: resources, oxygen, waste, detritus, pressure, deaths, eggs
    |
    v
organism state update: memory, energy, health, age, reproduction, lineage
    |
    v
inheritance through live offspring or eggs
```

## 4. Genetics and Phenotype Mechanics

### Genetics representation

Biological genes are fields on immutable `FishGenome` in `aquagenesys/agents/fish.py:48`. Founder genomes are generated by `FishGenome.founder` from archetype templates plus jitter. Offspring genomes are produced by `FishGenome.mutated`.

Inheritance is single-parent in the active implementation. A nearby compatible mate is required for paired reproduction, but the child's genome is a mutation of the reproducing parent's genome; there is no implemented two-parent recombination.

Mutations are stochastic and bounded:

- Most numeric genes receive Gaussian drift and are clamped.
- Categorical metabolism/body/tail/fin/pattern mutate at low probabilities.
- Parthenogenesis alleles can drift up/down within 0..4.
- Mutation load is recalculated from parent load and new random noise.
- No mutation currently uses environmental conditions directly, except environment affects who survives/reproduces.

### Gene / trait table

| Gene / trait | Source file | Inherited? | Mutates? | Affects phenotype? | Affects behavior? | Affects survival/reproduction? | Tradeoff? | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `archetype` | `aquagenesys/agents/fish.py:49` | yes | indirectly on lineage split | yes | indirectly | indirectly | medium | Founder archetype sets base trait bundle. |
| `species_id` | `aquagenesys/agents/fish.py:50` | yes | on lineage split | no | mate compatibility | yes | low | Compatibility uses species/metabolism heuristics. |
| `lineage_id` | `aquagenesys/agents/fish.py:51` | yes | split chance | no | telemetry only | lineage tracking | none | Identity/evaluation label, not a mechanic by itself. |
| `body_size` | `aquagenesys/agents/fish.py:52` | yes | yes | size/body length | energy cost, predation | lifecycle, radius, energy, predation | high | Larger can hunt/survive predation but costs more and changes clutch/life history. |
| `max_speed` | `aquagenesys/agents/fish.py:53` | yes | yes | body length | movement capability | escape/hunt/energy via movement | medium | Higher speed improves movement but can increase movement energy spent indirectly. |
| `turning` | `aquagenesys/agents/fish.py:54` | yes | yes | mechanics | movement | navigation/escape | low | Used in turn capacity. |
| `metabolism` | `aquagenesys/agents/fish.py:55` | yes | low-probability category | indirect | feeding and hunting | resource niche, life history | high | Grazer/filter/scavenger/predator/omnivore target different resources. |
| `oxygen_need` | `aquagenesys/agents/fish.py:56` | yes | yes | no | stress reflex indirectly | stress/death | high | Higher need makes hypoxia worse. |
| `ph_preference` | `aquagenesys/agents/fish.py:57` | yes | yes | no | stress reflex indirectly | stress/death | medium | Best value depends on environment. |
| `temperature_preference` | `aquagenesys/agents/fish.py:58` | yes | yes | no | stress reflex indirectly | stress/death | medium | Best value depends on environment. |
| `turbidity_tolerance` | `aquagenesys/agents/fish.py:59` | yes | yes | no | stress reflex indirectly | stress/death | medium | Useful in muddy/high-waste conditions. |
| `toxin_tolerance` | `aquagenesys/agents/fish.py:60` | yes | yes | no | stress reflex indirectly | stress/death/egg death | medium | Useful in toxic puddles. |
| `risk_tolerance` | `aquagenesys/agents/fish.py:61` | yes | yes | no | founder instruction, reflex thresholds | exposure vs opportunity | high | Cautious/bold policy seed derives from it. |
| `sociality` | `aquagenesys/agents/fish.py:62` | yes | yes | no | schooling/mate behavior | mate proximity, senescence | medium | Helps schooling but crowding can hurt. |
| `aggression` | `aquagenesys/agents/fish.py:63` | yes | yes | no | hunting/threat relations | predation and being perceived as threat | medium | Helps attack; may increase local danger dynamics. |
| `curiosity` | `aquagenesys/agents/fish.py:64` | yes | yes | no | exploration intensity/strategy | finding resources | medium | Exploration can find resources or waste energy. |
| `reproduction_rate` | `aquagenesys/agents/fish.py:65` | yes | yes | no | reproductive drive | maturity, clutch, interval, lifespan | high | More reproduction shortens/reshapes life history. |
| `sensory_range` | `aquagenesys/agents/fish.py:66` | yes | yes | no | perception radius | food/mate/threat detection | medium | Larger sensing can find resources/mates; no explicit cost. |
| `deliberation_chance` | `aquagenesys/agents/fish.py:67` | yes | yes | no | model call chance | indirect | medium | Model calls are optional and may fail; budget-limited. |
| `memory_span` | `aquagenesys/agents/fish.py:68` | yes | yes | no | memory summary and skill slots | indirect | low | Longer memory can enable more instruction slots. |
| `color`, `accent_color` | `aquagenesys/agents/fish.py:69` | yes | yes | visible | no | no | none | Cosmetic in mechanics. |
| `body_shape`, `tail_shape`, `fin_shape`, `pattern` | `aquagenesys/agents/fish.py:71` | yes | low-probability category | visible | no direct | no direct | mostly cosmetic | Shape labels mostly render; numeric depth/tail/fin affect mechanics. |
| `body_depth` | `aquagenesys/agents/fish.py:75` | yes | yes | body depth | drag/speed cap | energy/motion | high | Higher depth increases drag but affects visual/body form. |
| `tail_length` | `aquagenesys/agents/fish.py:76` | yes | yes | tail length | thrust/acceleration/locomotion | movement | medium | More thrust; no strong explicit cost except mutation balance. |
| `fin_span` | `aquagenesys/agents/fish.py:77` | yes | yes | fins | maneuver/turn/lateral damping | movement | medium | More maneuvering; no strong explicit cost. |
| `pattern_density`, `pattern_contrast` | `aquagenesys/agents/fish.py:78` | yes | yes | markings | no | no direct | mostly cosmetic | Contrast contributes only to phenotype mechanics visibility payload, not predation. |
| `iridescence` | `aquagenesys/agents/fish.py:80` | yes | yes | shine | no | no direct | mostly cosmetic | Visibility is calculated for payload only. |
| `camouflage` | `aquagenesys/agents/fish.py:81` | yes | yes | visible | no | no direct | mostly cosmetic | Not yet used to affect predation/threat detection. |
| `eye_scale`, `barbel_length` | `aquagenesys/agents/fish.py:82` | yes | yes | visible | no | no direct | mostly cosmetic | Rendered, not currently sensors. |
| `dormancy_bias` | `aquagenesys/agents/fish.py:84` | yes | yes | no | no direct | egg probability/dormancy/life history | high | Preserves lineage but can delay hatch. |
| `egg_viability_ticks` | `aquagenesys/agents/fish.py:85` | yes | yes | no | no | egg survival window | medium | Helps egg bank persistence. |
| `parthenogenesis_alleles` | `aquagenesys/agents/fish.py:86` | yes | yes | no | no | singleton reproduction | high | Helps bottlenecks but parthenogenetic offspring lose viability. |
| `parthenogenesis_bias` | `aquagenesys/agents/fish.py:87` | yes | yes | no | no | parthenogenesis chance | high | Same as above. |
| `mutation_load` | `aquagenesys/agents/fish.py:88` | yes | yes | no | instruction mutation rate seed | egg viability, parthenogenesis, decay | high | Higher load harms viability but increases policy mutation rate through founder instruction seeding. |

### Phenotype mechanics

`FishGenome.phenotype_payload` in `aquagenesys/agents/fish.py:341` converts genes into visible/rendered traits: body shape, pattern, tail, fins, body length/depth, tail length, fin span, stripe/spot counts, pattern density/contrast, iridescence, camouflage, eye scale, barbel length, and colors.

Full state includes a mechanics summary: thrust, maneuver, drag, visibility. The actual movement code directly uses genome fields `tail_length`, `body_depth`, `fin_span`, `body_size`, `max_speed`, and `turning` in `_apply_action`, rather than consuming the phenotype mechanics payload.

Visible in UI: body shape, tail, pattern, fin span, camouflage, color, locomotion, policy, life history, and egg traits.

Mechanically meaningful today:

- Movement: body size/depth, tail length, fin span, max speed, turning.
- Feeding: metabolism, sensory range, aggression/body size for hunting.
- Reproduction: reproduction rate, dormancy bias, egg viability, parthenogenesis traits, mutation load, body size, sociality.
- Survival: tolerances, oxygen need, body size/speed/aggression/risk, energy costs, egg viability.
- Behavior/policy: risk tolerance, sociality, aggression, curiosity, reproduction rate, deliberation chance, memory span, metabolism influence founder instruction genome.

Cosmetic or weakly mechanical today:

- Color/accent, categorical pattern/body/tail/fin labels, iridescence, camouflage, eye scale, barbels are mostly visual. Some numeric tail/fin/body traits matter; camouflage/visibility do not yet affect predation or detection.

Current genotype-to-agent pathway:

```text
FishGenome fields
  -> phenotype payload and life-history profile
  -> movement/resource/reproduction/stress constraints
  -> founder BehaviorInstructionGenome seed
  -> reflex/habit action affordances
  -> survival, reproduction, eggs, and lineage persistence
```

## 5. Behavior Policy Mechanics

Behavior policy is split between fixed code and inherited priors:

- Fixed reflex rules live in `FishAgent.reflex_action`.
- Fixed habit rules live in `FishAgent.heuristic_action`.
- Inherited behavior priors live in `BehaviorInstructionGenome`.
- Taught skills can bias the inherited instruction genome at reproduction.
- Optional model deliberation can return one bounded action JSON payload, but it does not rewrite policy.

`BehaviorInstructionGenome` fields:

- `risk_posture`
- `forage_strategy`
- `threat_strategy`
- `social_strategy`
- `reproduction_strategy`
- `exploration_strategy`
- `energy_strategy`
- `teaching_style`
- `memory_bias`
- `model_deliberation_bias`
- `allowed_skill_slots`
- `mutation_rate`
- `risk_bias`
- `energy_bias`
- patch lineage metadata

How it affects behavior:

- `risk_posture` changes fear thresholds and cautious shelter behavior.
- `forage_strategy` changes food vs shelter blending, opportunistic plankton weighting, or memory-success rationale.
- `threat_strategy` changes shelter/freeze/flee behavior.
- `social_strategy` changes schooling behavior.
- `reproduction_strategy` changes reproductive-drive increment.
- `exploration_strategy` changes exploratory direction and novelty intensity.
- `energy_strategy` changes movement intensity and rest/conserve behavior.
- `model_deliberation_bias` changes model queue chance.

The policy is bounded by enums and clamps. It cannot change physics constants, death rules, resource fields, file access, shell access, or code.

## 6. Parent-Child Teaching and Instruction Inheritance

### Current teaching/inheritance mechanism

- Genetic inheritance: offspring receive a mutated copy of the parent's `FishGenome`; no mate recombination is implemented.
- Behavioral inheritance: offspring receive a mutated copy of the parent's `BehaviorInstructionGenome`.
- Instruction genome: bounded enum/numeric policy seed that biases reflex/habit/model-gating behavior.
- Taught skills: bounded `TaughtSkill` objects that can be inherited and can bias the child's instruction genome.
- Transfer trigger: reproduction only, through `_offspring_instruction_seed` in `aquagenesys/simulation/engine.py:1037`.
- Transfer constraints: instruction inheritance can be disabled globally; skills obey slot caps, TTLs, confidence/decay filtering, enum validation, forbidden-token rejection, text length caps, and payload complexity caps.
- Decay/limits: inherited skills expire by generation during inheritance selection; allowed skill slots are clamped 0..4; taught skill TTL is clamped 1..5 generations.
- Evidence recorded: instruction log, lifecycle events, telemetry counters, policy hashes, patch ids, accepted/rejected patch counts, skill counts, and compact code snapshots.
- Missing evidence: no direct causal field records "this skill was used" or "this skill improved fitness"; skill hashes are not exposed richly in the bounded genealogy view; duplicate same-tick patches can occupy slots because there is no skill deduplication.

### What parents can pass

Parents can pass:

- Biological genome mutation.
- Instruction genome mutation.
- Taught skills inherited from their own parents if still valid.
- Newly rule-generated taught skills based on the parent's recent memory/state/population context.

Parent teaching is separate from genetic inheritance. It is automatic and conditional inside reproduction, not an explicit action that consumes a tick. It currently has no direct energy, time, risk, or opportunity cost beyond reproduction itself.

Multiple parents do not contribute genetically or behaviorally. A mate can satisfy reproduction gating, but the child is generated from the reproducing parent's genome and instruction seed. Non-parent organisms do not teach.

Bad behavior can be taught if it fits the bounded schema. The eval runner has a `bad_teaching` scenario that accepts a burst-style energy bias while preserving physics and death rules. Forbidden behavior such as shell/filesystem/network/death disabling is rejected by `validate_instruction_patch`.

### How taught skills work

`TaughtSkill` is defined in `aquagenesys/agents/instructions.py:75`. It contains source parent/lineage, created tick, generation created, skill type, trigger, action bias, confidence, energy/risk bias, memory bias, TTL generations, decay, rationale tag, and patch id.

Acquisition paths:

- A parent can receive a safe patch through `propose_offspring_instruction_patch`.
- More commonly, `rule_generated_patch` creates a proposal during reproduction when parent memory/state matches one of four patterns:
  - recent feeding success -> forage skill
  - sheltered/fearful survival -> threat skill
  - lineage/adult bottleneck -> reproduce skill
  - high-energy novelty seeker -> explore skill
- Accepted skills can be appended to the parent and offspring when slots allow.

Influence path:

```text
TaughtSkill
  -> BehaviorInstructionGenome.with_skill_bias
  -> changed enum/numeric instruction policy
  -> FishAgent.heuristic_action / reflex thresholds / reproduction-drive bias
```

The fish behavior code does not dynamically check a skill's trigger every tick. Instead, accepted skills alter the instruction genome at inheritance time. The model deliberation context also receives compact taught skills, but model teaching is disabled by default and model outputs are action-only.

### Concrete example from code execution

I ran a deterministic in-repo simulation using the same setup pattern as `tests/test_instruction_inheritance.py`. Parent fish `#1` had two recent `fed` memory outcomes, which triggered a forage teaching proposal during reproduction.

Example result:

- Parent `#1` policy hash: `746cc7a6736f8e73`, label `balanced`.
- Reproduction result: `egg_bank_deposited`, mode `paired`.
- Target egg `#1` lineage: `L3`, generation `1`.
- Target egg inherited-from policy hash: `746cc7a6736f8e73`.
- Target egg policy hash: `60e53452b059d106`, label `cautious`.
- Target taught skill: `forage`, trigger `low_energy`, action bias `nearest_food`, TTL `2`.
- Instruction telemetry after that forced reproduction: `patches_accepted=2`, `inheritance_events=8`.

What changed mechanically: the offspring's instruction genome policy hash changed through mutation and skill bias; future behavior can change because policy fields feed `heuristic_action` and reflex thresholds. What is not proven by that example: that the skill improved survival. The system records transfer and later outcomes, but not causal skill payoff.

## 7. Lifecycle, Reproduction, Dormancy, and Recovery

### Lifecycle/recovery mechanics

- Birth: founders are seeded by reset/start only; live births and egg hatches create new `FishAgent` instances.
- Growth: fish age by one tick per update; life history determines juvenile/mature/senescent and fertility states.
- Adult behavior: adults sense, act, feed/hunt/shelter/rest/court/school/explore, reproduce, and die.
- Fertility: reproduction requires maturity, not too old, no cooldown, sufficient energy/health/drive, acceptable local reproduction score, low enough crowding, and mate contact or parthenogenesis pressure.
- Reproduction: `_maybe_reproduce` computes chance and energy budget, then creates a clutch of live offspring and/or eggs.
- Eggs: `EggEntity` carries genome, instruction genome, taught skills, viability, gestation, location, dormancy status, hatch sensitivity, decay, and parthenogenesis flag.
- Dormancy: eggs can start dormant or enter dormancy if gestation stretches under poor reproduction conditions; dormant eggs decay more slowly but hatch less readily.
- Death: caused by starvation, environment health failure, age, shock, predation, density limit, or egg environment/decay causes.
- Ancestor preservation: dead fish produce compact summaries and death snapshots. The simulation retains up to 320 dead summaries in memory and genealogy samples up to 48.
- Recovery: viable eggs keep the biosphere `dormant` rather than extinct; hatching can restore active adults; parthenogenesis can produce bounded clonal eggs when rare genetic traits and pressure conditions align; dead bodies recycle nutrients/detritus.
- No-god-mode guarantees: debug reseed is off by default; randomizing environment does not spawn life; true extinction requires zero adults and zero viable eggs.

### Lifecycle stages

For fish:

- `juvenile`, `mature`, `senescent` via `LifeHistoryProfile.maturity_state`.
- `immature`, `fertile`, `late_fertility`, `too_old` via `LifeHistoryProfile.fertility_state`.

For biosphere:

- `active`
- `dormant`
- `extinct`

For eggs:

- `gestating`
- `dormant`
- `hatched`
- `dead`

### Recovery assays

`evals/recovery_assays.py` implements programmatic assays for bottleneck recovery, egg-bank resilience, reproduction gates, density/crowding, resource rebound, behavior payoff, and AI deliberation.

A compact run during this inspection with seeds `[711, 712]`, 90 ticks:

- schema: `aquagenesys.recovery_assays.v1`
- recovery possible: true
- egg bank preserves lineages: true
- gates are explainable: true
- low global population is not global overcrowding: true
- resource rebound window seen: true
- behavior has payoff: true
- AI optional: true
- mechanics tuning recommended: false
- bottleneck recovery rate in that short sample: `0.5`
- egg-bank dormant-to-hatched rate: `1.0`
- no god-mode reseed: true
- no instant adult rescue: true

The full stored v0.3.7 report used six seeds and reported bottleneck recovery rate `1.0`, extinction rate `0.0`, and no debug reseed.

What the assays prove: these code paths are executable, endogenous recovery is possible, egg banks can preserve lineages, resource rebound exists, model calls are not required, and reproduction gates are explicit.

What they do not prove: broad Monte Carlo robustness, long-run open-ended improvement, causal effect of a specific taught skill, or superiority of one policy family across environments.

## 8. Ecology as Evaluator

### Environment variables

The environment is `PuddleEnvironment` in `aquagenesys/environment/puddle.py:103`. It owns these sampled fields:

- static/spatial-ish: depth, light, current, shelter, substrate, obstacle.
- dynamic chemistry/resources: temperature, oxygen, pH, turbidity, nutrients, food, plankton, waste, toxins, decomposition, population pressure, reproduction, balance.

Fields that change over time: temperature, oxygen, pH, turbidity, nutrients, food, plankton, waste, toxins, decomposition, population pressure, reproduction, and balance.

Fields affected by organisms:

- oxygen decreases from respiration.
- waste increases from metabolism.
- food/plankton/decomposition/nutrients are consumed by feeding.
- population pressure increases around adults.
- death adds detritus, raising decomposition/nutrients/waste.
- predation removes organisms.
- reproduction adds eggs/adults.

Fields affecting survival:

- oxygen, pH, temperature, turbidity, toxins, crowding, resource availability, shelter, population pressure, food/plankton/nutrients/decomposition.

Fields affecting reproduction:

- local reproduction score, crowding, resources/health/energy/stress, mate/prey/neighbors, life history, parthenogenesis pressure.

Fields affecting behavior:

- local stress score, resource score, reproduction score, gradients for food/plankton/oxygen/shelter/stress/current, and neighbor vectors.

### Selection pressure

What kills organisms:

- `energy <= 0`: starvation.
- `health <= 0`: environment.
- age risk past expected/senescence windows.
- high stress shock.
- predation.
- density limit for excess newborns.
- egg environment/decay.

What helps survival:

- reaching resources, matching metabolism to resource niches, tolerating local chemistry, sheltering under stress/fear, avoiding predation, maintaining energy, and surviving lifecycle windows.

What helps reproduction:

- mature age, enough health/energy/drive, good local reproduction score, low crowding, mate contact, rare parthenogenesis under pressure, and enough energy per clutch.

Behaviors rewarded indirectly:

- foraging effectively, resting/conserving under low energy, sheltering under stress/threat, courtship near compatible mates, hunting successfully for predators, and laying viable eggs under favorable conditions.

Traits rewarded indirectly:

- tolerances suited to current chemistry, movement suited to resource seeking/escape/hunt, metabolism suited to available resources, life-history profiles that produce viable eggs/adults, dormancy under bottlenecks, and policy priors that avoid costly choices.

Can behavior be locally useful but globally harmful? Yes. Feeding and movement can help an individual while depleting resources, consuming oxygen, adding waste, increasing pressure, or increasing toxins/decomposition indirectly. Dense lineages can crowd local reproduction scores.

Can a lineage change the environment for descendants? Yes, through resource depletion, waste, population pressure, deaths/detritus, and egg bank occupancy. This is currently local and implicit rather than lineage-attributed in a full causal ledger.

### Ecology-as-evaluator map

```text
organism action
  -> movement / feeding / hunting / sheltering / resting / reproducing
  -> ecological consequence
     resources consumed, oxygen consumed, waste added, pressure added, detritus recycled, eggs/adults added or killed
  -> survival/reproduction consequence
     energy/health/fear/stress/reproductive gate/egg viability changes
  -> inheritance/lineage consequence
     some genomes and instruction policies produce more live descendants or viable eggs
```

### What the ecology currently evaluates well

- Whether bodies can survive local chemistry, energy costs, predation, and lifecycle constraints.
- Whether reproductive strategies can produce live offspring or viable eggs.
- Whether egg banks and dormancy can preserve lineages through adult bottlenecks.
- Whether instruction policies at least change behavior under controlled conditions.
- Whether no-god-mode recovery can occur.

### What the ecology weakly evaluates

- Which exact taught skill caused a descendant behavior.
- Whether a behavior prior improved fitness across comparable counterfactuals.
- Whether a lineage changed the environment in a way that helped or hurt descendants.
- Long-horizon policy family performance.
- Spatial niche specialization beyond current resources and chemistry.

### What the ecology does not yet evaluate

- Explicit individual or lineage fitness scores.
- Skill-use events and skill payoff.
- Full two-parent recombination or mate contribution.
- Morphological affordances such as venom, tentacles, armor, grazing apparatus, or camouflage affecting detection.
- Quality-diversity novelty/coverage metrics.
- Benchmark-style task success beyond survival/reproduction/recovery.

## 9. Genealogy and Lineage Tracking

Genealogy is built by `build_genealogy` in `aquagenesys/simulation/genealogy.py:14`.

Current genealogy capabilities:

- Tracks: live adults, viable eggs, dormant eggs, compact sampled dead ancestors, parent ids, lineage id, generation, compact biology hash, phenotype hash, policy hash/label, taught skill counts, patch counts, lifecycle/recovery role, edges, lineages, policy inheritance trail, and recovery contributions.
- Does not track: full memory, raw prompts, raw model outputs, exact per-field gene diffs, complete unbounded ancestor tree, non-parent teaching, true two-parent genetic contribution, or skill causal payoff.
- UI exposes: genealogy explorer, biology track, behavior track, selected lineage path, policy inheritance trail, recovery roles, compare-mode relationship hints, and lineage story renderer.
- API exposes: `/api/state.genealogy`, not `/api/frame`.
- Strong for: compact lineage/policy observability, parent-child edge visibility, egg-bank lineage continuity, and dead ancestor sampling.
- Weak for: deep genealogy, causal skill tracking, exact gene trajectory, and robust outperformance comparisons.

What counts as a lineage: `lineage_id` on fish/eggs/genomes. Most offspring stay in parent lineage; a low-probability split during paired reproduction can create a new lineage id.

Parent-child relationships: `parent_ids` are tracked. In current reproduction this is a one-element tuple, even when a mate is required.

Eggs/dormant eggs: included if viable.

Dead ancestors: included as compact samples. `dead_agent_summaries` keeps up to 320 in memory; genealogy samples up to 48 recent dead summaries and caps total nodes at 140 and edges at 180.

Can we trace behavior/skill/gene across generations?

- Behavior policy: yes by policy hash/label and policy inheritance trail, within bounded state.
- Taught skills: weakly by skill counts, accepted/rejected patch counts, and instruction inheritance events; full skill hashes are in lifecycle/archive, not richly in the genealogy cards.
- Gene: yes by compact genome and phenotype hash; no per-field diff in genealogy.
- Recovery role: yes by live adults, viable eggs, events, and recovery contribution role.
- Outperformance: only weakly by counts and status, not normalized by starting population, environment, or exposure time.

Short runtime trace from `/api/state` sampled during this inspection at tick `1568`:

- `population=8`, `lineages=2`, `eggs=0`, `biosphere_state=active`.
- instruction inheritance enabled, model teaching disabled.
- `inheritance_events=40`, `patches_accepted=22`, `patches_rejected=12`, `policy_variants_alive=8`.
- model calls were enabled but all 72 sampled calls had timed out, so the active ecology was running on reflex/habit behavior despite AI being enabled.
- one live fish `#39`, lineage `L39`, generation `0`, had policy `3949963b` / `high-yield-patch, energy-saver`.

## 10. Actual Self-Improvement Loops

| Loop | Exists today? | Mechanism | Code locations | Evidence exposed? | Strength | Missing evidence |
|---|---|---|---|---|---|---|
| Individual adaptation | Weak yes | Recent memory/recent outcomes affect `follow_success_memory`, `memory_guided`, and model uncertainty gates. | `FishMemory`, `heuristic_action`, `should_deliberate` | Memory summary in state/archive | weak | No persistent learned policy, no reward update, no skill creation from individual experience except parent teaching rules. |
| Parent-child teaching | Yes | Rule-generated patches from parent memory/state/population create bounded skills and bias offspring instruction genomes. | `instructions.py:437`, `engine.py:1037` | instruction telemetry, lifecycle archive, genealogy trail | medium | No skill-use or causal payoff attribution; single-parent only; no teaching action cost. |
| Genetic evolution | Yes | Parent genome mutates; traits affect survival/reproduction; survivors reproduce. | `FishGenome.mutated`, `_maybe_reproduce`, `_death_cause` | genome/phenotype hashes, lineage counts, lifecycle events | strong mechanically | No explicit fitness accounting; no sexual recombination; limited niche diversity. |
| Lineage selection | Yes, implicit | Lineages with more adults/viable eggs persist in dashboard/genealogy/story. | `dashboard.py`, `genealogy.py`, `lineage_story.py` | top lineages, recovery roles, story cards | medium | No normalized lineage fitness, counterfactual, or long-run lineage scoreboard. |
| Ecological recovery | Yes | Eggs, dormant egg bank, parthenogenesis, detritus/nutrient/resource rebound, no adult rescue. | `egg.py`, `engine.py:1282`, `engine.py:1538`, `puddle.py:430` | recovery dashboard, assays | strong for recovery path | Assays are seeded and short; not broad robustness proof. |
| Policy/skill evolution | Yes, implicit | Instruction genomes mutate and inherited skills bias policy fields; policies affect behavior and are indirectly selected. | `BehaviorInstructionGenome.mutated`, `with_skill_bias`, `heuristic_action` | policy variants alive, inheritance events, patch counts | medium | No per-policy survival/reproduction payoff metric; no skill-use telemetry. |
| Model/reflection self-improvement | Mostly no | Model can return short-lived action intent only; model teaching disabled by default; no retained verbal reflection. | `deliberation.py`, `_poll_model_results` | model telemetry and last intent | weak | No model-generated durable policy updates in normal config; live model not required and may fail. |

Aquagenesys currently self-improves in these senses:

1. Biological variants change across generations and ecological survival/reproduction decides which remain.
2. Behavior priors change across generations through instruction genome mutation and bounded taught-skill inheritance.
3. Lineages recover or disappear through endogenous egg-bank, reproduction, and ecological resource dynamics.

Aquagenesys does not yet self-improve in these senses:

1. A single fish does not perform durable self-reflection that rewrites its own policy.
2. A taught skill is not explicitly scored for success/failure/use.
3. The system does not run an explicit automated search over agent variants with a formal evaluator and selected archive.
4. The model does not safely author durable future policy patches in the default implementation.

## 11. Comparison to Modern Self-Improving-Agent Concepts

This is a conceptual comparison, not a literature review.

| SOTA concept | Aquagenesys similarity | Aquagenesys difference | Where fish may be stronger | Where fish are weaker | Improvement opportunity |
|---|---|---|---|---|---|
| Darwin Godel Machine style | Population of agent variants, archive snapshots, descendant variants, empirical survival. | Fish do not edit code; archive is observational, not a search archive used to generate next agents. | Ecological embodiment makes "improvement" harder to fake because dead agents stop reproducing. | No explicit evaluator, proof obligation, code-diff lineage, or archive-driven selection. | Add explicit variant scorecards without giving fish unsafe code authority. |
| AlphaEvolve style | Variants are generated, evaluated, and indirectly selected. | Variants are biological/instruction mutations, not generated programs; evaluator is ecology, not benchmark suite. | Constraints are physically grounded: body, energy, death, eggs. | Metrics are weaker and causality is implicit. | Add automated assays for policy/genome variants across seed families. |
| Voyager style | Embodied agents, local environment, skill-like library, persistent skills across descendants. | Skills are bounded enum priors, not rich executable or language skills; no curriculum manager. | Parent-child transfer and lineage ecology are richer than a one-agent skill library metaphor. | Skill library is small, trigger use is not logged, no explicit skill success measure. | Add skill-use events and lineage skill payoff while keeping schema bounded. |
| Reflexion-style | Recent memory influences future choices and model uncertainty. | No verbal reflection stored as future policy; model outputs actions only. | Avoids self-reported improvement without ecological consequences. | Very weak individual adaptation. | Add bounded post-outcome reflection cards that affect future action only after eval gates. |
| SEAL/self-adaptation style | System updates future behavior through offspring instruction genomes and taught skills; downstream survival filters updates. | Updates occur mainly at reproduction, not per-task self-adaptation; model teaching is disabled. | Downstream success is survival/reproduction, not just agent claims. | No explicit downstream success attribution to the update. | Add policy update IDs, descendants' outcomes, and rejection/rollback evidence. |
| Quality-diversity / evolutionary algorithms | Multiple lineages/policies coexist; ecology can support niches. | No explicit novelty archive, behavior descriptor grid, or diversity objective. | Spatial ecology, metabolism, egg banks, and life histories give natural diversity pressure. | Niches are still limited; morphology mostly visual; no QD metrics. | Track niche descriptors and preserve diverse successful strategies intentionally. |

What to emphasize cautiously:

- Ecological embodiment is a real evaluator in the limited sense that survival/reproduction are consequences, not declarations.
- Parent-child behavior transfer is an interesting recursive-agent frame distinct from one-agent self-editing.
- Gene constraints bound action space and prevent behavior policy from rewriting physics.
- The system already separates intent from capability: instruction changes intent, biology controls capability, ecology decides persistence.

What needs improvement before stronger claims:

- Explicit policy/skill/gene fitness metrics.
- Causal evidence that taught behavior crossed generations and helped or hurt.
- Wider seeded assays and long-run lineage comparisons.
- Better niche/morphology mechanics.
- Explicit uncertainty in lineage stories.

## 12. Where Aquagenesys Is Already Strong

- It has a real embodied loop: local sensing, bounded action, environmental consequence, survival/reproduction consequence, inheritance consequence.
- It does not depend on successful live model calls for core ecology or recovery.
- Instruction inheritance is bounded and inspectable.
- Genetic and instruction pathways are separate, which makes it clear what affects body capability versus behavior intent.
- Eggs and dormant eggs make recovery endogenous rather than a hidden spawn.
- Genealogy and lineage story are grounded in compact state, not model-written marketing text.
- Death and extinction remain possible.

## 13. Where Aquagenesys Is Weak or Under-Evidenced

- Individual learning is mostly recent-memory heuristics, not policy learning.
- Skill-use is not logged as a direct event.
- Skill benefit/harm is not causally attributed.
- Mate contribution is not genetic; reproduction is effectively single-parent mutation with mate-contact gating.
- Model teaching is a config/telemetry concept but not active default behavior.
- Some visible morphology is cosmetic and does not yet affect ecology.
- Policy success is not normalized by environment, generation, or starting conditions.
- Lineage story can summarize persistence but cannot prove why a lineage outperformed another.

## 14. Questions for v0.3.9

v0.3.9 is already implemented locally as a lineage story renderer. These are the smallest honest questions to use when evaluating or hardening it:

- What is the smallest lineage story we can honestly show with current data? A story with one live lineage, compact biology hash, policy hash, reproduction attempt, and either surviving adult or viable egg.
- Can we show a taught behavior crossing generations? Yes, by instruction inheritance event plus policy hash/skill count; stronger if archive skill hash is surfaced.
- Can we show a behavior prior being used by a descendant? Partially. We can show descendant policy fields and decisions that match the policy, but not a direct "skill used" event.
- Can we show whether it helped or failed? Weakly through descendant survival/reproduction/gates. Not causally.
- Can we show ecological context around the behavior? Yes: reproduction score, resource/crowding/recovery phase, death causes, and gate pressure exist, but not always attached to each decision.
- Can we show uncertainty instead of overclaiming? The story renderer should explicitly mark inferred links as "policy present" or "behavior consistent with" rather than "skill caused".
- What dashboard additions make the self-improvement loop legible? Add policy/skill lineage cards, descendant outcome panels, skill-use markers, and uncertainty labels.

## 15. Questions for v0.4.0

- How can richer morphology change the action space rather than only the render shape?
- How can genes constrain cognition/behavior, for example perception range, memory slots, policy mutation rate, and action availability?
- How can weird organisms emerge from trait combinations rather than hand-authored monster classes?
- What ecological niches must exist before venom, tentacles, armor, camouflage, filter sheets, giant herbivores, or ambush predators matter?
- How do we preserve tradeoffs so no trait is always better?
- How do we keep behavior evolution bounded and inspectable while allowing more behavioral diversity?
- What assay proves a morphology/action affordance matters?
- What metric catches a policy that succeeds individually while degrading the ecosystem for descendants?

## 16. Code Map

Primary mechanics:

- `aquagenesys/agents/fish.py`
  - `FishGenome`: biological genes, founder generation, mutation, phenotype payload.
  - `Action`: bounded action payload.
  - `Perception`: local sensor bundle.
  - `FishMemory`: recent outcome memory.
  - `FishAgent`: organism state, reflex/habit decisions, model gate, payload/frame payload.
- `aquagenesys/agents/instructions.py`
  - `BehaviorInstructionGenome`: bounded behavior priors.
  - `TaughtSkill`: parent-child behavioral transfer unit.
  - `inherit_taught_skills`: TTL/confidence/slot inheritance.
  - `rule_generated_patch`: parent teaching proposal rules.
  - `validate_instruction_patch`: safety and schema gate.
- `aquagenesys/agents/life_history.py`
  - `LifeHistoryProfile`
  - `derive_life_history`
- `aquagenesys/environment/puddle.py`
  - `PuddleEnvironment`
  - `CellSample`
  - environment field generation/update/resource cycles.
- `aquagenesys/simulation/engine.py`
  - `AquagenesysSimulation.step`
  - `_sense`
  - `_select_action`
  - `_apply_action`
  - `_maybe_reproduce`
  - `_offspring_instruction_seed`
  - `_update_eggs`
  - `_death_cause`
  - `_recycle_dead`
  - `state`
  - `frame_state`
- `aquagenesys/simulation/egg.py`
  - `EggEntity`
- `aquagenesys/agents/deliberation.py`
  - `FishDeliberationController`
  - bounded action parser.
- `aquagenesys/storage/archive.py`
  - JSONL state, memory, lifecycle archival.

Observability and UI:

- `aquagenesys/simulation/dashboard.py`: dashboard/recovery/narrator/focus hints.
- `aquagenesys/simulation/genealogy.py`: bounded lineage and policy genealogy.
- `aquagenesys/simulation/lineage_story.py`: deterministic lineage story renderer.
- `aquagenesys/web/app.py`: FastAPI `/api/state`, `/api/frame`, `/api/control`.
- `aquagenesys/web/static/index.html`: dashboard, genealogy, story, inspector, compare UI.
- `aquagenesys/web/static/app.js`: polling, rendering, inspector, compare mode, genealogy/story display.

Validation/evidence:

- `tests/test_aquagenesys_v03.py`: environment, loop, frame/state, model, archive.
- `tests/test_life_history_egg_bank.py`: life history, reproduction, eggs, dormancy, parthenogenesis, extinction.
- `tests/test_instruction_inheritance.py`: instruction genome, patch validation, teaching, behavior payoff boundaries.
- `tests/test_genealogy_explorer.py`: bounded genealogy and dead ancestor snapshots.
- `tests/test_lineage_story_renderer.py`: lineage story renderer.
- `tests/test_recovery_assays.py`: recovery assays.
- `evals/recovery_assays.py`: programmatic recovery and behavior payoff assays.
- `reports/aquagenesys_v035_instruction_inheritance_2026-05-23.md`
- `reports/aquagenesys_v037_recovery_assays_observability_2026_05_23.md`
- `reports/aquagenesys_v038_lineage_policy_genealogy_explorer_2026_05_23.md`
- `reports/aquagenesys_v039_lineage_story_renderer_2026_05_23.md`

## 17. Recommended Metrics

Add these before making stronger self-improvement claims:

- Per-policy adult survival ticks.
- Per-policy reproduction attempts, successful births, viable eggs, and hatched eggs.
- Per-policy death causes normalized by exposure ticks.
- Per-lineage generation depth, adult-days, egg-days, and recovery events.
- Skill-use events: skill hash, trigger matched, action selected, immediate energy/health delta.
- Skill-descendant outcome: descendants carrying skill hash, survival ticks, reproduction success, death causes.
- Policy transition graph: parent policy hash -> child policy hash -> descendant count.
- Gene transition graph: genome/phenotype hash changes and descendant count.
- Ecological externality: resource/oxygen/waste/pressure delta per lineage density.
- Niche occupancy: metabolism/resource target, spatial zone, chemistry tolerance band, morphology cluster.
- Counterfactual assays: same seed/environment with/without a specific policy or skill.
- Uncertainty labels in lineage story: observed, inferred, not evidenced.
- Model influence metric: action count from model intent vs habit/reflex, and descendant outcomes after model-influenced reproduction.
- Egg-bank contribution: lineages recovered from egg state, hatch timing, dormant duration, post-hatch reproduction.
