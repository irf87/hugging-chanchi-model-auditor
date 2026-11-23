# Phase 1 exit signal (read 2026-11-23)

**Signal** (design, *Adoption plan*, phase 1): three consecutive changes whose executor sessions
carry the tag `agent-chanchi-executor`, each audited with verdict `accepted` and the note
`gate:first-green`, and at least one with the note `verify:feature-map`.

**Reading taken:** an attempt superseded by a retry whose reason is outside the executor's work
(`retry_reason` in `NON_EXECUTOR_RETRY_REASONS`: `plan_fix`, `human_change`, `env`, as
`src/chanchi/taxonomy.py` defines and `src/chanchi/scoring.py` `executor_records` applies) does not
count; the retry is what the change delivered. An attempt retried for `executor_failure` would
count. The only such case here is `global-items-phase3` S3: attempt 1 (agy, `explore`) was
rejected for an `env_issue`, and attempt 2 ran on another executor (claude sonnet medium). Sessions
of other agents are not executor sessions: `global-items-phase1` S6 (researcher) and
`global-items-phase3` S4 attempts 1-2 (item builder).

**Source:** `chanchi show <change>` for each change below, and the same rows read with
`sqlite3 ~/.local/share/chanchi/chanchi.db` (sessions joined to changes, project
`hugging-chanchi-model-auditor`).

| Change | Executor session (attempt) | Verdict | Session notes |
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
| | S3 (1), tag `explore` | rejected | (none); incident `env_issue`: headless agy auto-denied the command permission |
| | S3 (2), `retry_reason: env` | accepted | gate:first-green |

Changes left out and why:

- `chanchi-agents-phase1` (before): its only `agent-chanchi-executor` session, S4, was
  `accepted_with_fixes` (S1-S3 carry no agent tag). `user-ownership-guard`: S1 was
  `accepted_with_fixes`.
- `global-items-phase4` (after): S4 and S5 were `accepted_with_fixes` without `gate:first-green`.
  So `global-items-phase2` to `-phase4` do not qualify; `-phase1` to `-phase3` do.

Between `global-items-phase1` and `global-items-phase3` no other change was opened in this
project (change ids 81, 82, 83 are consecutive).

Audited in chanchi audit 11, round 1, `accepted` (degraded: two google seats); reports
`phase1-close-round1-*.md` in this folder.
