VERDICT: PASS WITH FIXES

Subject: the cursor-harness implementation plan at commit 6faf92c (branch `docs/cursor-harness-plan`). I read the plan, the accepted design and the brief, then checked the cited code and test lines locally. I made no live `agent` or `claude` calls and edited no repository file.

I also tried a scratch copy of the commit with a partial src change (harness key, binary, home folder, taxonomy). I stopped it early because the copy lacked `_cursor`, so its failures meant nothing. I used no result from it.

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | major | Plan Task 1.8 (`tests/test_modelspec.py`) | The plan only swaps the `cursor:gpt` sentinel for `codex:gpt`. It misses the assertion in the same test, `test_unknown_agent_lists_agents`, which fails once `taxonomy.AGENTS` gains `cursor`. | `tests/test_modelspec.py:52` asserts `valid_values == ["claude", "agy", "opencode", "human"]`. `taxonomy.py:10-12` has `ALL_AGENTS = AGENTS + PLANNER_ONLY_AGENTS`. After Task 1.3 the list becomes `["claude", "agy", "opencode", "cursor", "human"]`. | Add to Task 1.8: change the line-52 expectation to `["claude", "agy", "opencode", "cursor", "human"]`. |
| F2 | minor | Task 1.7 (`tests/test_agents_sync.py`) | The count updates are incomplete or ambiguous. The plan says "`removed` counts 3 -> 4" but there are two such assertions. `_setup_two_sources` adds `.cursor`, which also changes counts in other tests that use it. | Current assertions: line 81 `written == 3`, line 200 manifest `== 3`, lines 303 and 312 `removed == 3`, line 223 `written == 2` (stays 2 only if `.cursor` is not created). The design also names a kind-set assertion at "line 204". | List every line and its new value (81, 200 and the kind set, 303, 312, 223), or tell the executor to run the file and fix every count caused by the fourth harness. |
| F3 | minor | Task 1.6 (`tests/test_harnesses.py`) | The sentinel replacement is described only for "`test_unknown_harness_lists_valid_keys`". That test uses `"cursor"` in three calls: `launch`, `home_dir` and `available` (lines 109, 113, 115). | `tests/test_harnesses.py:107-115` | Say "replace all three `"cursor"` uses with `"codex"`". |
| F4 | minor | Design coverage in Tasks 1.6, 1.7 and 1.9 | Three items from the design's Verification Plan are not in the plan. They are an `installed("cursor")` test, a `test_repository_wrappers_are_in_sync` update (it covers the four-harness wrapper set and may need nothing beyond the regenerated files), and an explicit `items mirror --check` / `--remove` test over `~/.cursor/agents`. | Design Verification Plan lines for `test_harnesses`, `test_agents_sync` and `test_mirror`. The plan covers mirror check and remove only through the S1 FEATURE_MAP step. | Add one-line tasks for these three. |
| F5 | minor | Pre-merge smoke 3b | The step is hedged and leaves choices to the orchestrator: "prefer checking whether `agent` respects HOME or ... temporary test copy ... after checking conflict safety". The plan promises that no decision is left open. The plan's safety statement is also inconsistent: it mentions using the real `~/.cursor`. | Plan lines 159-164. | Fix one procedure: scratch `HOME`, `chanchi agents link --user`, then run the launch line. If `agent` ignores `HOME`, state the fallback and require the cleanup check. |

Items checked and found correct:
- Harness code lines, `KEYS`, `_BINARY` and the `launch` fall-through match the cited code.
- `audits.py:156-157` is the correct location for the hint change.
- `inventory.py` has 7 `DEFAULT_ROOTS`, so the plan's 9 is right.
- `test_mirror.py` has the 6-to-7 counts the plan names, the `[0, 1, 2]` parametrization and the 3-harness `skipped_harnesses`.
- `test_taxonomy.py:221` is the right line; `test_sync.py:111` and `:115` are right.
- `FEATURE_MAP.md` lines 123, 306, 476 and 609, and the item-authoring table row, match.
- `AGENTS.md` is 141 lines, so adding a row stays under 150.
- Wrapper totals are 6 agents x 4 harnesses = 24.
- `skill_targets` needs no source change, as the design says.
- Exploration budget `max(1, floor(2/4)) = 1` is correct: S2 is the only explore session and it does not block anything.
- Worktree isolation, scratch `CHANCHI_DB`, `CHANCHI_SYNC` and `HOME`, and the pre-merge smoke tests 3a and 3b are present.
- The plan does not use `claude`, touch the MVP phase 2 branches or `run_evals.py`, or add operational Cursor rows.
- The plan contains no home paths or reference-project names.
- The S1 and S2 file ownership has no overlap.
