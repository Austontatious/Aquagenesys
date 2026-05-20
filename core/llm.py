from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request

from core.trace import LLMTraceRecord, NoopTraceSink, TokenUsage, TraceSink


CostHook = Callable[[str, TokenUsage, Mapping[str, Any]], None]


@dataclass(frozen=True)
class LLMClientConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0
    max_retries: int = 2
    temperature: float = 0.2
    max_tokens: int = 800
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    usage: TokenUsage
    raw_response: dict[str, Any]
    latency_ms: int


class LLMRequestError(RuntimeError):
    pass


class LLMClient:
    """OpenAI-compatible chat client with retries, tracing, and token hooks."""

    def __init__(
        self,
        config: LLMClientConfig,
        *,
        trace_sink: TraceSink | None = None,
        cost_hook: CostHook | None = None,
    ) -> None:
        self._config = config
        self._trace_sink = trace_sink or NoopTraceSink()
        self._cost_hook = cost_hook

    def complete(
        self,
        *,
        prompt_name: str,
        prompt_sha256: str,
        prompt_version: str,
        user_prompt: str,
        system_prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        model_override: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CompletionResult:
        payload_messages = _normalize_messages(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            messages=messages,
        )
        model = (model_override or self._config.model).strip() or self._config.model
        payload = {
            "model": model,
            "messages": payload_messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        started = time.perf_counter()
        response = self._post_with_retries(payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        text = _extract_text(response)
        usage = _extract_usage(response)
        if self._cost_hook is not None:
            self._cost_hook(model, usage, metadata or {})
        record = LLMTraceRecord.create(
            prompt_name=prompt_name,
            prompt_sha256=prompt_sha256,
            prompt_version=prompt_version,
            prompt_text=_joined_prompt_text(payload_messages),
            model=model,
            response_text=text,
            latency_ms=latency_ms,
            usage=usage,
            metadata=metadata,
        )
        self._trace_sink.write(record)
        return CompletionResult(
            text=text,
            model=model,
            usage=usage,
            raw_response=response,
            latency_ms=latency_ms,
        )

    def _post_with_retries(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                return _post_json(self._config, payload)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = exc
                if attempt >= self._config.max_retries:
                    break
                time.sleep(min(2**attempt, 4))
        raise LLMRequestError(f"LLM request failed: {last_error}") from last_error


def _normalize_messages(
    *,
    user_prompt: str,
    system_prompt: str | None,
    messages: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    if messages:
        return messages
    payload_messages: list[dict[str, str]] = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.append({"role": "user", "content": user_prompt})
    return payload_messages


def _post_json(config: LLMClientConfig, payload: Mapping[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", **config.headers}
    if config.api_key:
        headers.setdefault("Authorization", f"Bearer {config.api_key}")
    request = urllib.request.Request(
        _chat_url(config.base_url),
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
    if isinstance(decoded, dict) and decoded.get("error"):
        raise ValueError(f"LLM backend returned error payload: {decoded['error']}")
    return decoded


def _chat_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    if "/v1/" in normalized:
        return normalized
    return f"{normalized}/v1/chat/completions"


def _extract_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response did not include choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
        return "".join(parts).strip()
    raise ValueError("LLM response did not include textual content")


def _extract_usage(payload: Mapping[str, Any]) -> TokenUsage:
    usage = payload.get("usage", {})
    if not isinstance(usage, Mapping):
        return TokenUsage()
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _joined_prompt_text(messages: list[dict[str, str]]) -> str:
    lines = [f"{message.get('role', 'user')}: {message.get('content', '')}" for message in messages]
    return "\n".join(lines).strip()
