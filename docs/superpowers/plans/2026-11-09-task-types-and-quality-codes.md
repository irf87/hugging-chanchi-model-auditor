# Plan: architecture/unit-test task types and code-quality incident codes

Date: 2026-11-09. Change ref: `task-types-and-quality-codes` (adhoc). Branch:
`feat/task-types-and-quality-codes`. Baseline: `uv run pytest -q` -> 142 passed.

## Goal

Let `chanchi` rate models on two more kinds of work (architecture design, unit tests) and record two
more kinds of code-quality fault (architecture violations, code smells). Everything is additive:
no existing row, code, weight or score changes meaning.

## Decisions (made by the planner; do not revisit)

1. **New task types**, seeded by a new migration `002` so fresh installs get them and existing
   databases receive them on their next command:
   - `architecture-design` - "Define or change module boundaries, layering, dependency direction or public interfaces"
   - `unit-tests` - "Write or repair isolated unit tests (use tests for integration, device or end-to-end work)"
   The existing `tests` type and its description stay untouched (existing users may have rated
   sessions with it).
2. **The migration must be safe for databases that already hold these codes.** A user may have run
   `chanchi taxonomy add-type unit-tests --description "..."` already. Use `INSERT OR IGNORE`
   (`task_types.code` is the primary key): the user's own row and description win.
3. **New incident codes**, both fixed role `executor`, no schema change (`incidents.code` is free
   text; the closed set lives in `taxonomy.py`):
   - `architecture_violation` - weight **2.0** - "Broke layering, module boundaries or dependency direction, or added coupling the design forbids."
   - `code_smell` - weight **1.0** - "Works and passes verification but hurts maintainability: duplication, oversized functions, misleading names, dead code."
4. **Precedence between executor quality codes** (goes in the rubric): a broken *written* project
   rule is `rule_violation`; wrong behaviour or a weak test is `quality_defect`; a structural fault
   with no written rule is `architecture_violation`; working-but-hard-to-maintain code is
   `code_smell` (usually severity `low`). One incident per fault: pick the most specific code.
5. Session complexity is rated `medium` for both sessions (code + docs layers, 4-10 files).

## Rules for every executor session

- English only in code, docs and commits. Do not commit, stash, branch or touch git state; the
  planner commits after the audit.
- Work only in the files listed under the session. Do not edit anything under `docs/superpowers/plans/`.
- NEVER run `chanchi` against the real database. Prefix every `uv run chanchi ...` call with
  `CHANCHI_DB=<scratch db path given in your prompt>`. (`pytest` already isolates itself.)
- If something is undefined, contradicts the code, or needs a decision not written here: STOP, do
  not improvise, and say so in the report. Stopping correctly is the desired behaviour.
- Match the existing style (type hints, ruff-clean, test naming). No new dependencies.

## Session S1 - migration 002 and task types (`db-schema-migration`, medium, 5 tasks)

Files you may touch: `src/chanchi/migrations/002_more_task_types.sql` (new),
`src/chanchi/taxonomy.py` (only `TASK_TYPES` and its comment), `src/chanchi/data/template.db`
(regenerated, never hand-edited), `tests/test_catalog.py`, `tests/test_db.py`,
`docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` (sections 3 file tree and 4.1 only).

- **1.1** Create `002_more_task_types.sql` with one `INSERT OR IGNORE INTO task_types (code, description) VALUES ...`
  for the two types of decision 1, descriptions verbatim. No semicolons inside descriptions.
- **1.2** Append the same two tuples, in the same order, to `taxonomy.TASK_TYPES` and update its
  comment to say migrations 001 and 002 insert exactly these, in this order.
- **1.3** Regenerate the committed template:
  `CHANCHI_DB=<scratch> uv run chanchi db migrate --template`, then confirm
  `CHANCHI_DB=<scratch> uv run chanchi db status` shows the template at version 2.
- **1.4** Tests: update the task-type count in `tests/test_catalog.py` (11 -> 13). In
  `tests/test_db.py` add a test that builds a database with only migration 1 applied
  (`db.apply_migrations(conn, db.migrations()[:1])`), inserts a custom task type and a custom
  `unit-tests` row with its own description, then applies all migrations and asserts: `applied == [2]`,
  `user_version == 2`, the custom `unit-tests` description is preserved, `architecture-design` exists,
  the custom type is untouched. Reuse the pattern of the existing v1-to-v2 data-preservation test.
- **1.5** Spec: list the two types in section 4.1 and `002_more_task_types.sql` in the file tree.

Verify (paste the real output in the report): `uv run pytest -q` (must be >= 143 passed, 0 failed);
`CHANCHI_DB=<fresh scratch path> uv run chanchi taxonomy list | jq '.task_types | length'` -> 13;
`uv run ruff check .` if ruff is configured, otherwise say it is not.

## Session S2 - incident codes (`business-logic`, medium, 5 tasks)

Files you may touch: `src/chanchi/taxonomy.py` (only `INCIDENT_CODES`, `EXECUTOR_WEIGHTS`),
`skills/chanchi-session-audit/references/rubric.md`, `tests/test_taxonomy.py`, `tests/test_scoring.py`,
`docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` (section 5 codes table and the
executor weights table only).

- **2.1** Add `architecture_violation` and `code_smell` to `INCIDENT_CODES` right after
  `quality_defect`, role `executor`, descriptions verbatim from decision 3.
- **2.2** Add their weights (2.0 and 1.0) to `EXECUTOR_WEIGHTS`.
- **2.3** Rubric: add one table row per code to "From observation to incident code", add the
  precedence rule of decision 4 as a short subsection, and add one worked example for each code.
  Every code name must appear in backticks (an existing test enforces it).
- **2.4** Tests: in `tests/test_taxonomy.py` assert both codes exist with role `executor` and the
  weights above, and that `describe()` lists them. In `tests/test_scoring.py` add score cases:
  `architecture_violation` severity `medium` detected `planner_audit` on an `accepted_with_fixes`
  session -> 66.0; `code_smell` severity `low` on an `accepted` session -> 99.0. Follow the helpers
  already used there.
- **2.5** Spec: add both rows to the section 5 codes table and to the executor weights table
  (2.0 next to `scope_drift`, 1.0 as its own row).

Verify (paste the real output): `uv run pytest -q` (all passed, count not lower than after S1);
`CHANCHI_DB=<scratch> uv run chanchi taxonomy list | jq '.taxonomy.incident_codes[] | select(.code=="architecture_violation" or .code=="code_smell")'`
shows role `executor` and weights 2.0 / 1.0.

## Report format (written to the path given in the prompt)

`Status` (COMPLETE, STOPPED or BLOCKED), `Files changed`, `Verification` (each command with its
output), `Choices the plan left open` (or "none"), `Stops and questions` (or "none").
