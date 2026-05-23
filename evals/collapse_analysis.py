from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from aquagenesys.storage import segment_jsonl_runs


def classify_segment(records: list[dict[str, Any]]) -> str:
    if not records:
        return "unknown"
    last = records[-1]
    fish = last.get("fish") or []
    eggs = [egg for egg in last.get("eggs") or [] if egg.get("state") in {"gestating", "dormant"} and egg.get("viability", 0) > 0]
    if fish:
        return "active"
    if eggs:
        return "egg_bank_dormant"
    deaths = {}
    for record in records[-80:]:
        for event in record.get("recent_events") or []:
            if event.get("kind") == "death":
                deaths[event.get("cause", "unknown")] = deaths.get(event.get("cause", "unknown"), 0) + 1
    if deaths.get("environment", 0) > deaths.get("age", 0) + deaths.get("starvation", 0):
        return "environmental_collapse"
    if deaths.get("starvation", 0) > deaths.get("age", 0):
        return "starvation"
    return "lifecycle_attrition_or_reproduction_gate_failure"


def analyze_state_archive(path: Path) -> dict[str, Any]:
    segments = segment_jsonl_runs(path)
    summaries: list[dict[str, Any]] = []
    for segment in segments:
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line_number < segment["start_line"]:
                    continue
                if line_number > segment["end_line"]:
                    break
                if line.strip():
                    records.append(json.loads(line))
        populations = [len(record.get("fish") or []) for record in records]
        eggs = [len(record.get("eggs") or []) for record in records]
        summaries.append(
            {
                **segment,
                "max_population": max(populations) if populations else 0,
                "final_population": populations[-1] if populations else 0,
                "max_egg_count": max(eggs) if eggs else 0,
                "final_egg_count": eggs[-1] if eggs else 0,
                "classification": classify_segment(records),
            }
        )
    return {
        "path": str(path),
        "segments": summaries,
        "archive_contamination_warning": len(segments) > 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Aquagenesys append-only state archives by run segment")
    parser.add_argument("path", nargs="?", default="/tmp/aquagenesys-v03/fish_state.jsonl")
    args = parser.parse_args(argv)
    result = analyze_state_archive(Path(args.path))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
