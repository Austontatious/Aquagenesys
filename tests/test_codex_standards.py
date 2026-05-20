from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "CODEX_STANDARDS.md"
SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
SCAN_FILE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
SCAN_EXCLUDES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
}
INLINE_PROMPT_RE = re.compile(
    r"You are (?:[A-Z]|an?\s|the\s|[a-z]+ing)|"
    r"messages\s*=\s*\[\s*\{\s*['\"]role['\"]\s*:\s*['\"]system['\"]|"
    r"SYSTEM_PROMPT\s*=",
    re.MULTILINE,
)
ENV_LOOKUP_RE = re.compile(
    r"os\.getenv\(|os\.environ\.get\(|process\.env(?:\.[A-Za-z_][A-Za-z0-9_]*|\[)",
    re.MULTILINE,
)
DIRECT_SDK_RE = re.compile(
    r"from\s+openai\s+import|import\s+openai\b|OpenAI\(|AsyncOpenAI\(|"
    r"from\s+anthropic\s+import|import\s+anthropic\b|Anthropic\(|AsyncAnthropic\(|"
    r"import\s+litellm\b|from\s+litellm\s+import|import\s+google\.generativeai\b",
    re.MULTILINE,
)


def _parse_sections() -> dict[str, list[str]]:
    text = DOC_PATH.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        match = SECTION_RE.match(raw_line.strip())
        if match:
            current = match.group("title").strip()
            sections.setdefault(current, [])
            continue
        if current and raw_line.lstrip().startswith("- "):
            item = raw_line.split("`")
            value = item[1] if len(item) >= 3 else raw_line.lstrip()[2:].strip()
            sections[current].append(value)
    return sections


def _iter_scan_files(scan_roots: list[str]) -> list[Path]:
    files: list[Path] = []
    for rel in scan_roots:
        root = REPO_ROOT / rel
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix in SCAN_FILE_SUFFIXES and not any(part in SCAN_EXCLUDES for part in root.parts):
                files.append(root)
            continue
        for path in root.rglob("*"):
            if any(part in SCAN_EXCLUDES for part in path.parts):
                continue
            if path.is_file() and path.suffix in SCAN_FILE_SUFFIXES:
                files.append(path)
    return files


def _is_allowed(rel: str, allowed: set[str]) -> bool:
    for prefix in allowed:
        normalized = prefix.rstrip("/")
        if rel == normalized or rel.startswith(normalized + "/"):
            return True
    return False


def _scan_for_violations(
    *,
    section_name: str,
    allowed_section: str,
    exception_section: str,
    pattern: re.Pattern[str],
) -> list[str]:
    sections = _parse_sections()
    scan_roots = sections.get(section_name, [])
    assert scan_roots, f"{section_name} must be declared"
    allowed = set(sections.get(allowed_section, []))
    exceptions = set(sections.get(exception_section, []))
    failures: list[str] = []
    for path in _iter_scan_files(scan_roots):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _is_allowed(rel, allowed) or rel in exceptions:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
            failures.append(rel)
    return sorted(failures)


def test_codex_standards_doc_exists() -> None:
    assert DOC_PATH.exists(), "docs/CODEX_STANDARDS.md is required"


def test_baseline_reference_present() -> None:
    sections = _parse_sections()
    assert "/home/unix/codex-standards/BASELINE.md" in sections.get("Baseline Reference", [])


def test_required_directories_exist() -> None:
    sections = _parse_sections()
    for rel in sections.get("Required Directories", []):
        assert (REPO_ROOT / rel).is_dir(), f"missing required directory: {rel}"


def test_required_files_exist() -> None:
    sections = _parse_sections()
    required_files = sections.get("Required Files", [])
    assert required_files, "required files must be declared"
    for rel in required_files:
        assert (REPO_ROOT / rel).exists(), f"missing required file: {rel}"


def test_make_targets_exist() -> None:
    makefile = REPO_ROOT / "Makefile"
    assert makefile.exists(), "Makefile is required"
    text = makefile.read_text(encoding="utf-8")
    sections = _parse_sections()
    for target in sections.get("Make Targets", []):
        assert re.search(rf"(?m)^[.]PHONY:.*\b{re.escape(target)}\b|^{re.escape(target)}:", text), (
            f"missing required make target: {target}"
        )


def test_eval_runner_check_passes() -> None:
    runner = REPO_ROOT / "evals" / "runner.py"
    assert runner.exists(), "evals/runner.py is required"
    result = subprocess.run(
        [sys.executable, str(runner), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_untracked_inline_prompts() -> None:
    failures = _scan_for_violations(
        section_name="Prompt Scan Roots",
        allowed_section="Canonical Prompt Surfaces",
        exception_section="Temporary Prompt Exceptions",
        pattern=INLINE_PROMPT_RE,
    )
    assert not failures, "inline prompts must be extracted or declared: " + ", ".join(failures)


def test_no_untracked_env_lookups() -> None:
    failures = _scan_for_violations(
        section_name="Config Scan Roots",
        allowed_section="Canonical Config Surfaces",
        exception_section="Temporary Config Exceptions",
        pattern=ENV_LOOKUP_RE,
    )
    assert not failures, "env lookups must be centralized or declared: " + ", ".join(failures)


def test_no_direct_model_sdk_usage() -> None:
    failures = _scan_for_violations(
        section_name="Model Interface Scan Roots",
        allowed_section="Canonical Model Interface Surfaces",
        exception_section="Temporary Model Interface Exceptions",
        pattern=DIRECT_SDK_RE,
    )
    assert not failures, "direct model SDK usage must stay behind interface surfaces: " + ", ".join(failures)
