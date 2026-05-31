from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig
from core.config import AquagenesysRuntimeConfig


STATIC_ROOT = Path(__file__).resolve().parent / "static"


class ControlRequest(BaseModel):
    action: str | None = None
    speed: int | None = None
    deliberation_enabled: bool | None = None


class Runtime:
    def __init__(
        self,
        config: SimulationConfig | None = None,
        *,
        public_demo: bool = False,
        auto_reset_on_extinction: bool = False,
        auto_reset_extinction_ticks: int = 0,
    ) -> None:
        self.simulation = AquagenesysSimulation(config)
        self.public_demo = public_demo
        self.auto_reset_on_extinction = auto_reset_on_extinction
        self.auto_reset_extinction_ticks = max(0, int(auto_reset_extinction_ticks))
        self.auto_reset_count = 0
        self._extinction_seen_tick: int | None = None
        self.lock = Lock()
        self.last_advance = time.monotonic()

    def advance_for_viewer(self) -> dict[str, Any]:
        with self.lock:
            self._advance(max_ticks=1, force_tick=True)
            return self.simulation.state()

    def frame_for_viewer(self) -> dict[str, Any]:
        with self.lock:
            self._advance(max_ticks=1, force_tick=False)
            return self.simulation.frame_state()

    def _advance(self, *, max_ticks: int, force_tick: bool) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_advance)
        ticks = int(round(elapsed * 6.0 * self.simulation.speed))
        if force_tick:
            ticks = max(1, ticks)
        ticks = max(0, min(max_ticks, ticks))
        if ticks:
            self.simulation.run(ticks)
            self.last_advance = time.monotonic()
        self._maybe_auto_reset_after_extinction()

    def _maybe_auto_reset_after_extinction(self) -> None:
        if not self.auto_reset_on_extinction:
            return
        if not self.simulation.dead_puddle:
            self._extinction_seen_tick = None
            return
        if self._extinction_seen_tick is None:
            self._extinction_seen_tick = self.simulation.tick
        if self.simulation.tick - self._extinction_seen_tick >= self.auto_reset_extinction_ticks:
            self._reset_simulation()
            self.auto_reset_count += 1
            self._extinction_seen_tick = None

    def _reset_simulation(self) -> None:
        speed = self.simulation.speed
        deliberation_enabled = self.simulation.config.deliberation_enabled
        self.simulation.reset()
        self.simulation.set_speed(speed)
        self.simulation.set_deliberation_enabled(deliberation_enabled)
        self.last_advance = time.monotonic()

    def control(self, request: ControlRequest) -> dict[str, Any]:
        with self.lock:
            if self.public_demo and _blocked_public_demo_control(request):
                raise HTTPException(status_code=403, detail="Control locked in public demo mode.")
            if request.speed is not None:
                self.simulation.set_speed(request.speed)
            if request.deliberation_enabled is not None:
                self.simulation.set_deliberation_enabled(request.deliberation_enabled)
            if request.action == "reset":
                self._reset_simulation()
            elif request.action == "randomize_environment":
                self.simulation.randomize_environment()
            return self.simulation.state()


def _blocked_public_demo_control(request: ControlRequest) -> bool:
    if request.deliberation_enabled is not None:
        return True
    if request.action == "randomize_environment":
        return True
    if request.action not in {None, "", "reset"}:
        return True
    return False


def create_app(
    config: SimulationConfig | None = None,
    *,
    public_demo: bool | None = None,
    auto_reset_on_extinction: bool | None = None,
    auto_reset_extinction_ticks: int | None = None,
) -> FastAPI:
    runtime_config = AquagenesysRuntimeConfig.from_env()
    runtime = Runtime(
        config or simulation_config_from_runtime(runtime_config),
        public_demo=runtime_config.public_demo if public_demo is None else public_demo,
        auto_reset_on_extinction=(
            runtime_config.auto_reset_on_extinction if auto_reset_on_extinction is None else auto_reset_on_extinction
        ),
        auto_reset_extinction_ticks=(
            runtime_config.auto_reset_extinction_ticks
            if auto_reset_extinction_ticks is None
            else auto_reset_extinction_ticks
        ),
    )
    app = FastAPI(title="Aquagenesys v0.4.2 Evidence-Governed Dirty Puddle", version="0.4.2")
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html")

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return runtime.advance_for_viewer()

    @app.get("/api/frame")
    def frame() -> dict[str, Any]:
        return runtime.frame_for_viewer()

    @app.post("/api/control")
    def control(request: ControlRequest) -> dict[str, Any]:
        return runtime.control(request)

    return app


def simulation_config_from_runtime(runtime_config: AquagenesysRuntimeConfig) -> SimulationConfig:
    return SimulationConfig(
        seed=runtime_config.seed,
        width=runtime_config.width,
        height=runtime_config.height,
        initial_population=runtime_config.initial_population,
        max_population=runtime_config.max_population,
        deliberation_enabled=runtime_config.deliberation_enabled,
        deliberation_interval_ticks=runtime_config.deliberation_interval_ticks,
        global_deliberations_per_tick=runtime_config.global_deliberations_per_tick,
        fish_model_budget=runtime_config.fish_model_budget,
        model_intent_ttl=runtime_config.model_intent_ttl,
        max_inflight_model_calls=runtime_config.max_inflight_model_calls,
        ecology_update_interval=runtime_config.ecology_update_interval,
        llm_base_url=runtime_config.llm_base_url,
        llm_api_key=runtime_config.llm_api_key,
        llm_model=runtime_config.llm_model,
        llm_timeout_seconds=runtime_config.llm_timeout_seconds,
        llm_max_retries=runtime_config.llm_max_retries,
        llm_temperature=runtime_config.llm_temperature,
        llm_max_tokens=runtime_config.llm_max_tokens,
        trace_backend=runtime_config.trace_backend,
        trace_jsonl_path=runtime_config.trace_jsonl_path,
        archive_dir=runtime_config.archive_dir,
        archive_every_ticks=runtime_config.archive_every_ticks,
        instruction_inheritance_enabled=runtime_config.instruction_inheritance_enabled,
        model_teaching_enabled=runtime_config.model_teaching_enabled,
    )


app = create_app()


def main(argv: list[str] | None = None) -> None:
    runtime_config = AquagenesysRuntimeConfig.from_env()
    parser = argparse.ArgumentParser(description="Run the Aquagenesys v0.4.2 local web viewer")
    parser.add_argument("--host", default=runtime_config.host)
    parser.add_argument("--port", type=int, default=runtime_config.port)
    parser.add_argument("--seed", type=int, default=runtime_config.seed)
    parser.add_argument("--no-deliberation", action="store_true")
    args = parser.parse_args(argv)

    import uvicorn

    config = simulation_config_from_runtime(runtime_config)
    config = SimulationConfig(
        **{
            **config.__dict__,
            "seed": args.seed,
            "deliberation_enabled": config.deliberation_enabled and not args.no_deliberation,
        }
    )
    uvicorn.run(create_app(config, public_demo=runtime_config.public_demo), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main(sys.argv[1:])
