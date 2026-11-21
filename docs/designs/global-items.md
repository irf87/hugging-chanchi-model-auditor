# Global Items, Project Items and the Fractal Trust System

- **Author:** Iván R
- **Status:** Proposed
- **Date:** 2026-11-21
- **Revision:** 1
- **Brief:** [global-items.brief.md](global-items.brief.md). This document is complete without it.

---

## Overview

chanchi makes instruments; users make the music. Phase 1 of the agents MVP gave chanchi its own
agents, a gate and a feature map. This design lets chanchi help the projects that use it:

1. **Global items.** chanchi proposes agent items that hold in any project, builds them only when
   the evidence says they deserve to exist, versions them, and keeps them in the user's `SYNC`
   folder, never in this repository. A mirror exposes them to every harness on the machine.
2. **Adoption.** Each project decides, item by item, to adopt a global item, wrap it with what is
   particular to the project, decline it, or deprecate its own copy.
3. **Project items.** chanchi exposes agents and skills that help a project create its own items
   (`<item>-chanchi-<slug>-<name>`) and its own trust system.
4. **Replication.** An agent reads how a project works today and writes a plan to replicate
   chanchi's model in that project's context: the same pattern at every level (fractal).
5. **Redundant audits.** Every one of these steps is audited by three auditors of different model
   families, accepted by a majority of two, at most three rounds.

### Principles

1. **Users own their results.** `SYNC/` is ignored by git; the database stays in the user's home.
2. **Proposed, never pushed.** No global item reaches a project unless that project decides so.
3. **Evidence before promotion.** An item becomes global after repeated, independent use.
4. **One name, one item.** A global item and a project item never share a name, because harnesses
   disagree on which one wins.
5. **chanchi decides and records; agents execute.** chanchi stays a standard-library CLI that never
   launches a harness: it selects, validates and records; the orchestrating agent runs commands.
6. **Diversity over repetition.** Auditors come from different model families when available.

### Non-goals

- Mirroring global rules files (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
  `~/.gemini/GEMINI.md`), hooks or MCP configuration. They are runtime-sensitive and come later.
- Cursor, OpenAI Codex or other harnesses: the design leaves a slot for them (harness adapters),
  but none is added now.
- Syncing the SQLite database through a cloud folder (risk of corruption while open).
- Editing a consumer project without the owner's go-ahead for that project.

---

## Where things live

| What | Where | Committed here? |
|---|---|---|
| chanchi's own items | `agents/`, `skills/` in this repository | yes |
| the user's global items | `SYNC/ITEMS/` | never (`SYNC` is in `.gitignore`) |
| the user's configuration (auditor roster) | `SYNC/config/` | never |
| the database (sessions, lessons, audits, adoptions) | `~/.local/share/chanchi/chanchi.db` (`CHANCHI_DB`) | never |
| a project's own items | the project's repository | in that project, never here |

`SYNC/` sits at the root of this repository. `CHANCHI_SYNC` overrides its location (tests use a
temporary directory). `chanchi sync init` creates it; `chanchi sync init --link <dir>` makes it a
symbolic link to `<dir>` instead, and the command prints the recommendation: point `<dir>` at a
folder that a cloud service synchronizes (Google Drive, iCloud Drive, Dropbox) or at a clone of a
private git repository. It never creates or touches files inside a cloud provider's folder except
through that link. `chanchi sync status` reports the path, whether it is a link, and its target.

```
SYNC/
  config/
    auditors.toml          # the user's auditor roster (optional; defaults apply without it)
  ITEMS/
    agents/agent-chanchi-global-<name>/AGENT.md, CHANGELOG.md
    skills/skill-chanchi-global-<name>/SKILL.md, CHANGELOG.md, references/
    evals/eval-chanchi-global-<name>/
    retired.json           # append-only list of retired or renamed global items
```

### Naming

`global` becomes a reserved project slug: `chanchi project register --name global` fails with
`invalid_value`. Global items are `<item>-chanchi-global-<name>`. `tests/test_items.py` keeps
checking this repository; `chanchi items check` applies the same rule to `SYNC/ITEMS/` (every
directory there must be `<item>-chanchi-global-<name>` under the folder of its kind).

### Versions

- Each global item carries a semantic version: `version: <x.y.z>` in an `AGENT.md` frontmatter,
  and `metadata:` / `  version: "<x.y.z>"` in a `SKILL.md` frontmatter (the Agent Skills standard
  puts versions in `metadata`).
- `CHANGELOG.md` has one `## <x.y.z> — <date>` section per version, newest first; the current
  version must have a section.
- chanchi computes a **content hash**: SHA-256 over the item directory's files, sorted by relative
  path, excluding `CHANGELOG.md`. Adoption records store version and hash, so a project can tell
  "same version, edited by hand" from "new version".
- `retired.json` is a JSON list of `{"name", "version", "replaced_by", "date", "reason"}`;
  `replaced_by` is an item name or `null`. Entries are only appended.

### Mirror

`chanchi items mirror` exposes `SYNC/ITEMS/` to the harnesses installed on the machine; `--check`
writes nothing and fails when the mirror is stale; `--remove` deletes only what the mirror made.

| Kind | Claude Code | opencode | agy |
|---|---|---|---|
| skills | symlink `~/.claude/skills/<n>` | reads `~/.agents/skills` and `~/.claude/skills` (symlink `~/.agents/skills/<n>`) | symlink `~/.gemini/config/skills/<n>` |
| agents | generated `~/.claude/agents/<n>.md` | generated `~/.config/opencode/agents/<n>.md` | generated in `~/.gemini/config/agents/` (layout verified by the phase-2 plan) |

- Skills are symlinks into `SYNC/ITEMS/skills/`, so an edit or a sync from another machine is
  visible at once. Agents are compiled by `agents_sync.render` (the same generator as chanchi's own
  agents) because each harness needs its own frontmatter; generated files carry the header
  `# generated by chanchi items mirror from SYNC/ITEMS/agents/<n>/AGENT.md; do not edit`.
- The mirror only creates, updates or removes entries named `*-chanchi-global-*` that it owns
  (a symlink into `SYNC/ITEMS/`, or a file with its header). Anything else is a conflict and is
  never overwritten. It never links a file the harness rewrites at runtime (for example
  `~/.claude.json`).
- A harness that is not installed (its home directory is missing) is skipped and reported.

---

## Redundant audits (cross-cutting)

### Procedure

An **audit** examines one subject (a design at a commit, an item version, an adoption decision, a
replication plan). It runs in **rounds**, at most three.

1. **Select.** `chanchi audit open <change-ref> --subject "<what @ commit>"` opens round 1 and
   selects three auditors from the roster (below). It prints, per auditor, the spec
   (`harness:model:effort`), the family, and the headless launch command from the harness adapter.
2. **Run.** The orchestrator gives each auditor the same brief (the request, the evidence, the
   subject) in its own conversation and with no access to the other auditors' reports.
3. **Record.** Each result is a vote:
   `chanchi audit vote <change-ref> --round 1 --auditor <spec> --verdict pass|pass_with_fixes|fail --blocking <n> --major <n> --minor <n> --report <path>`.
   An auditor that cannot run (no credits, provider error, not installed) is recorded with
   `chanchi audit unavailable <change-ref> --round 1 --auditor <spec> --reason "<error>"`, which
   prints the replacement chosen from the roster.
4. **Decide.** `chanchi audit close <change-ref> --round 1` computes the outcome from the votes:

| Votes | Outcome |
|---|---|
| at least two `pass` | **accepted** — the audit ends |
| at least two non-`fail`, fewer than two `pass` | **fix** — apply the fixes, then the next round re-checks |
| at least two `fail` | **rework** — redo the subject, then the next round audits it again |
| any outcome other than accepted in round 3 | **escalated** — the human decides with the disagreement report |

5. **Dissent.** Before closing a round, the orchestrator lists every finding raised by exactly one
   auditor and marks it `confirmed` or `rejected` with evidence (`chanchi audit dissent ...`). A
   confirmed lone finding is also a fix. This is where a disagreement teaches something: why did
   two auditors miss it?
6. **Next round.** It uses the same auditors when they are available (they re-check their own
   findings) and the same brief plus the fixes.

`chanchi audit show <change-ref>` prints every round, vote, dissent and outcome.

### Roster and fallback

`SYNC/config/auditors.toml` lists auditors in order of preference. Without the file, chanchi uses
built-in defaults (the same list as the example).

```toml
# Auditors in order of preference. chanchi picks the first three that are available and
# belong to different model families; if fewer than three families are available, it fills
# the round with the next available auditors and records the round as degraded.
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

[[auditor]]   # fallback
harness = "agy"
model = "gemini-4-hydrogen-high"
effort = "high"
```

- **Family** belongs to the model, not the harness: `agy:claude-opus-5-5-high` is Anthropic, like
  `claude:opus`. Migration 005 adds `models.family`; the owner sets it with
  `chanchi models set <agent:model> --family <name>` and an auditor whose family is unknown counts
  as its own family but is reported.
- **Available** means: the harness adapter says the binary is installed, the model is in the
  catalog and active, and the auditor has not been marked unavailable in this audit.
- **Degraded** rounds (fewer than three families) are recorded, so `chanchi audit show` and later
  statistics can tell them apart.

### Harness adapters

`src/chanchi/harnesses.py` holds one row per harness: key, the binary name, the headless command
template (agent flag, model flag, effort flag, how the prompt is passed), and the global item
locations used by the mirror. Today: `claude`, `opencode`, `agy`. Adding Cursor or OpenAI Codex
means adding a row and its tests; the audit procedure and the mirror do not change. chanchi only
checks whether the binary exists on `PATH` (`shutil.which`); it never runs a harness.

Verified headless forms: `claude -p --agent <a> --model <m> "<prompt>"`,
`opencode run --agent <a> -m <provider/model> "<prompt>"`,
`agy --agent <a> --model <m> --effort <e> -p="<prompt>"`.

### Data model (migration `005_audits_and_families.sql`)

```sql
ALTER TABLE models ADD COLUMN family TEXT;            -- NULL = unknown

CREATE TABLE audit_rounds (
  id          INTEGER PRIMARY KEY,
  change_id   INTEGER NOT NULL REFERENCES changes(id),
  subject     TEXT NOT NULL,
  round       INTEGER NOT NULL CHECK (round BETWEEN 1 AND 3),
  degraded    INTEGER NOT NULL DEFAULT 0,
  outcome     TEXT,                                    -- accepted | fix | rework | escalated
  opened_at   TEXT NOT NULL,
  closed_at   TEXT,
  UNIQUE (change_id, subject, round)
);

CREATE TABLE audit_votes (
  id          INTEGER PRIMARY KEY,
  round_id    INTEGER NOT NULL REFERENCES audit_rounds(id),
  harness     TEXT NOT NULL,
  model_id    INTEGER NOT NULL REFERENCES models(id),
  effort      TEXT,
  verdict     TEXT NOT NULL,                           -- pass | pass_with_fixes | fail | unavailable
  blocking    INTEGER NOT NULL DEFAULT 0,
  major       INTEGER NOT NULL DEFAULT 0,
  minor       INTEGER NOT NULL DEFAULT 0,
  report      TEXT,
  reason      TEXT,                                    -- for unavailable
  created_at  TEXT NOT NULL,
  UNIQUE (round_id, harness, model_id)
);

CREATE TABLE audit_dissents (
  id          INTEGER PRIMARY KEY,
  round_id    INTEGER NOT NULL REFERENCES audit_rounds(id),
  vote_id     INTEGER NOT NULL REFERENCES audit_votes(id),
  finding     TEXT NOT NULL,
  decision    TEXT NOT NULL,                           -- confirmed | rejected
  evidence    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
```

Enum values are validated in `taxonomy.py`, as in the lessons migration. The template database is
regenerated with the migration.

### The skill

`skill-chanchi-audit-rounds` tells the orchestrator how to run the procedure: when an audit is
required (everything the orchestrator writes, every global item version, every adoption decision,
every replication plan), how to write one brief for three auditors, how to record votes,
unavailability and dissent, and when to stop. `AGENTS.md` keeps the one-paragraph rule.

---

## The improvement and promotion pipeline

### B. Capture (in every project)

- **Lessons** stay the record of what went wrong and the rule that would have prevented it. A
  lesson gains an optional `item` field: the item it improves, or the name of an item that is
  missing (`"item": "skill herdr (new)"`). The writer role records it as today.
- **Item inventory.** Projects keep most of their setup knowledge in their own files, not in
  chanchi. `chanchi items scan` reads, read-only, the item directories of every registered project
  (`.agents/skills`, `.claude/skills`, `.opencode/skills`, `agents/`, `.claude/agents`,
  `.opencode/agents`, `.agents/agents`, and the agnostic folders a project declares) and stores one
  fingerprint per item: project, kind, name, path, SHA-256, line count, scan time. It never copies
  content into the database and never writes into a project. Text similarity reuses `dedup.py`.

### C. Propose (in chanchi, started by the user)

`chanchi items propose` lists candidates for new or improved global items, each with its
evidence:

- the same kind of item in at least two registered projects, with text similarity above the
  threshold (same name or same purpose), or
- agnostic lessons from at least two projects that name the same item, or
- an existing global item whose adopters keep wrapping it with the same addition.

The default promotion threshold is **three independent uses** (an item copy in a project or an
approved agnostic lesson each count as one use), adapted from the "rule of three"; the user can
change it in `SYNC/config/`. A candidate is evidence, not a decision.

`agent-chanchi-item-builder` takes a candidate, reads the evidence (the project copies and the
lessons), and writes the global item in `SYNC/ITEMS/`: the shared core, harness agnostic, with no
project-specific rule and no project name. The item goes through a redundant audit. Accepted, it
gets version `1.0.0` (or the next version) and a changelog entry; `chanchi items mirror` exposes
it. Rejected after three rounds, it goes to the owner.

### D. Adopt (in each project, started by the user)

When the user asks a project to "check whether there are global items to adopt",
`skill-chanchi-item-adoption` runs:

1. `chanchi items inbox` lists the global items this project has no decision for, and those whose
   version changed since its decision.
2. For each one, the adopting agent compares the global item with the project's similar items
   (from the scan) and proposes one decision:
   - **adopt** — the project's copy is removed; the global item (mirrored) is used;
   - **wrap** — the project keeps `<item>-chanchi-<slug>-<name>` holding only what is particular
     to it, and the wrapper starts by telling the agent to load `<item>-chanchi-global-<name>`
     first and to follow it for everything the wrapper does not say;
   - **decline** — with a reason; the project keeps its item;
   - **deprecate** — the project's item is marked for removal in a later change.
3. The decision is audited (redundant audit), applied in the project with the owner's go-ahead,
   and recorded: `chanchi items decide <global-item> --decision adopt|wrap|decline|deprecate
   --version <x.y.z> [--local <item>] --reason "<why>"`. The record keeps version and hash.

This generalizes stage 2 of the lessons design (inbox, decline, replaces) to items. The lessons
inbox, when it is built, reuses the same pattern.

### E. Project items (in each project)

chanchi exposes some agents and skills to every project. An agent source gains
`audience: repo|global` (`repo` is the default): `repo` agents (orchestrator, executor, researcher)
run only inside this repository; `global` agents are also mirrored to the user's harness folders
by `chanchi agents link --global`. The first global agents are `agent-chanchi-item-builder` and,
in phase 6, `agent-chanchi-replicator`. Inside a project, the item builder creates
`<item>-chanchi-<slug>-<name>` items with the project's layout, and the project can run
`chanchi agents sync <project-root>` on its own `agents/` sources.

### F. Replicate (in each project)

`agent-chanchi-replicator` reads a project's rules files, roles, skills, gate, verification and
improvement records, compares them with chanchi's model (agnostic rules, gate, feature map, agents,
redundant audits, lessons), and writes a replication plan adapted to the project: what to add,
what to keep, what to change, in which order. The plan goes through a redundant audit and the
owner approves it; the item builder and the project's executor carry it out.

---

## Adopt / Adapt / Avoid

| Decision | Item | Source | Reason |
|---|---|---|---|
| Adopt | Two-out-of-three voting | Triple modular redundancy (IBM Journal, 1962) | The owner's flight-computer rule; simple and well understood |
| Adopt | Judges from disjoint model families | Verga et al. 2024 (panel of LLM evaluators); Panickssery et al. 2024 (self-preference) | Same-family judges share blind spots |
| Adopt | Content hash and version per adopted item | `vercel-labs/skills` lock file | Tells "edited by hand" from "new version" |
| Adopt | Append-only tombstones for retired items | Claude Code marketplace `renames` | Projects can migrate or drop a retired item safely |
| Adapt | Rule of three | Fowler; InnerSource "extensions" | Few projects exist, so a use is a copy or a lesson, and the threshold is configurable |
| Adapt | N-version diversity | Avizienis; Knight and Leveson 1986; Space Shuttle backup flight system | Diversity by model family, degraded rounds recorded when it is not available |
| Adapt | Explicit wrapper instead of inheritance | `vercel-labs/skills --rename`; layering in `obra/superpowers` | No skill standard has `extends` |
| Adapt | Round cap | Du et al. 2023 (debate saturates by four rounds); the owner's cap of three | Three rounds, then the human |
| Avoid | Pushing items into projects or silent same-name shadowing | Team Topologies (thinnest viable platform); harness precedence conflicts | Projects choose; names never collide |
| Avoid | Copying a process template verbatim | Spotify model post-mortem (J. Lee 2020) | The replicator adapts to context instead |
| Avoid | Syncing SQLite through a cloud folder | SQLite guidance on network and synced filesystems | Corruption risk; the database stays local |

---

## Adoption phases

| Phase | Delivers | Signal that it works |
|---|---|---|
| 1 | Redundant audits: migration 005, harness adapters, roster, `chanchi audit`, `skill-chanchi-audit-rounds` | This design's own audit is recorded with `chanchi audit` and closes within three rounds |
| 2 | `SYNC/` and `ITEMS/`: `sync init/status`, reserved slug, `items check/list`, versions and hashes, `items mirror` | A test global skill appears in all three harnesses and `items mirror --remove` leaves nothing behind |
| 3 | Capture and proposal: lesson `item` field, `items scan`, `items propose`, `agent-chanchi-item-builder` | `skill-chanchi-global-herdr` is built from the consumer copies and accepted by a redundant audit |
| 4 | Adoption: `items inbox/decide`, `skill-chanchi-item-adoption` | Each consumer project records a decision for the herdr skill (owner's go-ahead per project) |
| 5 | Project items: `audience`, `agents link --global`, project-side item builder | One consumer project creates one `<item>-chanchi-<slug>-<name>` item through the audit procedure |
| 6 | Replication: `agent-chanchi-replicator` | One consumer project gets an audited, owner-approved replication plan |

Each phase gets its own plan, executed with chanchi's agents and recorded in chanchi.

## Risks

| Risk | Mitigation |
|---|---|
| A cloud provider rewrites or conflicts `SYNC/` files | Items are plain text; versions and hashes reveal edits; the database is not there |
| An auditor harness has no credits | Fallback through the roster; the round is recorded as degraded |
| A harness changes its global folders | One adapter row per harness; `items mirror --check` in the verify skill after upgrades |
| Proposal noise | Threshold of three uses; a candidate is evidence, never an automatic item |
| Wrapper drift (project wrapper repeats global content) | The adoption audit checks that a wrapper only holds project-specific rules |
| Private project content leaking into global items | The item builder writes no project names; the global item audit checks it; `SYNC` never reaches this repository |
| Audit cost | At most nine auditor runs per subject; most subjects close in one or two rounds |

## Verification plan (phase 1 and 2; later phases define their own)

1. Unit tests: roster parsing, family-distinct selection, fallback and degraded rounds, outcome
   table, dissent records, round cap.
2. `chanchi audit` end to end on a scratch database, through a real three-auditor audit of this
   design.
3. `chanchi sync init --link` on a temporary directory; `SYNC` ignored by git (`git check-ignore`).
4. `items mirror` in a temporary `HOME` for all three harnesses, `--check` after a hand edit,
   `--remove` cleanup; a foreign entry with a global name is a conflict, never overwritten.
5. One headless run per harness that loads a test global skill through the mirror.
