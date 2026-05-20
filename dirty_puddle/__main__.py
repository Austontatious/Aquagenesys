from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from dirty_puddle.sim.world import World, load_world_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dirty Puddle artificial life simulator")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="run the pygame UI")
    run_parser.add_argument("--config", default="default_live", help="config name or path")

    web_parser = subparsers.add_parser("web", help="run the local web UI")
    web_parser.add_argument("--config", default="default_live", help="config name or path")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8765)
    web_parser.add_argument("--seed", type=int, default=None)

    smoke_parser = subparsers.add_parser("smoke", help="run a headless simulation")
    smoke_parser.add_argument("--config", default="default_live", help="config name or path")
    smoke_parser.add_argument("--ticks", type=int, default=10_000)
    smoke_parser.add_argument("--seed", type=int, default=None, help="override config seed")
    smoke_parser.add_argument("--output", default=None, help="write run history JSON")
    smoke_parser.add_argument("--events", default=None, help="write event JSONL incrementally")
    smoke_parser.add_argument("--checkpoint", default=None, help="write checkpoint JSON")
    smoke_parser.add_argument("--autosave-interval", type=int, default=None, help="checkpoint every N ticks")

    longrun_parser = subparsers.add_parser("longrun", help="run the optimized long-run tier")
    longrun_parser.add_argument("--config", default="headless_longrun", help="config name or path")
    longrun_parser.add_argument("--ticks", type=int, default=100_000)
    longrun_parser.add_argument("--seed", type=int, default=None, help="override config seed")
    longrun_parser.add_argument("--output", default=None, help="write run history JSON")
    longrun_parser.add_argument("--events", default=None, help="write event JSONL incrementally")
    longrun_parser.add_argument("--checkpoint", default=None, help="write checkpoint JSON")
    longrun_parser.add_argument("--autosave-interval", type=int, default=None, help="checkpoint every N ticks")

    args = parser.parse_args(argv)
    if args.command == "run":
        from dirty_puddle.ui.pygame_app import run_app

        return run_app(args.config)
    if args.command == "web":
        from dirty_puddle.web.app import main as web_main

        web_args = ["--config", args.config, "--host", args.host, "--port", str(args.port)]
        if args.seed is not None:
            web_args.extend(["--seed", str(args.seed)])
        return web_main(web_args)
    if args.command == "smoke":
        world = _build_world(args)
        world.run(args.ticks)
        _finish_headless(world, args.output)
        return 0
    if args.command == "longrun":
        world = _build_world(args)
        world.run(args.ticks)
        _finish_headless(world, args.output)
        return 0
    parser.print_help()
    return 1


def _build_world(args: argparse.Namespace) -> World:
    config = load_world_config(args.config)
    if args.seed is not None:
        config = replace(config, seed=args.seed).normalized()
    return World(
        config,
        event_log_path=args.events,
        checkpoint_path=args.checkpoint,
        autosave_interval=args.autosave_interval,
    )


def _finish_headless(world: World, output: str | None) -> None:
    report = world.export_history()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(world.summary_json())


if __name__ == "__main__":
    sys.exit(main())
