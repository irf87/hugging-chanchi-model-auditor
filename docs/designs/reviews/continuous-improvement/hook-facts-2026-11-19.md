# Hook facts report

- **Date:** 2026-11-19
- **CLI versions:**
  - `claude --version`: `2.1.328 (Claude Code)`
  - `agy --version`: `1.5.12`
  - `opencode --version`: `opencode v2.2.6`

---

## Q1 Claude Code

Lab folder: `lab/claude-q1/` (`.claude/settings.json`, `.claude/hooks/probe.py`, `.claude/agents/probe-worker.md`).

### (a) `agent_type` in hook input with `--agent <name>` vs without `--agent`
- **Answer:** `yes` (`agent_type` is present in `SessionStart`, `PreToolUse`, and `Stop` when started with `--agent <name>`, and absent from all three when started without `--agent`).
- **Evidence:**
  - **Pass case (with `--agent probe-worker`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- claude -p --agent probe-worker --allowedTools Bash -- "Run the bash command: echo PROBE_AGENT_MAIN"`
    - Log lines (`lab/claude-q1/q1a_with_agent.jsonl`, trimmed):
      - `{"session_id": "b05ac049-5711-4b59-8b0c-184822b1cdca", ..., "agent_type": "probe-worker", "hook_event_name": "SessionStart", "source": "startup"}`
      - `{"session_id": "b05ac049-5711-4b59-8b0c-184822b1cdca", ..., "permission_mode": "default", "agent_type": "probe-worker", ..., "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "echo PROBE_AGENT_MAIN", ...}}`
      - `{"session_id": "b05ac049-5711-4b59-8b0c-184822b1cdca", ..., "permission_mode": "default", "agent_type": "probe-worker", ..., "hook_event_name": "Stop", "stop_hook_active": false, ...}`
  - **Contrasting case (without `--agent`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- claude -p --allowedTools Bash -- "Run the bash command: echo PROBE_NO_AGENT"`
    - Log lines (`lab/claude-q1/q1a_no_agent.jsonl`, trimmed):
      - `{"session_id": "b8c79425-fa28-4499-8b5c-1079c9be70f0", ..., "hook_event_name": "SessionStart", "source": "startup"}` (no `agent_type`)
      - `{"session_id": "b8c79425-fa28-4499-8b5c-1079c9be70f0", ..., "permission_mode": "default", "effort": {"level": "medium"}, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "echo PROBE_NO_AGENT", ...}}` (no `agent_type`)
      - `{"session_id": "b8c79425-fa28-4499-8b5c-1079c9be70f0", ..., "hook_event_name": "Stop", "stop_hook_active": false, ...}` (no `agent_type`)

### (b) Subagent vs parent `PreToolUse`: `session_id`, `agent_type`, `agent_id`
- **Answer:** `yes` (subagent `PreToolUse` shares the parent's `session_id` and adds both `agent_id` and `agent_type`; parent without `--agent` has neither `agent_id` nor `agent_type`).
- **Evidence:**
  - Command: `perl -e 'alarm 120; exec @ARGV' -- claude -p --allowedTools Bash Agent -- "First run the bash command 'echo PROBE_PARENT' yourself, then spawn the probe-worker subagent using the Agent tool to run the bash command 'echo PROBE_SUBAGENT'."`
  - **Parent `PreToolUse` (`echo PROBE_PARENT`, `lab/claude-q1/q1b_subagent.jsonl`):**
    - `session_id`: `"7767b6a1-0791-4e01-b14e-bef80de09f80"`, `agent_type`: absent, `agent_id`: absent.
    - Log line (trimmed): `{"session_id": "7767b6a1-0791-4e01-b14e-bef80de09f80", ..., "permission_mode": "default", "effort": {"level": "medium"}, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "echo PROBE_PARENT", ...}, "tool_use_id": "toolu_01SvMvBHWbHR7aSMuBqMtwPV"}`
  - **Subagent `PreToolUse` (`echo PROBE_SUBAGENT`, `lab/claude-q1/q1b_subagent.jsonl`):**
    - `session_id`: `"7767b6a1-0791-4e01-b14e-bef80de09f80"` (identical to parent), `agent_type`: `"probe-worker"`, `agent_id`: `"a539570c699c4a938"`.
    - Log line (trimmed): `{"session_id": "7767b6a1-0791-4e01-b14e-bef80de09f80", ..., "permission_mode": "default", "agent_id": "a539570c699c4a938", "agent_type": "probe-worker", "effort": {"level": "medium"}, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "echo PROBE_SUBAGENT", ...}, "tool_use_id": "toolu_01MxQEqJAyzWQNbzGPPFHdYA"}`

### (c) `session_id` and `SessionStart.source` after `claude -p --resume <id>`
- **Answer:** `yes` (`session_id` stays the same; `SessionStart` reports `"source": "resume"`).
- **Evidence:**
  - **Resume case:**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- claude -p --resume 7767b6a1-0791-4e01-b14e-bef80de09f80 --allowedTools Bash -- "Run the bash command: echo PROBE_RESUMED"`
    - Log line (`lab/claude-q1/q1c_resume.jsonl`, trimmed):
      `{"session_id": "7767b6a1-0791-4e01-b14e-bef80de09f80", ..., "hook_event_name": "SessionStart", "source": "resume", "seconds_since_last_response": 22, "context_tokens": 36667, ...}`
  - **Contrasting fresh startup case (from Q1(a) without `--agent`):**
    - Log line (`lab/claude-q1/q1a_no_agent.jsonl`, trimmed):
      `{"session_id": "b8c79425-fa28-4499-8b5c-1079c9be70f0", ..., "hook_event_name": "SessionStart", "source": "startup"}`

### (d) `PreToolUse` JSON deny (`permissionDecision: "deny"`, exit 0)
- **Answer:** `yes` (blocks `echo PROBE_BLOCK_ME` and lets `echo PROBE_ALLOW` run).
- **Evidence:**
  - Command: `perl -e 'alarm 120; exec @ARGV' -- claude -p --output-format stream-json --verbose --allowedTools Bash -- "Run 'echo PROBE_BLOCK_ME' and 'echo PROBE_ALLOW' using Bash."`
  - **Blocked case (`echo PROBE_BLOCK_ME`):**
    - Hook printed `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "probe"}}` and exited `0`.
    - CLI stream output (trimmed): `{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"PreToolUse:Bash hook error: probe","is_error":true,"tool_use_id":"toolu_01GKjzaqovfUZ2tJLka5YoYY"}]},...,"tool_use_result":"Error: PreToolUse:Bash hook error: probe","tool_result_meta":[{"id":"toolu_01GKjzaqovfUZ2tJLka5YoYY","non_execution_kind":"permission-rule","permission_decision":{"decision":"reject","source":"hook","reason_type":"hook"}}]}`
  - **Allowed case (`echo PROBE_ALLOW`):**
    - Hook exited `0` with no stdout.
    - CLI stream output (trimmed): `{"type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01MmCGiHf64Cs41LfNzo5aNb","type":"tool_result","content":"PROBE_ALLOW","is_error":false}]},...,"tool_use_result":{"stdout":"PROBE_ALLOW","stderr":"","interrupted":false,"isImage":false,"noOutputExpected":false},"tool_result_meta":[{"id":"toolu_01MmCGiHf64Cs41LfNzo5aNb","permission_decision":{"decision":"accept","source":"config","reason_type":"rule"}}]}`

---

## Q2 agy

Lab folders: `lab/agy-q2/` (`.agents/hooks.json`, `.agents/hooks/probe.py`, `.agents/agents/probe-agent/agent.md`) and `lab/agy-q2-nohooks/`.

### (a) Exact field name and value of conversation id in `SessionStart`, `PreToolUse`, `Stop`
- **Answer:** `yes` — `"conversationId"` (camelCase) in all three events (e.g., `"ed184bd9-4d9d-4fb3-a7cd-cd045d3cd774"`). (Note: `--output-format stream-json` CLI events use `"conversation_id"`, while hook stdin payloads use `"conversationId"`.)
- **Evidence:**
  - Command (run 1): `perl -e 'alarm 120; exec @ARGV' -- agy -p "Run the command 'echo PROBE_AGY_1' using run_command."`
  - Log lines (`lab/agy-q2/q2a_no_agent.jsonl`, trimmed):
    - `{"artifactDirectoryPath": "...", "conversationId": "ed184bd9-4d9d-4fb3-a7cd-cd045d3cd774", "cwd": ".../lab/agy-q2", "hookEventName": "SessionStart", ..., "modelName": "claude-sonnet-5-5-low", ...}`
    - `{"artifactDirectoryPath": "...", "conversationId": "ed184bd9-4d9d-4fb3-a7cd-cd045d3cd774", ..., "hookEventName": "PreToolUse", ..., "stepIdx": 2, "toolCall": {"args": {"CommandLine": "echo PROBE_AGY_1", ...}, "name": "run_command"}, ...}`
    - `{"artifactDirectoryPath": "...", "continuationActive": false, "conversationId": "ed184bd9-4d9d-4fb3-a7cd-cd045d3cd774", ..., "hookEventName": "Stop", ..., "terminationReason": "NO_TOOL_CALL", ...}`
  - Contrasting run (`lab/agy-q2/q2b_first.jsonl`): `agy --agent probe-agent -p "Say OK."` produced a distinct `"conversationId": "662ba895-38bc-4626-9726-75bc795599c8"`.

### (b) Is agent name present in any hook input field when started with `agy --agent <name>`?
- **Answer:** `no` (not present in `SessionStart`, `PreToolUse`, or `Stop`, even when the project agent in `.agents/agents/probe-agent/agent.md` is confirmed loaded).
- **Evidence:**
  - **With `--agent probe-agent`:**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- agy --agent probe-agent -p "Use read_file to read .agents/agents/probe-agent/agent.md and tell me its name field."`
    - Observed stdout: `The \`name\` field is \`probe-agent\`. AGENT_DIR_LOADED` (confirming `agent.md` instructions loaded).
    - Contrasting invalid-agent check: `agy --agent nonexistent-probe-xyz -p "Say OK."` exited `1` with `error: unknown agent "nonexistent-probe-xyz" (available: ..., probe-agent)`.
    - Log lines (`lab/agy-q2/q2b_pretool.jsonl`, trimmed):
      - `SessionStart`: keys `artifactDirectoryPath, conversationId, cwd, hookEventName, lastUserInput, modelName, transcriptPath, workspacePaths` (no agent field).
      - `PreToolUse`: `{"conversationId": "a6ac2aea-9bae-4ff7-a1a0-734bc1e85f3a", ..., "hookEventName": "PreToolUse", ..., "stepIdx": 2, "toolCall": {"args": {"Path": ".../agent.md"}, "name": "read_file"}, ...}` (no agent field).
      - `Stop`: `{"continuationActive": false, "conversationId": "a6ac2aea-9bae-4ff7-a1a0-734bc1e85f3a", ..., "hookEventName": "Stop", ..., "terminationReason": "NO_TOOL_CALL", ...}` (no agent field).
  - **Without `--agent`:**
    - `lab/agy-q2/q2a_no_agent.jsonl` has the exact same key set across `SessionStart`, `PreToolUse`, and `Stop`.

### (c) Can `SessionStart` output put text into the model's context?
- **Answer:** `yes` when outputting structured `injectSteps` JSON (`{"injectSteps":[{"systemMessage":{"systemMessage":"..."}}]}`); `no` when outputting a plain-text line on stdout.
- **Evidence:**
  - **Pass case (`injectSteps` JSON):**
    - Hook stdout: `{"injectSteps": [{"systemMessage": {"systemMessage": "Startup token: PROBE_START_TOKEN_JSON_835194"}}]}`
    - Command: `PROBE_SESSION_MODE=json_inject perl -e 'alarm 120; exec @ARGV' -- agy -p "Repeat any startup token you were given at session start, or say NONE if none."`
    - Observed stdout: ``The startup token I was given at session start is: `PROBE_START_TOKEN_JSON_835194` `` (exit `0`).
  - **Fail case (plain-text stdout line) & empty control:**
    - Hook stdout (`PROBE_SESSION_MODE=plain`): `PROBE_START_TOKEN_PLAIN_947261`
    - Command: `PROBE_SESSION_MODE=plain perl -e 'alarm 120; exec @ARGV' -- agy -p "Repeat any startup token you were given at session start, or say NONE if none."`
    - Observed stdout: `NONE` (exit `0`).
    - Hook stdout (`PROBE_SESSION_MODE=empty`): `{}` -> observed stdout: `NONE. I wasn't given any startup token at the start of this session.` (exit `0`).

### (d) Is workspace-level `.agents/hooks.json` loaded at all?
- **Answer:** `yes` (`$R/lab/agy-q2/.agents/hooks.json` was loaded and executed `SessionStart`, `PreToolUse`, and `Stop`, even without a `.git` repository).
- **Evidence:**
  - **Pass case (workspace with `.agents/hooks.json`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- agy -p "Run the command 'echo PROBE_AGY_1' using run_command."` in `lab/agy-q2/`
    - Result: `lab/agy-q2/hooks.jsonl` recorded `SessionStart`, `PreToolUse`, and `Stop`.
  - **Contrasting case (workspace without `.agents/hooks.json`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- agy -p "Say OK."` in `lab/agy-q2-nohooks/`
    - Result: `wc -l ../agy-q2/hooks.jsonl` remained `4` before and after, confirming hooks were loaded from `lab/agy-q2/.agents/hooks.json` and not global config.

---

## Q3 agy (`PreToolUse` on `run_command`)

- **Answer:** `yes` — shell command field path is `toolCall.args.CommandLine`; blocking output shape is `{"decision": "deny", "reason": "..."}` (exit `0`), which blocks `echo PROBE_BLOCK_ME` while `{"decision": "allow"}` lets `echo PROBE_ALLOW` run.
- **Evidence:**
  - Command: `perl -e 'alarm 120; exec @ARGV' -- agy --output-format stream-json -p "Run 'echo PROBE_BLOCK_ME' using run_command, and also run 'echo PROBE_ALLOW' using run_command. Report what happened for each."`
  - **Hook stdin (`PreToolUse`, `lab/agy-q2/hooks.jsonl`, trimmed):**
    - `{"conversationId": "340b0b9d-f927-4e63-9e6b-36ce1bcbafcb", ..., "hookEventName": "PreToolUse", ..., "stepIdx": 2, "toolCall": {"args": {"CommandLine": "echo PROBE_BLOCK_ME", "WaitMsBeforeAsync": 3000, "toolSummary": "Echo block probe"}, "id": "toolu_vrtx_019SbK6a1fz8yAnJN7pgkUT2", "name": "run_command"}}`
  - **Blocked case (`echo PROBE_BLOCK_ME`, hook stdout `{"decision": "deny", "reason": "probe blocked"}`):**
    - Stream output (`lab/agy-q2/q3_stream.jsonl`): `{"event":"step_update","step_update":{...,"step_index":2,"state":"ERROR","step_type":"tool","tool_name":"run_command",...,"tool_info":{"name":"run_command","parameters":{"CommandLine":"echo PROBE_BLOCK_ME"},"error":{"type":"TOOL_ERROR","message":"tool call denied by pre-tool hook: probe blocked"}}}}`
  - **Allowed case (`echo PROBE_ALLOW`, hook stdout `{"decision": "allow"}`):**
    - Stream output (`lab/agy-q2/q3_stream.jsonl`): `{"event":"step_update","step_update":{...,"step_index":3,"state":"DONE","step_type":"tool","tool_name":"run_command",...,"tool_info":{"name":"run_command","parameters":{"CommandLine":"echo PROBE_ALLOW"},"output":"...\nCommand exited with code 0.\n\nCommand output:\nPROBE_ALLOW\r\n"}}}`

---

## Q4 opencode

Lab folder: `lab/opencode-q4/` (`.opencode/plugins/probe.js`, `.opencode/agents/probe-agent.md`). Runs used authenticated model `-m opencode-go/glm-5.3-flash` with `--standalone --auto` and `</dev/null`.

### (a) Which plugin API is called: `server()` (V1) or `setup()` (V2)?
- **Answer:** `setup()` (V2) — requires `export default { id: "...", setup(ctx) { ... } }`; `server()` (V1) is not called, and named exports without `export default` fail plugin loading.
- **Evidence:**
  - **Pass case (`export default { id: "probe", server, setup }`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- opencode run --standalone --auto -m opencode-go/glm-5.3-flash "Run 'echo PROBE_ALLOW' using bash." </dev/null`
    - Log (`lab/opencode-q4/q4a_allow.jsonl`): `{"ts":"...","kind":"called","fn":"setup","ctxShape":{...}}` — `server()` was never called.
  - **Fail case (named exports `export async function server` and `export async function setup` with no `export default`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- opencode run --standalone --auto --print-logs --log-level debug -m opencode-go/claude-haiku-5-5 "Say OK" </dev/null`
    - Observed server log: `level=WARN ... message="failed to load plugin" ... cause="Cause([Fail(PluginModule.LoadError: Plugin must export a default definition with an id and an effect or setup function. (cause: SchemaError(Missing key\n  at [\"default\"])))])"` (neither `server` nor `setup` ran).

### (b) Does throwing inside `"tool.execute.before"` block `echo PROBE_BLOCK_ME` while `echo PROBE_ALLOW` runs?
- **Answer:** `no` for the literal hook name `"tool.execute.before"` (never invoked in V2); `yes` for V2 `ctx.tool.hook("execute.before", ...)` (where tool is `"shell"` and command is `arg1.input.command`).
- **Evidence:**
  - Command: `perl -e 'alarm 120; exec @ARGV' -- opencode run --standalone --auto --format json -m opencode-go/glm-5.3-flash "Try to run 'echo PROBE_BLOCK_ME' using shell/bash, and also run 'echo PROBE_ALLOW' using shell/bash. Report what happened for each." </dev/null`
  - **Not-invoked case (`"tool.execute.before"`):**
    - Both returning `{"tool.execute.before": ...}` from `setup()` and calling `ctx.tool.hook("tool.execute.before", ...)` logged `0` invocations in `q4a_allow.jsonl` and `q4b_block_allow.jsonl`.
  - **Blocked vs allowed cases via `ctx.tool.hook("execute.before", ...)` (`lab/opencode-q4/q4b_block_allow.jsonl`):**
    - Log (`echo PROBE_BLOCK_ME`): `{"kind":"tool.hook","name":"execute.before","arg1":{"tool":"shell","sessionID":"ses_e0b20a5a8ffePWxdKucDGDwonf","agent":"build",...,"input":{"command":"echo PROBE_BLOCK_ME"}}}` -> handler threw `new Error("probe blocked: PROBE_BLOCK_ME")`; no `execute.after` fired; CLI JSON emitted `"tool":"shell","state":{"status":"error","input":{"command":"echo PROBE_BLOCK_ME"},"error":"probe blocked: PROBE_BLOCK_ME",...}`.
    - Log (`echo PROBE_ALLOW`): `{"kind":"tool.hook","name":"execute.before",...,"input":{"command":"echo PROBE_ALLOW"}}` followed by `{"kind":"tool.hook","name":"execute.after",...,"status":"completed","result":{...,"metadata":{"status":"completed","truncated":false,"exit":0}}}`; CLI JSON emitted `"tool":"shell","state":{"status":"completed","input":{"command":"echo PROBE_ALLOW"},"output":"PROBE_ALLOW\n",...}`.

### (c) Does any event or hook input carry the agent name with `opencode run --agent <name>`?
- **Answer:** `yes` (`execute.before` and `execute.after` hook inputs carry `"agent": "<name>"`).
- **Evidence:**
  - **Pass case (`--agent probe-agent`, defined in `.opencode/agents/probe-agent.md`):**
    - Command: `perl -e 'alarm 120; exec @ARGV' -- opencode run --standalone --auto --format json -m opencode-go/glm-5.3-flash --agent probe-agent "Run 'echo PROBE_AGENT' using shell." </dev/null`
    - Log (`lab/opencode-q4/q4c_agent.jsonl`, trimmed): `{"kind":"tool.hook","name":"execute.before","arg1":{"tool":"shell","sessionID":"ses_e0b2034e0ffeYbIM30544Z5MHU","agent":"probe-agent",...,"input":{"command":"echo PROBE_AGENT"}}}`
  - **Contrasting case (without `--agent`):**
    - Log (`lab/opencode-q4/q4b_block_allow.jsonl`, trimmed): `{"kind":"tool.hook","name":"execute.before","arg1":{"tool":"shell","sessionID":"ses_e0b20a5a8ffePWxdKucDGDwonf","agent":"build",...,"input":{"command":"echo PROBE_ALLOW"}}}`

### (d) Does session id stay the same when reopened with `opencode -s <id>`?
- **Answer:** `UNVERIFIED` for TUI `opencode -s <id>` (skipped because the TUI cannot run non-interactively); `yes` for `opencode run -s <id>`.
- **Evidence:**
  - **TUI (`opencode -s <id>`):**
    - Command: `perl -e 'alarm 8; exec @ARGV' -- opencode -s ses_e0b2034e0ffeYbIM30544Z5MHU </dev/null`
    - Observed output: rendered interactive TUI (`Switched agent to Probe-Agent ... PROBE_AGENT`) and hung until killed by the 8s alarm (`TUI_EXIT=142`).
  - **Non-interactive `opencode run -s <id>` vs fresh `opencode run`:**
    - Command: `perl -e 'alarm 60; exec @ARGV' -- opencode run --standalone --auto --format json -m opencode-go/glm-5.3-flash -s ses_e0b2034e0ffeYbIM30544Z5MHU "Run 'echo PROBE_RESUMED' using shell." </dev/null`
    - Log (`lab/opencode-q4/plugin.jsonl`, trimmed): `{"kind":"tool.hook","name":"execute.before","arg1":{"tool":"shell","sessionID":"ses_e0b2034e0ffeYbIM30544Z5MHU","agent":"probe-agent",...,"input":{"command":"echo PROBE_RESUMED"}}}` (same `sessionID`, vs fresh run creating a new ID such as `ses_e0b2034e0ffeYbIM30544Z5MHU`).

---

## Q5 Versions & Sources

- **CLI `--version` outputs:**
  - `claude --version`: `2.1.328 (Claude Code)`
  - `agy --version`: `1.5.12`
  - `opencode --version`: `opencode v2.2.6`
- **Source of agy facts (Q2 & Q3):**
  - Every agy fact in Q2(a)–(d) and Q3 came from **direct empirical observation** of `agy` `1.5.12` runs in `lab/agy-q2/` and `lab/agy-q2-nohooks/`.
  - `/Users/irf87/.gemini/antigravity-cli/cache/CHANGELOG.md` could not be read (`read_file` returned `Permission denied ... Matches hardcoded system protection boundary rule`), so no changelog line citations are claimed from that file.
  - `/Users/irf87/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/hooks.md` (lines 1–429) and `agy changelog` (lines for `1.5.12`–`1.5.7`) were read only as background reference to configure the probes.

---

## Summary table

| Question | Answer | Confidence |
| --- | --- | --- |
| Q1(a) Claude `agent_type` with `--agent` vs without | `yes` (present in all 3 events with `--agent`, absent without) | High |
| Q1(b) Claude subagent `session_id`, `agent_type`, `agent_id` | `yes` (same `session_id`; subagent adds `agent_id` + `agent_type`) | High |
| Q1(c) Claude `--resume` keeps `session_id` & `source: "resume"` | `yes` (`session_id` preserved; `SessionStart.source == "resume"`) | High |
| Q1(d) Claude `PreToolUse` JSON deny blocks `PROBE_BLOCK_ME` | `yes` (`PROBE_BLOCK_ME` rejected by hook; `PROBE_ALLOW` ran) | High |
| Q2(a) agy conversation id field in all 3 events | `yes` (`conversationId` in `SessionStart`, `PreToolUse`, `Stop`) | High |
| Q2(b) agy `--agent <name>` present in hook input | `no` (agent loaded, but no agent field in any hook input) | High |
| Q2(c) agy `SessionStart` puts text in context | `yes` via `injectSteps` JSON; `no` via plain stdout | High |
| Q2(d) agy workspace `.agents/hooks.json` loaded | `yes` (loaded and fired in `lab/agy-q2/` without `.git`) | High |
| Q3 agy `run_command` path & block shape | `yes` (`toolCall.args.CommandLine`; `{"decision":"deny","reason":"..."}`) | High |
| Q4(a) opencode plugin API (`server()` V1 vs `setup()` V2) | `setup()` (V2, `export default { id, setup }`) | High |
| Q4(b) opencode throwing in `"tool.execute.before"` | `no` for `"tool.execute.before"` (uncalled); `yes` for V2 `ctx.tool.hook("execute.before", ...)` | High |
| Q4(c) opencode `--agent <name>` in hook input | `yes` (`agent` field in `execute.before` / `execute.after`) | High |
| Q4(d) opencode `-s <id>` keeps session id | `UNVERIFIED` for TUI `opencode -s` (interactive only); `yes` for `opencode run -s` | High |
| Q5 Versions & agy fact sources | Observed `--version`; all agy facts empirically observed | High |
