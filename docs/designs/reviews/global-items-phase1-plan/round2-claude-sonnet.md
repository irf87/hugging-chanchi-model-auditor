VERDICT: PASS

Round 2 audit, seat 1 (claude:sonnet), of `docs/superpowers/plans/2026-11-21-global-items-phase1.md`,
Revision 2 (`13cfa9a`). I re-checked my round-1 findings G1-G17 against the plan text, the round-1
consolidation, and `src/chanchi/` and `tests/`. I did not read other auditors' reports or the other
files in the private folder. I ran only scratch commands (a SQLite check of the recursive-CTE
seeding, `agy models`); chanchi ran against no database. The `chanchi recommend` numbers in the
session protocol are still UNVERIFIED (operational database not touched).

## 1. Re-check of my round-1 findings

| id | status | evidence |
|---|---|---|
| G1 bare `chanchi` in worktrees | RESOLVED | Global constraint "Run the worktree's code ... always call `uv run chanchi`"; Task 1 verification and the S2/S3/S4 FEATURE_MAP drives now say `uv run chanchi`. The bare calls left in Task 7 and Task 8 are orchestrator steps on the main checkout, which is where the editable install points. |
| G2 docs naming items before S5 | RESOLVED | Constraint "Names that do not exist yet": S1-S4 write `<agent>` in README/FEATURE_MAP/AGENTS.md; code and tests may use the strings (`tests/test_items.py` scans only docs, agents and skills); Task 3 Step 2 repeats it, Task 6 lets README name them. |
| G3 `agents link --user` default root | RESOLVED | D4: root defaults to `Path(__file__).resolve().parents[2]`, never the cwd; D3 and Task 5 store `root` in each manifest entry and remove or touch only entries of the same root; Step 1 tests "an entry of another root survives `link` and `--remove`". |
| G4 opencode read-only cannot write the report | PARTIAL | The auditor body now says "on opencode, write it with the shell ... the read-only profile denies the edit and write tools there" (the core defect is fixed). Not carried over: Task 7 never makes each harness write a file, so a failed write on one seat would still show only on the first real audit, and the Risks table has no opencode row. Minor now. |
| G5 S6 "nothing depends on it" | RESOLVED | Sessions row 8 now depends on "S5 merged (not S6)"; the protocol says S6 is waited for by "no session and no task". (See N1 for an ordering side effect.) |
| G6 Task 8 step 3 incoherent | RESOLVED | Step 2 builds a scratch `CHANCHI_SYNC` roster in history's order and says to stop and report on a missing binary, "never add `unavailable` rows that did not happen". |
| G7 `render` signature vs "tests stay green" | RESOLVED | `render_by_kind(source, header)` is new; `render(source)` keeps signature and path-keyed output as a wrapper through `REPO_TARGETS`; "Existing tests stay unchanged and green". `USER_HEADER` uses `{name}`. |
| G8 round-3 cap overwrote `quorum` | RESOLVED | `outcome()` rows are ordered, row 1 is quorum "whatever the round", and the cap applies "only when rows 2-4 gave `rework` or `fix`"; Step 1 adds "round 3 with one voter -> `escalated`/`quorum` (not `round_cap`)". |
| G9 `launch` interface | RESOLVED | One `harnesses.launch(key, *, agent, model, effort, prompt)`; claude omits `--effort` when `None`, opencode ignores effort, agy `split_agy_model` refuses `None` or a mismatched suffix; Task 3 calls the same function. The built-in roster satisfies it (both agy entries carry an effort). |
| G10 `sync_dir` injection and test hermeticity | RESOLVED | `sync_dir(env, *, repo_root)` and `roster(env, *, repo_root)` via `projects.main_worktree` (exists in `projects.py`; `subprocess` stays in `projects.py`, which `tests/test_no_network.py` requires); Task 3 tests set `CHANCHI_SYNC` to a scratch folder and inject `which`. |
| G11 Task 7 commands | RESOLVED | The three verified launch forms replace the nonexistent `opencode debug skill` / `agy skills`; `agy agents` and `opencode debug agents` are used; no `audit open`. `agy models` lists `gemini-4-hydrogen-medium`, so `--model gemini-4-hydrogen --effort medium` is a valid split. |
| G12 SQL vs Python family rule | RESOLVED | D7 now states the prefix rule; Task 1 Step 3 gives a recursive CTE that reduces each model to its last segment. I ran that CTE in SQLite: `openrouter/qwen/other` -> NULL, `deepseek/r1` -> NULL, `claude/gemini-4` -> google, `opencode-go/minimax-m3#thinking` -> minimax, `fable-5.1` -> anthropic, all equal to the `family_for` expectations in Step 1(a). |
| G13 counts not machine-readable | RESOLVED | D9 and Task 8's table fix every count; I checked round 2 against the seat reports (seat 2: 4 new major plus partial F6 major = 5, 1 new minor plus partial F10 = 2; seat 3: partial GI-02 blocking, 3 new major, 3 new plus partial GI-15/16/17 minor = 6) and round 3 (R3-01/R3-02 major, R3-03/R3-04 minor). Dissent severity comes from each auditor's report. |
| G14 `--change` without project, refusal codes | RESOLVED | D5: `missing_prerequisite` with a `--project` hint, `unknown_change` for a bad ref; Global constraints and Tasks 3-4 use `invalid_transition` for lifecycle refusals. The `models set` "nothing to update" hint is not mentioned, a nit an executor will handle. |
| G15 `OPERATIONAL_TABLES`, S3/S4 conflicts | RESOLVED | Task 1 Step 2 updates the hardcoded version tests (`005_add_probe.sql` becomes `006`; I confirmed these tests exist at `tests/test_db.py` lines 253-314) and adds the four tables; Sessions and Risks name `cli.py`, `FEATURE_MAP.md`, `README.md`. |
| G16 complexity labels | RESOLVED | S1 is `high` with a re-run recommendation and `claude:sonnet:high` chosen; S4 is `business-logic`. Numbers UNVERIFIED. |
| G17 second signal, lessons | PARTIAL | "Out of this plan" now covers both. It says "Lessons #1-#4 stay pending on purpose (owner's request)", but the request in `request.md` says #1 to #3 (see N2). Minor. |

## 2. New findings from Revision 2

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | minor | Task 8 step 5 vs Sessions row 8 | Task 8 now runs "after S5 merges (independent of S6)", but its last step closes the chanchi change `global-items-phase1`. S6 is a session of that change, and closed changes reject new sessions, so closing before S6 is started, reported and audited blocks recording it. | VERIFIED: `FEATURE_MAP.md` `change` Gotchas: "Closed changes reject new sessions"; plan lines 90, 481-482. | Move `chanchi change close` and `chanchi show` to after S6 is audited (or say Task 8 steps 1-4 are independent and step 5 waits for S6). |
| N2 | minor | "Out of this plan" paragraph | It attributes "lessons #1-#4 stay pending" to the owner's request; the request says #1 to #3. If a fourth lesson was recorded later, the attribution is wrong; if not, the number is wrong. | VERIFIED: `.claude/worktrees/research/plan-gi1/request.md` last line: "Lessons #1 to #3 stay pending on purpose". | Write "#1-#3 (owner's request) and any later lesson recorded by this work stay pending", or fix the number. |
| N3 | minor | Task 5 manifest ("`db_dir` ... created if missing") and Task 7 step 3 | `--check` is specified as writing nothing, but the manifest rule creates `db_dir` if missing, and Task 7 runs `--check` in a "writes nothing but its report" task. | VERIFIED: plan lines 352-353, 360, 446. | Say the folder is created only by a normal `link`, never by `--check` or `--remove` (a missing manifest means no owned entries). |
| N4 | minor | Task 5 `root` and D4 | The default root is `Path(__file__).resolve().parents[2]`, which is the worktree when chanchi runs through `uv run` in a worktree and the main checkout for the editable install. The same target paths then carry two different `root` values; the plan does not say whether an entry owned under another root at the same path is updated or treated as a conflict. | VERIFIED: plan D3/D4 and Task 5 manifest text; `uv tool` editable install points at the main checkout. | Normalize the root with `projects.main_worktree(...)` before storing and comparing it, or state that a path owned by another root is a `link_conflict`. |

No new blocking or major finding. I found no contradiction with `docs/designs/global-items.md`: D1-D9, the
`outcome()` rows, seat filling with the `already_seated` exclusion, the quorum-at-open rule, the
`install`/`agents link --user` contract and the backfill table agree with it and with `src/chanchi/`.

OPEN: 0/0/5   (minors: G4 residual, G17 residual, N1, N3, N4; N2 is the G17 residual's detail and counted with it)

AUDIT DONE
