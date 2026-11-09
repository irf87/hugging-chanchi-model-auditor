# Plan: per-dimension executor stats (`chanchi stats --by dimension`)

Date: 2026-11-09. Change ref: `dimension-stats` (adhoc). Branch: `feat/dimension-stats`.
Baseline: `uv run pytest -q` -> 147 passed. **No schema change and no migration.**

## Goal

Show how each model performs on code-quality dimensions (correctness, architecture, clean code,
honesty, discipline) using the incidents already recorded. A new read-only view derived from
`incidents.code`; nothing is stored, so it also works on the existing history.

## Decisions (made by the planner; do not revisit)

1. **Dimensions** (closed set in `taxonomy.py`, kebab-case names, executor-role codes only):

   | Dimension | Codes |
   |---|---|
   | `correctness` | `quality_defect`, `incomplete_work` |
   | `architecture` | `architecture_violation` |
   | `clean-code` | `code_smell` |
   | `honesty` | `false_claim`, `hallucination` |
   | `discipline` | `rule_violation`, `scope_drift`, `improvised_decision` |

   `correct_stop` belongs to no dimension (it only feeds the session score). Planner, human and
   neutral codes belong to no dimension. Every code of `EXECUTOR_WEIGHTS` is in exactly one
   dimension.
2. **Dimension score of one audited session** =
   `clamp(100 - penalty, 0, 100)`, where `penalty` sums `weight * severity_multiplier * late_multiplier`
   (the existing `_penalty` and `EXECUTOR_WEIGHTS`) over the session's **executor-role** incidents
   whose code is in that dimension. The verdict base and the `correct_stop` credit are NOT used.
3. **Aggregation** reuses the existing machinery: mean over a model's audited sessions, smoothed with
   `smoothed(mean, n, prior)` where `prior` is the mean of that dimension's session scores across all
   records in scope (same filters), and `confidence(n)`. Records come from the existing
   `executor_records` (same exclusions: unaudited sessions, attempts superseded by a non-executor retry).
4. **`stats --by dimension` is executor-only.** For `--role planner` it must fail through the existing
   `validate_choice` error (the valid values then do not include `dimension`). `--role human` ignores
   `--by`, as today.
5. **Honesty about what the number means.** A dimension row with no incidents scores 100, which is
   absence of recorded faults, not proof of quality. The result therefore carries a top-level
   `note` (exact text below) and every row carries `n`, `incident_count`, `sessions_with_incidents`
   and `confidence`.
6. Output shape. Top level: `{"role": "executor", "by": "dimension", "rows": [...], "note": "<text>"}`.
   Each row: `agent`, `model`, `effort`, `dimension`, `spec`, `cost_tier`, `n`, `incident_count`,
   `sessions_with_incidents`, `incidents_per_session` (3 decimals), `mean_score` (2 decimals),
   `smoothed_score` (2), `prior` (2), `confidence`, `top_codes` (up to 3, only codes of that dimension).
   Rows sorted by the dimension's order in `DIMENSIONS`, then `-smoothed_score`, then `spec`.
   Exact `note` text: `Dimension scores count only faults the auditor recorded: 100 means no recorded fault, not proven quality. Read them with n and confidence.`
7. `chanchi taxonomy list` gains a `"dimensions"` key (list of `{"dimension", "codes"}`) and
   `chanchi scoring explain` gains a `"dimension_score"` key (formula, the dimensions, `correct_stop`
   excluded, the same note).

## Rules for every executor session

- English only in code, docs and commits. Do not commit, stash, branch or touch git state; the
  planner commits after the audit.
- Work only in the files listed under the session. Do not edit anything under `docs/superpowers/plans/`.
- NEVER run `chanchi` against the real database. Prefix every `uv run chanchi ...` call with
  `CHANCHI_DB=<scratch db path given in your prompt>`. (`pytest` already isolates itself.)
- If something is undefined, contradicts the code, or needs a decision not written here: STOP, do
  not improvise, and say so in the report. Stopping correctly is the desired behaviour.
- If adding the feature makes an existing test fail only because it asserts an exact key set or
  count, make the minimal adaptation in the allowed test file and list it under "Choices the plan
  left open".
- Match the existing style (type hints, line length). No new dependencies.

## Session S3 - dimension model and score (`business-logic`, medium, 5 tasks)

Files you may touch: `src/chanchi/taxonomy.py`, `src/chanchi/scoring.py`, `tests/test_taxonomy.py`,
`tests/test_scoring.py`.

- **3.1** `taxonomy.py`: add `DIMENSIONS` (ordered dict `name -> tuple of codes`, per decision 1),
  a derived `DIMENSION_OF` (`code -> dimension`), and the `"dimensions"` key in `describe()`.
- **3.2** `scoring.py`: add `dimension_score(dimension, incidents)` (pure, per decision 2); make
  `executor_records` also store each record's executor incidents under `"executor_incidents"`;
  add `"dimension": ("agent", "model", "effort", "dimension")` to `EXECUTOR_GROUPINGS` and make
  `_executor_stats` delegate to a new `_dimension_stats` when `by == "dimension"`, building rows and
  the top-level `note` per decisions 3 and 6 (`stats()` must return the `note` key only for this view).
- **3.3** `scoring.explain()`: add the `"dimension_score"` key (decision 7).
- **3.4** Tests in `tests/test_taxonomy.py`: every `EXECUTOR_WEIGHTS` code is in exactly one
  dimension; dimension codes are unique across dimensions and all exist in `INCIDENT_CODES` with a
  non-planner, non-human role; `describe()["dimensions"]` lists all five in order.
- **3.5** Tests in `tests/test_scoring.py`, using the `recorder` fixture. One model (`FLASH`), three
  `accepted` sessions with incidents `architecture_violation` medium, `code_smell` low, and
  `rule_violation` medium (all `planner_audit`), one per session. Expect: architecture mean 98.67,
  clean-code mean 99.67, discipline mean 99.0, correctness and honesty 100.0, each with `n == 3`;
  `incident_count == 1` for the first three; the `note` present. Also: a `false_claim` high detected
  `post_merge` gives honesty 86.5 for that session (use `dimension_score` directly); a session with
  only `correct_stop` scores 100 in all dimensions; a planner-role `hallucination` does not move
  `honesty`; `stats(role="planner", by="dimension")` raises `ChanchiError` with `field == "by"`.

Verify (paste the real output): `uv run pytest -q` (all passed, count not lower than 147 plus your new tests).

## Session S4 - CLI surface and docs (`docs`, medium, 5 tasks)

Files you may touch: `src/chanchi/cli.py`, `tests/test_cli.py`, `README.md`,
`skills/chanchi-model-selection/SKILL.md`, `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md`.

- **4.1** `cli.py`: the `--by` help of `stats` lists `dimension` and says it is executor-only. No
  other CLI change should be needed; if it is, STOP.
- **4.2** `tests/test_cli.py`: in the existing history test add `stats --by dimension` (rows
  non-empty, each row has `dimension`, the top-level `note` exists) and assert the taxonomy command
  output contains `"dimensions"`.
- **4.3** `README.md`: add `chanchi stats --by dimension` to "Everyday commands".
- **4.4** `chanchi-model-selection/SKILL.md`: add a bullet under "Catalog maintenance" for
  `chanchi stats --by dimension`, stating in the same bullet that 100 means no recorded fault.
- **4.5** Spec: in section 4.4 add a short "Dimensions" table after the incident codes table; in
  section 6.5 add a "Dimension view" paragraph (decisions 2, 3, 5); in section 7 add `dimension` to
  the `chanchi stats` synopsis line.

Verify (paste the real output): `uv run pytest -q` all passed; then, against a scratch database, run
`models add --agent agy --model m1 --cost 1 --efforts high`, `change open demo --kind adhoc --planner human`,
`session start demo S1 --executor agy:m1:high --task-type refactor --complexity low --tasks 1`,
`session report demo S1 --status COMPLETE`,
`incident add demo --session S1 --code architecture_violation --severity medium --detected-by planner_audit --desc x --evidence y`,
`session audit demo S1 --verdict accepted`, then `stats --by dimension`: the `architecture` row must
show `mean_score` 96.0 and `incident_count` 1, every other dimension 100.0.

## Report format (written to the path given in the prompt)

`Status` (COMPLETE, STOPPED or BLOCKED), `Files changed`, `Verification` (each command with its
output), `Choices the plan left open` (or "none"), `Stops and questions` (or "none").
