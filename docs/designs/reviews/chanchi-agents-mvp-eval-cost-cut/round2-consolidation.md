# Audit 16 — Round 2 Consolidation (Cheaper Eval Protocol Amendment)

- **Audit ID:** 16
- **Subject:** `docs/designs/chanchi-agents-mvp.md` (Revision 3) and `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` (Revision 5) at commit `67e3ec3` (branch `docs/eval-cost-cut`, change `chanchi-agents-phase2`)
- **Date:** 2026-11-23
- **Degraded:** `false` (same 3 distinct model families: `anthropic`, `google`, `tencent`)
- **Outcome:** `accepted`

## Seats and Votes

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|---|
| 1 | `claude:sonnet:medium` | `anthropic` | `pass` | 0 | 0 | 3 | `round2-claude-sonnet.md` |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass` | 0 | 0 | 2 | `round2-agy-gemini-4-neon.md` |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `pass_with_fixes` | 0 | 0 | 1 | `round2-opencode-hy4-flash-free.md` |

## Round 1 Re-check

All Round 1 findings across all three seats (`S1-F1..F10`, `S2-F1..F6`, `S3-F1`) were verified as **RESOLVED** (including Seat 1's independent verification of the Round 1 rejection of `S1-F4` against `review-check-first/grade.py`).

## Open Minor Fixes Applied (without opening a new round)

### Shared minor finding (Seats 2 and 3)

- **`S2-N1` / `S3-N1` (minor):** G3 grouped `(or lacking contrast)` into the `--rejudge` + reuse-existing-labels path, which cannot change owner labels. Separated the two failure modes in Design Rev 3 (*Judge calibration*), Plan D14, and G3: reword + `--rejudge` + `--calibrate` for low `agree`; collect contrasting samples (or propose a harder capability case) + label a new sheet for `"uncalibrated: no contrast"`.

### Lone-finding dissents (all confirmed and applied)

| Seat | Finding | Severity | Decision | Evidence & Fix Applied |
|---|---|---|---|---|
| 1 | `N1`: D7 judged-run score formula should explicitly include code criteria | minor | **confirmed** | Wrote `(passed_code + passed_rubric_applicable) / (len(code) + total_rubric_applicable)` in Design step 5 and Plan D7, and added an all-FAIL judge monotonicity test to S7. |
| 1 | `N2`: `cases_sha` excludes regression cases while `with` rows compare regression pass rates in `cases=` | minor | **confirmed** | Stated explicitly in Design (*Improving a skill*) and Plan D9 that regression cases are frozen with the harness and editing one requires a fresh baseline. |
| 1 | `N3`: D5 omits that 300s timeout applies to judge runs, and design/plan invert `--collect` alternation order | minor | **confirmed** | Stated in Plan D5 that `--timeout` applies to every harness call (candidate, judge, trigger) and aligned Design Rev 3 to `"alternating without and with"` matching D14. |
| 2 | `N2`: G2 committing `item-adoption` "at once" on `feat/mvp2-s5` can commit `item-authoring` rows before G3 calibration | minor | **confirmed** | Updated G2 to keep baseline rows on both branches uncommitted until G3 finishes so `--rejudge` is never blocked on `feat/mvp2-s5`. |

## Outcome

Accepted (3/3 approvals, 0 blocking, 0 major, `degraded: false`). All confirmed minor fixes applied on `docs/eval-cost-cut` and merged into `main` with `git merge --no-ff`.
