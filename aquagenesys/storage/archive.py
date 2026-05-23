from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from aquagenesys.agents.fish import FishAgent


@dataclass(frozen=True)
class FishArchive:
    state_path: Path
    memory_path: Path
    lifecycle_path: Path | None = None

    def write_snapshot(self, *, tick: int, fish: Iterable[FishAgent], eggs: Iterable[Any] = (), run_id: str = "") -> None:
        records = [
            {
                "tick": tick,
                "run_id": run_id,
                "fish_id": item.fish_id,
                "species_id": item.species_id,
                "lineage_id": item.lineage_id,
                "generation": item.generation,
                "age": item.age,
                "body_state": item.body_state,
                "maturity_state": item.maturity_state,
                "fertility_state": item.fertility_state,
                "position": [round(item.x, 3), round(item.y, 3)],
                "energy": round(item.energy, 3),
                "health": round(item.health, 3),
                "reproductive_drive": round(item.reproductive_drive, 3),
                "genome": item.genome.payload(),
                "life_history": item.life_history.payload(),
                "instruction_genome": item.instruction_genome.policy_payload(),
                "taught_skill_hashes": [skill.skill_hash for skill in item.taught_skills],
                "accepted_instruction_patch_ids": list(item.accepted_instruction_patch_ids[-8:]),
                "rejected_instruction_patch_ids": list(item.rejected_instruction_patch_ids[-8:]),
                "memory_summary": item.memory.summary(),
                "model_budget": item.model_budget,
                "last_reproduction_gate": item.last_reproduction_gate,
            }
            for item in fish
        ]
        egg_records = [item.payload(compact=True) for item in eggs]
        self._append_jsonl(self.state_path, {"tick": tick, "run_id": run_id, "fish": records, "eggs": egg_records})

    def write_decisions(self, *, tick: int, fish: Iterable[FishAgent], run_id: str = "") -> None:
        for item in fish:
            self._append_jsonl(
                self.memory_path,
                {
                    "tick": tick,
                    "run_id": run_id,
                    "fish_id": item.fish_id,
                    "species_id": item.species_id,
                    "lineage_id": item.lineage_id,
                    "decision": item.last_decision.payload(),
                    "instruction_policy_hash": item.instruction_genome.policy_hash,
                    "instruction_policy_label": item.instruction_genome.policy_label,
                    "taught_skill_hashes": [skill.skill_hash for skill in item.taught_skills],
                    "memory_summary": item.memory.summary(),
                    "recent_outcomes": list(item.recent_outcomes[-5:]),
                    "last_reproduction_gate": item.last_reproduction_gate,
                },
            )

    def write_lifecycle_event(self, payload: dict[str, Any]) -> None:
        if self.lifecycle_path is None:
            return
        self._append_jsonl(self.lifecycle_path, payload)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def segment_jsonl_runs(path: Path) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_tick: int | None = None
    previous_run_id: str | None = None
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            tick = int(record.get("tick", 0))
            run_id = str(record.get("run_id") or "")
            starts_new = current is None or tick < (previous_tick or 0) or (run_id and previous_run_id and run_id != previous_run_id)
            if starts_new:
                if current is not None:
                    current["end_line"] = line_number - 1
                    current["end_tick"] = previous_tick
                    segments.append(current)
                current = {
                    "run_id": run_id or None,
                    "start_line": line_number,
                    "start_tick": tick,
                    "end_line": line_number,
                    "end_tick": tick,
                    "records": 0,
                }
            if current is not None:
                current["records"] += 1
                current["end_line"] = line_number
                current["end_tick"] = tick
            previous_tick = tick
            previous_run_id = run_id
    if current is not None:
        segments.append(current)
    return segments
