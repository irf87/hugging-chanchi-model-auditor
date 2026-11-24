VERDICT: PASS WITH FIXES

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | phase2-exit.md, "Phase 2 audits" last bullet | It cites `phase2-close-round*-*.md` "in this folder". Those files do not exist yet, so the link is dangling until the audit records are archived. | `ls docs/designs/reviews/chanchi-agents-mvp/ \| grep phase2` returns only phase2-exit.md | Archive the closeout round reports in the same merge or a follow-up commit, or reword the bullet to say the records are added after acceptance. |
| F2 | minor | Design Status line, plan G5 line, phase2-exit.md | The text says "closed" and "closing ... on merge", but `chanchi show chanchi-agents-phase2` has `closed_at: null`. This is expected pre-merge. | `closed_at: null`, change id 85 | Run `chanchi change close chanchi-agents-phase2` right after the merge, as planned. |
| F3 | minor | phase2-exit.md header | It says the signal was read "on `main` at `2a115c1`". I ran it on branch `docs/phase2-exit`, which adds only docs over that commit, and got identical output. | The branch diff touches only 3 docs files | None needed. |

## Verification

1. **Signal.** `run_evals.py --signal` returned `met: true`, `reason: null`.
   - `session-audit`: regression 1/1, capability 1.0 vs 0.5.
   - `lessons`: regression 1/1, capability 1.0 vs 0.0.
   - `item-authoring`: regression 3/3, capability 1.0 vs 0.67.
   - `item-adoption`: `in_signal: false`, regression 1/1, capability 0.75 vs 0.25.
   - `lessons.flagged` is `[]`.
   - This matches the JSON block in phase2-exit.md exactly.
   - Ledger: 13 data rows. `item-authoring-4` has verdict `kept`, 6 runs, regression 3/3, `new-skill:1.00` and `new-hook:1.00`. The baseline rows match the summary table.
   - `item_sha` values: the table's `465113c9`, `efe7be79`, `bfec1f50` and `c690e4c4` (baseline) match the ledger. The `cc29cabd` value for the kept `item-authoring` row also matches (ledger row 4); the signal passing confirms the ledger matches the tree.
   - `GRANDFATHERED` in `tests/test_evals.py` is exactly `audit-rounds`, `model-selection` and `verify`.
   - Condition 4: `chanchi lesson export --all --status pending --limit 1000` returned 13 lessons. Every one has `occurrences` 1, matching the "13 pending, every one has occurrences 1" claim. I did not separately check the "1 rejected" count.
2. **Design Revision 5 claims** match the code.
   - `run_evals.py` has the neutral agent name `worker`. It renders the wrapper with `agents_sync.render` and writes the `.git/info/exclude` entries.
   - It uses `acceptEdits`, the `Bash Read Grep Glob Edit Write Skill` tool list, `Bash Read Grep Glob` for the judge, `--add-dir`, and `--` before the prompt.
   - agy gets `--dangerously-skip-permissions`.
   - `work-<tag>` and `sync-<tag>` directories are used.
   - `tree_hash` uses modes `100644`/`100755` and `40000`, over files from `git ls-files --cached`.
   - The git-status refusal to write a ledger row is at line 1177.
   - The default timeout is 300.
   - Opencode no longer appears in the runner.
   - `pyproject.toml` has the ruff `per-file-ignores` for `evals/*` and `tests/*`.
   - `tests/test_items.py` skips `cases/` and `triggers.md`.
   - `agent-chanchi-judge` has `scope: both`, `profile: read-only`, `install: repo` and `skills: []`.
   - The lessons SKILL.md line 101 carries the replacement procedure (`replaces`, `--force-new`, `duplicate --of`).
3. **Plan and records.** The new SHAs are in `git log` on main: `c88396f`, `6b50369`, `a9db5eb`, `baa96fa`, `5196327`, `d780bbd`, `eb6c931`, `ff3c456`, `b9b3228`, `46ae0c6`, `2a115c1`. `chanchi show` has sessions S1–S11 including S8a, S8b, S9, S10a, S10b and S11, all accepted.
   - The runs tally adds up: 160+3+32+32+11+13 = 251 of 300.
   - The G4 13 runs split 1+6+6 = 13.
4. **Tests and privacy.** `pytest tests/test_privacy.py tests/test_items.py tests/test_rules_budget.py tests/test_evals.py` gave 51 passed. `grep` for `/Users/` or `/home/` in the three changed docs found none. AGENTS.md is 142 lines, under the 150 limit.

## Summary
No blocking or major findings. The reconciliation is accurate against the code, the ledger and the database. Three minor items remain: the dangling `phase2-close-round*` reference, the change close that follows the merge, and the branch-vs-main note.
