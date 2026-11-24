VERDICT: PASS WITH FIXES

## Round 1 Findings Re-check

- **F1 (`RESOLVED`):** `docs/designs/cursor-harness.md` § 7 (`FEATURE_MAP.md`, lines 192–195) now explicitly adds `"$scratch_home/.cursor"` to the `mkdir -p` setup commands in `## agents` (`### How to get to it`, `FEATURE_MAP.md` line 123) and `## items` (`### How to get to it`, `FEATURE_MAP.md` line 476), and adds `~/.cursor/agents/<name>.md` to `items mirror` evidence (`FEATURE_MAP.md` lines 557–558) alongside `.cursor/agents/` in `agents sync --check` evidence and the nine default folders in `## project` and `items scan` gotchas.
- **F2 (`RESOLVED`):** `docs/designs/cursor-harness.md` § Verification Plan (lines 203 and 213) now explicitly instructs splitting the catch-all `else:` branch in `tests/test_harnesses.py` lines 73–96 (`test_launch_carries_permission_flags_and_add_dirs`) into `elif key == "opencode":` and `elif key == "cursor":` branches, and updates `tests/test_mirror.py` `world` fixture, `agent_paths`, kind assertions (line 135), `test_no_installed_harness_writes_nothing` (lines 160–164, removing `.cursor` and expecting `"cursor"` in `skipped_harnesses`), hardcoded entry counts (`6 -> 7` on lines 182, 486, 493), and `index` parametrization (`[0, 1, 2, 3]` on line 244).

## Open Findings

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F3 | minor | `docs/designs/cursor-harness.md` § Verification Plan (line 206); `tests/test_agents_sync.py` lines 213–231 | `test_link_user_skips_missing_harness_and_honours_opencode_config_dir` creates `home/.claude` and `home/.gemini` directly (without `_setup_two_sources`) and asserts `res["skipped_harnesses"] == ["opencode"]` (line 222) and `res2["skipped_harnesses"] == []` (line 229). Once `"cursor"` is added to `harnesses.KEYS`, those lists become `["opencode", "cursor"]` and `["cursor"]` (unless `.cursor` is also created in that test), but line 206 only notes `3 -> 4`, line 204, and `_setup_two_sources`. | `tests/test_agents_sync.py` lines 216–229: `(home / ".claude").mkdir(...)`, `(home / ".gemini").mkdir(...)`, `assert res["skipped_harnesses"] == ["opencode"]`, `assert res2["skipped_harnesses"] == []`. | Note in Verification Plan (`tests/test_agents_sync.py`) to update `test_link_user_skips_missing_harness_and_honours_opencode_config_dir` (lines 222, 229) to expect `"cursor"` in `skipped_harnesses` (or create `home / ".cursor"` in that test). |

## Summary

Re-audited `docs/designs/cursor-harness.md` at commit `17eab73` (branch `docs/cursor-harness-design`) against `docs/designs/cursor-harness.brief.md`, `docs/designs/reviews/cursor-harness/round1-consolidation.md`, the codebase, local `agent` CLI (`2026.11.22-e9042b2`), and `AGENTS.md`.

- **Open findings count:** 0 blocking, 0 major, 1 minor (`F3`).
- **Round 1 & Consolidation Verification:** Both Round 1 findings (`F1`, `F2`) and all confirmed items from `round1-consolidation.md` (bundled-skill attribution and `readonly: true` caveat, shared test breakage enumerations, `FEATURE_MAP.md` setup commands, `skill-chanchi-verify` Helpers, pre-merge live CLI smoke tests 3a/3b, `harnesses.binary()` + `audits.py:157` `not_on_path` hint, bracketed model-ID quoting and committed wrapper frontmatter tests, `home_dir()` ordering before opencode env fallbacks, `--workspace` cwd precondition, and behavioural read-only wording) are addressed in commit `17eab73`.
- **Local Checks:** Confirmed `agent --version` (`2026.11.22-e9042b2`) and `agent --help` (`--workspace` defaults to cwd, `--model` bracket override quoting); `uv run pytest -q tests/test_privacy.py tests/test_rules_budget.py tests/test_feature_map.py` passed (`19 passed in 3.09s`); `AGENTS.md` stands at 141 lines (<= 150 budget). No live LLM calls were run and no repository files were edited.
