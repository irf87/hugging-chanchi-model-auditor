# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-899, full file)
**Stage:** 5, Initial Zoom Out Review. Mode: REVIEW.

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-zoom-out` | completed |
| `egm-inventive-catalyst` | completed |

Severity breakdown after deduplication: 0 Blocker, 7 Major, 9 Nit.

Duplicates merged: the execution-plan budget violation (found by both reviewers) and the
per-effort counting of `n_task_type` (found by both reviewers).

The synthesizer checked one claim against the code. In `src/chanchi/scoring.py:441-445`, the
first loop takes the first level with at least `CONFIDENCE_LOW_MIN` records. Candidates are keyed
by `(agent, model, effort)` (line 435). Finding M5 and finding N2 both rely on this.

Neither reviewer found a Blocker. The core split holds: unaudited models go into a separate
`explore` list, and Hugging Face (HF) data only orders that list. Phase 1 alone fixes the
eligibility trap at `scoring.py:470`.

## Prioritized Findings (Blockers -> Major -> Nits)

### M1. Phase 3 costs much more than it delivers - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Overview item 3; Goals G5 and G7; Technical Plan "Phase 3: Hugging Face snapshot" (lines 255-360); Alternative M (lines 489-496); files 18-31.
* **Discrepancy Description:** Phase 3 adds the following:
  * a hand-written map;
  * a fetch script with a guard, token handling and merge logic;
  * a versioned snapshot schema;
  * the `hfsignals` module, which computes canonical values, applies a peer threshold and computes tie-aware percentiles;
  * new taxonomy tables;
  * a no-network test;
  * an owner step that registers 15 models;
  * a rewrite of the "No server, no network" principle in spec section 1.3.

  All of this only reorders an `explore` list of at most 3 entries. It applies to only 6 task types and to at most 1 in 4 sessions. The design itself calls the data unverified and says it comes from a different checkpoint than the one opencode serves. Phase 1 alone meets G1. The doc says Phase 3 is dropped "if the snapshot proves too sparse", but it gives no measurable criterion for that.
* **Rationale & Recommendation:** Ship Phases 1 and 2 first. Defer Phase 3 until a measurable trigger fires. For example: after N planner sessions, cost-tier ordering regularly pushes a model the owner would have preferred out of the top 3. If some ordering input is wanted now, use an owner-set rank per model in the hand-written map. That needs no fetch and no percentiles. If Phase 3 stays, write the "too sparse" drop criterion into the Verification Plan as a number.

### M2. The `source` column on capabilities exists only to serve Phase 3 - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Phase 2 "Storage" (lines 205-227); `CAPABILITY_SOURCES`; the `--capability-source` flag (lines 231-233); Alternative J's rejection reason (lines 470-471); the fetch script's "Capability suggestions" bullet (lines 313-315); file 19, which reads the catalog through a `chanchi models list --all` subprocess.
* **Discrepancy Description:** `source = 'hf'` only records that the owner pasted a command the script printed. A person runs every write either way, so the field carries no real provenance. Even so, it drives four costs:
  * a column in migration 003, which the doc calls the only irreversible step;
  * a CLI flag;
  * a taxonomy enum;
  * the fetch script's dependency on the installed CLI and the global database.

  It is also the main argument for rejecting Alternative J.
* **Rationale & Recommendation:** Unneeded fields cost the most in a forward-only schema. Drop `source`, `CAPABILITY_SOURCES` and `--capability-source`, and keep `(model_id, capability, value, set_at)`. Have the dry-run summary print `pipeline_tag` per model and leave the decision to the owner. The script then no longer needs to read the catalog. A map entry with no catalog match produces a warning instead of a stop. Rewrite Alternative J's rejection to match.

### M3. The execution plan breaks the design's own exploration budget and runs the irreversible migration on an unaudited model - Severity: Major
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Detailed Implementation Plan, "Execution sessions (agy)" table and the paragraph after it (lines 582-602).
* **Discrepancy Description:** The plan breaks the budget it introduces:
  * All three sessions use `gemini-4-hydrogen-high`. That model has 0 sessions on each task type (business-logic, db-schema-migration, integration), so all three sessions are exploration.
  * The budget allows at most 1 of 3 (1 in 4 rounded down, minimum 1). It also forbids exploration in any session that blocks others, and every session here blocks the next one (line 601-602).
  * S2 writes migration 003, the only irreversible step. Its task type is `db-schema-migration`, where the predecessor model holds an honesty red flag.
  * The S3 justification ("global confidence reaches `low`") does not help. Exploration counts per task type, and SKILL.md treats global-level data as weak evidence.
* **Rationale & Recommendation:** Pick one of two options:
  * Follow the budget. Use a proven model for S2 at least, and use Hydrogen in at most one non-blocking session.
  * Or label the plan an explicit owner override of the budget. Give the reason (no proven agy model is left after the red flag) and record `· explore: <spec>` on all three protocol lines.

  Either way, remove the "global confidence reaches low" rationale. Also consider moving the launch command and model narrative out of the design doc into planner protocol material.

### M4. "chanchi cannot detect" budget overruns is false; detection needs no migration - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 1 "Budget" (lines 196-201); Alternative N (lines 498-506); Future Improvements "Budget enforced by chanchi".
* **Discrepancy Description:** The `sessions` table already stores `change_id`, executor model and effort, `task_type`, `started_at` and `audited_at`. A session was exploratory if its spec had fewer than 3 audited sessions of its task type at `started_at`, and chanchi can compute that from data it already has. The free-text `tags` column could also carry an `explore` marker. Alternative N conflates detection, which is cheap, with prevention, which needs `--change`.
* **Rationale & Recommendation:** Add a derived `exploration_share` per change to `show change` or to the audit skill's change summary, and flag it above 1 in 4. Remove "chanchi cannot detect it". Rewrite Alternative N to say that only prevention is deferred. Known limit: a session picked through a global-level `recommendation` can count as exploratory under this definition. State that.

### M5. The low/medium exploration limit leaks into `recommendation` at high complexity through the level fallback - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Goal G3; Phase 1 rule 2; Alternative E (lines 425-431); `scoring.py:441-445` and `:476`.
* **Discrepancy Description:** Suppose an opencode model collects 3 audited low/medium `bugfix` sessions through exploration:
  1. At `high` complexity, its `task_type+complexity` subset is empty.
  2. `recommend()` falls through to the `task_type` level with n=3, so its confidence is `low` and it becomes eligible.
  3. The cheapest-in-window rule can then pick it at high complexity based only on low/medium evidence.

  This is exactly the risk Alternative E rejects. SKILL.md warns only about the `complexity` and `global` levels, not about `task_type`.
* **Rationale & Recommendation:** Keep G2 and state the leak in the Phase 1 text. Add a skill rule for `high` complexity: when the `recommendation` level is not `task_type+complexity` and it is a cheaper tier than a candidate that has `task_type+complexity` data, treat it as weak evidence. Add one test in `tests/test_scoring.py` that documents the fallback. The stronger fix is to require `level == task_type+complexity` for eligibility at `high`. That breaks G2, so it needs its own design.

### M6. `explore` ignores early audit failures - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 1 rule 3, sort order (lines 172-177).
* **Discrepancy Description:** Take a model whose first exploratory session scored 30. It stays at the top of `explore` until it reaches 3 task-type sessions, because sorting uses signal, then cost, then `n_task_type`. Up to two more budgeted sessions can go to a model that has already failed. Only `red_flag` removes a model from the list.
* **Rationale & Recommendation:** When `n_task_type >= 1` and the observed task-type mean is below a constant `EXPLORE_DEMOTE_BELOW`, sort the model last instead of removing it. For example, set the constant to the prior minus `RECOMMEND_WINDOW`. Expose `demoted: true` on the entry. Add a sentence explaining why partial evidence may order `explore` even though it may not drive `recommendation`. Trade-off: one bad session can bury a capable model.

### M7. "No signal last" keeps unmapped and closed models out of `explore` - Severity: Major
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 1 rule 3.1 (lines 173-174); Phase 3 signal derivation; Non-Goals on closed models; Goal G5.
* **Discrepancy Description:** Sorting by signal first puts every mapped model, however weak, ahead of every unmapped one, whatever its cost. Those models are mapped for the `swe`, `terminal` and `tool-use` task types. With 11-16 mapped models, `EXPLORE_MAX = 3` and a budget of 1 in 4 sessions, unmapped open models such as qwen3.8-max, kimi-k3.1-pro and deepseek-v4-pro, plus all closed models, could stay out of `explore` for those task types for many changes. A signal difference of 0.01 also outranks cost tier, which works against the stated goal of moving work to cheaper models.
* **Rationale & Recommendation:** Choose one of two fixes. Either sort by a signal bucket (high, mid, low, none), then `cost_tier`, then `n_task_type`, or reserve one of the 3 slots for the best candidate with no signal. Update the G5 wording and the ordering test in `tests/test_hfsignals.py`.

### N1. Phase 3 constants belong in `hfsignals.py`, not `taxonomy.py` - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Phase 3 "Three files, three owners" table (lines 257-263); file 22; Rollout and rollback (lines 384-385).
* **Discrepancy Description:** `HF_BENCHMARKS`, `TASK_SIGNALS` and `HF_MIN_REPORTERS` would sit in core `taxonomy.py`. If Phase 3 is dropped, these become dead constants, and "delete or empty the snapshot" does not remove them.
* **Rationale & Recommendation:** Keep these constants inside `hfsignals.py` so Phase 3 can be removed by deleting its files. Surface them only through `explain()`.

### N2. Exploration counting per effort versus per model is not stated - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`, `egm-inventive-catalyst`
* **Affected Scope:** Phase 1 rule 1 (lines 163-169); file 2 (`n_task_type` per spec); file 3, test bullet 2.
* **Discrepancy Description:** Candidates are keyed by `(agent, model, effort)` (`scoring.py:435`), so `n_task_type` would be counted per effort. As a result, GLM at `:high` with many `bugfix` audits is still explorable for `bugfix` at `:medium`. Capabilities, by contrast, are per `(agent, model)`. The doc only says "a model".
* **Rationale & Recommendation:** State which key counts. Prefer `(agent, model)` across efforts, to match the goal and the capability decision.

### N3. Fetch script guard is over-specified - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Phase 3 "Fetch script", Guard bullet (lines 299-302); CUJ 4.
* **Discrepancy Description:** The guard runs three checks (git top level, the script's parent's parent, and the `pyproject.toml` name), yet the doc says it is "not a security boundary".
* **Rationale & Recommendation:** Resolve the root from `Path(__file__).resolve().parents[1]` and check only that the current directory equals it.

### N4. Too much code-level detail in the Technical Plan - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** "Signal derivation" (percentile formula, the 81.85 example); "Fetch script" (timeout, User-Agent, sort and indent); files 2, 11 and 19 (helper signatures and the side map).
* **Discrepancy Description:** Helper-level detail is mixed with the interface decisions. This makes the doc longer and fixes choices in advance that the executor should make.
* **Rationale & Recommendation:** Keep only contracts in the Technical Plan: output keys, the ordering rule, the range filter, the minimum reporters and the no-network boundary. Move formulas, examples and signatures into the descriptions of files 25 and 26.

### N5. `n_total` in explore entries has no consumer - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** Phase 1 "Output" JSON (lines 184-190).
* **Discrepancy Description:** No rule and no sort key uses `n_total`.
* **Rationale & Recommendation:** Drop it, or state which planner decision it supports.

### N6. Traceability errors: brief path and Claw-Eval count - Severity: Nit
* **Reviewer Lens:** `egm-zoom-out`
* **Affected Scope:** "Additional Resources" (line 554); Phase 3 "Peers" bullet (lines 333-335).
* **Discrepancy Description:**
  * The doc cites `concepts_brief.md` (revision 3), but the brief is `docs/designs/explore-capabilities-hf.brief.md`.
  * The reviewer reports that the brief gives Claw-Eval 6 reporting models, while the design says 3. That count decides whether `tool-use` has a second benchmark.
* **Rationale & Recommendation:** Fix the path. Reconcile the Claw-Eval count against the observed data and cite the source.

### N7. `unknown` capability recreates the never-tried loop - Severity: Nit
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 2 "Recommend with --require" (lines 238-250); Owner step (lines 759-765); CUJ 2.
* **Discrepancy Description:** Excluding `unknown` is the right strictness, but it causes the same problem this design fixes. Models left `unknown` never get vision tasks, so the owner never learns whether they can do them. The owner step sets `vision` only for closed models. Open models get it only through `pipeline_tag` suggestions, and the doc itself calls that tag unreliable.
* **Rationale & Recommendation:** Have the owner step set `vision` to yes or no for every registered opencode model, using the provider's own model page. Add a `hint` with the `models set ... --capability vision=yes|no` command to `excluded` entries whose value is `unknown`.

### N8. A bad or missing snapshot fails silently in `recommend` - Severity: Nit
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 3 "A missing or unreadable snapshot file gives no signals and no error" (lines 340-342); Rollout and rollback.
* **Discrepancy Description:** A bad snapshot commit reaches every project and silently changes `explore` ordering. Only `scoring explain` shows the problem, and no test checks the committed file.
* **Rationale & Recommendation:** Add `explore_signal_source` (`snapshot`, `missing` or `schema_mismatch`) plus `generated_at` to the `recommend` result. Add a test that parses the committed snapshot when it exists and asserts `schema_version == 1`. The test should skip when the file is absent.

### N9. `match_quality` is displayed but unused; G3 says "and above" - Severity: Nit
* **Reviewer Lens:** `egm-inventive-catalyst`
* **Affected Scope:** Phase 3 peers and percentile (lines 333-339); Goal G3 (line 61); the `explore_reason` definition (lines 192-194).
* **Discrepancy Description:**
  * A `proxy` checkpoint ranks exactly like an `exact` one, both as a peer and as a ranked model.
  * Rows with different fetch dates are mixed into one peer set without any note.
  * `taxonomy.COMPLEXITIES` ends at `high`, so "high complexity and above" refers to nothing.
* **Rationale & Recommendation:**
  * Add a tie-break on `match_quality` after the signal, or document that it is display-only.
  * List each benchmark's `fetched_at` range in `explain()`.
  * In G3, say "at high complexity".
  * Define `complexity_not_explorable` as "complexity not in `EXPLORE_COMPLEXITIES`".
