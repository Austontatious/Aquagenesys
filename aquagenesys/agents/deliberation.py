from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from aquagenesys.agents.fish import Action, FishAgent, Perception, clamp
from core.llm import LLMClient, LLMClientConfig, LLMRequestError
from core.prompt_loader import PromptLoader
from core.trace import build_trace_sink


ALLOWED_ACTIONS = {"forage", "eat", "hunt", "flee", "shelter", "court", "school", "explore", "rest", "escape"}


@dataclass(frozen=True)
class FishDeliberationResult:
    action: Action | None
    called: bool
    ok: bool
    latency_ms: int = 0
    raw_text: str = ""
    error: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "called": self.called,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "action": self.action.payload() if self.action else None,
            "error": self.error,
        }


class FishDeliberationController:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        temperature: float,
        max_tokens: int,
        trace_backend: str = "noop",
        trace_jsonl_path: str = "/tmp/aquagenesys-v03/llm-trace.jsonl",
    ) -> None:
        self.prompt_loader = PromptLoader()
        self.prompt = self.prompt_loader.render(
            "tasks/fish_deliberation_v0.3.md",
            {"schema_version": "aquagenesys.fish_deliberation.v1"},
        )
        self.client = LLMClient(
            LLMClientConfig(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            trace_sink=build_trace_sink(backend=trace_backend, jsonl_path=trace_jsonl_path),
        )

    @staticmethod
    def build_context(*, fish: FishAgent, perception: Perception, tick: int) -> dict[str, Any]:
        return {
            "schema": "aquagenesys.fish_context.v1",
            "tick": tick,
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "fish": {
                "id": fish.fish_id,
                "species_id": fish.species_id,
                "body_state": fish.body_state,
                "energy": round(fish.energy, 3),
                "hunger": round(fish.hunger, 3),
                "fear": round(fish.fear, 3),
                "stress": round(fish.stress, 3),
                "health": round(fish.health, 3),
                "reproductive_drive": round(fish.reproductive_drive, 3),
                "age": fish.age,
                "model_budget": fish.model_budget,
                "genome": fish.genome.payload(),
                "memory_summary": fish.memory.summary(),
                "last_decision": fish.last_decision.payload(),
            },
            "perception": perception.payload(),
        }

    def deliberate(self, *, fish: FishAgent, perception: Perception, tick: int) -> FishDeliberationResult:
        payload = self.build_context(fish=fish, perception=perception, tick=tick)
        return self.deliberate_context(payload, fish_id=fish.fish_id, tick=tick)

    def deliberate_context(self, payload: dict[str, Any], *, fish_id: int, tick: int) -> FishDeliberationResult:
        try:
            result = self.client.complete(
                prompt_name=self.prompt.document.name,
                prompt_sha256=self.prompt.document.sha256,
                prompt_version=self.prompt.document.version,
                system_prompt=self.prompt.text,
                user_prompt=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                metadata={"fish_id": fish_id, "tick": tick, "schema": payload["schema"]},
            )
            action = _parse_action(result.text)
            return FishDeliberationResult(action=action, called=True, ok=action is not None, latency_ms=result.latency_ms, raw_text=result.text)
        except (LLMRequestError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return FishDeliberationResult(action=None, called=True, ok=False, error=str(exc)[:240])


def _parse_action(text: str) -> Action | None:
    payload = _extract_json_object(text)
    kind = str(payload.get("action", "")).strip().lower()
    if kind not in ALLOWED_ACTIONS:
        return None
    vector = payload.get("vector", {})
    if isinstance(vector, dict):
        dx = _float(vector.get("dx", 0.0))
        dy = _float(vector.get("dy", 0.0))
    elif isinstance(vector, list) and len(vector) >= 2:
        dx = _float(vector[0])
        dy = _float(vector[1])
    else:
        dx = dy = 0.0
    reason = str(payload.get("reason", "model deliberation")).strip() or "model deliberation"
    confidence = clamp(_float(payload.get("confidence", 0.55)))
    intensity = clamp(_float(payload.get("intensity", 0.55)))
    return Action(kind, dx, dy, intensity, "model", reason, confidence).normalized()


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        decoded = json.loads(stripped[start : end + 1])
    if not isinstance(decoded, dict):
        raise ValueError("model action payload must be an object")
    return decoded


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
