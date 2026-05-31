# ADR 0020: v0.4.2 Recursive Agent Loop Visibility

Status: Accepted for v0.4.2.

## Problem

The simulation already models the recursive-agent metaphor, but the boundary was distributed across morphology, behavior, evidence, inheritance, and UI payloads. A first-time reader or demo viewer needed to infer the mapping instead of seeing it directly.

## Options considered

- Add a broad new dashboard: rejected because it would add surface area without changing the loop.
- Rewrite the behavior system as a planner: rejected because Aquagenesys is explicitly a bounded scorer, not a general planner.
- Add a compact concept-loop payload to selected/full organism state: accepted.

## Decision

Add `agent_loop` to full organism payloads in `/api/state`, with schema `aquagenesys.agent_loop.v1`. It summarizes:

- agent goals and current state
- functional capability surface and separate visual traits
- available bounded behavior tools from the current candidate set
- harness decision, reasons, and rejected alternatives
- evidence/memory and inheritance status
- recursive channel wording

The compact `/api/frame` payload remains unchanged.

## Rationale

This makes the modeling boundary explicit without changing the core architecture. The fish remains the agent; morphology is the capability surface; behavior candidates are bounded tools/actions; the behavior selector is the harness-like layer; evidence/inheritance form the recursive improvement channel.

## Consequences

- `/api/state.fish[].agent_loop` is intentionally explanatory and demo-facing.
- Visual traits are separated from functional affordances so cosmetic rendering is not described as capability.
- The selected-organism inspector can explain the recursive loop without a large metrics dashboard.

## Explicit deferrals

- No full LLM planner.
- No arbitrary code rewriting.
- No open-ended tool invention.
- No claim that the agent/harness boundary is philosophically final.
