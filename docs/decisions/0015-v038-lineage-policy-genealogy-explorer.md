# ADR 0015: v0.3.8 Lineage and Policy Genealogy Explorer

## Status

Accepted.

## Context

Aquagenesys now has two inheritance channels: biological traits and bounded behavior instructions. v0.3.6 made the ecology observable, and v0.3.7 measured recovery, but the recursive-agent story still required reading logs to follow ancestor-to-offspring changes.

## Decision

v0.3.8 adds a bounded genealogy explorer backed by `/api/state.genealogy` with schema `aquagenesys.genealogy.v1`. `/api/state` moves to `aquagenesys.state.v8`; `/api/frame` remains `aquagenesys.frame.v3` and does not include genealogy.

The genealogy payload contains compact nodes for:

- live adults
- viable gestating eggs
- dormant eggs
- sampled dead ancestors

Each node includes parent ids, lineage, generation, compact biological genome hash, phenotype hash, instruction policy hash, policy label, taught-skill counts, patch counts, lifecycle/recovery role, and outcome summary.

## Biology vs Behavior

The UI presents two tracks:

```text
biology: genome -> phenotype -> life history -> capability
behavior: instruction genome -> policy -> taught skills -> action bias
```

The viewer includes the thesis line:

```text
Instruction changes intent. Biology controls capability. Ecology decides what persists.
```

This is the core recursive-agent framing. Offspring can inherit modified behavior priors, but those priors do not edit code, bypass energy, change physical speed caps, or disable death.

## Bounded History

The genealogy endpoint is intentionally bounded. It samples compact dead ancestors and caps node/edge counts. It does not send full runtime memory, raw prompt logs, arbitrary agent programs, or full unbounded genomes.

## UI Consequences

The below-puddle observatory now includes:

- lineage and policy genealogy summary
- selected-lineage biology track
- selected-lineage behavior track
- recovery roles by lineage
- recent policy inheritance trail
- compare-mode relationship hints for parent/child, siblings, matching biology, and matching policy

## Limitations

This is not yet a full interactive tree or graph database. It favors selected-lineage paths and compact cards to avoid graph spaghetti. A future pass can add a richer drilldown or dedicated lineage graph once the compact genealogy contract has proven stable.
