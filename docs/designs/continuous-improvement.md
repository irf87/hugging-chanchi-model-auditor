# Continuous Improvement (Lessons) in chanchi

- **Author:** Iván R
- **Status:** Proposed
- **Date:** 2026-11-19
- **Brief:** [continuous-improvement.brief.md](continuous-improvement.brief.md)
  (Revision 2)

---

## Overview

chanchi records how agents perform: each audited session, each incident, and the model ratings
that follow. It does not record what the agent **setup** should learn from a failure. This design
adds **lessons** to chanchi.

A lesson is written by the agent that coordinates the work (or by the person) after something went
wrong. It holds what happened, the evidence, the cause, and one general rule that would have
prevented it. It names the one place where the fix belongs. A different conversation later reviews
it, decides, applies it by hand, and records where it landed.

What lessons improve is the system that guides agents, at two levels:

- **Global** (the user's home setup, shared by every project): global skills such as
  `~/.agents/skills/*` and `~/.claude/skills/*`, global agents of each harness, global rules files,
  hooks and permissions of each harness, and chanchi's own skills.
- **Project**: the project's role definitions and their per-harness wrappers
  (`.claude/agents`, `.agents/agents`, `.opencode/agents`), project skills, rules files
  (`AGENTS.md`, `CLAUDE.md`, `openspec/config.yaml`) and workflows.

Lessons do not fix the project's code: that is fixed on the spot, before anything is recorded. They
do not rate models either. A failure caused by one model's weakness is an incident, and it lowers
that model's score in `chanchi recommend`.

chanchi stores, deduplicates, orders and tracks lessons, and compares what it recorded with what
the files say. It never edits a role, skill, prompt or rules file.

The work ships in four stages. This document gives the full plan for stages 1 and 2, which depend
only on chanchi's own code. Stages 3 and 4 (hooks in the harnesses) are specified by their contract
and dependencies; their file-level plan is written after the harness facts in Open Questions are
verified.

## The Problem

The owner runs multi-agent work across several projects and three harnesses (Claude Code, agy and
opencode). The same kinds of failure come back: an executor reports tests that never ran, a role
reads a skill only partly, a plan states a rule outside its real scope. Each time, the fix today is
one of these:

1. **Nothing is written down.** The failure is fixed in the work and forgotten. The next
   conversation, in the same or another project, repeats it.
2. **A rule is pasted into a role file by hand, by the agent that made the mistake**, in the same
   conversation. Nobody checks whether the cause was understood, whether a rule already covers it,
   or whether the rule is worth its cost in context. One of the owner's projects has a "Lessons
   learned" section in every role that says "the planner appends dated, sourced rules here after
   audits". All of those sections are empty: the practice has not taken hold.
3. **Rules are copied between projects by hand.** One project carries 30 rules in its roles and 9
   in its skills, each tagged with the name of the older project it came from. Nothing records
   which rules a project took, skipped or never saw, or which ones were later found wrong.

Three things make this worse over time:

- **Every rule costs context in every run.** One project's role folder is 1,932 lines, read in full
  by weak models at every start. Rules are only ever added; nothing tracks which to merge or
  remove.
- **The fix is often in the wrong place.** A rule that should hold everywhere lands in one
  project's file; a rule that only one harness needs lands in a role shared by all three; a rule
  that must never be broken is written as a prompt line that a model can ignore.
- **A model weakness gets turned into a permanent rule.** When one model fails, the instinct is to
  add an instruction that every model then pays for, instead of rating that model lower.

The owner already uses, in another setting, a per-project method that addresses most of this:
record a lesson with a general rule, review it in a different conversation, apply it, and record
where. chanchi already holds data for every project on the machine (one SQLite database), so it is
the natural place to run that method for global and per-project lessons together.

The proposed solution:

- **Stage 1.** Projects are registered in chanchi's database. Writer roles are set per project and
  globally. Lessons are recorded with the method's full record, plus the author's harness, model
  and effort, and links to existing changes, sessions and incidents. A lesson's decision (approved,
  rejected, and so on) is tracked separately from each place it is applied. Near-duplicates are
  blocked. One skill guides recording and review.
- **Stage 2.** Approved rules that hold anywhere reach other projects' inbox, where each project
  applies them or declines them. A read-only check compares the database with the files.
- **Stage 3.** Hooks: chanchi identifies each conversation, checks the role of whoever runs a
  lesson command, and reminds writer roles once to do the retrospective. Claude Code first.
- **Stage 4.** The same hooks for agy and opencode, limited to what was observed working.

## Goals

**Stage 1**

- A project is registered with `chanchi project register`, stored only in chanchi's database. No
  file is added to the project.
- A command run anywhere inside a registered project, including inside a nested git repository,
  resolves to that project.
- Session audits keep working for unregistered projects exactly as today.
- A lesson can only be recorded, reviewed or applied by a writer role of its scope (project or
  global), or by the `human` agent. An unknown role is refused.
- Every lesson carries a general rule, a generality (`agnostic`, `project`, `particular`) and a
  severity. A `particular` lesson needs `high` or `critical` severity and a justification.
- Every lesson records the author's harness, model (raw text, plus the catalog row when it
  matches) and effort, and may link a change, a session and incidents.
- A review from the same conversation that recorded the lesson is refused.
- A lesson can be applied to several places (global and per project), and retired in one place
  without affecting the others.
- `lesson add` blocks a near-duplicate of an open or applied lesson, names it, and offers
  `lesson repeat` or `--force-new`.
- `lesson export` lists pending lessons from general to particular, then by severity, then by
  occurrences, with a default limit of 20.
- One skill, `chanchi-lessons`, linked by `chanchi skills link`, covers recording (the end-of-
  conversation retrospective) and review.

**Stage 2**

- `lesson inbox` shows, for one project, the agnostic lessons that are approved, already applied
  to at least one project, and not yet decided by this project. A newly registered project sees
  only `high` and `critical` items from the existing backlog by default.
- `lesson verify` reports, from the files alone: applied lessons whose `[lesson #N]` tag is
  missing, retired lessons whose tag is still present, unknown tags, and the size of each target
  file.

**Stages 3 and 4** (goals only; plan after verification)

- `chanchi hook check` decides on lesson commands from the role of the event's actor, always exits
  0, allows on any internal error, never migrates the database, and is only called when the
  command mentions chanchi.
- A writer-role conversation in a registered project is asked for the retrospective at most once.
- Each harness adapter ships only the events whose behavior was observed in that harness.

## Non-Goals

- chanchi editing any role, skill, prompt or rules file.
- Opening the harness list beyond `taxonomy.ALL_AGENTS` (`claude`, `agy`, `opencode`, `human`).
- A shared or remote database, or sharing lessons between machines or people.
- Embedding or semantic search for duplicates.
- A hard context budget per file.
- A draft queue for reporter roles; they mention failures in their reports.
- Importing the existing hand-copied rules as lessons.
- Requiring registration for session audits.
- Changing model scores from lessons.

## Open Questions

These block stage 3 or 4 only. Each is checked in the real harness with one case that must pass and
one that must fail; the check is delegated to agy and its result is written here.

- **Q1 (Claude Code):** Is `agent_type` present in hook input for a main conversation started with
  `--agent`, and does `session_id` stay the same across resume and compaction?
- **Q2 (agy):** Which hook input field holds the conversation id (the herdr script reads
  `conversationId`), which field names the `--agent` role if any, and can `SessionStart` output add
  text to the model's context?
- **Q3 (agy):** What is the argument field name for `run_command` in `PreToolUse`?
- **Q4 (opencode 2.2.6):** Does it use plugin API V1 (`server()`) or V2 (`setup()`)? Does throwing
  in `tool.execute.before` block the tool? Does any event carry the agent name? Does the role
  survive `opencode run --agent X` followed by the TUI reopened with `-s <id>`?
- **Q5:** Which agy version is installed, and what is the source of each agy fact? The cached
  CHANGELOG stops at 1.5.7.

## Critical User Journeys (CUJs)

### CUJ 1: The planner records a lesson after an audit (stage 1)

- **Given**: project A is registered; its writer roles are the default (`planner`); a Claude Code
  planner conversation (`opus`, effort `high`) audits session S3 of change `add-export`; the
  executor claimed tests passed, but they never ran in the right package; the planner recorded
  incident 118 and had the work fixed.
- **When**: the planner runs `chanchi lesson similar "test output evidence package skipped"`, sees
  nothing close, and runs `chanchi lesson add --as planner --author claude:opus:high
  --conversation <session id> --json -` with the general rule "test output counts as evidence only
  if it names what ran and what was skipped", generality `agnostic`, severity `high`, target kind
  `role`, target `role executor`, change `add-export`, session `S3`, incident `118`.
- **Then**: lesson #42 exists as `pending`, with `author_model_raw = opus`, `author_model_id` set
  (the catalog has `claude:opus`), `git_head` captured, one `created` event, and links to the
  session and the incident. The command prints the id.

### CUJ 2: A maintenance conversation reviews and applies (stage 1)

- **Given**: lesson #42 is `pending`; a new conversation in project A, as `planner`.
- **When**: it runs `chanchi lesson export --generality agnostic`, reads #42, its incident and its
  session, runs `chanchi lesson review 42 --as planner --conversation <new id> --decision approve
  --reason "..."`, edits `.agents/roles/executor.md` adding the rule tagged `[lesson #42]`,
  commits, and runs `chanchi lesson apply 42 --as planner --conversation <new id> --site project
  --where ".agents/roles/executor.md [lesson #42] @ abc123"`.
- **Then**: #42 is `approved`; a site row (project A, `applied`) exists; two events are written.
  The same review from the recording conversation would have failed with `self_review`.

### CUJ 3: An executor tries to record a lesson (stage 1)

- **Given**: an executor started as `claude --agent executor` in project A has been told by its role
  file to report failures, not record them.
- **When**: it runs `chanchi lesson add --as executor ...`.
- **Then**: the command fails with `not_a_writer`, naming the role it saw (`executor`), the writer
  roles of project A (`planner`) and the command that changes them. Nothing is written. (Stage 1
  trusts the declared role. In stage 3 the hook also compares it with the role the harness
  reports.)

### CUJ 4: A command from inside a nested repository (stage 1)

- **Given**: project B is registered at `/work/b`; `/work/b/b-app` is an independent git repository
  with its own remote and is not registered.
- **When**: an agent runs `(cd b-app && chanchi lesson add ...)`.
- **Then**: the lesson belongs to project B, because `/work/b` is the longest registered path that
  contains the working directory.

### CUJ 5: Another project adopts or declines the rule (stage 2)

- **Given**: #42 is `approved`, `agnostic`, and applied to project A's site; project B is
  registered and has no site row for #42.
- **When**: project B's maintenance conversation runs `chanchi lesson inbox`.
- **Then**: #42 is listed. The conversation either applies it to project B's executor role
  (`lesson apply 42 --site project ...`), or declines it with a reason
  (`lesson decline 42 --reason ...`) or as `--not-applicable`. Either way #42 leaves project B's
  inbox, and project A's site is unchanged.

### CUJ 6: A rule is merged and retired in one project (stages 1 and 2)

- **Given**: #42 is applied in projects A and B; #57 merges #42 with another rule and lists #42 in
  `replaces`; #57 is approved.
- **When**: #57 is applied to project A's site.
- **Then**: #42's site row for project A becomes `retired` with an event; project B's site row
  stays `applied`. Project B's inbox shows #57 marked "replaces #42, which you applied". Later,
  `lesson verify` in project A reports `[lesson #42]` still in a file if nobody removed it.

### CUJ 7: A global lesson from outside any project (stage 1)

- **Given**: the owner edits a global skill from `~`, which is not inside any project.
- **When**: a conversation with the agent `human` (or a global writer role) runs
  `chanchi lesson add --global ...`, with target kind `skill` and target
  `skill ~/.agents/skills/chanchi-session-audit`.
- **Then**: the lesson has no origin project and is reviewed under the global writer roles.

## Technical Plan (Architecture)

### Overview of the pieces

```text
                     ┌──────────────────────────────────────────────┐
  agent / person ──▶ │ cli.py: project …, lesson …                  │
                     └────┬───────────────┬──────────────┬──────────┘
                          │               │              │
                 ┌────────▼──────┐ ┌──────▼───────┐ ┌────▼─────────┐
                 │ projects.py   │ │ lessons.py   │ │ dedup.py     │
                 │ register,     │ │ record,      │ │ tokens,      │
                 │ locators,     │ │ review, apply│ │ coverage,    │
                 │ resolve,      │ │ sites, inbox,│ │ thresholds   │
                 │ writer roles  │ │ verify       │ │              │
                 └────────┬──────┘ └──────┬───────┘ └────┬─────────┘
                          │               │              │
                 ┌────────▼───────────────▼──────────────▼─────────┐
                 │ SQLite (one file per machine), migration 004    │
                 │ projects(+registered_at) · project_locators ·   │
                 │ writer_roles · lessons · lesson_sites ·         │
                 │ lesson_replaces · lesson_incidents · lesson_events│
                 │ (existing: models · changes · sessions · incidents)│
                 └─────────────────────────────────────────────────┘

  skills/chanchi-lessons/SKILL.md  ── linked by `chanchi skills link` into projects and home
```

`lessons.py` holds every lesson rule and transition. `cli.py` only parses arguments and calls it,
as it does for `record.py` today. `dedup.py` is separate because it is pure text processing with its
own fixture tests and thresholds. Project registration and resolution extend `projects.py`.

### 1. Data model (migration `004_lessons.sql`)

```sql
ALTER TABLE projects ADD COLUMN registered_at TEXT;

CREATE TABLE project_locators (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  kind        TEXT NOT NULL,            -- 'path' | 'remote' (validated in taxonomy)
  value       TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  UNIQUE (kind, value)
);

CREATE TABLE writer_roles (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER REFERENCES projects(id),   -- NULL = global scope
  role        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX writer_roles_scope ON writer_roles (COALESCE(project_id, 0), role);

CREATE TABLE lessons (
  id                        INTEGER PRIMARY KEY,
  origin_project_id         INTEGER REFERENCES projects(id),   -- NULL = global origin
  author_role               TEXT NOT NULL,
  author_agent              TEXT NOT NULL,
  author_model_raw          TEXT NOT NULL,
  author_model_id           INTEGER REFERENCES models(id),
  author_effort             TEXT,
  author_conversation       TEXT NOT NULL,
  git_head                  TEXT,
  change_id                 INTEGER REFERENCES changes(id),
  session_id                INTEGER REFERENCES sessions(id),
  target_kind               TEXT NOT NULL,
  target                    TEXT NOT NULL,
  what_happened             TEXT NOT NULL,
  evidence                  TEXT NOT NULL,
  cause                     TEXT NOT NULL,
  prevention                TEXT NOT NULL,
  proposal                  TEXT NOT NULL,
  general_rule              TEXT NOT NULL,
  generality                TEXT NOT NULL,
  severity                  TEXT NOT NULL,
  particular_justification  TEXT,
  occurrences               INTEGER NOT NULL DEFAULT 1 CHECK (occurrences >= 1),
  tags                      TEXT NOT NULL DEFAULT '',
  status                    TEXT NOT NULL DEFAULT 'pending',
  reviewed_at               TEXT,
  reviewed_by_role          TEXT,
  review_conversation       TEXT,
  decision_reason           TEXT,
  reason_code               TEXT,
  duplicate_of              INTEGER REFERENCES lessons(id),
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL,
  CHECK (length(trim(what_happened)) > 0 AND length(trim(evidence)) > 0
         AND length(trim(cause)) > 0 AND length(trim(prevention)) > 0
         AND length(trim(proposal)) > 0 AND length(trim(general_rule)) > 0
         AND length(trim(target)) > 0),
  CHECK (generality <> 'particular'
         OR (severity IN ('high', 'critical')
             AND particular_justification IS NOT NULL
             AND length(trim(particular_justification)) > 0)),
  CHECK (status <> 'duplicate' OR (duplicate_of IS NOT NULL AND duplicate_of <> id)),
  CHECK (status = 'pending' OR reviewed_at IS NOT NULL)
);

CREATE TABLE lesson_sites (
  id                    INTEGER PRIMARY KEY,
  lesson_id             INTEGER NOT NULL REFERENCES lessons(id),
  site                  TEXT NOT NULL,                       -- 'global' | 'project'
  project_id            INTEGER REFERENCES projects(id),
  state                 TEXT NOT NULL,                       -- applied | declined | not_applicable | retired
  where_                TEXT,
  reason                TEXT,
  decided_conversation  TEXT NOT NULL,
  decided_at            TEXT NOT NULL,
  CHECK ((site = 'global' AND project_id IS NULL) OR (site = 'project' AND project_id IS NOT NULL)),
  CHECK (state NOT IN ('applied', 'retired') OR (where_ IS NOT NULL AND length(trim(where_)) > 0))
);
CREATE UNIQUE INDEX lesson_sites_place ON lesson_sites (lesson_id, site, COALESCE(project_id, 0));

CREATE TABLE lesson_replaces (
  lesson_id    INTEGER NOT NULL REFERENCES lessons(id),
  replaced_id  INTEGER NOT NULL REFERENCES lessons(id),
  PRIMARY KEY (lesson_id, replaced_id),
  CHECK (lesson_id <> replaced_id)
);

CREATE TABLE lesson_incidents (
  lesson_id    INTEGER NOT NULL REFERENCES lessons(id),
  incident_id  INTEGER NOT NULL REFERENCES incidents(id),
  PRIMARY KEY (lesson_id, incident_id)
);

CREATE TABLE lesson_events (
  id            INTEGER PRIMARY KEY,
  lesson_id     INTEGER NOT NULL REFERENCES lessons(id),
  site_id       INTEGER REFERENCES lesson_sites(id),
  at            TEXT NOT NULL,
  actor_role    TEXT NOT NULL,
  actor_agent   TEXT NOT NULL,
  conversation  TEXT NOT NULL,
  action        TEXT NOT NULL,
  from_state    TEXT,
  to_state      TEXT,
  note          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX lessons_by_status     ON lessons (status, generality, severity);
CREATE INDEX lessons_by_origin     ON lessons (origin_project_id);
CREATE INDEX lesson_sites_by_place ON lesson_sites (site, project_id, state);
CREATE INDEX lesson_events_by_lesson ON lesson_events (lesson_id, id);
```

**What `CHECK` holds, and what it does not.** `CHECK` holds structural invariants that will not
change: required text is not empty, the particular rule, the duplicate link, a reviewed status has
`reviewed_at`, a site's scope and `where_`. Enum sets (`target_kind`, `generality`, `severity`,
`status`, `reason_code`, site `state`, locator `kind`), the writer-role policy, the harness list
and the duplicate thresholds are validated in `taxonomy.py` and `lessons.py`, following
`003_model_capabilities.sql`, so they can change without rebuilding a table.

New sets in `taxonomy.py`, listed by `taxonomy.describe()` so `chanchi taxonomy list` shows them:

| Constant | Values |
|---|---|
| `LESSON_TARGET_KINDS` | `role`, `skill`, `wrapper`, `rules-file`, `hook`, `permission`, `workflow`, `tool` |
| `LESSON_GENERALITIES` | `agnostic`, `project`, `particular` (review order) |
| `LESSON_SEVERITIES` | `critical`, `high`, `medium`, `low` (review order) |
| `LESSON_STATUSES` | `pending`, `approved`, `rejected`, `postponed`, `duplicate` |
| `LESSON_DECISIONS` | `approve`, `reject`, `postpone`, `duplicate` |
| `LESSON_REASON_CODES` | `model_weakness`, `covered`, `too_costly`, `symptom_only` |
| `LESSON_SITE_STATES` | `applied`, `declined`, `not_applicable`, `retired` |
| `LOCATOR_KINDS` | `path`, `remote` |
| `DEFAULT_WRITER_ROLES` | `("planner",)` |

### 2. Project registration and resolution (`projects.py`)

New functions:

- `main_worktree(cwd) -> Path | None`: the parent of
  `git rev-parse --path-format=absolute --git-common-dir` when it ends in `/.git`; otherwise the
  toplevel. Computed directly; `detect()` is unchanged for audits.
- `normalize_remote(url) -> str`: strip `user[:password]@`, strip a trailing `.git` and `/`; turn
  `git@host:owner/repo` and `ssh://git@host/owner/repo` into `host/owner/repo`; lowercase the host;
  keep the path's case.
- `register(conn, name, cwd, no_remote) -> dict`: in one transaction, find a row whose slug equals
  the main worktree's folder name and that is not registered; adopt it, or create a new row with
  slug from `--name` or the folder name. Insert the `path` locator and, unless `--no-remote`, the
  `remote` locator. Set `registered_at`. If a locator already belongs to another project, fail
  with `invalid_value` naming that project.
- `relink(conn, slug, cwd)`: add the current main worktree path (and remote) as locators of a
  registered project.
- `rename(conn, slug, new_slug)`: change the slug; locators are untouched.
- `resolve_registered(conn, slug, cwd, *, global_ok) -> dict | None`: the order below. Returns
  `None` for the global scope.

Resolution order for lesson and project commands:

1. `--global` → global scope (only where the command allows it).
2. `--project <slug>` → that project; it must be registered.
3. The `path` locator that is the longest prefix of the real working directory (symlinks resolved;
   prefix match on whole path segments).
4. The `remote` locator equal to `normalize_remote(origin)` of the git toplevel.
5. Otherwise `project_not_registered`, hint `chanchi project register` (or `--global`).

Audit commands keep `identify()` and `ensure()`. `ensure()` gains one step before its slug lookup:
if steps 3 or 4 find a registered project, use it. This keeps a renamed, registered project from
being split by the next `change open`. `resolve_project()`'s hint changes to mention
`chanchi project register`.

Writer roles: `writer_roles(conn, project_id | None) -> tuple[str, ...]` returns the scope's rows,
or `DEFAULT_WRITER_ROLES` when it has none. `set_writer_roles(conn, project_id | None, roles)`
replaces the scope's rows in one transaction. Changing them is itself a guarded write: the caller
must declare a current writer role of that scope or be the `human` agent.

### 3. Lessons (`lessons.py`)

**Actor.** Every write command takes three identity flags, kept out of the JSON body so a stage-3
hook can read them from the command line:

- `--as <role>`: the role the caller declares.
- `--author <agent:model[:effort]>`: parsed by `modelspec.parse`, which validates the agent against
  `taxonomy.ALL_AGENTS` and the effort against `taxonomy.EFFORTS`. The model name is free text.
  `author_model_id` is set by looking up `(agent, model)` in `models`; a miss leaves it NULL and is
  not an error. Nothing is ever inserted into `models`.
- `--conversation <id | label>`: required, non-empty.

`check_writer(conn, scope, actor)` passes when `actor.agent == "human"`, or when `actor.role` is in
`writer_roles(scope)`. Otherwise `not_a_writer`, with the role seen, the scope's roles and the
`chanchi project writers` command.

**Scope of each check:**

| Command | Scope checked |
|---|---|
| `add`, `repeat`, `modify` | the lesson's origin (project or global) |
| `review`, `reopen` of a `project` or `particular` lesson | its origin project |
| `review`, `reopen` of an `agnostic` lesson | global |
| `apply`, `retire`, `decline`, `reopen-site` with `--site project` | the resolved project |
| the same with `--site global` | global |

**Commands and their rules** (each writes one `lesson_events` row per state change, inside the same
transaction):

- `add --json -`: reads the JSON body (`what_happened`, `evidence`, `cause`, `prevention`,
  `proposal`, `general_rule`, `generality`, `severity`, `target_kind`, `target`, optional
  `particular_justification`, `tags`, `change`, `session`, `incidents`). Validates enums. `change`
  is a change ref in the origin project; `session` is a session ref in that change (latest
  attempt); `incidents` are ids that must belong to that change. Captures `git_head` with
  `git rev-parse HEAD` when inside a repository. Rejects `severity = blocking` with a hint that
  lesson severity uses `critical`. Runs the duplicate check (§4); `--force-new` skips the block and
  logs a `force_new` event.
- `repeat <id> --evidence ... [--incident N]`: adds 1 to `occurrences`, appends the evidence to the
  event note, and links the incident. Refused on `duplicate` (points to `duplicate_of`).
- `modify <id> --json -`: replaces content fields. Only `pending` or `postponed`, and only when
  `--conversation` equals `author_conversation`.
- `review <id> --decision ... --reason ... [--reason-code ...] [--of N]`: only `pending` or
  `postponed` (and `postpone` only from `pending`). Refused with `self_review` when `--conversation`
  equals `author_conversation`. `model_weakness` requires a linked session. `duplicate` requires
  `--of N`, N different and not itself a duplicate; N gets this lesson's occurrences.
- `reopen <id> --reason`: from `rejected`, `postponed` or `duplicate` back to `pending`; clears
  review fields except history.
- `apply <id> --site global|project --where "<path> [lesson #N] @ <commit?>"`: only `approved`.
  Inserts or updates the site row to `applied`. `where_` must contain the tag `[lesson #<id>]`.
  Then, for each `replaced_id` in `lesson_replaces`, if that lesson has an `applied` row at the
  same place, set it to `retired` with reason "replaced by #<id>" and an event.
- `replaces <id> --add N | --remove N`: edits `lesson_replaces`; allowed while `pending`,
  `postponed` or `approved`.
- `retire <id> --site ... --reason`: from `applied` to `retired` at that place only.
- `similar "<text>"`, `list`, `show <id>`, `summary`, `export`: read-only.

`show` returns the lesson, its sites, replaces, incidents (with their session and model), and all
events. `summary` returns counts by status and generality, counts of `applied` sites per place, the
rate of `force_new` events, and (stage 2) the inbox size. `export` orders by generality
(`agnostic`, `project`, `particular`), then severity (`critical` first), then `occurrences`
descending; it takes `--status` (default `pending,postponed`), `--generality`, `--target-kind`,
`--since`, `--limit` (default 20) and `--format md|json`.

### 4. Duplicate detection (`dedup.py`)

- `tokens(text) -> set[str]`: lowercase; split on any character that is not a letter or a digit;
  keep tokens with 4 or more characters that are not in `data/stopwords_en.txt`.
- `coverage(a, b) = |a ∩ b| / min(|a|, |b|)` (0 when either is empty).
- `similar(text, candidates, limit=5)`: candidates sharing at least 2 tokens, ordered by coverage,
  then shared count.
- `blocking_match(new, candidates)`: the first candidate that matches either test:
  - full text (`what_happened` + `general_rule` + `proposal`): at least 4 shared tokens and
    coverage of at least 0.30;
  - general rule alone: at least 3 shared tokens and coverage of at least 0.50.

Candidates for blocking: lessons in the new lesson's scope (its origin project, or global) plus
every `agnostic` lesson, with status `pending`, `postponed` or `approved`. Candidates that only
warn: the same set with status `rejected` or `duplicate`, approved lessons whose every site is
`retired`, and `project` lessons of other projects (reported as "possibly agnostic"). The block
error `duplicate_lesson` carries the matched id, its general rule and the shared tokens, and hints
`chanchi lesson repeat <id>` or `--force-new`.

The four numbers live in one constant each in `dedup.py`. They were tuned on short Spanish texts
and are starting values.

### 5. Inbox and verify (stage 2, no migration)

**Inbox** for resolved project P:

```sql
SELECT l.* FROM lessons l
WHERE l.generality = 'agnostic'
  AND l.status = 'approved'
  AND EXISTS (SELECT 1 FROM lesson_sites s
              WHERE s.lesson_id = l.id AND s.site = 'project' AND s.state = 'applied')
  AND NOT EXISTS (SELECT 1 FROM lesson_sites s
                  WHERE s.lesson_id = l.id AND s.site = 'project' AND s.project_id = :p)
  AND NOT EXISTS (SELECT 1 FROM lesson_sites s
                  WHERE s.lesson_id = l.id AND s.site = 'global' AND s.state = 'applied')
  AND (:all OR l.reviewed_at >= :registered_at OR l.severity IN ('critical', 'high'))
ORDER BY <generality, severity, occurrences> LIMIT :limit;
```

A lesson applied globally does not reach any inbox: the global fix already covers every project.
Each item also lists the lessons it replaces that P has `applied`, so P sees "replaces #42, which
you applied".

`decline <id> --reason ... | --not-applicable` inserts P's site row as `declined` or
`not_applicable`. `reopen-site <id> --reason` deletes P's `declined` or `not_applicable` row (with
an event), returning the lesson to the inbox.

**Verify** for resolved project P (reads files only):

1. For each site row of P with `where_`, take the path before ` [lesson #`; resolve it against P's
   `path` locator (or `~` for global rows with `--global`).
2. Report `missing_tag` for `applied` rows whose file lacks `[lesson #N]`, `stale_tag` for
   `retired` rows whose file still has it, and `missing_file` when the path does not exist.
3. Scan every distinct path from step 1 (plus `--scan <path>` repeats) for `[lesson #(\d+)]` and
   report `unknown_tag` for ids with no lesson, or with no site row for P.
4. Report per file: line count and number of `[lesson #N]` tags.

### 6. The skill (`skills/chanchi-lessons/SKILL.md`)

Two sections, in English, short sentences, every sentence changes behavior:

- **Record** (writer roles, at the end of a conversation or when something fails): the five
  principles; when to record (the five triggers); fix first; for each failure write the cause and
  the general rule ("if you cannot write the cause, you have the symptom; if you cannot write the
  rule, you do not understand the failure yet"); `lesson similar`, and read pending general rules;
  `repeat` or `add`; a field guide with the severity table and the generality rule; one full
  example; "do not review or apply your own lesson; say what you recorded and its id".
- **Review** (maintenance conversations): `summary`; `export`; for each lesson: cause or symptom,
  an existing rule that covers it, whether the rule holds outside the case, its cost in context,
  the cheapest place (hook, permission or CLI check before a role line), what it replaces; decide
  with a reason and a reason code; apply, tag the file with `[lesson #N]`, record `--where`; then
  `inbox` and `verify` (stage 2).
- **Lines to paste**: the writer-role block for the planner's role file; the reporter line ("If
  something went wrong, say so in your report; do not record it in chanchi"); the project-rules
  line pointing the writer role to this skill at the end of each conversation.

### 7. Stages 3 and 4: contract and dependencies

Specified here; the file-level plan is written after Open Questions Q1 to Q5 are answered.

- **Migration `005_runs.sql`**: table `runs` (`agent`, `conversation_id`, `UNIQUE(agent,
  conversation_id)`, `source`, `project_id`, `role`, `role_source`, `model_raw`, `model_id`,
  `effort`, `session_id`, `opened_at`, `last_seen_at`, `retro_requested_at`, `retro_at`,
  `retro_notes`).
- **`chanchi hook check --event session-start|pre-tool|stop`**: input is one versioned JSON object
  on stdin, already normalized by the adapter (`v`, `harness`, `harness_version`, `event`,
  `conversation_id`, `parent_conversation_id`, `actor_role`, `role_source`, `is_subagent`, `cwd`,
  `tool`, `command`, `model`). Output is always exit 0 with `{"decision", "message", "context"}`.
  Any error, lock, missing git, unregistered project or schema mismatch means `allow` plus a
  logged warning. It opens the database without `bootstrap()` and never migrates.
- **Actor**: from the event (`agent_type` in Claude Code), then the run's role, then
  `CHANCHI_ROLE` set by the launcher, then `unknown`. `pre-tool` blocks a guarded lesson command
  when the actor is not a writer or differs from `--as`.
- **Fast path**: the adapter calls chanchi only when the shell command contains `chanchi`.
- **Stop**: writer roles in registered projects only; once per run; respects `stop_hook_active`
  (Claude Code) and `continuation_active` (agy); never closes the run; none for opencode unless a
  loop-safe mechanism is verified.
- **Install**: global only; Claude Code entries recognized by their exact command string; an agy
  top-level `"chanchi"` group; a standalone opencode plugin file with a header marker; atomic write
  after a backup; refuse invalid JSON; absolute path to the binary; `uninstall` removes only
  chanchi's entries; `hooks status` shows the last event per harness.
- **Order**: stage 3 is the contract, fixture tests and the Claude Code adapter (needs Q1). Stage 4
  is agy (needs Q2, Q3, Q5) and then opencode (needs Q4).

### Rollout and rollback

- Migration 004 only adds a column and tables. Existing audit commands behave the same on
  unregistered projects, and `ensure()` only changes for registered ones.
- The operational database migrates itself on the next command, after its usual
  `chanchi.db.bak-v3` backup.
- Rollback is forward-only, as today: an older chanchi on a version-4 database fails with
  `schema_too_new` on every command. Rolling back means restoring `chanchi.db.bak-v3` and losing
  the lessons and registrations recorded since. The README states this.
- No hook is installed in stages 1 and 2, so nothing runs inside the harnesses until stage 3.

## Alternatives Considered

### Alternative A: Project id in a committed file in each project

- **Pros**: identity travels with the repository; no lookup by path or remote.
- **Cons**: needs a commit in every project, and in every new project; a public tool would ask
  every user to commit chanchi files.
- **Reason for Rejection**: Rejected by author: registration must live in chanchi's database and
  must not require a commit.

### Alternative B: Keep the current slug detection and add no registration (zoom-out v1)

- **Pros**: no new tables or commands; `ensure()` already works for audits.
- **Cons**: a renamed folder or a second clone splits or merges history; nested repositories
  resolve to the wrong project; there is no scope to hold writer roles.
- **Reason for Rejection**: Rejected by author: a project must be registered before it can record
  lessons, and writer roles need a scope.

### Alternative C: Resolve by remote URL first

- **Pros**: survives moving the folder; recognizes a new clone with no step.
- **Cons**: inside a nested repository the remote is the inner repository's, so the lesson lands in
  the wrong project or fails; forks that share an `origin` collide.
- **Reason for Rejection**: Rejected by author: the longest registered path is checked first; the
  remote is the second step, and `--no-remote` opts out.

### Alternative D: Guard on "is this a subagent?" (the source method's hook)

- **Pros**: one field in Claude Code's hook input; simple.
- **Cons**: roles also run as top-level processes started with `--agent`, so an executor in its own
  pane passes.
- **Reason for Rejection**: Rejected by author: the check is on the role, not on whether the caller
  is a subagent.

### Alternative E: Guard on the role of the conversation

- **Pros**: one lookup per conversation; no per-event field needed.
- **Cons**: a Claude Code subagent's events carry its parent's `session_id`, so an executor
  subagent spawned by the planner passes as the planner.
- **Reason for Rejection**: Rejected by author: the stage-3 hook decides on the actor of each
  event; the CLI checks the declared role on every write.

### Alternative F: "No role means a person, so it can write"

- **Pros**: a person typing in a plain conversation needs no setup.
- **Cons**: in a harness that hides the role, every agent has no role and passes.
- **Reason for Rejection**: Rejected by author: an unknown role is refused; only the `human` agent
  passes without a writer role.

### Alternative G: One status per lesson, with apply and retire fields on the lesson

- **Pros**: the source method's shape; one table; simple queries.
- **Cons**: cannot say that a rule is applied in two projects, declined in a third and retired in
  one; retiring in one place would retire it everywhere.
- **Reason for Rejection**: Rejected by author: the decision on the rule (`lessons.status`) is
  separate from each place it is applied (`lesson_sites`).

### Alternative H: Push agnostic lessons to every inbox when recorded

- **Pros**: projects see new rules early.
- **Cons**: projects adopt rules nobody reviewed, against principle 4; a new project inherits the
  whole backlog; the inbox grows with projects times lessons.
- **Reason for Rejection**: Rejected by author: a lesson reaches the inbox only once it is approved
  and applied to one project; new projects see only `high` and `critical` backlog by default.

### Alternative I: A stop hook that asks every conversation for a retrospective

- **Pros**: no conversation ends without the question.
- **Cons**: `Stop` and `session.idle` fire after every reply, not at the end; reporter roles get
  asked for something they may not do; it pushes empty retrospectives, against "record only what
  really went wrong".
- **Reason for Rejection**: Rejected by author: stage 1 relies on the skill and a project rule
  line; stage 3 asks writer roles once per conversation and never closes it.

### Alternative J: A `runs` table and hooks in stage 1

- **Pros**: conversation identity and role come from the harness from day one.
- **Cons**: four of the facts it depends on are unverified in agy and opencode; it would delay the
  core and build adapters that may only partly work.
- **Reason for Rejection**: Rejected by author: stage 1 takes identity as flags; runs and hooks
  arrive in stage 3 after verification.

### Alternative K: Free harness values validated against `models.agent`

- **Pros**: any harness a user adds would work.
- **Cons**: the code fixes the list in `taxonomy.ALL_AGENTS`, and `modelspec.parse` and
  `catalog.add_model` reject anything else; supporting it means changing the catalog.
- **Reason for Rejection**: Rejected by author: out of scope; validation uses
  `taxonomy.ALL_AGENTS`.

### Alternative L: Add unknown models reported by authors or hooks to the catalog

- **Pros**: every lesson's model links to a catalog row.
- **Cons**: the new rows would enter `recommend`'s exploration list and its Hugging Face ordering.
- **Reason for Rejection**: Rejected by author: the model is stored as raw text; the catalog link
  is set only on an exact match.

### Alternative M: Policy as SQLite `CHECK` constraints (the source method's approach)

- **Pros**: rules hold even if someone writes to the database another way.
- **Cons**: SQLite needs a table rebuild to change a `CHECK`; thresholds and enum sets are expected
  to change.
- **Reason for Rejection**: Rejected by author: `CHECK` keeps only structural invariants; enum sets
  and policy are validated in `taxonomy.py` and `lessons.py`, as `003_model_capabilities.sql`
  already does.

### Alternative N: Two skills (record and review) and a `rules snippet` command

- **Pros**: each skill is shorter; the command prints the lines to paste.
- **Cons**: a second skill to link and keep in sync; a command that prints fixed text is code with
  no logic.
- **Reason for Rejection**: Rejected by author: one skill with two sections carries the lines to
  paste.

### Alternative O: Retire rules through a `replaces` list that names file lines, not lessons

- **Pros**: could retire the 39 hand-copied rules that are not lessons.
- **Cons**: free text cannot be checked or tracked; it would need the import that is a non-goal.
- **Reason for Rejection**: Rejected by author: `lesson_replaces` holds lesson ids only; a file
  rule that is not a lesson is named in the proposal text.

---

## Non-Functional Requirements

- **Security and privacy**: lessons hold text that agents write, which can include paths, commit
  ids and quotes from reports. Everything stays in the local database; the `chanchi` package keeps
  importing no network module (`tests/test_no_network.py`). `lesson add` does not read files.
  `lesson verify` reads only paths recorded in site rows or passed with `--scan`.
- **Performance**: stages 1 and 2 add no work to existing commands except one locator lookup in
  `ensure()` (one indexed query and at most one extra `git` call, only when no slug row matches
  first). The duplicate check reads candidate lessons into memory; at hundreds of lessons this is
  a few milliseconds.
- **Context cost**: the skill is the only text agents load. It is kept short, and the review section
  makes context cost an explicit review question.
- **Rollout and rollback**: see "Rollout and rollback" in the Technical Plan.

---

## Future Improvements

- **Context budget per target file**: refuse approving a `role` fix for a file over a set size
  unless it replaces another rule. Revisit when `lesson verify` shows real growth.
- **Import of hand-copied rules**: a one-off command that turns tagged rules in files into
  applied lessons, so they can be replaced and retired.
- **Draft queue for reporter roles**: let non-writers file a draft that only writers turn into a
  lesson, if writers keep missing failures mentioned in reports.
- **Semantic duplicate search**: if word overlap misses too many duplicates.
- **Open harness list**: an `agents` table, if a user needs a harness beyond the four.

## Additional Resources

- [Brief, Revision 2](continuous-improvement.brief.md) and the seven Goldfish reports
  summarized in it.
- `src/chanchi/projects.py`, `db.py`, `errors.py`, `taxonomy.py`, `modelspec.py`, `catalog.py`,
  `skills_link.py`; `src/chanchi/migrations/001_init.sql`, `003_model_capabilities.sql`.
- README sections "Give the skills to a project" and "Databases and migrations".

---

## Detailed Implementation Plan

Stages 1 and 2 only. Stages 3 and 4 get their plan after Open Questions Q1 to Q5 are answered.
Stage 1 and stage 2 are separate branches and merges; stage 2 starts after stage 1 is on `main`.

### Stage 1: Target Files to Create/Modify

#### 1. `src/chanchi/migrations/004_lessons.sql` (Create)

- **Type / Scope**: SQL migration.
- **Proposed Changes**: exactly the schema in Technical Plan §1: `ALTER TABLE projects ADD COLUMN
  registered_at`, tables `project_locators`, `writer_roles`, `lessons`, `lesson_sites`,
  `lesson_replaces`, `lesson_incidents`, `lesson_events`, and their indexes. A header comment names
  the migration and says enum sets are validated in `taxonomy.py`. No seed rows (the default writer
  role is applied in code).

#### 2. `src/chanchi/data/template.db` (Modify)

- **Type / Scope**: committed template database.
- **Proposed Changes**: regenerated with `uv run chanchi db migrate --template` and committed in the
  same commit as `004_lessons.sql`. `tests/test_db.py` fails if they drift.

#### 3. `src/chanchi/data/stopwords_en.txt` (Create)

- **Type / Scope**: data file, one lowercase word per line, `#` comments allowed.
- **Proposed Changes**: a standard English stopword list (function words such as `about`, `after`,
  `again`, `because`, `before`, `being`, `between`, `could`, `does`, `doing`, `during`, `each`,
  `from`, `have`, `having`, `into`, `more`, `most`, `other`, `over`, `same`, `should`, `some`,
  `such`, `than`, `that`, `their`, `them`, `then`, `there`, `these`, `they`, `this`, `those`,
  `through`, `under`, `until`, `very`, `were`, `what`, `when`, `where`, `which`, `while`, `will`,
  `with`, `would`, `your`), plus words common to every lesson that carry no meaning here (`agent`,
  `lesson`, `rule`, `session`). Words shorter than 4 characters are not listed, because they are
  dropped anyway. It ships inside the package (hatch already includes `src/chanchi/data`).

#### 4. `src/chanchi/taxonomy.py` (Modify)

- **Type / Scope**: Python module, enum sets.
- **Proposed Changes**: add `LESSON_TARGET_KINDS`, `LESSON_GENERALITIES`, `LESSON_SEVERITIES`,
  `LESSON_STATUSES`, `LESSON_DECISIONS`, `LESSON_REASON_CODES`, `LESSON_SITE_STATES`,
  `LOCATOR_KINDS`, `DEFAULT_WRITER_ROLES`, with the values in Technical Plan §1. Extend
  `describe()` so `chanchi taxonomy list` returns them under a `lessons` key. No change to existing
  sets.

#### 5. `src/chanchi/errors.py` (Modify)

- **Type / Scope**: Python module, error codes.
- **Proposed Changes**: add to `ERROR_CODES`: `project_not_registered`, `not_a_writer`,
  `self_review`, `duplicate_lesson`, `invalid_transition`, `lesson_not_found`. All exit with the
  existing validation exit code. Messages and hints:
  - `project_not_registered`: "this directory is not inside a registered project"; hint
    `chanchi project register` or `--global`.
  - `not_a_writer`: "role <r> cannot write lessons in <scope>"; `valid_values` = the scope's writer
    roles; hint `chanchi project writers <scope> --set ...`.
  - `self_review`: "lesson #N was recorded in this conversation"; hint "review it from another
    conversation".
  - `duplicate_lesson`: "lesson looks like #N"; carries the matched general rule and shared tokens;
    hint `chanchi lesson repeat N --evidence ...` or `--force-new`.
  - `invalid_transition`: "lesson #N is <status>; <command> needs <allowed states>".
  - `lesson_not_found`: "no lesson #N"; hint `chanchi lesson list`.

#### 6. `src/chanchi/projects.py` (Modify)

- **Type / Scope**: Python module, project identity.
- **Proposed Changes**: add `main_worktree`, `normalize_remote`, `register`, `relink`, `rename`,
  `list_projects`, `show`, `resolve_registered`, `writer_roles`, `set_writer_roles`, as specified in
  Technical Plan §2. In `ensure()`, before the slug lookup, call the locator lookup (path prefix,
  then remote) and return a registered match. Change the `resolve_project()` hint to mention
  `chanchi project register`. `detect()` and `identify()` keep their behavior.

#### 7. `src/chanchi/dedup.py` (Create)

- **Type / Scope**: Python module, pure functions.
- **Proposed Changes**: `load_stopwords() -> frozenset[str]` (cached), `tokens(text)`,
  `coverage(a, b)`, `similar(text, candidates, limit=5)`, `blocking_match(new, candidates)`, and the
  constants `MIN_TOKEN_LEN = 4`, `SIMILAR_MIN_SHARED = 2`, `FULL_MIN_SHARED = 4`,
  `FULL_MIN_COVERAGE = 0.30`, `RULE_MIN_SHARED = 3`, `RULE_MIN_COVERAGE = 0.50`, as in Technical
  Plan §4. Candidates are plain dicts; the module does not touch the database.

#### 8. `src/chanchi/lessons.py` (Create)

- **Type / Scope**: Python module, lesson rules and transitions.
- **Proposed Changes**:
  - `Actor` dataclass (`role`, `agent`, `model_raw`, `model_id`, `effort`, `conversation`) and
    `make_actor(conn, as_role, author_spec, conversation)` using `modelspec.parse` and a direct
    `SELECT id FROM models WHERE agent = ? AND model = ?`.
  - `check_writer(conn, scope_project_id, actor)` per Technical Plan §3.
  - `add`, `repeat`, `modify`, `review`, `reopen`, `apply`, `set_replaces`, `retire`, `similar`,
    `list_lessons`, `show`, `summary`, `export`, each in one `db.transaction` for writes, each
    writing `lesson_events`, with the preconditions and scopes of Technical Plan §3 and the state
    tables of the brief §4.
  - Required text fields validated with `record._required_text` (reused, not copied).
  - `git_head(cwd)` via `git rev-parse HEAD`, `None` outside a repository.
  - `export(..., fmt="md")` renders Markdown: one section per lesson with its fields, sites,
    incidents and occurrences.

#### 9. `src/chanchi/cli.py` (Modify)

- **Type / Scope**: Python module, argument parsing and handlers.
- **Proposed Changes**:
  - New group `project`: `register [--name] [--no-remote]`, `relink <slug>`,
    `rename <slug> <new>`, `list`, `show [<slug>]`, `writers [<slug>|--global] [--set roles]
    [--as] [--author] [--conversation]` (without `--set` it lists).
  - New group `lesson`: `add`, `repeat`, `modify`, `review`, `reopen`, `apply`, `replaces`,
    `retire`, `similar`, `list`, `show`, `summary`, `export`. Write commands share a parent parser
    with `--as`, `--author`, `--conversation` (all required) and `--global`. `add` and `modify`
    take `--json -` (stdin) or `--json <file>`; `add` takes `--force-new`.
  - Handlers only parse and call `projects` or `lessons`, as the existing handlers call `record`.
  - The `--project` help text changes from "default: git toplevel name" to "default: the
    registered project for this directory, else the git toplevel name".

#### 10. `src/chanchi/render.py` (Modify)

- **Type / Scope**: Python module, text output.
- **Proposed Changes**: none to the renderer itself unless `--format text` of `lesson show`
  produces unreadable nesting; then add a flat layout for long text fields (wrap at 100 columns).
  Verified during implementation with the `lesson show` text output; if no change is needed, this
  file is not touched.

#### 11. `src/chanchi/skills_link.py` (Modify)

- **Type / Scope**: Python module.
- **Proposed Changes**: add `chanchi-lessons` to `SUGGESTED_CONFIG_LINE`. `available_skills()`
  already picks up any `chanchi-*` folder with a `SKILL.md`, so linking needs no change.

#### 12. `skills/chanchi-lessons/SKILL.md` (Create)

- **Type / Scope**: agent skill.
- **Proposed Changes**: frontmatter `name: chanchi-lessons` and a description that triggers at the
  end of a conversation, after an audit that found a failure, and in maintenance conversations.
  Body as in Technical Plan §6: principles, when to record, the record steps, the field guide with
  the severity table and generality rule, one full `lesson add` example with a heredoc, the review
  steps and questions, and the three lines to paste.

#### 13. `skills/chanchi-session-audit/SKILL.md` (Modify)

- **Type / Scope**: agent skill.
- **Proposed Changes**: one paragraph after the verdict step: "If the audit found a failure of the
  process (not only of the model), after recording incidents, follow `chanchi-lessons` to record a
  lesson that links the session and incidents. A failure that is only one model's weakness stays an
  incident."

#### 14. `README.md` (Modify)

- **Type / Scope**: documentation.
- **Proposed Changes**: new section "Lessons" after "Everyday commands": what a lesson is, what it
  improves (global and project setup, not code, not ratings), `project register`, writer roles,
  the record and review commands, the lines to paste, and the stage-1 limit (the role is declared,
  not checked against the harness). Update "Give the skills to a project" to list
  `chanchi-lessons`. In "Databases and migrations", add the rollback note for version 4.

#### 15. `tests/test_projects.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**: `normalize_remote` cases (ssh, https, credentials, `.git`, trailing slash,
  host case); `main_worktree` from a linked worktree; `register` creates, adopts an unregistered
  slug row, and refuses a locator owned by another project; resolution by longest path prefix
  inside a nested repository; resolution by remote after a move; `project_not_registered` outside;
  `ensure()` returns the registered project after `rename`; audits on unregistered projects behave
  as before.

#### 16. `tests/test_dedup.py` (Create)

- **Type / Scope**: unit tests.
- **Proposed Changes**: tokenization (case, punctuation, 3-letter words dropped, stopwords
  dropped); coverage on empty sets; a near-duplicate told with another case blocks by the rule
  test; a near-duplicate by full text blocks; a different lesson sharing 2 or 3 words passes;
  `similar` returns at most 5 ordered by coverage. Fixtures in `tests/fixtures/lessons/*.json`.

#### 17. `tests/test_lessons.py` (Create)

- **Type / Scope**: unit tests, ported from the source method's test list plus the additions.
- **Proposed Changes**:
  - No general rule, no record. A particular lesson at `medium`, or without justification, is
    refused; a `critical` justified one is recorded.
  - `blocking` severity is refused with the hint.
  - A non-writer role is refused; `human` passes; a custom writer role set with
    `project writers` passes; global scope uses global writer roles.
  - Review from the recording conversation is refused; from another passes.
  - `apply` on a non-approved lesson is refused; `where_` without the tag is refused.
  - `modify` from another conversation, or after approval, is refused.
  - `duplicate` moves occurrences to the original and refuses itself.
  - `model_weakness` without a linked session is refused.
  - Applying a lesson that replaces another retires it at the same place only.
  - Every state change writes one event with actor, conversation and states.
  - `export` order: generality, then severity, then occurrences; default limit 20.
  - `author_model_id` is set on an exact catalog match and NULL otherwise; no row is added to
    `models`.

#### 18. `tests/test_taxonomy.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**: `describe()` includes the lesson sets; the sets match the values in this
  document.

#### 19. `tests/test_cli.py` and `tests/test_cli_integration.py` (Modify)

- **Type / Scope**: CLI tests.
- **Proposed Changes**: argument parsing for the new groups; JSON envelopes; each new error code
  appears with `field`, `valid_values` and `hint`; an end-to-end run of CUJs 1, 2, 3, 4 and 7 in a
  temporary `CHANCHI_DB` with temporary git repositories (including a nested one).

#### 20. `tests/test_skills_content.py` (Modify)

- **Type / Scope**: skill tests.
- **Proposed Changes**: the skill list becomes the three skills; frontmatter checks run on
  `chanchi-lessons`; every `chanchi ...` command quoted in the skill parses with the real parser.

#### 21. `tests/test_skills_link.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**: `link` creates the `chanchi-lessons` link; `SUGGESTED_CONFIG_LINE` names
  it.

#### 22. `docs/designs/continuous-improvement.md` (Create)

- **Type / Scope**: design document.
- **Proposed Changes**: this document, finalized. The brief stays next to it.

### Stage 2: Target Files to Create/Modify

#### 23. `src/chanchi/lessons.py` (Modify)

- **Proposed Changes**: add `inbox`, `decline`, `reopen_site` and `verify`, per Technical Plan §5.
  `summary` adds the inbox size for the resolved project.

#### 24. `src/chanchi/cli.py` (Modify)

- **Proposed Changes**: add `lesson inbox [--all] [--limit]`, `lesson decline <id> (--reason ... |
  --not-applicable)`, `lesson reopen-site <id> --reason ...`, `lesson verify [--global]
  [--scan <path>]...`.

#### 25. `skills/chanchi-lessons/SKILL.md` (Modify)

- **Proposed Changes**: the review section adds `lesson inbox` (apply, decline or not applicable
  for each item) and `lesson verify` (fix every `missing_tag` and `stale_tag`).

#### 26. `README.md` (Modify)

- **Proposed Changes**: the "Lessons" section adds the inbox and verify, and how the backlog
  filter works for a newly registered project.

#### 27. `tests/test_lessons.py` (Modify)

- **Proposed Changes**: inbox shows only approved agnostic lessons applied to one project and not
  decided by this one; a globally applied lesson never appears; the backlog filter by registration
  date and severity, and `--all`; decline and `reopen-site`; an item that replaces a lesson this
  project applied is marked. Verify reports `missing_tag`, `stale_tag`, `unknown_tag`,
  `missing_file`, and per-file size, on fixture files in a temporary directory.

#### 28. `tests/test_cli_integration.py` (Modify)

- **Proposed Changes**: end-to-end run of CUJs 5 and 6 across two temporary registered projects.

### Verification Plan

- **Build**: `uv tool install --editable .` still installs; `chanchi --version` runs.
- **Unit and integration tests**: `uv run pytest`, all green, including the template drift check in
  `tests/test_db.py` and `tests/test_no_network.py`.
- **Migration on real data**: copy the owner's operational database to a temporary
  `CHANCHI_DB`, run any command, and check that `chanchi.db.bak-v3` exists, `user_version` is 4,
  and `chanchi show <existing change>` returns the same result as before.
- **Manual journey**: in a scratch `CHANCHI_DB`, register two temporary projects (one with a nested
  repository), then run CUJs 1 to 7 by hand with the commands in this document, and keep the JSON
  outputs as evidence in the stage's report.
- **Skill check**: `chanchi skills link` into a scratch directory creates `chanchi-lessons` for
  both `.agents/skills` and `.claude/skills`.

---

*Drafted with EGM*
