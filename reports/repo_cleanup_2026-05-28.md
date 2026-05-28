# Repository Cleanup Report - 2026-05-28

> Status: GENERATED REPORT. This file records the conservative cleanup pass performed on 2026-05-28. Do not treat it as architecture authority; confirm current behavior against the canonical docs, code, and tests.

## Scope

- Repository: `/mnt/data/Aquagenesys`
- Cleanup mode: two-pass conservative cleanup.
- Policy: preserve generated evidence and version chronology; no meaningful files deleted.

## Pass 1 Inventory

Current canonical docs:

- `README.md` - project overview, run commands, architecture, recovery assays, validation, configuration, and limitations.
- `AGENTS.md` - global baseline pointer and repo-local invariants.
- `docs/CODEX_STANDARDS.md` - repo-local standards contract.
- `docs/decisions/` - chronological architecture decision records.

Preexisting drift observed before cleanup:

- Worktree was clean before cleanup.
- `reports/` contained versioned JSON/Markdown implementation and validation reports.

## Classification

- `CURRENT_CANONICAL`: `README.md`, `AGENTS.md`, `docs/CODEX_STANDARDS.md`, current code/tests/evals, latest applicable decision records.
- `HISTORICAL_EVIDENCE`: chronological ADRs and earlier version reports.
- `GENERATED_ARTIFACT`: JSON/Markdown report pairs in `reports/`.
- `REVIEW_NEEDED`: none identified.

## Pass 2 Cleanup

- Added `docs/README.md` as the documentation index.
- Added `reports/README.md` with generated-evidence status.
- Added this cleanup report under `reports/`.
- Updated `README.md` with canonical doc/report pointers.
- Did not move reports because their version/date ordering is already clear and useful.

## Files Moved

- None.

## Deletion Candidates Requiring Approval

- None proposed.

## Validation

Validation recorded after edits:

- `git diff --check` - passed.
- `python3 -m pytest -q tests/test_codex_standards.py --noconftest` - passed, 9 tests.
- `python3 evals/runner.py --check` - passed, 6 case files.
- `make lint` - passed.
- `bash /mnt/data/.codex_ssot/v1/tools/agents_lint.sh` - exited 0, `FAIL=0`; reported preexisting WARNs for this repo's `AGENTS.md` governance sections.

## Remaining Risk

- No cleanup-specific unresolved drift identified at report creation.
