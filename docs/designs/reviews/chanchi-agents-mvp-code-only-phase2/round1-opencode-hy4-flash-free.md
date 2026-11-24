VERDICT: FAIL

# Audit 17, Round 1 — report

Subject: commit `6fdc5ef` on branch `docs/code-only-phase2-evals`, amending
`docs/designs/chanchi-agents-mvp.md` (Rev 3 -> 4) and
`docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` (Rev 5 -> 6). Round 1, so there are no
earlier findings of mine to re-check. Evidence was re-verified locally by reading the diff, both
amended docs, `scripts/run_evals.py`, `tests/test_evals.py`, `tests/test_run_evals.py`, `README.md`,
`AGENTS.md`, the two executor worktrees' `eval.toml`/`grade.py`/`rubric.md`/`ledger.tsv`, and by
running `uv run pytest -q tests/test_evals.py tests/test_run_evals.py` (59 passed).

## Findings table

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | major | plan Rev 6 line 93 (D15), line 429 (Task S9 `cmd_signal` bullet); `scripts/run_evals.py:1723-1725`; `tests/test_run_evals.py:1049-1056` | The proposed `--signal` still computes `met = lessons["met"] and all(... for e in scoped)`, which is vacuously true when `scoped` is empty. Signal membership now depends on a hand-added `signal = true` in three `eval.toml` files with a default of `bool(judge)` (false for code-only). If any of S10a/S10b omits or misspells that key, the required skill silently drops out of scope and `--signal` can report `met: true` while a phase-2 exit condition is unmeasured. The plan specifies no non-empty / expected-membership guard and no test for it. | Current code: `scoped = [e for e in items_out.values() if e["in_signal"]]` (line 1723) and `all(...)` (line 1724). Existing test `test_signal_reports_none_judge_and_unmet_conditions` asserts `report["met"] is True` with comment "the one item is out of scope" — i.e. the vacuous pass is baked in and Task S9 does not change it. Task S9's test list covers `signal = true` on a code-only eval, `signal = false` on a judged eval, and the omitted default, but never the empty-scope case. | In Task S9 require `cmd_signal` to fail (or report `met: false` with an explicit `reason`) when `scoped` is empty, and preferably to assert that the three expected signal skills are present in `scoped` by `item`. Add a test: with all evals `signal = false` (or all code-only and key omitted), `--signal` must not report `met: true`. Keep the vacuous pass only for the genuine "no evaluated items" case if that is intended, and say so explicitly in D15. |
| F2 | major | plan Rev 6 line 96 (D18), line 455 (G2); `scripts/run_evals.py:1349,1351-1365,1060-1061,1151` | Ledger preservation across rebase produces duplicate `id` values. D18/G2 discard the superseded judged `with`/`without` rows and keep only each item's `triggers` row (and `item-adoption`'s code-only rows). The runner numbers new rows with `counter = sum(1 for r in rows if r["item"] == cfg.item)`, i.e. a row *count*, not `max(numeric suffix)+1`. With only the preserved `triggers` row (id `<item>-3`) left for `session-audit`/`lessons`/`item-authoring`, `counter = 1`, so the fresh G2 `with` row becomes `<item>-2` and the `without` row becomes `<item>-3` — colliding with the preserved triggers row. `append_rows` does not renumber, so duplicates persist into the committed ledger. | On `feat/mvp2-s4`, `evals/ledger.tsv` has `skill-chanchi-session-audit-1/-2/-3` (`with`/`without`/`triggers`); D18 keeps only `-3`, G2 runs with + without (3 candidate runs as stated), giving `counter=1` -> new `-2` and `-3`. `matching_triggers_row` (line 1136-1141) matches the preserved row by `triggers_sha`, so no new triggers row is written — nothing raises the count. `read_ledger` (line 122) does no de-duplication; `--rejudge` (line 1657) and `committed_ledger_ids` (line 1164) resolve rows by `id`, so duplicate IDs can mis-target later tooling even though the Rev 6 gate steps themselves do not call `--rejudge`. | Change the runner's id counter to `max(suffix)+1` over rows for the item (so preservation order/count cannot cause collisions), or have D18 renumber preserved rows to a contiguous `1..k` before G2, and state explicitly that preserved `triggers` rows keep their `triggers_sha` but may be re-numbered. Add a test that ledger ids are unique after preservation + a fresh baseline. |
| F3 | minor | plan Rev 6 line 86 (D8); design Rev 4 line 271 and line 643 (Eval cost risk row) | Leftover judge-centric wording not reconciled with "all four phase-2 evals run code-graded only". D8 still says "This phase judges each output alone against its rubric" — under Option B phase 2 runs no judge at all. The design still says "Graders run in this order: code first, judge second" and the Eval cost risk row still lists "gated judge" as an unconditional mitigation. These read as mandatory-judge statements and contradict the amended sections (design lines 309-311/348-350/414-417 and plan D14/D16). | D8 was not among the decisions Rev 6 amended (header lists D1, D2, D14, D15, D16, D18). Its "why" column ("No comparison of two outputs is needed for the signal") remains true, but the body is stale. | Amend D8 to "This phase has no pairwise judging; phase-2 evals are code-graded (an opt-in judged eval would be judged alone against its rubric)". Make design line 271 conditional ("when an eval opts into a rubric, code runs first, judge second") and mark `rubric.md` as optional in the layout block (line 283) / drop "gated judge" from the unconditional Eval cost row (line 643). |

## Detail and reasoning

### F1 — empty `scoped` can pass the phase vacuously
Task S9 (plan line 429) proposes `entry["in_signal"] = cfg.signal` and a `cal_ok` fallback for
`calibrated: None`, which correctly fixes the crash on code-only evals. It does not, however, guard
the `all(...)` aggregation. `bool(judge)` as the omitted-key default is the right backwards-compatible
choice, but for a code-only eval it is `False`, so adding `signal = true` in S10a/S10b is the only
thing that puts the three required skills in scope. A single missed key removes a required exit
condition without failing anything. The design's "Done only when the phase signal holds ... never
from an impression" (plan line 24) makes a vacuous `met: true` especially harmful. G5's manual check
that all three signal skills appear is a process mitigation, but S9 is the contract that future
evals rely on, so the code should fail closed.

### F2 — id collision from the D18/G2 ledger preservation
D18's intent (reuse cached `triggers` and `item-adoption` rows to save ~19 runs) is sound: neither
`signal` in `eval.toml` nor removal of `rubric.md`/`[judge]` changes `triggers_sha`, and removing the
rubric changes `cases_sha` (rubric hash and judge spec go to `None`), so discarding judged
`with`/`without` rows is correct. The missed detail is row numbering: the runner derives the next id
from a count of the item's rows, not from the largest existing numeric suffix. Discarding two of the
three rows for an item guarantees the next `with`/`without` ids overlap the preserved `triggers`
id. The fix is small and belongs with S9 (which already edits `scripts/run_evals.py`) or as an
explicit note in D18 before G2 writes any rows.

### Design/plan consistency otherwise verified (no finding)
- Revision headers, status line, "Done only when" conditions, D1/D2/D14/D15/D16/D18, S9/S10a/S10b
  and G2/G4/G5 agree on code-graded-by-default with an optional judge; design line 578 and plan
  lines 27-35 express the same four conditions.
- `asymmetry cost` arithmetic checks out: 160 + 3 + 32 + 32 = 227 spent; 227 + 15..26 = 242..253 of
  300; ~19 runs saved = 3 triggers x 4 + `item-adoption` 7.
- `cases_sha` refresh reasoning is correct: kept triggers rows stay valid (`triggers_sha` excludes
  judge/rubric/signal), judged rows are stale after rubric removal; adding `signal` does not change
  the skill tree hash used by `test_ledger_matches_current_item_trees`.
- Cost math for code-only scoring re-verified against the actual graders: Rev-5 `without 0.20`
  (session-audit, 2 code criteria + 3 rubric criteria, 1 code pass) becomes `1/2 = 0.50` code-only;
  `without 0.14` (lessons, 3 code + 4 rubric, 1 pass) becomes `1/3 ~ 0.33`; both still lose to the
  `with` arm at 1.00, so `grade.py` alone is sufficient there. `item-authoring`'s Rev-5 tie stays a
  tie under code-only, which is exactly why G4 schedules its hill climb.
- Removing `rubric.md`/`[judge]` keeps `check_eval_layout`'s `has_judge == has_rubric` invariant
  (both false) and does not break `test_items.py`; adding a `signal: bool` field to `EvalConfig` is
  safe because no test constructs `EvalConfig` directly.
- README's `## Evals` section is still judge-centric, but the plan correctly assigns its update to
  Task S9; that is not a defect of this documentation-only commit.
