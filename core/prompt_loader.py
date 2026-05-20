from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Mapping


_PROMPT_EXTENSIONS = (".md", ".jinja")
_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
_VERSION_RE = re.compile(r"(?:^|[._-])v(?P<version>\d+(?:\.\d+)*)$")


@dataclass(frozen=True)
class PromptDocument:
    name: str
    path: Path
    raw_text: str
    sha256: str
    version: str


@dataclass(frozen=True)
class PromptRender:
    document: PromptDocument
    text: str
    input_hash: str


class PromptNotFoundError(FileNotFoundError):
    pass


class PromptRenderError(ValueError):
    pass


class PromptLoader:
    """Deterministic repo-local prompt loader with content hashing."""

    def __init__(self, root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "prompts"
        self._root = Path(root) if root is not None else default_root

    @property
    def root(self) -> Path:
        return self._root

    def load(self, name: str) -> PromptDocument:
        path = self._resolve_path(name)
        raw_text = path.read_text(encoding="utf-8")
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return PromptDocument(
            name=name,
            path=path,
            raw_text=raw_text,
            sha256=sha256,
            version=_infer_version(path),
        )

    def render(self, name: str, params: Mapping[str, object] | None = None) -> PromptRender:
        document = self.load(name)
        rendered = _render_placeholders(document.raw_text, params or {})
        input_hash = _hash_mapping(params or {})
        return PromptRender(document=document, text=rendered, input_hash=input_hash)

    def _resolve_path(self, name: str) -> Path:
        candidate = self.root / name
        search_paths = []
        if candidate.suffix:
            search_paths.append(candidate)
        else:
            for suffix in _PROMPT_EXTENSIONS:
                search_paths.append(candidate.with_suffix(suffix))
        for path in search_paths:
            if path.exists() and path.is_file():
                return path
        raise PromptNotFoundError(f"Prompt '{name}' was not found under {self.root}")


def _render_placeholders(text: str, params: Mapping[str, object]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in params:
            missing.add(key)
            return match.group(0)
        return str(params[key])

    rendered = _PLACEHOLDER_RE.sub(replace, text)
    if missing:
        missing_keys = ", ".join(sorted(missing))
        raise PromptRenderError(f"Missing prompt params: {missing_keys}")
    return rendered


def _hash_mapping(params: Mapping[str, object]) -> str:
    if not params:
        return hashlib.sha256(b"{}").hexdigest()
    items = [f"{key}={params[key]!r}" for key in sorted(params)]
    joined = "\n".join(items)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _infer_version(path: Path) -> str:
    stem = path.stem
    match = _VERSION_RE.search(stem)
    if match:
        return f"v{match.group('version')}"
    return "unversioned"

