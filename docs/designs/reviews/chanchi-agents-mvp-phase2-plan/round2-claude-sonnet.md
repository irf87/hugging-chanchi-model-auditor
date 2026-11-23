VERDICT: PASS WITH FIXES

Subject: `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` at `127581b` (Revision 2). I re-read the plan against the design, the five skills, `agents_sync.py`, `lessons.py`, `taxonomy.py`, `sync.py`, the three test files and `scripts/check`. I ran `agy models`, `claude --help`, `agy --help` and a read-only `chanchi recommend`. I launched no headless run and did not run pytest. Nothing went wrong in this audit.

## Round-1 findings (my own report)

| id | status | evidence |
|---|---|---|
| F1 design wins vs adapted decisions | RESOLVED | Spec paragraph (lines 27-32) now says the numbered decisions take precedence until G5, and lists D3, D4, D5, D6, D9, D10, D14, D16, D19, D21 for G5 to amend. See N3 for one omission. |
| F2 `skill-chanchi-proof` breaks `test_references_resolve` | RESOLVED | D19 makes the check skip `evals/*/cases/**` and `evals/*/triggers.md`; trigger prompts no longer use fictional names. The `<n>` placeholders in the authoring-skill row do not match the `REFERENCE` regex. |
| F3 runner contract missing | RESOLVED (small gap, N2) | D20 and D22 give the layout (`W`, `W/.state/chanchi.db`, scratch `SYNC`, shim, `FINAL_MESSAGE_FILE`, `python -I grade.py W`). |
| F4 baseline rows rest on a reworded rubric | RESOLVED | D14 `--rejudge` re-judges all baseline outputs; G2 holds rows uncommitted until G3. |
| F5 no path for failing regression or ceiling | RESOLVED | D17 covers a regression failure, the keep rule, and a ceiling stop. |
| F6 skill and wrapper cannot be blind | RESOLVED | D6 exempts the evaluated skill and the wrapper; the static blinding check scans only `prompt.md`, `setup.sh` and case fixtures. |
| F7 calibration label contract | RESOLVED | D14: rubric criteria only, arm hidden, judge label is the rubric-only verdict. A transcript excerpt is on the sheet. |
| F8 S1 misses `--agent` main/scope checks | RESOLVED | D3 renders candidates as `scope: both`; D12 judge is `scope: both`; S1 checks preload on a probe agent. |
| F9 S4/S5 branch order | RESOLVED | Lines 93-95 and D18: branch from `main` after S2, merge `main` with S3 before the baseline. |
| F10 fallback model unverified | RESOLVED | `agy models` lists `claude-sonnet-5-5-low/medium/high`. The Risks row still says "listed in chanchi's catalog", which I did not check; the model itself exists. |
| F11 hill-climb sessions unbudgeted | RESOLVED | D17 and lines 94-95: planned at the gate, exploration count recomputed. |
| F12 `triggers` rows reuse `median_pass` | RESOLVED | D9 documents it, says the signal never reads `triggers` rows, and S2 puts it in the README. |
| F13 unstaged/untracked item before a baseline | RESOLVED | D10 (CLI refuses on unstaged or untracked changes) and G2 (item directory staged). |

Open round-1 findings: none.

## Checks that pass

- **Coverage:** every request item and every phase-2 design item maps to a session or gate step (judge S2; three evals S4/S5; runner S3; ledger and check S2/D10; lesson question S4/D21; adoption eval S5). The signal is computable from `ledger.tsv`, `calibration.tsv` and `chanchi lesson export` (D15).
- **Budget:** per judged skill, capability 2 cases x 2 arms x 3 = 12 and regression 2 x 3 (with-arm only, D5) = 6, so 18 candidate runs plus 18 judge runs = 36; three skills = 108. Adoption is 6 + 3 = 9 (no judge). Triggers are 4 x 4 = 16. Total 133. S1's 14 runs and a few smoke runs leave about 150 for rejudges and hill climbs, so 300 is safe.
- **Lessons skill cap:** the file is 150 lines. The `### Example` block is lines 90-108; replacing it with one line and adding a bullet of about 5 lines ends near 138. `chanchi lesson add` is still documented outside the example, so `test_documented_commands_exist` holds.
- **D21 is feasible with existing code:** `lessons.py` accepts `replaces` (any existing lesson id), `--force-new` exists, `review --decision duplicate --of` moves occurrences, and the reviewer is not the original's author. `tool`, `hook` and `permission` are valid `target_kind` values.
- **D2/D12:** `family_for("sonnet")` is anthropic and `family_for("gemini-4-neon-high")` is google. `agy --model/--effort/--add-dir/--agent` exist, as do `claude --add-dir/--allowedTools/--agent`.
- **Session protocol:** `chanchi recommend --task-type tests --complexity medium` returns `agy:gemini-4-hydrogen-medium:medium` (global, low). Its `explore` list contains `agy:gemini-4-hydrogen-high:high`, so S5 as the single explore session (budget `max(1, floor(5/4))` = 1, blocks nothing) is valid. The `claude:sonnet:high` deviations for S1 and S3 have a stated reason.

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | major | S5 `new-agent` (regression) grader, with D3/D22 | The grader requires `chanchi agents sync --check` to exit 0 in `W`. The runner puts the candidate's rendered wrapper in `W/.claude/agents/agent-chanchi-<role>.md` (or `.agents/agents/...`). That path matches `WRAPPER_GLOBS`, and `sync --check` fails when a present wrapper has no source under `W/agents/`. The check therefore reports an orphan in both arms, so a regression case that must pass 3/3 can never pass, and the unattended executor cannot see why. The same runner-owned paths (`.state/`, `.claude/`, `.agents/`) also sit in the repository that `rename-skill` and `rule-or-check` graders scan. | `agents_sync.sync(check=True)`: `orphans = present - wanted` raises `stale_wrappers`. `WRAPPER_GLOBS = (".claude/agents/agent-chanchi-*.md", ".opencode/...", ".agents/agents/agent-chanchi-*/agent.md")`. Plan D22: "a project repository, if any, is `W` itself". | Pin in D22/S5: graders ignore runner-owned paths (`.state`, `.claude`, `.agents`, `.opencode`). The `new-agent` grader copies only `W/agents/` into a temporary repository and runs `chanchi agents sync <tmp>` then `--check` there. Also say that the setup makes `W` a git repository whose `.gitignore` or exclude file lists the runner-owned paths, so "a file under `tests/` changed" and "no line added to `AGENTS.md`" are read with `git diff`/`git status` on tracked paths. |
| N2 | minor | D22 vs S2 file list | D22 says S2 writes the runner contract into the README evals section and pins it in `tests/test_evals.py`. S2's task text lists neither; its README bullet says only "pointing to the design". An executor following S2 literally omits the contract S4 and S5 depend on. | D22 text; S2 "Files" and the README bullet. | Add the contract text and a test (the documented keys appear in the README) to S2, or move the writing to S3 and make S4/S5 read the plan's D22 directly. |
| N3 | minor | Spec paragraph (line 31) vs D17 | D17 changes the design's keep rule: the design says "kept only when the median improves and the regression cases stay at 100%". D17 also keeps a change when only regression runs rise, and adds a ceiling stop. D17 is not in the list G5 must amend. | Design *Improving a skill*; D17. D11, D15, D20 and D22 add behavior without contradicting, so they are fine. | Add D17 to line 31's list. |
| N4 | minor | D15/D9 signal | The signal takes "rows with `runs` ≥ 3" but does not say which `with` row is current after hill-climb rows exist (latest `kept` or `baseline` whose `item_sha` equals the current tree). A reverted row could be read as the current median. | D9, D15. | State: use the newest `baseline` or `kept` `with` row whose `item_sha` matches the skill's current tree hash, and compare it with the baseline `without` row. Test it in S3. |
| N5 | minor | D7/D14 blinding of the judge | The judge reads `transcript.jsonl`, which shows whether the skill was loaded, so it is not blind to the arm. The owner's sheet hides the arm; the judge's input does not. This can inflate with-arm scores slightly and widen the judge/owner gap. | D14 sheet contents versus the judge inputs in S3. | Accept and record it as a known limit in D14, or strip skill-load events from the transcript copy given to the judge. |
| N6 | minor | Risks table, fallback | "listed in chanchi's catalog for agy" is unverified; the model exists in `agy models`, but the claim about chanchi's catalog was not checked. | Risks row 1. | Say "listed by `agy models`", or check `chanchi models list`. |

No blocking findings. N1 would make an executor stop in S5 or force a baseline with a failing regression case; the rest are cheap wording fixes.
