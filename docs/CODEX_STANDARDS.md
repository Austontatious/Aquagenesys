# CODEX Standards

## Baseline Reference
- `/home/unix/codex-standards/BASELINE.md`

## Required Directories
- `prompts/`
- `prompts/system/`
- `prompts/tasks/`
- `prompts/evals/`
- `evals/`
- `evals/datasets/`
- `evals/cases/`
- `core/`
- `tests/`
- `docs/`

## Required Files
- `Makefile`
- `core/config.py`
- `core/prompt_loader.py`
- `core/llm.py`
- `core/trace.py`
- `evals/runner.py`
- `tests/test_codex_standards.py`

## Make Targets
- `run`
- `test`
- `eval`
- `lint`

## Prompt Scan Roots
- `aquagenesys/`

## Config Scan Roots
- `aquagenesys/`

## Model Interface Scan Roots
- `aquagenesys/`

## Canonical Config Surfaces
- `core/config.py`
- `.env.example`

## Canonical Prompt Surfaces
- `prompts/`

## Canonical Model Interface Surfaces
- `core/llm.py`

## Temporary Prompt Exceptions
- None.

## Temporary Config Exceptions
- None.

## Temporary Model Interface Exceptions
- None.

## Core Rules
- No inline prompts in runtime code.
- No direct model SDK usage outside canonical interface surfaces.
- No ad hoc env lookups outside canonical config surfaces.
- Eval scaffolding and tracing are mandatory.

## Contract Change Rules
- Request/response schema changes require a version bump.
- Shared contract changes require cross-repo compatibility review and test updates.

## Anti-Bloat Rule
- Do not add speculative frameworks, routers, or wrappers without runtime proof.

## Simplicity Rule
- Remove layers that do not improve correctness, observability, or control.

## Validation
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest`
- `python3 evals/runner.py --check`
