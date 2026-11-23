VERDICT: PASS WITH FIXES

## Round 2 findings re-check

| id | round 2 severity | status | evidence |
|---|---|---|---|
| F9 | minor | RESOLVED | `D14` (plan line 73), `S3` (lines 170–171, 192), and `G3` (line 316) now all use `run_evals.py <item> --rejudge` with no `<sheet>` argument, re-judging every saved output of the latest baseline, honoring `--yes` and `--dry-run`, updating the uncommitted `with` and `without` rows, and then re-running `--calibrate <sheet>`. |
| F10 | minor | RESOLVED | `launch-permissions` merged on `main` and into `f0004ae` (`src/chanchi/harnesses.py:102-108` emits `--permission-mode acceptEdits --allowedTools ... -- <prompt>`), so `D4` (plan line 63) accurately cites it, adds `Skill`, explicitly covers every `claude` run of the runner (both candidate and trigger), and `S3` (lines 177–178) passes `D4`'s permission flags on trigger runs. Verified flags against `claude --help`. |

## New findings (open: 0 blocking, 1 major, 0 minor)

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F11 | major | `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` (`S5` `new-agent`, lines 276–279) | `S5` grades `new-agent` by running `chanchi agents sync --check` *"on a temporary git repository holding a copy of `W`'s tracked files (runner paths are excluded, D22)"*. Because `agent-chanchi-executor` never commits (`agents/agent-chanchi-executor/AGENT.md:21`) and will not stage new files, the newly created `agents/agent-chanchi-<n>/AGENT.md` and its generated wrappers are untracked in `W`. Copying only tracked files (`git ls-files`) omits the new agent and its wrappers, so `chanchi agents sync --check` passes trivially on the setup's existing agents even if the candidate forgot to run `chanchi agents sync` or wrote stale wrappers. | Plan lines 276–279 (`new-agent`), line 81 (`D22` excludes runner paths via `W/.git/info/exclude`), `agents/agent-chanchi-executor/AGENT.md:21`, and `src/chanchi/agents_sync.py:20,192` (`WRAPPER_GLOBS` only matches `agent-chanchi-*`, so the neutral `worker` wrapper from `D3` is already ignored). | Grade `chanchi agents sync --check` either directly in `W` (since `D3`'s `worker` wrapper does not match `WRAPPER_GLOBS`), or on a temporary git repository holding a copy of `W`'s tracked and untracked non-excluded files (`git ls-files -z --cached --others --exclude-standard`), which includes the candidate's new untracked files while omitting the runner paths excluded in `W/.git/info/exclude`. |

## Summary by check (open findings only: 0 blocking, 1 major, 0 minor)

1. **Coverage:** Complete. `agent-chanchi-judge`, evals for all three design skills plus `skill-chanchi-item-adoption`, `scripts/run_evals.py`, `evals/ledger.tsv` and its `tests/test_evals.py` checks, the check-first review question in `skill-chanchi-lessons`, the `skill-chanchi-item-authoring` layout rule update, and the file-backed `--signal` report (`phase2-exit.md`) are all covered by `S1`–`S5` and `G1`–`G5`.
2. **Fidelity:** Sound. `D3`, `D4`, `D5`, `D6`, `D9`, `D10`, `D14`, `D16`, `D17`, `D19`, and `D21` are all listed in lines 31–32 and scheduled for design amendment in `G5` (audited as a rule change). `D4` and `D21` match `src/chanchi/harnesses.py`, `src/chanchi/lessons.py`, and `AGENTS.md`.
3. **Feasibility:** One major defect (`F11`) in `S5` (`new-agent` grader copying only tracked files instead of `--cached --others --exclude-standard` or running in `W`). Everything else in `S1`–`S5` and `G1`–`G5` is executable as written: `D11` + `D18` keep `scripts/check` green on `main`, `skills/skill-chanchi-lessons/SKILL.md` stays within the 150-line cap (~138–140 lines after moving `### Example` to `references/example.md` and adding the verbatim bullet), `eval-chanchi-lessons` works without `chanchi models add` (`lessons.py:85-106`), and `eval-chanchi-session-audit` adds models explicitly.
4. **Eval soundness & budget:** Sound. `D3` (neutral `worker` wrapper, `scope: both`, `skills: [<item>]` vs `[]`), `D4` (isolated `HOME`), `D20`/`D22` (`CHANCHI_DB`, `CHANCHI_SYNC`, `.git/info/exclude`), `D6` (blinding + `blind_allow`), and `D14` (stripped skill-load events in judge transcript copy) keep arms isolated and blinded. Baseline arithmetic (`40 * 3 + 13 = 133` runs) plus `S1` (`≤ 14`) and `G1` (`2`) totals `≤ 149` of 300 approved runs, leaving `≥ 151` runs for `--rejudge` and hill climbing.
5. **Session protocol:** Sound. Re-verified against `uv run chanchi recommend` for `integration/medium`, `tests/medium`, and `integration/high`: `S1` and `S3` cite `claude:sonnet:high` `task_type+complexity` / `task_type` evidence (`n = 7`, `clean_rate = 1.0`) over weak `global` recommendations; `S5` uses one explore session (`agy:gemini-4-hydrogen-high:high`) on non-blocking `tests/medium` work within the `max(1, floor(4 / 4)) = 1` budget and starts with `--tags agent-chanchi-executor,explore`.

## Local checks run

- `git rev-parse HEAD` → `f0004aee18f01f3d36eedc6c2db5af889725b0ca`
- `git diff 127581b f0004ae -- docs/superpowers/plans/`
- `uv run pytest -q tests/test_items.py tests/test_skills_content.py tests/test_rules_budget.py tests/test_harnesses.py` → `72 passed in 0.41s`
- `uv run chanchi recommend` for `integration/medium`, `tests/medium`, and `integration/high`
- `uv run chanchi lesson export --all --status pending --limit 1000`, `uv run chanchi lesson export --help`, `uv run chanchi lesson add --help`, `uv run chanchi lesson review --help`, `uv run chanchi models list`
- `claude --help` and `agy --help`
