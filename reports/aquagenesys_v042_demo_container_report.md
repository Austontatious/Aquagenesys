# Aquagenesys v0.4.2 Demo Container Report

Date: 2026-05-31

## Branch and commits

- Branch: `main`
- Starting HEAD: `d1b22e9`
- Ending HEAD: recorded in the final task response after this report is committed.
- Commit message prepared: `chore(aquagenesys): add demo container for tunnel launch`

## Files changed

- `Dockerfile`
- `.dockerignore`
- `docker-compose.demo.yml`
- `scripts/run_demo_container.sh`
- `scripts/stop_demo_container.sh`
- `.env.example`
- `README.md`
- `core/config.py`
- `aquagenesys/web/app.py`
- `aquagenesys/web/static/app.js`
- `tests/test_aquagenesys_v03.py`
- `docs/README.md`
- `docs/decisions/0021-v042-demo-container-tunnel.md`
- `reports/README.md`
- `reports/aquagenesys_v042_demo_container_report.md`
- `reports/aquagenesys_v042_demo_container_report.json`

## Demo topology

```text
Cloudflare Tunnel / HTTPS public URL
-> http://127.0.0.1:8782
-> Docker port mapping 127.0.0.1:8782:8765
-> aquagenesys-demo container
-> optional internal-only host route http://host.docker.internal:8008/v1
```

- Selected host port: `127.0.0.1:8782`
- Container internal port: `8765`
- Local origin URL: `http://127.0.0.1:8782`
- Cloudflare origin target: `http://127.0.0.1:8782`
- Container image: `aquagenesys:demo`
- Container name: `aquagenesys-demo`
- Restart policy: `no`
- Host networking: no
- Privileged mode: no
- Docker socket mount: no
- Broad host mount: no
- Public Lexi/vLLM exposure: no

## Launch mode

Container command:

```bash
python -m aquagenesys.web.app --host 0.0.0.0 --port 8765
```

Deliberation is disabled by default through the environment:

```text
AQUAGENESYS_DELIBERATION_ENABLED=false
AQUAGENESYS_MODEL_TEACHING_ENABLED=false
AQUAGENESYS_PUBLIC_DEMO=false
```

For controlled Lexi/vLLM testing, the same container route can be restarted with bounded deliberation enabled:

```bash
scripts/run_demo_container.sh --deliberation
```

That sets `AQUAGENESYS_DELIBERATION_ENABLED=true` while keeping model teaching disabled and keeping port `8008` internal-only.
The demo container timeout for Lexi/vLLM deliberation is `AQUAGENESYS_LLM_TIMEOUT_SECONDS=30.0`.

For the current limited-release demo, the same route runs with controls unlocked by default:

```bash
scripts/run_demo_container.sh --deliberation
```

Unlocked mode sets `AQUAGENESYS_PUBLIC_DEMO=false`, allowing Reset, Randomize, speed, and AI-deliberation controls in the page. Locked-control mode can still be selected with `--locked-controls`; it allows Reset and speed changes but blocks Randomize and AI-deliberation toggles.

The demo container uses a whole-run reset if the ecology reaches true extinction:

```text
AQUAGENESYS_AUTO_RESET_ON_EXTINCTION=true
AQUAGENESYS_AUTO_RESET_EXTINCTION_TICKS=8
```

This prevents a long-lived dead public page while preserving the distinction from in-run debug founder reseeding.

Lexi/vLLM remains configured only for later controlled testing:

```text
AQUAGENESYS_LLM_BASE_URL=http://host.docker.internal:8008/v1
AQUAGENESYS_LLM_MODEL=Lexi
extra_hosts: host.docker.internal:host-gateway
```

Container-to-host Lexi route validation succeeded from inside the container against:

```text
http://host.docker.internal:8008/v1/models
```

The endpoint returned the `Lexi` model metadata. Port `8008` is not published by Docker and must not be used as a Cloudflare origin.

## `/api/control` decision

Chosen option: unlocked controls for the current limited release, with locked-control mode available if broader sharing is needed.

`AQUAGENESYS_PUBLIC_DEMO=false` leaves the page controls interactive:

- `POST /api/control {"action":"reset"}` -> `200`
- `POST /api/control {"action":"randomize_environment"}` -> `200`
- `POST /api/control {"deliberation_enabled":true}` -> `200`
- `POST /api/control {"speed":2}` -> `200`

`AQUAGENESYS_PUBLIC_DEMO=true` locks broader controls:

- `POST /api/control {"action":"reset"}` -> `200`
- `POST /api/control {"action":"randomize_environment"}` -> `403`
- `POST /api/control {"deliberation_enabled":true}` -> `403`

The control endpoint cannot set model URLs, model names, API keys, tools, source code, energy, death rules, reproduction rules, Docker state, or host filesystem access.

## Commands

Start demo:

```bash
scripts/run_demo_container.sh
```

Start demo with optional AI deliberation:

```bash
scripts/run_demo_container.sh --deliberation
```

Start demo with controls explicitly unlocked:

```bash
scripts/run_demo_container.sh --deliberation --unlocked-controls
```

Stop demo:

```bash
scripts/stop_demo_container.sh
```

Manual start:

```bash
docker compose -f docker-compose.demo.yml build
docker compose -f docker-compose.demo.yml up -d
```

Manual stop:

```bash
docker compose -f docker-compose.demo.yml down
```

Temporary Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8782
```

Named tunnel origin service:

```text
http://127.0.0.1:8782
```

If `8782` is occupied, `scripts/run_demo_container.sh` chooses the next free port from `8783`, `8784`, or `8785` and prints the actual origin. Use that printed origin for Cloudflare.

## Container validation

- Port check: `8782` was free and selected.
- Docker build: passed; image built as `aquagenesys:demo`.
- Container start: passed; `aquagenesys-demo` running and healthy.
- Port binding: `127.0.0.1:8782->8765/tcp`.
- `/api/frame`: passed, schema `aquagenesys.frame.v3`.
- `/api/state`: passed, schema `aquagenesys.state.v13`, `deliberation_enabled=false`, model calls `0`.
- `/`: passed, HTML shell returned.
- `/api/control` public-demo restriction: passed; Reset and speed remain allowed while Randomize and AI toggle stay locked.
- Unlocked tuning mode: passed; Reset, Randomize, speed, and AI toggle all returned `200`.
- Auto-reset on true extinction: focused test passed with whole-run reset after true extinction.
- Logs: showed normal Uvicorn startup and successful API requests.
- Restart repeatability: `docker compose down`, `docker compose up -d`, and `/api/frame` passed after restart.
- Optional deliberation restart: passed; `/api/frame` reported `deliberation_enabled=true`, the container-to-host Lexi route was reachable, and model calls succeeded after the timeout was raised to 30 seconds.
- Optional deliberation validation: after restart with `AQUAGENESYS_LLM_TIMEOUT_SECONDS=30.0`, telemetry reached model calls `3`, successes `3`, failures `0`, pending `0`, and frame probes stayed under roughly 2 seconds.
- Container remains running on `127.0.0.1:8782` after validation.

Browser automation smoke was not run because Playwright is not installed in this environment.

## Standard validation

- `python3 -m pytest -q tests`: passed, `85 passed`.
- `python3 evals/runner.py --check`: passed, 7 case files present.
- `python3 evals/runner.py`: passed.
- `python3 evals/recovery_assays.py --json`: passed.
- `make lint`: passed.
- `node --check aquagenesys/web/static/app.js`: passed.
- `node --check aquagenesys/web/static/renderer_canvas.js`: passed.
- `node --check aquagenesys/web/static/creature_portrait.js`: passed.

Recovery assay conclusion:

- recovery possible: true
- no god-mode reseed: true
- AI optional: true

## Cloudflare safety notes

- Do not route Cloudflare to the container IP, host public IP, port `8008`, SSH, Docker, or any vLLM/Lexi endpoint.
- Use `http://127.0.0.1:8782` as the origin.
- Cloudflare Access is recommended for Dr. Hulme-only sharing even though public-demo mode blocks unsafe control mutations.
- The container is a demo appliance, not production hosting.

## Worktree

Worktree status is recorded in the final task response after commit.
