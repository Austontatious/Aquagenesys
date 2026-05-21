from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = REPO_ROOT / "evals" / "cases"
DATASETS_ROOT = REPO_ROOT / "evals" / "datasets"
RESULTS_PATH = REPO_ROOT / "evals" / "last_results.json"


def _load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Eval case must be an object: {path}")
    return payload


def run_check() -> int:
    errors: list[str] = []
    if not DATASETS_ROOT.is_dir():
        errors.append("missing evals/datasets")
    if not CASES_ROOT.is_dir():
        errors.append("missing evals/cases")
    cases = sorted(CASES_ROOT.rglob("*.json"))
    if not cases:
        errors.append("missing deterministic eval cases (*.json) under evals/cases")
    for path in cases:
        payload = _load_case(path)
        for key in ("name", "input", "expected"):
            if key not in payload:
                errors.append(f"{path.relative_to(REPO_ROOT)} missing required key: {key}")
    if errors:
        for error in errors:
            print(f"[fail] {error}")
        return 1
    print(f"[ok] eval scaffolding present ({len(cases)} case files)")
    return 0


def run_eval() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from aquagenesys.simulation import AquagenesysSimulation, SimulationConfig

    case_results: list[dict[str, Any]] = []
    status = "pass"
    for path in sorted(CASES_ROOT.rglob("*.json")):
        case = _load_case(path)
        input_payload = case["input"]
        expected = case["expected"]
        config = SimulationConfig(
            seed=int(input_payload.get("seed", 42)),
            width=int(input_payload.get("width", 34)),
            height=int(input_payload.get("height", 22)),
            initial_population=int(input_payload.get("initial_population", 10)),
            max_population=int(input_payload.get("max_population", 32)),
            deliberation_enabled=bool(input_payload.get("deliberation_enabled", False)),
            archive_every_ticks=0,
        )
        sim = AquagenesysSimulation(config)
        sim.run(int(input_payload.get("ticks", 10)))
        state = sim.state()
        frame = sim.frame_state()
        failures: list[str] = []
        if state.get("schema") != expected.get("schema"):
            failures.append("schema mismatch")
        if expected.get("frame_schema") and frame.get("schema") != expected.get("frame_schema"):
            failures.append("frame schema mismatch")
        if "fields" in frame.get("environment", {}):
            failures.append("frame includes full environment fields")
        if len(json.dumps(frame)) >= len(json.dumps(state)) * float(expected.get("max_frame_state_ratio", 1.0)):
            failures.append("frame payload too large")
        if state["telemetry"]["population"] < int(expected.get("min_population", 0)):
            failures.append("population below threshold")
        if expected.get("requires_decisions") and not state["telemetry"]["agent_decisions"]:
            failures.append("missing agent decisions")
        if state["telemetry"]["model"]["calls"] != int(expected.get("model_calls", state["telemetry"]["model"]["calls"])):
            failures.append("unexpected model call count")
        if failures:
            status = "fail"
        case_results.append(
            {
                "name": case.get("name", path.stem),
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "result": "fail" if failures else "pass",
                "failures": failures,
                "population": state["telemetry"]["population"],
                "tick": state["telemetry"]["tick"],
                "model_calls": state["telemetry"]["model"]["calls"],
                "frame_bytes": len(json.dumps(frame)),
                "state_bytes": len(json.dumps(state)),
            }
        )
    results = {"status": status, "cases": case_results}
    RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[{status}] wrote eval results to {RESULTS_PATH.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aquagenesys v0.3.2 eval harness")
    parser.add_argument("--check", action="store_true", help="validate eval scaffolding only")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    return run_eval()


if __name__ == "__main__":
    sys.exit(main())
