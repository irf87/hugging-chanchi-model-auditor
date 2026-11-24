VERDICT: FAIL

Audit 18, round 1, auditor S3. Subject: commit `4726b09` on `feat/mvp2-s5`,
`skills/skill-chanchi-item-authoring/SKILL.md` (80 lines, HEAD verified at the commit; worktree clean).
Checked against `AGENTS.md`, `docs/designs/chanchi-agents-mvp.md` (Rev 4), `README.md` (D22),
`tests/test_evals.py`, `tests/test_items.py`, `tests/test_skills_content.py`,
`tests/test_rules_budget.py`, `tests/test_privacy.py`, `scripts/run_evals.py`, `scripts/check`,
`agents/agent-chanchi-executor/AGENT.md`, and the eval fixtures for this skill.

## Findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | major | `skills/skill-chanchi-item-authoring/SKILL.md:78-80` (`## Last step`) | The new guidance tells the reader to run "the repository checks named in `AGENTS.md` (such as `python3 tests/check_items.py` and `chanchi agents sync --check`)". `tests/check_items.py` does not exist in this repository and `AGENTS.md` does not name it; the command is taken from the eval's synthetic work directory. This is both factually wrong for the repository the skill targets and evidence that the edit was fitted to the grader rather than derived from the repository's documented workflow. | `ls tests/check_items.py` fails and `git ls-files` has no such path. `AGENTS.md` says only "Tests: `uv run pytest`"; the actual gate is `scripts/check:26-27` (`uv run --group dev ruff check`, `uv run --group dev pytest -q`). The command appears only in `evals/eval-chanchi-item-authoring/cases/*/setup.sh:6-13,50-137` (which writes a synthetic `AGENTS.md` naming it and creates the stdlib shim) and in `new-skill/grade.py:86` / `new-hook/grade.py:63` (which run it). `chanchi agents sync --check` is real (`src/chanchi/cli.py:713-715`), so only the first example is wrong. | Replace the examples with the repository's real checks: `scripts/check` when present, otherwise `uv run pytest` (and `chanchi agents sync --check` where relevant). If a generic example is wanted for minimal repositories, describe it as "the naming check the repository provides, if any" instead of a concrete nonexistent path. |
| F2 | minor | `skills/skill-chanchi-item-authoring/SKILL.md:73-76` (`## Last step`, first paragraph) | "author the item directly in the current working tree ... never stop merely because no separate brief file or branch name was supplied" is unqualified. It is consistent with `AGENTS.md` rule 1 (propose and solve) and does not tell an executor to ignore a worktree/branch that a brief *does* name, but "current working tree" can be read as permission to work on `main` without a branch, which `AGENTS.md` ("Branch per change (never work on `main` directly)") and `agent-chanchi-executor/AGENT.md:13` ("Work only in the worktree and branch the brief names") forbid. | `AGENTS.md` Working Conventions; `agents/agent-chanchi-executor/AGENT.md:13`. The skill text contains no branch/worktree qualification. | Add a clause: "in the worktree and branch the brief names, or create a branch per `AGENTS.md` when none is named". Keep "never commit" as is — it already matches the executor. |

## Accuracy assessment

- `## Eval source` (lines 36-48) matches the enforced contract: `name` equals the directory, `item` is an existing skill, `regression` has at least one case, `capability`/`blind_allow` are string lists, top-level boolean `signal` before `[candidate]`, `[candidate]` keys `agent`/`harness`/`model`/`effort`, `[judge]` iff `rubric.md`, `triggers.md` headings, case files `prompt.md`/`setup.sh`/`grade.py`, and the JSON criterion line (`tests/test_evals.py:70-152,579-592`; `README.md` runner contract; `scripts/run_evals.py:940-941`; design Rev 4 lines 283-292). Accurate.
- `## Hook source` (lines 50-58) matches design Rev 4 lines 84-85: a harness hook is an item under `hooks/hook-chanchi-<name>/` and git hooks are not items. The "never `.githooks/` or `.git/hooks/`" phrasing mirrors the grader's `no_git_hooks` criterion, but it is a fair paraphrase of the design and does not forbid the repository's own gate hooks in `.githooks/`. The executable-script-plus-README layout is sensible, harness-neutral guidance, though it is not a documented repository invariant. Not a finding.
- `## Last step` second paragraph is inaccurate as recorded in F1. The `sys.argv[1]` (work directory) and JSON-line contract for `grade.py` are otherwise correct per `README.md` and `scripts/run_evals.py:940-941`.

## Generalizability assessment

`## Eval source` and `## Hook source` are genuinely useful authoring guidance: they describe real, documented structures a developer needs in order to create a new skill's eval or a hook item, and they are harness-neutral. The `Last step` "do not stall waiting for a brief/branch; never commit; use the checks the repository provides" is also aligned with `AGENTS.md` rule 1 and the executor's "never commit". The overfitting concern is localized to F1: the one concrete check command is lifted from the eval fixture, not from the repository, and would mislead a real author. No evidence of hard-coded grader outputs, eval-only keywords, or behavior that only makes sense under the harness.

## Rules compliance (verified)

- Line budget: 80 <= 300 (`tests/test_rules_budget.py`). PASS.
- No dangling literal item references: the new `<n>` placeholders do not match the item-reference regex in `tests/test_items.py`. PASS.
- Documented `chanchi` commands exist: `chanchi agents sync` is real (`src/chanchi/cli.py:713-715`); `test_skills_content.py` passes. PASS.
- No home paths or consumer/reference-project names in the edited file (`tests/test_privacy.py`). PASS.
- No contradiction with the executor's "never commit"; no instruction to bypass worktree/branch isolation when a brief names one (F2 is a clarity minor only). PASS.
- `evals/ledger.tsv` contains the kept row `skill-chanchi-item-authoring-4` with matching tree hash and verdict; `test_evals.py` passes. PASS.
- Cheap local verification: `pytest -q tests/test_skills_content.py tests/test_items.py tests/test_rules_budget.py tests/test_privacy.py tests/test_evals.py` -> 68 passed. No repository file was edited.

## Summary

Open findings: 2 (1 major, 1 minor). F1 is the blocking issue for approval: the skill cites a nonexistent command as a repository check and thereby leaks the eval fixture into general guidance. F2 is a small clarity fix to keep the "no brief/branch" guidance from implying work on `main`. Recommend a follow-up commit that fixes F1 and optionally F2, then re-audit before merge.
