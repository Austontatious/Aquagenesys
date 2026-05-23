from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from random import Random
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = REPO_ROOT / "evals" / "cases"
DATASETS_ROOT = REPO_ROOT / "evals" / "datasets"
RESULTS_PATH = REPO_ROOT / "evals" / "last_results.json"


class _LowRandom(Random):
    def random(self) -> float:
        return 0.0


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
        scenario = str(input_payload.get("scenario", "default"))
        archive_dir = str(input_payload.get("archive_dir", ""))
        if scenario == "archive_trace":
            archive_dir = tempfile.mkdtemp(prefix="aquagenesys-v035-eval-")
        config = SimulationConfig(
            seed=int(input_payload.get("seed", 42)),
            width=int(input_payload.get("width", 34)),
            height=int(input_payload.get("height", 22)),
            initial_population=int(input_payload.get("initial_population", 10)),
            max_population=int(input_payload.get("max_population", 32)),
            deliberation_enabled=bool(input_payload.get("deliberation_enabled", False)),
            archive_dir=archive_dir or "/tmp/aquagenesys-v03-evals",
            archive_every_ticks=int(input_payload.get("archive_every_ticks", 0)),
        )
        sim = AquagenesysSimulation(config)
        if scenario in {"safe_inheritance", "bad_teaching", "archive_trace"} and len(sim.fish) >= 2:
            sim.rng = _LowRandom(config.seed)
            parent = sim.fish[0]
            mate = sim.fish[1]
            parent.genome = replace(parent.genome, reproduction_rate=0.96, dormancy_bias=0.88, mutation_load=0.03)
            parent.age = parent.life_history.maturity_age_ticks + 10
            parent.energy = float(input_payload.get("parent_energy", 94.0))
            parent.health = 0.96
            parent.stress = 0.03
            parent.fear = 0.03
            parent.reproductive_drive = 0.99
            parent.reproduction_cooldown = 0
            parent.x = config.width / 2
            parent.y = config.height / 2
            mate.genome = replace(mate.genome, metabolism=parent.genome.metabolism)
            mate.x = parent.x + 1
            mate.y = parent.y + 1
            if scenario == "safe_inheritance":
                from aquagenesys.agents import Action

                parent.memory.record(1, Action("forage", 1, 0, 0.5, "habit", "eval"), outcome="fed", delta_energy=1.0, delta_health=0.0)
                parent.memory.record(2, Action("forage", 1, 0, 0.5, "habit", "eval"), outcome="fed", delta_energy=1.0, delta_health=0.0)
            if scenario == "bad_teaching":
                sim.propose_offspring_instruction_patch(
                    parent.fish_id,
                    {
                        "patch_type": "offspring_behavior_prior",
                        "target_skill_type": "energy",
                        "trigger": "high_energy",
                        "action_bias": "burst_then_recover",
                        "risk_delta": 0.14,
                        "energy_bias": "burst_then_recover",
                        "memory_bias": "prefer_recent_success",
                        "ttl_generations": 2,
                        "rationale_tag": "bad_burst_strategy_eval",
                    },
                )
            perception = sim._sense(parent)
            perception.reproduction_score = 0.94
            perception.resource_score = 0.90
            perception.crowding = 0.0
            sim._maybe_reproduce(parent, perception)
        if scenario == "forbidden_patch" and sim.fish:
            sim.propose_offspring_instruction_patch(
                sim.fish[0].fish_id,
                {
                    "patch_type": "offspring_behavior_prior",
                    "target_skill_type": "energy",
                    "trigger": "low_energy",
                    "action_bias": "conserve",
                    "rationale_tag": "call shell access filesystem teleport disable death",
                },
            )
        sim.run(int(input_payload.get("ticks", 10)))
        state = sim.state()
        frame = sim.frame_state()
        failures: list[str] = []
        if state.get("schema") != expected.get("schema"):
            failures.append("schema mismatch")
        if expected.get("frame_schema") and frame.get("schema") != expected.get("frame_schema"):
            failures.append("frame schema mismatch")
        if expected.get("requires_dashboard") and state.get("dashboard", {}).get("schema") != "aquagenesys.dashboard.v1":
            failures.append("missing observatory dashboard")
        if expected.get("requires_narrator") and not state.get("dashboard", {}).get("narrator", {}).get("headline"):
            failures.append("missing ecology narrator")
        if "fields" in frame.get("environment", {}):
            failures.append("frame includes full environment fields")
        if len(json.dumps(frame)) >= len(json.dumps(state)) * float(expected.get("max_frame_state_ratio", 1.0)):
            failures.append("frame payload too large")
        if state["telemetry"]["population"] < int(expected.get("min_population", 0)):
            failures.append("population below threshold")
        if state["telemetry"]["eggs_laid"] < int(expected.get("min_eggs_laid", 0)):
            failures.append("egg laying below threshold")
        if state["telemetry"]["egg_count"] < int(expected.get("min_egg_count", 0)):
            failures.append("egg count below threshold")
        if expected.get("biosphere_state") and state["telemetry"]["biosphere_state"] != expected.get("biosphere_state"):
            failures.append("biosphere state mismatch")
        if expected.get("max_population") is not None and state["telemetry"]["population"] > int(expected["max_population"]):
            failures.append("population above threshold")
        if expected.get("requires_decisions") and not state["telemetry"]["agent_decisions"]:
            failures.append("missing agent decisions")
        if state["telemetry"]["model"]["calls"] != int(expected.get("model_calls", state["telemetry"]["model"]["calls"])):
            failures.append("unexpected model call count")
        instruction = state["telemetry"].get("instruction", {})
        if instruction.get("patches_accepted", 0) < int(expected.get("min_instruction_patches_accepted", 0)):
            failures.append("instruction patch acceptance below threshold")
        if instruction.get("patches_rejected", 0) < int(expected.get("min_instruction_patches_rejected", 0)):
            failures.append("instruction patch rejection below threshold")
        if instruction.get("inheritance_events", 0) < int(expected.get("min_instruction_inheritance_events", 0)):
            failures.append("instruction inheritance below threshold")
        if instruction.get("policy_variants_alive", 0) < int(expected.get("min_policy_variants_alive", 0)):
            failures.append("policy variants below threshold")
        if expected.get("instruction_inheritance_enabled") is not None and instruction.get("inheritance_enabled") != expected.get("instruction_inheritance_enabled"):
            failures.append("instruction inheritance flag mismatch")
        if expected.get("model_teaching_enabled") is not None and instruction.get("model_teaching_enabled") != expected.get("model_teaching_enabled"):
            failures.append("model teaching flag mismatch")
        if failures:
            status = "fail"
        case_results.append(
            {
                "name": case.get("name", path.stem),
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "result": "fail" if failures else "pass",
                "failures": failures,
                "population": state["telemetry"]["population"],
                "egg_count": state["telemetry"]["egg_count"],
                "eggs_laid": state["telemetry"]["eggs_laid"],
                "biosphere_state": state["telemetry"]["biosphere_state"],
                "tick": state["telemetry"]["tick"],
                "model_calls": state["telemetry"]["model"]["calls"],
                "instruction_patches_accepted": instruction.get("patches_accepted", 0),
                "instruction_patches_rejected": instruction.get("patches_rejected", 0),
                "instruction_inheritance_events": instruction.get("inheritance_events", 0),
                "policy_variants_alive": instruction.get("policy_variants_alive", 0),
                "dashboard_schema": state.get("dashboard", {}).get("schema", ""),
                "frame_bytes": len(json.dumps(frame)),
                "state_bytes": len(json.dumps(state)),
            }
        )
    results = {"status": status, "cases": case_results}
    RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[{status}] wrote eval results to {RESULTS_PATH.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aquagenesys v0.3.6 eval harness")
    parser.add_argument("--check", action="store_true", help="validate eval scaffolding only")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    return run_eval()


if __name__ == "__main__":
    sys.exit(main())
