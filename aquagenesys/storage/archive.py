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

    def write_snapshot(self, *, tick: int, fish: Iterable[FishAgent]) -> None:
        records = [
            {
                "tick": tick,
                "fish_id": item.fish_id,
                "species_id": item.species_id,
                "lineage_id": item.lineage_id,
                "body_state": item.body_state,
                "position": [round(item.x, 3), round(item.y, 3)],
                "energy": round(item.energy, 3),
                "health": round(item.health, 3),
                "genome": item.genome.payload(),
                "memory_summary": item.memory.summary(),
                "model_budget": item.model_budget,
            }
            for item in fish
        ]
        self._append_jsonl(self.state_path, {"tick": tick, "fish": records})

    def write_decisions(self, *, tick: int, fish: Iterable[FishAgent]) -> None:
        for item in fish:
            self._append_jsonl(
                self.memory_path,
                {
                    "tick": tick,
                    "fish_id": item.fish_id,
                    "species_id": item.species_id,
                    "lineage_id": item.lineage_id,
                    "decision": item.last_decision.payload(),
                    "memory_summary": item.memory.summary(),
                    "recent_outcomes": list(item.recent_outcomes[-5:]),
                },
            )

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
