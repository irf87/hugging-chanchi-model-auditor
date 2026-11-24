VERDICT: PASS WITH FIXES

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | `docs/designs/cursor-harness.md` § 7 (`FEATURE_MAP.md`); `FEATURE_MAP.md` lines 123, 476, 557–558 | The design updates `FEATURE_MAP.md` `agents` notes and `items` evidence for Cursor (`~/.cursor/agents/<name>.md`), but does not explicitly update the `mkdir -p` setup lines in `## agents` (`### How to get to it`, line 123) and `## items` (`### How to get to it`, line 476). If line 476 keeps only `.claude`, `.config/opencode`, and `.gemini/antigravity-cli` without `"$scratch_home/.cursor"`, running `FEATURE_MAP.md` verbatim (`skill-chanchi-verify`) will produce `skipped_harnesses: ["cursor"]` instead of `[]` on line 558 and omit `~/.cursor/agents/<name>.md`. | `FEATURE_MAP.md` line 476: `mkdir -p "$scratch_home/.claude" "$scratch_home/.config/opencode" "$scratch_home/.gemini/antigravity-cli"`; line 558: `` `skipped_harnesses` `[]` ``. | Explicitly add `"$scratch_home/.cursor"` to the `mkdir -p` setup commands in `FEATURE_MAP.md` `## agents` (line 123) and `## items` (line 476), and include `~/.cursor/agents/<name>.md` in `## items` `items mirror` evidence (lines 557–558). |
| F2 | minor | `docs/designs/cursor-harness.md` § Verification Plan (lines 181, 187); `tests/test_harnesses.py` lines 73–96; `tests/test_mirror.py` lines 159–165, 182, 244, 486, 493 | Two existing test shapes break by implication when adding `"cursor"` and need explicit branch/count updates beyond the brief summary in the Verification Plan: (1) `test_launch_carries_permission_flags_and_add_dirs` parametrizes over `harnesses.KEYS` and uses a catch-all `else:` branch for `opencode` (`--auto`, no `--add-dir`), which would fail on `"cursor"`; (2) adding `.cursor` to the `world` fixture in `tests/test_mirror.py` breaks `test_no_installed_harness_writes_nothing` (must also remove `world.home / ".cursor"` and expect `"cursor"` in `skipped_harnesses`), hardcoded counts (`6` -> `7` on lines 182, 486, 493), and `index` parametrization (`[0, 1, 2]` -> `[0, 1, 2, 3]` on line 244). | `tests/test_harnesses.py` lines 73–96 (`if key == "claude": ... elif key == "agy": ... else: ...`); `tests/test_mirror.py` lines 160–164, 182, 244, 486, 493. | Note in the Verification Plan to split `test_launch_carries_permission_flags_and_add_dirs` into explicit `opencode` and `cursor` branches, and update `test_no_installed_harness_writes_nothing`, expected entry counts (`6` -> `7`), and `index` parametrization (`0..3`) in `tests/test_mirror.py`. |

## Summary

Audited `docs/designs/cursor-harness.md` (commit `4359753`, branch `docs/cursor-harness-design`) against `docs/designs/cursor-harness.brief.md`, the codebase, local `agent` CLI facts, and `AGENTS.md` rules.

### Checks Performed

- **Request & Owner Decisions (`docs/designs/cursor-harness.brief.md`):**
  - Decision 1A (`--trust --force`, prompt-prefixed role instruction pointing to `.cursor/agents/<agent>.md` or `~/.cursor/agents/<agent>.md`, omitting `--mode ask`/`--mode plan` on outer `agent -p`, emitting `readonly: true` on `profile: read-only` wrappers): matches Design § 1, § 2, § 7, and Adopt/Adapt/Avoid.
  - Decision 2 (defer operational DB rows and `SYNC/config/auditors.toml` edits; test via scratch `CHANCHI_DB`/`CHANCHI_SYNC`): matches Non-goals and Verification Plan.
  - Decision 3A (`home_dir("cursor") = ~/.cursor`, `user_agent_path("cursor", name) = ~/.cursor/agents/{name}.md`, documenting CLI `.cursor/agents/` vs desktop `~/.cursor/agents/` behavior, and manual desktop verification handoff): matches Design § 1, § 2, § 6, § 7, and Verification Plan step 4.
  - Decision 4 (no `claude` usage, no edits to `scripts/run_evals.py` or `feat/mvp2-s4`/`feat/mvp2-s5`): matches Non-goals.
- **Local CLI & Environment Verification:**
  - `agent --version` -> `2026.11.22-e9042b2`; `agent` and `cursor-agent` symlinks both point to `cursor-agent` version `2026.11.22-e9042b2`.
  - `agent --help` confirms `-p`/`--print`, `--model <model>` (with quoted bracket overrides), `--trust`, `-f`/`--force`, `--add-dir <path>` (repeatable), `--workspace <path-or-name>`, `--mode <mode>` (`plan`, `ask`), and positional `[prompt...]`.
  - `~/.cursor/skills-cursor/create-subagent/SKILL.md` confirms `.cursor/agents/` (project: desktop, CLI, cloud) vs `~/.cursor/agents/` (user: desktop app and self-hosted workers where enabled; not CLI or hosted cloud), flat `.md` format with `name` and `description`.
  - `~/.cursor/skills-cursor/create-skill/SKILL.md` confirms `~/.cursor/skills-cursor/` is reserved for internal built-in skills.
- **Codebase & Rules Verification:**
  - `./scripts/check` passes on baseline commit `4359753` (`All checks passed!`, `988 passed in 65.75s`).
  - `wc -l AGENTS.md` is `141` lines; proposed additions (~1–2 lines) stay within the `150`-line budget enforced by `tests/test_rules_budget.py`.
  - No SQL migration is needed: migrations `001`–`006` place no `CHECK` constraint on `models.agent` or `audit_seats`, and keeping `taxonomy.FAMILY_PREFIXES` unchanged preserves parity with `005_audits_and_families.sql`.
  - `Adopt / Adapt / Avoid` section is present and cites primary sources (`agent --help`, `agent --list-models`, Cursor's bundled skills, and Cursor documentation).
  - Shell escaping in `harnesses.launch("cursor", ...)`: `_arg(model)` uses `shlex.quote` when bracket overrides (`[...]`) are present, `_dq(d)` quotes `--add-dir` paths, and `-- {_dq(role_prompt)} < /dev/null` prevents prompts starting with `-` from being parsed as flags and prevents stdin hangs.
  - `agents_sync._cursor()` emits `# generated by chanchi ...` in frontmatter, so `inventory._generated()` skips generated `.cursor/agents/agent-chanchi-*.md` files automatically when scanning `.cursor/agents` in `AGENT_FILE_ROOTS`.
  - No home paths or reference-project names appear in `docs/designs/cursor-harness.md` or `docs/designs/cursor-harness.brief.md`.
