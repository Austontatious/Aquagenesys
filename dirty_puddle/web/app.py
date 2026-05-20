from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from pathlib import Path
import sys
import threading
from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from dirty_puddle.sim.world import CONFIG_ROOT, World, load_world_config
from dirty_puddle.ui.controls import RUNTIME_SLIDERS


STATIC_ROOT = Path(__file__).resolve().parent / "static"


class WebSimState:
    def __init__(self, *, config_name: str, seed: int | None = None) -> None:
        self.config_name = config_name
        config = load_world_config(config_name)
        if seed is not None:
            config = replace(config, seed=seed).normalized()
        self.world = World(config)
        self.seed = config.seed
        self.speed = 4
        self.paused = False
        self.field_mode = "nutrient"
        self.lock = threading.Lock()

    def reset(self, *, config_name: str | None = None, seed: int | None = None) -> None:
        if config_name is not None:
            self.config_name = config_name
        config = load_world_config(self.config_name)
        if seed is not None:
            self.seed = seed
        config = replace(config, seed=self.seed).normalized()
        self.world = World(config)

    def advance(self) -> None:
        if not self.paused:
            self.world.step(max(1, min(128, self.speed)))


def create_app(config_name: str = "default_live", seed: int | None = None) -> FastAPI:
    state = WebSimState(config_name=config_name, seed=seed)
    app = FastAPI(title="Aquagenesys Dirty Puddle", version="0.4.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((STATIC_ROOT / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/configs")
    def configs() -> dict[str, object]:
        names = sorted(path.stem for path in CONFIG_ROOT.glob("*.yaml"))
        return {"configs": names, "active": state.config_name}

    @app.get("/api/state")
    def api_state() -> dict[str, object]:
        with state.lock:
            state.advance()
            return _world_payload(state)

    @app.post("/api/control")
    def api_control(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, object]:
        with state.lock:
            action = str(payload.get("action", "") or "")
            if action == "toggle_pause":
                state.paused = not state.paused
            elif action == "pause":
                state.paused = True
            elif action == "resume":
                state.paused = False
            elif action == "step":
                state.world.step(max(1, int(payload.get("ticks", 1))))
            elif action == "reset":
                state.reset(
                    config_name=payload.get("config") if payload.get("config") else None,
                    seed=int(payload["seed"]) if payload.get("seed") is not None else None,
                )
            if "speed" in payload:
                state.speed = max(1, min(128, int(payload["speed"])))
            if "field_mode" in payload:
                mode = str(payload["field_mode"])
                if mode in {"nutrient", "heat", "toxin"}:
                    state.field_mode = mode
            controls = payload.get("controls")
            if isinstance(controls, dict):
                state.world.update_controls(**controls)
            return _world_payload(state)

    return app


def _world_payload(state: WebSimState) -> dict[str, object]:
    world = state.world
    latest = world.metrics.latest()
    return {
        "config_name": state.config_name,
        "paused": state.paused,
        "speed": state.speed,
        "field_mode": state.field_mode,
        "width": world.config.width,
        "height": world.config.height,
        "tick": world.tick,
        "stage": world.environment_stage.value,
        "support": world.environment_support_score,
        "effective_mutation_rate": world.current_effective_mutation_rate(),
        "performance": asdict(world.performance.snapshot()),
        "snapshot": asdict(latest) if latest else None,
        "fields": {
            "nutrient": world.fields.nutrient,
            "heat": world.fields.heat,
            "toxin": world.fields.toxin,
        },
        "cells": [
            {
                "id": cell.id,
                "lineage_id": cell.lineage_id,
                "x": cell.x,
                "y": cell.y,
                "energy": cell.energy,
                "color": cell.genome.color(),
                "adhesion": cell.genome.adhesion,
                "cooperation": cell.genome.cooperation,
                "selfishness": cell.genome.selfishness,
            }
            for cell in world.cells
        ],
        "colonies": [colony.to_dict() for colony in world.colonies.active.values()],
        "organisms": [organism.to_dict() for organism in world.organisms],
        "aquatics": [aquatic.to_dict() for aquatic in world.aquatics],
        "events": world.events.to_list()[-60:],
        "controls": {
            spec.key: {
                "label": spec.label,
                "minimum": spec.minimum,
                "maximum": spec.maximum,
                "step": spec.step,
                "value": state.speed if spec.key == "speed" else getattr(world.config, spec.key),
            }
            for spec in RUNTIME_SLIDERS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the local Aquagenesys web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", default="default_live")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(args.config, seed=args.seed), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
