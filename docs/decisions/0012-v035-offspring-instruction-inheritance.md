# ADR 0012: v0.3.5 Offspring Instruction Inheritance

## Problem

Aquagenesys had biological genome, phenotype, life-history reproduction, egg banks, dormancy, parthenogenesis, and sparse model deliberation, but offspring inherited only biological traits. That made the project less explicit as a recursive-agent showcase: parent agents could survive and reproduce, but their successful behavior priors did not become bounded inheritable structure.

The goal is to let parents influence offspring behavior without creating self-modifying runtime programs.

## Options Considered

1. Store free-form parent prompts and pass them to offspring.
   - Rejected because unbounded prompt growth is hard to validate, hard to compare, and risks implying runtime authority the fish do not have.
2. Let fish edit behavior code or tools.
   - Rejected. Fish are simulated organisms and must not receive shell, file, network, repo, server, or code-editing authority.
3. Add a compact behavior/instruction genome and bounded taught skills.
   - Accepted. It is machine-readable, hashable, mutable under clamps, and can affect behavior while remaining subordinate to physics and ecology.

## Decision

v0.3.5 adds `BehaviorInstructionGenome` and `TaughtSkill` in `aquagenesys/agents/instructions.py`.

The biological genome continues to own body, phenotype, lifespan, reproduction, and energy economics. The instruction genome owns bounded policy priors:

- risk posture
- forage strategy
- threat strategy
- social strategy
- reproduction strategy
- exploration strategy
- energy strategy
- teaching style
- memory bias
- model deliberation bias
- skill slots and mutation rate

Parents may produce bounded offspring behavior patches. A patch can become a taught skill only after schema validation, capability checks, bounds clamps, and complexity checks. Accepted skills may bias offspring instruction genomes for a small number of generations. Rejected patches are recorded but do not change behavior.

## Rationale

This design demonstrates recursive agent engineering without granting unsafe agency. Parent behavior can influence child behavior, but the system owns validation and clamps. The child still must survive with its inherited body, energy budget, and local environment. A bad taught strategy can burn energy or reduce survival; it cannot make the body faster, disable death, spawn resources, or bypass reproduction.

Model teaching is deliberately disabled by default. Rule-generated teaching establishes the inheritance and validation path without requiring live Lexi success.

## Consequences

- `/api/state` moves to `aquagenesys.state.v5`.
- `/api/frame` moves to `aquagenesys.frame.v3`.
- Eggs now carry biological genome plus instruction seed.
- Fish inspector exposes policy hash, strategy labels, teaching style, skill count, and accepted/rejected patch counts.
- Telemetry exposes instruction patch proposals, acceptances, rejections, teaching events, inheritance events, policy variants alive, and rejection reasons.
- Archives include compact code snapshots and instruction inheritance events with `run_id`.
- Dead fish do not retain full runtime programs indefinitely. The archive keeps compact hashes, parent IDs, skill hashes, patch IDs, and final summary stats.

## Validation And Sandbox

Patch validation rejects:

- forbidden capability text such as shell, filesystem, network, repo, server, tool, code editing, teleport, death disabling, energy bypass, and spawning resources
- unknown fields
- invalid enum values
- overlong trigger/rationale text
- excessive JSON complexity
- skill slot overflows

Tests and evals cover safe inheritance, forbidden patch rejection, bad burst-style teaching remaining biological, model-disabled operation, compact archive trace, and run segmentation.

## Explicit Deferrals

- No runtime code editing.
- No arbitrary prompt evolution.
- No model-generated teaching enabled by default.
- No full lineage tree UI.
- No hybrid sexual genetics or cross-species instruction crossover beyond single-parent inheritance.
- No WebGL/Pixi rewrite or 3D environment.
- No Lexi prompt/model tuning.
