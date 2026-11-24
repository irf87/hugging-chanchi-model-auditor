# Audit 15 — Round 1 Consolidation (`docs/superpowers/plans/2026-11-23-cursor-harness.md`)

- **Audit ID:** 15
- **Subject:** `docs/superpowers/plans/2026-11-23-cursor-harness.md` at commit `6faf92c` (branch `docs/cursor-harness-plan`)
- **Date:** 2026-11-23
- **Degraded:** `false` (3 distinct families: `anthropic`, `google`, `tencent`; `claude:sonnet:medium` marked unavailable per owner instruction excluding Claude CLI, refilled with `agy:claude-sonnet-5-5-medium:medium`)
- **Outcome:** `fix`

## Seats and Votes

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|---|
| 1 (orig) | `claude:sonnet:medium` | `anthropic` | unavailable | — | — | — | owner instruction 2026-11-23: no claude CLI |
| 1 (voted) | `agy:claude-sonnet-5-5-medium:medium` | `anthropic` | `pass_with_fixes` | 0 | 1 | 4 | `round1-agy-claude-sonnet-5-5.md` |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass_with_fixes` | 0 | 0 | 5 | `round1-agy-gemini-4-neon.md` |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `pass_with_fixes` | 0 | 1 | 2 | `round1-opencode-hy4-flash-free.md` |

## Consolidated Findings

### Shared findings (2+ seats)

1. **`tests/test_modelspec.py:52` missing `valid_values` update (S1-F1 major, S3-F1 major, S2-F1 minor):** Adding `"cursor"` to `taxonomy.AGENTS` changes `taxonomy.ALL_AGENTS` to `("claude", "agy", "opencode", "cursor", "human")`, breaking line 52. **Fix:** Add explicit update of `tests/test_modelspec.py:52` to Task 1.8.
2. **`installed("cursor")` test missing in Task 1.6 (S1-F4a minor, S2-F3 minor):** Required by accepted design Verification Plan. **Fix:** Add `installed("cursor")` false/true test to Task 1.6.
3. **Smoke 3b setup under-specified / hedged (S1-F5 minor, S3-F3 minor):** Missing scratch `cursor:auto` catalog row + roster step and hedged `HOME` vs real `~/.cursor` wording. **Fix:** Pin a single concrete procedure: seed `cursor:auto` (`cost 1`, `family: null`) on scratch `CHANCHI_DB` + scratch `SYNC/config/auditors.toml` with `harness = "cursor", model = "auto"`, run `uv run chanchi agents link --user` against scratch `HOME` containing `.cursor` first, and specify the exact fallback + cleanup check only if `agent` ignores `HOME`.

### Lone-finding dissent decisions

| Dissent ID | Seat | Finding | Severity | Decision | Evidence |
|---|---|---|---|---|---|
| 182 | 1 | `F2`: Enumerate exact count/kind lines in `tests/test_agents_sync.py` (81, 200, 204, 223, 303, 312) | minor | **confirmed** | Lines 81, 200, 223, 303, 312 assert counts; line 204 asserts kind set |
| 183 | 1 | `F3`: Specify replacing all three `"cursor"` calls (`lines 109, 113, 115`) in `test_unknown_harness_lists_valid_keys` | minor | **confirmed** | `tests/test_harnesses.py:109,113,115` all pass `"cursor"` |
| 184 | 1 | `F4b`: Note `test_repository_wrappers_are_in_sync` and explicit `items mirror --check`/`--remove` over `~/.cursor/agents` | minor | **confirmed** | Accepted design Verification Plan lists both explicitly |
| 185 | 2 | `F2`: Use `uv run chanchi` (not bare `chanchi`) in S1 Verification #3 and Smoke 3b before merge | minor | **confirmed** | Editable `chanchi` shim on PATH points to `main` until S1 merges |
| 186 | 2 | `F4`: If Smoke 3b fails on `~/.cursor/agents/` access, dispatch an S1 fix/retry updating code, tests, and design rather than inline orchestrator edit | minor | **confirmed** | `AGENTS.md`: orchestrator plans and audits; executors implement |
| 187 | 2 | `F5`: Rename `test_defaults_are_the_seven_roots_in_order` to `test_defaults_are_the_nine_roots_in_order` (`tests/test_inventory.py:117`) | minor | **confirmed** | `tests/test_inventory.py:117` hardcodes `seven` |
| 188 | 3 | `F2`: Task 1.10 custom roster must be explicit (`[*sync.BUILTIN_ROSTER, cursor entry]`) so 3 families sit and `degraded is False` | minor | **confirmed** | `audits.is_degraded` needs 3 distinct families; 1 entry escalates on quorum |

## Next Action

Apply all shared and confirmed lone findings to `docs/superpowers/plans/2026-11-23-cursor-harness.md`, commit on `docs/cursor-harness-plan`, and open Round 2 (`chanchi audit round 15 --commit <next-sha>`).
