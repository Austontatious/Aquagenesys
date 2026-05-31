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
AQUAGENESYS_PUBLIC_DEMO=true
```

For controlled Lexi/vLLM testing, the same container route can be restarted with bounded deliberation enabled:

```bash
scripts/run_demo_container.sh --deliberation
```

That sets `AQUAGENESYS_DELIBERATION_ENABLED=true` while keeping model teaching disabled and keeping port `8008` internal-only.

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

Chosen option: public-demo app restriction plus recommendation to use Cloudflare Access for narrow sharing.

`AQUAGENESYS_PUBLIC_DEMO=true` blocks unsafe controls:

- `POST /api/control {"action":"reset"}` -> `403`
- `POST /api/control {"action":"randomize_environment"}` -> `403`
- `POST /api/control {"deliberation_enabled":true}` -> `403`

Speed control remains allowed:

- `POST /api/control {"speed":2}` -> `200`

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
- `/api/control` public-demo restriction: passed.
- Logs: showed normal Uvicorn startup and successful API requests.
- Restart repeatability: `docker compose down`, `docker compose up -d`, and `/api/frame` passed after restart.
- Optional deliberation restart: passed; `/api/state` reported `deliberation_enabled=true`, the container-to-host Lexi route was reachable, and model calls were attempted.
- Optional deliberation caveat: Lexi calls timed out in the observed run, and API probes took roughly 6-13 seconds during those timeouts. Keep no-deliberation as the public default unless that latency is acceptable.
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
