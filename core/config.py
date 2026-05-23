from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class CodexStandardsConfig:
    """Small typed config surface for cross-repo LLM/eval plumbing."""

    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    llm_temperature: float
    llm_max_tokens: int
    tracing_enabled: bool
    tracing_backend: str
    tracing_jsonl_path: str
    eval_pass_threshold: float
    eval_dataset_glob: str
    prompt_root: str

    @classmethod
    def from_env(cls, *, prefix: str = "CODEX_") -> "CodexStandardsConfig":
        return cls(
            llm_base_url=os.getenv(f"{prefix}LLM_BASE_URL", "https://api.openai.com/v1").strip(),
            llm_api_key=os.getenv(f"{prefix}LLM_API_KEY", "").strip(),
            llm_model=os.getenv(f"{prefix}LLM_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
            llm_timeout_seconds=_env_float(f"{prefix}LLM_TIMEOUT_SECONDS", 30.0),
            llm_max_retries=_env_int(f"{prefix}LLM_MAX_RETRIES", 2),
            llm_temperature=_env_float(f"{prefix}LLM_TEMPERATURE", 0.2),
            llm_max_tokens=_env_int(f"{prefix}LLM_MAX_TOKENS", 800),
            tracing_enabled=_env_bool(f"{prefix}TRACING_ENABLED", False),
            tracing_backend=os.getenv(f"{prefix}TRACING_BACKEND", "noop").strip() or "noop",
            tracing_jsonl_path=os.getenv(
                f"{prefix}TRACING_JSONL_PATH",
                ".codex-traces/llm-trace.jsonl",
            ).strip(),
            eval_pass_threshold=_env_float(f"{prefix}EVAL_PASS_THRESHOLD", 1.0),
            eval_dataset_glob=os.getenv(f"{prefix}EVAL_DATASET_GLOB", "evals/cases/**/*.json").strip()
            or "evals/cases/**/*.json",
            prompt_root=os.getenv(f"{prefix}PROMPT_ROOT", "prompts").strip() or "prompts",
        )


@dataclass(frozen=True)
class AquagenesysRuntimeConfig:
    """Typed runtime config for the v0.3.6 local ecology service."""

    host: str
    port: int
    seed: int
    width: int
    height: int
    initial_population: int
    max_population: int
    deliberation_enabled: bool
    deliberation_interval_ticks: int
    global_deliberations_per_tick: int
    fish_model_budget: int
    model_intent_ttl: int
    max_inflight_model_calls: int
    ecology_update_interval: int
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    llm_temperature: float
    llm_max_tokens: int
    trace_backend: str
    trace_jsonl_path: str
    archive_dir: str
    archive_every_ticks: int
    instruction_inheritance_enabled: bool
    model_teaching_enabled: bool

    @classmethod
    def from_env(cls, *, prefix: str = "AQUAGENESYS_") -> "AquagenesysRuntimeConfig":
        return cls(
            host=os.getenv(f"{prefix}HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_env_int(f"{prefix}PORT", 8765),
            seed=_env_int(f"{prefix}SEED", 42),
            width=_env_int(f"{prefix}WIDTH", 96),
            height=_env_int(f"{prefix}HEIGHT", 60),
            initial_population=_env_int(f"{prefix}INITIAL_POPULATION", 42),
            max_population=_env_int(f"{prefix}MAX_POPULATION", 140),
            deliberation_enabled=_env_bool(f"{prefix}DELIBERATION_ENABLED", True),
            deliberation_interval_ticks=_env_int(f"{prefix}DELIBERATION_INTERVAL_TICKS", 36),
            global_deliberations_per_tick=_env_int(f"{prefix}GLOBAL_DELIBERATIONS_PER_TICK", 1),
            fish_model_budget=_env_int(f"{prefix}FISH_MODEL_BUDGET", 3),
            model_intent_ttl=_env_int(f"{prefix}MODEL_INTENT_TTL", 14),
            max_inflight_model_calls=_env_int(f"{prefix}MAX_INFLIGHT_MODEL_CALLS", 1),
            ecology_update_interval=_env_int(f"{prefix}ECOLOGY_UPDATE_INTERVAL", 4),
            llm_base_url=os.getenv(f"{prefix}LLM_BASE_URL", "http://127.0.0.1:8008/v1").strip()
            or "http://127.0.0.1:8008/v1",
            llm_api_key=os.getenv(f"{prefix}LLM_API_KEY", "").strip(),
            llm_model=os.getenv(f"{prefix}LLM_MODEL", "Lexi").strip() or "Lexi",
            llm_timeout_seconds=_env_float(f"{prefix}LLM_TIMEOUT_SECONDS", 1.8),
            llm_max_retries=_env_int(f"{prefix}LLM_MAX_RETRIES", 0),
            llm_temperature=_env_float(f"{prefix}LLM_TEMPERATURE", 0.1),
            llm_max_tokens=_env_int(f"{prefix}LLM_MAX_TOKENS", 140),
            trace_backend=os.getenv(f"{prefix}TRACE_BACKEND", "noop").strip() or "noop",
            trace_jsonl_path=os.getenv(
                f"{prefix}TRACE_JSONL_PATH",
                "/tmp/aquagenesys-v03/llm-trace.jsonl",
            ).strip()
            or "/tmp/aquagenesys-v03/llm-trace.jsonl",
            archive_dir=os.getenv(f"{prefix}ARCHIVE_DIR", "/tmp/aquagenesys-v03").strip()
            or "/tmp/aquagenesys-v03",
            archive_every_ticks=_env_int(f"{prefix}ARCHIVE_EVERY_TICKS", 25),
            instruction_inheritance_enabled=_env_bool(f"{prefix}INSTRUCTION_INHERITANCE_ENABLED", True),
            model_teaching_enabled=_env_bool(f"{prefix}MODEL_TEACHING_ENABLED", False),
        )
