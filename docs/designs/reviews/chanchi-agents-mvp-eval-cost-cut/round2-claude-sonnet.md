VERDICT: PASS

# Audit 16, round 2, seat 1 (commit 67e3ec3)

Scope: the diffs of Design Rev 3 and Plan Rev 5 against d73b44a and main. I also read the current plan and design text, the S4 worktree grader and the repository test file names. The change is docs only, so `scripts/run_evals.py` and `tests/test_evals.py` are unchanged. The plan's S7 task is what updates the runner. I edited no repository file. Open findings: 0 blocking, 0 major, 3 minor.

## Re-check of my Round 1 findings

| id | status | evidence |
|---|---|---|
| F1 `--rejudge` / escalation vs `cases_sha` | RESOLVED | D14 (a)–(c) now refreshes `cases_sha` and `cases=` in both uncommitted baseline rows and refuses if they are already committed. The G3 escalation flow and the Risks row both say to run `--rejudge` and then `--calibrate`. The S7 test list covers it. |
| F2 `with` rows lack `cases_sha` | RESOLVED | D9 writes `cases_sha=` in `with` notes. Both the current and previous `with` rows match on `(item, [item_sha,] candidate, cases_sha)`. Design step 7 says the same. D15 condition 3 matches on `cases_sha`. |
| F3 S8 rebase contradiction | RESOLVED | S8 is split into S8a and S8b, each on a single worktree. The orchestrator discards the dirty ledger, rebases and commits. Executors "never commit or rebase". D18, G1b and G3 agree. G3 commits the s5 ledger before rebasing. |
| F4 lessons rubric fit | RESOLVED (rejected in consolidation; I verified it) | In the S4 worktree, `review-check-first/grade.py` checks `replacement_exists` among its criteria. The kept capability case therefore records a replacement lesson, which exercises rubric criteria 1–3. I had wrongly described it as a review-only case. S8a also adds "confirm each kept capability case exercises its `rubric.md` criteria before freezing". |
| F5 calibration without label contrast | RESOLVED | D14, D15, the design's *Judge calibration* section and the Risks table now require ≥1 owner PASS and ≥1 FAIL, else "uncalibrated: no contrast". The S7 tests include the 6/6 all-PASS failure. |
| F6 `cases_sha` omits agent source | RESOLVED | D9 and design step 2 include sha256 of `agents/<agent>/AGENT.md`. The S7 tests cover an `AGENT.md` edit. |
| F7 S7 ambiguities | RESOLVED | (a) D5 says top-up to 3 for `--runs 1` and `--runs 2`. (b) D9 defines `cases=` per arm. (c) D9 and D17 define the `triggers` row during `--hypothesis`. (d) D7 gives the parse-failure score. (e) D17 allows `--hypothesis` with `--arm auto` or `--arm with`. Explicit `--arm` skips triggers, and `--triggers` and `--no-triggers` are mutually exclusive. |
| F8 single-run noise unnamed | RESOLVED | New Risks row. It also adds adaptive repeat on `< 100%` regression pass rate and G4 near-tie re-measurement with `--runs 3 --arm both`. |
| F9 agy timing and `--print-timeout` | RESOLVED | G1b records wall-clock time and widens `--timeout` above 200s. `--print-timeout` is mentioned, with the reason a uniform subprocess timeout is kept. |
| F10 stale calibration sheet | RESOLVED | G3 begins by discarding pre-Rev-5 sheets and maps, including the Rev-4 lessons sheet. |

## New findings (open)

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | minor | Plan D7 and design step 5 | The judged-run score is written as `passed_applicable / total_applicable`. The code-failed and parse-failure formulas use `len(code) + len(rubric_criteria)`. It is unclear whether the judged score counts the code criteria. If it counts only rubric criteria, a code-passed run with every rubric criterion FAIL scores 0 and falls below a code-failed run, which breaks the stated strict monotonicity. The parse-failure score `C/(C+R)` implies code criteria are included. | D7 text: "`score = passed_applicable / total_applicable` … `C / (C + R)`". | Write the judged score explicitly as `(passed_code + passed_rubric_applicable) / (len(code) + total_rubric_applicable)`. Add one monotonicity test with an all-FAIL judge. |
| N2 | minor | Plan D9 `cases_sha` vs `with` `cases=` | `cases_sha` excludes regression cases. The `with` row's `cases=` includes regression pass rates, and D5 and D17 compare against them. An edit to a regression case's `grade.py`, `prompt.md` or `setup.sh` leaves the hash unchanged, so the previous pass rate is compared with one measured on a different case. The rubrics and capability cases are frozen, but regression cases are not named as frozen. | D9: hash "excluding regression cases". | Either include regression case files in a separate `reg_sha` used for the `with` match, or state that regression cases are frozen with the harness and that an edit forces a new baseline. |
| N3 | minor | Plan D5 / D14 vs design | Two small gaps. D5 does not say whether the 300s `--timeout` applies to judge runs. The calibration collect order is "alternating `without` and `with`" in the plan but "`with` and `without`" in the design. | D5, D14 and the design's *Judge calibration* section. | Say the timeout applies to every harness call, judge included. Use one order in both documents. |

## Cross-document checks (no new contradiction found)

- The design and plan agree on the thresholds, the note tokens and the default 300s timeout.
- The plan and design agree on the run budget. A first baseline is 7–9 runs, and G2 is ~31 runs (up to ~36). G3 is ~24–30 runs and G4 is ~10–15 runs. The Risks row gives ~160 spent plus ~74–105 remaining, which is ~234–265 of the 300 cap. This is consistent.
- D23 keeps and drops the same cases that S8a and S8b name. S8b resets the committed Rev-4 `item-adoption` ledger rows. The merge order in D18 and G3 is coherent. Merging s4 first and then rebasing s5 with the ledger conflict noted is workable.
- `tests/test_run_evals.py` and `tests/test_evals.py` both exist. The S7 test list covers each new rule.
- AGENTS.md needs no change, and the diff touches no home path or reference-project name.
