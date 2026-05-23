# ADR 0011: v0.3.4 Life-History Reproduction And Egg Bank

## Problem

The v0.3.3 live biosphere died from lifecycle attrition, not final water poisoning. The population narrowed to one healthy `omnivore-046` survivor, that fish entered its age-risk window, and it died before reproductive RNG produced another offspring. A stable, food-rich puddle should not require a hidden rescue spawn, but it should have plausible biological recovery paths.

## Options Considered

- Re-enable founder reseed when population falls below a threshold.
- Increase single-offspring reproduction chance and keep direct live spawn.
- Add a modeled life-history layer, brood/clutch reproduction, independent eggs, dormancy, and rare bounded parthenogenesis.

## Decision

Implement organic reproductive resilience in v0.3.4:

- Derive a heritable `LifeHistoryProfile` from genome and phenotype traits.
- Replace one-off reproduction with energy-costed brood/clutch reproduction.
- Add `EggEntity` embryos that exist independently of parents.
- Add a dormant egg bank for lineages whose life-history traits support it.
- Add rare facultative parthenogenesis alleles with viability and mutation-load tradeoffs.
- Treat adult-zero plus viable eggs as `biosphere_state=dormant`, not true extinction.
- Treat true extinction as adult-zero plus no viable eggs.
- Add lifecycle events and run ids to archives so collapse analysis can separate current runs from append-only history.

## Rationale

Founder reseeding would make the viewer lively but would erase the ecological meaning of collapse. The v0.3 diagnosis showed the existing system already had useful environmental recovery dynamics but lacked a propagule layer and robust reproduction observability. Eggs let life survive parent death without creating animals from nowhere. Life-history profiles let small/short-lived organisms mature earlier and produce larger clutches, while larger organisms mature later and invest more per offspring.

Parthenogenesis is intentionally not a free win. Zero-allele singletons cannot reproduce. One-allele fish are emergency-only and rare. Higher allele counts increase clonal attempts under mate isolation, but offspring are usually eggs and inherit viability/mutation penalties that can make clonal lineages fragile under environmental shifts.

## Consequences

- Extinction remains possible under hostile chemistry, bad genetics, low viability, or failed hatching.
- Adult population can temporarily hit zero while viable eggs remain.
- The viewer and API expose adult population, egg count, viable eggs, dormant eggs, hatch counts, reproduction gates, and biosphere state.
- `/api/state` moves to `aquagenesys.state.v4`; compact `/api/frame` moves to `aquagenesys.frame.v2`.
- Archive records now include `run_id` and lifecycle events under `lifecycle_events.jsonl`.
- Decomposition/detritus from deaths and waste can feed nutrient, plankton, and food rebound, while excess decay still costs oxygen and can add toxins.

## Explicit Deferrals

- No full sexual genetics model.
- No hybrid speciation tree or full phylogeny UI.
- No detailed embryology, disease, or immune system.
- No WebGL/Pixi rewrite.
- No Lexi prompt/model tuning.
- No v0.3.5 offspring instruction editing in this pass.

## v0.3.5 Roadmap

v0.3.5 should explore agent instruction inheritance and offspring teaching. Parent agents may propose bounded offspring behavior priors; the system validates, clamps, and mutates those priors as part of reproduction. Agents still cannot edit runtime code. Structure remains body/lifecycle/genome, function becomes behavior policy/instruction seed, and selection remains the environment.
