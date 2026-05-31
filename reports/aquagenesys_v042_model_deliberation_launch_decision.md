# Aquagenesys v0.4.2 Model Deliberation Launch Decision

Date: 2026-05-31

## Branch and scope

- Branch: `main`
- Starting HEAD for this pass: `b091805`
- Scope: launch-readiness audit for optional fish deliberation, not a general model benchmark.
- Code impact: no simulation logic changed. Public README/UI wording was tightened to describe the LLM role accurately.

## Verdict

Recommended launch mode: launch with `--no-deliberation` for the Dr. Hulme outreach/demo default.

Reason: Aquagenesys remains valid and legible as a bounded recursive-agent ecology without model calls. In this environment the existing Lexi endpoint is reachable, but fish-deliberation calls timed out at the configured 1.8s timeout, and failed/missing model calls did not change the seeded proxy run's population, deaths, behavior distribution, or tick health relative to no deliberation.

Keep Lexi/Qwen as an optional local toggle for developer demos only if the operator wants to show bounded AI intent telemetry and accepts timeout/failure noise. Do not deploy a smaller model before outreach unless a simple structured-output endpoint can return valid fish intent well below the configured timeout.

## What the LLM actually does

The current LLM path is optional, sparse, nonblocking fish deliberation:

1. The CPU behavior harness first builds and scores bounded behavior candidates.
2. Reflexes can override the harness under urgent pressure.
3. If deliberation is enabled, budget remains, no call is pending, and a stochastic/pressure gate passes, the fish queues one model call.
4. The tick loop keeps using the CPU-selected habit while the model call is pending.
5. If the model returns valid JSON with an allowed action, that action becomes short-lived `model_intent` for `AQUAGENESYS_MODEL_INTENT_TTL` ticks.
6. If the model times out, returns bad JSON, or chooses an invalid action, the result is rejected and the fish keeps using normal behavior.

The LLM cannot create new actions, rewrite code, change physics, alter genome/morphology, bypass energy/death/reproduction rules, mutate the environment directly, or keep the ecology alive.

The LLM is not the main skill-evolution mechanism in v0.4.2. Model-generated teaching is disabled by default and there is no active default path where the LLM authors durable taught-skill patches. Skill evolution comes from bounded rule-generated teaching patches, observed skill-use outcomes, evidence-governed inheritance, and selection pressure. A successful model intent can indirectly contribute to skill evidence only if it executes an already skill-matched action; that evidence is still governed by the same observational gates.

## Code path audit

- Prompt: `prompts/tasks/fish_deliberation_v0.3.md`
- Boundary: `core.llm.LLMClient`
- Controller: `aquagenesys/agents/deliberation.py`
- Queue/poll/intent path: `aquagenesys/simulation/engine.py`
- Skill inheritance path: `aquagenesys/simulation/skill_evidence.py`
- Config defaults: `.env.example` and `core/config.py`

Important defaults:

- `AQUAGENESYS_DELIBERATION_ENABLED=true`
- `AQUAGENESYS_DELIBERATION_INTERVAL_TICKS=36`
- `AQUAGENESYS_GLOBAL_DELIBERATIONS_PER_TICK=1`
- `AQUAGENESYS_FISH_MODEL_BUDGET=3`
- `AQUAGENESYS_MODEL_INTENT_TTL=14`
- `AQUAGENESYS_MAX_INFLIGHT_MODEL_CALLS=1`
- `AQUAGENESYS_LLM_BASE_URL=http://127.0.0.1:8008/v1`
- `AQUAGENESYS_LLM_MODEL=Lexi`
- `AQUAGENESYS_LLM_TIMEOUT_SECONDS=1.8`
- `AQUAGENESYS_MODEL_TEACHING_ENABLED=false`

## Endpoint checks

Local endpoints observed:

| Endpoint | Model | Result |
| --- | --- | --- |
| `http://127.0.0.1:8008/v1` | `Lexi` | reachable, backed by `/mnt/data/models/Qwen/lexi-qwen3-30b-a3b-dpo-merged` |
| `http://127.0.0.1:8104/v1` | `exec` | reachable, Qwen3-8B vLLM endpoint |
| `http://127.0.0.1:8105/v1` | `coder` | reachable, Qwen2.5-Coder-7B endpoint |

Direct fish-deliberation sample calls timed out:

| Sample | Timeout | Result |
| --- | ---: | --- |
| Lexi configured default | 1.8s | timeout |
| Lexi long timeout probe | 6.0s | timeout |
| Qwen3-8B `exec` probe | 3.0s | timeout |
| Qwen2.5-Coder `coder` probe | 3.0s | timeout |

No smaller model was spun up. The already-running smaller endpoints did not demonstrate launch-ready structured response latency in this pass.

## Seeded simulation proxy

Run shape: direct in-process simulation, seed `515`, `24x18`, initial population `8`, max population `30`, `80` target ticks, archive disabled, default sparse deliberation interval `36`, one max inflight call. This is an eval-style proxy, not a full visual demo soak. The tight loop is conservative for pending-call skips because it advances faster than browser-paced ticks.

| Config | Endpoint/model | Delib | Fish start/end | Eggs end | Deaths | Repro events | Skill evidence | Inherited / suppressed hints | Model calls ok/fail | Timeout/conn errors | Mean/p95 latency | Tick mean/p95 ms | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |
| no_deliberation | none | off | 8 / 2 | 0 | 6 | 0 | 0 | 0 / 0 | 0 / 0 | 0 / 0 | n/a | 56.140 / 79.020 | baseline behavior |
| lexi_default_endpoint | `8008` / `Lexi` | on | 8 / 2 | 0 | 6 | 0 | 0 | 0 / 0 | 0 / 1 | 1 / 0 | n/a | 56.758 / 79.930 | one timed-out call, behavior unchanged |
| missing_endpoint | `65534` / missing | on | 8 / 2 | 0 | 6 | 0 | 0 | 0 / 0 | 0 / 2 | 0 / 2 | n/a | 56.143 / 85.533 | connection failures, behavior unchanged |
| small_candidate_qwen3_8b_existing | `8104` / `exec` | on | 8 / 2 | 0 | 6 | 0 | 0 | 0 / 0 | 0 / 2 | 2 / 0 | n/a | 55.802 / 78.671 | existing small endpoint timed out |

Additional model-call metrics:

| Config | Calls/min wall | Calls/fish/min wall | Ticks with queued call | Max pending | Fallback count | Invalid action | Parse failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_deliberation | 0.000 | 0.0000 | 0.00% | 0 | 0 | 0 | 0 |
| lexi_default_endpoint | 12.254 | 2.4508 | 1.25% | 1 | 1 | 0 | 0 |
| missing_endpoint | 24.744 | 4.9487 | 2.50% | 1 | 2 | 0 | 0 |
| small_candidate_qwen3_8b_existing | 24.926 | 4.9852 | 2.50% | 1 | 2 | 0 | 0 |

Dominant recent actions were identical across all four configs: `flee`, `court`, and `shelter`. No debug founder reseed occurred.

This short proxy did not reach reproduction or skill inheritance events. The standard eval suite separately covers no-deliberation skill governance, including evidence-supported inherited hints and evidence-suppressed hints.

## Demo quality assessment

Does model choice materially affect core simulation function? No evidence from this pass. The model path failed safely and the no-deliberation run matched the enabled/failing runs for population, deaths, eggs, reproduction, and recent behavior distribution.

Does model choice materially affect demo quality? Yes, but mainly by adding operational risk and confusing telemetry. In the measured environment, deliberation enabled with Lexi produced a timeout instead of a useful visible bounded intent. That hurts demo clarity more than it helps.

## Safety and routing notes

- `/api/control` is unauthenticated. If exposed through Cloudflare or a public tunnel, viewers can reset the simulation, randomize the environment, change speed, and toggle deliberation. That is acceptable for a controlled interactive demo only if intentional; otherwise put the route behind Cloudflare Access/basic auth or proxy only read endpoints.
- `/api/control` does not let clients set model base URL, model name, API key, tools, code paths, energy, death, or reproduction rules.
- `/api/state.telemetry.model.base_url` exposes local model topology (`127.0.0.1` URLs). It does not expose secrets, but public demos may want to redact or omit it for polish.
- The Lexi/vLLM endpoints are separate services. Aquagenesys should not expose them directly through the public route.

## Decision

Launch default: `python -m aquagenesys.web.app --host 127.0.0.1 --port 8765 --no-deliberation`

Optional developer mode: keep the AI deliberation toggle available locally, but treat it as telemetry, not core function.

Do not block launch on model choice. Do not spin up a new model before Dr. Hulme outreach unless a very small OpenAI-compatible endpoint can be proven to return valid fish-intent JSON quickly and without changing the public story.

## Validation run

Validation commands run after this report and UI/README wording update:

```bash
python3 -m pytest -q tests
python3 evals/runner.py --check
python3 evals/runner.py
python3 evals/recovery_assays.py --json
make lint
node --check aquagenesys/web/static/app.js
node --check aquagenesys/web/static/renderer_canvas.js
node --check aquagenesys/web/static/creature_portrait.js
```

Results:

- `python3 -m pytest -q tests`: passed, `84 passed`.
- `python3 evals/runner.py --check`: passed, 7 case files present.
- `python3 evals/runner.py`: passed.
- `python3 evals/recovery_assays.py --json`: passed; recovery possible, no god-mode reseed, AI optional.
- `make lint`: passed.
- JS syntax checks for `app.js`, `renderer_canvas.js`, and `creature_portrait.js`: passed.
- API smoke on `http://127.0.0.1:8776 --no-deliberation`: `/`, `/api/state`, `/api/frame`, and `/api/control` healthy; `/api/state` reported `deliberation_enabled=false` and zero model calls.
- Browser automation smoke was not run because Playwright was not installed for Node or Python in this environment.
