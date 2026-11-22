# chanchi

A local, agent-first auditor for multi-agent coding work. The orchestrating agent records every
executor session and every incident found while auditing it; `chanchi` turns those audits into
scores and recommends which `(agent, model, effort)` to use for a given task type and complexity.

- **Local only:** one SQLite database at `~/.local/share/chanchi/chanchi.db` (override with
  `CHANCHI_DB`). The `chanchi` package imports no network module; one maintainer script in
  `scripts/` fetches public benchmark metadata into a committed file.
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

## Development gate

`scripts/check` runs ruff and the test suite. Turn on the git hooks once per clone, so every merge
and push runs it, and keep merges as merge commits so the merge hook fires:

    git config core.hooksPath .githooks
    git config merge.ff false

GitHub Actions runs the same script on every push (`.github/workflows/check.yml`).

## Give the skills to a project

```bash
chanchi skills link /path/to/project
```

This creates `.agents/skills/skill-chanchi-*` (read by opencode and agy) and `.claude/skills/skill-chanchi-*`
(read by Claude Code) as symlinks to this repository, and prints a line to add to the project's
`openspec/config.yaml`. `chanchi skills link --global` does the same in your home directory;
`chanchi skills unlink` removes only the links it created.

`--global` also keeps `chanchi-<n>` compatibility links in `~/.agents/skills` and `~/.claude/skills`
for projects that still use the old names; `--global --no-compat` removes them once those projects
are updated.

- `skill-chanchi-model-selection` — used while planning: asks `chanchi recommend` for each session.
- `skill-chanchi-session-audit` — used while orchestrating: records sessions, incidents and verdicts.
- `skill-chanchi-lessons` — used by writer roles at the end of a conversation, and in maintenance
  conversations that review lessons.

## Agents

chanchi's own agents are written once in `agents/agent-chanchi-<name>/AGENT.md` and compiled into
committed wrappers for Claude Code (`.claude/agents/`), opencode (`.opencode/agents/`) and agy
(`.agents/agents/`). Never edit a wrapper by hand:

```bash
chanchi agents sync                  # regenerate the wrappers after editing a source
chanchi agents sync --check          # fail if any wrapper is stale (part of scripts/check)
chanchi agents link --user           # compile install: user agents into installed user harness folders
chanchi agents link --user --check   # fail if user wrappers or manifest are stale
chanchi agents link --user --remove  # remove user wrappers owned by this repository
```

- `agent-chanchi-orchestrator` — plans, assigns executors, audits, records, merges.
- `agent-chanchi-executor` — implements one brief in a worktree and reports; never commits.
- `agent-chanchi-researcher` — read-only research with VERIFIED/UNVERIFIED claims.
- `agent-chanchi-auditor` — read-only user-installed auditor that checks one subject against a brief and writes a verdict report.

Launch one with `claude --agent <name>`, `opencode run --agent <name>` or
`agy --agent <name>` (headless: `agy --agent <name> -p="<prompt>"`). `FEATURE_MAP.md` tells an
agent how to reach and verify every command. Design: `docs/designs/chanchi-agents-mvp.md`.

## Everyday commands

```bash
chanchi models add --agent agy --model gemini-3.8-flash-high --cost 1 --efforts low,medium,high
chanchi models set <agent:model> --family <name>   # model family; inferred from the name on add
chanchi recommend --task-type ui-component --complexity medium --available "agy:gemini-3.8-flash-high:high,claude:sonnet:medium"
chanchi stats --by task-type
chanchi stats --by dimension
chanchi show <change-ref>
chanchi scoring explain
chanchi taxonomy list
```

Commands detect the project from git (deriving the slug from the main repository across git worktrees); `--project` still overrides.

## Lessons

A lesson records a failure of the setup that guides agents (roles, skills, rules files, workflows)
and one general rule that would have prevented it. A different conversation reviews it, decides,
applies it by hand to a file, and records where it landed. Lessons improve global and project
setup. They do not change code, and they do not change model scores: a failure caused by one
model's weakness is an incident.

Register each project once. Registration is stored only in chanchi's database; no file is added to
the project:

```bash
cd /path/to/project
chanchi project register                 # slug = main worktree folder name
chanchi project register --name myslug   # or choose the slug
chanchi project relink myslug            # run from another clone or a moved folder
```

Commands run anywhere inside the project, including nested git repositories, resolve to it.
`--name` sets the registered slug; audits recorded under the folder name keep that name.

Only writer roles record and review lessons. The default writer role is `planner`:

```bash
chanchi project writers                  # show the roles that may write lessons
chanchi project writers --set planner,auditor
chanchi project writers --global --set planner
```

Record a lesson from a JSON body on stdin, review it from another conversation, then apply it:

```bash
chanchi lesson similar "<general rule>"  # find existing lessons first
chanchi lesson add --as planner --author claude:opus:high --conversation <id> --json - < lesson.json
chanchi lesson export                    # pending lessons, most urgent first
chanchi lesson review 12 --as planner --author claude:sonnet:medium --conversation <other-id> \
  --decision approve --reason "the cause is clear and the rule holds outside this case"
chanchi lesson apply 12 --as planner --author claude:sonnet:medium --conversation <other-id> \
  --site project --where "AGENTS.md [lesson #12] @ <commit>"
chanchi lesson summary
```

The full procedure, field guide and example body are in the `skill-chanchi-lessons` skill. Two lines
tell agents where to go: the writer-role block goes into the planner's role file, and the reporter
line goes into every other role. `chanchi skills link` prints the project-rules line.

Threat model in this version: `--as`, `--author` and `--conversation` are what the caller declares.
The checks stop an agent that declares its real role, not an agent that lies about it. Hooks that
check the harness are planned for a later release.

## Audits

An audit has three auditors of different model families examine one subject (a design, an item,
an adoption or a replication plan) in separate conversations (`agent-chanchi-auditor`, installed
with `chanchi agents link --user`; orchestrator procedure in `skill-chanchi-audit-rounds`).
`chanchi audit open` seats them from the roster and prints, per seat, the model, its family and
a headless launch line to run; chanchi itself never launches a harness. The roster is
`SYNC/config/auditors.toml` when that file exists, else a built-in list of four auditors (`SYNC`
is `CHANCHI_SYNC`, else `<main checkout>/SYNC`).

```bash
chanchi audit open --kind design --ref docs/designs/<topic>.md --author claude:opus:high --commit <sha>
chanchi audit unavailable <audit-id> --round 1 --seat <n> --reason "<error>"   # refill a seat
chanchi audit vote <audit-id> --round 1 --seat <n> --verdict pass_with_fixes --blocking 0 --major 1 --minor 2 --report <path>
chanchi audit dissent <audit-id> --round 1 --seat <n> --finding "<id: text>" --severity major --decision confirmed --evidence "<why>"
chanchi audit close <audit-id> --round 1
chanchi audit round <audit-id> --commit <next-sha>
chanchi audit show <audit-id>
chanchi audit list [--kind <k>] [--ref <ref>]
```

A round with fewer than three distinct known families is recorded as degraded; a model whose
family is unknown never counts as distinct (`chanchi models set <agent:model> --family <name>`).
Rounds run up to three times; `accepted` (at least two approvals and no confirmed lone blocking or
major finding) or `escalated` (`quorum` or `round_cap`) closes the audit. Design:
`docs/designs/global-items.md`.

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

## Refreshing Hugging Face signals (maintainers only)

`chanchi` never contacts the network. Maintainers refresh the committed benchmark snapshot (`src/chanchi/data/hf_snapshot.json`) in a git worktree of this repository, so other projects keep using the previous snapshot until the change merges to `main`.

1. Check that the keys in `scripts/hf_model_map.json` match `chanchi models list --all`.
2. From the worktree root, run a dry run (`HF_TOKEN` is optional for higher Hub rate limits):

```bash
uv run python scripts/fetch_hf_benchmarks.py
```

3. Review the printed summary, then write the snapshot:

```bash
uv run python scripts/fetch_hf_benchmarks.py --write
```

4. Compare `vision_candidates` in the summary with `chanchi models list`, check each provider's model page, and update capabilities with the installed `chanchi` (`chanchi models set <agent:model> --capability vision=yes|no`).
5. Review `git diff src/chanchi/data/hf_snapshot.json`, commit, and merge to `main`. Every project's next `chanchi recommend` call uses the new snapshot automatically through the editable install.

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

Version 4 adds the lesson and project-registration tables. Rollback is forward-only: an older
chanchi on a version-4 database fails with `schema_too_new`. To roll back, restore
`chanchi.db.bak-v3`; the lessons and registrations recorded since are lost.

## Development

```bash
uv run pytest
```
