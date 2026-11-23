VERDICT: PASS WITH FIXES

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| S3-01 | minor | `AGENTS.md` L119-120 | Text says "skip-permissions flag" for all three harnesses (`agy`, `opencode`, `claude`), whereas `opencode`'s installed CLI flag is `--auto` ("Auto-approve permissions that are not explicitly denied"), not a `skip-permissions` flag. An agent that does not check `opencode --help` first could guess `--dangerously-skip-permissions`. | `agy --help` prints `--dangerously-skip-permissions  Auto-approve all tool permission requests without prompting`; `opencode --help` and `opencode run --help` print `--auto  Auto-approve permissions that are not explicitly denied` and have no `skip-permissions` flag. | Say "skip-permissions or auto-approve flag" (or note that agents check the harness's local CLI help per Core Rule 4). |
| S3-02 | minor | `AGENTS.md` L117-121 | The rule opens with "When delegating to another harness" and scopes the permission to "Delegated executors", which is slightly narrower than the owner's request (all `agy`, `opencode`, and pane-launched `claude` runs in the delegation flow) and creates minor ambiguity when delegating to Claude in another pane (same harness) or to non-executor agents (`agent-chanchi-item-builder`, `agent-chanchi-researcher`). | Owner request names `agy`, `claude (only when it runs in another herdr pane)`, and `opencode` without restricting to executors; `AGENTS.md` L117-123 bounds the rule by "worktree and scratch database" for "Delegated executors". | Clarify whether "Delegated executors" intentionally limits auto-approval to worktree-isolated executors or covers any delegated pane session (e.g., "When delegating a session to another pane or harness..."). |

## Summary of Checks

- **Count (open):** 0 blocking, 0 major, 2 minor.
- **1. Faithfulness to owner's request:** Faithful on harnesses (`agy`, `opencode`, `claude`), the `claude` condition ("when it runs in another terminal pane (not as an in-process subagent)"), explicit owner authorization (`2026-11-22`), and rationale ("a permission prompt would stop the flow"). Uses "another terminal pane" rather than naming `herdr` directly, keeping `AGENTS.md` tool-agnostic while preserving the exact boundary; the global `herdr` skill itself lives outside this repository in `SYNC/`. Minor scope narrowing noted in `S3-02`.
- **2. Consistency with `AGENTS.md` and `agents/agent-chanchi-executor/AGENT.md`:** Consistent with Core Rule 1 (minimizes human bottlenecks), Core Rule 3 (English), Core Rule 4 (harness agnostic), and `agents/agent-chanchi-executor/AGENT.md` (which relies on worktree/branch isolation and a scratch `CHANCHI_DB`, matching the stated safety boundary). No conflict with `src/chanchi/harnesses.py` (which only builds headless `chanchi audit open` launch lines for `agent-chanchi-auditor`).
- **3. Harness-agnosticism, clarity, and line budget:** Harness-agnostic and clear aside from the `opencode` flag naming nuance (`S3-01`). `AGENTS.md` is 133 lines (`<= 150` budget). Locally verified:
  - `uv run pytest --confcutdir=tests tests/test_rules_budget.py tests/test_agent_rules.py tests/test_privacy.py` -> `19 passed`
  - `uv run pytest --confcutdir=tests -q` -> `911 passed`
  - `uv run ruff check` -> `All checks passed!`
- **4. Rule or check? (`skill-chanchi-item-authoring`):** Text in `AGENTS.md` is appropriate; no code check can enforce this. `chanchi` never launches harnesses (`src/chanchi/harnesses.py`), delegated executors in terminal panes are started outside `chanchi`, and recording owner authorization so agents do not treat the flag as a safety violation is policy text rather than a statically verifiable invariant.

## Environment Notes

- Default `uv run pytest` collection failed in this sandbox with `PermissionError` while scanning the `SYNC` symlink at the repository root; passing `--confcutdir=tests` ran the full suite (`911 passed`).
- `opencode --help` and `opencode run --help` required redirecting `HOME` and `XDG_*` to a temporary directory under `/tmp` because `~/.local/state/opencode` was blocked by the sandbox.
- `claude --help` could not be executed in this sandbox (`operation not permitted`).
