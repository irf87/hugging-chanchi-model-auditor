# Cursor Harness Support — Brief

- **Author:** Iván R
- **Date:** 2026-11-23
- **Revision:** 1

## Request

Add Cursor (`agent` CLI; alias `cursor-agent`) as a supported harness in `chanchi`, matching the contract defined in `docs/designs/global-items.md` ("Adding a harness (Cursor, OpenAI Codex) needs an adapter row, an agent renderer in `agents_sync` for its frontmatter, its agent key in `taxonomy`, catalog rows with families, and tests; the audit procedure and the outcome rules do not change"):

1. `src/chanchi/harnesses.py`: a `cursor` key with binary `agent`, a headless launch line carrying the permission flags its auto-approval needs (`AGENTS.md`, Working Conventions; enforced by `tests/test_harnesses.py`), repeatable `--add-dir` support, and its user-level folders.
2. `src/chanchi/agents_sync.py`: a renderer for Cursor's agent format and `.cursor/agents/` folder, generated and checked like the other three (`chanchi agents sync --check`), with the profile-to-frontmatter mapping.
3. `src/chanchi/taxonomy.py`: `cursor` agent key, `chanchi models add` / `SYNC/config/auditors.toml` compatibility, and `chanchi skills link` support (verified locally whether Cursor needs its own folder or reads `.agents/skills/` natively).
4. Operational docs and rules: the harness entry-point table in `AGENTS.md` verified by a local canary test, `FEATURE_MAP.md`, `README.md`, relevant skills, and `inventory.py` default scan roots for Cursor-native items.

## Decisions taken with the owner (2026-11-23)

1. **Headless launch flags, agent role handoff, and `read-only` profile (Decision 1A):**
   - Authorize `--trust --force` for headless Cursor (`agent -p`), documented in `AGENTS.md` Working Conventions alongside `agy` and `opencode`.
   - Because `agent` has no `--agent` flag, `harnesses.launch("cursor", ...)` prefixes the prompt with an explicit role instruction pointing to `.cursor/agents/<agent>.md` or `~/.cursor/agents/<agent>.md` and omits `--mode ask`/`--mode plan` on the outer command so read-only auditors can still write their report file to `<report-dir>`.
   - `.cursor/agents/<name>.md` emits `readonly: true` for `profile: read-only`, enforcing read-only Ask mode whenever Cursor invokes the wrapper as a subagent.
2. **Operational catalog rows and `SYNC/config/auditors.toml` (Decision 2 — deferred):**
   - Omit inserting Cursor models into the operational database and omit editing `SYNC/config/auditors.toml` to add Cursor until the owner starts actively using Cursor.
   - Code, docs, and tests still support `chanchi models add --agent cursor ...` and `harness = "cursor"` in `SYNC/config/auditors.toml`, verified on a scratch `CHANCHI_DB` and `CHANCHI_SYNC`.
3. **User-level agent mirroring at `~/.cursor/agents/` (Decision 3A):**
   - Support `home_dir("cursor") = ~/.cursor` and `user_agent_path("cursor", name) = ~/.cursor/agents/{name}.md`, so `chanchi agents link --user` and `chanchi items mirror` expose user-level agents to the Cursor desktop app and self-hosted workers.
   - Document clearly that Cursor CLI (`agent`) only auto-loads `.cursor/agents/` from the project workspace (not `~/.cursor/agents/`), and hand the owner a short verification prompt for the Cursor desktop app.
4. **Execution constraints:**
   - Do not use `claude` for this change (use `agy` and free `opencode` models only).
   - Do not touch MVP phase 2 branches `feat/mvp2-s4` or `feat/mvp2-s5`, their worktrees, or `scripts/run_evals.py`.

## Facts gathered locally (2026-11-23)

All local checks ran on `agent` CLI version `2026.11.22-e9042b2` (symlinked at `~/.local/bin/agent` and `~/.local/bin/cursor-agent`, Free tier, default model `auto`) in an isolated scratch workspace outside this repository:

- **CLI flags (`agent --help`):** **VERIFIED.** Supports `-p`/`--print`, `--model <model>`, `--trust`, `-f`/`--force` (`--yolo`), `--add-dir <path>` (repeatable), `--workspace <path-or-name>`, `--mode plan|ask`, `--output-format text|json|stream-json`, `--list-models`, and positional `-- <prompt>`.
- **No `--agent` flag:** **VERIFIED.** Running `agent --agent nonexistent -p "hi"` exits 1 with `error: unknown option '--agent'`.
- **`AGENTS.md` loading (Canary 1):** **VERIFIED.** `agent -p --trust --workspace <ws>` loaded `AGENTS.md` natively into workspace rules at session start and returned the canary token (`MANGO-742`) with zero tool calls. No thin wrapper is needed.
- **Skills discovery (Canary 2):** **VERIFIED.** Without tool calls, Cursor CLI listed workspace skills from both `.cursor/skills/` and `.agents/skills/`, and listed all eight user-level `skill-chanchi-*` skills from `~/.agents/skills/` (with no `~/.cursor/skills/` folder present). `chanchi skills link` therefore covers Cursor via `.agents/skills/` and `~/.agents/skills/` without duplicating links in `.cursor/skills/`.
- **Workspace subagents & `readonly: true` (Canary 3):** **VERIFIED.** `.cursor/agents/canary-auditor.md` with YAML frontmatter `name`, `description`, `readonly: true` appeared in `<available_subagent_types>`, was invoked via the `Task` tool (`subagent_type: "canary-auditor"`), returned its token (`CANARY-AGENT-OK-333`), and ran in Ask (read-only) mode, refusing to create `blocked.txt`.
- **Headless command execution & `--add-dir` (Canary 4):** **VERIFIED.** `agent -p --trust --force --workspace <ws> --add-dir <extra>` ran `echo SHELL-OK-444` via shell without prompting and read `<extra>/note.txt` (`EXTRA-DIR-OK-555`).
- **Launch line end-to-end with `--` and read-only report write (Canary 5):** **VERIFIED.** `agent -p --trust --force --model auto --workspace <ws> --add-dir <report-dir> -- "Follow the canary-ro-report role (.cursor/agents/canary-ro-report.md): ..."` accepted `--`, read `.cursor/agents/canary-ro-report.md` (which had `readonly: true`), wrote `VERDICT: PASS` to `<report-dir>/r1.md` via shell, and made no workspace edits.
- **User-level `~/.cursor/agents/` in CLI vs desktop:** **VERIFIED** from Cursor's bundled `~/.cursor/skills-cursor/create-subagent/SKILL.md`: `.cursor/agents/` is loaded by Cursor desktop, CLI, and cloud agents; `~/.cursor/agents/` is loaded by Cursor desktop and self-hosted workers where enabled, and **not** by the CLI or hosted cloud agents. Live behavior in the Cursor desktop app is **UNVERIFIED** until the owner runs the handoff prompt.
- **Model catalog & Free tier limits:** `agent --list-models` prints ~280 IDs that bake effort/variants into the ID (e.g. `gpt-5.3-codex-high`, `grok-4.7-high`, `composer-2.5`, `auto`) and documents bracket overrides (`'model[effort=high]'`) — **VERIFIED**. Which non-`auto` models are runnable under the Free tier is **UNVERIFIED**.
- **Built-in skills directory:** Cursor reserves `~/.cursor/skills-cursor/` for internal built-in skills (`create-skill/SKILL.md`: never write custom skills there) — **VERIFIED**.
