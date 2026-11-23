VERDICT: PASS

Audited branch `fix/launch-permissions` at commit `7261f8d` (diff against `26d18b7`) in `.claude/worktrees/chanchi-launchperm` against the request, CLI `--help` contracts, and local tests.

## Findings

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | `README.md:76-77`, `docs/designs/global-items.md:311-315`, `skills/skill-chanchi-verify/SKILL.md:33` | Stale headless launch examples remain without the new permission flags: `README.md` shows `opencode run --agent <name>` and `agy --agent <name> -p="<prompt>"` without `--auto` / `--dangerously-skip-permissions`; `docs/designs/global-items.md` (cited by `src/chanchi/harnesses.py:4`) shows all three headless templates without permission flags, `--add-dir`, or `--` for claude; `skills/skill-chanchi-verify/SKILL.md:33` shows `claude -p --agent agent-chanchi-researcher "..."` without `--permission-mode` / `--allowedTools`. | Read `README.md:76-77`, `docs/designs/global-items.md:311-315`, `skills/skill-chanchi-verify/SKILL.md:31-35`, and ran `rg -n "claude -p\|opencode run\|agy .*(-p\|--agent)"` across the worktree. | Update the headless examples in `README.md:76-77` and the adapter table in `docs/designs/global-items.md:311-315` (and optionally `skills/skill-chanchi-verify/SKILL.md:33`) to match `harnesses.launch`. |
| F2 | minor | `skills/skill-chanchi-audit-rounds/SKILL.md:23` | Step 3 instructs callers to replace `<report-dir>` in every seat's `launch` command without noting `(where present)`, unlike `FEATURE_MAP.md:393`, even though `opencode` seats have no `<report-dir>` placeholder. | `skills/skill-chanchi-audit-rounds/SKILL.md:23` vs `FEATURE_MAP.md:393` and `src/chanchi/harnesses.py:104-106`. | Add `(where present)` after `<report-dir>` in `skills/skill-chanchi-audit-rounds/SKILL.md:23`. |
| F3 | minor | `tests/test_harnesses.py:74` | `test_launch_carries_permission_flags_and_add_dirs` parametrizes `profile` over a hardcoded tuple `("read-only", "workspace-write", "orchestrator")` instead of `harnesses.PROFILES`, whereas line 73 uses `harnesses.KEYS`. | Read `tests/test_harnesses.py:73-74`. | Parametrize `profile` over `harnesses.PROFILES`. |

## Check Summary

1. **Code & tests (`src/chanchi/harnesses.py`, `src/chanchi/audits.py`, `src/chanchi/agents_sync.py`, `tests/`):**
   - `harnesses.launch` adds `profile="read-only"` (validated against `harnesses.PROFILES`) and `add_dirs=()`.
   - For `claude`, it emits `--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob"` (`read-only`) or `"Bash Read Grep Glob Edit Write"` (`workspace-write`, `orchestrator`), any `--add-dir "<dir>"` arguments, and `--` before the double-quoted prompt so variadic `--allowedTools`/`--add-dir` cannot swallow `<prompt>`. It never emits `--dangerously-skip-permissions`.
   - For `agy`, it emits `--dangerously-skip-permissions` and `--add-dir "<dir>"` before `-p="<prompt>"`.
   - For `opencode`, it emits `--auto` and ignores `add_dirs` (confirmed via `opencode run --help` that `opencode run` has no `--add-dir` flag).
   - `audits._fill` and `audits._seat_view` both pass `profile="read-only"` and `add_dirs=(REPORT_DIR,)`, with `REPORT_DIR = "<report-dir>"`.
   - Verified CLI flags locally via `claude --help`, `opencode run --help`, and `agy --help`.
   - Ran `uv run pytest -q tests/test_harnesses.py tests/test_audits.py`: `72 passed in 0.65s`.
   - Ran full suite `uv run pytest -q`: `938 passed in 32.79s`.
   - Ran `./scripts/check` (ruff + pytest): `All checks passed!`, `938 passed in 29.36s`.
2. **Rules & docs (`AGENTS.md`, `FEATURE_MAP.md`, `skills/skill-chanchi-audit-rounds/SKILL.md`):**
   - `AGENTS.md` (138 lines, within the 150-line budget enforced by `tests/test_rules_budget.py`) accurately and consistently documents `agy` (`--dangerously-skip-permissions`), `opencode` (`--auto`), and headless `claude -p` (`--permission-mode acceptEdits --allowedTools` naming `Bash` and the profile's tools; `--dangerously-skip-permissions` restricted to separate terminal/herdr panes), and references `harnesses.launch` and `tests/test_harnesses.py`.
   - `FEATURE_MAP.md:393` accurately describes the permission flags and `<report-dir>` placeholder `(where present)`.
3. **Risks:**
   - **Quoting:** `_dq` escapes `\`, `"`, `$`, and `` ` `` inside double quotes for tools, `add_dirs`, and `prompt`; `--` precedes `prompt` in `claude`, and `-p=` attaches `prompt` in `agy`, avoiding option-parsing ambiguity. Note that callers substituting `<report-dir>` into the returned template string are responsible for keeping the path valid inside the surrounding double quotes.
   - **`<report-dir>` placeholder & `opencode` ignoring `add_dirs`:** `opencode` has no `--add-dir` flag (`opencode run --help`), and `agent-chanchi-auditor` on `opencode` uses shell writes (`agents/agent-chanchi-auditor/AGENT.md:15`) under `--auto`.
   - **Shared `PROFILES` tuple:** `harnesses.PROFILES` is defined in the leaf module `src/chanchi/harnesses.py` (imports only `chanchi.errors`, passing `tests/test_layers.py`) and re-exported as `agents_sync.PROFILES = harnesses.PROFILES`.
