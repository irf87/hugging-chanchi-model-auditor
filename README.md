# chanchi

A local, agent-first auditor for multi-agent coding work. The orchestrating agent records every
executor session and every incident found while auditing it; `chanchi` turns those audits into
scores and recommends which `(agent, model, effort)` to use for a given task type and complexity.

- **Local only:** one SQLite database at `~/.local/share/chanchi/chanchi.db` (override with
  `CHANCHI_DB`). Nothing leaves the machine.
- **Agent-first:** JSON output by default (`--format text` for humans), structured errors with
  `field`, `valid_values` and `hint`.
- **No runtime dependencies:** Python ≥ 3.11 standard library.

Design: `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md`.

## Install

```bash
uv tool install --editable .
```

`--editable` keeps this checkout as the live source, which the skill symlinks rely on. The first
command that opens the database (anything except `chanchi db status` and `chanchi db migrate --template`) creates the operational database by copying the committed template.

## Give the skills to a project

```bash
chanchi skills link /path/to/project
```

This creates `.agents/skills/chanchi-*` (read by opencode and agy) and `.claude/skills/chanchi-*`
(read by Claude Code) as symlinks to this repository, and prints a line to add to the project's
`openspec/config.yaml`. `chanchi skills link --global` does the same in your home directory;
`chanchi skills unlink` removes only the links it created.

- `chanchi-model-selection` — used while planning: asks `chanchi recommend` for each session.
- `chanchi-session-audit` — used while orchestrating: records sessions, incidents and verdicts.

## Everyday commands

```bash
chanchi models add --agent agy --model gemini-3.8-flash-high --cost 1 --efforts low,medium,high
chanchi recommend --task-type ui-component --complexity medium --available "agy:gemini-3.8-flash-high:high,claude:sonnet:medium"
chanchi stats --by task-type
chanchi stats --by dimension
chanchi show <change-ref>
chanchi scoring explain
chanchi taxonomy list
```

Commands detect the project from git (deriving the slug from the main repository across git worktrees); `--project` still overrides.

## Exploration

At `low` and `medium` complexity, `chanchi recommend` also returns an `explore` list of up to 3 models where no listed effort has 3 or more audited sessions of the requested task type (excluding the `recommendation` model and models red-flagged on 3 or more sessions). This lets planners gather initial audits for untested models without changing the evidence-based `recommendation`.

Planners keep exploration within a budget of `max(1, floor(n / 4))` sessions for a change of `n` executor sessions (`0` when `n` is 1), start each explore session and its retries with `--tags explore`, and verify the count and `over_budget` in the `exploration` block of `chanchi show <change>`.

## Capabilities

Planners can filter recommendations by model capability with `--require`:

```bash
chanchi recommend --task-type ui-component --complexity low --require vision --available "..."
```

Only models with `vision=yes` stay in `candidates` and `explore`; models with `no` or `unknown` are listed in `excluded`. If none remain, `recommendation` is `null` with `reason: no_capable_candidates`.

The owner classifies models (`yes`, `no`, or `unknown` to clear) on `agent:model` (`models set` rejects `agent:model:effort`):

```bash
chanchi models set <agent:model> --capability vision=yes
```

## Databases and migrations

| | Template | Operational |
|---|---|---|
| Path | `src/chanchi/data/template.db` | `~/.local/share/chanchi/chanchi.db` |
| Content | schema + seed rows | your data |
| In git | committed | never |

Every migration affects both. To add one:

1. Add `src/chanchi/migrations/NNN_<name>.sql`.
2. Run `uv run chanchi db migrate --template` and commit the SQL file and `template.db` together.
3. The operational database migrates itself on its next command, after a `chanchi.db.bak-v<N>`
   backup (the three most recent are kept).

`tests/test_db.py` fails if the template drifts from the migrations.

## Development

```bash
uv run pytest
```
