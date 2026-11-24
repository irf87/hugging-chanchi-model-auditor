VERDICT: PASS WITH FIXES

# Audit 17, Round 2 — report (seat 3, opencode:opencode-go/hy4-flash-free)

Subject: commit `4aed32b` on branch `docs/code-only-phase2-evals`, amending
`docs/designs/chanchi-agents-mvp.md` (Rev 4) and
`docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` (Rev 6) to apply all Round 1 fixes.

Method (re-verified locally, not trusted from the brief): read the full diff
`git diff 6fdc5ef..4aed32b -- <the two docs>` (224 lines), both amended docs in full, the Round 1
consolidation and all three Round 1 reports, the current runner and tests, both executor
worktrees' `evals/ledger.tsv` and one `eval.toml`, and ran
`uv run pytest -q tests/test_evals.py tests/test_run_evals.py` (59 passed). Confirmed via
`git diff-tree` that `4aed32b` is documentation-only (the two docs plus the four new Round 1
review files); no runner/test source changed, so the applied fixes are *specifications* for the
still-future Tasks S9/S10 and are audited as plan/design text, exactly as in Round 1.

## Re-check of my Round 1 findings (done first, per the brief)

| id | status | evidence |
|---|---|---|
| **F1** (major) — empty `scoped` passes `--signal` vacuously | **RESOLVED** | Plan D15 (line 94) now states the fail-closed guard verbatim: `met = bool(scoped) and lessons["met"] and all(cal_ok and e["regression"]["met"] and e["capability"]["met"] for e in scoped)` and `"reason": "no signal evals"` (or null when non-empty). Task S9 (lines 431, 434) specifies the same `bool(scoped)` guard, the `cal_ok = True if e["calibrated"] is None else e["calibrated"]["met"]` fallback (also fixes the crash on `calibrated: None`), the top-level `reason`, and updates `test_signal_reports_none_judge_and_unmet_conditions` to assert `report["met"] is False` **and** `report["reason"] == "no signal evals"`. G5 (line 462) adds the explicit membership check: `in_signal: true` for the exact three signal skills and `false` for `item-adoption`. Cross-checked against current source: `run_evals.py:1723-1725` still has the unguarded `all(...)`, and `:1695` still uses `cfg.judge is not None` — i.e. the change is correctly left to S9, not silently assumed done. |
| **F2** (major) — duplicate ledger IDs after D18/G2 preservation | **RESOLVED** | Task S9 (line 430) now requires `counter` from the maximum existing numeric suffix `<item>-<n>` (default 0) instead of `sum(1 for r in rows if r["item"] == cfg.item)`, with test (f) for unique IDs after gaps (`<item>-3` + fresh baseline -> `-4`, `-5`). D18 (line 97) renumbers each preserved `triggers` row from `<item>-3` to `<item>-1`, verifies cache hits with `--dry-run`, and replaces shared `refs/stash` with per-worktree temp-file save/`git checkout --`/rebase/restore; S10a (441), S10b (449) and G2 (459) carry the same procedure. Verified against source and data: `run_evals.py:1349` is the old count-based `counter`, `make_row` (`:1149-1151`) uses the counter directly as the suffix, and both worktree ledgers have `-1/-2/-3` rows per skill — so the described collision was real and the specified fix removes it. |
| **F3** (minor) — leftover judge-centric wording | **RESOLVED** | Design line 271-272 is now conditional ("code-graded by default ... when an eval opts into a qualitative `rubric.md`, ... code first, judge second"); layout block (280, 284, 289) marks `eval.toml`'s `[judge]` and `rubric.md` optional/present only with `[judge]`; Eval cost risk (645) reads "code-graded by default (optional judge gated on passing code when a rubric is present)". Plan D8 (87) now says "no pairwise judging; all four phase-2 evals are code-graded only", Sessions note (122), Verification plan (467-471) and Risks (480, 482, 484) all reconcile. All three of my F3 targets are addressed. |

All three of my Round 1 findings are RESOLVED. No PARTIAL or OPEN Round 1 finding remains.

## Findings table (new, still open — counted in the verdict)

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | minor | plan Rev 6 line 97 (D18 parenthetical), vs lines 449 (S10b) and 459 (G2) | The newly added blanket "renumbering each preserved uncommitted `triggers` row from `<item>-3` to `<item>-1`" is literally inconsistent with preserving `item-adoption`'s 3 code-only rows: `item-adoption`'s rows are `-1 (with), -2 (without), -3 (triggers)`, so renumbering *its* preserved triggers row to `-1` collides with its preserved `with` row `-1`. S10b and G2 disambiguate correctly (keep all 3 `item-adoption` rows as-is; renumber only `item-authoring`'s triggers row), so practical risk is low, but the primary decision text invites a literal reading that creates a duplicate ID — the very class of defect F2 set out to eliminate. | Worktree ledger `.claude/worktrees/chanchi-p2s5/evals/ledger.tsv` shows `skill-chanchi-item-adoption-1/-2/-3` (with/without/triggers). D18 says "each preserved uncommitted `triggers` row"; S10b says "`item-adoption`'s 3 code-only rows and `item-authoring`'s preserved `triggers` row renumbered to `skill-chanchi-item-authoring-1`"; G2 says "preserve ... `triggers` rows (renumbered to `<item>-1`) and `item-adoption`'s 3 code-only rows". | Qualify D18's parenthetical to the three skills whose `with`/`without` rows are regenerated (`session-audit`, `lessons`, `item-authoring`), e.g. "renumber each preserved `triggers` row **for a skill being re-baselined** from `<item>-3` to `<item>-1`; keep `item-adoption`'s 3 code-only rows unchanged". Or delete the renumbering from D18 and rely solely on S9's max-suffix IDs (which already prevent collisions) plus S10a/S10b/G2. |
| N2 | minor | plan Rev 6 line 371-373 (Task S7 bullet), vs line 94 (D15) and line 431 (S9) | Task S7 still describes D15 as the Rev-5 judge-based signal: "`--signal` (D15) checks contrast + `len(cal_rows) >= 6 and agree >= len(cal_rows) - 1`, `passed == runs and runs >= 1`, and `with > without`". D15/S9 now define a code-only signal with `bool(scoped)`/reason and `cal_ok` fallback, so this is stale judge-centric wording left behind by F3's reconciliation. S7 is a completed task, so this is a documentation-consistency nit, not a behavioral defect. | S7 is marked complete at lines 114/458 (`6ef6ff4`) and S9 (lines 424-437) is the current D15 spec. The Round 1 consolidation (line 27) enumerated the reconciled plan sections (D8, S4/S5 rubric bullets, Sessions note, Verification, Risks) and did not include S7. | Add a one-line note to the S7 bullet that it implemented D15 under Revision 5 and is superseded for phase 2 by S9/D15 (code-only, fail-closed), or reword the bullet to reference S9 for the current `--signal` semantics. |

## Design/plan consistency otherwise verified (no finding)

- Revision headers (design Rev 4 / plan Rev 6, both `draft`) and the "Done only when" conditions
  (design 580-588, plan 24-38) agree: four conditions, with Condition 1 now explicitly optional
  for code-graded evals; the fail-closed guard is correctly a runner/plan (D15) detail, not a
  design contradiction.
- `signal` key placement is fact-correct: verified `.claude/worktrees/chanchi-p2s4/evals/eval-chanchi-session-audit/eval.toml`
  has `blind_allow = []` as a top-level key immediately before `[candidate]`, so "place `signal`
  before `[candidate]`, next to `blind_allow`, never nested" is accurate; `tests/test_evals.py:92`
  (`cand = cfg.get("candidate")`) confirms the spec'd `assert "signal" not in cand` catches nesting.
- D18's hash-invalidation claim is sound: `cases_sha` includes `judge_or_null` and `rubric.md`
  (D9), but `item-adoption` is code-only in both Rev 5 and Rev 6 (`judge_or_null = null`, no
  rubric), so its `cases_sha` is stable; `triggers_sha` hashes `{harness, model, effort}`, skill
  description and `triggers.md`, none of which include `judge`/`rubric`/`signal`. Judged
  `with`/`without` rows are correctly discarded after rubric removal.
- Renumbering + max-suffix interlock: after a preserved triggers row becomes `<item>-1`, a fresh
  `--arm auto` run (no cached `without`, cached `triggers`) writes only `with`/`without` rows as
  `-2`/`-3` — cleanly ordered and unique, matching D18's stated `1 (triggers), 2 (with), 3 (without)`.
- Cost/budget math still checks: ~227 spent + ~15–26 remaining = ~242–253 of 300; the Budget note
  about `description`-change adding +4 trigger runs matches the 4 prompts in each `triggers.md`
  (2 must-load + 2 must-not-load); G4's `2–6`/`4–6` range and the 3–4 optional-judge runs are
  consistent with D5 adaptive repeat as confirmed in Round 1.
- `uv run pytest -q tests/test_evals.py tests/test_run_evals.py`: 59 passed on `4aed32b`
  (expected — the code changes are scheduled for S9, which has not run).

## Summary

No blocking or major finding; all three of my Round 1 findings (F1 empty-scope guard, F2
max-suffix IDs/ledger preservation, F3 judge-centric wording) are RESOLVED in `4aed32b`. Two new
minor findings remain (N1 D18 renumbering ambiguity vs `item-adoption`'s preserved rows; N2 stale
Rev-5 `--signal` wording in Task S7), both low-risk documentation fixes. Per the audit-round rule
(a pass with only minor fixes counts as approval), the Round 2 subject is acceptable once N1/N2
are applied.
