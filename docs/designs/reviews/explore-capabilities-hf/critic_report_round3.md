# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-829, top of file up to but not including "## Detailed Implementation Plan" at line 830)
**Stage:** 7 (Critic Review), round 3. Mode: REVIEW.
**Standard:** `resources/document_standards/feature-spec-standard.md` (egm-design, egm-structural). egm-style used its persona's audit vectors.
**Settled items not re-raised:** Phase 3 drop criterion, no `source` column on `model_capabilities`, the owner's budget override for the Hydrogen sessions, the known leak into `recommendation` (G2), line wrapping beyond 100 columns.

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `egm-design` | completed | 0 Blocker, 2 Major, 6 Nit |
| `egm-structural` | completed | 0 Blocker, 2 Major, 7 Nit |
| `egm-style` | completed | 0 Blocker, 3 Major, 4 Nit |

After deduplication: **0 Blocker, 4 Major, 8 Nit.** When two or more reviewers raised the same point, the finding keeps one id and lists the others under "Also raised by".

**Round-2 fixes.** All three reviewers checked every round-2 fix (7 Majors, 24 Nits) and found them all applied. Every internal cross-reference resolves, including the brief anchor. Three fixes left gaps or created new problems:
* design-2-5 (the subprocess guard) is the source of design-3-1.
* design-2-2 (the per-model red flag) is the source of design-3-2.
* design-2-1 (per-effort counting) left the scope gap in structural-3-1 and the wording drift in style-3-1.

**Verified by the synthesizer against source:**
* `db.status()` reports `pending: null` for a file that does not exist (`db.py` 266-276). `bootstrap()` creates a database from the template when the file is missing (`db.py` 216-224). Both underlie design-3-1.
* `chanchi db migrate` exists (`cli.py`:243), so option (b) in design-3-1 needs no new command.
* When no level reaches 3 sessions, `recommend()` falls back to the first level with any session (`scoring.py` 446-451). This underlies design-3-2.

## Prioritized Findings (Blockers -> Major -> Nits)

### design-3-1: The pending-migration guard blocks the first fetch, so the drop criterion cannot be evaluated before the merge. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-structural` (Major 1) and `egm-style` (M3, N2). Merges design N4 (second half) and N6.
* **Affected Scope:** Lines 45, 170-172, 429-436, 473-478, 499, 507-509, 614-615, 779.
* **Discrepancy Description:**
  * The fetch script stops if `db status` reports any pending migration on the `CHANCHI_DB` database (475-476). Fetch runs use a copy of the real database (45, CUJ 3).
  * Until Phase 2 is merged and the real database has been migrated, that copy is at version 2. A worktree whose code includes Phase 2 has latest migration 3, so `pending` is 1 and the script always stops.
  * The text implies that one branch carries all three phases ("Phase 3 is removed before the branch merges ... Phases 1-2 ship alone", 435-436; task ids written "before the branch merges", 508-509). Under that reading, the first `--write`, the drop-criterion count and the `task_id` capture can never run.
  * Line 499 ("once Phase 2 is merged") hints at an earlier separate merge of Phase 2 but never makes it a precondition. Lines 614-615 say pre-merge Phase 2 code runs only against a scratch `CHANCHI_DB`, which contradicts fetch runs against a copy (45).
  * The guard has a hole. If `CHANCHI_DB` names a file that does not exist, `db status` reports `pending: null` and the check passes. `models list` then bootstraps an empty catalog from the template, and the script tells the owner to `models add` all 17 entries against the real database.
  * Once `CHANCHI_DB` points at a copy, the pending check protects nothing: migrating a copy is harmless. The hazard that remains is `CHANCHI_DB` set to the real file's path.
* **Rationale & Recommendation:** Choose one option and state it once, in "Fetch script", "Drop criterion", CUJ 3 and Rollout:
  * (a) Phases 1-2 merge, and the real database migrates, before Phase 3's first fetch. Reword 433-436 so that only the Phase 3 branch is dropped.
  * (b) Keep one branch. The owner runs `CHANCHI_DB=<copy> uv run chanchi db migrate` before the fetch. Replace the pending check with these guards: stop if `CHANCHI_DB` is unset, if it resolves to the default operational path, or if `db status` shows `operational.exists: false`.

  Under either option:
  * add the `exists: false` stop;
  * change 615 to "a scratch file or a copy";
  * update Risks row 779.

### design-3-2: One honesty incident in one session removes a low-data model from exploration on every task type, with no automatic way back. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 63-66, 222-225, 272-274.
* **Discrepancy Description:**
  * Rule 1 now drops a model when any of its listed specs is red-flagged (round-2 fix design-2-2).
  * When no level of a spec reaches 3 sessions, `red_flag` is computed at the first level with any session, often `complexity` or `global` (`scoring.py` 446-451). One audited session with one `false_claim` or `hallucination` gives an honesty rate of 1.0. That is above 0.2, so the spec is red-flagged for every task type.
  * The model then never appears in `explore`. With fewer than 3 sessions, it is never eligible for `recommendation` either. Only hand picks can add sessions, so line 66's "it clears when enough clean sessions bring the average down" does not happen in practice.
  * This recreates the stuck loop the design exists to break, triggered by a single incident.
* **Rationale & Recommendation:** Decide and document one of these:
  * (a) It is intended: an honesty incident during exploration disqualifies the model until the owner picks it by hand. Add a Risks row and a skill note.
  * (b) In rule 1, apply the red flag only when the flagged spec's level has `n >= CONFIDENCE_LOW_MIN`. Below that, treat the flag like `weak_start` (sort last) instead of excluding the model.

  Either way, add a test with 1 session and 1 honesty incident.

### structural-3-1: Rule 1 does not say which efforts count, and one reading drops a model from both lists. Severity: Major
* **Reviewer Lens:** `egm-structural` (Major 2). Also raised by `egm-style` (M2) and `egm-design` (N1).
* **Affected Scope:** Lines 216-225, 250-253, 273-274.
* **Discrepancy Description:**
  * `n_task_type` is defined only for specs in `--available` (216-217). The red-flag clause is limited to "its specs in `--available`". "No effort of it has 3 or more" has no stated scope.
  * Example: `GLM:low` has 3 `bugfix` audits and the planner lists only `GLM:high`.
    * Database scope: GLM is not explorable. `GLM:high` has 0 sessions, so it is not eligible for `recommendation` either, and the model silently drops out of both lists.
    * `--available` scope: GLM is explored at `:high`, and its sessions split across efforts again.
  * Rule 4 keeps "the effort with the highest `n_task_type`" only among listed specs, so sessions recorded at an unlisted effort do not count. Line 274 has the same ambiguity.
* **Rationale & Recommendation:**
  * Name the scope in rule 1 and on line 274. For example: "no spec of it in `--available` has `n_task_type` >= 3".
  * If database scope is chosen, state that a model can fall out of both lists. Add a skill hint: list the effort that already holds the audits.
  * Add this case to the split-effort test.

### style-3-1: The exploration threshold is stated three different ways. Severity: Major
* **Reviewer Lens:** `egm-style` (M1). Also raised by `egm-structural` (Nit 1).
* **Affected Scope:** Lines 19-20 (Overview), 93-97 (G1), 222-226 (rule 1).
* **Discrepancy Description:**
  * The Overview says candidates "with fewer than 3 audited sessions". That is a total count with no task type, which is the definition Alternative Q rejects.
  * G1 says "fewer than 3 audited sessions of the requested task type", which reads as a per-model sum across efforts.
  * Rule 1 counts per effort. A model with 2 sessions at `:low` and 2 at `:high` is explorable under rule 1 but not under G1.
  * Acceptance tests are written from G1, so they would test the wrong rule.
* **Rationale & Recommendation:** Use rule 1's wording, with the scope chosen in structural-3-1, in both places:
  * Overview: "candidates where no effort has 3 audited sessions of the requested task type".
  * G1: "models none of whose (listed) efforts has 3 or more audited sessions of the requested task type".

### Nits

| Id | Lines | Problem | Fix |
| --- | --- | --- | --- |
| design-3-3 | 239-240, 254-257 | The reserved no-signal slot goes to "the first spec without a signal", whatever its cost tier and even if it is `weak_start: true`. A tier-3 closed model, or one that failed its first trial, can then displace a tier-1 model, against "cost comes before the external signal" and the purpose of weak start. | Restrict the slot to specs without `weak_start`, and optionally to the third-ranked spec's cost tier. Otherwise, state that the slot ignores cost. |
| design-3-4 (also style N3, structural Nit 2) | 543-548 | `now` is passed into `recommend()` and `hfsignals`, but not into `explain()`, which also reports `explore_signal_stale` and takes no arguments today (`scoring.py`:525). Existing tests call `recommend()` without `now`, and G2 requires them to pass unedited. | Make `now` an optional keyword argument of `recommend()` and `explain()`. Define the default, for example `None`, which gives `explore_signal_stale: null`. The CLI passes it to both. |
| design-3-5 | 45, 170-172, 431 | The real database uses WAL (`db.py`:225). A plain file copy can miss recent `models add` and `models set` writes still in `-wal`, and those are the writes the copy must include. | Say the copy is made with `sqlite3 <db> ".backup <copy>"`. |
| style-3-2 (also structural Nit 3) | 365-367 | `hint_commands` is "two complete commands" with `vision` hard-coded. With two `unknown` capabilities (Future Improvements, 814), the output is undefined. | Use "for each missing capability whose value is `unknown`, a `=yes` and a `=no` command". |
| style-3-3 (also structural Nit 4, design N5) | 503-505 | An edit artifact. The `HF_BENCHMARKS` sentence says twice that each entry has allowed `task_id` values and a unit and range. | Keep one: "Benchmark → signal mapping in the constant `HF_BENCHMARKS`: per dataset id, its signal, allowed `task_id` values and unit (`percent`, range 0-100)." |
| structural-3-2 (also design N5) | 794 | The NFR still says "never `source_name`, `source_url` or notes". `notes` is not a snapshot field, and 576 was already changed to "any other Hub field". | Use "`source_name`, `source_url` or any other Hub field". |
| structural-3-3 | 113-114 | G5 says "each candidate shows `external_signals`". Line 564 says it appears only in `explore` entries, never in `candidates`. | Use "each `explore` entry shows `external_signals`". |
| structural-3-4 | 609-612 | A broken paragraph. Line 611 ends at "from then on the" and 612 continues it. This is the same defect as structural-2-1, not the settled 100-column question. | Rejoin 609-612 into one normally wrapped paragraph. |
