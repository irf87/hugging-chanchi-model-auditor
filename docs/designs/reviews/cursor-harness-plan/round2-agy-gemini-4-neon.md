VERDICT: PASS WITH FIXES

## Round 1 Findings Re-check (commit `1775ccb`)

| r1 id | status | evidence at `1775ccb` |
|---|---|---|
| F1 | RESOLVED | `docs/superpowers/plans/2026-11-23-cursor-harness.md:141` (Task 1.8) now explicitly instructs updating `info.value.valid_values` at `tests/test_modelspec.py:52` to `["claude", "agy", "opencode", "cursor", "human"]`. |
| F2 | RESOLVED | `docs/superpowers/plans/2026-11-23-cursor-harness.md:156-165` (S1 Verification) and `lines 175-181` (Pre-Merge Smoke 3b) now explicitly specify `uv run chanchi` (never bare `chanchi`) from `.claude/worktrees/chanchi-cursor-s1` before S1 merges to `main`. |
| F3 | RESOLVED | `docs/superpowers/plans/2026-11-23-cursor-harness.md:122` (Task 1.6) now includes the unit test for `installed("cursor", env={}, home=tmp_path)` (`False` before `(tmp_path / ".cursor").mkdir()`, `True` after), matching `docs/designs/cursor-harness.md:204`. |
| F4 | RESOLVED | `docs/superpowers/plans/2026-11-23-cursor-harness.md:183` (Smoke 3b step 5) now explicitly forbids inline orchestrator code edits and directs dispatching an S1 fix/retry updating `harnesses.py`, `tests/test_harnesses.py`, `tests/test_audits.py` (and amending `docs/designs/cursor-harness.md` if the launch contract changes), then re-running `scripts/check` and Smoke 3b before merging S1. |
| F5 | RESOLVED | `docs/superpowers/plans/2026-11-23-cursor-harness.md:146` (Task 1.9) now specifies renaming `test_defaults_are_the_seven_roots_in_order` (`tests/test_inventory.py:117`) to `test_defaults_are_the_nine_roots_in_order`. |

## Open Findings (New in Round 2)

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | minor | `docs/superpowers/plans/2026-11-23-cursor-harness.md:181` (Smoke 3b step 3) | The real-`HOME` fallback installs `~/.cursor/agents/agent-chanchi-auditor.md` by running `uv run chanchi agents link --user` with real `HOME` against a scratch `CHANCHI_DB` (and removing it with `--remove`). Because `link_user()` plans wrappers for *every* installed harness in `HOME` against `Path(CHANCHI_DB).parent / "mirror.json"` (which is empty for a scratch DB), existing operational user wrappers for `claude`, `opencode`, and `agy` will trigger `link_conflict` and abort with nothing written. (Running against the operational DB followed by `--remove` would instead delete operational wrappers for all harnesses.) | `src/chanchi/agents_sync.py:352-354,357,381-382,405-412` reads `mirror.json` from `db_dir`, resolves `active_harnesses` across `harnesses.KEYS`, and raises `link_conflict` if any planned path exists outside that manifest. Local check confirms `~/.claude/agents/agent-chanchi-*.md`, `~/.config/opencode/agents/agent-chanchi-*.md`, and `~/.gemini/config/agents/agent-chanchi-*/agent.md` already exist on this machine. | In Smoke 3b step 3, copy the already-rendered `$scratch_home/.cursor/agents/agent-chanchi-auditor.md` (produced in step 1 by `HOME="$scratch_home" ... uv run chanchi agents link --user`) to `~/.cursor/agents/agent-chanchi-auditor.md` only after verifying it does not already exist, run the extracted `launch` line from the scratch consumer repo under real `HOME`, then immediately `rm ~/.cursor/agents/agent-chanchi-auditor.md` and assert it is gone. |

## Summary

- **Open finding counts:** 0 blocking, 0 major, 1 minor (all 5 Round 1 findings `RESOLVED`; 1 new minor finding `N1`).
- **Verification performed at `1775ccb`:**
  - Verified all 5 Round 1 findings (`F1`–`F5`) resolved in `docs/superpowers/plans/2026-11-23-cursor-harness.md`.
  - Verified every updated line reference and assertion added in Revision 2 against the repository:
    - `tests/test_harnesses.py:73-96,109,113,115,131-135`
    - `tests/test_agents_sync.py:33-37,81,127,152-154,172-177,183-210,213-231,269-270,303,312-315`
    - `tests/test_modelspec.py:51-52`, `tests/test_taxonomy.py:221`, `tests/test_sync.py:111,115`, `tests/test_skills_link.py:251-265`
    - `tests/test_inventory.py:117-122`, `tests/test_mirror.py:135,160-164,182,244,486,493`
    - `src/chanchi/sync.py:16-21` and `src/chanchi/audits.py:180-239,351-381` (confirming Task 1.10's `[*sync.BUILTIN_ROSTER, cursor entry]` seats `anthropic`, `google`, `openai` with `degraded is False`, and confirming Smoke 3b step 1 needs quorum `>= 2` so `launch` is non-null).
  - Verified `uv run pytest -q tests/test_privacy.py` passes (`3 passed`) on commit `1775ccb`, and confirmed no repository file was edited.
