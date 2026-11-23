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
- `skill-chanchi-item-adoption` — used in a project to compare global items against its own, propose a decision, apply it and record it.

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
- `agent-chanchi-item-builder` — user-installed builder that turns one stored item proposal into a global item draft in `SYNC/ITEMS`; never publishes and never writes chanchi records.

Launch one with `claude --agent <name>`, `opencode run --agent <name>` or
`agy --agent <name>`. Unattended headless lines need each harness's permission flags
(`AGENTS.md`, Working Conventions); `chanchi audit open` prints them. `FEATURE_MAP.md` tells an
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

`chanchi items scan` reads the item folders of every registered project. Besides the defaults it reads the
agnostic folders a project registers (a relative folder that exists, never a link):

```bash
chanchi project items-dirs                       # the default folders and the ones registered
chanchi project items-dirs --add docs/agents
chanchi project items-dirs --remove docs/agents
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

## SYNC

User configuration (`config/`) and global items (`ITEMS/`) live in `SYNC` (`CHANCHI_SYNC`, else
`<main checkout>/SYNC`, shared across worktrees and ignored by `.gitignore`). Point `--link` at a
folder a cloud service synchronizes (Google Drive, iCloud Drive, Dropbox) or at a clone of a
private git repository; keep the SQLite database out of `SYNC`.

```bash
chanchi sync init                # create SYNC/config, SYNC/ITEMS/agents, SYNC/ITEMS/skills
chanchi sync init --link <dir>   # create those folders in <dir> and symlink SYNC to it
chanchi sync status              # show SYNC path, symlink target, reachability and folders
```

## Global items

Global agents and skills live in `SYNC/ITEMS/agents/<item>-chanchi-global-<name>/` and
`SYNC/ITEMS/skills/...`, never in this repository. Each carries a `version` and a `status`
(`draft`, `published`, `retired`) and a `CHANGELOG.md` section per version. An `item` audit records
`<version>@<content hash>`; `items publish` sets `status: published` only after an accepted audit of
exactly that version and content, and any later edit shows up as `edited_after_publish`.

```bash
chanchi items check                                 # validate SYNC/ITEMS; one failure lists every problem
chanchi items list                                  # name, kind, version, status, hashes, retired
chanchi audit open --kind item --ref <item> --author <agent:model[:effort]> --version <x.y.z>
chanchi items publish <item> --audit <audit-id>     # after `audit close` returned accepted
chanchi items retire <item> [--replaced-by <item>] --reason "<why>"
chanchi items mirror                                # expose published items to the installed harnesses
chanchi items mirror --check                        # write nothing; fail when the mirror is stale
chanchi items mirror --remove                       # delete exactly what the mirror made
chanchi items scan [--project <slug>]               # fingerprint the item folders of registered projects
chanchi items propose [--owner-promote <name>]      # candidate global items from the scan and the lessons
chanchi items proposals [--status open|built|rejected | --id <n>]   # stored candidates; --id adds absolute paths
chanchi items proposal-status <n> --status built --global-item <item>   # or --status rejected
chanchi items inbox [--all] [--project <slug>]      # global items needing a decision for this project
chanchi items decide <item> --decision adopt|wrap|keep|deprecate --version <x.y.z> [--local <item>] --reason "<why>" --audit <id> [--project <slug>]
```

`items mirror` links each published skill into `~/.agents/skills` (plus relative links for Claude Code and the
agy CLI) and writes each published agent for the installed harnesses (`~/.claude/agents`, the opencode
`agents` folder, `~/.gemini/config/agents`). Drafts and retired items never appear. Every entry is recorded
in `mirror.json` next to the database; the mirror updates or removes only what it recorded, refuses to
overwrite anything else, and leaves `chanchi skills link` and `chanchi agents link --user` entries alone.

`items scan` is read-only on projects: it never writes into one and never follows a link. For each skill and
agent it finds (`.agents/skills`, `.claude/skills`, `.opencode/skills`, `agents`, `.claude/agents`,
`.opencode/agents`, `.agents/agents` and the folders from `project items-dirs`) it stores the path, a content
hash, the line count and the frontmatter `description`, never the item text; wrappers that `chanchi agents sync`
generated are skipped. Running it twice changes nothing. A global item named like a scanned project item is a
`project_item_collision` in `items check`, `items publish` and `items mirror`.

`items propose` turns the scan and the agnostic lessons into stored candidates, each with its evidence and its
independent uses (copies that share most of their lines count once, so vendored upstream text is not mistaken
for several uses). It never writes into a project, and it fails with `missing_prerequisite` when a counted copy
changed since the last `items scan`. `--owner-promote <name>` records the owner's decision to promote a
candidate before it reaches the threshold; the flag stays set on later runs. `SYNC/config/promotion.toml` is
optional and accepts exactly two keys:

```toml
min_uses = 3          # independent uses that make a candidate eligible (integer, at least 1)
vendored_share = 0.5  # two copies sharing a block of identical lines this share of the shorter one count once
```

`items proposals --id <n>` prints one candidate with the absolute path of each copy, for the item builder;
`items proposal-status` closes an open candidate as `built` (linked to the draft in `SYNC/ITEMS`) or `rejected`.

`items inbox` lists, for one registered project, global items that need an adoption decision (`new`, `changed`,
`deprecate_pending` or `retired`), together with overlapping scanned items (`similar`); `--all` also shows
`up_to_date` items. `items decide` records an audited `adopt`, `wrap`, `keep` or `deprecate` decision (backed by
an accepted `adoption` audit of `<project>:<item>`), keeping the item's version and content hash.

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
