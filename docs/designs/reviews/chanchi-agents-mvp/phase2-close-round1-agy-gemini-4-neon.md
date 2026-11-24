VERDICT: PASS

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | `docs/designs/reviews/chanchi-agents-mvp/phase2-exit.md:97` | The Rev-6 code-only G2 baselines note (`Reused 16 cached triggers + 3 item-adoption rows`) mixes units (runs vs rows) and double-counts `skill-chanchi-item-adoption-3`'s 4 trigger runs, which are already included in the 16 trigger runs across all 4 skills. | `evals/ledger.tsv` has 4 `triggers` rows totaling 16 runs (`session-audit-1`, `lessons-1`, `item-authoring-1`, `item-adoption-3`, 4 runs each) and 3 `item-adoption` rows totaling 7 runs (`with` 2 + `without` 1 + `triggers` 4); plan D18 reports `~19 runs saved` (12 signal-skill trigger runs + 7 `item-adoption` runs, across 6 preserved rows). | Clarify to `Reused 12 cached signal-skill trigger runs (3 rows) + 7 item-adoption runs (3 rows)` (or `Reused 16 cached trigger runs (4 rows) + 3 item-adoption with/without runs (2 rows)`). |
| F2 | minor | `docs/designs/chanchi-agents-mvp.md:330,336,352-353` | Shorthand `W` is used in `W/.state/chanchi.db`, `W/.git`, `W/.git/info/exclude`, and `so W starts git-clean` without introducing `W` at first mention of the work directory on line 330. | `grep -n '\bW\b' docs/designs/chanchi-agents-mvp.md` shows lines 336, 352, and 353 only; line 330 says `a new directory <tmp>/work-<8 hex>` without naming `W`. | Change line 330 to `a new directory W = <tmp>/work-<8 hex>` (or `(<tmp>/work-<8 hex>, hereafter W)`). |

## Summary

Audited commit `c54da33` (`git diff 2a115c1..c54da33`) on `docs/phase2-exit` covering `docs/designs/chanchi-agents-mvp.md` (Revision 5), `docs/designs/reviews/chanchi-agents-mvp/phase2-exit.md`, and `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md`. No blocking or major defects were found (0 blocking, 0 major, 2 minor).

### Verification evidence

1. **Exit signal, ledger, tree hashes, `GRANDFATHERED`, and Condition 4:**
   - `uv run python scripts/run_evals.py --signal` returned `met: true`, `reason: null`, `lessons: {"met": true, "flagged": []}`, `in_signal: true` for `skill-chanchi-item-authoring` (`3/3`, `1.0` vs `0.67`), `skill-chanchi-lessons` (`1/1`, `1.0` vs `0.0`), and `skill-chanchi-session-audit` (`1/1`, `1.0` vs `0.5`), and `in_signal: false` for `skill-chanchi-item-adoption` (`1/1`, `0.75` vs `0.25`) — exact match with `phase2-exit.md` and the design Status line.
   - `evals/ledger.tsv` has 13 data rows (all candidate `agy:claude-sonnet-5-5-low:low`). `tree_hash()` matches every current `item_sha` prefix in `phase2-exit.md` (`465113c9...`, `efe7be79...`, `cc29cabd...`, `bfec1f50...`).
   - `tests/test_evals.py` `GRANDFATHERED` holds exactly `skill-chanchi-audit-rounds`, `skill-chanchi-model-selection`, and `skill-chanchi-verify`.
   - `uv run chanchi lesson summary` reports 13 pending, 1 rejected, 0 approved/postponed/duplicate; `uv run chanchi lesson export --all --status pending --limit 1000` confirms all 13 pending lessons have `occurrences: 1`.
2. **Design Revision 5 reconciliations (D3, D4, D6, D10, D11, D12, D16, D19, D20, D21, D22):**
   - Verified every reconciled claim against `scripts/run_evals.py` (`NEUTRAL_AGENT = "worker"`, `candidate_wrapper` with `agents_sync.render` / `scope="both"` / arm-specific `skills`, `skill_dir_for`, `exclude_paths`, `build_home`, `build_argv`, `CLAUDE_TOOLS`, `CLAUDE_JUDGE_TOOLS`, `BLINDED_WORDS`, `check_blinded_paths`, `tree_hash`, `item_dir_status`, `CHANCHI_SYNC`), `agents/agent-chanchi-judge/AGENT.md`, `evals/*/eval.toml`, `tests/test_evals.py`, `tests/test_items.py` (`_skip_eval_file`), `pyproject.toml` (`"evals/*" = ["T20"]`, `"tests/*" = ["T20"]`), `skills/skill-chanchi-lessons/SKILL.md` (line 101), and `src/chanchi/lessons.py`. All match shipped code.
3. **Git history, sessions, and audits:**
   - Every referenced commit SHA (`2a115c1`, `6ef6ff4`, `c88396f`, `6b50369`, `ff3c456`, `b9b3228`, `a9db5eb`, `46ae0c6`, `baa96fa`, `5196327`, `d780bbd`, `eb6c931`) exists in git history with matching commit messages and verified merge ancestry (`git merge-base --is-ancestor`).
   - `uv run chanchi show chanchi-agents-phase2` matches every session row (S1–S11, verdicts, executors, `gate:first-green` notes; `closed_at: null` pre-merge as expected).
   - `uv run chanchi audit show` for Audits 12, 16, 17, and 18 matches the outcomes, round counts, approval counts (3/3 with 0 blocking/major in R2 of Audits 16, 17, 18), and `degraded` flags listed in `phase2-exit.md` and G4.
4. **Tests and privacy:**
   - `uv run pytest -q tests/test_privacy.py tests/test_items.py tests/test_rules_budget.py tests/test_evals.py`: `51 passed`.
   - `uv run ruff check && uv run pytest -q`: `All checks passed!` and `1026 passed`, matching the `2a115c1` check count cited in `phase2-exit.md` and G4.
   - Verified zero home paths, emails, or reference-project names in the diff and all three changed files.
