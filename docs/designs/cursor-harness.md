# Cursor Harness Support — Design

- **Status:** Draft — Revision 2 after Audit 14 Round 1 (2026-11-23)
- **Brief:** `docs/designs/cursor-harness.brief.md`
- **Reference design:** `docs/designs/global-items.md` ("Harness adapters"), `docs/designs/chanchi-agents-mvp.md`

## Goal

Add `cursor` (CLI binary `agent`, alias `cursor-agent`) as a fourth supported harness alongside `claude`, `opencode`, and `agy`:

1. Headless launch lines, binary lookup, and user-level folders in `src/chanchi/harnesses.py` (plus binary-aware `not_on_path` hints in `src/chanchi/audits.py`).
2. Repository and user-level agent compilation in `src/chanchi/agents_sync.py` (`.cursor/agents/<name>.md` and `~/.cursor/agents/<name>.md`), checked by `chanchi agents sync --check` and `scripts/check`.
3. `cursor` agent key in `src/chanchi/taxonomy.py`, Cursor-only skill target support via `.agents/skills/` in `src/chanchi/skills_link.py`, and read-only project scanning of `.cursor/skills` and `.cursor/agents` in `src/chanchi/inventory.py`.
4. Updated rules, skills, docs, feature map, and tests.

## Non-goals

- **No SQL migration.** `models.agent` and `audit_seats` have no SQL `CHECK` constraint on agent names; agent keys are validated in `taxonomy.py` and `harnesses.py`. `taxonomy.FAMILY_PREFIXES` is kept unchanged so its SQL parity test against `005_audits_and_families.sql` stays intact.
- **No operational database rows or `SYNC/config/auditors.toml` edits in this change** (owner Decision 2, 2026-11-23). Both paths are tested on scratch `CHANCHI_DB` and `CHANCHI_SYNC`.
- **No changes to `scripts/run_evals.py` or MVP phase 2 branches** (`feat/mvp2-s4`, `feat/mvp2-s5`).
- **No duplicate `.cursor/skills/` symlinks** in `skills_link.py` or `items.mirror`.

## Adopt / Adapt / Avoid (external sources)

Primary sources inspected on 2026-11-23: local `agent --help` and `agent --list-models` (`2026.11.22-e9042b2`), Cursor's bundled skills (`~/.cursor/skills-cursor/create-subagent/SKILL.md`, `create-skill/SKILL.md`, `create-rule/SKILL.md`), and `cursor.com` documentation on CLI headless mode, subagents, and skills.

- **Adopt:**
  - Native `AGENTS.md` loading without a thin wrapper (`agent` `2026.11.22-e9042b2` Canary 1).
  - Native `.agents/skills/` and `~/.agents/skills/` skill discovery (`agent` Canary 2), matching `opencode` so `chanchi skills link` and `items mirror` avoid duplicate symlinks.
  - Project `.cursor/agents/<name>.md` and user `~/.cursor/agents/<name>.md` flat Markdown layout with YAML frontmatter `name` and `description` (bundled `create-subagent/SKILL.md`).
  - `readonly: true` on `profile: read-only` wrappers. **Evidence caveat:** bundled `create-subagent/SKILL.md` documents only `name` and `description` and does not list `readonly`; `readonly: true` is documented in external Cursor subagent guides and verified locally solely by Canary 3 on `agent` `2026.11.22-e9042b2`, where the delegated `canary-auditor` subagent replied *"Ask mode also forbids creating or modifying files, so `blocked.txt` was not created."* Treat `readonly: true` as an undocumented bundled-skill key subject to recheck on Cursor upgrades, and guard emission with a unit test.
  - `-p --trust --force --model <m>` plus repeatable `--add-dir "<dir>"` and `-- "<prompt>"` for unattended headless runs (`agent --help`, Canaries 4–5).
- **Adapt:**
  - **Missing `--agent` flag:** Cursor CLI has no `--agent` option (`error: unknown option '--agent'`). Adapt `harnesses.launch("cursor", ...)` to pass the agent role explicitly in the prompt (`Follow the <agent> role (.cursor/agents/<agent>.md or ~/.cursor/agents/<agent>.md): <prompt>`), so the outer headless session reads the compiled wrapper whether it runs inside the `chanchi` repository or in a consumer project where `agents link --user` wrote `~/.cursor/agents/<agent>.md`.
  - **Skill preloading in agent wrappers:** Neither bundled `create-subagent/SKILL.md` nor `cursor.com` subagents docs define a `skills:` or `preloadSkills:` preload key. Adapt `_cursor()` in `agents_sync.py` to append `Before starting, load these skills: ...` to the body when `skills` is non-empty, matching `_opencode()`.
  - **`read-only` profile in headless runs:** Passing `--mode ask` or `--mode plan` on the outer `agent -p` command would risk preventing `agent-chanchi-auditor` from writing its report to `<report-dir>`. Instead, keep `readonly: true` in `.cursor/agents/<name>.md` (which puts Cursor's `Task`-delegated subagent into Ask mode, verified in Canary 3) while running the outer headless session with `agent -p --trust --force` so it can write its report file to `<report-dir>` (verified in Canary 5). On that outer headless session, read-only discipline is **behavioural** (parity with `opencode run --auto`), not enforced by CLI flags; `readonly: true` enforces Ask mode only when Cursor delegates to the wrapper as a subagent.
- **Avoid:**
  - **Writing into `~/.cursor/skills-cursor/`:** Reserved for Cursor's built-in skills (`create-skill/SKILL.md`). Never link or mirror there.
  - **Creating duplicate `.cursor/skills/` symlinks:** Cursor already discovers `.agents/skills/` and `~/.agents/skills/` natively; linking both would list every skill twice.
  - **Putting `model:` in agent frontmatter:** Cursor subagents accept `model:` (`cursor.com` subagents docs), but `skill-chanchi-item-authoring` forbids hardcoding models in wrappers; the orchestrator selects models at launch time.
  - **Splitting effort suffixes from Cursor model IDs:** Unlike `agy`, `agent --list-models` exposes heterogeneous IDs (`auto`, `composer-2.5`, `gpt-5.3-codex-high`, `gpt-5.5-extra-high`, `claude-4.5-sonnet-thinking`, plus bracket overrides). Pass `--model <model>` verbatim and ignore `effort` in `launch()`, matching `opencode`.

## Technical Design

### 1. `src/chanchi/harnesses.py`

- Extend `KEYS`:
  ```python
  KEYS = ("claude", "opencode", "agy", "cursor")
  ```
- Extend `_BINARY` and expose `binary(key: str) -> str`:
  ```python
  _BINARY = {"claude": "claude", "opencode": "opencode", "agy": "agy", "cursor": "agent"}

  def binary(key: str) -> str:
      """The CLI executable name of a harness."""
      return _BINARY[_key(key)]
  ```
  `available()` calls `which(binary(key)) is not None`.
- Extend `launch()` for `key == "cursor"`:
  ```python
  if key == "cursor":
      role_prompt = (
          f"Follow the {agent} role "
          f"(.cursor/agents/{agent}.md or ~/.cursor/agents/{agent}.md): {prompt}"
      )
      return (
          f"agent -p --trust --force --model {_arg(model)}{dirs} "
          f"-- {_dq(role_prompt)} < /dev/null"
      )
  ```
  - **Working-directory precondition:** `agent --workspace` defaults to the current working directory (`agent --help`), so like `claude`, `opencode`, and `agy`, the caller must run the launch line from the workspace/repository root. From there, relative `.cursor/agents/<agent>.md` resolves directly in repositories that contain it, and `~/.cursor/agents/<agent>.md` covers consumer projects where `chanchi agents link --user` installed the role (verified in pre-merge smoke test item 3b below).
  - All three profiles (`read-only`, `workspace-write`, `orchestrator`) are accepted and validated by `_profile(profile)`.
  - `effort` is accepted (including `None`) and ignored in the CLI line, matching `opencode`: the catalog model ID is passed verbatim to `--model` (with `_arg()` quoting bracketed overrides such as `claude-opus-4-8[context=1m,effort=high,fast=false]`).
  - `add_dirs` emits repeatable ` --add-dir "<dir>"` with `_dq()` escaping, matching `claude` and `agy`.
  - `role_prompt` (including `agent`) is escaped as one double-quoted shell word with `_dq()` after `--`, preventing prompts starting with `-` from being parsed as options.
- Extend `home_dir()` — place the `cursor` branch **with `claude` and `agy`, before the `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME` fallbacks** so those env vars never redirect Cursor's home folder:
  ```python
  if key == "claude":
      return home / ".claude"
  if key == "agy":
      return home / ".gemini"
  if key == "cursor":
      return home / ".cursor"
  if env.get("OPENCODE_CONFIG_DIR"):
      ...
  ```
- Extend `user_agent_path()`:
  ```python
  if key in ("claude", "opencode", "cursor"):
      return base / "agents" / f"{name}.md"
  ```
  (`installed("cursor")` works automatically through `home_dir`.)

### 2. `src/chanchi/agents_sync.py`

- Extend `WRAPPER_GLOBS`:
  ```python
  WRAPPER_GLOBS = (
      ".claude/agents/agent-chanchi-*.md",
      ".opencode/agents/agent-chanchi-*.md",
      ".agents/agents/agent-chanchi-*/agent.md",
      ".cursor/agents/agent-chanchi-*.md",
  )
  ```
- Extend `REPO_TARGETS`:
  ```python
  REPO_TARGETS = {
      "claude": lambda name: f".claude/agents/{name}.md",
      "opencode": lambda name: f".opencode/agents/{name}.md",
      "agy": lambda name: f".agents/agents/{name}/agent.md",
      "cursor": lambda name: f".cursor/agents/{name}.md",
  }
  ```
- Add `_cursor(s: AgentSource, header: str) -> str`:
  ```python
  def _cursor(s: AgentSource, header: str) -> str:
      head = [header, f"name: {s.name}", f"description: {json.dumps(s.description)}"]
      if s.profile == "read-only":
          head.append("readonly: true")
      line = _skills_line(s)
      return _doc(head, "\n" + s.body + (f"\n{line}\n" if line else ""))
  ```
  - `scope` (`main`, `subagent`, `both`) has no Cursor frontmatter field in bundled `create-subagent/SKILL.md` or `cursor.com` subagents docs; all agents compile to `.cursor/agents/<name>.md`.
  - `profile: read-only` maps to `readonly: true` (enforcing Ask mode when Cursor delegates to the wrapper as a subagent; see Adopt/Adapt/Avoid caveat above); `workspace-write` and `orchestrator` omit `readonly`.
  - Non-empty `skills` appends `Before starting, load these skills: ...` to the body.
  - `header` matches the other harnesses (`# generated by chanchi agents sync ...`, `USER_HEADER`, or `MIRROR_HEADER`), so `inventory._generated()` skips generated `.cursor/agents/` wrappers automatically. Pre-merge smoke test item 3a verifies that Cursor's subagent loader parses a generated wrapper whose first frontmatter line is `# generated by chanchi ...`.
- Add `"cursor": _cursor(source, header)` to `render_by_kind()`.
- Regenerate and commit `.cursor/agents/agent-chanchi-*.md` for all six repository agents via `uv run chanchi agents sync`.
- `link_user()` iterates `harnesses.KEYS` and uses `render_by_kind` + `harnesses.user_agent_path`: it automatically writes `~/.cursor/agents/<name>.md` for `install: user` agents when `~/.cursor` exists, tracks ownership in `mirror.json` (`kind: "cursor"`), checks hashes with `--check`, and removes them cleanly with `--remove`.

### 3. `src/chanchi/taxonomy.py`

- Extend `AGENTS`:
  ```python
  AGENTS = ("claude", "agy", "opencode", "cursor")
  ```
- Keep `FAMILY_PREFIXES` unchanged so the SQL parity test against `005_audits_and_families.sql` remains untouched.
  - Standard vendor-prefixed Cursor models (`gpt-*` → `openai`, `claude-*` → `anthropic`, `gemini-*` → `google`, `grok-*` → `xai`, `kimi-*` → `moonshot`, `glm-*` → `zhipu`, `deepseek-*` → `deepseek`) already infer their family automatically on `chanchi models add`.
  - Models without a matching prefix (`composer-2.5`, `cursor-grok-*`, `muse-*`) accept `--family <slug>` on `chanchi models add` or `chanchi models set`.
  - `cursor:auto` intentionally keeps `family: null` because Cursor's Auto mode routes across model families and must never count as a distinct family in audits (fail closed).

### 4. `src/chanchi/skills_link.py`

- No change to `plan_targets()` or secondary directories: Cursor reads `.agents/skills/` (project) and `~/.agents/skills/` (user) natively.
- `skill_targets()` already checks `if not any(installed(key) for key in harnesses.KEYS): return []`; adding `"cursor"` to `harnesses.KEYS` automatically makes `skill_targets()` emit `~/.agents/skills/<name>` primaries on machines where only Cursor (`~/.cursor`) is installed.

### 5. `src/chanchi/inventory.py`

- Extend `DEFAULT_ROOTS` (7 → 9 folders) and `AGENT_FILE_ROOTS` (2 → 3 folders) so `chanchi items scan` and `chanchi project items-dirs` recognize Cursor-native items in registered projects:
  ```python
  DEFAULT_ROOTS = (
      ".agents/skills",
      ".claude/skills",
      ".opencode/skills",
      ".cursor/skills",
      "agents",
      ".claude/agents",
      ".opencode/agents",
      ".agents/agents",
      ".cursor/agents",
  )
  AGENT_FILE_ROOTS = (".claude/agents", ".opencode/agents", ".cursor/agents")
  ```
- Update module docstring in `inventory.py` to mention `.cursor/agents/<name>.md`.

### 6. `src/chanchi/sync.py`, `src/chanchi/audits.py`, and `src/chanchi/items.py`

- `sync._entry()` checks `harness in harnesses.KEYS` → `SYNC/config/auditors.toml` automatically accepts `harness = "cursor"`.
- `audits.py`: update the `not_on_path` hint in `_candidates()` (`src/chanchi/audits.py:157`) to use `harnesses.binary(harness)`:
  ```python
  binary = harnesses.binary(harness)
  target = harness if binary == harness else f"{binary} ({harness})"
  skip = {"reason": "not_on_path", "hint": f"install {target} or put it on PATH"}
  ```
  Existing hints for `claude`, `opencode`, and `agy` stay byte-identical; for `cursor`, the hint names `agent (cursor)` instead of misleadingly pointing at the separate `cursor` desktop-launcher binary. All other `audits.py` paths (`available`, `launch`, `modelspec.parse`) support `"cursor"` automatically.
- `items.mirror()` iterates `harnesses.KEYS` → published global skills get `~/.agents/skills/<name>` (read by Cursor) and published global agents get `~/.cursor/agents/<name>.md` when `~/.cursor` exists, tracked in `mirror.json`.

### 7. Operational docs, rules, and skills

- **`AGENTS.md`** (must stay ≤ 150 lines; currently 141 lines):
  - Add Cursor row to `Harness Entry Points` table: `Cursor (agent CLI)` | `Natively` | `agent 2026.11.22-e9042b2 canary test, 2026-11-23`.
  - Mention Cursor alongside opencode and agy for `.agents/skills/`.
  - Add Cursor (`--trust --force`) to the headless auto-approval rule in `Working Conventions` (owner authorized 2026-11-23).
- **`skills/skill-chanchi-model-selection/SKILL.md`**: update `(agents: claude, agy, opencode, cursor)`.
- **`skills/skill-chanchi-item-authoring/SKILL.md`**: add `.cursor/agents` to the list of generated wrapper folders never to edit by hand.
- **`skills/skill-chanchi-verify/SKILL.md`**: update `## Helpers` to include a Cursor agent-load check alongside `agy`, `opencode`, and `claude` (noting `.cursor/agents/` is checked via `agent -p --trust` and `readonly: true` should be rechecked after a Cursor upgrade).
- **`README.md`**:
  - Skills section: `.agents/skills/skill-chanchi-*` is read by opencode, agy, and Cursor.
  - Agents section: include Cursor (`.cursor/agents/`), note `agent -p --trust --force` headless usage, and note that `~/.cursor/agents/` is read by Cursor desktop (CLI reads `.cursor/agents/`).
  - Audits / Global items sections: note `harness = "cursor"` in `SYNC/config/auditors.toml`, `~/.cursor/agents` in `items mirror`, and `.cursor/skills` + `.cursor/agents` in `items scan`.
- **`FEATURE_MAP.md`**:
  - `## agents`: add `"$scratch_home/.cursor"` to `mkdir -p` in `### How to get to it` (line 123), and include `.cursor/agents/` in `agents sync --check` evidence.
  - `## project`: update default scanned folder count (7 → 9).
  - `## items`: add `"$scratch_home/.cursor"` to `mkdir -p` in `### How to get to it` (line 476); include `~/.cursor/agents/<name>.md` in `items mirror` evidence (lines 557–558); update `items scan` gotchas to list the nine default folders (`.cursor/skills`, `.cursor/agents`) and `.cursor/agents` single-file agents.

## Verification Plan

1. **Automated gate (`scripts/check` = `ruff check` + `pytest -q`):**
   - `tests/test_harnesses.py`:
     - Update `KEYS` assertion to `("claude", "opencode", "agy", "cursor")`.
     - Replace `"cursor"` unknown-harness sentinel with `"codex"`.
     - Split the catch-all `else:` branch in parametrized `test_launch_carries_permission_flags_and_add_dirs` (`lines 73–96`) into explicit `elif key == "opencode":` and `elif key == "cursor":` branches asserting `--trust --force`, `--add-dir` quoting, and `< /dev/null`.
     - Add unit tests for `launch("cursor", ...)` (with/without effort, bracketed model override quoting like `claude-opus-4-8[context=1m,effort=high,fast=false]`, prompt/agent escaping after `--`, repeatable `--add-dir`), `binary("cursor") == "agent"`, `home_dir("cursor")` including with `XDG_CONFIG_HOME` and `OPENCODE_CONFIG_DIR` set, `user_agent_path("cursor", ...)`, `installed("cursor")`, and `available("cursor")` looking up `"agent"`.
   - `tests/test_agents_sync.py`:
     - Update wrapper count/path assertions (`3 -> 4`), kind set assertion (`line 204`: add `"cursor"`), and `_setup_two_sources` (add `.cursor`).
     - Add `_cursor` frontmatter/body tests (`readonly: true` on `read-only`, omitted on `workspace-write`/`orchestrator`, `Before starting, load these skills:` appended when skills present), `link_user` tests with and without `~/.cursor`, and `test_cursor_wrappers_frontmatter` checking committed `.cursor/agents/agent-chanchi-*.md` files (mirroring `test_claude_wrappers_frontmatter`).
     - `test_repository_wrappers_are_in_sync` checks all four harnesses including committed `.cursor/agents/agent-chanchi-*.md`.
   - `tests/test_taxonomy.py` & `tests/test_modelspec.py`: update `AGENTS` expectation; replace `"cursor:gpt"` invalid-agent sentinel with `"codex:gpt"` and verify `parse("cursor:gpt-5.4-high")` succeeds.
   - `tests/test_sync.py`: replace `"cursor"` invalid-harness sentinel with `"codex"` and verify `harness = "cursor"` is accepted in `auditors.toml`.
   - `tests/test_skills_link.py`: add test asserting `skill_targets(..., installed=only("cursor"))` emits only `skill-primary` under `.agents/skills/` (no `.cursor/skills/` duplicate).
   - `tests/test_inventory.py`: update `DEFAULT_ROOTS` and `AGENT_FILE_ROOTS` assertions; add test scanning `.cursor/skills/<name>/SKILL.md`, `.cursor/agents/<name>.md`, and skipping generated `.cursor/agents/agent-chanchi-*.md`.
   - `tests/test_mirror.py`: add `.cursor` to `world` fixture and `agent_paths`; update kind assertions (`line 135`), `test_no_installed_harness_writes_nothing` (`lines 160–164`: also remove `.cursor` and expect `"cursor"` in `skipped_harnesses`), hardcoded entry counts (`6 -> 7` on `lines 182, 486, 493`), and `index` parametrization (`[0, 1, 2, 3]` on `line 244`); verify `mirror --check` / `--remove` manage `~/.cursor/agents/`.
   - `tests/test_audits.py`: add a Cursor auditor-seat test using a dedicated `which` lookup that recognizes `"agent"` (keeping existing `ON_PATH` tests untouched), asserting the generated `launch` line carries `agent -p --trust --force --model ... --add-dir "<report-dir>" -- "Follow the agent-chanchi-auditor role ..."` and `< /dev/null`, plus a test asserting the `"not_on_path"` hint names `agent (cursor)`.
   - `tests/test_rules_budget.py`, `tests/test_items.py`, `tests/test_privacy.py`, `tests/test_layers.py`, `tests/test_feature_map.py`: all pass unchanged.

2. **Scratch CLI verification (`FEATURE_MAP.md`):**
   - Run `chanchi agents sync --check`, `chanchi agents link --user` (against scratch `HOME` containing `.cursor` and scratch `CHANCHI_DB`), `chanchi items mirror` (against scratch `HOME` + scratch `CHANCHI_SYNC` + scratch `CHANCHI_DB`), `chanchi models add --agent cursor ...` + `chanchi audit open` (against scratch `CHANCHI_DB` + scratch `CHANCHI_SYNC`), and `chanchi items scan` (against a scratch repo containing `.cursor/skills/` and `.cursor/agents/`).

3. **Live Cursor CLI smoke tests (before merging to `main`, in the implementation worktree):**
   - **(3a) Generated wrapper parsing with `# generated by ...` header:** Run one headless `agent -p --trust` check from the implementation worktree (containing the real generated `.cursor/agents/agent-chanchi-*.md` files) asking which `agent-chanchi-*` subagents appear in `<available_subagent_types>`, confirming Cursor's YAML parser accepts the `# generated by chanchi ...` first frontmatter line and `readonly: true`.
   - **(3b) Generated launch line + consumer-project `~/.cursor/agents/` read path:** From a scratch consumer workspace *without* `.cursor/agents/` (after mirroring/copying `agent-chanchi-auditor.md` into `~/.cursor/agents/` or a scratch test path), run the exact `launch` line emitted by `chanchi audit open` for `cursor:auto` (with `<report-dir>` substituted) to prove the generated launch command executes from `cwd`, reads the role file, writes a report to `<report-dir>`, and exits 0. If Cursor blocks reading `~/.cursor/agents/<agent>.md` outside workspace roots, add `--add-dir` or adjust the launch line and re-verify before merge.

4. **Owner desktop verification (manual handoff):**
   - After `chanchi agents link --user` populates `~/.cursor/agents/agent-chanchi-auditor.md` and `agent-chanchi-item-builder.md`, provide the owner a one-line prompt to run in the Cursor desktop app to confirm it recognizes the user-level subagents.
