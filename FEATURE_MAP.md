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
`audit open`, `audit unavailable`, `audit show`, `audit list`

### How to get to it
    export CHANCHI_DB="$(mktemp -d)/chanchi.db"
    export CHANCHI_SYNC="$(mktemp -d)"      # a scratch SYNC, so the machine's roster never leaks in
    chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high
    chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high
    chanchi models add --agent opencode --model opencode-go/minimax-m3 --cost 1

### Driving it
    chanchi audit open --kind design --ref docs/designs/example.md --author claude:opus:high --commit abc1234
    chanchi audit unavailable 1 --round 1 --seat 2 --reason "quota exceeded"
    chanchi audit show 1
    chanchi audit list --kind design

### Evidence
`audit open` prints `audit_id` `1`, `round` `1`, `degraded` and a `seats` list of three entries
`{seat, spec, family, effort, status, launch}`: with the three models above and all three binaries on
`PATH` the families are `anthropic`, `google` and `minimax`, `degraded` is `false` and `outcome` is
`null`. A binary that is not on `PATH`, or a roster model that is not in the catalog, appears in
`skipped` with its reason and fix. With fewer than two seats filled the round closes at once:
`outcome` `escalated`, `escalation` `quorum`. `audit unavailable` prints the refilled `seat` (`null`
when the roster is exhausted) and the recomputed `degraded`; `audit show 1` then lists the
unavailable row and its replacement under the same seat number; `audit list` shows the audit with
its round count and last outcome. The roster is `SYNC/config/auditors.toml` when it exists, else the
built-in one.
Covered by: tests/test_audits.py, tests/test_harnesses.py, tests/test_sync.py

### Gotchas
- `chanchi` never launches a harness: `launch` is a line the orchestrator runs, one conversation per seat.
- A model with `family: null` never counts as a distinct family; the seat carries the hint
  `chanchi models set <agent:model> --family <name>`.
- `--change <ref>` needs a project: pass `--project <slug>` or run inside a project that has recorded
  a change (`chanchi change open`); otherwise `missing_prerequisite`.
- An audit is `unknown_audit` when its id does not exist; a closed round or a seat that is not
  `assigned` refuses `audit unavailable` with `invalid_transition`.

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
