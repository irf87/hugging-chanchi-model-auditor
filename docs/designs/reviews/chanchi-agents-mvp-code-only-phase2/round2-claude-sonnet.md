VERDICT: PASS

Scope: `git diff 6fdc5ef..4aed32b` for the design (Rev 4) and the plan (Rev 6), read against `scripts/run_evals.py` on main (hash functions, the `counter` at lines ~1349-1388, `load_eval` at ~194). Docs-only commit, so no tests were run.

## Round 1 re-check

| id | status | evidence |
|---|---|---|
| F1 (`signal` placement) | RESOLVED | D1 says `signal` is a top-level boolean "placed before `[candidate]`, next to `blind_allow`, never nested under `[candidate]`". S10a and S10b repeat this. S9 adds `assert "signal" not in cand` plus a test for nested `candidate.signal`. |
| F2 (empty `scoped` is vacuously true) | RESOLVED | D15 and S9 define `met = bool(scoped) and lessons["met"] and all(...)` with `"reason": "no signal evals"`. S9 updates `test_signal_reports_none_judge_and_unmet_conditions`. G5 requires `in_signal: true` for exactly the three skills and `false` for item-adoption. |
| F3 (missing runner tests) | RESOLVED | S9 (b) covers judged + `signal = true` with an uncalibrated sheet, which must fail. S9 (e) covers `load_eval` raising `RunnerError` on a non-bool `signal`. |
| F4 (stale rubric/judge text) | RESOLVED | S4/S5 rubric bullets (plan lines 259, 278, 315) are marked "superseded by S10a/S10b / Rev 6". The Risks rows are tagged "Optional judged evals only". D8, D2, D14, the Verification plan and the design's Layout section are reconciled. Status stays `draft` until the round closes, as the brief states. |
| F5 (ledger preservation) | RESOLVED | D18 states that `triggers_sha` and item-adoption's `cases_sha` do not depend on judge, rubric or signal. This matches the code: `cases_sha` hashes `rubric_sha256` and `judge`, which item-adoption lacks. D18 and G2 require renumbering the preserved triggers row to `<item>-1`, `--dry-run` cache-hit checks, and max-suffix ids. The S9 counter fix is real: the current code uses `sum(1 for ...)`. S9 test (f) covers it. |
| F6 (G4 grader/setup check) | RESOLVED | G4 now begins with inspecting `new-skill` and `new-hook` `grade.py` and `setup.sh`. The run range is updated and the 300 stop rule is kept. |
| F7 (budget assumes unchanged descriptions) | RESOLVED | The Budget and Risks rows state "assumes `SKILL.md` description unchanged; +4 trigger runs otherwise, visible in `--dry-run`". |

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | minor | Plan S8a/S8b (lines 390-420) | These Rev 5 tasks are already done (73903c1 and 9d9309a), but they still say to set `[judge]` and to "confirm each case exercises its `rubric.md` criteria". Unlike S4/S5 they carry no "superseded" note. | Plan lines 400-402 and 417-420. | Add a one-line "done; judge parts superseded by S10a/S10b" note. Cosmetic. |
| N2 | minor | Plan S9 test (f) vs D18 | The (f) example, a preserved `<item>-3` followed by new `-4` and `-5`, differs from D18's renumbering to `<item>-1` (new rows would be `-2` and `-3`). | Both are valid for the max-suffix counter, so the test is a generic gap case. | Optional: mention both cases in (f). |

No blocking or major finding remains. The design and plan agree on `signal` semantics, the fail-closed guard, the default `bool(judge)`, and the budget arithmetic (227 + 15..26 = 242..253).
