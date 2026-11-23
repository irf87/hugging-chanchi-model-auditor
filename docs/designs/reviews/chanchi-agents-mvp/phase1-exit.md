# Phase 1 exit signal (read 2026-11-23)

**Signal** (design, *Adoption plan*, phase 1): three consecutive changes whose executor sessions
carry the tag `agent-chanchi-executor`, each audited with verdict `accepted` and the note
`gate:first-green`, and at least one with the note `verify:feature-map`.

**Reading taken:** a session counts by its last attempt; an earlier attempt rejected for a cause
outside the executor's work (`retry_reason: env`) is retried, not accepted, and the retry is what
the change delivered. Sessions of other agents (researcher, item builder) are not executor sessions.

**Source:** `chanchi show <change>` for each change below, and the same rows read with
`sqlite3 ~/.local/share/chanchi/chanchi.db` (sessions joined to changes, project
`hugging-chanchi-model-auditor`).

| Change | Executor session (attempt) | Verdict | Notes |
|---|---|---|---|
| `global-items-phase1` | S1 (1) | accepted | gate:first-green verify:feature-map |
| | S2 (1) | accepted | gate:first-green verify:feature-map |
| | S3 (1) | accepted | gate:first-green verify:feature-map |
| | S4 (1) | accepted | gate:first-green verify:feature-map |
| | S5 (1) | accepted | gate:first-green verify:feature-map |
| `global-items-phase2` | S1 (1) | accepted | gate:first-green verify:feature-map |
| | S2 (1) | accepted | gate:first-green verify:feature-map |
| | S3 (1) | accepted | gate:first-green verify:feature-map |
| `global-items-phase3` | S1 (1) | accepted | gate:first-green verify:feature-map |
| | S2 (1) | accepted | gate:first-green verify:feature-map |
| | S3 (1), tag `explore` | rejected | incident `env_issue`: headless agy auto-denied the command permission |
| | S3 (2), `retry_reason: env` | accepted | gate:first-green |

Changes left out and why:

- `chanchi-agents-phase1` and `user-ownership-guard` (before): their executor sessions were
  `accepted_with_fixes`.
- `global-items-phase4` (after): S4 and S5 were `accepted_with_fixes` without `gate:first-green`.
  So `global-items-phase2` to `-phase4` do not qualify; `-phase1` to `-phase3` do.

Between `global-items-phase1` and `global-items-phase3` no other change was opened in this
project (change ids 81, 82, 83 are consecutive).
