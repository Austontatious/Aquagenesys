# ADR 0007: v0.3 Agent-Fish Dirty Puddle Architecture

## Problem
Aquagenesys needed to move from abstract gene-token organisms to an agentic fish ecology while preserving deterministic environmental simulation and avoiding expensive per-tick model dependence.

## Options Considered
- Continue the v0.2 gene-token organism loop and add fish visuals.
- Build a new fish-agent architecture with CPU-owned environment fields and sparse model deliberation.
- Make the model responsible for all fish decisions.

## Decision
Build v0.3 around a CPU-owned `PuddleEnvironment` and bounded `FishAgent` organisms. Fish execute reflex and habit policies every tick, and only use the local Lexi OpenAI-compatible vLLM endpoint for sparse higher-level deliberation when budget, cooldown, and pressure gates allow.

## Rationale
The environment must remain deterministic and fast enough to run without a model. Fish can still demonstrate agentic behavior by combining local memory, genome strategy, observable decisions, and occasional model calls through the canonical `core.llm` boundary and repo prompt files.

## Consequences
The viewer shows fish-agent state rather than old gene-token traits. Model unavailability degrades to habit policy with explicit telemetry. Fish state, memory, and genomes are externalized to JSONL archives under the configured archive directory.

## Explicit Deferrals
- No persistent lineage database beyond JSONL archives.
- No 3D renderer in v0.3.
- No learned policy tuning loop.
- No dormant propagule lifecycle.
