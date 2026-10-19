# chanchi — Model Auditor Design

**Date:** 2026-10-18
**Status:** Approved in brainstorming, pending written-spec review

## 1. Purpose

A developer runs AI coding work through several agents (`claude`, `agy`, `opencode`) and many models, following an OpenSpec planner → executor workflow. Today there is no record of how well each agent/model/effort performs, so model selection is guesswork.

`chanchi` is a **local-only utility** that:

1. Records planner and executor sessions and the incidents found while orchestrating and auditing them.
2. Converts those audits into numbers.
3. Recommends which `(agent, model, effort)` to use for a given task type and complexity.

It is exposed to agents through **skills** that drive a **CLI** backed by **SQLite**.

### 1.1 Primary user is an agent

Humans interact with `chanchi` through agents, almost never directly. Every interface decision optimises for an agent caller:

- Output is **JSON by default**; `--format text` gives a compact human-readable rendering.
- Errors are structured and **self-correcting**: they name the offending field, list the valid values and give a hint.
- Every enumerated value is discoverable from the CLI itself (`chanchi taxonomy list`).

### 1.2 Workflow being measured

- The **planner** writes the OpenSpec change (proposal, design, specs, tasks) and, in the common case, also **orchestrates and audits** the executors (same session — it holds the planning context). Occasionally a different agent/session orchestrates.
- **Executors** run sessions (S1, S2, …), each pinned to one agent, model and effort and owning a subset of task groups.
- Executors **never rate the planner**. When an executor finds something undefined, blocking, or a design gap, it **stops and hands off** to the orchestrator. That handoff is the signal of a plan defect.
- The orchestrator is therefore the **single writer** of audit data.
- Small changes may skip OpenSpec ("adhoc"); complex changes always use it.

The reference implementation of this workflow (DATEMApp) already produces per-session reports with `status: COMPLETE | STOPPED | BLOCKED`, `stops`, `verification`, `files_changed`, retries named `S1-attempt1`, and a planner audit that classifies each mismatch as an app, plan or executor defect. `chanchi` turns that existing output into data; it does not invent a new process.

### 1.3 Non-goals

- No server, no network, no multi-machine sync. One SQLite file per machine.
- No MCP server (a skill already is the interface; an MCP layer could be added later over the same core).
- No token or monetary cost tracking (only a manual relative cost tier).
- No automatic parsing of agent transcripts or report files — the orchestrating agent reads them and calls the CLI.
- No editing of any project's `openspec/config.yaml` or agent instruction files.

## 2. Technology

- **Python, standard library only** at runtime (`sqlite3`, `argparse`, `json`, `pathlib`, `datetime`, `subprocess` for `git`).
- **Installed with `uv tool install --editable .`**: `uv` provisions its own interpreter (independent of pyenv) and places `chanchi` in `~/.local/bin`, which is on the PATH of non-interactive shells. `--editable` makes the repo checkout the live source.
- Supported platforms: macOS and Linux.
- Dev-only dependency: `pytest`.

Rejected alternatives:

- **Node/TypeScript** — Node is managed by fnm on this machine and is not on the PATH of non-interactive agent shells (the same reason `openspec` must be invoked through `zsh -i -c`); `better-sqlite3` is a native module.
- **Go** — best distribution story, but more code for the same features and a rebuild on every change. Revisit only if `chanchi` must run on machines without `uv`.
- **MCP server** — needs per-agent configuration in three agents and a long-lived stdio process for no gain over a skill + CLI.
- **Bash + sqlite3 CLI** — too brittle for aggregation and validation.

## 3. Architecture

```
hugging-chanchi-model-auditor/
├── pyproject.toml              # console script: chanchi = chanchi.cli:main
├── src/chanchi/
│   ├── cli.py                  # argparse, subcommands, output formatting, error envelope
│   ├── db.py                   # connection, pragmas, bootstrap from template, migrations
│   ├── migrations/001_init.sql # schema + seed (task types, human:human)
│   ├── data/template.db        # committed template database (schema + seed, no operational rows)
│   ├── taxonomy.py             # enums, incident codes, roles, weights, multipliers
│   ├── modelspec.py            # parse "agent:model[:effort]"
│   ├── projects.py             # project detection (git toplevel)
│   ├── record.py               # changes, sessions, incidents, verdicts
│   ├── scoring.py              # per-session and per-change scores, aggregation, recommend
│   └── skills_link.py          # mirror skills into projects via symlinks
├── skills/
│   ├── chanchi-model-selection/SKILL.md
│   └── chanchi-session-audit/
│       ├── SKILL.md
│       └── references/rubric.md
└── tests/
```

Unit boundaries:

| Unit | Does | Depends on |
|---|---|---|
| `taxonomy` | Holds every closed set and every weight. Pure data + validation helpers. | nothing |
| `modelspec` | Parses and formats `agent:model[:effort]`. | `taxonomy` (effort values) |
| `db` | Bootstraps the operational database from the template, opens it, applies pragmas and pending migrations; rebuilds/migrates the template on demand. | `sqlite3`, `data/template.db` |
| `projects` | Resolves the current project from cwd or `--project`. | `git`, `db` |
| `record` | Validates and writes changes, sessions, incidents, verdicts. | `db`, `taxonomy`, `modelspec`, `projects` |
| `scoring` | Reads raw rows and computes scores, stats and recommendations. Never writes. | `db`, `taxonomy` |
| `skills_link` | Creates/removes skill symlinks. No database access. | filesystem |
| `cli` | Parses arguments, calls one unit, renders JSON/text, maps exceptions to exit codes. | all of the above |

### 3.1 Databases: template and operational

There are always two SQLite databases with the same schema:

| | Template | Operational |
|---|---|---|
| Path | `src/chanchi/data/template.db` (resolved via `importlib.resources`, so it works for editable and regular installs) | see location below |
| Content | Schema + seed rows only (task types, `human:human` model). Never operational rows. | Real data |
| In git | **Committed** (a `.gitignore` exception) | **Never committed** (lives outside the repo) |
| Written by | Only `chanchi db migrate --template` | Every recording command |

**Bootstrap:** on any command, if the operational database does not exist, it is created by **copying the template**, then any pending migrations are applied (normally none). The template itself is never opened for writing by normal commands.

**Every migration affects both databases.** Adding a migration means: add `migrations/NNN_<name>.sql`, run `chanchi db migrate --template` to bring the committed template to the new version, and commit both. The operational database picks the migration up automatically on its next command. Tests enforce that the two never drift (see §10).

**Before migrating the operational database**, `chanchi` copies it to `chanchi.db.bak-v<old_version>` next to it, and keeps only the three most recent backups.

Database commands:

```text
chanchi db status                 # paths, versions of template and operational, pending migrations
chanchi db migrate                # apply pending migrations to the operational database (also automatic)
chanchi db migrate --template     # apply pending migrations to the committed template (developer step)
```

#### Operational database location

A single **global** database (cross-project comparison is the point):

1. `$CHANCHI_DB` if set (tests use this).
2. Otherwise `$XDG_DATA_HOME/chanchi/chanchi.db`, defaulting to `~/.local/share/chanchi/chanchi.db`.

The directory is created on first use; the database itself is created from the template (bootstrap above). Pending migrations are applied automatically by every command.

### 3.2 Project detection

`git rev-parse --show-toplevel` from the cwd; the project slug is the toplevel directory's basename, and the absolute path is stored. `--project <slug>` overrides detection. A monorepo with sub-projects (e.g. `cacao-api/`, `cacao-app/`) is one project; use `--tags` to distinguish. Outside a git repository, `--project` is required.

### 3.3 Skills distribution (mirror)

`skills/` in this repo is the single source. Each `SKILL.md` uses the standard frontmatter (`name`, `description`) so the same file serves Claude Code, opencode and agy — no per-agent wrappers.

`chanchi skills link [path]` (default: cwd) creates, for each skill `chanchi-*`:

- `<path>/.agents/skills/<skill>` → **absolute** symlink to `<repo>/skills/<skill>`.
- `<path>/.claude/skills/<skill>` → **relative** symlink to `../../.agents/skills/<skill>` (the pattern already used in `~/.claude/skills`).
- Additionally, if `<path>/.agent/skills` or `<path>/.opencode/skills` already exists, a relative symlink there as well.

`--global` targets `~` instead of a project. The command is idempotent, never overwrites a non-symlink or a symlink pointing elsewhere (it reports a conflict instead), and `chanchi skills unlink [path]` removes only symlinks that resolve into this repo's `skills/`.

On success, `skills link` prints a **suggested line** for the project's `openspec/config.yaml` (it does not edit it), e.g.: *"When assigning sessions use the `chanchi-model-selection` skill; when orchestrating and auditing sessions use the `chanchi-session-audit` skill."*

**Implementation must verify** (via each agent's `--help`/docs, not assumption) which skill directories opencode and agy actually read, and adjust the target list accordingly.

## 4. Taxonomy

All closed sets live in `taxonomy.py`, except task types, which live in a table so they can be extended.

### 4.1 Task types (table `task_types`, seeded)

`ui-component`, `ui-layout-styling`, `api-endpoint`, `business-logic`, `db-schema-migration`, `refactor`, `bugfix`, `tests`, `infra-config-ci`, `docs`, `integration`.

Extended with `chanchi taxonomy add-type <code> --description "..."`. Codes are kebab-case.

### 4.2 Complexity

`low`, `medium`, `high`. Criteria (stated in the rubric so every orchestrator applies them the same way):

- **low** — one layer, ≤ 3 files, no domain ambiguity, mechanical.
- **medium** — 2 layers or 4–10 files, or one non-trivial domain rule.
- **high** — ≥ 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), or meaningful domain ambiguity.

### 4.3 Other enums

| Enum | Values |
|---|---|
| agent | `claude`, `agy`, `opencode` (plus `human` as a planner only) |
| effort | `low`, `medium`, `high`, `xhigh`, `max`, `unknown`; NULL when the agent has no effort concept |
| change kind | `openspec`, `adhoc` |
| reported status | `COMPLETE`, `STOPPED`, `BLOCKED` |
| verdict | `accepted`, `accepted_with_fixes`, `rejected` |
| retry reason | `executor_failure`, `plan_fix`, `human_change`, `env` |
| severity | `low`, `medium`, `high`, `blocking` |
| detected by | `executor_stop`, `planner_audit`, `human`, `post_merge` |
| role | `planner`, `executor`, `human`, `none` |

### 4.4 Incident codes

Each code has a fixed role, except `hallucination`, which requires `--role planner|executor`.

| Code | Role | Meaning |
|---|---|---|
| `plan_gap` | planner | Something was not defined; the executor had to stop. |
| `plan_delegated_decision` | planner | The plan left a decision open and the executor made it. |
| `plan_wrong_expectation` | planner | An expected value, path or baseline in the plan was wrong. |
| `plan_conflict` | planner | The plan contradicts existing code, rules or behaviour. |
| `rule_violation` | executor | Broke a project rule. |
| `scope_drift` | executor | Touched files/groups outside its session, or edited planning artifacts. |
| `improvised_decision` | executor | Decided on its own where the protocol required a stop. |
| `false_claim` | executor | Reported a number or status that did not reproduce on audit. |
| `incomplete_work` | executor | Marked work done that was not done or was wrong. |
| `quality_defect` | executor | Bug, weak test or incorrect implementation despite passing verification. |
| `correct_stop` | executor | **Positive.** Stopped at a real gap instead of improvising. |
| `hallucination` | planner or executor | Invented something that does not exist: file, hook, function, library API, CLI flag, project rule, domain fact. Distinct from `false_claim`, which misreports a *result*. |
| `human_unclear_requirement` | human | The requirement was ambiguous or incomplete at its origin. |
| `human_wrong_requirement` | human | The human asked for the wrong thing and it had to be corrected. |
| `human_scope_addition` | human | The human added new or unrelated work after the change started. |
| `env_issue` | none | Tooling or environment problem (watchman, emulator, CLI). |
| `preexisting_defect` | none | A bug that already existed in the app. |

**Planner vs human test** (in the rubric): *Could the planner have detected this from what it had — the requirement plus the codebase and project rules?* Yes → `plan_*`. No, or the human changed their mind → `human_*`.

## 5. Data model

All timestamps are ISO-8601 UTC text. Foreign keys are enforced.

```sql
CREATE TABLE models (
  id          INTEGER PRIMARY KEY,
  agent       TEXT NOT NULL,              -- claude | agy | opencode | human
  model       TEXT NOT NULL,              -- exactly as launched
  cost_tier   INTEGER NOT NULL CHECK (cost_tier BETWEEN 1 AND 3),  -- 1=$ 2=$$ 3=$$$
  efforts     TEXT,                       -- comma list of supported efforts; NULL = no effort flag
  active      INTEGER NOT NULL DEFAULT 1,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  UNIQUE (agent, model)
);

CREATE TABLE projects (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,
  path        TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE task_types (
  code        TEXT PRIMARY KEY,
  description TEXT NOT NULL
);

CREATE TABLE changes (
  id                    INTEGER PRIMARY KEY,
  project_id            INTEGER NOT NULL REFERENCES projects(id),
  ref                   TEXT NOT NULL,     -- OpenSpec change name or free id
  kind                  TEXT NOT NULL,     -- openspec | adhoc
  planner_model_id      INTEGER NOT NULL REFERENCES models(id),
  planner_effort        TEXT,
  orchestrator_model_id INTEGER NOT NULL REFERENCES models(id),  -- defaults to planner
  orchestrator_effort   TEXT,
  opened_at             TEXT NOT NULL,
  closed_at             TEXT,
  UNIQUE (project_id, ref)
);

CREATE TABLE sessions (
  id                INTEGER PRIMARY KEY,
  change_id         INTEGER NOT NULL REFERENCES changes(id),
  session_ref       TEXT NOT NULL,          -- S1, S2, ...
  attempt           INTEGER NOT NULL DEFAULT 1,
  retry_reason      TEXT,                   -- required when attempt > 1
  executor_model_id INTEGER NOT NULL REFERENCES models(id),
  executor_effort   TEXT,
  task_type         TEXT NOT NULL REFERENCES task_types(code),
  complexity        TEXT NOT NULL,
  tags              TEXT,                   -- comma list; filter only, never a grouping key
  groups            TEXT,                   -- e.g. "8,9,10"
  tasks_total       INTEGER NOT NULL CHECK (tasks_total > 0),
  started_at        TEXT NOT NULL,
  ended_at          TEXT,
  reported_status   TEXT,
  verdict           TEXT,
  audited_at        TEXT,
  notes             TEXT,
  UNIQUE (change_id, session_ref, attempt)
);

CREATE TABLE incidents (
  id           INTEGER PRIMARY KEY,
  change_id    INTEGER NOT NULL REFERENCES changes(id),
  session_id   INTEGER REFERENCES sessions(id),   -- NULL = plan defect found outside a session
  code         TEXT NOT NULL,
  role         TEXT NOT NULL,                     -- derived from code; explicit for hallucination
  severity     TEXT NOT NULL,
  task_ref     TEXT,                              -- e.g. "7.3"
  detected_by  TEXT NOT NULL,
  description  TEXT NOT NULL,
  evidence     TEXT NOT NULL,                     -- command + output, path, quote
  created_at   TEXT NOT NULL,
  voided_at    TEXT,
  void_reason  TEXT
);
```

Rules enforced by `record` (not only by SQL):

- Every enum value is validated against `taxonomy`.
- A model must exist in the catalog before use; unknown models are an error suggesting `chanchi models add`. Models are never created implicitly.
- A role-`executor` incident requires a session. A role-`planner` incident may omit it.
- `hallucination` requires `--role planner|executor`; any other code rejects `--role`.
- Incidents may be added to closed changes (late discoveries use `detected_by = human | post_merge`).
- Nothing is deleted: corrections use `incident void` and `session update`.

## 6. Scoring

**Scores are never stored.** They are computed at query time from raw rows, so changing a weight in `taxonomy.py` re-scores the whole history. Voided incidents are ignored everywhere.

### 6.1 Executor session score (0–100)

```
base     = {accepted: 100, accepted_with_fixes: 70, rejected: 0}[verdict]
penalty  = Σ over role=executor incidents (excluding correct_stop) of
           weight(code) × severity_mult(severity) × (1.5 if detected_by in {human, post_merge} else 1)
credit   = 5 × count(correct_stop)
score    = clamp(base − penalty + credit, 0, 100)
```

Sessions without a verdict are not scored.

| Executor weight | Codes |
|---|---|
| 3 | `false_claim`, `hallucination` |
| 2.5 | `improvised_decision` |
| 2 | `scope_drift`, `incomplete_work` |
| 1.5 | `rule_violation`, `quality_defect` |

Severity multipliers: `low 1`, `medium 2`, `high 3`, `blocking 5`.

### 6.2 Planner change score (0–100)

```
tasks    = Σ tasks_total over the change's sessions (latest attempt per session_ref)
density  = Σ over role=planner incidents of weight(code) × severity_mult(severity)
           × (1.5 if detected_by in {human, post_merge} else 1)
           ÷ max(tasks, 10) × 10                    -- penalty points per 10 tasks
score    = clamp(100 − 5 × density, 0, 100)
```

| Planner weight | Codes |
|---|---|
| 3 | `hallucination` |
| 2.5 | `plan_delegated_decision` |
| 2 | `plan_gap`, `plan_conflict` |
| 1 | `plan_wrong_expectation` |

Only changes with at least one audited session are scored.

### 6.3 Human and neutral incidents

Role `human` and `none` never affect any model score. `chanchi stats --role human` reports them per project, including the share of stops caused by human incidents.

### 6.4 Attempts

An attempt counts as an executor failure only when the *next* attempt of the same `session_ref` has `retry_reason = executor_failure`. Attempts superseded for `plan_fix`, `human_change` or `env` are excluded from executor attempt metrics.

### 6.5 Aggregation

Grouping key: `(agent, model, effort) × (task_type, complexity)`. A NULL effort is its own group (rendered `none`), distinct from `unknown`.

- **Smoothed score:** `(n × mean + 3 × prior) ÷ (n + 3)`, where `prior` is the mean session score of all models for that `(task_type, complexity)`, falling back to the global mean, and to `70` with no data at all.
- **Confidence:** `n < 3` → `insufficient`, `3 ≤ n < 10` → `low`, `n ≥ 10` → `ok`.
- **Reported metrics alongside the score:** `n`, clean-session rate (verdict `accepted` and no executor incident of severity ≥ medium), first-attempt acceptance rate, honesty flags per session (`false_claim` + executor `hallucination`), mean attempts, mean duration, top three incident codes.
- **Honesty red flag:** honesty flags per session > 0.2.

Planner aggregation uses the same smoothing over change scores, grouped by `(agent, model, effort)`.

### 6.6 Recommendation

```
chanchi recommend --task-type <code> --complexity <level> --available "<spec>,<spec>,..."
```

1. Candidates are exactly the `--available` specs (the human/planner states what is available; never assumed). Unknown specs are an error.
2. For each candidate, find data at the first level that has `n ≥ 3`: (task_type, complexity) → (task_type, any) → (any, complexity) → (any, any). The output states the level used.
3. Rank by smoothed score. Among candidates with confidence `low` or `ok` and no honesty red flag, the **recommendation** is the cheapest (lowest `cost_tier`) whose smoothed score is within 5 points of the best.
4. If no candidate reaches confidence `low` at any level, the output says so explicitly (`"recommendation": null`, reason `insufficient_data`) and still lists whatever data exists. The planner then chooses by judgement, and that choice becomes data.

The recommendation is an input, not an order: the selection skill requires the planner to write, in the session protocol, what `chanchi` recommended, what it chose, and why if it deviated.

## 7. CLI

Model specs: `agent:model[:effort]`. The agent is the text before the first `:`. The last `:`-segment is the effort **only if it is a valid effort value**; otherwise it is part of the model (so `opencode:openrouter/qwen/qwen3-coder:free` parses as model `openrouter/qwen/qwen3-coder:free`, no effort). The planner/orchestrator may be `human` (shorthand for `human:human`, a catalog row seeded by the initial migration) for adhoc changes the human instructed directly; `human` is rejected as an executor.

Every command accepts `--format json|text` (default `json`) and `--project <slug>`.

```text
# Catalog & setup
chanchi models add --agent <a> --model <m> --cost <1-3> [--efforts low,medium,high] [--notes ...]
chanchi models list [--all]
chanchi models set <agent:model> [--cost N] [--active 0|1] [--efforts ...] [--notes ...]
chanchi taxonomy list                          # every enum, code, role, weight
chanchi taxonomy add-type <code> --description "..."
chanchi skills link [path] [--global]
chanchi skills unlink [path] [--global]

# Recording
chanchi change open <ref> --kind openspec|adhoc --planner <spec> [--orchestrator <spec>]
chanchi change close <ref>
chanchi session start <ref> <session> --executor <spec> --task-type <code> --complexity <level>
        --tasks <n> [--groups 8,9,10] [--tags a,b] [--retry-reason <reason>]
chanchi session report <ref> <session> --status COMPLETE|STOPPED|BLOCKED
chanchi session audit <ref> <session> --verdict <verdict> [--notes ...]
chanchi session update <ref> <session> [--attempt N]   # --attempt selects, never changes, the attempt
        [--task-type ...] [--complexity ...] [--tags ...] [--tasks N] [--notes ...]
chanchi incident add <ref> [--session <session>] [--attempt N] --code <code> --severity <s>
        --detected-by <d> --desc "..." --evidence "..." [--task 7.3] [--role planner|executor]
chanchi incident void <id> --reason "..."

# Querying
chanchi recommend --task-type <code> --complexity <level> --available "<spec>,..."
chanchi stats [--role executor|planner|human] [--by model|task-type|project] [--since YYYY-MM-DD]
chanchi show <ref>                             # change timeline: sessions, incidents, scores
chanchi scoring explain                        # current weights and formulas
```

Behaviour details:

- `session start` on an existing `(ref, session)` creates the next attempt and requires `--retry-reason`.
- `session report`, `session audit`, `session update` and `incident add --session` target the latest attempt unless `--attempt` is given.
- `session audit` requires a prior `session report`.
- `--orchestrator` defaults to `--planner`.

### 7.1 Output and errors

- Success: a JSON object on stdout (`{"ok": true, ...}`), or text with `--format text`.
- Failure: exit code `2` for validation errors, `1` for internal errors, with JSON on stderr:

```json
{"ok": false, "error": {"code": "invalid_value", "field": "complexity",
  "message": "complexity must be one of the listed values",
  "valid_values": ["low", "medium", "high"],
  "hint": "run `chanchi taxonomy list` to see every enum"}}
```

Error codes: `invalid_value`, `unknown_model`, `unknown_change`, `unknown_session`, `duplicate`, `missing_prerequisite`, `project_not_detected`, `link_conflict`, `schema_too_new`, `internal`.

## 8. Skills

Both skills are written in English, are agent-agnostic, and assume only a shell.

### 8.1 `chanchi-model-selection` — used during propose

1. Take the list of available `agent:model:effort` from the human's prompt. Never assume availability.
2. Ensure each available model is in the catalog; if not, ask the human for its cost tier and run `models add`.
3. For each planned session, pick `task_type` and `complexity` using the rubric criteria.
4. Run `chanchi recommend` per session.
5. In the session protocol table, record the recommendation, the choice, and the reason for any deviation.
6. Run `chanchi change open` with its own identity (effort `unknown` if it does not know it).

Also covers catalog maintenance (`models list/set`, `taxonomy add-type`) when the human asks for it.

### 8.2 `chanchi-session-audit` — used during apply/orchestration

1. Before launching a session: `session start`.
2. When the report or handoff arrives: `session report --status`.
3. Classify every stop (one stop can yield two incidents): real plan gap → `plan_gap` (planner) **and** `correct_stop` (executor); caused by the human → `human_*`; environment → `env_issue`.
4. Audit: re-run verification (a non-reproducing number → `false_claim`); check the diff scope (`scope_drift`); check project rules (`rule_violation`); "choices the plan left open" → `plan_delegated_decision`, plus `improvised_decision` when the protocol required a stop.
5. `session audit --verdict`.
6. At archive: `change close`, then `chanchi show <ref>` as the summary for the human.

`references/rubric.md` holds: complexity criteria, the planner-vs-human test, a decision table from observation to incident code, severity guidance, and the rules: every incident carries evidence; one incident per distinct fault, not per symptom; no evidence, no incident.

## 9. Robustness

- Pragmas on every connection: `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`.
- Migrations: numbered SQL files applied in one transaction each, tracked by `PRAGMA user_version`, identical for template and operational databases.
- If the operational database reports a `user_version` higher than the latest known migration (a newer `chanchi` wrote it), every command refuses to run with `error.code = schema_too_new`.
- Each command runs in a single transaction; a validation failure leaves the database unchanged.

## 10. Testing

- **Unit:** scoring formulas against fixed fixtures (including clamping, smoothing, fallback levels, cost-aware ranking, honesty red flag, attempt exclusion), model spec parsing (including `:free`-style model ids), taxonomy validation.
- **Integration:** the CLI run as a subprocess against a temp database (`CHANCHI_DB` in `tmp_path`) through the full flow: catalog → change open → sessions → report → incidents → audit → close → stats → recommend → show. Error envelope and exit codes are asserted.
- **Scenario:** a fixture embedded in the test suite (it never reads the DATEMApp repository) replaying DATEMApp's `clinical-summary-doctor-addressee-and-polish` change (S1–S10 on `agy` with `gemini-4-argon-high` and `gemini-3.8-flash-*`) plus synthetic incidents; `recommend` must produce the expected ranking.
- **Skills link:** in a temp directory — absolute vs relative targets, idempotency, conflict reporting, `unlink` touching only its own symlinks, optional `.agent`/`.opencode` targets.
- **Template integrity:** the committed `template.db` has `user_version` equal to the latest migration number; its schema (`sqlite_master` minus internal tables) equals the schema produced by applying every migration to an empty database; its seed rows match; and it contains zero rows in `projects`, `changes`, `sessions` and `incidents`. This test is what forces every migration to update the template.
- **Bootstrap:** a missing operational database is created from the template; an outdated one is backed up and migrated; a too-new one is refused.
- **Skills:** every `skills/*/SKILL.md` has valid frontmatter with `name` matching its directory and a non-empty `description`.

## 11. Delivery

- The project is built by subagents (Sonnet or Haiku) orchestrated and audited by the planning session.
- All code, docs, skills and commit messages are in English.
