# Audit 17, Round 1 — Consolidation (Design Rev 4 & Plan Rev 6: Code-Only Phase-2 Evals)

- **Audit ID:** 17
- **Round:** 1 (subject at `6fdc5ef`, `degraded: false`)
- **Outcome:** `fix`

## Seats & Votes

| Seat | Spec | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---:|---:|---:|---|
| 1 | `claude:sonnet:medium` | `anthropic` | `pass_with_fixes` | 0 | 2 | 5 | [round1-claude-sonnet.md](round1-claude-sonnet.md) |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass_with_fixes` | 0 | 2 | 3 | [round1-agy-gemini-4-neon.md](round1-agy-gemini-4-neon.md) |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `fail` | 0 | 2 | 1 | [round1-opencode-hy4-flash-free.md](round1-opencode-hy4-flash-free.md) |

## Consolidated Shared Findings

1. **Empty `scoped` passes `--signal` vacuously (`S1-F2`, `S2-F1`, `S3-F1` — major):**
   - `cmd_signal` computes `met = lessons["met"] and all(... for e in scoped)`, which evaluates to `True` when `scoped` is empty. Under Rev 6, removing `rubric.md`/`[judge]` makes `cfg.signal` default to `False`, so omitting or misplacing `signal = true` drops all three skills out of `scoped` and reports a false `met: true`.
   - **Resolution:** Require `bool(scoped)` in `cmd_signal` (reporting `met: false` and an explicit reason `"no signal evals"` when `scoped` is empty), update `tests/test_run_evals.py::test_signal_reports_none_judge_and_unmet_conditions` to assert `report["met"] is False`, add tests for empty `scoped` and out-of-scope failing + in-scope passing, and verify in G5 that `in_signal: true` holds for the exact three signal skills and `false` for `skill-chanchi-item-adoption`.

2. **Ledger row ID collision when preserving `<item>-3` `triggers` rows (`S2-F2`, `S3-F2` major; `S1-F5` minor):**
   - `scripts/run_evals.py` computes `counter = sum(1 for r in rows if r["item"] == cfg.item)` rather than `max(suffix) + 1`. Keeping only `<item>-3` (`triggers`) gives `counter = 1`, so G2 writes `<item>-2` (`with`) and `<item>-3` (`without`), colliding with `<item>-3`.
   - **Resolution:** In Task S9 (`scripts/run_evals.py`), derive `counter` from the maximum existing numeric suffix for `cfg.item` (+ unit test for unique IDs after gaps). In D18/G2, renumber preserved uncommitted `triggers` rows from `<item>-3` to `<item>-1` so committed rows are cleanly ordered `1 (triggers), 2 (with), 3 (without)`, state explicitly that `triggers_sha` and `item-adoption`'s `cases_sha` do not depend on `judge`/`rubric`/`signal`, and require `--dry-run` to confirm cache hits before the real G2 run.

3. **Leftover judge-centric / mandatory-calibration wording (`S1-F4`, `S2-F3`, `S3-F3` — minor):**
   - Stale wording remained in Design Rev 4 (`### Layout` lines 271, 279, 283, 288; `Eval cost` line 643) and Plan Rev 6 (`D8`, `S4`/`S5` rubric bullets, Sessions note line 121, Verification plan items 2–3, and Risks rows on calibration/judge agreement).
   - **Resolution:** Reconcile all leftover text to reflect optional `rubric.md`/`[judge]` and code-graded phase-2 defaults.

## Lone-Finding Dissent Decisions

| Seat | Finding | Severity | Decision | Evidence & Resolution |
|---|---|---|---|---|
| 1 | `F1`: `signal` key placement in `eval.toml` unspecified (appending after `[candidate]` creates `candidate.signal`) | major | `confirmed` | Verified in `eval.toml` on both worktrees: `[candidate]` is the final table once `[judge]` is removed. Specify top-level placement before `[candidate]` (next to `blind_allow`) in D1/S10a/S10b and assert `"signal" not in cand` in `tests/test_evals.py` (`check_eval_layout`). |
| 1 | `F3`: S9 tests omit judged + `signal = true` uncalibrated failure and `load_eval` non-bool `signal` `RunnerError` | minor | `confirmed` | Both tests were absent from S9's test list; added to Task S9. |
| 1 | `F6`: G4 should inspect `new-skill` `grade.py` and `setup.sh` before spending hill-climb runs | minor | `confirmed` | Added pre-edit grader/setup inspection as step 1 of G4. |
| 1 | `F7`: Budget estimate assumes `SKILL.md` `description` stays unchanged (+4 runs/skill if edited) | minor | `confirmed` | Added note in Budget + `--dry-run` verification. |
| 2 | `F4`: G4 run estimate (`2–6` / `4–6`), S4 skill hill-climb branch scope, Design Cost controls adaptive judge count (`3–4`) | minor | `confirmed` | Verified `scripts/run_evals.py:1219-1226`: prior `< 100%` regression + changed capability each add `+2` runs; S4 skills must hill-climb before G2 merges `feat/mvp2-s4`; optional judge adds up to 3–4 runs with adaptive repeat. |
| 2 | `F5`: `git stash` shares `refs/stash` across worktrees | minor | `confirmed` | Replaced shared-stash wording in D18/S10a/S10b with per-worktree temp file save/restore (or strictly sequential stash/rebase/pop one worktree at a time). |

## Next Step
Apply all confirmed fixes, commit on `docs/code-only-phase2-evals`, and open Audit 17 Round 2 so all three seats re-check their findings.
