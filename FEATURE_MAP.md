# chanchi feature map

How an agent reaches, drives and verifies every chanchi command without a human. Format:
`docs/designs/chanchi-agents-mvp.md`, Layer 1. `tests/test_feature_map.py` fails when a command
is missing or a covering test file does not exist.

Every entry assumes a scratch database and a scratch git repository:

    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    scratch="$(mktemp -d)" && git -C "$scratch" init -q && cd "$scratch"

## db

### Sub-features
`db status`, `db migrate`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"

### Driving it
    chanchi db status
    chanchi db migrate

### Evidence
`db status` reports `latest_migration`, `template.exists` `true`, and `operational.path` matching
`CHANCHI_DB`; `db migrate` initializes the operational database so a subsequent `chanchi db status`
reports `operational.exists` `true` and `operational.pending` `0`.
Covered by: tests/test_db.py, tests/test_cli.py

### Gotchas
- `chanchi db migrate --template` updates the committed template database (developer step only).
- Always confirm `operational.path` in `chanchi db status` points to your scratch DB before writing.

## models

### Sub-features
`models add`, `models list`, `models set`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"

### Driving it
    chanchi models add --agent claude --model opus --cost 3 --efforts low,medium,high
    chanchi models list
    chanchi models set claude:opus --notes "primary planner" --active 1
    chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high
    chanchi models set agy:gemini-4-neon-high --family google

### Evidence
`models add` returns `ok: true` with `model.spec` `claude:opus`; `models list` includes
`claude:opus` (alongside seeded `human:human`); `models set` returns the updated `model.notes`.
Every model carries `family`: `models add` infers it from the model name (`claude:opus` is
`anthropic`, `agy:gemini-4-neon-high` is `google`; `null` when the name matches no known vendor),
`--family <slug>` overrides it on `add` and `set`, and a bad slug is `invalid_value` with
`field: "family"`.
Covered by: tests/test_catalog.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- `models set` takes `agent:model` without an effort suffix.
- `models list` omits inactive models unless `--all` is passed.
- A model with `family: null` never counts as a distinct family in audits: set it with
  `chanchi models set <agent:model> --family <slug>`.
- Never pass `--capability` to `models add` or `models set`: capability values belong to the owner
  (`skill-chanchi-model-selection`).

## taxonomy

### Sub-features
`taxonomy list`, `taxonomy add-type`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"

### Driving it
    chanchi taxonomy list
    chanchi taxonomy add-type security-audit --description "Review auth and boundaries"

### Evidence
`taxonomy list` outputs all enums, incident codes, roles, dimensions and `task_types`;
`taxonomy add-type` returns `ok: true` with `task_type.code` `security-audit`, visible in a follow-up
`chanchi taxonomy list`.
Covered by: tests/test_taxonomy.py, tests/test_catalog.py, tests/test_cli.py

### Gotchas
- Task type `code` must be unique (`duplicate` error if it already exists) and `--description` non-empty.

## skills

### Sub-features
`skills link`, `skills unlink`

### How to get to it
    scratch="$(mktemp -d)" && cd "$scratch"

### Driving it
    chanchi skills link "$scratch"
    chanchi skills unlink "$scratch"

### Evidence
`skills link` creates `.agents/skills/skill-chanchi-*` and `.claude/skills/skill-chanchi-*`
symlinks and lists them in `created`; `skills unlink` removes chanchi-owned symlinks and lists
them in `removed`.
Covered by: tests/test_skills_link.py, tests/test_cli.py

### Gotchas
- Existing non-chanchi entries at link paths raise `link_conflict` without overwriting.
- `--global` targets `~` (and creates `chanchi-*` compatibility links unless `--no-compat` is passed);
  never pass `--global` during automated verification.
- A link whose name contains `chanchi-global-` belongs to `items mirror`: `skills link` and `skills unlink`
  never create, repair or remove it, even a dangling secondary.

## agents

### Sub-features
`agents sync`, `agents link`

### How to get to it
For `agents sync`, run from `<repo>` (the chanchi repository root) or pass `<repo>` as the path argument.
For `agents link --user`, set a scratch `HOME` and scratch `CHANCHI_DB` (never the real home):

    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    scratch_home="$(mktemp -d)"
    mkdir -p "$scratch_home/.claude" "$scratch_home/.gemini"

### Driving it
    chanchi agents sync --check <repo>
    HOME="$scratch_home" OPENCODE_CONFIG_DIR="" XDG_CONFIG_HOME="" chanchi agents link --user
    HOME="$scratch_home" OPENCODE_CONFIG_DIR="" XDG_CONFIG_HOME="" chanchi agents link --user --check
    HOME="$scratch_home" OPENCODE_CONFIG_DIR="" XDG_CONFIG_HOME="" chanchi agents link --user --remove

### Evidence
`agents sync --check` returns `ok: true` with `agents` listing each compiled `agent-chanchi-*`, empty
`written` and `removed`, and all generated `.claude/agents/`, `.opencode/agents/` and
`.agents/agents/` wrappers listed in `unchanged`.
`agents link --user` compiles sources with `install: user` into installed user harness folders
(reporting `written`, `unchanged`, `removed`, `conflicts`, and missing harnesses in `skipped_harnesses`)
and records ownership in `mirror.json` next to `CHANCHI_DB`; `--check` verifies without writing;
`--remove` deletes entries owned by that root.
Covered by: tests/test_agents_sync.py, tests/test_cli.py

### Gotchas
- Edit `agents/<name>/AGENT.md`, never the generated wrappers; run `chanchi agents sync` to regenerate.
- `--check` fails with `stale_wrappers` if any wrapper is out of date, missing, orphaned, or conflicts.
- `agents link` requires `--user` (`--check` and `--remove` are mutually exclusive); never target the
  real home during automated verification.
- Existing or foreign-owned files at target paths raise `link_conflict` without writing anything.

## change

### Sub-features
`change open`, `change close`

### How to get to it
    chanchi models add --agent claude --model opus --cost 3 --efforts high

### Driving it
    chanchi change open c1 --kind openspec --planner claude:opus:high
    chanchi change close c1

### Evidence
`change open` returns `ok: true` with `change.ref` `c1` and `closed_at` `null`; `change close`
populates `change.closed_at`, visible in `chanchi show c1`.
Covered by: tests/test_record.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- `--planner` must resolve to an active catalog model (`human:human` is pre-seeded; others require `models add`).
- Closed changes reject new sessions (`change 'c1' is closed`).
- `global` is a reserved project slug (`invalid_value`, `field: "slug"`): a directory named `global` must be registered with `chanchi project register --name <other>`, and `--project global` is refused.

## session

### Sub-features
`session start`, `session report`, `session audit`, `session update`

### How to get to it
    chanchi models add --agent claude --model opus --cost 3 --efforts high
    chanchi models add --agent claude --model haiku --cost 1 --efforts low
    chanchi change open c1 --kind openspec --planner claude:opus:high

### Driving it
    chanchi session start c1 S1 --executor claude:haiku:low --task-type docs --complexity low --tasks 2
    chanchi session update c1 S1 --tags feature-map --notes "updated scope"
    chanchi session report c1 S1 --status COMPLETE
    chanchi session audit c1 S1 --verdict accepted

### Evidence
`session start` records `attempt` `1`; `session update` updates `tags` and `notes`; `session report`
sets `reported_status` `COMPLETE`; `session audit` sets `verdict` `accepted` and `chanchi show c1`
reports `score` `100`.
Covered by: tests/test_record.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- `session audit` fails with `missing_prerequisite` until `session report` has been recorded.
- Starting another attempt for the same session ref requires `--retry-reason`.
- `session update --attempt` selects an attempt and never changes the attempt number.

## incident

### Sub-features
`incident add`, `incident void`

### How to get to it
    chanchi models add --agent claude --model opus --cost 3 --efforts high
    chanchi models add --agent claude --model haiku --cost 1 --efforts low
    chanchi change open c1 --kind openspec --planner claude:opus:high
    chanchi session start c1 S1 --executor claude:haiku:low --task-type docs --complexity low --tasks 2

### Driving it
    chanchi incident add c1 --session S1 --code quality_defect --severity low --detected-by planner_audit --desc "missing edge case" --evidence "tests/test_x.py failed"
    chanchi incident void 1 --reason "false positive on rerun"

### Evidence
`incident add` returns `ok: true` with `incident.id` `1` and `voided_at` `null`; `incident void`
sets `voided_at` and `void_reason`, and `chanchi show c1` lists the incident as voided (excluding it
from penalty scoring once audited).
Covered by: tests/test_record.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- Executor-role incident codes require `--session`; `--attempt` requires `--session`; `hallucination` requires `--role planner|executor`.
- `--evidence` must be non-empty.

## recommend

### Sub-features
`recommend`

### How to get to it
    chanchi models add --agent claude --model opus --cost 3 --efforts high
    chanchi models add --agent claude --model haiku --cost 1 --efforts low

### Driving it
    chanchi recommend --task-type docs --complexity medium --available claude:haiku:low,claude:opus:high

### Evidence
Returns `ok: true` with `recommendation`, `candidates`, `explore`, `explore_reason` and `excluded`,
ranking candidates from `--available`.
Covered by: tests/test_scoring.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- Every spec in `--available` must be registered in the catalog (`human` is planner-only and rejected).
- `--require` excludes models whose capability value is not `yes`, listing them under `excluded`.

## stats

### Sub-features
`stats`

### How to get to it
Run after at least one audited session exists in `CHANCHI_DB` (see `## session`).

### Driving it
    chanchi stats --role executor --by model

### Evidence
Returns `ok: true` with `role` `executor`, `by` `model`, and aggregated `rows` (mean and smoothed scores).
Covered by: tests/test_scoring.py, tests/test_scenario.py, tests/test_cli.py

### Gotchas
- `--by dimension` is valid only with `--role executor`.
- Without `--project`, `stats` aggregates across every project in the database.

## show

### Sub-features
`show`

### How to get to it
Run inside `$scratch` (or pass `--project <slug>`) after opening a change `c1`.

### Driving it
    chanchi show c1

### Evidence
Returns `ok: true` with `change`, `sessions` (with computed `score`), `incidents`, `planner_score`
and `exploration`.
Covered by: tests/test_scoring.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- Outside a git repository (or in an unregistered folder), pass `--project <slug>` or `show` raises `project_not_detected`.

## project

### Sub-features
`project register`, `project relink`, `project list`, `project show`, `project writers`

### How to get to it
    scratch="$(mktemp -d)" && git -C "$scratch" init -q && cd "$scratch"

### Driving it
    chanchi project register --name scratch
    chanchi project list
    chanchi project show scratch
    chanchi project writers scratch --set planner,orchestrator --as planner --author claude:opus:high --conversation c1
    chanchi project relink scratch

### Evidence
`project register` returns `project.slug` `scratch`; `project list` and `project show` report its
`locators`, `writers` and `lessons`; `project writers --set` sets `roles` to
`["planner", "orchestrator"]`; `project relink` confirms `locator` is linked to `scratch`.
Covered by: tests/test_projects.py, tests/test_lessons.py, tests/test_cli.py, tests/test_cli_integration.py

### Gotchas
- `project register` registers the main worktree; use `project relink <slug>` to attach a linked worktree.
- `project writers --set` requires `--as`, `--author` and `--conversation`.
- `global` is a reserved slug: `project register` inside a directory named `global` requires `--name <other>`, and `--name global` is refused (`invalid_value`, `field: "slug"`).

## lesson

### Sub-features
`lesson add`, `lesson repeat`, `lesson modify`, `lesson review`, `lesson reopen`, `lesson apply`,
`lesson retire`, `lesson similar`, `lesson list`, `lesson show`, `lesson summary`, `lesson export`

### How to get to it
    chanchi project register --name scratch

### Driving it
    chanchi lesson add --as planner --author claude:opus:high --conversation c1 --json - < <repo>/tests/fixtures/lessons/base.json
    chanchi lesson review 1 --as planner --author claude:sonnet:medium --conversation c2 --decision approve --reason "holds generally"

### Evidence
`lesson add` prints `"ok": true` and `lesson.status` `pending`; after the review, `chanchi lesson
show 1` has `status` `approved`; `chanchi lesson summary` counts it.
Covered by: tests/test_lessons.py, tests/test_cli_integration.py

### Gotchas
- `--global` requires `generality: agnostic`.
- The reviewing conversation must differ from the author's (`self_review` error).

## audit

### Sub-features
`audit open`, `audit unavailable`, `audit vote`, `audit dissent`, `audit close`, `audit round`, `audit show`, `audit list`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    export CHANCHI_SYNC="$(mktemp -d)"      # a scratch SYNC, so the machine's roster never leaks in
    chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high
    chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high
    chanchi models add --agent opencode --model opencode-go/minimax-m3 --cost 1
    chanchi models add --agent agy --model gemini-4-hydrogen-high --cost 1 --efforts high

### Driving it
    chanchi audit open --kind design --ref docs/designs/example.md --author claude:opus:high --commit abc1234
    chanchi audit unavailable 1 --round 1 --seat 2 --reason "quota exceeded"
    chanchi audit vote 1 --round 1 --seat 1 --verdict pass_with_fixes --blocking 0 --major 1 --minor 2 --report round1-s1.md
    chanchi audit vote 1 --round 1 --seat 2 --verdict pass --blocking 0 --major 0 --minor 1 --report round1-s2.md
    chanchi audit vote 1 --round 1 --seat 3 --verdict pass_with_fixes --blocking 0 --major 0 --minor 3 --report round1-s3.md
    chanchi audit dissent 1 --round 1 --seat 1 --finding "F1: missing edge case" --severity major --decision confirmed --evidence "verified in code"
    chanchi audit close 1 --round 1
    chanchi audit round 1 --commit def5678
    chanchi audit show 1
    chanchi audit list --kind design
    # the item form (needs SYNC and an item in it; see the `items` entry for the fixture):
    chanchi audit open --kind item --ref skill-chanchi-global-demo --author claude:opus:unknown --version 0.1.0
    chanchi audit round <id> --version 0.1.0

### Evidence
`audit open` prints `audit_id` `1`, `round` `1`, `degraded` and a `seats` list of three entries
`{seat, spec, family, effort, status, launch}`: with the roster models above and all three binaries
on `PATH` the families are `anthropic`, `google` and `minimax`, `degraded` is `false` and `outcome`
is `null`. A binary that is not on `PATH`, or a roster model that is not in the catalog, appears in
`skipped` with its reason and fix. With fewer than two seats filled the round closes at once:
`outcome` `escalated`, `escalation` `quorum`. `audit unavailable` prints the refilled `seat` (`null`
when the roster is exhausted) and the recomputed `degraded`; `audit vote` marks each seat `voted`
and records its verdict, counts and report path; `audit dissent` records a confirmed or rejected
decision on a lone finding; `audit close` computes the round outcome (`fix` here because seat 1 has
a confirmed lone major dissent; on `accepted`, `minor_fixes` lists approving minor counts and
confirmed lone minors); `audit round` opens round `2` with the same seats when still available;
`audit show 1` then lists round 1 (including the unavailable row, replacement, votes, dissent and
outcome) and round 2; `audit list` shows the audit with its round count and last outcome. The roster
is `SYNC/config/auditors.toml` when it exists, else the built-in one. An `item` audit takes
`--version` (never `--commit`) and records each round's `subject_at` as `<version>@<content hash>`,
computed from the item in `SYNC/ITEMS`; `audit show` prints it.
Covered by: tests/test_audits.py, tests/test_harnesses.py, tests/test_sync.py, tests/test_items_global.py

### Gotchas
- `chanchi` never launches a harness: `launch` is a line the orchestrator runs, one conversation per seat.
- A model with `family: null` never counts as a distinct family; the seat carries the hint
  `chanchi models set <agent:model> --family <name>`.
- `--change <ref>` needs a project: pass `--project <slug>` or run inside a project that has recorded
  a change (`chanchi change open`); otherwise `missing_prerequisite`.
- `audit vote` refuses `pass` when `blocking > 0` or `major > 0` (vote `pass_with_fixes`).
- `audit close` refuses while any seat is still `assigned`; `audit vote`, `audit dissent` and
  `audit unavailable` refuse on a closed round (`invalid_transition`).
- `audit round` refuses unless the last round is closed with `fix` or `rework` and is below round 3.
- An audit is `unknown_audit` when its id does not exist.
- `audit open --kind item` and `audit round` on an item audit need `SYNC` (`missing_prerequisite`, hint
  `chanchi sync init`), an existing global item as `--ref` and that item's current version
  (`invalid_value`, `field` `ref` or `version`); `--commit` on an item audit is `invalid_value`.
  Every other kind works without `SYNC`.

## scoring

### Sub-features
`scoring explain`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"

### Driving it
    chanchi scoring explain

### Evidence
Returns `ok: true` with current scoring parameters and weights (`executor_session_score`,
`planner_change_score`, `dimension_score`, `severity_multipliers`, `late_detection`, `smoothing`,
`confidence`, `recommendation`, `exploration`).
Covered by: tests/test_scoring.py, tests/test_cli.py

### Gotchas
- Read-only; prints the configured scoring formulas and constants.

## sync

### Sub-features
`sync init`, `sync status`

### How to get to it
    export CHANCHI_SYNC="$(mktemp -d)/SYNC"
    sync_target="$(mktemp -d)/cloud-sync"

### Driving it
    chanchi sync status
    chanchi sync init --link "$sync_target"
    chanchi sync status

### Evidence
Before initialization, `sync status` reports `exists` `false`, `reachable` `false`, `config` `false`,
`items` `false` (and creates nothing). `sync init --link` creates `config/`, `ITEMS/agents/` and
`ITEMS/skills/` inside `$sync_target`, symlinks `CHANCHI_SYNC` to it, and returns `created`, `link`
and `recommendation`. A follow-up `sync status` reports `exists` `true`, `is_link` `true`, `target`
equal to `$sync_target`, `reachable` `true`, `config` `true` and `items` `true`. Without `--link`,
`chanchi sync init` creates the three folders directly at `SYNC` and returns `link: null`.
Covered by: tests/test_sync.py, tests/test_cli.py

### Gotchas
- Without `CHANCHI_SYNC`, `SYNC` resolves to `<main checkout>/SYNC` across every git worktree of this repository (ignored by `.gitignore`).
- `sync init --link` refuses with `link_conflict` if anything already exists at `SYNC`; plain `sync init` is idempotent on an existing `SYNC` directory, refuses a file at `SYNC` (`link_conflict`), and refuses a dangling link (`missing_prerequisite`).
- `sync init --link` to an existing non-directory raises `invalid_value` (`field: "link"`).

## items

### Sub-features
`items check`, `items list`, `items publish`, `items retire`, `items mirror`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    export CHANCHI_SYNC="$(mktemp -d)/SYNC"
    chanchi sync init
    chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high
    chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high
    chanchi models add --agent opencode --model opencode-go/minimax-m3 --cost 1
    item="$CHANCHI_SYNC/ITEMS/skills/skill-chanchi-global-demo" && mkdir -p "$item"
    printf -- '---\nname: skill-chanchi-global-demo\ndescription: Demo skill.\nmetadata:\n  version: "0.1.0"\n  status: "draft"\n---\n\n# Demo\n' > "$item/SKILL.md"
    printf -- '# Changelog\n\n## 0.1.0 — 2026-11-22\n\n- First draft.\n' > "$item/CHANGELOG.md"
    item="$CHANCHI_SYNC/ITEMS/agents/agent-chanchi-global-demo" && mkdir -p "$item"
    printf -- '---\nname: agent-chanchi-global-demo\ndescription: Demo agent.\nscope: both\nprofile: read-only\nskills: [skill-chanchi-global-demo]\nversion: 0.1.0\nstatus: draft\n---\n\n# Demo\n\nState your agent name.\n' > "$item/AGENT.md"
    printf -- '# Changelog\n\n## 0.1.0 — 2026-11-22\n\n- First draft.\n' > "$item/CHANGELOG.md"
    scratch_home="$(mktemp -d)"   # `items mirror` writes user folders: never run it against the real home
    mkdir -p "$scratch_home/.claude" "$scratch_home/.config/opencode" "$scratch_home/.gemini/antigravity-cli"

### Driving it
    chanchi items check
    chanchi items list
    HOME="$scratch_home" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= chanchi items mirror   # drafts: nothing written
    chanchi audit open --kind item --ref skill-chanchi-global-demo --author claude:opus:unknown --version 0.1.0
    chanchi audit vote 1 --round 1 --seat 1 --verdict pass --blocking 0 --major 0 --minor 0 --report fixture   # seats 2 and 3 too
    chanchi audit close 1 --round 1
    chanchi items publish skill-chanchi-global-demo --audit 1
    chanchi audit open --kind item --ref agent-chanchi-global-demo --author claude:opus:unknown --version 0.1.0
    chanchi audit vote 2 --round 1 --seat 1 --verdict pass --blocking 0 --major 0 --minor 0 --report fixture   # seats 2 and 3 too
    chanchi audit close 2 --round 1
    chanchi items publish agent-chanchi-global-demo --audit 2
    chanchi items list
    chanchi items check
    mirror() { HOME="$scratch_home" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= chanchi items mirror "$@"; }
    mirror
    printf 'hand edit\n' >> "$scratch_home/.claude/agents/agent-chanchi-global-demo.md"
    mirror --check
    mirror
    mirror --check
    mirror --remove
    find "$scratch_home" -name '*-chanchi-global-*'
    chanchi items retire skill-chanchi-global-demo --reason "demo is over"

### Evidence
`items check` prints `problems` `[]` and one entry per item (`name`, `kind`, `version`, `status`, `hash`,
`published_hash`); with problems it fails once with `invalid_value`, `field` `items` and every problem in
`details.problems` (`{item, code, detail}`). `items list` prints every item with `retired` and never fails
on a broken item (unreadable fields are `null`). After `audit close` returns `accepted`, `items publish`
prints `{name, version, status: published, audit_id, audited_hash, hash}`: `hash` differs from
`audited_hash` because the status line changed, and `CHANGELOG.md` gains the line
`Published: <date> · audit <id> · audited <hash> · sha256 <hash>` inside the current version's section.
The next `items list` shows `status` `published` and `published_hash` equal to `hash`; `items check` still
passes. `items retire` rewrites the status to `retired` and appends `{name, version, replaced_by, date,
reason}` to `ITEMS/retired.json` (created when missing); `items list` then shows `retired` `true`.
`items mirror` on drafts prints empty `written`, `unchanged` and `removed`, `conflicts` `[]` and `items` `[]`. After
both items are published it prints `written` (the skill's primary `.agents/skills/<name>` link, its relative
`.claude/skills` and `.gemini/antigravity-cli/skills` links, and the agent file for claude, opencode and agy at
`.gemini/config/agents/<name>/agent.md`), `unchanged` `[]`, `skipped_harnesses` `[]` and both names in `items`;
`mirror.json` next to `$CHANCHI_DB` then holds one `{owner: "items-mirror", item, kind, path, link|sha256}` entry
per path. After the hand edit, `mirror --check` fails with `stale_wrappers` and the edited path in
`details.stale`; `mirror` lists only that path in `written` and `mirror --check` then passes with every path in
`unchanged`. `mirror --remove` lists every entry in `removed` and the final `find` prints nothing.
Covered by: tests/test_items_global.py, tests/test_audits.py, tests/test_agents_sync.py, tests/test_mirror.py

### Gotchas
- Every command needs `SYNC` (`missing_prerequisite`, hint `chanchi sync init`).
- A global item is `<agent|skill>-chanchi-global-<name>` under `ITEMS/agents/` or `ITEMS/skills/`. An
  `AGENT.md` keeps flat `key: value` lines and gains `version: <x.y.z>` and `status: draft|published|retired`
  (never copied into wrappers); a `SKILL.md` carries them in a `metadata:` block of two-space-indented lines.
- The content hash covers every regular file except `CHANGELOG.md`, paths with a component starting with `.`
  and cloud conflict copies; a symlink inside an item is a `symlink` problem.
- `items publish` refusals, in order: unknown item or name (`invalid_value`), retired or listed in
  `retired.json` (`invalid_transition`), already published (`invalid_transition`: write the next version as
  `draft`), `items check` problems for the item or a malformed `retired.json` (`invalid_value`), unknown audit
  (`unknown_audit`), an audit that is not an `item` audit of this name (`invalid_value`, `field` `audit`), a last
  round that is not `accepted` at the item's current `<version>@<draft hash>` (`invalid_transition`: any edit
  after the audit needs a new round or a new version).
- A published item that is edited reports `edited_after_publish`; `status: published` set by hand, with no
  `Published:` line, reports `published_without_record`. Retired and draft items are exempt.
- `items mirror` exposes only `published` items and is all or nothing: an `items check` problem is refused
  (`invalid_value`, `field` `items`; with `--check`, `stale_wrappers`), and a conflict on any wanted path
  (`link_conflict`, paths in `details.conflicts`) writes nothing. A path that exists and is not an entry of the
  mirror (a foreign file or link, or an entry `agents link --user` owns) is a conflict and is never overwritten;
  a foreign `*chanchi-global-*` entry at a path the mirror does not want is left alone.
- `items mirror` writes a harness's entries only when its user folder exists (`skipped_harnesses` names the
  others) and the `.agents/skills` primaries whenever any harness is installed; skill links point at the
  unresolved `SYNC` path, so re-pointing `SYNC` leaves them valid. `--check` writes nothing and fails with
  `stale_wrappers` on a missing, changed or no-longer-wanted entry; `--remove` deletes every entry the mirror
  made, dangling or not, and works without `SYNC`. Ownership is `mirror.json` (the folder of `CHANCHI_DB`); `skills
  link/unlink` never touch a `*chanchi-global-*` name and the mirror never touches chanchi's own links.
- `items retire` refuses a blank reason, a retired item (`invalid_transition`), `--replaced-by` that is the item
  itself, does not exist, is retired or is of another kind (`invalid_value`), and an item whose name,
  frontmatter, version or status cannot be read; a draft may be retired. A retired name set back to another
  status fails `items check` (`retired_not_retired`).
