from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMTraceRecord:
    timestamp_utc: str
    prompt_name: str
    prompt_sha256: str
    prompt_version: str
    prompt_text: str
    model: str
    response_text: str
    latency_ms: int
    usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        prompt_name: str,
        prompt_sha256: str,
        prompt_version: str,
        prompt_text: str,
        model: str,
        response_text: str,
        latency_ms: int,
        usage: TokenUsage | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "LLMTraceRecord":
        return cls(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            prompt_name=prompt_name,
            prompt_sha256=prompt_sha256,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            model=model,
            response_text=response_text,
            latency_ms=latency_ms,
            usage=usage or TokenUsage(),
            metadata=dict(metadata or {}),
        )


class TraceSink:
    def write(self, record: LLMTraceRecord) -> None:  # pragma: no cover
        raise NotImplementedError


class NoopTraceSink(TraceSink):
    def write(self, record: LLMTraceRecord) -> None:
        return None


class JsonlTraceSink(TraceSink):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def write(self, record: LLMTraceRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        payload["usage"] = asdict(record.usage)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def build_trace_sink(*, backend: str, jsonl_path: str | Path) -> TraceSink:
    normalized = backend.strip().lower()
    if normalized in {"", "noop", "disabled"}:
        return NoopTraceSink()
    if normalized == "jsonl":
        return JsonlTraceSink(jsonl_path)
    raise ValueError(f"Unsupported tracing backend: {backend}")
