# ADR 0008: v0.3.1 Smooth Viewer and Async Deliberation

## Problem
The v0.3 viewer used full `/api/state` snapshots for both simulation advancement and rendering. The payload was large enough that fish motion appeared choppy, and synchronous Lexi deliberation could block viewer requests while the model timed out.

## Options Considered
- Increase full `/api/state` polling frequency.
- Move to a dedicated background simulation loop.
- Add a compact frame endpoint, browser interpolation, and nonblocking model deliberation while keeping the existing request-driven runtime.

## Decision
Add compact `/api/frame` snapshots for high-cadence viewer motion and keep full `/api/state` at a lower cadence for environment fields and controls. The browser renders with `requestAnimationFrame`, interpolates and lightly extrapolates fish positions between frames, and uses mouse hit-testing for fish inspection.

Model deliberation is queued on a bounded `ThreadPoolExecutor`. The simulation polls completed futures during normal ticks, applies successful results as short-lived fish intents, and records failures without blocking state or frame requests.

## Rationale
This preserves the v0.3 architecture and avoids polling the full environment grid at visual frame rate. The simulation remains deterministic without model availability, and the model path is still observable through counters, events, pending flags, and active intent TTL.

## Consequences
- Viewer smoothness now depends mostly on compact frame cadence and interpolation, not full state snapshots.
- Model calls can remain slow or unavailable without stalling `/api/state` or `/api/frame`.
- Successful model output influences several future ticks through an intent TTL instead of a single logged action.
- The runtime is still request-driven; a dedicated background simulation loop remains deferred.

## Explicit Deferrals
- No WebSocket/SSE transport in v0.3.1.
- No major biology or speciation expansion.
- No 3D simulation or renderer.
- No changes to the Lexi/vLLM service.
