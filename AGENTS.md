# AGENTS.md

This repo follows:
- `/home/unix/codex-standards/BASELINE.md`
Repo-specific overrides and invariants below.

## Muninn Memory Integration (Required)
Use Muninn as durable memory for decisions, constraints, runbooks, interfaces, and validated lessons.

On task start (before substantial edits):
- Call `muninn.spaces.resolve` with current absolute `cwd`.
- Use the returned `space.key` as `<resolved-space-key>` for retrieval calls.
- Preferred: call `muninn.rehydrate.bundle` with:
  - `lens`: `{space_key:"<resolved-space-key>", scope:"soft", kinds:["decision","constraint","runbook","interface"], limit:12}`
  - `query`: short task summary.
- Compatibility sequence (when bundle is unavailable):
  - `muninn.cards.recent` with `lens`: `{space_key:"<resolved-space-key>", scope:"strict", kinds:["decision","constraint","runbook","interface"], limit:12}`
  - `muninn.cards.search` with `lens`: `{space_key:"<resolved-space-key>", scope:"soft", kinds:["decision","constraint","runbook","interface"], limit:12}` and short task query.
- If `space_key` is unavailable, pass a full lens with `space:"auto"` and absolute `cwd`.
- Use retrieved memory to inform plan and edits before implementing.

On meaningful completion:
- Write durable outcomes via `muninn.cards.upsert` (target `1-3` cards per task).
- Send object-shaped upsert arguments only (never prose strings for `card`).
- Canonical upsert payload:

```json
{
  "lens": {
    "space_key": "<resolved-space-key>",
    "scope": "strict"
  },
  "card": {
    "kind": "decision",
    "title": "Summarize the durable decision",
    "summary": "One to three sentences with the durable outcome.",
    "body": "Durable details that should survive future sessions."
  },
  "evidence": [
    {"type": "file", "ref": "/abs/path/file.py:42"}
  ]
}
```

- For `decision`, `constraint`, `interface`, and `runbook`, include at least one evidence ref whenever applicable.
- If evidence is unavailable, do not fabricate it; delay the durable write or mark explicit follow-up and treat it as non-compliant until evidence is added.
- Use `muninn.cards.supersede` or `muninn.cards.merge` when refining existing memory, not duplicate cards.

Memory hygiene:
- Do not persist transient reasoning, scratch notes, or speculative output.
- Prefer `strict` scope by default; use `soft` only when cross-project recall is intentional.
- Regression gate command:
  - `cd /mnt/data/Muninn && PYTHONPATH=src python3 -m muninn.cli audit --last 24h --json --gate`

## Mission
Describe the repository mission and operating mode.

## Repo-Specific Invariants
- Add domain constraints and hard rules here.

## Definition of Done
- List required checks and acceptance gates for this repo.

## Architecture and Operations Source of Truth
- Architecture truth: `ARCHITECTURE_CHECKPOINT.md` (if present)
- Operational procedures: `RUNBOOK.md` (if present)

## Overrides
- `GIT_POLICY: conservative`
- rationale: default non-destructive posture.
