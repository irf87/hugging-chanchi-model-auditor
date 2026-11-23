---
name: skill-chanchi-verify
description: Use when you changed chanchi and must prove the change works before handing it off. Runs the affected FEATURE_MAP.md entries on a scratch database and the gate, and reports evidence. Not for auditing someone else's session (that is skill-chanchi-session-audit).
---

# chanchi — verify

Prove the change with evidence an auditor can rerun. Never touch the operational database.

## Launch
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    uv run chanchi db status        # must show the scratch path

## Doctor
`chanchi db status` (run as `uv run chanchi db status`) reports the scratch path and `uv run pytest -q` is green before you
start. If not, stop and report: the starting state is broken, not your change.

## Drive
Open `FEATURE_MAP.md`, find every entry for a command your change touches, and run its "How to
get to it" and "Driving it" commands as written. For a new command, write its entry first.

## Evidence
For each command: the exact command and its last output line, plus the state it must leave
(the row or status `chanchi show`, `chanchi lesson show` or `chanchi db status` reports), not only
the exit code. Finish with `scripts/check` and its last line.

## Cleanup
Delete the scratch directory only after the evidence is in your report. Never delete evidence.

## Helpers
After a harness upgrade, check that agents still load: `agy agents` (in a trusted folder) and
`opencode debug agents` list the `agent-chanchi-*` agents,
`claude -p --agent agent-chanchi-researcher --permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" -- "Name the test that guards the import layers."`
answers `tests/test_layers.py`, re-run each adapter's launch template (`src/chanchi/harnesses.py`)
once with `agent-chanchi-auditor` and a trivial prompt, and run `chanchi agents link --user --check` and,
when `SYNC` holds published global items, `chanchi items mirror --check`.
If agy tool names changed, update `AGY_*_TOOLS` in `src/chanchi/agents_sync.py` and run
`chanchi agents sync`.
