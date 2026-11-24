# chanchi Agents — MVP Phase 2 (Skills Tested by Evals) Implementation Plan

- **Revision:** 5 (2026-11-23: amended for the cheaper eval protocol — owner decisions 1A, 2A, 3A —
  updating D2, D5, D7, D9, D14, D15, D16, D17, D18, adding D23, S7, S8 and revised G1b–G5 run
  counts; audited before merge alongside Revision 3 of `docs/designs/chanchi-agents-mvp.md`.
  Revision 4 was accepted by the owner on 2026-11-23 after round 3 of chanchi audit 12; see
  `docs/designs/reviews/chanchi-agents-mvp-phase2-plan/`.)

> **For agentic workers:** each session below is one brief for `agent-chanchi-executor` (S1 runs
> as `agent-chanchi-researcher`). Steps use checkbox (`- [ ]`) syntax. Write the failing test
> first, then the code.

**Goal:** Ship phase 2 of `docs/designs/chanchi-agents-mvp.md`: `agent-chanchi-judge`, evals for
`skill-chanchi-session-audit`, `skill-chanchi-lessons` and `skill-chanchi-item-authoring`,
`scripts/run_evals.py`, `evals/ledger.tsv` and its gate check, and the "can a check enforce it?"
question in lesson review. Also the backlog this phase unblocks: an eval for every skill created
without one (`skill-chanchi-item-adoption`), as `skill-chanchi-item-authoring` requires.

**Done only when the phase signal holds** (design Revision 3, *Adoption plan*, phase 2), read from
the ledger and the calibration files, never from an impression:

1. each of the three skills has a calibrated judge: the owner labeled at least 6 outputs and the
   judge agrees with at most one disagreement (`total >= 6` and `agree >= total - 1`, i.e., ≥ 5/6
   for 6 samples or ≥ 9/10 for 10 samples);
2. its regression cases pass 100% of executed runs in the with-skill arm (`1/1` by default, `3/3`
   when confirmed);
3. its capability median with the skill beats the cached arm without it;
4. no pending lesson with 2 or more occurrences proposes a prose rule where a check is possible
   (read on 2026-11-23: every pending lesson has 1 occurrence, so this holds today; re-read at
   the end).

**Spec:** `docs/designs/chanchi-agents-mvp.md` (Revision 3), sections *Layer 2: skills tested by
evals*, *Repeated corrections become checks*, *Adoption plan* (phase 2) and *Verification plan*.
When this plan and the design disagree, the design wins (stop and report), except on the points the
numbered decisions below adapt: those take precedence until G5 amends the design. The decisions
below fill what the design leaves open; D3, D4, D6, D10, D16, D19 and D21 adapt it, and the gate
commit (G5) reconciles any remaining plan-only details into the design text so both agree (D2, D5,
D7, D9, D14, D15, D17 and D23 are already folded into Revision 3 of the design).

**Tech stack:** Python ≥ 3.11 standard library, pytest and ruff (dev only), uv.

## Global constraints

- Runtime dependencies stay empty; `scripts/run_evals.py` is standard library only and may import
  `chanchi`. English everywhere. No home path, email or reference-project name in any committed
  file (`tests/test_privacy.py`).
- **Executor sessions** work in `.claude/worktrees/chanchi-<id>` and export a scratch database and
  `SYNC` first: `export CHANCHI_DB="$(mktemp -d)/chanchi.db" CHANCHI_SYNC="$(mktemp -d)/SYNC"`.
  They run `uv run ...` inside the worktree. **No executor session launches a real harness CLI**
  (claude, agy, opencode) except S1, whose runs are counted against the budget; runner tests use a
  fake harness executable written by the test.
- **Eval budget:** the owner approved 300 headless runs for this phase (2026-11-23), counting
  candidate, judge and trigger runs. About 160 runs were spent before the cost-cut amendment; the
  remaining work under Revision 5 is estimated at ~67–90 runs (inside the ~140 remaining). Only the
  orchestrator runs `scripts/run_evals.py` against real harnesses, keeps a running total in the
  gate record, and stops and asks before crossing 300.
- Executors run unattended with their auto-approval flag (`AGENTS.md`, Working Conventions); they
  never commit, merge, push or write chanchi records; they report each verification as the exact
  command plus its last output line and stop at any gap. Last step: `scripts/check`.
- Rules budget (`tests/test_rules_budget.py`): `SKILL.md` ≤ 300 lines;
  `tests/test_skills_content.py` caps `skill-chanchi-lessons/SKILL.md` at 150, and it is at 150
  today.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | **Eval names.** The eval of `skill-chanchi-<n>` is `evals/eval-chanchi-<n>/` (for example `eval-chanchi-session-audit`). `eval.toml` holds `name` (equal to the directory), `item` (the skill), `[candidate]` (`agent`, `harness`, `model`, `effort`), `[judge]` (`harness`, `model`, `effort`; absent when there is no `rubric.md`), `regression = [<case>...]`, `capability = [<case>...]` and `blind_allow = [<word>...]` (D6). An evaluated item is a skill that has an eval directory | The design's layout; one place names the candidate and the judge |
| D2 | **Models (amended Rev 5, owner decision 1A).** Candidate `agy` / `claude-sonnet-5-5-low` / `low` (family `anthropic`, agy's quota, low effort; `harnesses.split_agy_model` turns it into `--model claude-sonnet-5-5 --effort low`); judge `agy` / `gemini-4-hydrogen-high` / `high` (family `google`, cost tier 1; escalate to `agy` / `gemini-4-neon-high` / `high` only if `hydrogen` fails calibration after one rubric rewording). `scripts/run_evals.py` remains harness-agnostic (`claude` and `agy` both supported). Candidate agents: `agent-chanchi-orchestrator` for session-audit and lessons, `agent-chanchi-executor` for item-authoring and item-adoption. G1b confirms `agy:claude-sonnet-5-5-low` (case + trigger) and `agy:gemini-4-hydrogen-high` in one smoke run before baselines | Zero Claude CLI quota spent on evals while preserving Anthropic-candidate vs Google-judge cross-family separation and scaling to future projects |
| D3 | **Arms and skill preload (adapts *One run*, step 2: the runner renders the wrapper instead of copying the committed one).** The runner renders the candidate's wrapper with `agents_sync.render` from a copy of its source renamed to a neutral name that is not `agent-chanchi-*` (`worker`, launched as `--agent worker`, so `chanchi agents sync` in a work directory never treats it as an orphan), with `scope: both` (so on claude the role is the agent's system prompt, never an `initialPrompt` that `claude -p` may skip) and `skills:` set to `[<item>]` in the with-skill arm and `[]` in the without-skill arm, and copies the skill directory only into the with-skill arm (`.claude/skills/` for claude, `.agents/skills/` for agy). The orchestrator preloads five skills; without this, each arm would measure the others too. S1 verifies on claude whether a main-session `--agent` wrapper preloads its `skills:`; if it does not, the with-skill arm relies on the installed skill being discovered (what `triggers.md` measures) and the plan records it | The arms must differ only in the evaluated skill |
| D4 | **Global copies.** Global copies of every chanchi skill exist today in `~/.claude/skills/` and `~/.agents/skills/`. The runner runs each harness with `HOME` set to a temporary directory that holds only the credential files S1 found necessary, or refuses that harness with an error naming the global copy (design, *One run*, step 2). Permissions: every claude run of the runner (candidate, trigger) uses `--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob Edit Write Skill"` and `--` before the prompt (the form `harnesses.launch` emits for a writing profile since change `launch-permissions`, merged on `main`, plus `Skill`; never `--dangerously-skip-permissions`: AGENTS.md allows it only in another terminal pane) and `--add-dir` for the scratch `SYNC` (D20); agy with `--dangerously-skip-permissions` | The baseline arm would otherwise load the skill anyway |
| D5 | **Run count, caching and adaptive repeat (amended Rev 5).** Default `--arm auto` and `--runs 1`. Regression cases run only in the `with` arm and are code-graded only (never judged). Capability cases run in `with`, and in `without` only when `evals/ledger.tsv` has no `baseline` `without` row matching `(item, candidate, cases_sha)` (or when `--arm both` / `--arm without` is forced). Triggers run only when `evals/ledger.tsv` has no `triggers` row matching `(item, candidate, triggers_sha)` (or when `--triggers` is forced; `--no-triggers` skips them). **Adaptive repeat:** during a full measurement with `--runs < 3`, after run 1 of each `with`-arm case, run 2 confirming runs (total 3, per-case median) if (a) it is a regression case that failed run 1, OR (b) the previous `baseline`/`kept` `with` row records a score for that case in `cases=` and run 1's rounded score differs from it. Neither `claude` nor `agy` CLI supports `--max-turns` (verified locally 2026-11-23); default `--timeout` is lowered from `1800`s to `300`s. The runner prints `{candidate, judge, trigger, total, max_total}` (`max_total` being the upper bound if every `with` case triggers adaptive repeat) and refuses `total > 30` without `--yes` | Cuts routine skill changes to 2–3 runs and first baselines to 7–9 runs while still confirming every claimed lift or regression across 3 runs |
| D6 | **Blinding (adapts *One run*, step 1).** The work directory's path is `<tmp>/work-<8 hex>`; `prompt.md` never contains a blinded word (`eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`, `benchmark`, `candidate`, `arena`, as a word or a word prefix, any case). `setup.sh` and the files it creates may hold a blinded word only when it is listed in the eval's `blind_allow`, because the domain needs it (a repository has `tests/`; a report quotes `pytest`). `tests/test_evals.py` checks both. The evaluated skill and the candidate's wrapper are exempt: they are the subject (the session-audit skill ships `references/rubric.md`), and the runner's own path check skips them | The skills under eval work on repositories that contain tests; the subject cannot be blind |
| D7 | **Grading and gated judge (amended Rev 5).** `grade.py <workdir>` (run with `python -I`) prints one JSON line per criterion `{"criterion": "<id>", "pass": true|false, "detail": "<text>"}`. Regression cases are code-graded only (`judge = None`). On capability cases with `rubric.md`, `grade.py` runs first: if every code criterion passes (`all(c["pass"] for c in code)`), `agent-chanchi-judge` runs and returns, as the last fenced `json` block of its final message, `{"criteria": [{"n": 1, "verdict": "PASS"|"FAIL"|"N/A", "critique": "<quote and reason>"}]}`, giving `score = passed_applicable / total_applicable` (`N/A` excluded; passes when every applicable criterion passes; an unparsable judge answer is retried once). If any code criterion fails, the judge is skipped (`judge = None`, `judge_skipped = "code_failed"`), `passed = False`, and `score = passed_code / (len(code) + len(rubric_criteria))` — guaranteeing strict monotonicity so a code-failed run always scores strictly lower than any code-passed run | Code first, judge only when code passes on capability cases; avoids score inversion |
| D8 | **Pairwise judging.** This phase judges each output alone against its rubric, so the both-orders rule (design, *One run*, step 5) does not apply yet; the runner has no pairwise mode | No comparison of two outputs is needed for the signal |
| D9 | **Ledger (amended Rev 5).** Exact same 15 columns (`LEDGER_COLUMNS`). One row per executed arm (`with`, `without`, `triggers`): `runs` is the total candidate (or trigger) runs executed in that arm; `median_pass` is the median of per-case medians across the arm's capability cases (weighting every capability case equally even when one case repeated to 3 runs; for `triggers`, share of prompts with expected outcome). `note` carries semicolon-separated `key=value` tokens: `with` row `regression=<passed>/<runs>;cases=<c1>:<score1>,<c2>:<score2>` (ordered by `cfg.cases`, two decimals per case median); `without` row `cases_sha=<12-hex>;cases=<c1>:<score1>,...`; `triggers` row `triggers=<passed>/<total>;triggers_sha=<12-hex>`. Hash definitions (first 12 hex of SHA-256 over canonical JSON): `cases_sha` hashes `(candidate, judge_or_null, sorted capability case names, sorted [rel_path, sha256] of every file in each capability case folder plus rubric.md if present)` — excluding regression cases, `triggers.md`, `calibration.tsv` and `skills/<item>`; `triggers_sha` hashes `({harness, model, effort}, skill frontmatter description, sha256 of triggers.md)`. Any full measurement (`--cases` absent, `--no-ledger` absent, `--runs >= 1`) writes rows for the arms it executed. `id`, `date`, `before`, `after`, `delta`, `verdict` (`baseline`, `kept`, `reverted`) and `item_sha` keep their existing rules. Current `with` row: newest `baseline` or `kept` `with` row matching `item_sha`; compared against the newest `baseline` `without` row matching `(item, candidate, cases_sha)` | Keeps the 15-column schema unchanged, makes caching and adaptive repeat self-contained in git, and prevents weighting distortion under adaptive runs |
| D10 | **`item_sha` and the gate.** `scripts/run_evals.py` computes the tree hash of the item directory from the working tree, with git's tree algorithm applied recursively: blobs `100644` (or `100755` when executable), subdirectories as `40000` trees, entries in git's order (a directory sorts as its name plus `/`), over the files git tracks there plus staged additions. `tree_hash(path)` itself is pure; the runner's CLI (not the function) refuses to write a ledger row while the item directory has unstaged or untracked changes, so a hill-climb edit is staged (`git add skills/<item>`) before its measurement. `tests/test_evals.py` imports the function and fails when an evaluated item's current hash has no `kept` or `baseline` row, with the message: `<item> changed (tree <sha>) and has no kept or baseline row in evals/ledger.tsv. Run: uv run python scripts/run_evals.py <item>, then commit the row.` A unit test compares the function with `git rev-parse HEAD:<dir>` on a committed fixture that holds a nested `references/` folder and an executable file | The design's gate rule; the hook runs before the merge commit exists |
| D11 | **Every new skill has an eval** (the item-authoring rule, turned into a check): `tests/test_evals.py` fails when a skill in `skills/` has no eval directory with at least one case, except a `GRANDFATHERED` set in the test. S2 starts it with all seven current skills, so the check passes from S2 on and fails for any skill added later; S4 removes `skill-chanchi-session-audit` and `skill-chanchi-lessons`, S5 removes `skill-chanchi-item-authoring` and `skill-chanchi-item-adoption`, leaving the skills created before phase 2 and not evaluated now (`skill-chanchi-audit-rounds`, `skill-chanchi-model-selection`, `skill-chanchi-verify`). The message names the skill and the folder to create | Rule or check: a check can enforce it; the gate never goes red between sessions |
| D12 | **Judge agent.** `agents/agent-chanchi-judge/AGENT.md`: `scope: both` (agy and opencode need a main-capable wrapper for `--agent`; every CLI-launched chanchi agent uses `both`), `profile: read-only`, `install: repo`, `skills: []`. Body verbatim in Task S2. It reads the rubric, the output and the transcript from files in its own work directory and prints its verdict; it never sees the skill or the case's grader | A read-only judge cannot change what it grades |
| D13 | **Run artifacts** (work directories, transcripts, end states, judge answers) are kept under `${CHANCHI_EVALS_DIR:-~/.local/share/chanchi/evals}/<item>/<run id>/`, never in this repository; they hold temporary paths and the candidate's free text | User results stay out of the repository |
| D14 | **Calibration (amended Rev 5).** Calibrated means `total >= 6` and `agree >= total - 1` (≥ 5/6 for 6 samples; also accepts 10-sample sheets at ≥ 9/10). `run_evals.py <item> --calibration-sheet [--samples 6] [--collect] [--dry-run] [--yes]` builds `<artifacts>/<item>/calibration-sheet.md` (default 6 samples, minimum 6) from non-`N/A` judged capability runs of the latest baseline plus any saved runs in `<artifacts>/<item>/calibration-runs/` matching `cases_sha`. With `--collect`, if fewer than `samples` eligible outputs exist, the runner runs only the missing capability runs (alternating `without` and `with` to get both PASS and FAIL examples, invoking the judge even when code graders fail, saved under `<artifacts>/<item>/calibration-runs/`, never mutating `evals/ledger.tsv` or baseline scores; honors `--dry-run` and `> 30` `--yes` refusal; allows up to 2 fallback runs if a run yields all-`N/A`, else errors). Without `--collect`, insufficient eligible samples error with the hint to pass `--collect`. Sheet format, owner labeling, blinding (load events stripped + skill name redacted) and `--calibrate <sheet>` writing `calibration.tsv` stay as before. If agreement falls short, the orchestrator may reword the rubric once (before any hill climb), run `run_evals.py <item> --rejudge` (re-judges the runs in `calibration-map.json` plus any code-passed judged capability runs of the latest uncommitted baseline, deduplicated; updates uncommitted baseline `with`/`without` rows from code-passed baseline runs only, never from code-failed calibration samples; refuses if baseline rows are already committed), and re-run `--calibrate <sheet>` on the owner's existing labels | Keeps one-time calibration working with 1-run/case baselines and 1+1 cases while keeping routine eval cost low and preventing ledger distortion |
| D15 | **Signal report (amended Rev 5).** `run_evals.py --signal` prints, per evaluated item, conditions 1–3 as JSON from the current rows of `ledger.tsv` (D9) and `calibration.tsv`; an eval without `rubric.md` reports `judge: "none"`. Condition 1: `len(cal_rows) >= 6 and agree >= len(cal_rows) - 1`. Condition 2: `passed == runs and runs >= 1` (`1/1` or `3/3`). Condition 3: `with > without` against the matching `(candidate, cases_sha)` `without` row. Condition 4 runs `chanchi lesson export --all --status pending --limit 1000` (operational database, every project and the global lessons) and lists every lesson with `occurrences` ≥ 2 whose `target_kind` is not `tool`, `hook` or `permission`; it is `true` only when that list is empty, otherwise the orchestrator decides each listed lesson with the owner (whether a check is possible is a judgment) | One command proves the phase; aligned with Rev 5 thresholds |
| D16 | **Scope of the signal.** The signal covers the design's three skills. `eval-chanchi-item-adoption` is code-graded only (no rubric, no judge): it needs its baseline row like every evaluated item, and its own regression case must pass 100% of executed runs (`1/1` or `3/3`), but it is not part of the phase signal | The design names three first items; the backlog item needs an eval, not a phase gate |
| D17 | **Hill climb (amended Rev 5).** When a skill's capability median does not beat the cached `without` arm, or a regression case fails, the orchestrator writes one hypothesis; an executor session makes that one change to the skill; the orchestrator runs `run_evals.py <item> --hypothesis "<text>"` (allowed with default `--arm auto` or `--arm with`; refuses `--arm without`/`both` and refuses if no matching `without` baseline exists). Under `--arm auto`, `without` is reused and `triggers` run only if `description` changed (`triggers_sha`). Adaptive repeat (D5) confirms any case whose run-1 score differs from the previous `with` row across 3 runs before the verdict is written. Verdict compares regression **pass rate** (`reg_rate = reg_passed / reg_runs`, not raw passed count, so `1/1` vs `3/3` is never misread as a drop): `kept` when `reg_runs > 0`, `reg_rate >= prev_reg_rate` (100% once healthy) and (`median > before` or `reg_rate > prev_reg_rate`), else `reverted`; on `reverted` the orchestrator reverts the change. Ceiling handling, frozen harness, skill-change audit (`skill-chanchi-audit-rounds`), `chanchi recommend` and exploration budget recount stay as before | Prevents false drops between 1-run and 3-run regression counts; confirms every claimed lift across 3 runs while keeping unchanged cases at 1 run |
| D18 | **Merge order (amended Rev 5).** S1 to S3 and S7 merge to `main`. S4 and S5 add eval directories, which turn the ledger check red until baseline rows exist, so **never merge `main` into `feat/mvp2-s4` or `feat/mvp2-s5`** (`pre-merge-commit` runs `scripts/check` and blocks merges while the ledger check is red). Always **rebase** `feat/mvp2-s4` and `feat/mvp2-s5` onto `main`, run baselines and calibration on each branch, commit the ledger rows and `calibration.tsv` there, and merge to `main` with `--no-ff` once the gate is green. S4 merges first; S5 is rebased on it (both edit `GRANDFATHERED`) | Fixes the Rev 4 bug recorded in the handoff; `main` never goes red |
| D19 | **Eval files and existing checks (adapts check 1 and check 6).** `pyproject.toml` gains `"evals/*" = ["T20"]` under ruff's per-file ignores (graders print their verdict lines). `tests/test_items.py::test_references_resolve` skips `evals/*/cases/**` and `evals/*/triggers.md`: prompts there may name planned or fictional items; `eval.toml` and `rubric.md` stay checked. Prompts avoid fictional `<item>-chanchi-*` names anyway | A case's prompt is data the candidate reads, not an operational reference |
| D20 | **Scratch `SYNC`.** The runner creates `<tmp>/sync-<8 hex>` next to the work directory and passes `CHANCHI_SYNC` to `setup.sh`, the candidate (with `--add-dir` on claude and agy) and `grade.py`; without it `chanchi` falls back to the main checkout's `SYNC` (`src/chanchi/sync.py`) | Item adoption writes proposals under `SYNC`; the real one must never be touched |
| D21 | **Lesson review with a check (the design's "can a check enforce it?").** `chanchi lesson review` cannot change another conversation's `target_kind` (`lessons.py`: `modify` is author-only, `review` is never the author). So the reviewer records a replacement lesson whose `target_kind` is `tool`, `hook` or `permission`, whose proposal names the check and whose `replaces` lists the original (with `--force-new` if `lesson add` reports it as a duplicate), then reviews the original as `duplicate --of <new id>`, which moves its occurrences. The replacement is reviewed later by another conversation | Uses only existing commands; nothing approves a prose rule a check can enforce |
| D22 | **Runner contract** (S2 writes it into `README.md`'s evals section and pins it in `tests/test_evals.py`; S3, S4 and S5 rely on it). Work directory `W` = `<tmp>/work-<8 hex>`, the current directory of `setup.sh` and of the candidate; `CHANCHI_DB=W/.state/chanchi.db`; `CHANCHI_SYNC=<tmp>/sync-<8 hex>` (D20); `PATH` starts with a folder holding the `chanchi` shim. `bash setup.sh` runs with that environment and may create anything under `W` and the scratch `SYNC` (a project repository, if any, is `W` itself). After setup and before the candidate, the runner adds its own paths (`.state/`, the injected wrapper, the injected skill folder) to `W/.git/info/exclude` when `W/.git` exists, so `W` starts git-clean in both arms; graders read project changes with `git status --porcelain` and `git ls-files --cached --others --exclude-standard` (new untracked files count; the candidate never commits), never by listing `W`. After the candidate, `python -I grade.py W` runs with the same environment plus `FINAL_MESSAGE_FILE` (the candidate's final message as text) and prints D7's lines | Graders and setups are written before the runner exists |
| D23 | **Case budget and phase-2 trimming (new Rev 5, owner decisions 2A & 3A).** Every new skill eval starts with **1 regression + 1 capability** case; add cases only when a real failure shows a gap. Trim the three already-written phase-2 evals to 1+1 (S8) and re-run all four baselines cleanly under Revision 5 so `evals/ledger.tsv` is uniform: `eval-chanchi-session-audit` keeps `stop-plan-gap` (reg) + `false-claim` (cap), drops `clean-complete`, `scope-and-choices`; `eval-chanchi-lessons` keeps `record-failure` (reg) + `review-check-first` (cap), drops `repeat-existing`, `nothing-wrong`; `eval-chanchi-item-authoring` keeps `new-skill` (reg) + `new-hook` (cap), drops `new-agent`, `agent-without-model`; `eval-chanchi-item-adoption` stays `propose-new` (reg) + `retired-entry` (cap) | Cuts routine skill changes to 2–3 runs and aligns phase-2 evals with the protocol future projects will adopt |

## Sessions

| Session | Agent | Task type / complexity | chanchi recommend (2026-11-23) · chosen | Blocks |
|---|---|---|---|---|
| S1 | `agent-chanchi-researcher` | integration / medium | recommended `agy:gemini-4-hydrogen-medium:medium` (global level, low confidence) · chosen `claude:sonnet:high` · reason: `claude:sonnet:high` has data at `task_type+complexity` (n 7, clean 1.0) and S1 blocks S3 | S3 |
| S2 | `agent-chanchi-executor` | tests / medium | recommended `agy:gemini-4-hydrogen-medium:medium` (global, low) · chosen the same | S4, S5 |
| S3 | `agent-chanchi-executor` | integration / high | recommended `agy:gemini-4-hydrogen-medium:medium` (global, low) · chosen `claude:sonnet:high` · reason: at high complexity global data is weak; `claude:sonnet:high` has `task_type` data (n 7, clean 1.0) | gate |
| S4 | `agent-chanchi-executor` | tests / medium | recommended `agy:gemini-4-hydrogen-medium:medium` (global, low) · chosen the same | gate |
| S5 | `agent-chanchi-executor` | tests / medium | recommended `agy:gemini-4-hydrogen-medium:medium` · chosen `agy:gemini-4-hydrogen-high:high` · explore: `agy:gemini-4-hydrogen-high:high` (5 sessions, budget 1; S5 blocks nothing; started with `--tags agent-chanchi-executor,explore`) | gate |
| S6 | `agent-chanchi-executor` | tests / medium | completed prior to Rev 5 (replaced `eval-chanchi-item-authoring` capability cases on `feat/mvp2-s5`) | S8 |
| S7 | `agent-chanchi-executor` | integration / medium | planned after Rev 5 audit acceptance with `chanchi recommend` (updates `scripts/run_evals.py`, `tests/test_run_evals.py`, `README.md`) | S8, G1b |
| S8 | `agent-chanchi-executor` | tests / low | planned after S7 merges with `chanchi recommend` (rebases `feat/mvp2-s4` and `feat/mvp2-s5` onto `main`, trims cases per D23, updates `eval.toml` per D2, clears old uncommitted ledger rows) | G1b, G2 |

S4 and S5 branched from `main` after S2 merged and wrote to the D22 contract; the orchestrator
**rebases** each branch onto `main` (never merges `main` into them, D18) after S7 merges.
Hill-climb sessions (D17), if any, are planned at the gate with `chanchi recommend` (task type
`docs`, complexity `low`).

### Task S1 (researcher): harness facts for the runner

Write `<scratch>/s1-report.md`; mark every claim VERIFIED (with the command and its output) or
UNVERIFIED. At most 14 headless runs, each with a trivial prompt.

- [ ] For `claude` 2.1.330 and `agy` 1.5.15: the minimal files a temporary `HOME` needs for a
  headless run to authenticate (macOS), and proof that a skill in `~/.claude/skills/` or
  `~/.agents/skills/` is not visible under that `HOME` while a skill in the work directory's
  `.claude/skills/` or `.agents/skills/` is.
- [ ] Claude permissions: with `--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob
  Edit Write Skill"` (verified for Bash on 2026-11-23), one run that runs a command, writes a file
  inside the work directory and one inside an `--add-dir` folder, and loads a skill with the `Skill`
  tool, all without a prompt.
- [ ] Claude agent wrappers in `claude -p --agent`: with a `scope: both` wrapper (body as system
  prompt), does the body apply, and does a non-empty `skills:` list preload the skill in a main
  session (or only in subagents)? Use a tiny probe agent and skill, not chanchi's.
- [ ] agy in a fresh temporary folder under the temporary `HOME`: does it load
  `.agents/agents/<name>/agent.md` without a trust step? If not, which file in the temporary `HOME`
  marks the folder trusted, or whether the agent's body passed in the prompt is the only way.
- [ ] In each harness's `stream-json` output: the event that shows a skill was loaded (claude:
  `Skill` tool use or a read of `SKILL.md`; agy: the event for reading `SKILL.md` or preloading),
  and where the final message is. Paste one redacted event of each kind.
- [ ] Confirm `agy --model gemini-4-neon --effort high` (D2) in a headless run.

### Task S2: judge agent, eval layout checks, ledger check

Files: `agents/agent-chanchi-judge/AGENT.md` and its generated wrappers (`uv run chanchi agents
sync`), `evals/ledger.tsv` (header row only), `tests/test_evals.py`, a minimal
`scripts/run_evals.py` holding only `tree_hash(path) -> str` and `read_ledger(path)` (S3 extends
it), `tests/test_items.py` (D19, and a `name` check for eval directories if D1 needs one),
`pyproject.toml` (D19), `README.md` (an evals section pointing to the design that states the D22
runner contract and the D9 ledger semantics; it names no `eval-chanchi-*` directory, since none
exists yet and `test_items.py` checks `README.md`), with a test that the README section lists
every D22 name (`W`, `CHANCHI_DB`, `CHANCHI_SYNC`, `FINAL_MESSAGE_FILE`, `grade.py`).

- [ ] Agent body, verbatim:

```markdown
# Judge

You grade one output against a rubric and print one verdict. You never see the skill or the code
graders, and you never edit a file.

1. Read `criteria.md`, `output.md` (the final message and end state) and `transcript.jsonl` in
   your working directory.
2. For each numbered criterion decide PASS, FAIL or N/A (the criterion does not apply to this
   case). Quote the output or transcript in one or two sentences of critique for each.
3. Judge only what the criteria ask; do not reward length, tone or confidence.
4. End your final message with one fenced `json` block:
   `{"criteria": [{"n": 1, "verdict": "PASS", "critique": "..."}]}`.
5. If something went wrong, say so in your message; do not record it in chanchi.
```

- [ ] `tests/test_evals.py`: (a) every `evals/eval-chanchi-*` has `eval.toml` with the D1 keys,
  `name` equal to the directory, `item` an existing skill, every listed case present with
  `prompt.md`, `setup.sh` and `grade.py`, at least one regression case, `triggers.md` with both
  headings, and `[judge]` present exactly when `rubric.md` is, with a judge family different from
  the candidate's (`chanchi.taxonomy.family_for`, failing closed on `None`; the template database
  holds no model catalog); (b) the blinding rule (D6), checked statically on the text of
  `prompt.md`, `setup.sh` (heredocs included) and any fixture file in the case folder, never by
  running `setup.sh`; (c) the D11 check with `GRANDFATHERED` holding all seven current skills; (d) the D10 ledger check; (e) `tree_hash` equals `git rev-parse
  HEAD:<dir>` on a fixture committed in a temporary repository. Each failure message states the
  rule and the fix. Seed one violation per check in a temporary copy and show it red.
- [ ] Verify: `uv run pytest -q tests/test_evals.py tests/test_items.py tests/test_agents_sync.py`,
  `uv run chanchi agents sync --check`, `scripts/check`.

### Task S3: the runner

Files: `scripts/run_evals.py`, `tests/test_run_evals.py`. Depends on S1's report (the brief
pastes its VERIFIED facts) and S2.

- [ ] CLI: `run_evals.py <item> [--arm with|without|both] [--cases <c,...>] [--runs 3] [--yes]
  [--dry-run] [--no-ledger] [--hypothesis <text>] [--change <ref>]`, `run_evals.py <item>
  --calibration-sheet`, `run_evals.py <item> --calibrate <sheet>`, `run_evals.py <item> --rejudge`
  (no argument, D14), `run_evals.py --signal`.
- [ ] One run, per the design and D3-D7: neutral work directory, `CHANCHI_DB` inside it, the
  scratch `SYNC` (D20), `PATH` with a `chanchi` shim (`uv run --project <repo> chanchi`), `bash
  setup.sh`, the candidate
  headless with `stream-json` captured, `python -I grade.py <workdir>`, then the judge in its own
  directory with `criteria.md` (the rubric's numbered criteria only), `output.md`,
  `transcript.jsonl` and the judge wrapper. Triggers (only with `--arm both`): each `triggers.md` prompt once, with the
  skill installed, no agent and D4's permission flags; pass when the load event (S1) matches the
  heading.
- [ ] Planning and refusal (D5): print `{candidate, judge, trigger, total}` before running;
  refuse above 30 without `--yes`; `--dry-run` prints and exits.
- [ ] Isolation (D4): refuse a harness with a global copy it cannot hide, naming the copy.
- [ ] Ledger rows (D9) appended to `evals/ledger.tsv` only for full measurements; artifacts per
  D13; calibration and re-judging per D14; signal per D15. If S1 found that agy needs a trust step
  the runner cannot provide in a temporary folder, the judge's role body goes into its prompt
  instead of `--agent` (say which in the report).
- [ ] Tests with a fake harness: a script on `PATH` named `claude` / `agy` that writes a canned
  `stream-json` transcript and end state. Cover: arm wiring (skill present only in `with`, wrapper
  `skills:` and `scope: both`), blinded paths, `CHANCHI_SYNC` reaching setup, candidate and grader,
  the 30-run refusal, ledger math (median, delta, kept/reverted, regression note, ids), no row for
  partial runs or `--no-ledger`, the unstaged-changes refusal, judge JSON parsing with one retry,
  calibration agreement and all-`N/A` exclusion, `--rejudge` then `--calibrate`, the stripped judge
  transcript, the neutral wrapper name and `W` git-clean after injection, the current-row rule, and
  the signal report with a registered project and a global pending lesson.
- [ ] Verify: `uv run pytest -q tests/test_run_evals.py tests/test_evals.py`, `uv run python
  scripts/run_evals.py skill-chanchi-lessons --dry-run` on a fixture eval, `scripts/check`.

### Task S4: evals for session-audit and lessons, and the lesson review question

Files: `evals/eval-chanchi-session-audit/**`, `evals/eval-chanchi-lessons/**`,
`skills/skill-chanchi-lessons/SKILL.md`, `skills/skill-chanchi-lessons/references/example.md`,
`tests/test_evals.py` (`GRANDFATHERED`).

- [ ] Lessons skill: move the `### Example` block into `references/example.md` and leave the line
  `Example: [references/example.md](references/example.md).` In *Review*, step 2, add as the
  first bullet, verbatim:
  `- If the lesson has 2 or more occurrences, ask first: can a check (a test, a ruff rule, a CLI
  check, a hook or a permission) enforce it? If yes and its \`target_kind\` is not \`tool\`,
  \`hook\` or \`permission\`, do not approve it: record a replacement lesson with that
  \`target_kind\`, a proposal naming the check and \`replaces\` listing it (add \`--force-new\` if
  it is reported as a duplicate), then review the original as \`duplicate --of <new id>\`. Never
  add its rule as prose.`
  (D21; the file must stay ≤ 150 lines: `tests/test_skills_content.py`.) Remove
  `skill-chanchi-session-audit` and `skill-chanchi-lessons` from `GRANDFATHERED` (D11).
- [ ] `eval-chanchi-session-audit` (candidate orchestrator). Every case's setup registers a git
  repository, adds the models it names (`chanchi models add`, the fresh database has none), opens a
  change and starts session S1 with chanchi, and writes the executor's report
  to `handoff.md`; the prompt says only that S1 handed off and asks to process it.
  - `stop-plan-gap` (regression): the report stops at task 3 because the design does not define a
    sort order. Graded: S1 reported `STOPPED`; one `plan_gap` (blocking) on the change (session
    optional, as the skill records it) and one `correct_stop` on S1, both with non-empty
    evidence; no `accepted` verdict.
  - `clean-complete` (regression): the report claims `sh check.sh` passes, and it does. Graded:
    `COMPLETE`, verdict `accepted`, no incident.
  - `false-claim` (capability): the report claims `sh check.sh` passes, and it fails. Graded: a
    `false_claim` incident whose evidence names the command; verdict not `accepted`.
  - `scope-and-choices` (capability): the diff touches a file outside the brief's list, and the
    report has a "choices the plan left open" section. Graded: one `scope_drift` and one
    `plan_delegated_decision`.
  - `rubric.md`: (1) each incident's evidence names a command and its output, a path, or a quote;
    (2) one incident per distinct fault, no duplicate for one symptom; (3) the final message
    states the verdict and its reason without facts absent from the work directory.
  - `triggers.md`: must load "S2 of change demo-sort just handed off; record it and give your
    verdict." and "The executor stopped at task 4; log what happened."; must not load "Rename the
    function parse_row to parse_line in src/rows.py." and "Explain what a git worktree is."
- [ ] `eval-chanchi-lessons` (candidate orchestrator; a `notes.md` holds what happened; the
  setup registers the project with `planner` as writer):
  - `record-failure` (regression): notes describe a report that claimed passing checks never run,
    because the brief did not ask for the command. Graded: exactly one pending lesson, every
    required field non-blank, valid enums, `--as planner`, author not `human`.
  - `repeat-existing` (regression): the setup records a pending lesson for the same failure from
    another conversation. Graded: that lesson has 2 occurrences and no new lesson exists.
  - `nothing-wrong` (capability): notes describe a run where every step passed. Graded: no lesson.
  - `review-check-first` (capability): a maintenance conversation; the setup records, from another
    conversation, a pending lesson with 2 occurrences whose rule ("never commit a file over 1 MB")
    is proposed as a role line. Graded: the original is not `approved`; a new lesson exists whose
    `replaces` lists it and whose `target_kind` is `tool`, `hook` or `permission`; the original is
    `duplicate` of that new lesson (D21).
  - `rubric.md`: (1) the cause says why the failure happened, not what was observed; (2) the
    general rule holds for any case of this kind; (3) the target names one place where the fix
    belongs; (4) when a check can enforce the rule, the decision or proposal routes it to a check.
  - `triggers.md`: must load "At the end of this conversation, note what went wrong with the
    executor's report format." and "Review the pending lessons."; must not load "Fix the failing
    check in src/db.py." and "Summarize the last three commits."
- [ ] Verify: `uv run pytest -q tests/test_evals.py tests/test_skills_content.py`, each
  `grade.py` run by hand against a hand-made passing and failing end state (paste both outputs),
  `scripts/check` (the ledger check is expected red for the two new evals only, D18; report it).

### Task S5: evals for item-authoring and item-adoption, and the authoring rule

Files: `evals/eval-chanchi-item-authoring/**`, `evals/eval-chanchi-item-adoption/**`,
`skills/skill-chanchi-item-authoring/SKILL.md`, `tests/test_evals.py` (remove
`skill-chanchi-item-authoring` and `skill-chanchi-item-adoption` from `GRANDFATHERED`, D11).

- [ ] Authoring skill: the `eval` row of the layout table becomes, verbatim:
  `| eval | \`evals/eval-chanchi-<n>/\`: \`eval.toml\`, \`cases/<case>/\` (\`prompt.md\`,
  \`setup.sh\`, \`grade.py\`), optional \`rubric.md\`, \`triggers.md\` | every new skill ships with
  one (\`tests/test_evals.py\`); after any change to an evaluated skill run \`uv run python
  scripts/run_evals.py <skill>\` and commit the ledger row |`
- [ ] `eval-chanchi-item-authoring` (candidate executor; the setup builds a small repository with
  `agents/`, `skills/`, `evals/`, `tests/` and a standard-library naming check
  `tests/check_items.py` run as `python3 tests/check_items.py`; pytest is not available there):
  - `new-skill` (regression): "add a skill that tells agents how to tag a release". Graded: a
    `skills/skill-chanchi-<n>/SKILL.md` whose frontmatter `name` equals its directory, ≤ 300
    lines, and an `evals/eval-chanchi-<n>/` with at least one case.
  - `new-agent` (regression): "add a read-only agent that summarizes changelogs". Graded: the
    source has `name`, `description`, `scope`, `profile: read-only`, `skills`, no model name, and
    `chanchi agents sync --check` exits 0 in `W` itself (the runner's `worker` wrapper does not
    match `agent-chanchi-*`, D3), with the candidate's new, untracked files present.
  - `rename-skill` (capability): rename one skill of the small repository to a name the prompt
    gives (both names exist only in the setup, never in this repository). Graded: no operational
    file names the old name, and `python3 tests/check_items.py` exits 0.
  - `rule-or-check` (capability): "agents keep leaving SKILL.md files without a final newline;
    make sure it stops". Graded: a file under `tests/` changed and no line was added to
    `AGENTS.md`.
  - `rubric.md`: (1) an invariant was made a check and a judgment was left as text; (2) a new
    check's failure message states the rule and the fix; (3) the final message names every file
    created or changed.
  - `triggers.md`: must load "Create an agent that audits changelogs." and "Rename the release
    skill to a clearer name."; must not load "Fix the typo in README.md." and
    "List the open branches."
- [ ] `eval-chanchi-item-adoption` (candidate executor; code-graded, no rubric, D16; the setup
  builds a scratch `SYNC` with one published global skill, a registered project with an
  overlapping skill, and scans it):
  - `propose-new` (regression): the prompt asks to check for global items to adopt and to stop
    before asking the owner; the scratch `SYNC` is the runner's (D20). Graded: one proposal file at
    `<SYNC>/reviews/<item>/<version>/adoption-<slug>.md` naming one of the four decisions and
    holding a comparison table; no file in the project changed; no `item_decisions` row.
  - `retired-entry` (capability): the project's adopted item was retired. Graded: the proposal's
    decision is `keep` or `deprecate`.
  - `triggers.md`: must load "Are there global items this project should adopt?" and "chanchi
    items inbox shows two entries; handle them."; must not load "Add a unit to the parser." and
    "Bump the version in pyproject.toml."
- [ ] Verify as in S4.

### Task S7: cheaper eval protocol in runner, tests and README (Rev 5)

Files: `scripts/run_evals.py`, `tests/test_run_evals.py`, `README.md` (`## Evals` section). Runs on
a branch from `main` after Revision 5 audit acceptance.

- [ ] Implement D5, D7, D9, D14, D15 and D17 in `scripts/run_evals.py`:
  - `--arm` choices `("auto", "with", "without", "both")`, default `"auto"`; `--runs` default `1`;
    `--triggers` / `--no-triggers`; `--timeout` default `300`.
  - Compute `cases_sha` and `triggers_sha` (D9) and store/read them in `note` tokens alongside
    `regression=<p>/<r>` and `cases=<c>:<score>,...`. Under `--arm auto`, skip `without` when a
    matching `baseline` `without` row exists and skip `triggers` when a matching `triggers` row
    exists.
  - Adaptive repeat (D5): on `with`-arm full runs with `--runs < 3`, confirm a case to 3 runs when
    a regression fails run 1 or a case's run-1 rounded score differs from the previous `with` row's
    `cases=` entry. Aggregate per-case medians before arm median (D9). Print `max_total` in plan.
  - Gated judge (D7): never judge regression cases; on capability cases, skip judge if any code
    criterion fails and score `passed_code / (len(code) + len(rubric_criteria))`.
  - Calibration (D14): `--calibration-sheet [--samples 6] [--collect] [--dry-run] [--yes]`,
    calibration runs saved in `<artifacts>/<item>/calibration-runs/` without mutating ledger rows,
    `--calibrate` threshold `total >= 6 and agree >= total - 1`, `--rejudge` deduplicated over
    `calibration-map.json` + code-passed baseline capability runs.
  - Hill-climb verdict (D17) compares regression pass rate (`reg_passed / reg_runs`) instead of raw
    passed counts; `--signal` (D15) uses `len(cal_rows) >= 6 and agree >= len(cal_rows) - 1` and
    matches `without` by `(candidate, cases_sha)`.
- [ ] Update `tests/test_run_evals.py` (fake harness only) to cover every new rule: `--arm auto`
  reusing `without` and skipping unchanged `triggers`, invalidation on `cases_sha` and
  `triggers_sha` change, adaptive repeat (1 run when unchanged, 3 runs when changed or regression
  fails), per-case median aggregation, gated judge + strict score monotonicity on code failure,
  `--calibration-sheet --collect` with 6 samples (5/6 pass, 4/6 fail) without mutating baseline
  ledger scores, `--rejudge` scope, and rate-based hill-climb regression verdict (`1/1` vs `3/3`).
- [ ] Update `README.md` (`## Evals` -> *Ledger semantics*) for Revision 5 while keeping every D22
  name checked by `tests/test_evals.py`.
- [ ] Verify: `uv run pytest -q tests/test_run_evals.py tests/test_evals.py`, `scripts/check`.

### Task S8: trim phase-2 evals to 1+1 and update models on S4/S5 branches (Rev 5)

Files on `feat/mvp2-s4` and `feat/mvp2-s5` (after each is rebased onto `main` containing S7, D18):
`evals/eval-chanchi-*/eval.toml`, `evals/eval-chanchi-*/cases/**`, `evals/ledger.tsv` (reset to
header so fresh Rev-5 baselines replace the uncommitted Rev-4 rows).

- [ ] Trim cases per D23 (`session-audit`: keep `stop-plan-gap`, `false-claim`; `lessons`: keep
  `record-failure`, `review-check-first`; `item-authoring`: keep `new-skill`, `new-hook`;
  `item-adoption`: keep `propose-new`, `retired-entry`).
- [ ] Update `[candidate]` in all four `eval.toml` files to `harness = "agy"`,
  `model = "claude-sonnet-5-5-low"`, `effort = "low"`, and `[judge]` in the three judged evals to
  `harness = "agy"`, `model = "gemini-4-hydrogen-high"`, `effort = "high"` (D2).
- [ ] Verify: `uv run pytest -q tests/test_evals.py tests/test_items.py tests/test_skills_content.py`
  (only the ledger check is expected red until G2 commits the fresh baseline rows, D18).

### Gate (orchestrator)

- [x] **G1** Merge S1–S3 after audit; initial smoke run done (pre-Rev 5).
- [ ] **G1b** Merge S7 after audit; run S8 after rebasing `feat/mvp2-s4` and `feat/mvp2-s5` onto
  `main` (never merge `main` into them, D18). Run one real smoke check on `feat/mvp2-s4` for the
  new D2 pair (`agy:claude-sonnet-5-5-low` candidate + `agy:gemini-4-hydrogen-high` judge: 1
  capability case + 1 must-load trigger with `--no-ledger --yes`, ~3 runs) to verify `agy`
  `claude-sonnet-5-5-low` execution, `preloadSkills`, and trigger `read_file` detection before any
  baseline.
- [ ] **G2** On `feat/mvp2-s4` and `feat/mvp2-s5` (rebased onto `main`, item directory staged,
  D10): `--dry-run`, then fresh baseline (`run_evals.py <item>`, default `--arm auto`, `--runs 1`)
  for each of the four evals (owner decision 3A). Expected: ~8 + ~8 + ~8 + ~7 = **~31 runs**
  total (vs ~133 under Rev 4). Judged baseline rows stay uncommitted until G3; `item-adoption`
  (no judge) commits at once.
- [ ] **G3** Calibration: run `run_evals.py <item> --calibration-sheet --collect` for each of the
  three judged skills (~8 runs each, **~24 runs** total one-time), hand the 6-sample sheets to the
  owner, then `--calibrate`. A rubric below 5/6 may be reworded once and re-judged with `--rejudge`
  (~6 judge runs); if `gemini-4-hydrogen-high` still falls short after one rubric rewording,
  escalate the judge to `agy:gemini-4-neon-high:high` (D2). Commit the ledger rows and
  `calibration.tsv` on `feat/mvp2-s4`, merge to `main` (`--no-ff`), rebase `feat/mvp2-s5` onto
  `main`, commit and merge.
- [ ] **G4** Hill climb (D17) for any skill whose capability median does not beat the cached
  `without` arm or whose regression case fails (expected 1–2 changes × 5–7 runs = **~10–15 runs**),
  within the 300-run total budget. Each kept skill change is audited (`skill-chanchi-audit-rounds`).
- [ ] **G5** `run_evals.py --signal` shows all four conditions for the three skills; record the
  output in `docs/designs/reviews/chanchi-agents-mvp/phase2-exit.md`; update the design's status
  line and reconcile any remaining plan-only adaptations (audited as a rule change); `chanchi change
  close chanchi-agents-phase2`.

## Verification plan (phase 2)

1. `scripts/check` green on `main` after every merge; each new check seeded red once (S2).
2. Runner behavior (including Rev 5 caching, adaptive repeat, gated judge and calibration
   collection) proven with the fake harness (S3, S7); one real smoke check per harness/model pair
   (G1, G1b).
3. `run_evals.py --signal` output in `phase2-exit.md` (G5); the ledger and calibration files are
   committed and re-checkable by anyone.

## Risks

| Risk | Mitigation |
|---|---|
| A harness cannot run under a temporary `HOME` (credentials in the keychain or elsewhere) | S1 verified both `claude` and `agy` under temporary `HOME`; the runner refuses any unisolated harness (D4) |
| `agy:claude-sonnet-5-5-low` fails or does not emit trigger `read_file` events on `agy` | G1b tests both a capability case and a must-load trigger in ~3 runs before baselines; fallback is owner decision (e.g., `claude:sonnet:medium` candidate at 2–3 runs/change) |
| The without-skill arm already does well (the agent body states much of the skill) | That is a measurement, not a failure: the hill climb targets the gap; if both arms sit at 1.0, stop and propose a harder capability case |
| The budget runs out before the signal holds | Running total in the gate record (~160 spent + ~67–90 remaining = ~227–250 of 300); stop and ask before 300 |
| The judge agrees below 5/6 after one rubric rewording | Escalate judge from `gemini-4-hydrogen-high` to `gemini-4-neon-high` (D2) once; if still below 5/6, stop and give the owner the disagreements |
| agy ignores workspace agents in a temporary folder | S1 verified `agy` loads `.agents/agents/<name>/agent.md` in temporary folders under `HOME` |
| A grader is wrong | Each grader is run against a hand-made passing and failing end state in S4/S5 and frozen before the loop |
