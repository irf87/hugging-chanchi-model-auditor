VERDICT: PASS

Audit 18, round 2, auditor S3 (`opencode:opencode-go/hy4-flash-free`). Subject: commit `691472b` on `feat/mvp2-s5`, `skills/skill-chanchi-item-authoring/SKILL.md` (85 lines) plus the `evals/ledger.tsv` row. HEAD verified at `691472b53b8c912fedae9622ed7660f4062e0e53`; worktree clean. Diff checked with `git diff 4726b09..691472b`. In line with my auditor role I re-checked only my own Round 1 findings and did not read any other auditor's report.

## Round 1 re-check (done first, as required)

| id | severity | where | problem (Round 1) | evidence | fix |
|---|---|---|---|---|---|
| F1 — RESOLVED | major | `SKILL.md:83-85` (`## Last step`) | Cited a nonexistent check command (`python3 tests/check_items.py`) taken from the eval fixture, not from the repository — factually wrong and evidence of grader-fitting. | The offending command is gone from the file. It now reads: "Run `scripts/check` when present; otherwise run the verification checks documented in the repository's `AGENTS.md` (such as its item-naming check and `chanchi agents sync --check`)." `scripts/check` exists (executable, gate at `scripts/check:26-27`); the item-naming check is real (`tests/test_items.py`); `chanchi agents sync --check` is real (`src/chanchi/cli.py:715`). This is the fix I recommended in Round 1. | No further action. |
| F2 — RESOLVED | minor | `SKILL.md:77-81` (`## Last step`) | Unqualified "author directly in the current working tree ... never stop merely because no separate brief file or branch name was supplied" could be read as permission to work on `main`. | The text now opens: "Follow the worktree and branch a brief names, and never work directly on `main` (`AGENTS.md`)." The no-brief case is narrowed to "a direct authoring request inside an already-isolated workspace with no separate brief file", and the blanket "never commit" is replaced by role-based rules "(executors never commit; orchestrators commit source, wrappers, and ledger rows after checks pass)". Verified against `AGENTS.md` Working Conventions ("Branch per change (never work on `main` directly)") and `agents/agent-chanchi-executor/AGENT.md:3,21` ("Never commits, merges or writes chanchi records"). Matches my Round 1 recommendation. | No further action. |

Both Round 1 findings are RESOLVED with direct textual and source-level evidence.

## New findings

None. No open findings remain (0 blocking, 0 major, 0 minor).

## Accuracy assessment

- `## Eval source` (`SKILL.md:36-52`) matches the enforced contract in `tests/test_evals.py`: `name` equals the directory, `item` is an existing skill, `regression` requires at least one case (`test_evals.py:104-107`), `capability` and `blind_allow` are string lists (`:108-109`), top-level boolean `signal` before `[candidate]` (`:92-99`, `:431-448`), `[candidate]` keys `agent`/`harness`/`model`/`effort`, `[judge]` iff `rubric.md` (`:126-131`), and a judge model from a different family via `chanchi.taxonomy.family_for` (`:132-150`, imported at `:14`). The new blinding claims are accurate: blinded words are banned unconditionally in `prompt.md` and allowed elsewhere only via `blind_allow` in `setup.sh`/fixtures (`check_blinding`, `:155-182`), with `grade.py` exempt (`:164-165`). The "1 regression + 1 capability by default" line is guidance, not a false statement of the code contract (`capability = []` remains valid). The "grandfathered skills are listed in `tests/test_evals.py`" claim matches `check_skills_have_evals` (`:185-188`). Accurate.
- `## Hook source` (`SKILL.md:54-62`) is consistent with the design: harness hooks live under `hooks/hook-chanchi-<n>/`; git hooks in `.githooks/`/`.git/hooks/` are not items. Softening "never `.githooks/`" to "are not chanchi items" and "Minimal" to "Suggested" removes the Round 1 grader-paraphrase smell without changing the documented invariant. The executable script + `README.md` layout is sensible harness-neutral guidance, not a claimed repository invariant. Accurate.
- `## Last step` (`SKILL.md:75-85`): branch/worktree precedence, the "no separate brief in an isolated workspace" carve-out, and role-based commit rules all match `AGENTS.md` and the executor agent (see re-check evidence above). `scripts/check` and both `chanchi` commands (`agents sync --check`, `agents link --user`) exist (`src/chanchi/cli.py:715,719,152-153`). Accurate.
- Eval ledger: row `skill-chanchi-item-authoring-4` records tree hash `cc29cabd93da0abf723ce2a5dd68ffcc3c119e55`, which I verified equals `git rev-parse HEAD:skills/skill-chanchi-item-authoring` at `691472b`. Recorded result: `verdict=kept`, `regression=3/3` (`new-skill:1.00,new-hook:1.00`), `capability=1.00`, `lift=0.33`, 6 runs — internally consistent with the brief. I did not independently re-execute the six live adaptive harness runs (they require external model calls, not cheap local checks); I verified the recorded row, the matching tree hash, and the static gates.

## Generalizability assessment

`## Eval source` and `## Hook source` remain genuinely useful, harness-neutral authoring guidance describing real documented structures. The Round 2 edits remove the last eval-fixture leak (the nonexistent check command) and replace it with the repository's real checks, so the `Last step` now generalizes to a real authoring repository. No hard-coded grader outputs, eval-only keywords, or harness-specific behavior found.

## Rules compliance (verified)

- Line budget: 85 <= 300 (`tests/test_rules_budget.py`). PASS.
- No dangling literal item references: `<n>` placeholders and new dotted references do not match the item-reference regex; `tests/test_items.py` passes. PASS.
- Documented `chanchi` commands exist; `test_skills_content.py` passes. PASS.
- No home paths or consumer/reference-project names in the edited file (`tests/test_privacy.py`). PASS.
- No contradiction with the executor's commit rule; brief branch/worktree precedence and the `main` prohibition are preserved. PASS.
- `evals/ledger.tsv` row present with matching tree hash and `kept` verdict; `test_evals.py` passes. PASS.
- Cheap local verification: `uv run pytest -q tests/test_skills_content.py tests/test_items.py tests/test_rules_budget.py tests/test_privacy.py tests/test_evals.py` -> 68 passed. No repository file was edited.

## Summary

Open findings: 0. Both Round 1 findings (F1 major, F2 minor) are RESOLVED with verified textual and source-level evidence. The Round 2 changes fix the grader-fit and the `main`-work ambiguity exactly as recommended, introduce no new issues, and all static gates pass. Approve for merge.
