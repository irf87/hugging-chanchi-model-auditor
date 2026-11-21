# Global Items, Project Items and the Fractal Trust System

- **Author:** Iván R
- **Status:** Proposed
- **Date:** 2026-11-21
- **Revision:** 2 (after audit round 1: three auditors of three families, all `PASS WITH FIXES`;
  consolidation and dissent decisions in [reviews/global-items/round1-consolidation.md](reviews/global-items/round1-consolidation.md))
- **Brief:** [global-items.brief.md](global-items.brief.md). This document is complete without it.

---

## Overview

chanchi makes instruments; users make the music. Phase 1 of the agents MVP gave chanchi its own
agents, a gate and a feature map. This design lets chanchi help the projects that use it:

1. **Global items.** chanchi proposes agent items that hold in any project, builds them only when
   the evidence says they deserve to exist, versions them, and keeps them in the user's `SYNC`
   folder, never in this repository. A mirror exposes them to every harness on the machine.
2. **Adoption.** Each project decides, item by item, what happens to its own copy: replace it with
   the global item, keep a thin wrapper with what is particular to the project, keep it as is, or
   deprecate it.
3. **Project items.** chanchi exposes agents and skills that help a project create its own items
   (`<item>-chanchi-<slug>-<name>`) and its own trust system.
4. **Replication.** An agent reads how a project works today and writes a plan to replicate
   chanchi's model in that project's context: the same pattern at every level (fractal).
5. **Redundant audits.** Every one of these steps is audited by three auditors of different model
   families, accepted when at least two pass, at most three rounds.

### Principles

1. **Users own their results.** `SYNC/` is ignored by git; the database stays outside it.
2. **Global items are available, never imposed.** The mirror makes a global item available to the
   user's harnesses on this machine, so it is visible in every project. It never edits, replaces or
   removes a project's own item: only that project's adoption decision does.
3. **Evidence before promotion.** An item becomes global after repeated, independent use.
4. **One name, one item.** A global item and a project item never share a name, because harnesses
   disagree on which one wins.
5. **chanchi decides and records; agents execute.** chanchi stays a standard-library CLI that never
   launches a harness: it selects, validates and records; the orchestrating agent runs commands.
6. **Diversity over repetition, and fail closed.** Auditors come from different model families
   when available; a family chanchi does not know never counts as a distinct one.

### Non-goals

- Mirroring global rules files (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
  `~/.gemini/GEMINI.md`), hooks, MCP configuration or eval items. They come later.
- Cursor, OpenAI Codex or other harnesses: the design leaves a slot for them, none is added now.
- Syncing the SQLite database through a cloud folder (risk of corruption while open).
- Editing a consumer project without the owner's go-ahead for that project.

---

## Where things live

| What | Where | Committed here? |
|---|---|---|
| chanchi's own items | `agents/`, `skills/` in this repository | yes |
| the user's global items | `SYNC/ITEMS/` | never (`SYNC` is in `.gitignore`) |
| the user's configuration (auditor roster, thresholds) | `SYNC/config/` | never |
| the database (sessions, lessons, audits, scans, decisions) | `CHANCHI_DB`, default `$XDG_DATA_HOME/chanchi/chanchi.db` (`~/.local/share/...`) | never |
| a project's own items | the project's repository | in that project, never here |

### Locating `SYNC`

`SYNC` is resolved in this order: the `CHANCHI_SYNC` environment variable (tests use a temporary
directory); otherwise `<main checkout>/SYNC`, where the main checkout is the parent of
`git rev-parse --path-format=absolute --git-common-dir` for the repository that holds chanchi's
source (`src/chanchi/../..`). Every git worktree of chanchi therefore resolves to the same `SYNC`.
Commands run from a consumer project resolve it the same way, because they import the same
installed chanchi.

- `chanchi sync init` creates `SYNC/` with `config/` and `ITEMS/`; `chanchi sync init --link <dir>`
  makes `SYNC` a symbolic link to `<dir>` (created if missing) and prints the recommendation: point
  `<dir>` at a folder a cloud service synchronizes (Google Drive, iCloud Drive, Dropbox) or at a
  clone of a private git repository. An existing `SYNC` is never replaced: the command fails with
  `link_conflict` and a hint.
- `chanchi sync status` prints the path, whether it is a link, its target, and whether the target
  is reachable (an unmounted volume or a removed folder is reported, not created).
- Without `SYNC`, every command that needs it fails with `missing_prerequisite` and the hint
  `chanchi sync init`, except `chanchi audit`, which falls back to the built-in roster.

```
SYNC/
  config/
    auditors.toml          # auditor roster (optional)
    promotion.toml         # promotion thresholds (optional)
  ITEMS/
    agents/agent-chanchi-global-<name>/AGENT.md, CHANGELOG.md
    skills/skill-chanchi-global-<name>/SKILL.md, CHANGELOG.md, references/
    retired.json           # append-only list of retired or renamed global items
```

### Naming and the reserved slug

Global items are `<item>-chanchi-global-<name>`. `global` is a reserved project slug in every path
that creates or derives a slug: `projects.register` (with or without `--name`), and the slug
derivation used by `change open` and `project relink`. A folder named `global` must be registered
with `--name <other>`; otherwise the command fails with `invalid_value`, `field: "slug"` and that
hint. `chanchi items check` validates `SYNC/ITEMS/`: every directory is
`<kind>-chanchi-global-<name>` under the folder of its kind (`agents/`, `skills/`), its frontmatter
`name` equals the directory, its version is valid and has a changelog section. `AGENTS.md`
(§ Items and Other Projects) states the global form.

### Versions and hashes

- **Version.** An `AGENT.md` frontmatter carries `version: <x.y.z>`; a `SKILL.md` frontmatter
  carries it as `metadata:` followed by `  version: "<x.y.z>"` (the Agent Skills standard allows a
  free-form `metadata` map). `agents_sync` accepts the optional `version` key and does not emit it
  into wrappers except in the generated header.
- **Changelog.** `CHANGELOG.md` has one `## <x.y.z> — <YYYY-MM-DD>` section per version, newest
  first; the current version must have one.
- **Content hash.** SHA-256 over, for each regular file in the item directory sorted by relative
  POSIX path: the path, a NUL byte, the file's bytes, a NUL byte. Excluded: `CHANGELOG.md`, any
  path with a component starting with `.`, cloud placeholders and conflict copies (`*.icloud`,
  names containing `conflicted copy` or `(conflict`). A symlink inside an item is an error
  (`items check` fails). Bytes are hashed as stored; no line-ending normalization.
- **Retirement.** `retired.json` is a JSON list of `{"name", "version", "replaced_by", "date",
  "reason"}` (`replaced_by` is a global item name or `null`); entries are only appended. A retired
  item's directory may stay for history. Effects: `items mirror` removes its entries;
  `items inbox` shows the retirement to every project that adopted or wrapped it, with the
  replacement if any; a retired name may never be published again (`items check` fails on a live
  directory or a new version under a retired name).

### Mirror

`chanchi items mirror` exposes `SYNC/ITEMS/` to the harnesses installed on the machine; `--check`
writes nothing and fails when the mirror is stale; `--remove` deletes only what the mirror made.
It reuses chanchi's existing link code instead of adding a second scheme:

- **Skills** go through `skills_link`, generalized to take a source directory and a name prefix.
  Global skills get exactly the links chanchi's own skills get from `chanchi skills link --global`
  today: an absolute link in `~/.agents/skills/` (read by opencode and agy workspaces), relative
  links to it in `~/.claude/skills/` (Claude Code; also read by opencode) and in
  `~/.gemini/antigravity-cli/skills/` when agy is installed (agy CLI). opencode's native
  `~/.config/opencode/skills/` is not needed while opencode reads `~/.agents/skills/`; adding it is
  one line in the harness adapter if that changes.
- **Agents** are compiled per harness. `agents_sync` is refactored so that rendering returns
  content per harness kind (`claude`, `opencode`, `agy`) and takes the header text as a parameter;
  a target map turns kinds into paths: the repository map (`.claude/agents/<n>.md`, ...) for
  `chanchi agents sync`, and the user map for the mirror (`~/.claude/agents/<n>.md`,
  `~/.config/opencode/agents/<n>.md`, and agy's user agents folder, whose exact layout under
  `~/.gemini/config/agents/` is verified by a live probe before phase 2 is built). Mirrored files
  carry `# generated by chanchi items mirror from SYNC/ITEMS/agents/<n>/AGENT.md; do not edit`.
- **Ownership.** The mirror owns an entry named `*-chanchi-global-*` that is either a symlink whose
  link text starts with the resolved `SYNC/ITEMS/` path (dangling or not) or a file whose
  frontmatter carries the mirror header. Anything else with such a name is a conflict and is never
  overwritten. When `SYNC` is re-pointed or unmounted, `items mirror` and `--remove` still recognize
  and fix the dangling entries by that rule.
- It never links or writes a file the harness rewrites at runtime (for example `~/.claude.json`).
  A harness whose home folder is missing is skipped and reported.

---

## Redundant audits (cross-cutting)

### Concepts

- An **audit** examines one **subject**, identified by a kind (`design`, `item`, `adoption`,
  `replication`, `other`) and a stable reference (a path such as `docs/designs/global-items.md`, a
  global item name, `<project>:<item>`). It may link a chanchi change and a project, both optional.
  The audit records its **author** (`agent:model[:effort]`).
- A **round** (1 to 3) audits the subject at one commit or version. Rounds are numbered within the
  audit, so a fix commit never restarts the count.
- A round has three **seats**. Each seat holds one auditor; an auditor that cannot run is replaced
  in the same seat.

### Procedure

1. **Open.** `chanchi audit open --kind design --ref docs/designs/global-items.md --author
   claude:opus:high [--change <ref>] [--project <slug>]` creates the audit, opens round 1 with
   `--commit <sha>` (or `--version <x.y.z>`), and fills the three seats from the roster. It prints
   the audit id and, per seat, the spec (`harness:model:effort`), the family and the launch command.
2. **Run.** The orchestrator gives each auditor the same brief (request, evidence, subject) in its
   own conversation. Auditors write their reports to a private scratch path; the orchestrator moves
   them into `docs/designs/reviews/<topic>/` only after every seat has voted, so no auditor can read
   another's report.
3. **Vote.** `chanchi audit vote <audit-id> --round 1 --seat <1-3> --verdict
   pass|pass_with_fixes|fail --blocking <n> --major <n> --minor <n> --report <path>`.
4. **Unavailable.** `chanchi audit unavailable <audit-id> --round 1 --seat <n> --reason "<error>"`
   records the failure and fills the seat with the next available roster entry, printing it. If
   the roster has no auditor left, the seat stays empty.
5. **Dissent.** For every finding raised by exactly one auditor, the orchestrator records a decision
   with evidence: `chanchi audit dissent <audit-id> --round 1 --seat <n> --finding "<id: text>"
   --severity blocking|major|minor --decision confirmed|rejected --evidence "<why>"`.
6. **Close.** `chanchi audit close <audit-id> --round 1` computes the outcome:

| Condition (in order) | Outcome |
|---|---|
| fewer than two seats voted | **escalated** — not enough auditors; the human decides |
| at least two `fail` | **rework** — redo the subject; the next round audits it again |
| at least two `pass` and no confirmed lone blocking or major finding | **accepted** — confirmed lone minor findings are fixed and listed, without a new round |
| otherwise | **fix** — apply every confirmed finding; the next round re-checks |
| round 3 ends with any outcome other than accepted | **escalated** — the human decides with the disagreement report |

7. **Next round.** `chanchi audit round <audit-id> --commit <sha>` opens the next round with the
   same seats when those auditors are available; they re-check their own findings and the fixes.

`chanchi audit show <audit-id>` prints every round, seat, vote, dissent and outcome;
`chanchi audit list` lists audits with their last outcome.

### Roster, families and fallback

`SYNC/config/auditors.toml` lists auditors in order of preference. Without `SYNC` or without the
file, chanchi uses the built-in defaults, which are the same list:

```toml
# Auditors in order of preference. chanchi fills three seats with available auditors of
# different model families; if fewer than three families are available it fills the
# remaining seats with the next available auditors and records the round as degraded.
[[auditor]]
harness = "claude"
model = "sonnet"
effort = "medium"

[[auditor]]
harness = "agy"
model = "gemini-4-neon-high"
effort = "high"

[[auditor]]
harness = "opencode"
model = "opencode-go/minimax-m3"

[[auditor]]   # fallback, same family as the second
harness = "agy"
model = "gemini-4-hydrogen-high"
effort = "high"
```

- Each entry resolves to a catalog model `harness:model` (the harness is the catalog's agent). An
  entry that is not in the catalog is an error with the hint
  `chanchi models add --agent <harness> --model <model> --cost <1-3>`.
- **Family** belongs to the model, not the harness: `agy:claude-opus-5-5-high` is Anthropic, like
  `claude:opus`. Migration 005 adds `models.family` and seeds it for the models already in the
  catalog from their names (`claude*`, `opus`, `sonnet`, `haiku`, `fable` → `anthropic`; `gemini*`
  → `google`; `gpt*` → `openai`; `minimax*` → `minimax`; `deepseek*` → `deepseek`; `glm*` →
  `zhipu`; `kimi*` → `moonshot`; `qwen*` → `alibaba`; `grok*` → `xai`; `mimo*` → `xiaomi`; others
  stay unknown). The owner corrects it with `chanchi models set <agent:model> --family <name>`.
- **Fail closed.** A model with an unknown family never counts as a distinct family: a round that
  relies on one is degraded, and `audit open` names the model with the `models set` hint.
- **Available** means: the harness adapter finds the binary on `PATH`, the model is in the catalog
  and active, and the auditor has not been marked unavailable in this audit.
- **Degraded** rounds (fewer than three distinct known families among the seats) are recorded.
- The author's family is recorded but not excluded: with three families available, one auditor
  usually shares the author's family. Statistics can separate those votes later.

### The auditor agent

`agent-chanchi-auditor` (scope `both`, profile `read-only`, audience `global`) audits one subject
against a brief and writes one report: first line `VERDICT: ...`, then a findings table with
severity, place, problem, evidence and fix. It never edits the subject and never reads other
auditors' reports.

### Harness adapters

`src/chanchi/harnesses.py` holds one row per harness: key, binary name, family-independent launch
template (agent flag, model flag, effort or variant, prompt passing), and the user-level folders the
mirror writes. Launch templates verified on the installed CLIs (the phase-1 plan re-runs each once):

| Harness | Headless launch |
|---|---|
| claude | `claude -p --agent <a> --model <m> --effort <e> "<prompt>" < /dev/null` |
| opencode | `opencode run --agent <a> -m <provider/model>[#variant] "<prompt>" < /dev/null` |
| agy | `agy --agent <a> --model <m> --effort <e> -p="<prompt>" < /dev/null` (the model id carries the effort suffix) |

chanchi only checks whether the binary is on `PATH` (`shutil.which`); it never runs a harness.
Adding a harness (Cursor, OpenAI Codex) needs an adapter row, an agent renderer in `agents_sync`
for its frontmatter, its agent key in `taxonomy`, catalog rows with families, and tests; the audit
procedure and the outcome rules do not change.

### Data model (migration `005_audits_and_families.sql`)

The lessons design reserved `005_runs.sql` for its stage 3; that stage is not built, so this design
takes 005 and the lessons stage 3 takes the next free number when it is built (noted in that design).

```sql
ALTER TABLE models ADD COLUMN family TEXT;               -- NULL = unknown; seeded by name patterns

CREATE TABLE audits (
  id           INTEGER PRIMARY KEY,
  subject_kind TEXT NOT NULL,                             -- design | item | adoption | replication | other
  subject_ref  TEXT NOT NULL,
  project_id   INTEGER REFERENCES projects(id),
  change_id    INTEGER REFERENCES changes(id),
  author_model_id INTEGER NOT NULL REFERENCES models(id),
  author_effort   TEXT,
  outcome      TEXT,                                      -- last round's outcome
  opened_at    TEXT NOT NULL,
  closed_at    TEXT
);

CREATE TABLE audit_rounds (
  id          INTEGER PRIMARY KEY,
  audit_id    INTEGER NOT NULL REFERENCES audits(id),
  round       INTEGER NOT NULL CHECK (round BETWEEN 1 AND 3),
  subject_at  TEXT NOT NULL,                              -- commit sha or item version
  degraded    INTEGER NOT NULL DEFAULT 0,
  outcome     TEXT,                                       -- accepted | fix | rework | escalated
  opened_at   TEXT NOT NULL,
  closed_at   TEXT,
  UNIQUE (audit_id, round)
);

CREATE TABLE audit_seats (
  id          INTEGER PRIMARY KEY,
  round_id    INTEGER NOT NULL REFERENCES audit_rounds(id),
  seat        INTEGER NOT NULL CHECK (seat BETWEEN 1 AND 3),
  harness     TEXT NOT NULL,
  model_id    INTEGER NOT NULL REFERENCES models(id),
  effort      TEXT,
  status      TEXT NOT NULL,                              -- assigned | voted | unavailable
  verdict     TEXT,                                       -- pass | pass_with_fixes | fail
  blocking    INTEGER NOT NULL DEFAULT 0,
  major       INTEGER NOT NULL DEFAULT 0,
  minor       INTEGER NOT NULL DEFAULT 0,
  report      TEXT,
  reason      TEXT,                                       -- why unavailable
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX audit_seats_active ON audit_seats (round_id, seat) WHERE status != 'unavailable';

CREATE TABLE audit_dissents (
  id          INTEGER PRIMARY KEY,
  seat_id     INTEGER NOT NULL REFERENCES audit_seats(id),
  finding     TEXT NOT NULL,
  severity    TEXT NOT NULL,                              -- blocking | major | minor
  decision    TEXT NOT NULL,                              -- confirmed | rejected
  evidence    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
```

Enum values are validated in `taxonomy.py`, as in the lessons migration. The template database is
regenerated with the migration. Phases 3 and 4 add migration 006 (below).

### The skill

`skill-chanchi-audit-rounds` tells the orchestrator how to run the procedure: what needs an audit
(everything the orchestrator writes, every global item version, every adoption decision, every
replication plan), how to write one brief for three auditors, how to keep reports private until
all seats voted, how to record votes, unavailability and dissent, and when to stop.
`agent-chanchi-orchestrator` points to it. Until phase 1 is built, the procedure is run by hand
and its rounds are backfilled into the database when the commands exist.

---

## The improvement and promotion pipeline

### B. Capture (in every project)

- **Lessons** stay the record of what went wrong and the rule that would have prevented it. An
  improvement of an item, or a missing item, uses the existing fields: `target_kind: skill` (or
  `role`, `hook`, ...) and `target: "skill herdr"` or `target: "skill herdr (new)"`. No new field.
- **Item inventory.** Projects keep most of their setup knowledge in their own files.
  `chanchi items scan` reads, read-only, the item directories of every registered project
  (`.agents/skills`, `.claude/skills`, `.opencode/skills`, `agents/`, `.claude/agents`,
  `.opencode/agents`, `.agents/agents`, and the agnostic folders the project registers with
  `chanchi project items-dirs --add <path>`), and stores one fingerprint per item. It never copies
  item text into the database and never writes into a project.

### C. Propose (in chanchi, started by the user)

`chanchi items propose` lists candidates, each with its evidence:

- items of the same kind in at least two registered projects that share a name, or that the
  project declares as the same purpose (`description` overlap), or
- agnostic lessons from at least two projects whose `target` names the same item, or
- an existing global item whose adopters keep wrapping it with the same addition.

**Independent uses.** Copies of one upstream are one use, not several: two project copies whose
largest shared block of identical lines covers most of the shorter copy count once (the herdr
copies share a 209-line block vendored from `herdr --skill`). The default promotion threshold is
three independent uses, where a use is an independent project copy or an approved agnostic lesson;
`SYNC/config/promotion.toml` changes it. Text similarity scores are not a criterion: same-purpose
skills score low (0.12 to 0.38 in the consumer projects). A candidate is evidence, never an item.

For the first experiment, the herdr skill is promoted by the owner's decision (2026-11-21) even if
the counted uses are fewer than three; `items propose` records it as owner-promoted.

`agent-chanchi-item-builder` takes a candidate, reads the evidence (the project copies and the
lessons) and writes the global item in `SYNC/ITEMS/`: the shared core, harness agnostic, with no
project-specific rule and no project name. The item goes through a redundant audit (kind `item`).
Accepted, it gets its version and changelog entry and `items mirror` exposes it.

### D. Adopt (in each project, started by the user)

When the user asks a project to "check whether there are global items to adopt",
`skill-chanchi-item-adoption` runs:

1. `chanchi items inbox` lists, for this project: global items with no decision, global items whose
   version changed since the decision, and retirements of items it adopted or wrapped.
2. For each one, the adopting agent compares the global item with the project's similar items
   (from the scan) and proposes one decision:
   - **adopt** — the project's copy is removed and every reference to it in the project (roles,
     rules files, other skills) is updated to the global name;
   - **wrap** — the project keeps `<item>-chanchi-<slug>-<name>` holding only what is particular to
     it; the wrapper starts by telling the agent to load `<item>-chanchi-global-<name>` first and
     to follow it for everything the wrapper does not say; references move to the wrapper's name;
   - **keep** — the project keeps its item, with a reason;
   - **deprecate** — the project's own item is to be removed in a later change; the decision
     records the follow-up and the inbox keeps showing it until a later `adopt`, `wrap` or `keep`.
3. The decision is audited (kind `adoption`), applied in the project with the owner's go-ahead, and
   recorded: `chanchi items decide <global-item> --decision adopt|wrap|keep|deprecate
   --version <x.y.z> [--local <item>] --reason "<why>"`. The record keeps version and hash.

This generalizes stage 2 of the lessons design (inbox, decline, replaces) to items; the lessons
inbox, when built, reuses the same pattern.

### Data model (migration `006_items.sql`, phases 3 and 4)

```sql
CREATE TABLE project_item_dirs (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  path        TEXT NOT NULL,                              -- relative to the project root
  UNIQUE (project_id, path)
);

CREATE TABLE project_items (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  kind        TEXT NOT NULL,                              -- agent | skill | hook | rule
  name        TEXT NOT NULL,
  path        TEXT NOT NULL,                              -- relative to the project root
  sha256      TEXT NOT NULL,
  lines       INTEGER NOT NULL,
  description TEXT,                                       -- frontmatter description only
  scanned_at  TEXT NOT NULL,
  UNIQUE (project_id, path)
);

CREATE TABLE item_decisions (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  global_item TEXT NOT NULL,
  version     TEXT NOT NULL,
  hash        TEXT NOT NULL,
  decision    TEXT NOT NULL,                              -- adopt | wrap | keep | deprecate
  local_item  TEXT,
  reason      TEXT NOT NULL,
  audit_id    INTEGER REFERENCES audits(id),
  decided_at  TEXT NOT NULL
);
```

The latest row per `(project_id, global_item)` is the current decision; earlier rows are history.

### E. Project items (in each project)

An agent source gains `audience: repo|global` (default `repo`). `repo` agents (orchestrator,
executor, researcher) run only inside this repository; `global` agents are also compiled into the
user's harness folders by `chanchi agents link --global`, with the same target map and ownership
rule as the mirror. The first global agents are `agent-chanchi-auditor` and
`agent-chanchi-item-builder`, then `agent-chanchi-replicator`. Inside a project, the item builder
creates `<item>-chanchi-<slug>-<name>` items with the project's layout; the project can run
`chanchi agents sync <project-root>` on its own `agents/` sources.

### F. Replicate (in each project)

`agent-chanchi-replicator` reads a project's rules files, roles, skills, gate, verification and
improvement records, compares them with chanchi's model (agnostic rules, gate, feature map, agents,
redundant audits, lessons), and writes a replication plan adapted to the project: what to add,
keep or change, and in which order. The plan goes through a redundant audit (kind `replication`)
and the owner approves it; the item builder and the project's executor carry it out.

---

## Adopt / Adapt / Avoid

| Decision | Item | Source | Reason |
|---|---|---|---|
| Adopt | Two-out-of-three voting | Triple modular redundancy (IBM Journal of R&D, 1962) | The owner's flight-computer rule; simple and well understood |
| Adopt | Judges from disjoint model families | Verga et al. 2024 (panel of LLM evaluators); Panickssery et al. 2024 (self-preference) | Same-family judges share blind spots |
| Adopt | Content hash and version per adopted item | `vercel-labs/skills` lock file | Tells "edited by hand" from "new version" |
| Adopt | Append-only tombstones for retired items | Claude Code marketplace `renames` | Projects can migrate or drop a retired item safely |
| Adapt | Rule of three ("use before reuse") | H. Vocke, *The Practical Test Pyramid* (martinfowler.com); InnerSource Commons "extensions" | Few projects exist, so a use is an independent copy or a lesson, vendored copies count once, and the threshold is configurable |
| Adapt | N-version diversity | Avizienis; Knight and Leveson 1986; Space Shuttle backup flight system | Diversity by model family; unknown families fail closed; degraded rounds recorded |
| Adapt | Explicit wrapper instead of inheritance | `vercel-labs/skills --rename`; layering in `obra/superpowers` | No skill standard has `extends` |
| Adapt | Round cap | Du et al. 2023 (multi-agent debate saturates by four rounds, measured on reasoning tasks, not audits); the owner's cap of three | Three rounds, then the human |
| Avoid | Pushing items into projects or silent same-name shadowing | Team Topologies (thinnest viable platform); harness precedence conflicts | Projects choose; names never collide |
| Avoid | Copying a process template verbatim | Spotify model post-mortem (J. Lee 2020) | The replicator adapts to context instead |
| Avoid | Syncing SQLite through a cloud folder | SQLite guidance on network and synced filesystems | Corruption risk; the database stays local |

---

## Adoption phases

| Phase | Delivers | Signal that it works |
|---|---|---|
| 1 | Redundant audits: migration 005 (families, audits, rounds, seats, dissents), harness adapters, roster, `chanchi audit`, `agent-chanchi-auditor`, `skill-chanchi-audit-rounds` | This design's rounds, run by hand, are backfilled and `chanchi audit show` reproduces their outcomes; the next design is audited with the commands |
| 2 | `SYNC/` and `ITEMS/`: `sync init/status`, reserved slug, `items check/list`, versions and hashes, `retired.json`, `items mirror` | A test global skill and agent appear in all three harnesses; `--check` catches a hand edit; `--remove` leaves nothing behind |
| 3 | Capture and proposal: migration 006, `items scan`, `project items-dirs`, `items propose`, `agent-chanchi-item-builder` | `skill-chanchi-global-herdr` is built from the consumer copies and accepted by a redundant audit |
| 4 | Adoption: `items inbox/decide`, `skill-chanchi-item-adoption` | Each consumer project records an audited decision for the herdr skill (owner's go-ahead per project) |
| 5 | Project items: `audience`, `agents link --global`, project-side item builder | One consumer project creates one `<item>-chanchi-<slug>-<name>` item through the audit procedure |
| 6 | Replication: `agent-chanchi-replicator` | One consumer project gets an audited, owner-approved replication plan |

Each phase gets its own plan, executed with chanchi's agents and recorded in chanchi.

## Risks

| Risk | Mitigation |
|---|---|
| A cloud provider rewrites or conflicts `SYNC/` files | Items are plain text; hashes reveal edits; conflict copies are excluded from hashes and flagged by `items check`; the database is not there |
| `SYNC` target unmounted or re-pointed | `sync status` reports it; the mirror's ownership rule recognizes dangling entries and fixes them |
| An auditor harness has no credits | Seats are refilled from the roster; the round is recorded as degraded; fewer than two voters escalates |
| Same-family auditors masquerading as diverse | Families belong to models, are seeded, and unknown families fail closed |
| A harness changes its global folders | One adapter row per harness; `items mirror --check` in the verify skill after upgrades |
| Global item visible in a project that has its own copy | Distinct names; the inbox lists the overlap; adoption resolves it |
| Proposal noise | Independent-use threshold; vendored copies count once; a candidate is evidence, never an item |
| Wrapper drift | The adoption audit checks that a wrapper holds only project-specific rules |
| Private project content leaking into global items | The item builder writes no project names; the item audit checks it; `SYNC` never reaches this repository |
| Audit cost | At most nine auditor runs per subject; most subjects close in one or two rounds |

## Verification plan (phases 1 and 2; later phases define their own)

1. Unit tests: roster parsing and catalog resolution; family seeding; seat filling with distinct
   families; fail-closed unknown families; degraded rounds; unavailable seat refill; outcome table
   including the lone-finding rule and fewer than two voters; round cap and escalation; dissent
   records; rounds numbered per audit across commits.
2. Backfill of this design's rounds and `chanchi audit show` matching them.
3. Reserved slug refused by `project register` (with and without `--name`) and by the slug
   derivation of `change open` inside a folder named `global`.
4. `SYNC` resolution from the main checkout, from a worktree, with `CHANCHI_SYNC`, and with
   `sync init --link` on a temporary directory; `git check-ignore SYNC`; an existing `SYNC` is never
   replaced.
5. `items mirror` in a temporary `HOME` for all three harnesses; `--check` after a hand edit;
   `--remove` cleanup including dangling links after re-pointing `SYNC`; a foreign entry with a
   global name is a conflict, never overwritten; content hash ignores excluded files and fails on
   symlinks.
6. One headless run per harness that loads a test global skill through the mirror, using the
   adapter's launch template.
