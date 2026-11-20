# Continuous Improvement (Lessons) in chanchi

- **Author:** Iván R
- **Status:** Proposed
- **Date:** 2026-11-19
- **Revision:** 3 (after the Goldfish review in
  [reviews/continuous-improvement/](reviews/continuous-improvement/consolidated_review_report.md)
  and its readiness re-audit,
  [implementation_readiness_report_round2.md](reviews/continuous-improvement/implementation_readiness_report_round2.md))
- **Brief:** [continuous-improvement.brief.md](continuous-improvement.brief.md)
  (Revision 2). This document is complete without it.

---

## Overview

chanchi records how agents perform: each audited session, each incident, and the model ratings
that follow. It does not record what the agent **setup** should learn from a failure. This design
adds **lessons** to chanchi.

A lesson is written by the agent that coordinates the work (or by the person) after something went
wrong. It holds what happened, the evidence, the cause, and one general rule that would have
prevented it. It names the one place where the fix belongs. A different conversation later reviews
it, decides, applies it by hand, and records where it landed.

The method comes from a per-project process the owner uses in another setting (called "the source
method" below). That process is private; this document restates everything it needs. Its five principles:

1. **Fix first, then record.** A lesson is for learning; it does not replace the fix.
2. **Record only what really went wrong.** These are the five triggers: a wrong result, work that
   had to be redone, an existing rule that was not followed, a control that did not stop what it
   should, or an assumption that turned out false. A run that went well records nothing.
3. **From general to particular.** Every lesson carries a general rule. Rules that only serve one
   case become noise and narrow the model.
4. **The author does not judge.** A different conversation reviews, so the person or agent that
   made the mistake does not rule on it.
5. **What matters does not depend on the model obeying.** Hard rules are enforced by the database,
   the CLI or a hook, not by a line in a prompt. In stages 1 and 2 the CLI checks only what the
   caller declares (see "Actor and threat model" in §3); stage 3 adds the hook.

Lessons improve the setup that guides agents, at two levels:

- **Global** (the user's home setup, shared by every project): global skills such as
  `~/.agents/skills/*` and `~/.claude/skills/*`, global agents of each harness, global rules files,
  hooks and permissions of each harness, and chanchi's own skills.
- **Project**: the project's role definitions and their per-harness wrappers
  (`.claude/agents`, `.agents/agents`, `.opencode/agents`), project skills, rules files
  (`AGENTS.md`, `CLAUDE.md`, `openspec/config.yaml`) and workflows.

Lessons do not fix the project's code: code is fixed before the lesson is recorded. They do not
rate models either. A failure caused by one model's weakness is an incident, and it lowers that
model's score in `chanchi recommend`.

chanchi stores, deduplicates, orders and tracks lessons, and compares what it recorded with what
the files say. It never edits a role, skill, prompt, rules file or harness setting, except for the
hook entries a user installs on purpose in stage 3.

Three harnesses are in scope: Claude Code, agy (Google's Antigravity CLI) and opencode. They are
the values of `taxonomy.ALL_AGENTS`, together with `human` for a person.

The work ships in four stages. This document gives the full plan for stages 1 and 2, which depend
only on chanchi's own code. Stages 3 and 4 (hooks in the harnesses) are specified by their
invariants and dependencies; their file-level plan is written after the last open harness question
(Q6) is answered.

## The Problem

The owner runs multi-agent work across several projects and the three harnesses. Examples of
failures that have come back more than once: an executor reports tests that never ran, a role
reads a skill only partly, a plan states a rule outside its real scope. Each time, the fix today is
one of these (the project figures below come from two of the owner's private projects and are an
illustration, not requirements):

1. **Nothing is written down.** The failure is fixed in the work and forgotten. The next
   conversation, in the same or another project, repeats it.
2. **A rule is pasted into a role file by hand, by the agent that made the mistake**, in the same
   conversation. Nobody checks whether the cause was understood, whether a rule already covers it,
   or whether the rule is worth its cost in context. One of the owner's projects has a "Lessons
   learned" section in every role that says "the planner appends dated, sourced rules here after
   audits". All of those sections are empty: the practice has never been used.
3. **Rules are copied between projects by hand.** One project carries 30 rules in its roles and 9
   in its skills, each tagged with the name of the older project it came from. Nothing records
   which rules a project took, skipped or never saw, or which ones were later found wrong.

Three things make this worse over time:

- **Every rule costs context in every run.** One project's role folder is 1,932 lines; its README
  says every model reads it in full at every start. Rules are only ever added; nothing tracks which
  to merge or remove.
- **A fix can land in the wrong place.** A rule that should hold everywhere can land in one
  project's file; a rule that only one harness needs can land in a role shared by all three; a rule
  that must never be broken can be written as a prompt line that a model can ignore.
- **A model weakness can become a permanent rule.** When one model fails, the usual fix adds an
  instruction that every model then pays for, instead of rating that model lower.

The method above addresses most of this: record a lesson with a general rule, review it in a
different conversation, apply it, and record where. chanchi already holds per-project data for
every project on the machine in one SQLite database, so global and per-project lessons can live
next to the audits they come from.

The proposed solution ships in four stages. Each stage ships with its migration (if any), the
regenerated template database, its tests, and its skill and README changes.

| Stage | Migration | Ships | Depends on |
|---|---|---|---|
| 1 | `004_lessons.sql` | project registration by path; writer roles per project and global; lessons with the full record, the author's harness, model and effort, and links to changes, sessions and incidents; decisions tracked apart from the places a lesson is applied; duplicate blocking; the `chanchi-lessons` skill | nothing |
| 2 | none | the inbox (approved agnostic rules offered to other projects, which apply or decline them); `replaces` retirement on apply; `lesson verify` (database against files) | stage 1 on `main` |
| 3 | `005_runs.sql` | hooks for Claude Code: conversation identity, the actor's role checked on lesson commands, one retrospective reminder for writer roles | stage 2; Q6 answered |
| 4 | none | the same hooks for agy and opencode, limited to what was observed working | stage 3 |

## Goals

**Stage 1**

- A project is registered with `chanchi project register`, stored only in chanchi's database. No
  file is added to the project.
- Every command run anywhere inside a registered project, including inside a nested git
  repository, resolves to that project: lesson and project commands, and the audit commands
  (`change open`, `change close`, `session ...`, `incident add`, `show`, `stats --project`).
- Session audits keep working for unregistered projects exactly as today.
- A lesson can only be recorded, reviewed or applied by a writer role of its scope (project or
  global), or by the `human` agent. An unknown role is refused. In stages 1 and 2 this guard stops
  a cooperative agent that declares its real role; it is not a control against an agent that lies
  (see "Actor and threat model").
- Every lesson carries a general rule, a generality (`agnostic`, `project`, `particular`) and a
  severity. A `particular` lesson needs `high` or `critical` severity and a justification.
- Every lesson records the author's harness, model (raw text, plus the catalog row when it
  matches) and effort, and may link a change, a session and incidents.
- A review from the same conversation that recorded the lesson is refused.
- A lesson can be applied to several places (global and per project), and retired in one place
  without affecting the others.
- `lesson add` blocks a near-duplicate of a `pending`, `postponed` or `approved` lesson, names
  it, and offers `lesson repeat` or `--force-new`.
- `lesson export` lists pending lessons from general to particular, then by severity, then by
  occurrences, with a default limit of 20.
- One skill, `chanchi-lessons`, of at most 150 lines and linked by `chanchi skills link`, covers
  recording (the retrospective at the end of a conversation) and review.

**Stage 2**

- `lesson inbox` shows, for one project, the agnostic lessons that are approved, applied to at
  least one project site, not applied at the global site, and not yet decided by this project. A
  project registered after a lesson's review sees that lesson only if it is `high` or `critical`,
  unless `--all` is passed.
- Applying a lesson retires, at the same place only, every lesson it `replaces`.
- `lesson verify` reports, from the files alone: applied lessons whose `[lesson #N]` tag is
  missing, retired lessons whose tag is still present, unknown tags, and the size of each target
  file.

**Stages 3 and 4** (goals only; plan after verification)

- `chanchi hook check` decides on lesson commands from the role of the event's actor, always exits
  0, allows on any internal error, and never migrates the database.
- A writer-role conversation in a registered project is asked for the retrospective at most once.
- Each harness adapter ships only the events whose behavior was observed in that harness.

## Non-Goals

- chanchi editing any role, skill, prompt or rules file.
- Opening the harness list beyond `taxonomy.ALL_AGENTS` (`claude`, `agy`, `opencode`, `human`).
- A shared or remote database, or sharing lessons between machines or people.
- Embedding or semantic search for duplicates.
- A hard context budget per file.
- A draft queue for reporter roles; they mention failures in their reports.
- Recognizing a moved folder or a second clone by its git remote. `project relink` covers both by
  hand (see Future Improvements).
- Importing the existing hand-copied rules as lessons.
- Requiring registration for session audits.
- Changing model scores from lessons.

## Open Questions

These block stage 3 or 4 only. Each was checked in the real harness with one case that must pass
and one that must fail. Q1 to Q5 were answered on 2026-11-19 (Claude Code 2.1.328, agy 1.5.12,
opencode 2.2.6); the evidence is in
[hook-facts-2026-11-19.md](reviews/continuous-improvement/hook-facts-2026-11-19.md).

- **Q1 (Claude Code), answered:** `agent_type` is present in `SessionStart`, `PreToolUse` and
  `Stop` when the conversation starts with `--agent`, and absent without it. A subagent's events
  share the parent's `session_id` and add `agent_id` and `agent_type`. `session_id` stays the same
  on resume (`SessionStart.source = "resume"`). A `PreToolUse` hook blocks by printing
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}` and
  exiting 0.
- **Q2 (agy), answered:** the conversation id is `conversationId` in every hook input. No hook
  input names the `--agent` role, so agy's role must come from the launcher (`CHANCHI_ROLE`).
  `SessionStart` adds text to the model's context only through
  `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}`; plain stdout is ignored.
- **Q3 (agy), answered:** the shell command is `toolCall.args.CommandLine`; the hook blocks with
  `{"decision": "deny", "reason": "..."}` and exit 0.
- **Q4 (opencode 2.2.6), mostly answered:** the plugin API is V2 (`export default { id, setup }`).
  Blocking works through `ctx.tool.hook("execute.before", ...)`, not `"tool.execute.before"`. Its
  input carries `"agent": "<name>"`. Still unverified: whether the role survives the TUI reopened
  with `opencode -s <id>` (it does for `opencode run -s <id>`).
- **Q5, answered:** agy 1.5.12; each fact above was observed, not taken from the CHANGELOG.
- **Q6 (Claude Code), open, blocks stage 3:** can a hook entry be limited to Bash commands whose
  text contains `chanchi`, or does every Bash call start the hook process? If every call starts
  it, the Claude Code adapter must be a small script that filters the command text before it
  starts Python (see §7).

## Critical User Journeys (CUJs)

### CUJ 1: The planner records a lesson after an audit (stage 1)

- **Given**: project A is registered; its writer roles are the default (`planner`); a Claude Code
  planner conversation (`opus`, effort `high`) audits session S3 of change `add-export`; the
  executor claimed tests passed, but they never ran in the right package; the planner recorded
  incident 118 and had the work fixed.
- **When**: the planner runs `chanchi lesson similar "test output evidence package skipped"`, sees
  nothing close, and runs `chanchi lesson add --as planner --author claude:opus:high
  --conversation <conversation id> --json -` with the general rule "test output counts as evidence only
  if it names what ran and what was skipped", generality `agnostic`, severity `high`, target kind
  `role`, target `role executor`, change `add-export`, session `S3`, incident `118`.
- **Then**: lesson #42 exists as `pending`, with `author_model_raw = opus`, `author_model_id` set
  (the catalog has `claude:opus`), `git_head` captured, one `created` event, and links to the
  session and the incident. The command prints the id.
- **Note**: the conversation id is the harness's own id when the agent can see it; otherwise the
  planner picks a label once (for example `2026-11-19 add-export audit`) and reuses it for every
  command in that conversation.

### CUJ 2: A maintenance conversation reviews and applies (stage 1)

- **Given**: lesson #42 is `pending`; a new conversation in project A, as `planner`.
- **When**: it runs `chanchi lesson export --generality agnostic`, reads #42, its incident and its
  session, runs `chanchi lesson review 42 --as planner --author claude:opus:high --conversation
  <new id> --decision approve --reason "..."`, edits `.agents/roles/executor.md` adding the rule
  tagged `[lesson #42]`, commits, and runs `chanchi lesson apply 42 --as planner --author
  claude:opus:high --conversation <new id> --site project --where
  ".agents/roles/executor.md [lesson #42] @ abc123"`.
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
- **When**: an agent runs `(cd b-app && chanchi lesson add ...)`, and later, in the same folder,
  `chanchi change open fix-login` followed by `chanchi session start fix-login ...`.
- **Then**: the lesson, the change and the session all belong to project B, because `/work/b` is
  the longest registered path that contains the working directory. No `b-app` project row is
  created.

### CUJ 5: Another project adopts or declines the rule (stage 2)

- **Given**: #42 is `approved`, `agnostic`, and applied to project A's site; project B is
  registered and has no site row for #42.
- **When**: project B's maintenance conversation runs `chanchi lesson inbox`.
- **Then**: #42 is listed. The conversation either applies it to project B's executor role
  (`lesson apply 42 --site project ...`), or declines it with a reason
  (`lesson decline 42 --reason ...`) or as `--not-applicable`. Either way #42 leaves project B's
  inbox, and project A's site is unchanged.

### CUJ 6: A rule is merged and retired in one project (stage 2)

- **Given**: #42 is applied in projects A and B; #57 merges #42 with another rule and lists `42`
  in the `replaces` field of its JSON body; #57 is approved.
- **When**: #57 is applied to project A's site.
- **Then**: #42's site row for project A becomes `retired` with an event; project B's site row
  stays `applied`. Project B's inbox shows #57 marked "replaces #42, which you applied". Later,
  `lesson verify` in project A reports `[lesson #42]` still in a file if nobody removed it.

### CUJ 7: A global lesson from outside any project (stage 1)

- **Given**: the owner edits a global skill from `~`, which is not inside any project.
- **When**: the owner (`--author human`) or a conversation declaring a global writer role runs
  `chanchi lesson add --global ...`, with generality `agnostic`, target kind `skill` and target
  `skill ~/.agents/skills/chanchi-session-audit`.
- **Then**: the lesson has no origin project and is reviewed under the global writer roles. A
  global lesson with generality `project` or `particular` is refused: it has no project to belong
  to.

## Technical Plan (Architecture)

### Vocabulary and states

**How chanchi works today.** A **change** is one unit of planned work in a project (for example
`add-export`), opened with `chanchi change open`. Each executor turn inside it is a **session**
(`S1`, `S2`, ...); a session that is redone gets a new **attempt** under the same ref. An
**incident** is an audited fact about one session or change, used for model ratings. A project row
is created by `change open` the first time a slug is seen; the slug is the folder name of the git
repository (`projects.detect()`). The other audit commands look the project up by that slug
(`projects.identify()` and `projects.resolve_project()`), and `projects.ensure()` creates the row.

| Term | Meaning |
|---|---|
| **harness** (stored as `agent`) | The program that runs a model: `claude`, `agy`, `opencode`, or `human` for a person. The fixed list is `taxonomy.ALL_AGENTS`. Elsewhere in this document "agent" means an AI working in a harness; the stored column always means the harness |
| **role** | A named job with its own instructions, such as `planner` (plans and audits the work), `executor` (does one session's work) or `auditor`. Role names belong to each project and are stored as text |
| **wrapper** | A small harness-specific file that starts a role in one harness and points to the role's shared definition |
| **writer role** | A role allowed to record, review and apply lessons in a scope. Set per project and globally (`planner` by default) |
| **reporter role** | Any role that is not a writer role. It mentions failures in its report and never records lessons |
| **conversation** | One working conversation in one harness, from start to end. Harnesses call it a session; this document never does, because "session" is chanchi's executor turn |
| **conversation id** | The id a harness gives a conversation (Claude Code `session_id`, agy `conversationId`, opencode `sessionID`), or a label the writer picks once when it cannot see the id |
| **lesson** | One improvement record: a general rule plus the case that showed it |
| **scope** | Where a lesson or setting belongs: one registered project, or global (the user's home setup) |
| **site** | One place where a lesson is applied or declined: global, or one project |
| **maintenance conversation** | A conversation, different from the one that recorded a lesson, that reviews and applies lessons |
| **inbox** | The approved agnostic lessons that one project has not decided on yet (stage 2) |

**Generality** says how far the **rule** holds, not where the fix goes. It is decided by the rule:
a rule that holds anywhere is `agnostic` even if the fix touches one file.

| Generality | Meaning | Allowed origin | Can be applied at | Reaches other projects' inbox (stage 2) |
|---|---|---|---|---|
| `agnostic` | holds in any project and any harness | a project or global | any site | yes, once applied at one project site |
| `project` | holds in all of one project | a project | its origin project's site only | no |
| `particular` | holds for one case; only `high` or `critical`, with a justification | a project | its origin project's site only | no |

**Target** says where the author thinks the fix goes: `target_kind` plus `target`, free text
naming one place, written as `<kind> <name or path>` by convention (for example `role executor`,
`wrapper claude/executor`, `skill ~/.agents/skills/chanchi-session-audit`). It is not parsed:
duplicate detection does not read it, and `verify` uses the recorded `where_`, not the target.

**Severity** is the risk if the failure happens again, not this time's damage:

| Severity | If it happens again |
|---|---|
| `low` | a little time is lost |
| `medium` | work must be redone, or a wrong result appears that is noticed soon |
| `high` | a wrong result appears that may go unnoticed, or a control fails to block what it should |
| `critical` | data is lost, production is touched, or a secret is exposed |

Lesson severity uses `critical`; incident severity uses `blocking` (`taxonomy.py:22`). They
measure different things, and `lesson add` rejects `blocking` with a hint.

**Lesson decision (`lessons.status`).** This table is complete: any other transition fails with
`invalid_transition`.

| From | Command | To | Precondition |
|---|---|---|---|
| (new) | `lesson add` | `pending` | no blocking duplicate, or `--force-new` |
| `pending`, `postponed` | `lesson review --decision approve` | `approved` | review conversation differs from `author_conversation`; `--reason` required |
| `pending`, `postponed` | `lesson review --decision reject` | `rejected` | same; `--reason` required |
| `pending` | `lesson review --decision postpone` | `postponed` | same; `--reason` required |
| `pending`, `postponed` | `lesson review --decision duplicate --of N` | `duplicate` | N exists, is not this lesson, and is not `duplicate`; occurrences move to N |
| `rejected`, `postponed`, `duplicate` | `lesson reopen` | `pending` | `--reason` required |
| `pending`, `postponed` | `lesson modify` | same | only from the author conversation |
| any except `duplicate` | `lesson repeat` | same | adds 1 occurrence and evidence; on `rejected` it also returns a `rejected_recurs` warning |

`approved` has no way back to `pending`. To withdraw an approved lesson, retire it at every site:
it then leaves every inbox, and duplicate detection only warns about it.

Reason codes for a review: `model_weakness` (one model failed; record an incident on the linked
session instead; allowed only when the lesson links a session), `covered` (an existing rule already
covers it; adjust that rule instead), `too_costly` (rare and cheap; not worth the context),
`symptom_only` (the cause is not identified).

**Site (`lesson_sites.state`).**

| From | Command | To | Precondition |
|---|---|---|---|
| (no row) | `lesson apply` | `applied` | lesson is `approved`; the site is allowed by its generality |
| `applied` | `lesson apply` | `applied` | updates `where_` |
| `retired` | `lesson apply` | `applied` | the rule is put back at that site |
| `applied` | `lesson retire` | `retired` | `--reason` required |
| `applied` | applying a lesson that `replaces` this one, at the same site (stage 2) | `retired` | automatic |
| (no row) | `lesson decline --reason` / `--not-applicable` (stage 2) | `declined` / `not_applicable` | lesson is `approved` and `agnostic` |
| `declined`, `not_applicable` | `lesson reopen-site` (stage 2) | (row removed; back in the inbox) | `--reason` required |

`lesson apply` on a `declined` or `not_applicable` row fails with `invalid_transition` and the
hint `chanchi lesson reopen-site`. A lesson is "applied" when it has at least one `applied` site.

### Overview of the pieces

```text
                    ┌───────────────────────────────────────────────┐
 agent / person ──▶ │ cli.py: project …, lesson …, audit commands   │
                    └─────┬────────────────┬────────────────┬───────┘
                          │                │                │
                 ┌────────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
                 │ projects.py   │ │ lessons.py   │ │ dedup.py     │
                 │ register,     │ │ record,      │ │ tokens,      │
                 │ locate,       │ │ review,      │ │ coverage,    │
                 │ identify,     │ │ apply, sites,│ │ thresholds   │
                 │ writer roles, │ │ inbox,       │ │              │
                 │ git helpers   │ │ verify       │ │              │
                 └────────┬──────┘ └───────┬──────┘ └───────┬──────┘
                          │                │                │
                 ┌────────▼────────────────▼────────────────▼──────┐
                 │ SQLite (one file per machine), migration 004    │
                 │ projects (+registered_at), project_locators,    │
                 │ writer_roles, lessons, lesson_sites,            │
                 │ lesson_replaces, lesson_incidents,              │
                 │ lesson_events                                   │
                 │ existing: models, changes, sessions, incidents  │
                 └─────────────────────────────────────────────────┘

 taxonomy.py: the new enum sets.  errors.py: the new error codes.
 skills/chanchi-lessons/SKILL.md: linked by `chanchi skills link` into projects and home.
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
  kind        TEXT NOT NULL,            -- 'path' in stages 1-4 (validated in taxonomy)
  value       TEXT NOT NULL,            -- canonical absolute path (symlinks resolved)
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
  id               INTEGER PRIMARY KEY,
  lesson_id        INTEGER NOT NULL REFERENCES lessons(id),
  site             TEXT,                                   -- 'global' | 'project' | NULL
  site_project_id  INTEGER REFERENCES projects(id),       -- set when site = 'project'
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

**Events name the place, not the site row.** An event records `site` and `site_project_id`
instead of a foreign key to `lesson_sites`, because `reopen-site` (stage 2) deletes a site row
and `PRAGMA foreign_keys = ON` (`db.py:70`) would refuse that delete while an event still pointed
at it. The history of a place stays complete after its row is removed.

**Current state and history.** The review columns on `lessons` (`reviewed_at`,
`reviewed_by_role`, `review_conversation`, `decision_reason`, `reason_code`, `duplicate_of`) hold
the current decision; `lesson reopen` clears them. `lesson_events` is the history and is never
updated or deleted.

**What `CHECK` holds, and what it does not.** `CHECK` holds structural invariants that this design
does not expect to change: required text is not empty, the particular rule, the duplicate link, a
reviewed status has `reviewed_at`, a site's scope and `where_`. Enum sets (`target_kind`,
`generality`, `severity`, `status`, `reason_code`, site `state`, locator `kind`), the writer-role
policy, the harness list and the duplicate thresholds are validated in `taxonomy.py` and
`lessons.py`, following `003_model_capabilities.sql`, so they can change without rebuilding a
table.

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
| `LOCATOR_KINDS` | `path` (a `remote` kind can be added later with no migration) |
| `DEFAULT_WRITER_ROLES` | `("planner",)` |

### 2. Project registration and resolution (`projects.py`)

**One resolver for every command.** The registered-path lookup lives in one place,
`projects.identify()`, which the audit commands, the lesson commands and the project commands all
use. `projects.ensure()` does not change.

Resolution order:

1. `--global`, where the command allows it → the global scope. `--global` together with
   `--project` fails with `invalid_value`.
2. `--project <slug>` → that slug. An explicit slug always wins over the working directory.
3. The registered project whose `path` locator is the longest prefix of the canonical working
   directory (symlinks resolved on both sides; the prefix must end on a whole path segment).
4. Audit commands only: today's folder slug from `detect()`, so unregistered projects work as
   before.
5. Lesson and project commands: otherwise `project_not_registered`, with the hint
   `chanchi project register` (or `--global`).

Functions, all in `projects.py` (the only module allowed to import `subprocess`, enforced by
`tests/test_no_network.py`):

- `_git(cwd, *args) -> str | None`: runs one git command and returns its stripped stdout, or
  `None` when git is missing or the command fails. `detect()` is rewritten on top of it with the
  same behavior.
- `main_worktree(cwd) -> Path | None`: the canonical parent of
  `git rev-parse --path-format=absolute --git-common-dir` when it ends in `/.git`; otherwise the
  canonical `--show-toplevel`; `None` outside a repository. This extracts the logic `detect()`
  already has (`projects.py:34-47`).
- `git_head(cwd) -> str | None`: `git rev-parse HEAD`, or `None`.
- `locate(conn, cwd) -> sqlite3.Row | None`: step 3. One query reads every `path` locator of a
  registered project; the longest match is chosen in Python. No git call.
- `identify(slug=None, cwd=None, *, conn=None) -> tuple[str, str | None]`: step 2, then step 3
  when `conn` is given, then step 4. A registered match returns that project's slug and path.
  With an explicit slug and `conn`, the path is that project's `projects.path` when `locate()`
  finds that same project for the working directory, and `None` when it finds another one. When
  `locate()` finds nothing, today's rule applies: the path is kept only when the folder slug
  equals the explicit slug (`projects.py:58-62`), so unregistered projects work as before.
- `resolve_project(conn, slug=None, cwd=None)`: unchanged contract; it now calls
  `identify(slug, cwd, conn=conn)`. Its hint for an unknown slug mentions
  `chanchi project register`.
- `resolve_scope(conn, *, project=None, global_=False, cwd=None) -> Scope`: steps 1, 2, 3 and 5
  for lesson and project commands. `Scope` holds `project_id` (`None` for global) and `slug`. An
  explicit `--project` must name a registered project.
- `register(conn, cwd, name=None) -> dict`: in one transaction:
  1. `main = main_worktree(cwd)`; outside a repository it fails with the existing
     `project_not_detected`.
  2. If `main` is already a `path` locator, it returns that project with
     `"already_registered": true` and changes nothing.
  3. `slug = name or main.name`. If a row with that slug is registered, it fails with
     `invalid_value` naming the row's path, hint `--name <other slug>`. If the row exists and is
     not registered, it is adopted (`"adopted": true`). Otherwise a row is created.
  4. It sets `registered_at`, sets `projects.path` to `main`, and inserts the `path` locator.
  With `--name`, an unregistered row under the folder name is not adopted, and its audit history
  stays under that slug. The README says so.
- `relink(conn, slug, cwd)`: adds the canonical `--show-toplevel` of the working directory as a
  `path` locator of a registered project. It covers a moved folder and a linked worktree outside
  the main path. A locator owned by another project fails with `invalid_value` naming it; one the
  project already owns is a no-op.
- `list_projects(conn)` and `show(conn, slug)`: slug, path, `registered_at`, locators, writer
  roles (with `"default": true` when none are stored) and lesson counts by status.
- `writer_roles(conn, project_id | None) -> tuple[str, ...]`: the scope's rows, or
  `DEFAULT_WRITER_ROLES` when it has none.
- `set_writer_roles(conn, project_id | None, roles)`: replaces the scope's rows in one
  transaction, with no actor check of its own. Changing them is a guarded write done through
  `lessons.set_writers`, which checks that the caller declares a current writer role of that
  scope or is `human` (`projects.py` cannot import `lessons`).

`cli.cmd_change_open` opens the connection first and calls `identify(args.project, conn=conn)`,
so a change opened inside a registered project gets the registered slug, and `ensure()` finds its
row. Every other audit command already goes through `resolve_project()`. A project whose folder
was moved is found again after `chanchi project relink <slug>` from the new folder.

### 3. Lessons (`lessons.py`)

**Actor.** Every write command takes three identity flags, all required, kept out of the JSON body
so a stage-3 hook can read them from the command line:

- `--as <role>`: the role the caller declares.
- `--author <agent:model[:effort]>`: the harness, model and effort of whoever runs this command.
  On `add` it fills the `author_*` columns; on every other write it fills the event's
  `actor_agent`. `modelspec.parse` validates the agent against `taxonomy.ALL_AGENTS` and
  recognizes the last segment as an effort only when it is in `taxonomy.EFFORTS`; otherwise that
  segment stays in the model name. Model names may contain `:` (opencode models such as
  `openrouter/qwen/qwen3-coder:free`, seeded at `tests/conftest.py:53`), so a colon alone is not
  an error. `make_actor` first looks up `(agent, model)` with `catalog._model_row(conn, agent,
  model)`; an exact match is accepted and sets `author_model_id`. Only when there is no match, the
  model name contains `:`, and its last `:` segment is within edit distance 2 of a value of
  `taxonomy.EFFORTS` (for example `claude:opus:hgh`), it is refused as a mistyped effort with
  `invalid_value`, `field` = `author`, `valid_values` = `EFFORTS`. Its hint says that a real model
  name with that suffix (for example `:pro`, distance 2 from `low`) is accepted once it is in the
  catalog with `chanchi models add`. The model name is otherwise free text, and a miss leaves
  `author_model_id` NULL and is not an error. Nothing is ever inserted into `models`. A
  missing effort is stored as NULL. `--author human` parses to `human:human`, which migration 001
  seeds in the catalog.
- `--conversation <id | label>`: the conversation id, or a label chosen once and reused (CUJ 1).

`check_writer(conn, scope_project_id, actor)` passes when `actor.agent == "human"`, or when
`actor.role` is in `writer_roles(scope_project_id)`. Otherwise it fails with `not_a_writer`, naming
the role seen, the scope's roles and the `chanchi project writers` command. When the agent is
`human`, `--as` is still required and recorded, but not checked.

**Actor and threat model.** In stages 1 and 2, `--as`, `--conversation` and `--author human` are
declarations the caller makes; the CLI cannot see the harness. The guard stops a cooperative agent
that declares its real role, which is the case the skill and the role files set up. It does not
stop an agent that declares a writer role it does not have, invents a second conversation label to
review its own lesson, or passes `--author human`. The skill tells agents never to pass
`--author human`. Stage 3 closes these gaps for Claude Code with the actor the harness reports
(Q1); for agy the role comes from the launcher, because no agy hook input names it (Q2).

**Scope of each check.** Lesson-level commands are checked against the lesson's origin scope.
Site-level commands are checked against the site's scope. This differs from brief §2, where
agnostic lessons were reviewed under the global list: a project that renames its writer role would
otherwise lose the right to review its own agnostic lessons.

| Command | Scope checked |
|---|---|
| `add`, `repeat`, `modify`, `review`, `reopen` | the lesson's origin (its project, or global) |
| `apply`, `retire`, `decline`, `reopen-site` with `--site project` | the resolved project |
| the same with `--site global` | global |
| `project writers --set` | the scope being changed |

**Scope flags.** `--global` and `--project` choose a scope only where one is needed:

- `lesson add`: `--global` records a global-origin lesson; otherwise the origin is the resolved
  project (`resolve_scope`).
- `lesson repeat`, `modify`, `review`, `reopen`: no scope flag. The scope is the lesson's origin,
  read from the row, so these work from any directory, registered or not.
- `lesson apply`, `retire` (and `decline`, `reopen-site` in stage 2): `--site global` needs no
  project. `--site project` resolves the project from `--project` or the working directory with
  `resolve_scope`.
- `project writers`: `--global`, a slug, or the resolved project.
- Read commands: `--project`, `--global` or `--all`, as described below.

**The `add` JSON body.** The body must be a JSON object. Unknown keys fail with `invalid_value`
listing the valid keys. The type of every key is checked first, before any other rule: a value of
the wrong JSON type (for example a number for `cause`, or a string for `incidents`) fails with
`invalid_value`, `field` = the key. Only then is text validated with `record._required_text`,
which expects a string. Tags are normalized with
`record._csv(",".join(v) if isinstance(v, list) else v) or ""`, because `_csv` takes a string and
returns `None` for an empty list.

| Key | Type | Rule |
|---|---|---|
| `what_happened`, `evidence`, `cause`, `prevention`, `proposal`, `general_rule`, `target` | string | required, not blank (`record._required_text`) |
| `generality`, `severity`, `target_kind` | string | required; in the `taxonomy` sets; `severity = blocking` is refused with a hint to use `critical` |
| `particular_justification` | string | required when `generality = particular` |
| `tags` | list of strings, or one comma-separated string | normalized with `record._csv`; stored as `''` when empty |
| `change` | string | a change ref in the origin project |
| `session` | string | a session ref in `change` (latest attempt); requires `change` |
| `incidents` | list of integers | each must belong to `change`; requires `change` |
| `replaces` | list of integers | each an existing lesson other than this one; stored in `lesson_replaces`; acted on by `apply` in stage 2 |

A lesson recorded with `--global` must be `agnostic` and may not carry `change`, `session` or
`incidents`, which belong to a project.

**Commands and their rules.** Every write runs in one `db.transaction` (`BEGIN IMMEDIATE`) and
writes exactly one `lesson_events` row, except the stage-2 retire-on-apply, which adds one row per
retired site.

- `add --json - | --json <file> [--force-new]`: validates the body, captures `git_head` with
  `projects.git_head(cwd)`, and runs the duplicate check (§4) inside the same transaction. A block
  fails with `duplicate_lesson`. `--force-new` records the lesson anyway. Warnings are returned
  under `warnings`.
- `repeat <id> --evidence ... [--incident N]`: adds 1 to `occurrences` and puts the evidence in the
  event note. `--incident N` must belong to the lesson's change; a lesson with no change cannot
  link one. Refused on `duplicate`, with the hint naming `duplicate_of`. On `rejected` it returns
  the warning `rejected_recurs` with the stored `reason_code` and `decision_reason`.
- `modify <id> --json -`: takes a full body with the same rules as `add` and replaces the text
  fields, the enums (`generality`, `severity`, `target_kind`, `particular_justification`) and
  `tags`. It replaces the `incidents` and `replaces` links (delete the lesson's rows, then insert
  the new ones). It keeps `change`, `session` and `git_head`; a body whose `change` or `session`
  differs from the stored one fails with `invalid_value`. It runs the duplicate check again
  without comparing the lesson with itself. Only `pending` or `postponed`, and only when
  `--conversation` equals `author_conversation`.
- `review <id> --decision ... --reason ... [--reason-code ...] [--of N]`: per the decision table.
  `--reason` is required for every decision. `--reason-code` is optional with `reject` and
  refused with any other decision. `--of N` is required with
  `duplicate` and refused otherwise. Refused with `self_review` when `--conversation` equals
  `author_conversation`. `--reason-code model_weakness` requires a linked session.
  `duplicate --of N` adds this lesson's occurrences to N and writes the event note
  `moved=<n> to=#<N>`; no column stores the count. Lessons that were already `duplicate_of` this
  one are re-pointed to N in the same transaction; their own notes are not changed.
- `reopen <id> --reason`: per the decision table. From `duplicate`, it reads `<n>` from the
  latest `reviewed` event of this lesson whose note starts with `moved=`, and subtracts it from
  the lesson its `duplicate_of` now names, but never below 1. It clears `reviewed_at`,
  `reviewed_by_role`, `review_conversation`, `decision_reason`, `reason_code` and `duplicate_of`.
- `apply <id> --site global|project --where "<path> [lesson #<id>] @ <commit>"`: per the site
  table. The commit part is optional. `where_` must contain `[lesson #<id>]`. A `project` or
  `particular` lesson can only be applied with `--site project` in its origin project; anything
  else fails with `invalid_value`.
- `retire <id> --site global|project --reason`: `applied` to `retired` at that place only.
- `similar`, `list`, `show`, `summary`, `export`: read-only, described below.

**Events.** `from_state` and `to_state` hold the lesson status for lesson-level actions and the
site state for site-level actions (NULL when there was no row).

| Command | `action` | From → to | `site`, `site_project_id` |
|---|---|---|---|
| `add` | `created`, or `force_new` with `--force-new` | NULL → `pending` | NULL |
| `repeat` | `repeated` | status → same | NULL |
| `modify` | `modified` | status → same | NULL |
| `review` | `reviewed` | status → new status | NULL |
| `reopen` | `reopened` | status → `pending` | NULL |
| `apply` | `applied` | site state → `applied` | set |
| `retire` | `retired` | `applied` → `retired` | set |
| retire on apply (stage 2) | `retired` (note "replaced by #M") | `applied` → `retired` | set |
| `decline` (stage 2) | `declined` | NULL → `declined` or `not_applicable` | set |
| `reopen-site` (stage 2) | `site_reopened` | `declined` or `not_applicable` → NULL | set |

A `force_new` event's note records the matched lesson id, its coverage and the shared token count,
so overrides can be used later to retune the thresholds.

**Results.** Every command prints one JSON object. A **lesson dict** is every column of the
`lessons` row, with `tags` as a list of strings and an added `origin` (the slug, or `global`). A
**site dict** is `{site, project (slug or null), state, where_, reason, decided_conversation,
decided_at}`. `"scope"`
is always the slug, `global`, or `all`.

| Command | Result |
|---|---|
| `lesson add`, `modify` | `{"lesson": <lesson>, "warnings": [{id, kind, general_rule, shared}]}` |
| `lesson repeat` | `{"lesson": <lesson>, "warnings": [...]}`; on `rejected` one warning `{"kind": "rejected_recurs", "id", "reason_code", "decision_reason"}` |
| `lesson review` | `{"lesson": <lesson>, "repointed": [<ids>]}` (`repointed` is empty except for `duplicate`) |
| `lesson reopen` | `{"lesson": <lesson>}` |
| `lesson apply`, `retire` | `{"lesson": <lesson>, "site": <site>}`; in stage 2 `apply` adds `"retired": [{"id", "site"}]` |
| `lesson list` | `{"scope", "lessons": [<row of the list command>]}` |
| `lesson show` | `{"lesson", "sites", "replaces": [<ids>], "incidents": [<record.incident_dict>], "events": [<event row>]}` |
| `lesson similar` | `{"scope": "all", "matches": [{id, status, generality, origin, general_rule, coverage, shared}]}` |
| `lesson summary` | `{"scope", "by_status": {}, "by_generality": {}, "applied_sites": {"global": n, "<slug>": n}, "force_new_rate": <float or null>}`; stage 2 adds `"inbox"` |
| `lesson export` | `{"scope", "lessons": [<lesson>], "markdown": <string, only with --format md>}` |
| `project register` | `{"project": <project>, "already_registered": bool, "adopted": bool}` |
| `project relink` | `{"project": <project>, "locator": <path>, "added": bool}` |
| `project list` | `{"projects": [<project>]}` |
| `project show` | `<project>`: `{id, slug, path, registered_at, locators: [<path>], writers: {roles, default}, lessons: {<status>: n}}` |
| `project writers` | `{"scope", "roles": [...], "default": bool}` |

`force_new_rate` is null when there are no `created` or `force_new` events. `incidents` use
`record.incident_dict`, so they carry the session ref and the model as `chanchi show` does. An
incident with `voided_at` set (voided) cannot be linked by `add`, `modify` or `repeat`
(`invalid_value`, `field` = `incidents`).

**Read commands.** They need no writer role and no registered project. They take `--project`,
`--global` or `--all` to choose the lessons by origin. With no flag, they use the resolved project
when one resolves, and every lesson otherwise. The response names the scope it used (`"scope"`).

- `list [--status ...] [--generality ...] [--target-kind ...] [--limit 50]`: one row per lesson
  with `id`, `status`, `generality`, `severity`, `occurrences`, `target_kind`, `target`,
  `general_rule`, `origin` (slug or `global`) and a count of sites by state.
- `show <id>`: any lesson, whatever the scope. It returns the lesson, its sites, the lessons it
  replaces, its incidents (with their session and model), and every event.
- `similar "<text>" [--limit 5]`: compares the text with every lesson, whatever the scope (§4). Each
  match has `id`, `status`, `generality`, `origin`, `general_rule`, `coverage` and `shared`.
- `summary`: counts by status and generality, counts of `applied` sites per place, the `force_new`
  rate (`force_new` events over all `created` and `force_new` events), and in stage 2 the inbox
  size when a project resolves.
- `export [--status pending,postponed] [--generality ...] [--target-kind ...] [--since <date>]
  [--limit 20]`: orders by generality (`agnostic`, `project`, `particular`), then severity
  (`critical` first), then `occurrences` descending, then `id`. `--since` filters on
  `created_at`. It honors the shared `--format`. `md` is a new value of `cli.FORMATS`: for it,
  `_emit` writes `payload["markdown"]` when present and falls back to the text renderer otherwise.
  Only `export` fills `markdown`, built by `lessons.export_markdown(rows)`. The layout has one
  `## #<id> · <generality> · <severity> · ×<occurrences>` heading per lesson, then one
  `- **<field>:** <value>` line per content field, then its sites and incidents.

### 4. Duplicate detection (`dedup.py`)

- `tokens(text) -> set[str]`: lowercase; split on any character that is not a letter or a digit;
  keep tokens with 4 or more characters that are not in `data/stopwords_en.txt`.
- `coverage(a, b) = |a ∩ b| / min(|a|, |b|)` (0 when either is empty).
- A **candidate** is a plain dict `{"id": int, "full": str, "rule": str}`, where `full` is
  `what_happened + " " + general_rule + " " + proposal` and `rule` is `general_rule`. The new
  lesson is passed in the same shape (with `id` = `None`).
- `similar(text, candidates, limit=5)`: compares `tokens(text)` with each candidate's `full`
  tokens and with its `rule` tokens, and keeps the higher of the two coverages (with that test's
  shared count). Candidates sharing at least 2 tokens are returned as
  `{"id", "coverage", "shared"}`, ordered by coverage, then shared count, then id.
- `matches(new, candidate)`: true when either test passes:
  - full text (`what_happened` + `general_rule` + `proposal`): at least 4 shared tokens and
    coverage of at least 0.30;
  - general rule alone: at least 3 shared tokens and coverage of at least 0.50.
- `blocking_match(new, candidates)`: of the matching candidates, the one with the highest coverage
  (ties: lowest id).

`lessons.py` sorts each existing lesson into one class before calling `dedup`. Here, "in scope"
means the lesson has the same origin as the new lesson, or is `agnostic`.

| Class | Condition (the first that holds) | Effect |
|---|---|---|
| retired | `approved`, with at least one site row and every site row `retired` | warning `retired` |
| blocking | in scope, and `pending`, `postponed` or `approved` | blocks |
| warning | in scope, and `rejected` or `duplicate` | warning `rejected` or `duplicate` |
| warning | a `project` lesson of another project | warning `possibly_agnostic` |
| ignored | anything else | none |

An approved lesson with no site rows is still blocking. A block fails with `duplicate_lesson`. Its
`details` holds the matched `id`, `status`, `general_rule`, the shared tokens and the test that
matched. Its hint is `chanchi lesson repeat <id> --evidence ...` or `--force-new`. Warnings, at
most 5, are returned on success as `warnings: [{id, kind, general_rule, shared}]`.

The four thresholds (`FULL_MIN_SHARED = 4`, `FULL_MIN_COVERAGE = 0.30`, `RULE_MIN_SHARED = 3`,
`RULE_MIN_COVERAGE = 0.50`) each live in one constant in `dedup.py`, next to `MIN_TOKEN_LEN = 4`
and `SIMILAR_MIN_SHARED = 2`. They were tuned on short Spanish texts and are starting values for
English text. Retune them when a fixture test fails, or when `lesson summary` shows a `force_new`
rate above 20% once there are at least 20 lessons; the `force_new` event notes list the matches
that were overridden.

### 5. Inbox, replaces and verify (stage 2, no migration)

**Inbox** for resolved project P (`lesson inbox [--all] [--target-kind ...] [--since <date>]
[--limit 20]`):

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
ORDER BY CASE l.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                         WHEN 'medium' THEN 2 ELSE 3 END,
         l.occurrences DESC, l.id
LIMIT :limit;
```

`--target-kind` and `--since` (on `reviewed_at`) add filters. A lesson applied globally does not
reach any inbox, because the global setup is loaded in every project. Each item carries
`replaces_applied_here`: the ids it replaces that P has `applied`, so P sees "replaces #42, which
you applied". To withdraw an approved lesson, retire it at every site; it then leaves every inbox.

`decline <id> --reason ... | --not-applicable` inserts P's site row as `declined` or
`not_applicable`. `reopen-site <id> --reason` deletes that row; the event keeps the place, and the
lesson returns to the inbox.

**Replaces on apply.** When lesson M is applied at a place, every lesson in M's `replaces` that has
an `applied` row at the same place becomes `retired` there, with the note "replaced by #M". Rows at
other places do not change.

**Verify** (`lesson verify [--global] [--scan <path>]...`) reads files only. Without `--global` it
checks the site rows of the resolved project P; with `--global` it checks global site rows and
works outside any project.

1. For each site row in scope, the path is the part of `where_` before ` [lesson #`. An absolute
   path is used as is; a path starting with `~` is expanded; a relative path is resolved against
   `projects.path` of P for project rows and against `~` for global rows.
2. Findings:
   - `missing_file` when the path does not exist;
   - `missing_tag` for an `applied` row whose file lacks `[lesson #N]`;
   - `stale_tag` for a `retired` row whose file still has it;
   - `unchecked` instead of `missing_tag` when the lesson's `target_kind` is `hook` or
     `permission`, because those targets are JSON files that cannot hold a comment.
3. Every distinct path from step 1, plus each `--scan <path>`, is scanned for `[lesson #(\d+)]`.
   An id with no lesson, or with no site row in scope, is reported as `unknown_tag`.
   `--scan <path>` is resolved against the working directory when relative. A file is read
   whole; a directory is walked recursively, skipping `.git` and files over 1 MB. Bytes that are
   not UTF-8 are read with `errors="replace"`, so a binary file never fails the command.
4. Output: `{"scope": ..., "findings": [{"kind", "lesson", "site", "path", "line"}], "files":
   [{"path", "lines", "tags"}]}`. `line` is set for tag findings.

### 6. The skill (`skills/chanchi-lessons/SKILL.md`)

In English, at most 150 lines (checked by `tests/test_skills_content.py`), in three parts:

- **Record** (writer roles, at the end of a conversation or when something fails): the five
  principles and the five triggers from the Overview; fix first; for each failure write the cause
  and the general rule ("if you cannot write the cause, you have the symptom; if you cannot write
  the rule, you do not understand the failure yet"); run `lesson similar` and read the pending
  general rules; then `repeat` or `add`; a field guide with the severity table and the generality
  table; one full `lesson add` example; "never pass `--author human`"; "do not review or apply
  your own lesson; say what you recorded and its id".
- **Review** (maintenance conversations): `summary`; `export`; for each lesson: cause or symptom,
  an existing rule that covers it, whether the rule holds outside the case, its cost in context,
  the cheapest place (hook, permission or CLI check before a role line), what it replaces; decide
  with a reason and a reason code; apply, tag the file with `[lesson #N]`, record `--where`.
  Stage 2 adds `inbox` and `verify`. The stage-1 skill does not mention them, because
  `test_skills_content.py` checks that every quoted command exists.
- **Lines to paste**, written verbatim in the skill:
  - the writer-role block, for the planner's role file: "You are a writer role for chanchi
    lessons. At the end of each conversation, or when something went wrong, follow the
    `chanchi-lessons` skill: fix first, then record the cause and a general rule. Never review or
    apply a lesson you recorded.";
  - the reporter line, for every other role: "If something went wrong, say so in your report; do
    not record it in chanchi.";
  - the project-rules line, which is `skills_link.SUGGESTED_CONFIG_LINE`, extended to name
    `chanchi-lessons`. `chanchi skills link` already prints it, so the skill points to that output
    instead of keeping a second copy.

### 7. Stages 3 and 4: invariants and dependencies

Only the parts that stages 1 and 2 must not contradict are fixed here. Brief §10 holds the draft
contract (normalized input fields, command matching, the guarded-verb list, the session-start
line, the fixture-test matrix). It is revised into a file-level plan once Q6 is answered.

- **Migration `005_runs.sql`**: a `runs` table, one row per harness conversation
  (`UNIQUE(agent, conversation_id)`), with its project, role and where the role came from, its
  model, effort and linked session, and the retrospective timestamps.
- **`chanchi hook check`** always exits 0. Any error, lock, missing git, unregistered project or
  schema mismatch means "allow" plus a logged warning. It opens the database without `bootstrap()`
  and never migrates. chanchi's normal exit code 2 on errors (`EXIT_VALIDATION`) must never reach a
  harness, because Claude Code reads exit 2 from a hook as "block".
- **Actor**: from the event (`agent_type` in Claude Code, `agent` in opencode), then
  `CHANCHI_ROLE` set by the launcher, the script that starts a role in its own terminal pane (the
  only source for agy), then `unknown`. An unknown actor is
  not a writer. `pre-tool` blocks a guarded lesson command when the actor is not a writer or
  differs from `--as`.
- **Adapters** translate each harness's input and output (Q1 to Q4). Unless Q6 shows that Claude
  Code can filter hooks by command text, the Claude Code adapter is a small shell script that exits
  at once when the command does not contain `chanchi`, so ordinary Bash calls never start Python.
- **Stop**: writer roles in registered projects only; at most once per conversation; respects
  `stop_hook_active` (Claude Code) and `continuationActive` (agy); never ends the conversation.
- **Install** writes only chanchi's own entries, after a backup, and `uninstall` removes only
  those.
- **Order**: stage 3 is Claude Code (Q1, Q6). Stage 4 is agy (Q2, Q3, Q5), then opencode (Q4).

### Rollout and rollback

- Migration 004 only adds a column and tables. Existing audit commands behave the same on
  unregistered projects. Inside a registered project they use the registered project's slug, which
  equals today's folder slug unless `--name` was given at registration.
- The operational database migrates itself on the next command, after its usual
  `chanchi.db.bak-v3` backup.
- Rollback is forward-only, as today: an older chanchi on a version-4 database fails with
  `schema_too_new` on every command. Rolling back means restoring `chanchi.db.bak-v3` and losing
  the lessons and registrations recorded since. The README states this.
- No hook is installed in stages 1 and 2, so nothing runs inside the harnesses until stage 3.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Rolling back to a commit before 004 makes every command fail with `schema_too_new`, audits included | Forward-only, as today. Rollback means restoring `chanchi.db.bak-v3` and losing lessons and registrations recorded since. The README states it |
| In stages 1 and 2 the role, the conversation and `human` are only declared, so an agent can pass the guard by declaring falsely | Stated threat model ("Actor and threat model" in §3); the skill forbids `--author human`; stage 3 compares the declaration with the actor the harness reports |
| Word overlap misses the same failure told in different words | The skill tells the writer to run `lesson similar` and read the pending general rules before recording. Semantic search is a non-goal |
| Thresholds tuned on Spanish text block too much or too little on English text | Fixture tests; the `force_new` rate in `lesson summary` with a retune trigger (§4); each override's match is logged in its event |
| Lessons pile up with no review | `lesson summary` shows pending counts. In stage 3, the session-start line of a writer conversation mentions pending `high` and `critical` lessons |
| Role files keep growing | The review prefers zero-context targets (hook, permission, CLI check); `replaces` and per-site retirement; `lesson verify` reports lines and tags per file |
| A fix in a JSON target (hook, permission) cannot hold the `[lesson #N]` tag | `verify` reports it as `unchecked`, not as a missing tag |
| The method does not detect failures | It depends on someone noticing. Audit incidents and verdicts are the usual trigger, and the session-audit skill points to `chanchi-lessons` |

## Alternatives Considered

### Alternative A: Project id in a committed file in each project

- **Pros**: identity travels with the repository; no lookup by path or remote.
- **Cons**: needs a commit in every project, and in every new project; a public tool would ask
  every user to commit chanchi files.
- **Reason for Rejection**: The cost falls on every project and every user: a commit per project,
  and chanchi files in repositories that chanchi does not own. A row in the local database gives
  the same identity at no cost to the repository.

### Alternative B: Keep the current slug detection and add no registration

- **Pros**: no new tables or commands; `ensure()` already works for audits.
- **Cons**: a moved folder or a second clone splits or merges history; nested repositories
  resolve to the wrong project; there is no scope to hold writer roles.
- **Reason for Rejection**: Nested repositories are the case the owner's projects actually have,
  and the folder slug resolves them to the inner repository, which is the wrong project. Writer
  roles also need a project row that exists before any change is opened.

### Alternative C: Resolve by git remote URL, first or as a fallback

- **Pros**: survives moving the folder; recognizes a new clone with no step.
- **Cons**: inside a nested repository the remote is the inner repository's, so the lesson lands in
  the wrong project or fails; forks that share an `origin` collide; URLs need normalizing (ssh,
  https, credentials, `.git`); separate clones of one repository cannot be told apart.
- **Reason for Rejection**: It solves moved folders and new clones, which the evidence does not
  show, and brings normalization, collision rules and an opt-out flag. `project relink` handles a
  moved folder with one command. `kind` stays in `project_locators`, so a remote locator can be
  added later with no migration.

### Alternative D: Guard on "is this a subagent?" (the source method's hook)

- **Pros**: one field in Claude Code's hook input; simple.
- **Cons**: roles also run as top-level processes started with `--agent`, so an executor in its own
  pane passes.
- **Reason for Rejection**: It misses every role started as a top-level process, which is how the
  owner runs executors and auditors. Checking the actor's role covers both cases.

### Alternative E: Guard on the role of the conversation

- **Pros**: one lookup per conversation; no per-event field needed.
- **Cons**: a Claude Code subagent's events carry its parent's `session_id`, so an executor
  subagent spawned by the planner passes as the planner.
- **Reason for Rejection**: It lets an executor subagent write as its planner parent (observed in
  Q1). The per-event `agent_type` names the actual actor, so the stage-3 hook decides on that.

### Alternative F: "No role means a person, so it can write"

- **Pros**: a person typing in a plain conversation needs no setup.
- **Cons**: in a harness that hides the role, every agent has no role and passes.
- **Reason for Rejection**: agy hook input never names the role (Q2), so in agy every agent would
  pass. A person declares `--author human` instead.

### Alternative G: One status per lesson, with apply and retire fields on the lesson

- **Pros**: the source method's shape; one table; simple queries.
- **Cons**: cannot say that a rule is applied in two projects, declined in a third and retired in
  one; retiring in one place would retire it everywhere.
- **Reason for Rejection**: Cross-project use (stage 2) needs one state per place, and one column
  cannot hold that. A separate `lesson_sites` table costs one join.

### Alternative H: Push agnostic lessons to every inbox when recorded

- **Pros**: projects see new rules early.
- **Cons**: projects adopt rules nobody reviewed, against principle 4 (the author does not judge); a new project inherits the
  whole backlog; the inbox grows with projects times lessons.
- **Reason for Rejection**: Unreviewed rules would spread to every project, and the inbox would
  grow with projects times lessons. Pulling only approved, applied lessons keeps the inbox to rules
  that already worked somewhere.

### Alternative I: A stop hook that asks every conversation for a retrospective

- **Pros**: no conversation ends without the question.
- **Cons**: `Stop` and `session.idle` fire after every reply, not at the end; reporter roles get
  asked for something they may not do; it pushes empty retrospectives, against principle 2 ("record only
  what really went wrong").
- **Reason for Rejection**: Firing after every reply would nag every conversation and ask reporter
  roles to do what they must not. Stage 3 asks writer roles only, at most once per conversation.

### Alternative J: A `runs` table and hooks in stage 1

- **Pros**: conversation identity and role come from the harness from day one.
- **Cons**: it depends on harness facts (Q1 to Q6), one of which is still open; it would delay
  the core and build adapters that may only partly work.
- **Reason for Rejection**: The core is useful with declared identity and does not need to wait for
  harness work. Stage 1 takes identity as flags; runs and hooks arrive in stage 3.

### Alternative K: Free harness values validated against `models.agent`

- **Pros**: any harness a user adds would work.
- **Cons**: the code fixes the list in `taxonomy.ALL_AGENTS`, and `modelspec.parse` and
  `catalog.add_model` reject anything else; supporting it means changing the catalog.
- **Reason for Rejection**: It would change the catalog and `recommend` for a need nobody has: the
  three harnesses plus `human` cover every current user.

### Alternative L: Add unknown models reported by authors or hooks to the catalog

- **Pros**: every lesson's model links to a catalog row.
- **Cons**: the new rows would enter `recommend`'s exploration list and its Hugging Face ordering.
- **Reason for Rejection**: Unverified names from free text would change model recommendations.
  Storing the raw text and linking only on an exact match keeps `recommend` unchanged.

### Alternative M: Policy as SQLite `CHECK` constraints (the source method's approach)

- **Pros**: rules hold even if someone writes to the database another way.
- **Cons**: SQLite needs a table rebuild to change a `CHECK`; thresholds and enum sets are expected
  to change.
- **Reason for Rejection**: Policy is expected to change and a rebuild per change is costly;
  every write already goes through the CLI. `CHECK` keeps only structural invariants, as
  `003_model_capabilities.sql` already does.

### Alternative N: Two skills (record and review) and a `rules snippet` command

- **Pros**: each skill is shorter; the command prints the lines to paste.
- **Cons**: a second skill to link and keep in sync; a command that prints fixed text is code with
  no logic.
- **Reason for Rejection**: Writer roles need both parts in the same conversations, so one skill
  avoids a second link to keep in sync. The project-rules line already comes from
  `chanchi skills link`; the other two lines are fixed text in the skill.

### Alternative O: Retire rules through a `replaces` list that names file lines, not lessons

- **Pros**: could retire the 39 hand-copied rules that are not lessons.
- **Cons**: free text cannot be checked or tracked; it would need the import that is a non-goal.
- **Reason for Rejection**: A free-text line cannot be checked or retired per site. A file rule
  that is not a lesson is named in the proposal text instead.

---

## Non-Functional Requirements

- **Security and privacy**: lessons hold text that agents write, which can include paths, commit
  ids and quotes from reports. Everything stays in the local database; the `chanchi` package keeps
  importing no network module (`tests/test_no_network.py`). `lesson add` reads only its JSON body
  and runs `git rev-parse HEAD`; it never opens a target file. `lesson verify` reads only paths
  recorded in site rows or passed with `--scan`.
- **Performance**: commands with no explicit `--project` run one extra query that reads every
  `path` locator (one row per registered project) and compare them in Python. No git call is
  added: `detect()` runs only when no locator matches, as today. The duplicate check reads every
  lesson into memory and tokenizes it. Target: under 100 ms for 1,000 lessons, measured once during
  implementation (see the Verification Plan).
- **Context cost**: the skill is the only text agents load. It is at most 150 lines, checked by a
  test, and the review asks about each fix's context cost.

---

## Future Improvements

- **Context budget per target file**: refuse approving a `role` fix for a file over a set size
  unless it replaces another rule. Revisit when `lesson verify` shows a target file growing by more
  than 10% across two maintenance conversations.
- **Import of hand-copied rules**: a one-off command that turns tagged rules in files into
  applied lessons, so they can be replaced and retired.
- **Draft queue for reporter roles**: let non-writers file a draft that only writers turn into a
  lesson, if audits show reports that mention a failure with no matching lesson.
- **Remote locator**: recognize a moved folder or a new clone by its normalized `origin`, if
  `project relink` turns out to be needed often.
- **Semantic duplicate search**: if reviews keep marking `duplicate` lessons that `add` did not
  block.
- **Open harness list**: an `agents` table, if a user needs a harness beyond the four.

## Additional Resources

- [Brief, Revision 2](continuous-improvement.brief.md), with its summary of the review of
  Revision 1.
- [Review of this design](reviews/continuous-improvement/consolidated_review_report.md) and the
  [harness facts](reviews/continuous-improvement/hook-facts-2026-11-19.md).
- Source: [projects.py](../../src/chanchi/projects.py), [db.py](../../src/chanchi/db.py),
  [errors.py](../../src/chanchi/errors.py), [taxonomy.py](../../src/chanchi/taxonomy.py),
  [modelspec.py](../../src/chanchi/modelspec.py), [catalog.py](../../src/chanchi/catalog.py),
  [skills_link.py](../../src/chanchi/skills_link.py),
  [001_init.sql](../../src/chanchi/migrations/001_init.sql),
  [003_model_capabilities.sql](../../src/chanchi/migrations/003_model_capabilities.sql).
- [README](../../README.md) sections "Give the skills to a project" and "Databases and
  migrations".

---

## Detailed Implementation Plan

Stages 1 and 2 only. Stages 3 and 4 get their plan after Q6 is answered. Stage 1 and stage 2 are
separate branches and merges; stage 2 starts after stage 1 is on `main`.

Stage 1 is done in seven steps, in this order. Each step ends with `uv run pytest` passing before
the next one starts.

| Step | Files | Checkpoint |
|---|---|---|
| 1. Schema | 1, 2, 3 | `tests/test_db.py` passes with migration 004 |
| 2. Sets and errors | 4, 5, 6 | `tests/test_taxonomy.py` passes |
| 3. Projects | 7, 8 | `tests/test_projects.py` passes, including audits in a nested registered repository |
| 4. Duplicates | 9, 10, 11 | `tests/test_dedup.py` passes |
| 5. Lessons | 12, 13 | `tests/test_lessons.py` passes |
| 6. CLI | 14, 15 | `tests/test_cli.py` and `tests/test_cli_integration.py` pass |
| 7. Skill and docs | 16 to 21 | the full suite passes; the Verification Plan is run |

### Stage 1: Target Files to Create/Modify

#### 1. `src/chanchi/migrations/004_lessons.sql` (Create)

- **Type / Scope**: SQL migration.
- **Proposed Changes**: exactly the schema in Technical Plan §1: `ALTER TABLE projects ADD COLUMN
  registered_at`, tables `project_locators`, `writer_roles`, `lessons`, `lesson_sites`,
  `lesson_replaces`, `lesson_incidents`, `lesson_events` (with `site` and `site_project_id`, no
  foreign key to `lesson_sites`), and their indexes. A header comment names the migration and says
  enum sets are validated in `taxonomy.py`. No seed rows (the default writer role is applied in
  code).

#### 2. `src/chanchi/data/template.db` (Modify)

- **Type / Scope**: committed template database.
- **Proposed Changes**: regenerated with `uv run chanchi db migrate --template` and committed in the
  same commit as `004_lessons.sql`. The drift check in `tests/test_db.py:53-67` fails if they
  differ.

#### 3. `tests/test_db.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**:
  - The synthetic migration at line 240 becomes `(5, "005_add_probe.sql", ...)`, and the version
    expected at line 244 becomes 5, and the list at line 243 becomes `[2, 3, 4, 5]`. A real 004
    would otherwise be applied first and the probe skipped.
  - The assertions at lines 271-273 become `new_applied == [2, 3, 4]` and `user_version == 4`.
  - `OPERATIONAL_TABLES` (line 9) adds `project_locators`, `writer_roles`, `lessons`,
    `lesson_sites`, `lesson_replaces`, `lesson_incidents` and `lesson_events`, so the template is
    checked to ship them empty.
  - New test: a version-3 database with a `projects` row migrates to 4, and the row keeps its id
    and slug with `registered_at` NULL.

#### 4. `src/chanchi/taxonomy.py` (Modify)

- **Type / Scope**: Python module, enum sets.
- **Proposed Changes**: add `LESSON_TARGET_KINDS`, `LESSON_GENERALITIES`, `LESSON_SEVERITIES`,
  `LESSON_STATUSES`, `LESSON_DECISIONS`, `LESSON_REASON_CODES`, `LESSON_SITE_STATES`,
  `LOCATOR_KINDS`, `DEFAULT_WRITER_ROLES`, with the values in the Technical Plan §1 table. Extend
  `describe()` so `chanchi taxonomy list` returns them under a `lessons` key, an object with the
  sub-keys `target_kinds`, `generalities`, `severities`, `statuses`, `decisions`, `reason_codes`,
  `site_states`, `locator_kinds` and `default_writer_roles`, each a list of strings. No change to
  existing sets.

#### 5. `src/chanchi/errors.py` (Modify)

- **Type / Scope**: Python module, error codes and envelope.
- **Proposed Changes**:
  - `ChanchiError.__init__` takes an optional keyword `details: dict | None`; `to_dict()` adds
    `"details"` to the error object when it is set.
  - Add to `ERROR_CODES` the codes below. `exit_code` needs no change: every code except
    `internal` already maps to `EXIT_VALIDATION` (2).

  | Code | Message | `field` | `valid_values` | `details` | Hint |
  |---|---|---|---|---|---|
  | `project_not_registered` | "this directory is not inside a registered project" | `project` | | | `chanchi project register`, or `--global` |
  | `not_a_writer` | "role <role> cannot write lessons in <scope>" | `as` | the scope's writer roles | | `chanchi project writers <scope> --set ...` |
  | `self_review` | "lesson #<id> was recorded in this conversation" | `conversation` | | | review it from another conversation |
  | `duplicate_lesson` | "lesson looks like #<id>" | `general_rule` | | `{id, status, general_rule, shared, test}` | `chanchi lesson repeat <id> --evidence ...`, or `--force-new` |
  | `invalid_transition` | "lesson #<id> is <state>; <command> needs <allowed states>" | `status` | the allowed states | | the command that reaches an allowed state, e.g. `chanchi lesson reopen <id>` or `chanchi lesson reopen-site <id>` |
  | `lesson_not_found` | "no lesson #<id>" | `id` | | | `chanchi lesson list` |

  - **One rule for every other refusal.** A refusal that is not in this table uses the existing
    `invalid_value`, with `field` set to the JSON key (e.g. `particular_justification`,
    `incidents`) or the flag name without dashes (e.g. `where`, `site`, `reason_code`), and
    `valid_values` when the field is an enum. A missing lesson, including the `N` of `--of N`,
    is `lesson_not_found`. An unknown `change` or `session` in the body reuses the existing
    `unknown_change` and `unknown_session` raised by `record.get_change` and `record.get_session`.
    A state refusal on a site row is `invalid_transition` with `field` = `state`.

#### 6. `tests/test_taxonomy.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**: `describe()` includes the lesson sets with the values of the Technical Plan
  §1 table; `details` appears in the envelope only when set; each new code builds an envelope
  with the `field`, `valid_values` and `details` of the table in item 5.

#### 7. `src/chanchi/projects.py` (Modify)

- **Type / Scope**: Python module, project identity.
- **Proposed Changes**: add `_git`, `main_worktree`, `git_head`, `locate`, `resolve_scope`,
  `register`, `relink`, `list_projects`, `show`, `writer_roles`, `set_writer_roles` as specified
  in Technical Plan §2. Rewrite `detect()` on `_git` with the same behavior. `identify()` gains the
  keyword `conn`; `resolve_project()` passes it, and its hint mentions `chanchi project register`.
  `ensure()` is unchanged. `set_writer_roles` is a plain data function with no actor check; the
  guard lives in `lessons.set_writers` (item 12), because `projects.py` cannot import `lessons`.
- **Also in step 3** (`src/chanchi/cli.py`, Modify): `cmd_change_open` opens the connection
  before calling `projects.identify(args.project, conn=conn)`. This is the only `cli.py` change
  in step 3; the step-3 tests need it.

#### 8. `tests/test_projects.py`, `tests/conftest.py` and `tests/helpers.py` (Modify)

- **Type / Scope**: unit tests and shared fixtures.
- **Proposed Changes**:
  - `helpers.py`: `Recorder.change` (line 24) calls `projects.identify(conn=self.conn)` instead of
    `projects.identify()`, so recorded changes resolve as `cmd_change_open` does. `Recorder.pid`
    (line 31) already goes through `resolve_project(self.conn)` and needs no change.
  - `conftest.py` gains two fixtures. `registered_repo` is a git repository with one commit,
    registered with `projects.register`. `nested_repo` is a registered repository that contains
    an independent, unregistered repository in `inner/`. Both `monkeypatch.chdir` into the
    repository and make one commit with `git -c user.name=Test -c user.email=test@example.com
    commit -q -m init` after adding a file, as `tests/test_projects.py:19-26` does. The existing `git_repo` has no
    commit, so `git_head` is `None` there; it is unchanged.
  - Tests:
    - `main_worktree` from a linked worktree returns the main path.
    - `register` creates a row, adopts an unregistered row with the same slug, and is a no-op on a
      second run (`already_registered`).
    - `register` refuses a slug owned by another registered project, and fails outside a
      repository with `project_not_detected`.
    - `register --name X` leaves an unregistered folder-slug row alone.
    - `relink` adds a path, is a no-op for the project's own path, and refuses one owned by
      another project.
    - `locate` picks the longest prefix on whole segments (`/work/b` does not match `/work/bb`),
      with symlinks resolved on both sides.
    - From `nested_repo/inner`: `identify(conn=conn)` returns the outer project; `change open`,
      `session start`, `incident add` and `show` all resolve to it, and no `inner` row is created.
    - An explicit `--project` wins over the locator.
    - `resolve_scope` fails with `project_not_registered` outside any registered project, and
      `--global` with `--project` fails with `invalid_value`.
    - `git_head` returns the commit in `registered_repo`, and `None` outside a repository.
    - On an unregistered repository, `identify()` returns the same slug and path as before, no
      locator row exists, and `registered_at` stays NULL.
    - `writer_roles` returns the default when a scope has no rows; `set_writer_roles` replaces
      them.

#### 9. `src/chanchi/data/stopwords_en.txt` (Create)

- **Type / Scope**: data file, one lowercase word per line, `#` comments allowed.
- **Proposed Changes**: exactly these words, the function words of 4 or more letters that occur in
  lesson text, plus four words frequent in lesson text: `about`, `after`, `again`, `because`,
  `before`, `being`, `between`, `could`, `does`, `doing`, `during`, `each`, `from`, `have`,
  `having`, `into`, `more`, `most`, `other`, `over`, `same`, `should`, `some`, `such`, `than`,
  `that`, `their`, `them`, `then`, `there`, `these`, `they`, `this`, `those`, `through`, `under`,
  `until`, `very`, `were`, `what`, `when`, `where`, `which`, `while`, `will`, `with`, `would`,
  `your`, and the domain words `agent`, `lesson`, `rule`, `session`. Shorter words are not listed
  because the tokenizer drops them. It ships inside the package (`pyproject.toml:16-17` packages
  `src/chanchi`).

#### 10. `src/chanchi/dedup.py` (Create)

- **Type / Scope**: Python module, pure functions.
- **Proposed Changes**: `load_stopwords() -> frozenset[str]` (cached, read with
  `importlib.resources.files("chanchi") / "data" / "stopwords_en.txt"`, as `db.py:31` reads the
  template), `tokens(text)`, `coverage(a, b)`, `similar(text, candidates, limit=5)`,
  `matches(new, candidate)`, `blocking_match(new, candidates)`, and the six constants of Technical
  Plan §4. Candidates are plain dicts; the module does not touch the database.

#### 11. `tests/test_dedup.py` and `tests/fixtures/lessons/` (Create)

- **Type / Scope**: unit tests and fixture files.
- **Proposed Changes**:
  - Fixtures, each one lesson body in JSON: `base.json` (the CUJ 1 lesson);
    `same_rule_other_case.json` (the same general rule, a different `what_happened`);
    `same_case_other_words.json` (the same full text with the rule reworded); `unrelated.json`
    (shares exactly 2 tokens with `base.json`, none of them in `base.json`'s `general_rule`, so
    neither test can match; a test asserts this count).
  - Tests:
    - Tokenization: case, punctuation, 3-letter words dropped, stopwords dropped.
    - Coverage is 0 when either set is empty.
    - `same_rule_other_case` blocks by the rule test; `same_case_other_words` blocks by the full-text
      test; `unrelated` passes.
    - Each threshold at its boundary, with token sets built in the test (coverage divides by the
      smaller set, so only some ratios are reachable):
      - full text: 6 shared of a smaller set of 20 (0.30) blocks; 4 shared of 14 (0.286) does
        not; 3 shared of 3 (1.0) does not, because it is under 4 shared tokens;
      - general rule: 3 shared of 6 (0.50) blocks; 3 shared of 7 (0.43) does not; 2 shared of
        2 (1.0) does not.
    - `blocking_match` returns the highest coverage, then the lowest id.
    - `similar` returns at most 5, ordered by coverage, then shared count, then id.

#### 12. `src/chanchi/lessons.py` (Create)

- **Type / Scope**: Python module, lesson rules and transitions.
- **Proposed Changes**:
  - `Actor` dataclass (`role`, `agent`, `model_raw`, `model_id`, `effort`, `conversation`) and
    `make_actor(conn, as_role, author_spec, conversation)`, using `modelspec.parse` and
    `catalog._model_row`. An exact catalog match is accepted; a colon is refused only for a miss
    whose last segment is within edit distance 2 of an effort (Technical Plan §3). The edit
    distance is a small local helper (Levenshtein on strings of at most 10 characters).
  - `check_writer(conn, scope_project_id, actor)` per Technical Plan §3.
  - `set_writers(conn, scope, actor, roles) -> dict`: calls `check_writer(conn, scope.project_id,
    actor)`, then `projects.set_writer_roles`. Roles are stripped; a blank role or an empty list
    fails with `invalid_value` (`field` = `set`); duplicates are dropped, order kept. It writes no
    `lesson_events` row (the event table is for lessons). Returns `{"scope": <slug or "global">,
    "roles": [...], "default": false}`.
  - Signatures (each returns the result dict of the Technical Plan §3 "Results" table; `scope` is
    a `projects.Scope`, or `None` for every lesson):
    - `add(conn, scope, actor, body, *, force_new=False, cwd=None)`
    - `repeat(conn, actor, lesson_id, evidence, *, incident=None)`
    - `modify(conn, actor, lesson_id, body)`
    - `review(conn, actor, lesson_id, decision, reason, *, reason_code=None, of=None)`
    - `reopen(conn, actor, lesson_id, reason)`
    - `apply(conn, actor, lesson_id, site, where, *, project_scope=None)` and
      `retire(conn, actor, lesson_id, site, reason, *, project_scope=None)`; `project_scope` is
      required when `site == "project"`
    - `similar(conn, text, *, limit=5)`, `list_lessons(conn, scope, *, status=None,
      generality=None, target_kind=None, limit=50)`, `show(conn, lesson_id)`,
      `summary(conn, scope)`, `export(conn, scope, *, status=("pending", "postponed"),
      generality=None, target_kind=None, since=None, limit=20)`, `export_markdown(rows) -> str`
  - Each write runs in one `db.transaction` and
    writes the event of the Technical Plan §3 events table. Preconditions follow the two state
    tables in "Vocabulary and states" and the rules in §3. The duplicate classes follow §4.
  - Required text is validated with `record._required_text` and tags are normalized with
    `record._csv`; neither is copied. `git_head` comes from `projects.git_head`, because only
    `projects.py` may import `subprocess`.

#### 13. `tests/test_lessons.py` (Create)

- **Type / Scope**: unit tests. This list is complete.
- **Proposed Changes**:
  - A body without `general_rule` is refused. A `particular` lesson at `medium`, or without a
    justification, is refused; a justified `critical` one is recorded.
  - `severity: blocking` is refused with the hint. An unknown JSON key is refused.
  - `session` without `change` is refused; an incident from another change is refused.
  - A `--global` lesson that is not `agnostic`, or that carries `change`, is refused.
  - `tags` given as a list and as a string store the same text; no tags, `[]` and `""` store
    `''`. A non-string text field (`"cause": 3`), a string `incidents` and a non-object body are
    refused with `invalid_value` naming the key, before any other rule runs.
  - An unknown `change` fails with `unknown_change`; `--of 999` fails with `lesson_not_found`; a
    voided incident is refused.
  - `author_model_id` is set on an exact catalog match and NULL otherwise, and no row is added to
    `models`. `--author human` gets the seeded `human:human` row. `claude:opus:hgh` is refused
    (`field` = `author`). `opencode:openrouter/qwen/qwen3-coder:free` is accepted with
    `author_model_id` set, and `opencode:vendor/model:beta` (not in the catalog, last segment far
    from every effort) is accepted with `author_model_id` NULL.
  - A non-writer role is refused; `human` passes; a custom writer role set with
    `set_writer_roles` passes; a global lesson uses the global writer roles; an agnostic lesson is
    reviewed under its origin project's roles.
  - `set_writers`: a non-writer role is refused with `not_a_writer`; a current writer role or
    `human` replaces the roles; a blank role or an empty list is refused; `planner,planner`
    stores one row; changing the global list does not change a project's list.
  - Review from the recording conversation is refused; from another conversation it passes.
  - `postpone` from `postponed` is refused; `approved` cannot be reopened.
  - `duplicate --of N` moves occurrences to N; `--of` its own id, or a duplicate N, is refused;
    lessons already pointing to the lesson are re-pointed to N.
  - `reopen` from `duplicate` gives the moved occurrences back, never below 1, and clears the six
    review fields.
  - `model_weakness` without a linked session is refused.
  - `repeat` adds one occurrence; it is refused on `duplicate`; on `rejected` it returns
    `rejected_recurs`; `--incident` on a lesson without a change is refused.
  - `modify` from another conversation, or after approval, is refused; it re-runs the duplicate
    check without matching itself.
  - `apply` on a non-approved lesson is refused; `where_` without the tag is refused; a `project`
    lesson applied at another project or at `--site global` is refused; re-applying `retired`
    works; re-applying `applied` updates `where_`.
  - `retire` at one site leaves the other sites `applied`.
  - Every write writes exactly one event, with the action, the states and the site columns of the
    events table.
  - Duplicate classes: an approved lesson with every site retired only warns; one with no sites
    blocks; a `project` lesson of another project warns `possibly_agnostic`; a `force_new` event
    note records the match.
  - `export` orders by generality, severity, occurrences, then id; the default limit is 20;
    `--since` filters on `created_at`; `export_markdown` produces one heading per lesson.
  - Read commands report the scope they used.

#### 14. `src/chanchi/cli.py` (Modify)

- **Type / Scope**: Python module, argument parsing, handlers and output.
- **Proposed Changes**:
  - `FORMATS` becomes `("json", "text", "md")`. `_emit` writes `payload["markdown"]` for `md` when
    present and the text rendering otherwise. `_sniff_format` needs no change.
  - `leaf()` gains an optional `parents` argument, appended after `common`.
  - A parent parser `identity` holds only `--as` (`dest="as_role"`), `--author` (`dest="author"`)
    and `--conversation` (`dest="conversation"`), all `required=True`. It holds no `--global`;
    each command that accepts `--global` adds it itself with `dest="global_"`, as
    `cli.py:286` does for `skills link`.
  - Where `--global` is accepted (Technical Plan §3, "Scope flags"): `lesson add`, `project
    writers`, and the read commands `similar`, `list`, `summary`, `export`. `lesson repeat`,
    `modify`, `review` and `reopen` take neither `--global` nor `--project`: they act on the
    lesson's origin. `lesson apply` and `retire` take `--site global|project`, and `--project`
    only to name the project when `--site project` is run outside it.
  - New group `project`: `register [--name]`, `relink <slug>`, `list`, `show [<slug>]`,
    `writers [<slug>] [--global] [--set <role,...>] [--as ...] [--author ...] [--conversation
    ...]`. `writers` does not use the `identity` parent: it declares the three flags itself as
    optional, and the handler requires all three when `--set` is given (missing one fails with
    `invalid_value`, `field` = the missing flag without dashes, e.g. `as`). A positional slug wins
    over `--project`; if both are given and differ, it fails with `invalid_value`. `--global` with
    a slug fails with `invalid_value`.
  - New group `lesson`: `add`, `repeat`, `modify`, `review`, `reopen`, `apply`, `retire` (with
    `identity`), and `similar`, `list`, `show`, `summary`, `export` (with `--all` and `--global`,
    mutually exclusive). `add` and `modify` take `--json -` (stdin) or `--json <file>`; `add` takes
    `--force-new`. `review --decision` uses `choices=LESSON_DECISIONS`; every other enum flag is
    validated in `lessons.py` with `taxonomy.validate_choice`, so the error envelope matches.
  - Handlers only parse arguments and call `projects` or `lessons`, as the existing handlers call
    `record`. `project writers --set` calls `lessons.set_writers`, never
    `projects.set_writer_roles` directly. Comma lists use `cli._split`, integers `cli._int`, and
    `--since` `timeutil.since_to_iso`. The `export` handler adds `markdown` to the payload when
    `args.format == "md"`. (`cmd_change_open` was already changed in step 3.)
  - The `--project` help text changes from "default: git toplevel name" to "default: the
    registered project for this directory, else the git toplevel name".

#### 15. `tests/test_cli.py` and `tests/test_cli_integration.py` (Modify)

- **Type / Scope**: CLI tests.
- **Proposed Changes**:
  - Every new command parses; `--format md` works on `lesson export` and falls back to text
    elsewhere.
  - Each new error code reaches stderr with the fields of the table in item 5.
  - `project show <a> --project <b>` fails.
  - End-to-end runs of CUJs 1, 2, 3, 4 and 7 in a temporary `CHANCHI_DB` with the `registered_repo`
    and `nested_repo` fixtures. CUJ 4 includes `change open` and `session start` from the inner
    repository.

#### 16. `src/chanchi/skills_link.py` (Modify)

- **Type / Scope**: Python module.
- **Proposed Changes**: `SUGGESTED_CONFIG_LINE` (lines 11-14) becomes exactly: "When assigning
  sessions use the `chanchi-model-selection` skill; when orchestrating and auditing sessions use
  the `chanchi-session-audit` skill; at the end of each conversation, writer roles use the
  `chanchi-lessons` skill." `available_skills()` (line 28)
  already picks up any `chanchi-*` folder with a `SKILL.md`, so linking needs no change.

#### 17. `skills/chanchi-lessons/SKILL.md` (Create)

- **Type / Scope**: agent skill.
- **Proposed Changes**: frontmatter `name: chanchi-lessons` and a description that triggers at the
  end of a conversation, after an audit that found a failure, and in maintenance conversations.
  Body as in Technical Plan §6: the principles and triggers, the record steps, the field guide
  with the severity and generality tables, one full `lesson add` example with a heredoc, the
  review steps and questions, and the lines to paste. At most 150 lines. It quotes no stage-2
  command.

#### 18. `skills/chanchi-session-audit/SKILL.md` (Modify)

- **Type / Scope**: agent skill.
- **Proposed Changes**: a new sub-bullet at the end of step 5 ("Record the verdict"), so the
  numbered list stays whole: "If the audit found a failure of the process (not only of the model),
  after recording incidents, follow `chanchi-lessons` to record a lesson that links the session and
  incidents. A failure that is only one model's weakness stays an incident."

#### 19. `README.md` (Modify)

- **Type / Scope**: documentation.
- **Proposed Changes**: new section "Lessons" after "Everyday commands": what a lesson is, what it
  improves (global and project setup, not code, not ratings), `project register` and `relink`
  (including that `--name` leaves the folder-slug history where it is), writer roles, the record
  and review commands, the lines to paste, and the stage-1 threat model (roles are declared, not
  checked against the harness). "Give the skills to a project" lists `chanchi-lessons`.
  "Databases and migrations" adds the rollback note for version 4.

#### 20. `tests/test_skills_content.py` and `tests/test_cli.py` (Modify)

- **Type / Scope**: skill tests.
- **Proposed Changes**: `test_both_skills_exist` (line 27) is renamed `test_all_skills_exist`
  and its expected list becomes `["chanchi-lessons", "chanchi-model-selection",
  "chanchi-session-audit"]` (`SKILL_FILES` is sorted, so `chanchi-lessons` comes first); the frontmatter and quoted-command checks (lines 30-45) already run on every
  skill; a new test checks that `skills/chanchi-lessons/SKILL.md` has at most 150 lines. The CLI
  test at `tests/test_cli.py:163-168`, which links the real skills folder, also checks that
  `chanchi-lessons` is linked and that `SUGGESTED_CONFIG_LINE` names it.

#### 21. `docs/designs/continuous-improvement.md` (Modify)

- **Type / Scope**: design document.
- **Proposed Changes**: the Status line becomes "Stage 1 implemented" when stage 1 merges.

### Stage 2: Target Files to Create/Modify

Stage 2 is done in three steps, each ending with `uv run pytest` passing.

| Step | Files | Checkpoint |
|---|---|---|
| 1. Lessons | 22, 26 | `tests/test_lessons.py` passes, including the inbox, decline, replaces and verify tests |
| 2. CLI | 23, 27 | `tests/test_cli.py` and `tests/test_cli_integration.py` pass |
| 3. Skill, docs and status | 24, 25, 28 | the full suite passes; the stage-2 Verification Plan is run |

#### 22. `src/chanchi/lessons.py` (Modify)

- **Type / Scope**: Python module.
- **Proposed Changes**: add `inbox`, `decline`, `reopen_site` and `verify` per Technical Plan §5,
  and the retire-on-apply step in `apply`. `summary` adds the inbox size when a project resolves.

#### 23. `src/chanchi/cli.py` (Modify)

- **Type / Scope**: Python module.
- **Proposed Changes**: add `lesson inbox [--all] [--target-kind ...] [--since <date>]
  [--limit 20]`, `lesson decline <id> (--reason ... | --not-applicable)`,
  `lesson reopen-site <id> --reason ...` (both with the `identity` parent), and
  `lesson verify [--global] [--scan <path>]...`.

#### 24. `skills/chanchi-lessons/SKILL.md` (Modify)

- **Type / Scope**: agent skill.
- **Proposed Changes**: the review part adds `lesson inbox` (apply, decline or mark not applicable
  for each item) and `lesson verify` (fix every `missing_tag` and `stale_tag`; check `unchecked`
  items by hand). It stays within 150 lines.

#### 25. `README.md` (Modify)

- **Type / Scope**: documentation.
- **Proposed Changes**: the "Lessons" section adds the inbox, `replaces`, and verify, and how the
  backlog filter works for a project registered later.

#### 26. `tests/test_lessons.py` (Modify)

- **Type / Scope**: unit tests.
- **Proposed Changes**:
  - The inbox shows only approved agnostic lessons applied to at least one project site and not
    decided by this project; a lesson applied at the global site never appears.
  - The backlog filter by registration date and severity, and `--all`.
  - Decline, `--not-applicable`, and `reopen-site` (the row is removed and its events remain);
    `apply` on a declined row is refused with the `reopen-site` hint.
  - An item that replaces a lesson this project applied lists it in `replaces_applied_here`.
  - Applying a lesson that replaces another retires it at the same place only, with one event per
    retired site.
  - Verify, on fixture files in a temporary directory: `missing_tag`, `stale_tag`, `unknown_tag`,
    `missing_file`, `unchecked` for a `hook` target, absolute, `~` and relative paths, `--global`
    outside a project, and the line and tag counts per file. `--scan` on a directory, a relative
    `--scan` path and a non-UTF-8 file follow the rules of Technical Plan §5.
  - `summary` reports the inbox size when a project resolves, and omits it otherwise.

#### 27. `tests/test_cli.py` and `tests/test_cli_integration.py` (Modify)

- **Type / Scope**: CLI tests.
- **Proposed Changes**: `lesson inbox`, `decline`, `reopen-site` and `verify` parse, including
  `decline` without `--reason` or `--not-applicable` (refused) and `verify --scan` given twice;
  end-to-end runs of CUJs 5 and 6 across two temporary registered projects.

#### 28. `docs/designs/continuous-improvement.md` (Modify)

- **Type / Scope**: design document.
- **Proposed Changes**: the Status line becomes "Stages 1 and 2 implemented" when stage 2 merges.

### Verification Plan

Stage 1 runs every check below at the end of step 7. Stage 2 runs the build, the tests and the
stage-2 manual journey at the end of its step 3.

- **Build**: `uv tool install --editable .` exits 0, and `chanchi --version` prints the version.
- **Unit and integration tests**: `uv run pytest` passes, including the template drift check in
  `tests/test_db.py` and `tests/test_no_network.py`.
- **Duplicate-check speed** (stage 1, step 4, before any command exists): a throwaway script in
  the scratch directory builds 1,000 candidate dicts from the fixture texts with varied words,
  and times `dedup.blocking_match(new, candidates)` with `time.perf_counter()`. It must take under
  100 ms. Record the number in the stage's pull-request description. The script is not committed.
- **Migration on real data** (stage 1): copy the operational database
  (`$XDG_DATA_HOME/chanchi/chanchi.db`, `~/.local/share/chanchi/chanchi.db` by default, or
  `CHANCHI_DB`) to a temporary path `$T`. Build the older chanchi from `main` before the stage-1
  merge in a separate worktree: `git worktree add $W main`, then run
  `CHANCHI_DB=$T uv run --project $W chanchi show <an existing change> --project <its slug>` and
  save the output. Then run `CHANCHI_DB=$T chanchi models list` with the new build, which opens
  and migrates the database. Check that `$T.bak-v3` exists, that `CHANCHI_DB=$T chanchi db status`
  reports operational version 4, and that the same `show` command with the new build returns
  identical JSON. Remove the worktree with `git worktree remove $W`.
- **Manual journey, stage 1**: in a scratch `CHANCHI_DB`, register two temporary projects (one
  with a nested repository), then run CUJs 1, 2, 3, 4 and 7 by hand, and paste the JSON outputs
  into the stage-1 pull-request description.
- **Manual journey, stage 2**: in a scratch `CHANCHI_DB` with two registered temporary projects,
  run CUJs 5 and 6 by hand, and paste the JSON outputs into the stage-2 pull-request description.
- **Skill check** (stage 1): `chanchi skills link` into a scratch directory creates
  `chanchi-lessons` in both `.agents/skills` and `.claude/skills`.
