# Aquagenesys v0.4.2 Recursive Agent Metaphor Closure

Date: 2026-05-31

## Branch and commits

- Branch: `main`
- Starting HEAD for this closure pass: `6eece76`
- Concept-closure changes are intended to land after `6eece76`.

## Supported claim

Aquagenesys now supports the public claim as a bounded metaphor, not as AGI, biological realism, open-ended self-modification, or arbitrary tool invention:

> Aquagenesys is a bounded artificial ecology for exploring recursive agent improvement. Each fish is an agent with survival and reproduction goals. Its morphology defines its capability surface, which changes what behaviors/tools are viable. A bounded behavior harness chooses among those actions under environmental pressure. Outcomes become evidence, and evidence influences what traits, behavior hints, and lineage patterns persist into future generations.

The claim is supported within the explicit implementation boundary: bounded action library, heuristic scorer, observational evidence, evidence-governed inheritance, and environmental selection through survival/reproduction.

## Concept map

| Agent-system concept | Aquagenesys surface |
| --- | --- |
| Agent | Fish / organism |
| Capability surface | Morphology affordances |
| Tools/actions | Bounded behavior candidates |
| Harness/orchestration | Behavior selector and reflex/model override path |
| Evaluator/environment | Puddle chemistry, resources, predators/prey, crowding, lifecycle gates |
| Memory | Fish memory, recent outcomes, skill evidence, lineage evidence |
| Recursive improvement channel | Biological inheritance plus evidence-governed taught-skill inheritance |
| Long-horizon success signal | Lineage persistence, viable eggs, recovery, reproduction, extinction |

## Morphology to affordance to behavior mapping

| Behavior/tool | Relevant affordances | Effect | Visible in UI/API | Test coverage |
| --- | --- | --- | --- | --- |
| `filter_feed` | `filter_rate`, `suction_force`, plankton/bloom context, oxygen/drag cost | scoring, cost, risk, mismatch warning when filter is weak | yes: affordances, tools, harness decision, behavior candidates | yes |
| `graze` | `scrape_rate`, `gut_capacity`, food/nutrients, drag | scoring and movement cost | yes | yes |
| `scavenge` | `reach`, `grip`, decomposition, tissue vulnerability | scoring, cost, risk | yes | yes |
| `anchor_feed` | `reach`, `filter_rate`/`scrape_rate`, drag/oxygen burden | scoring and low-movement cost benefit | yes | yes |
| `forage` | `feeding_throughput`, resource pressure, drag | general scoring and cost | yes | yes |
| `strike` | `bite_force`, `strike_impulse`, prey proximity, tissue vulnerability | scoring, cost, risk | yes | yes |
| `hunt` | `bite_force`, speed, drag, prey proximity | scoring and high movement cost | yes | yes |
| `chemical_defense` | `toxin_payload`, `toxin_delivery`, `toxin_self_cost` | scoring, self-cost, risk | yes | partial via affordance tags/warnings |
| `flee` | `drag`, `oxygen_cost`, `armor_protection`, `tissue_vulnerability` | cost/risk scoring | yes | yes |
| `shelter` | shelter context, stress/fear, movement burden | scoring, cost, risk reduction | yes | yes |
| `rest` | metabolic burden, energy, stress, threat | scoring and cost | yes | yes |
| `court` | reproduction drive, mate proximity, `reproduction_cost`, crowding | scoring, cost, risk | yes | covered by smoke/evals |
| `school` | sociality, neighbor count, crowding, movement burden | scoring and risk tradeoff | yes | covered by smoke/evals |
| `explore` | `sensory_range`, curiosity, oxygen/drag cost, open water | scoring and cost/risk | yes | yes |

Visual phenotype traits such as shape, tail, pattern, and rendering colors are shown separately from functional affordances. They are not described as capabilities unless represented by an affordance.

## Behavior harness explanation

The harness is `build_behavior_decision`: it builds a bounded candidate set, scores candidates with physiology, local context, morphology affordances, inherited policy, and taught skills, then chooses the highest-scoring action. Reflex and optional model intent can override, but neither creates arbitrary tools or changes physics. Full organism state now exposes `agent_loop.harness_decision` with the selected behavior, primary reasons, score, and rejected alternatives.

## Evidence and inheritance loop

Skill-matched actions create observational evidence with action, context, affordance tags, outcome label, organism, lineage, parent/descendant references, and reproduction/death associations. Aggregates count observed uses, helped-possible, harmed-possible, unclear, stale/suppression state, and governance status. Inheritance uses deterministic gates: enough recent positive lineage-local evidence can preserve a hint; weak, stale, expired, slot-limited, observed-only, or negative evidence suppresses it.

Inherited hints affect future behavior through the existing skill bias in the behavior scorer. Tests verify that a descendant with an inherited forage hint scores matching feeding actions higher than the same descendant without the hint.

## Implemented vs metaphorical

Implemented:

- bounded agents with survival/reproduction pressure
- morphology-derived affordances
- bounded behavior/action library
- behavior scorer with reasons and candidate scores
- outcome evidence linked to skill, organism, lineage, context, and affordances
- evidence-governed skill inheritance
- selected-organism concept-loop state and UI
- deterministic lineage stories with cautious language

Still metaphorical or limited:

- no AGI or cognitively rich planning
- no arbitrary source-code rewriting
- no open-ended tool invention
- no biological realism claim
- evidence is observational, not causal proof
- selection pressure is simulation-local and seeded, not a general fitness theorem

## UI/API changes

- `/api/state.fish[].agent_loop` exposes `aquagenesys.agent_loop.v1`.
- `/api/frame` remains compact and does not include `agent_loop`.
- Selected-organism inspector now shows agent goal, visual traits, capability surface, available tools, harness decision, evidence/memory, and skill inheritance.

## Tests and validation

Focused tests added or tightened:

- morphology affects behavior scoring/selection
- visual traits remain separate from functional capability
- behavior selector exposes candidates and rejected alternatives
- outcome evidence carries context/affordance tags
- evidence-supported hints become heritable
- insufficient/stale/negative hints are suppressed
- inherited hints affect descendant behavior scoring
- lineage story avoids unsupported causal conclusions
- API/state exposes concept-loop fields without frame bloat

Full validation results should be taken from the final task report after this pass.

## Known limitations

- The behavior selector is a bounded heuristic harness, not a full planner.
- Skill evidence supports inheritance governance but does not prove causality.
- Biological traits are abstracted into affordances, not detailed biology.
- The agent/harness boundary is a modeling boundary for the demo, not a philosophical resolution.

## Recommended final demo wording

Aquagenesys is a bounded artificial ecology for exploring recursive agent improvement. Each organism has survival and reproduction pressure, morphology-derived affordances, a bounded action set, a behavior harness, evidence memory, and an inheritance channel. The system does not claim open-ended intelligence; it makes a constrained improvement loop visible and testable.
