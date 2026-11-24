VERDICT: PASS

## Audit 16 / Round 1 — Cheaper Eval Protocol Amendment (seat 3)

**Subject.** commit `d73b44a` on branch `docs/eval-cost-cut`, diff against `main` (`9fee08d`). Two
files changed, docs only: `docs/designs/chanchi-agents-mvp.md` -> Revision 3 and
`docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` -> Revision 5. No implementation file
is touched by the commit; S7/S8 (future executors) carry the runner/test/doc changes. I therefore
audited the two docs against the current code, CLI, tests and the S4/S5 worktrees as the feasibility
and self-consistency evidence, and re-ran cheap facts locally. I edited no repository file.

**Round.** Round 1; no earlier findings of mine to re-check.

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | plan Rev 5, gate step G3 (and Risks row "judge agrees below 5/6") | The one-time judge escalation path (`gemini-4-hydrogen-high` -> `gemini-4-neon-high` after a failed reword) is stated as a model swap followed immediately by "Commit the ledger rows". Because the judge spec is part of `cases_sha` (D9), swapping the judge changes `cases_sha`, so the uncommitted baseline `without` row no longer matches and the saved calibration runs no longer qualify. G3 does not explicitly say to re-run the baselines / re-collect calibration under the new judge before committing. A literal reading could commit rows whose scores and `calibration.tsv` were produced by a judge no longer named in `eval.toml`. It is conditional (only on the escalation branch) and the owner is involved, so it is minor, not blocking. | Plan D9: `cases_sha` hashes `(candidate, judge_or_null, ...)`. D14: collection reuses saved runs "matching `cases_sha`". G3 (lines ~384-386): "...escalate the judge to `agy:gemini-4-neon-high:high` (D2). Commit the ledger rows...". No re-baseline step between them. | In G3 and the matching Risks row, state that a judge escalation re-keys `cases_sha`: re-run the fresh baselines (`--arm auto` re-runs `without` automatically), re-run `--calibration-sheet --collect` and `--calibrate`, then commit. The work stays within budget (~227-250 spent before escalation; ~23 extra runs still under 300). |

No blocking or major findings. All seven handoff items and decisions 1A/2A/3A are covered and the
two amended documents are mutually consistent and mathematically sound. Detail below.

## Verification performed (all local, no headless eval runs launched)

- **Diff scope:** `git diff main..d73b44a --stat` shows only the two docs (126 + 169 lines). HEAD
  is `d73b44a`, parent `9fee08d`; branch `docs/eval-cost-cut`.
- **Handoff items 1-7:** mapped to D5/D9 (1 run + adaptive repeat), D5/D9 (cached `without` via
  `cases_sha`), D5/D9 + design step 6 (description-gated `triggers_sha`), D7 + design step 5 (judge
  only capability cases and only on code-passed runs), D23/S8 (1+1 cases), D2 + cost controls
  (other-quota candidate, no `--max-turns`, 300s `--timeout`), D14/D15 (6-sample calibration). All
  present. Decisions 1A (D2 candidate/judge/escalation), 2A (D23 + S8 trims), 3A (D23 + G2 clean
  re-baselines of all four evals) are reflected verbatim in both docs.
- **Doc-to-doc consistency:** the plan's "Done only when" 4 conditions match the design's "Signal to
  move on"; both use `total >= 6 and agree >= total - 1`, `1/1 or 3/3` regression, "beats the cached
  without arm", and the pending-lesson check. The plan's Spec paragraph correctly says D2, D5, D7,
  D9, D14, D15, D17 and D23 are already folded into Rev 3 of the design; the design diff confirms
  each of those topics is present.
- **Ledger compatibility (D9):** `LEDGER_COLUMNS` in `scripts/run_evals.py` and the header of
  `evals/ledger.tsv` both have exactly 15 columns in the same order; `tests/test_evals.py`
  (`test_ledger_header_exists`, `check_ledger`) still import `LEDGER_COLUMNS`, `read_ledger`,
  `tree_hash` and pass. The `note` key=value tokens are additions inside the existing `note` cell,
  so no schema change is needed. Verified.
- **D7 monotonicity:** with C code criteria and R rubric criteria, a code-passed run scores
  `(C + j)/(C + R - n) >= C/(C+R)` (applicable = code + judge, N/A excluded; `score_run` at line 547
  confirms code criteria are in the denominator), while a code-failed run scores
  `passed_code/(C+R) <= (C-1)/(C+R)`. Since `C/(C+R) > (C-1)/(C+R)`, every code-failed run scores
  strictly below every code-passed run. The `C=0` branch is unreachable (empty `all()` passes code).
  Claim holds.
- **Aggregation and hill climb:** D9's "median of per-case medians" weights capability cases equally
  under adaptive 3-run repeats; D17's `reg_rate = reg_passed/reg_runs` with `>= prev_reg_rate`
  correctly avoids reading `1/1` as worse than `3/3`; ceiling (1.0 vs 1.0) handling is specified.
  Sound.
- **Caching hashes (D9):** `cases_sha` covers capability cases + rubric + candidate + judge and
  excludes regression cases, `triggers.md`, `calibration.tsv`, `skills/<item>` — exactly the inputs
  the `without` arm uses. `triggers_sha` covers `{harness, model, effort}`, description and
  `triggers.md`. `candidate_spec` in the runner is `harness:model:effort` (line 181), consistent with
  both hash definitions. Invalidation rules are self-contained and rose from the ledger's own
  `note` tokens. Sound (with minor F1 on the escalation path).
- **D2 model facts:** `harnesses.split_agy_model` requires the effort suffix and strips it, so
  `claude-sonnet-5-5-low/low -> claude-sonnet-5-5`, `gemini-4-hydrogen-high/high ->
  gemini-4-hydrogen`, `gemini-4-neon-high/high -> gemini-4-neon`. `taxonomy.family_for` maps the
  candidate family to `anthropic` and both judges to `google` — cross-family invariant holds on the
  base and escalation paths. `chanchi models list` confirms all three specs active: candidate cost
  tier 2 / anthropic, hydrogen cost tier 1 / google, neon cost tier 2 / google. Verified.
- **CLI facts:** `claude --help` and `agy --help` contain no `--max-turns` flag (agy only has
  `--print-timeout`), confirming the docs' "verified locally 2026-11-23" claim. The runner's
  `--timeout` default is currently 1800s (line 1362) and S7 lowers it to 300s — the plan describes
  this as future work, so no contradiction. Verified.
- **D23 case selection vs S4/S5 worktrees:** inspected read-only. S4 has
  `eval-chanchi-session-audit` cases {stop-plan-gap, clean-complete, false-claim, scope-and-choices}
  and `eval-chanchi-lessons` {record-failure, repeat-existing, nothing-wrong, review-check-first};
  S5 has `eval-chanchi-item-authoring` {new-skill, new-agent, new-hook, agent-without-model} and
  `eval-chanchi-item-adoption` {propose-new, retired-entry} (already 1+1). Every keep/drop name in
  D23 and S8 exists in the correct arm list; the candidate agents in `eval.toml` match D2. Verified.
- **Budget / order:** G1b ~3 + G2 ~31 + G3 ~30 + G4 ~10-15 = ~68-79 remaining (doc says ~67-90),
  plus ~160 spent = ~227-250 of the 300 cap; consistent with the Risks row. D18/S7/S8 order is
  rebase-not-merge onto `main`, S4 before S5 (both edit `GRANDFATHERED`), S7 before S8 before G1b,
  gate green before each merge — consistent with AGENTS.md (`--no-ff`, author-does-not-audit,
  event-driven evals) and the handoff's recorded Rev-4 rebase bug.
- **Gate health:** `bash scripts/check` -> ruff clean + 1002 tests passed; `uv run pytest -q
  tests/test_evals.py tests/test_run_evals.py tests/test_harnesses.py tests/test_catalog.py` -> 95
  passed. The docs-only commit does not break any current check. No home path or reference-project
  name appears in the amendments.

**Anything that went wrong:** nothing; all local checks were reproducible. I did not run any real
headless eval (out of scope and cost-sensitive), so claims that depend on a live agy run (G1b smoke,
actual judge agreement) are treated as plan steps, not verified outcomes.
