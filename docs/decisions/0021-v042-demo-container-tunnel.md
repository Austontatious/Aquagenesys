# ADR 0021: v0.4.2 Demo Container and Tunnel Boundary

Status: Accepted for v0.4.2 demo prep.

## Problem

Aquagenesys needs a public-demo launch path that can be exposed through Cloudflare Tunnel without exposing raw host services, Docker, SSH, repo files, broad host mounts, or model endpoints. The demo also needs to keep the v0.4.2 launch decision that no-deliberation is the safest public default.

## Options considered

- Run the host Python service directly behind Cloudflare: rejected because it blurs the public boundary with local development state.
- Use host networking for a container: rejected because it exposes unnecessary host network surface.
- Add a local-only Docker Compose demo service with public-demo controls: accepted.

## Decision

Add a Dockerfile, `.dockerignore`, `docker-compose.demo.yml`, and start/stop scripts for a local demo appliance. The container listens on internal port `8765`; the host maps only `127.0.0.1:8782` by default, with script fallback ports `8783` through `8785`.

The container runs `--no-deliberation` by default. It keeps an internal route to host Lexi at `http://host.docker.internal:8008/v1` for later controlled testing, but Docker and Cloudflare do not expose that endpoint.

Add `AQUAGENESYS_PUBLIC_DEMO=true` as a web-runtime safety mode. Public-demo mode leaves read endpoints and speed control available, while blocking reset, environment randomization, and AI-deliberation toggling through `/api/control`.

## Rationale

This keeps the public boundary narrow and easy to route through Cloudflare Tunnel:

```text
Cloudflare Tunnel -> http://127.0.0.1:8782 -> container:8765
```

No broad host paths, Docker socket, privileged mode, host networking, raw model APIs, or extra dev ports are required.

## Consequences

- The public demo is reproducible with `scripts/run_demo_container.sh`.
- `/api/frame`, `/api/state`, and the viewer remain reachable.
- `/api/control` is safer for public demos but still allows speed changes.
- Operators can still run local developer demos with the normal Python command and full controls.
- Cloudflare Access remains recommended when sharing narrowly.

## Explicit deferrals

- No Kubernetes or production orchestration.
- No Cloudflare tunnel creation or DNS configuration in repo automation.
- No public exposure of Lexi/vLLM.
- No model-deliberation optimization before Dr. Hulme outreach.
