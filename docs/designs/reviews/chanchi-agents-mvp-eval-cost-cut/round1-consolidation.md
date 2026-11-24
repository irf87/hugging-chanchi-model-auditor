# Audit 16 — Round 1 Consolidation (Cheaper Eval Protocol Amendment)

- **Audit ID:** 16
- **Subject:** `docs/designs/chanchi-agents-mvp.md` (Revision 3) and `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` (Revision 5) at commit `d73b44a` (branch `docs/eval-cost-cut`, change `chanchi-agents-phase2`)
- **Date:** 2026-11-23
- **Degraded:** `false` (3 distinct model families: `anthropic`, `google`, `tencent`; `cursor:grok-4.7-high-fast` marked unavailable due to exhausted Cursor credits and refilled with `opencode:opencode-go/hy4-flash-free`)
- **Outcome:** `fix`

## Seats and Votes

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|---|
| 1 | `claude:sonnet:medium` | `anthropic` | `pass_with_fixes` | 0 | 5 | 5 | `round1-claude-sonnet.md` |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass_with_fixes` | 0 | 3 | 3 | `round1-agy-gemini-4-neon.md` |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `pass` | 0 | 0 | 1 | `round1-opencode-hy4-flash-free.md` |

## Shared Findings (2+ seats)

1. **`--rejudge` and judge escalation vs `cases_sha` + baseline recomputation** (`S1-F1` major, `S2-F2` major, `S3-F1` minor): Rewording `rubric.md` or escalating `[judge]` changes `cases_sha`, but D14/G3 did not instruct `--rejudge` to refresh `cases_sha=`/`cases=` in uncommitted baseline rows, and D14's phrasing "from code-passed baseline runs only" would omit code-failed baseline capability runs from baseline arm medians. **Fix:** Specify exact `--rejudge` recomputation across all latest baseline runs (re-judged scores for code-passed runs, recomputed gated scores without judge for code-failed baseline runs, never mixing `calibration-runs/`), refreshing `cases_sha=` and `cases=` in both uncommitted `with` and `without` rows, and specify the exact G3 judge-escalation flow (`--rejudge` + `--calibrate`, or re-collect if needed).
2. **S8 rebase/worktree contradiction and S4/S5 ledger git state** (`S1-F3` major, `S2-F3` major): Plan Sessions table assigned rebasing and editing two worktrees to a single executor session S8, violating `agent-chanchi-executor` rules; `feat/mvp2-s4` has uncommitted `M evals/ledger.tsv` and `feat/mvp2-s5` has committed Rev-4 rows (`5f5cd5a`); G3 rebased `feat/mvp2-s5` before committing its ledger. **Fix:** Orchestrator discards dirty ledger on `feat/mvp2-s4` and rebases both branches onto `main` after S7; split S8 into single-worktree sessions `S8a` (`feat/mvp2-s4`) and `S8b` (`feat/mvp2-s5`, resetting committed Rev-4 ledger rows); in G3, commit `evals/ledger.tsv` and `calibration.tsv` on `feat/mvp2-s5` before rebasing onto `main`.
3. **Unstated S7 CLI/ledger edge cases** (`S1-F7` minor, `S2-F5` minor): Clarify `--runs 2` top-up to 3, `cases=` contents per arm, `triggers` row fields under `--hypothesis`, explicit `--arm with`/`without` trigger skipping and `--triggers`/`--no-triggers` mutual exclusion, `max_total > 30` refusal, judge parse-failure score monotonicity, and ignoring `__pycache__`/`.pyc`/`.DS_Store` in `cases_sha`.

## Lone-Finding Dissent Decisions

| Seat | Finding | Severity | Decision | Evidence |
|---|---|---|---|---|
| 1 | `F2`: `with` rows carry no `cases_sha`, risking cross-harness comparisons | major | **confirmed** | Plan D9 omitted `cases_sha` from `with` notes and `current_with_row`/`previous_with_row` did not filter on `(candidate, cases_sha)`. Fix: include `cases_sha` in `with` rows and match `(candidate, cases_sha)`. |
| 1 | `F4`: `lessons` rubric criteria 1–3 would be N/A on `review-check-first` and `record-failure` criterion 4 unjudged | major | **rejected** | Verified locally in `.claude/worktrees/chanchi-p2s4/evals/eval-chanchi-lessons/cases/review-check-first/grade.py` (`replacement_exists` requires recording a replacement lesson via `chanchi lesson add`) and saved baseline artifacts: criteria 1–4 all applied on 3/3 `with/review-check-first` runs (including `3:FAIL` on run #2) and criterion 4 failed on 3/3 `without` runs; on `record-failure`, criterion 4 was `N/A` in 2/3 runs. |
| 1 | `F5`: 6-sample calibration lacks label-contrast requirement | major | **confirmed** | Plan D14 checked only `total >= 6 and agree >= total - 1`, allowing an all-PASS rubber-stamp judge to pass. Fix: require at least 1 owner `PASS` and 1 owner `FAIL` (preferring ≥ 2 each) and note small-sample variance in Risks. |
| 1 | `F6`: `cases_sha` omits candidate agent source `agents/<agent>/AGENT.md` | minor | **confirmed** | D3 injects the candidate agent body into both arms; include sha256 of `agents/<agent>/AGENT.md` in `cases_sha`. |
| 1 | `F8`: single-run baseline variance omitted from Risks | minor | **confirmed** | Add Risks row in design and plan; mitigate by re-measuring near-ties with `--runs 3 --arm both` in G4. |
| 1 | `F9`: 300s agy wall time unbenchmarked and `agy --print-timeout` unmentioned | minor | **confirmed** | `chanchi models list` confirms `cost_tier=1` for `agy:gemini-4-hydrogen-high`; have G1b record wall-clock times (widen timeout if > 200s) and note why Python subprocess timeout is kept over `--print-timeout` for harness parity. |
| 1 | `F10`: stale pre-Rev-5 `lessons` calibration sheet not mentioned in G3 | minor | **confirmed** | Add explicit G3 instruction to discard pre-Rev-5 calibration sheets and maps before collecting Rev-5 sheets. |
| 2 | `F1`: flaky regression (`2/3`) has per-case median `1.00`, letting a single hill-climb pass bypass adaptive repeat | major | **confirmed** | `[0.75, 1.00, 1.00]` has median `1.00`, bypassing D5 and satisfying `1/1 > 2/3` in D17 without 3-run confirmation. Fix: store per-case pass rate for regression cases in `cases=` and trigger 3-run confirmation whenever prior regression pass rate `< 100%`. |
| 2 | `F4`: `scripts/run_evals.py:1380` never forwards `args.timeout` to `Context` | minor | **confirmed** | Verified at `scripts/run_evals.py:578,1362,1380`: `main()` omits `timeout=args.timeout`. Fix: add wiring `Context.timeout = 300` and `timeout=args.timeout` plus unit test to Task S7. |
| 2 | `F6`: Design Rev 3 calibration judging wording vs Plan D14 and G3 `--collect` run estimate | minor | **confirmed** | Align Design Rev 3 line 369 to "code-failed calibration runs" and update G3 `--collect` estimate to ~8–10 runs each (~24–30 runs total). |

## Next Steps

Apply all confirmed shared and lone fixes to `docs/designs/chanchi-agents-mvp.md` and `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md`, verify with `scripts/check`, commit on `docs/eval-cost-cut`, and open Round 2 for the same three seats to re-check their findings.
