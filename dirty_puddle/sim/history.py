from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunEvent:
    tick: int
    kind: str
    message: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventLog:
    def __init__(self, *, maxlen: int = 2000, jsonl_path: str | None = None) -> None:
        self.events: deque[RunEvent] = deque(maxlen=maxlen)
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        if self.jsonl_path:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self.jsonl_path.write_text("", encoding="utf-8")

    def append(self, event: RunEvent) -> None:
        self.events.append(event)
        if self.jsonl_path:
            with self.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def add(self, *, tick: int, kind: str, message: str, **data: Any) -> None:
        self.append(RunEvent(tick=tick, kind=kind, message=message, data=data))

    def to_list(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
