# Continuous Improvement (Lessons) in chanchi

- **Author:** Iván R
- **Date:** 2026-11-18
- **Revision:** 2 (after the first Goldfish review: seven lenses on Revision 1)

## Overview

When something goes wrong in a working conversation, the agent that coordinates the work records a
**lesson**: what happened, the evidence, the cause, and the general rule that would have prevented
it. Each lesson names the one place where the fix belongs, such as a role definition, a skill, a
harness wrapper, a rules file, a hook or a workflow. A different conversation later reviews pending
lessons, decides, applies the approved ones by hand, and records where each change landed. A rule
that holds in any project can be applied in the user's home setup, and can be offered to each of
the user's other projects, which then adopt it or decline it.

chanchi stores, deduplicates, orders and tracks lessons, and compares what it recorded with what
the files say. It never edits a role, skill, prompt, rules file or harness setting by itself, except
for the hook adapters a user installs on purpose (stage 3).

The method comes from a per-project process the owner already uses elsewhere. Its principles are
restated here so this brief stands on its own:

1. **Fix first, then record.** A lesson is for learning; it does not replace the fix.
2. **Record only what really went wrong**: a wrong result, work that had to be redone, an existing
   rule that was not followed, a control that did not stop what it should, or an assumption that
   turned out false. A run that went well records nothing.
3. **From general to particular.** Every lesson carries a general rule. Rules that only serve one
   case become noise and narrow the model.
4. **The author does not judge.** A different conversation reviews, so the person or agent that
   made the mistake does not rule on it.
5. **What matters does not depend on the model obeying.** Hard rules are enforced by the database,
   the CLI or a hook, not by a line in a prompt.

## Analysis

### What two consumer projects show (illustration, not requirements)

Two of the owner's projects that already use chanchi were read on 2026-11-18. They are private, so
they are evidence for the motivation only. The requirements below stand without them.

- **Role content is written once, and each harness gets a thin wrapper.** One project keeps each
  role in `.agents/roles/<name>.md` and has three wrappers that only point to it
  (`.claude/agents/<name>.md`, `.agents/agents/<name>/agent.md` for agy,
  `.opencode/agents/<name>.md`). The other does the same with `agents/agents/<name>.md`, with some
  wrappers missing. So most fixes belong in the shared **role**. A **wrapper** fix is the rare,
  harness-specific case.
- **Rules were copied between projects once, by hand.** The newer project carries 30 rules tagged
  `[<older project>, <incident>]` in its roles, plus 9 in its skills, copied when it was created.
  Nothing records which rules it took, skipped or never saw. This is a one-time copy, not a steady
  stream, so cross-project sharing is staged after the core.
- **Every "Lessons learned" section in the newer project is empty.** The practice "the planner
  appends rules here after audits" is written down but has never been used. If it were used, the
  agent that recorded a lesson would also apply it with no separate review, which principle 4
  forbids.
- **Rules cost context.** The newer project's role folder is 1,932 lines, and its README says "a
  weak model reads it in full at every startup: every sentence must change behaviour". Removing and
  merging rules has to be part of the cycle.
- **Roles also run as top-level processes.** Executors and auditors start as
  `claude --agent executor`, `agy --agent auditor` or `opencode run --agent ...` in their own
  terminal panes, not only as subagents. A guard that only asks "is this a subagent?" misses them.
- **Nested repositories.** The newer project is one root repository that contains two independent
  git repositories, and agents run commands inside them. `git rev-parse --show-toplevel` from there
  returns the inner repository, not the project.

### What the review found, and how this revision answers it

| Finding | Lens | Answer in this revision |
|---|---|---|
| Revision 1 bundled about 10 subsystems, 7 tables and about 25 commands into one unit, with little evidence of need | zoom-out, structural, readiness | Four stages, each shippable alone. Stage 1 is the core the owner asked for. Hooks come last (§11) |
| Fields, states and thresholds were defined by pointing to a private Spanish document | comprehension, structural | Principles, fields, states and thresholds are written out here (§3 to §6) |
| One `status` cannot describe a rule applied in several places, and retiring it in one project must not retire it in all | design, structural | The decision on the rule is separate from where it is applied: `lesson_sites`, one row per place (§3, §4) |
| A run with an unknown role could write, and in Claude Code a subagent shares its parent's `session_id`, so a guard on "the run's role" lets an executor subagent through | catalyst, design, readiness | The CLI checks the declared actor role on every write. Unknown means no. The stage-3 hook reads the actor of each event (`agent_type`), not the run (§8) |
| `Stop` and `session.idle` fire after every reply, not at the end of a conversation | catalyst, design, readiness | The retrospective is a written rule plus a skill. The stage-3 stop nudge fires once per run, only for writer roles, and never closes the run (§9) |
| A pre-tool hook runs on every tool call, and chanchi exits 2 on errors, which Claude Code reads as "block" | design, readiness | `hook check` always exits 0, fails open, never migrates, and the adapter only calls it when the command mentions chanchi (§10) |
| "Agents are any value a user adds" is false: `taxonomy.ALL_AGENTS` is fixed (`taxonomy.py:10-12`) | codebase | Agents are validated against `taxonomy.ALL_AGENTS`. Opening that list is a non-goal |
| Detection from the working directory breaks inside nested repositories, and `detect()` returns the current worktree, not the main one (`projects.py:32,48`) | catalyst, codebase | Resolution goes by the longest registered path that contains the working directory first (§7) |
| Hook payload model names will not match the catalog, and auto-adding them would pollute `recommend` | codebase, design | The author's model is stored as raw text, with `model_id` filled only on an exact catalog match. Nothing is ever inserted into `models` (§3) |
| Global lessons recorded from `~` have no project | design | Lessons may have a global origin, governed by global settings (§3, §7) |
| Opencode blocking, agy context injection, agy and opencode role visibility, and native-id stability are unverified | codebase, readiness | They are listed as stage-3 verification work, delegated to agy, and each adapter ships only what was observed working (§11) |

### The contradictions left, and how they are resolved

1. **Rules must keep coming, and role files must stay short.** Resolved by making the reviewer
   prefer fixes that cost no context (a hook, a permission or a CLI check before a role line), by
   `replaces` with retirement per site, and by `lesson verify`, which reports rule counts and lines
   per target file (stage 2). A hard size budget per file is deferred until real lessons show the
   growth rate.
2. **chanchi never edits files, and the database must match the files.** Resolved with the
   `[lesson #N]` tag as the anchor. `lesson verify` scans recorded target paths and reports four
   cases: applied with no tag, retired with the tag still present, unknown tags, and size per file.
   It reads only.
3. **The author has the best context, and the author must not judge.** Resolved by capturing
   checkable pointers at record time (git HEAD, the linked change, session and incidents) so the
   reviewer can rebuild the case without trusting the author's prose.
4. **Agnostic rules should reach every project, and each project must decide.** Resolved by pull,
   not push: a lesson reaches other projects' inbox only after it is approved and applied
   somewhere, and only when its fix is in project files. A project that registers later sees only
   the `high` and `critical` backlog by default.

### Ideal final result

Who wrote what never depends on a prompt line, and an unknown author cannot write. A lesson is
recorded once, reviewed by someone else, applied where it costs the least context, and tracked per
place. The files and the database are compared on every maintenance run. Agents in any of the three
harnesses get the same rules from one command.

## Design

### 1. Vocabulary

| Term | Meaning |
|---|---|
| **harness** (stored as `agent`) | The program that runs a model: `claude`, `agy`, `opencode`, or `human`. The fixed list is `taxonomy.ALL_AGENTS` |
| **wrapper** | A small harness-specific file that starts a role in one harness and points to the role's shared definition |
| **role** | A named job with its own instructions, such as `planner`, `executor` or `auditor`. Names belong to each project and are stored as text |
| **writer role** | A role allowed to record and review lessons. Set per project in the database (`planner` by default) |
| **orchestrator** | The writer role that coordinates the work. It sees whole failures, which is why it records |
| **reporter** | Any other role. It mentions what went wrong in its report and never records |
| **change** | An existing chanchi unit of planned work (`changes` table) |
| **session** | An existing chanchi record of one executor turn inside a change (S1, S2, ...). Unchanged |
| **incident** | An existing chanchi fact about one session or change, with evidence, used for model ratings |
| **conversation** | One working conversation in one harness, from start to end. Harnesses call it a session; this brief never does |
| **conversation id** | The id a harness gives a conversation: Claude Code `session_id`, agy `conversationId`, opencode `sessionID` |
| **lesson** | One improvement record: a general rule plus the case that showed it |
| **site** | One place where a lesson is applied: global (home setup) or one project |
| **maintenance run** | A conversation, different from the one that recorded a lesson, that reviews and applies lessons |
| **inbox** | The approved agnostic lessons that one project has not decided on yet (stage 2) |

**Boundaries.** An incident changes a model's rating. A lesson changes instructions or controls. A
failure caused by one model's weakness is an incident, not a lesson.

### 2. Generality and target: two separate questions

- **Generality** says how far the **rule** holds: `agnostic` (any project, any harness),
  `project` (all of one project), `particular` (one case). It is decided by the rule, not by the
  proposed fix. A rule that holds anywhere is agnostic even if the fix touches one file.
- **Target** says where the author thinks the **fix** goes: `target_kind` plus `target`, a free
  text naming one place, such as `role planner`, `wrapper claude/executor`, or
  `skill ~/.agents/skills/chanchi-session-audit`. It is one place, the most general one where the
  fix makes sense. Other places go in the proposal.

| Generality | Reviewed in | Can reach other projects' inbox (stage 2) |
|---|---|---|
| `agnostic` | the global list (any maintenance run with a global writer role) | yes, after it is applied once to a project site |
| `project` | its origin project | no |
| `particular` | its origin project; only `high` or `critical`, with a justification | no |

### 3. Data model (stage 1 unless noted)

One migration per stage. Stage 1 is `004_lessons.sql`.

**`projects`** (existing): add `registered_at` (NULL for rows auto-created by audits).

**`project_locators`**: `id`, `project_id` FK, `kind` (`path` | `remote`), `value`.
`UNIQUE(kind, value)`. Added only by `project register` and `project relink`, never by a read.

**`writer_roles`**: `project_id` FK nullable (NULL means the global scope), `role`.
`UNIQUE(project_id, role)`. When a scope has no rows, the code applies the default `planner`. No
backfill is needed.

**`lessons`**:

| Column | Required | Content |
|---|---|---|
| `id` | yes | integer, shown as `#42` |
| `origin_project_id` | no | FK to `projects`. NULL means a global origin (recorded outside any registered project) |
| `author_role` | yes | the role that recorded it; must be a writer role in the origin scope, or the agent is `human` |
| `author_agent` | yes | one of `taxonomy.ALL_AGENTS` |
| `author_model_raw`, `author_model_id`, `author_effort` | model text yes, others no | the model as the author or hook reported it; `author_model_id` is set only on an exact catalog match; effort may be `unknown` |
| `author_conversation` | yes | the conversation id when known, otherwise a label such as `2026-11-18 checkout review` |
| `git_head` | no | captured at record time when inside a repository |
| `change_id`, `session_id` | no | links to an audited change or executor session; the session gives the executor's model and effort |
| `target_kind` | yes | `role`, `skill`, `wrapper`, `rules-file`, `hook`, `permission`, `workflow`, `tool` |
| `target` | yes | one place, free text (see §2) |
| `what_happened` | yes | the fact |
| `evidence` | yes | where it can be checked: a file and line, a commit, a log, a report, an incident id; or `none` with the reason |
| `cause` | yes | why it happened; the cause, not the symptom |
| `prevention` | yes | what would have prevented it |
| `proposal` | yes | the concrete change |
| `general_rule` | yes | the rule that holds beyond this case. Always required |
| `generality` | yes | `agnostic`, `project`, `particular` |
| `severity` | yes | risk if it happens again (table below) |
| `particular_justification` | when particular | why it is serious and why it cannot be generalized |
| `occurrences` | yes | starts at 1 |
| `tags` | no | comma-separated |
| `status` | yes | the decision on the rule (§4) |
| `reviewed_at`, `reviewed_by_role`, `review_conversation`, `decision_reason`, `reason_code` | after review | who decided, from which conversation, and why |
| `duplicate_of` | when duplicate | FK to `lessons`, never itself |
| `created_at`, `updated_at` | yes | UTC |

Severity is measured by the risk if it happens again, not by this time's damage:

| Severity | If it happens again |
|---|---|
| `low` | a little time is lost |
| `medium` | work must be redone, or a wrong result appears that is noticed soon |
| `high` | a wrong result appears that may go unnoticed, or a control stops failing to block what it should |
| `critical` | data is lost, production is touched, or a secret is exposed |

Lesson severity uses `critical`; incident severity uses `blocking` (`taxonomy.py:22`). They measure
different things, and `lesson add` rejects `blocking` with a hint.

**`lesson_sites`**: one row per place a lesson is applied or declined. `id`, `lesson_id` FK,
`site` (`global` | `project`), `project_id` (required when `site = project`), `state` (§4),
`where_` (path plus the `[lesson #N]` tag; commit optional), `reason`, `decided_conversation`,
`decided_at`. `UNIQUE(lesson_id, site, project_id)`.

**`lesson_replaces`**: `lesson_id`, `replaced_id`, both FK to `lessons`, never equal. A rule that is
in a file but is not a lesson is named in the proposal text instead.

**`lesson_incidents`**: `lesson_id`, `incident_id`. Facts already recorded as incidents are cited,
not copied.

**`lesson_events`**: `id`, `lesson_id`, `at`, `actor_role`, `actor_agent`, `conversation`,
`action`, `from_state`, `to_state`, `site_id` (nullable), `note`. Every change writes one row.

**Constraints.** `CHECK` holds only structural invariants that never change: required text is not
empty; a particular lesson has a justification and is `high` or `critical`; `duplicate` has
`duplicate_of`; a reviewed status has `reviewed_at`; a site row in `applied` has `where_`. Enum
sets and every policy (writer roles, thresholds, agent list) are validated in `taxonomy.py` and the
CLI, following the precedent of `003_model_capabilities.sql`, so they can change without rebuilding
tables. The enum sets above are settled now because SQLite cannot alter a `CHECK` later.

**Stage 3 adds `runs`**: `id`, `agent`, `conversation_id`, `UNIQUE(agent, conversation_id)`,
`source` (`hook` | `manual`), `project_id` nullable, `role`, `role_source` (`harness` | `launcher` |
`unknown`), `model_raw`, `model_id` nullable, `effort` nullable, `session_id` nullable,
`opened_at`, `last_seen_at`, `retro_requested_at`, `retro_at`, `retro_notes`. When `session_id` is
set, model and effort are read from the session and not stored twice.

### 4. States

**Lesson decision (`lessons.status`)**

| From | Command | To | Who | Precondition |
|---|---|---|---|---|
| (new) | `lesson add` | `pending` | writer role | no blocking duplicate, or `--force-new` |
| `pending`, `postponed` | `lesson review --decision approve` | `approved` | writer role | review conversation differs from `author_conversation` |
| `pending`, `postponed` | `lesson review --decision reject` | `rejected` | writer role | same; `--reason` required |
| `pending` | `lesson review --decision postpone` | `postponed` | writer role | same; `--reason` required |
| `pending`, `postponed` | `lesson review --decision duplicate --of N` | `duplicate` | writer role | N is not this lesson; occurrences move to N |
| `rejected`, `postponed`, `duplicate` | `lesson reopen` | `pending` | writer role | `--reason` required |
| `pending`, `postponed` | `lesson modify` | same | the author conversation only | others add evidence through `lesson repeat` |
| any except `duplicate` | `lesson repeat` | same | writer role | adds 1 occurrence and evidence; a `rejected` lesson that recurs is reported as such |

Reason codes for review: `model_weakness` (one model failed; record an incident on the linked
session instead; allowed only when the lesson links a session), `covered` (an existing rule already
covers it; adjust that rule instead), `too_costly` (rare and cheap; not worth the context),
`symptom_only` (the cause is not identified).

**Site (`lesson_sites.state`)**

| From | Command | To | Precondition |
|---|---|---|---|
| (none) | `lesson apply N --site global\|project --where ...` | `applied` | lesson is `approved` |
| (none) | `lesson decline N --reason ...` (stage 2, inbox) | `declined` | lesson is `approved` and agnostic |
| (none) | `lesson decline N --not-applicable` (stage 2) | `not_applicable` | same |
| `applied` | `lesson retire N --site ... --reason ...` | `retired` | the rule was removed or merged at that site |
| `applied` | applying a lesson whose `replaces` lists N, at the same site | `retired` | automatic, one event row |
| `declined`, `not_applicable` | `lesson reopen-site` | (row removed, back in the inbox) | `--reason` required |

A lesson is "applied" when it has at least one `applied` site. Retiring is per site: retiring #42
in one project leaves it applied elsewhere.

### 5. Duplicate detection

The source method's word-overlap check, with the values written out:

- **Tokens:** lowercase; split on anything that is not a letter or digit; keep tokens of 4 or more
  characters that are not in the stopword list (`src/chanchi/data/stopwords_en.txt`, committed).
- **Coverage** = shared tokens / size of the smaller set.
- **`lesson similar "<text>"`** returns the 5 closest lessons that share at least 2 tokens.
- **`lesson add` blocks** when an existing `pending`, `postponed`, `approved` or applied lesson is
  close by either test:
  - full text (`what_happened` + `general_rule` + `proposal`): at least 4 shared tokens and
    coverage of at least 0.30;
  - general rule alone: at least 3 shared tokens and coverage of at least 0.50.
- The block names the matched lesson, its general rule and the shared tokens, and offers
  `lesson repeat <id>` or `--force-new`. `--force-new` is logged as an event, and
  `lesson summary` shows its rate as a health signal for the thresholds.
- **Warn only** (no block) when the match is `rejected`, `duplicate`, or retired at every site
  ("this rule was retired; consider `lesson reopen`"), or when it is a `project` lesson of another
  project ("possibly agnostic: the same rule appears in two projects").
- The thresholds were tuned on short Spanish texts. They are starting values, kept in one constant
  each, and covered by fixture tests: a near-duplicate told with another case must block; a
  different lesson sharing a few words must pass.

### 6. Command surface

All commands print JSON by default and use `ChanchiError` with `field`, `valid_values` and `hint`.

| Command | Stage | Needs a registered project | Needs a writer role |
|---|---|---|---|
| `project register [--name] [--no-remote]` | 1 | no | no |
| `project relink <slug>` / `rename` / `list` / `show` | 1 | no | no |
| `project writers <slug\|--global> --set planner,lead` | 1 | yes (or `--global`) | the caller declares a writer role or is `human` |
| `lesson add --as <role> --author <agent:model[:effort]> --conversation <id\|label> --json -` | 1 | yes, or `--global` | yes |
| `lesson similar`, `list`, `show`, `summary`, `export` | 1 | no | no |
| `lesson repeat`, `modify`, `review`, `reopen`, `apply`, `retire` | 1 | yes, or `--global` | yes |
| `lesson inbox`, `decline`, `reopen-site`, `verify` | 2 | yes | `verify` no; others yes |
| `run open`, `run current`, `retro` | 3 | no | no |
| `hook check --event session-start\|pre-tool\|stop` | 3 | no | no |
| `hooks install\|uninstall\|status --agent claude\|agy\|opencode` | 3 to 4 | no | no |

`--as` is the role the caller declares. In stage 1 that is an honest-agent guard: it stops an
obedient agent that was told it is not a writer, not an adversary. In stage 3 the hook checks the
declared role against the role the harness reports for the event, and refuses a mismatch.

`export` and `inbox` take `--limit` (default 20), `--generality`, `--target-kind` and `--since`,
and order by generality, then severity (critical first), then occurrences.

New error codes, registered in `errors.ERROR_CODES` (`errors.py:11-25`): `project_not_registered`,
`not_a_writer`, `self_review`, `duplicate_lesson`, `invalid_transition`, `lesson_not_found`,
`run_not_found`. Each message names the next command to run. For example, `not_a_writer` prints the
role it saw, the scope's writer roles, and the `project writers` command that changes them.

### 7. Project registration and resolution

Projects are registered in the database. No file is committed to any project.

- `project register`, run inside the repository, creates the project or adopts an unregistered row
  with the same slug, so audit history is kept. It records two locators: the main worktree path
  (the parent of `git rev-parse --path-format=absolute --git-common-dir`, computed directly, not
  taken from `detect()`), and the normalized `origin` URL unless `--no-remote`.
- **Remote normalization:** strip credentials and a trailing `.git`; turn `git@host:owner/repo`
  into `host/owner/repo`; lowercase the host. Two projects cannot share a normalized remote
  (`UNIQUE`), so deliberate separate clones use `--no-remote`.
- **Resolution order, for every command:**
  1. `--project <slug>` (or `--global` for lesson commands);
  2. the registered `path` locator that is the longest prefix of the working directory. This keeps
     a command run inside a nested repository in its parent project;
  3. a registered `remote` locator that matches the git toplevel's `origin`;
  4. audit commands only: today's slug from the folder name, through `ensure()`, which now
     consults steps 2 and 3 first so a renamed, registered project is not split.
- Lesson commands stop at step 3: an unregistered project gets `project_not_registered`, with the
  hint `chanchi project register`. Outside any repository, lesson commands need `--global`.
- The `resolve_project` hint "projects are created by `chanchi change open`" (`projects.py:84-90`)
  changes to mention `project register`.

### 8. Who writes

- Every write checks the declared actor role against the writer roles of the lesson's scope (the
  origin project, or global for global lessons and for reviewing agnostic lessons). An empty or
  unknown role is refused. `human` as the agent always passes, because a person typing is the
  owner.
- Reporter roles get one line in their role files: "If something went wrong, say so in your
  report; do not record it". The writer role's file gets the "When something went wrong" block from
  the `chanchi-lessons` skill (§9). Both blocks are printed in the skill for copy and paste.
- In stage 3, the hook resolves the actor from the **event**, not from the conversation: Claude
  Code `agent_type` (present for subagents and for sessions started with `--agent`), then the
  role recorded on the run, then `unknown`. This matters because a Claude Code subagent's events
  carry its parent's `session_id`. Where a harness does not report the role, the launcher may
  declare it with `CHANCHI_ROLE=<role>` (`role_source = launcher`), which projects that launch
  roles from fixed command lines can add at no cost. An environment variable can be forged; the
  threat model is a model ignoring its instructions, not an attacker.

### 9. The retrospective

- One skill, `chanchi-lessons`, linked by the existing `chanchi skills link`, with two sections:
  - **Record** (for writer roles, at the end of a conversation or when something fails): fix
    first; list what went wrong; for each item write the cause and the general rule; run
    `lesson similar`; then `lesson repeat` or `lesson add`. If nothing went wrong, record nothing.
  - **Review** (for maintenance runs): `lesson summary`, then `lesson export` in order; for each
    lesson ask whether the cause is a cause or a symptom, whether an existing rule covers it, whether
    the rule holds outside this case, what it costs in context, and where it costs the least (a hook,
    a permission or a CLI check before a role line); which existing rule it replaces; then decide
    with a reason; apply and tag the file with `[lesson #N]`.
- The project's rules (its `AGENTS.md`, `CLAUDE.md` or OpenSpec config) get one line pointing the
  writer role to the skill at the end of each conversation. The owner pastes it; chanchi prints it
  in the skill and the README.
- Stage 3 records whether the retrospective happened: `retro --notes ...` sets `runs.retro_at`
  without closing the run, so lessons recorded later in the same conversation still attach. The
  stop nudge (§10) asks a writer-role run at most once.

### 10. Hooks (stage 3 for the contract and Claude Code; stage 4 for agy and opencode)

**Contract of `chanchi hook check`:**

- **Input:** one JSON object on stdin, already normalized by the adapter, with a version:
  `{"v": 1, "harness", "harness_version", "event", "conversation_id", "parent_conversation_id",
  "actor_role", "role_source", "is_subagent", "cwd", "tool", "command", "model"}`. Unknown or
  missing fields are allowed.
- **Output:** always exit code 0. The decision is JSON on stdout: `{"decision": "allow"|"block",
  "message": "...", "context": "..."}`. Claude Code reads exit code 2 as "block", so chanchi's
  normal exit code 2 on errors (`errors.py:50-51`) must never reach a hook.
- **Fail open:** any internal error, locked database, missing git, unregistered project or schema
  mismatch returns `allow` with a warning written to a log file.
- **No migrations:** `hook check` opens the database without `bootstrap()` (`db.py:251-253`). A
  wrong schema version is an `allow` with a warning. Several panes starting at once never race a
  migration.
- **Fast path:** the adapter calls chanchi only when the shell command contains `chanchi`.
  Everything else is allowed in the adapter, with no Python start-up.
- **Command matching:** split the command on `&&`, `||`, `;` and `|`, tokenize each part with
  `shlex`, and match when a token ends in `chanchi` or `-m chanchi` appears, followed by a guarded
  verb (`lesson add|repeat|modify|review|reopen|apply|retire|decline`, `project writers`). Text
  inside `echo` or a quoted string is not a match. The CLI's own role check (§8) is the real
  barrier; the hook adds the harness-reported role.

**Events:**

- `session-start`: upserts the run on `(agent, conversation_id)` and returns one context line,
  `chanchi run <id> (role <role>)`, on every start source (startup, resume, compact, clear), so
  compaction does not lose it.
- `pre-tool`: blocks a guarded command when the event's actor role is not a writer, or when the
  declared `--as` differs from it.
- `stop`: only for writer-role runs in a registered project, at most once per run
  (`runs.retro_requested_at`), and respecting each harness's loop guard (Claude Code
  `stop_hook_active`, agy `continuation_active`). It asks for the retrospective and does not close
  the run. Opencode gets no stop nudge unless a loop-safe mechanism is verified.

**Install:** `hooks install --agent X [--global]` (global is the default; projects hold no
chanchi files):

- Claude Code: entries in `~/.claude/settings.json` under `hooks.<Event>[]`, recognized by the
  exact command string `chanchi hook check --agent claude`.
- agy: a top-level `"chanchi"` group in `~/.gemini/config/hooks.json`, next to existing groups such
  as `"herdr"`. agy hooks must print a JSON object on every exit path.
- opencode: a standalone `chanchi-hooks.js` in `~/.config/opencode/plugins/` with a header marker.
- Every install is idempotent, writes atomically after a backup, refuses an invalid JSON file, and
  uses the absolute path of the chanchi binary because hooks run with a minimal `PATH`.
  `uninstall` removes only chanchi's entries. `hooks status` shows, per harness, whether it is
  installed and when it last delivered an event.

**Tests:** captured payloads per harness and version in `tests/fixtures/hooks/<agent>/`, covering
an executor started with `--agent` (block), the planner (allow), an executor subagent inside a
planner conversation (block), no role (block), an unregistered project (allow), a non-git directory
(allow), and a newer database (allow). Install and uninstall run against a temporary home that
already holds third-party entries.

### 11. Facts to verify before stage 3 and 4 (delegated to agy)

Each item is checked in the real harness with one case that must pass and one that must fail, and
the command, the version and the result are written down:

1. Claude Code: `agent_type` is present for a main conversation started with `--agent`.
2. Claude Code: `session_id` stays the same across resume and compaction.
3. agy: the hook input field for the conversation id (`conversationId` per the herdr script), the
   field that names the `--agent` role, if any, and whether `SessionStart` output can add context.
4. agy: the argument field name for `run_command` in `PreToolUse`.
5. opencode 2.2.6: which plugin API it uses (V1 `server()` or V2 `setup()`); whether
   `tool.execute.before` blocks by throwing; whether an event carries the agent name; whether the
   role survives `opencode run --agent X` followed by the TUI reopened with `-s <id>`.
6. The installed agy version and the source of each fact. The cached CHANGELOG stops at 1.5.7.

An adapter ships only the events whose facts were observed. A gap goes in the README.

### 12. Worked example

1. In project A, a planner conversation (Claude Code, `opus`, effort `high`) audits session S3.
   The executor claimed tests passed, but they never ran in the right package. The planner records
   the incident and fixes the work (principle 1).
2. The planner checks for an existing rule: `chanchi lesson similar "test output evidence package"`.
   Nothing close.
3. `chanchi lesson add --as planner --author claude:opus:high --conversation <session_id> --json -`
   with the general rule "test output counts as evidence only if it names what ran and what was
   skipped", generality `agnostic`, severity `high`, target `role executor`, linking incident 118
   and session S3. Result: lesson #42, `pending`.
4. Later, a maintenance conversation in project A runs `lesson export --generality agnostic`,
   reviews #42 (a different conversation), and runs `lesson review 42 --decision approve`.
5. It edits project A's executor role, adds the line with `[lesson #42]`, commits, and runs
   `lesson apply 42 --site project --where ".agents/roles/executor.md [lesson #42] @ abc123"`.
6. Stage 2: project B's maintenance run sees #42 in `lesson inbox`, because #42 is agnostic,
   approved and applied once to a project site. It adopts it with `lesson apply 42 --site project`
   in project B.
7. Months later, lesson #57 merges #42 with another rule and lists `replaces 42`. Applying #57 in
   project A retires #42 at project A's site only. Project B's inbox shows #57 as "replaces #42,
   which you applied".
8. `lesson verify` in project A then reports whether the `[lesson #42]` line is still in the file.

### 13. Risks and limits

| Risk | Mitigation |
|---|---|
| Rolling back to a commit before 004 makes every command fail with `schema_too_new` (`db.py:229-230`), including audits | Forward-only, as today. Rollback means restoring `chanchi.db.bak-v3` and losing lessons recorded since. Hooks fail open on `schema_too_new` |
| Word overlap misses the same failure told with different words | The skill tells the writer to read the pending general rules before recording. Embedding search is a non-goal |
| Lessons pile up with no review | `lesson summary` shows pending counts. In stage 3, the session-start line of a writer run mentions pending `high` and `critical` lessons when there are any |
| Role files keep growing | Review prefers zero-context targets; `replaces` and per-site retirement; `lesson verify` reports size per file |
| A stage-1 role is only declared, so it can be wrong | Stated threat model; stage 3 compares the declaration with the harness |
| The method does not detect failures | It depends on someone noticing; incidents and audit verdicts are the usual trigger |

## Goals vs. Non-Goals

### In-Scope Goals

- **Stage 1:** project registration in the database with locators and nested-repository
  resolution; global and per-project writer roles; lessons with the full record, author model and
  effort, links to changes, sessions and incidents; decision states and per-site application;
  duplicate detection; one skill with the record and review sections; the rule lines to paste.
- **Stage 2:** inbox and decline for agnostic lessons across projects; `lesson verify`.
- **Stage 3:** runs; `hook check` with its contract and fixture tests; the Claude Code adapter;
  `retro` tracking and the once-per-run stop nudge.
- **Stage 4:** agy and opencode adapters, each limited to the verified events.

### Out-of-Scope Non-Goals

- chanchi editing any role, skill, prompt or rules file.
- Opening the harness list beyond `taxonomy.ALL_AGENTS`.
- A shared or remote database, or sharing between machines.
- Embedding or semantic search.
- A hard context budget per file (revisit when real lessons show growth).
- A draft queue for reporter roles (they report in text; revisit if writers miss them).
- Importing the 39 existing hand-copied rules as lessons (possible later as a one-off).
- Requiring registration for session audits.
- Scoring models from lessons.

## Alternatives Weighed

- **Project id in a committed file in each project:** rejected: it needs a commit in every project
  and does not scale.
- **Project-level hook installs:** rejected: they write into files that projects usually commit, and
  would contain an absolute path to the chanchi binary. Global install plus database lookup keeps
  projects free of chanchi files.
- **Guard on "is this a subagent?" (the source method's hook):** rejected: roles also run top-level
  with `--agent`.
- **Guard on the conversation's role:** rejected: a Claude Code subagent's events carry its parent's
  conversation id, so an executor subagent would pass as the planner.
- **"No role means a person, so it can write":** rejected: in harnesses that hide the role, every
  agent would pass. Only the `human` agent passes without a writer role.
- **A stop hook that asks every conversation for a retrospective:** rejected: it fires after every
  reply, nags reporter roles, and pushes empty retrospectives.
- **One `status` with apply and retire fields on the lesson:** rejected: it cannot describe a rule
  applied in several projects, or retired in one of them.
- **Agnostic lessons pushed to every inbox on `add`:** rejected: projects would adopt rules nobody
  reviewed, and a new project would inherit the whole backlog.
- **Shipping the source method only, with no registration and no cross-project sharing (the
  zoom-out lens's v1):** partly adopted: stage 1 keeps the source method's core and cuts runs,
  hooks and the inbox. Registration stays in stage 1 because the owner requires a registered
  project before recording, and global writer roles need a scope.
- **Two skills (record and review):** rejected in favor of one skill with two sections.
- **A `rules snippet` command:** rejected: it prints fixed text; the skill and README carry it.
- **Free agent values validated against `models.agent`:** rejected: the code fixes the list in
  `taxonomy.ALL_AGENTS`, and nothing can add another agent today.
- **Auto-adding unknown hook models to the catalog:** rejected: they would enter `recommend`'s
  exploration list.
- **Policy as SQLite `CHECK` constraints:** rejected for anything that may change; SQLite needs a
  table rebuild to alter a `CHECK`.

## Key Decisions & Staging for Next Steps

### Decisions

1. Registration and writer roles live in the database (§3, §7).
2. Resolution goes by the longest registered path first, so nested repositories stay in their
   project (§7).
3. Generality decides where the rule is reviewed; the target names one fix place; sites track each
   place separately (§2, §3, §4).
4. The author's model is raw text with an optional catalog match, and the executor's model comes
   from the linked session (§3). `model_weakness` sends the problem to incidents (§4).
5. Writes check the declared actor role; unknown means no; `human` always passes (§8).
6. The retrospective is a skill and a rule line; tracking and the stop nudge come with hooks (§9).
7. One hook command with a fixed contract: exit 0, fail open, no migrations, fast path, actor from
   the event (§10).

### Staging

| Stage | Migration | Ships | Depends on |
|---|---|---|---|
| 1 | `004_lessons.sql` | registration, writer roles, lessons, sites, replaces, incidents link, events, dedup, `chanchi-lessons` skill | nothing |
| 2 | none | `lesson inbox`, `decline`, `reopen-site`, `verify` | stage 1 |
| 3 | `005_runs.sql` | runs, `hook check`, Claude Code adapter, `retro`, stop nudge | stage 1; §11 facts 1 and 2 |
| 4 | none | agy adapter, then opencode adapter | stage 3; §11 facts 3 to 6 |

Each stage ships with its migration, its regenerated template database (README "Databases and
migrations"), updated `tests/test_skills_content.py` and `skills_link.SUGGESTED_CONFIG_LINE` when
skills change, and the error codes it introduces.
