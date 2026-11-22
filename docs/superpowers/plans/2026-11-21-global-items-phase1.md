# Global Items — Phase 1 (Redundant Audits) Implementation Plan

- **Revision:** 2 (after audit round 1:
  [round1-consolidation.md](../../designs/reviews/global-items-phase1-plan/round1-consolidation.md))

> **For agentic workers:** each session below is one brief for `agent-chanchi-executor`. Steps use
> checkbox (`- [ ]`) syntax. Write the failing test first, then the code.

**Goal:** Ship phase 1 of `docs/designs/global-items.md` (Revision 4): migration 005 (model
families, audits, rounds, seats, dissents), harness adapters, the auditor roster, `chanchi audit`,
the `install` key with `chanchi agents link --user`, `agent-chanchi-auditor` and
`skill-chanchi-audit-rounds`. Then backfill the design's three hand-run rounds so that
`chanchi audit show` reproduces their outcomes.

**Spec:** `docs/designs/global-items.md`, sections *Redundant audits*, *E. Project items* (the
`install` key) and *Verification plan* items 1 and 2. Read them before starting any task. When this
plan and the design disagree, the design wins: stop and report the disagreement.

**Tech stack:** Python ≥ 3.11 standard library (`tomllib`, `sqlite3`, `shutil`, `hashlib`), pytest
and ruff (dev only), uv.

## Global constraints

- Runtime dependencies stay empty (`[project] dependencies = []`).
- English everywhere. No home path (`/Users/<u>/`, `/home/<u>/`), email or reference-project name
  in any committed file (`tests/test_privacy.py`).
- **Run the worktree's code:** inside an executor worktree, always call `uv run chanchi ...`. A bare
  `chanchi` is the editable install of the main checkout and runs `main`'s code, not yours.
- **Executor sessions (S1-S6)** use a scratch database (`export CHANCHI_DB="$(mktemp -d)/chanchi.db"`)
  and, for anything that writes user folders, a scratch home (`export HOME="$(mktemp -d)"`, and
  unset `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME` or point them inside it). They never touch the
  operational database or the real `~/.claude`, `~/.config/opencode`, `~/.gemini`. Only the
  orchestrator's steps (the S6 precondition and Task 8) act on the real home and the operational
  database, and they say so.
- Never launch a harness from chanchi code or tests: chanchi only checks `shutil.which`
  (Principle 5). Tests inject the lookup; they never depend on what is installed.
- `ChanchiError` codes come from `src/chanchi/errors.py::ERROR_CODES`; add a code there when needed.
  Lifecycle refusals (closed round, seat not `assigned`, round not allowed) use
  `invalid_transition`. Enum values are validated in `taxonomy.py`, not in `CHECK` constraints.
- Layers (`tests/test_layers.py`): `harnesses.py` is a leaf (imports only `chanchi.errors`; add it
  to `LEAVES`); `audits.py` and `sync.py` are domain modules; only `cli.py` renders. Only
  `projects.py` may import `subprocess` (`tests/test_no_network.py`): any git call goes through it.
- Every new command gets a `FEATURE_MAP.md` entry (`tests/test_feature_map.py`) and a line in
  `README.md`.
- **Names that do not exist yet:** `tests/test_items.py` fails when `README.md`, `FEATURE_MAP.md`,
  `AGENTS.md`, `agents/` or `skills/` name an `agent-chanchi-*` or `skill-chanchi-*` item that does
  not exist. Until S5 creates them, S1-S4 never write `agent-chanchi-auditor` or
  `skill-chanchi-audit-rounds` into those files (code and tests may use the strings; docs show
  launch commands with `<agent>`).
- Executors never commit, merge, push or write chanchi records. They report each verification as the
  exact command plus its last output line, list every changed file, and stop at any gap.
- Last step of every session: `scripts/check` passes.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | agy user agents go to `~/.gemini/config/agents/<n>/agent.md` | Live probe on agy 1.5.14 (2026-11-21): an agent there is listed by `agy agents` and runs headless from a non-git folder; `~/.agents/agents/` is workspace-only. `~/.gemini/antigravity-cli/agents/` also loads, but the agy changelog names `~/.gemini/config/` as the global folder. Settles the design's live-probe item for phases 1 and 2. |
| D2 | Phase 1 adds `sync.sync_dir()` and `sync.roster()` only; `sync init/status` stay in phase 2. When chanchi is not installed from a git checkout (no main checkout), `sync_dir()` is `None` and the built-in roster applies | `chanchi audit` reads `SYNC/config/auditors.toml` when it exists and falls back to the built-in roster otherwise (design, *Locating SYNC*). |
| D3 | `agents link --user` records its entries in `mirror.json` next to the database, each with `"owner": "agents-link"` and the source root it came from; phase 2's `items mirror` uses the same file with `"owner": "items-mirror"` and touches only its own entries | The design asks for "the same ... manifest ownership as the mirror"; one file per machine keeps one ownership rule. |
| D4 | `chanchi agents link` requires `--user` in phase 1; `--check` and `--remove` are mutually exclusive; the source root defaults to chanchi's own repository (`Path(__file__).resolve().parents[2]`, like `skills_link.repo_skills_dir()`), never the current directory | Running it from another project must not read that project's `agents/` or drop chanchi's user agents. |
| D5 | `audit open --project <slug>` resolves with `projects.resolve_project`; when omitted, the project detected from git if registered, else none. `--change <ref>` needs a project: with none, `missing_prerequisite` and the hint `--project <slug>`; an unknown ref is `unknown_change` | Design: "It may link a chanchi change and a project, both optional"; `changes` is unique per project. |
| D6 | The author's spec is stored raw; `author_model_id` is set only when it resolves to an active catalog row, never an error | Design: `author_model_id ... NULL when not in the catalog`. |
| D7 | Families: the last `/`-separated segment, lowercased, matched by **prefix** (`opus`, `sonnet`, `haiku`, `fable` are prefixes like the others, so `fable-5.1` is `anthropic`; a `#variant` suffix does not affect a prefix match). Implemented twice: a recursive-CTE `UPDATE` in migration 005 and `taxonomy.family_for()`; a test asserts both agree on a fixed list including multi-segment ids | One rule, two implementations, held equal by a check instead of text. |
| D8 | A round's `degraded` is recomputed whenever its seats change (open, unavailable refill, next round) | The design records degraded per round; refills can change it. |
| D9 | The backfill records, per seat, the findings **open after that auditor's re-check** as the round's consolidation states them, with partial carry-overs at their original severity (table in Task 8) | Round-2 and round-3 reports also list resolved earlier findings; only open ones are votes. |

## File map

| File | Session | Responsibility |
|---|---|---|
| `src/chanchi/migrations/005_audits_and_families.sql`, `src/chanchi/data/template.db` | S1 | schema and family seeding |
| `src/chanchi/taxonomy.py`, `src/chanchi/catalog.py`, `src/chanchi/cli.py` (models) | S1 | audit enums, `family_for`, `--family`, `family` in model output |
| `src/chanchi/harnesses.py` (new, leaf), `src/chanchi/sync.py` (new), `src/chanchi/audits.py` (new) | S2, S3 | adapters, `SYNC` resolution, roster, audit procedure |
| `src/chanchi/cli.py` (audit group), `src/chanchi/errors.py` | S2, S3 | `chanchi audit ...` |
| `src/chanchi/agents_sync.py`, `src/chanchi/cli.py` (agents link) | S4 | per-kind render, `install`, user target map, manifest |
| `agents/agent-chanchi-auditor/AGENT.md`, `agents/agent-chanchi-orchestrator/AGENT.md`, wrappers, `skills/skill-chanchi-audit-rounds/SKILL.md`, `skills/skill-chanchi-verify/SKILL.md`, `skills/skill-chanchi-item-authoring/SKILL.md`, `AGENTS.md` | S5 | the agent, the skill, pointers |
| `FEATURE_MAP.md`, `README.md`, `tests/test_*.py` | each session | coverage of what the session adds |

## Sessions

| Session | Tasks | Depends on | task_type / complexity |
|---|---|---|---|
| S1 | 1 | — | `db-schema-migration` high (migration, template, three modules, CLI) |
| S2 | 2, 3 | S1 merged | `business-logic` high |
| S3 | 4 | S2 merged | `business-logic` medium |
| S4 | 5 | S2 merged (in parallel with S3) | `business-logic` medium |
| S5 | 6 | S3 and S4 merged | `docs` medium |
| S6 | 7 | S5 merged and linked by the orchestrator | `integration` low (read-only, `agent-chanchi-researcher`) |
| — | 8 | S5 merged (not S6) | orchestrator: backfill, records only |

Session protocol (chanchi change `global-items-phase1`, available
`agy:gemini-4-hydrogen-{medium,high}`, `claude:sonnet:{medium,high}`; explore budget
`max(1, floor(6/4)) = 1`, spent on S6, which no session and no task waits for):

- S1 `db-schema-migration` high — chanchi: recommended claude:sonnet:medium (95.1, ok confidence, global) · chosen claude:sonnet:high · reason: at high complexity global data is weak evidence; claude:sonnet:high has 27 sessions at the complexity level (93.2) against 3 for agy:gemini-4-hydrogen-high
- S2 `business-logic` high — chanchi: recommended claude:sonnet:medium (95.1, ok confidence, global) · chosen claude:sonnet:high · reason: claude:sonnet:high has 9 sessions at task_type+complexity (93.1)
- S3 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S4 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S5 `docs` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S6 `integration` low — chanchi: recommended claude:sonnet:high (98.7, low confidence, task_type) · chosen agy:gemini-4-hydrogen-medium:medium · explore: agy:gemini-4-hydrogen-medium:medium

Each executor works in its own worktree `.claude/worktrees/chanchi-gi1-sN` on branch
`feat/gi1-sN`, created from `main` after its dependencies merged. The orchestrator commits and
merges each session with `git merge --no-ff`. S3 and S4 both touch `cli.py`, `FEATURE_MAP.md` and
`README.md` in different sections; the orchestrator merges S3 first and resolves S4's merge.

---

### Task 1 (S1): Migration 005 and model families

**Files:** create `src/chanchi/migrations/005_audits_and_families.sql`; modify
`src/chanchi/data/template.db` (regenerated), `src/chanchi/taxonomy.py`, `src/chanchi/catalog.py`,
`src/chanchi/cli.py` (models parsers only), `tests/test_db.py`, `tests/test_catalog.py`,
`tests/test_taxonomy.py`, `FEATURE_MAP.md` (models entry), `README.md`.

**Interfaces produced:**
- Tables `audits`, `audit_rounds`, `audit_seats` (with the partial unique index
  `audit_seats_active`), `audit_dissents` and column `models.family`, exactly as in the design's
  *Data model (migration 005)* block. Header comment names the design and says the lessons stage 3
  takes the next free number.
- `taxonomy.family_for(model: str) -> str | None` (decision D7): last `/` segment, lowercased,
  prefixes `claude`, `opus`, `sonnet`, `haiku`, `fable` → `anthropic`; `gemini` → `google`; `gpt`
  → `openai`; `minimax` → `minimax`; `deepseek` → `deepseek`; `glm` → `zhipu`; `kimi` →
  `moonshot`; `qwen` → `alibaba`; `grok` → `xai`; `mimo` → `xiaomi`; otherwise `None`.
- `taxonomy` constants: `AUDIT_SUBJECT_KINDS = ("design", "item", "adoption", "replication",
  "other")`, `AUDIT_VERDICTS = ("pass", "pass_with_fixes", "fail")`, `AUDIT_SEVERITIES =
  ("blocking", "major", "minor")`, `DISSENT_DECISIONS = ("confirmed", "rejected")`,
  `AUDIT_OUTCOMES = ("accepted", "fix", "rework", "escalated")`, `AUDIT_ESCALATIONS = ("quorum",
  "round_cap")`, `SEAT_STATUSES = ("assigned", "voted", "unavailable")`; all listed by
  `taxonomy.describe()`.
- `catalog.add_model(..., family: str | None = None)`: when `None`, store `family_for(model)`;
  `catalog.set_model(..., family=...)`; a family is a kebab-case slug (`[a-z0-9]+(-[a-z0-9]+)*`),
  else `invalid_value`, `field: "family"`.
- `models add --family <name>`, `models set <agent:model> --family <name>`; every model dict
  carries `family` (null when unknown).

- [ ] **Step 1:** Write failing tests: (a) `family_for` on `claude`, `sonnet`, `fable-5.1`,
  `gemini-4-neon-high`, `claude-opus-5-5-high`, `opencode-go/minimax-m3#thinking`,
  `opencode-go/glm-5.3`, `opencode-go/kimi-k3`, `opencode-go/qwen3.8-max`,
  `opencode-go/grok-4.7`, `opencode-go/mimo-v2.6-pro`, `opencode-go/deepseek-v4-pro`,
  `gpt-oss-120b-medium`, `opencode-go/hy4`, `human`, and the multi-segment ids
  `openrouter/qwen/other` → `None`, `deepseek/r1` → `None`, `claude/gemini-4` → `google`;
  (b) the same ids inserted into a scratch database at version 4 and migrated get the same family
  from the SQL as from `family_for`; (c) `models add` infers the family, `--family` overrides it,
  `models set --family` changes it, a bad slug is refused; (d) the four audit tables and the index
  exist after migration.
- [ ] **Step 2:** Update the existing `tests/test_db.py` tests that hardcode the latest version
  (the synthetic `005_add_probe.sql` becomes `006_add_probe.sql`; version lists and the
  `latest_version` assertions gain 5) and add the four new tables to `OPERATIONAL_TABLES` (the
  template must hold no audit rows).
- [ ] **Step 3:** Write the migration. Seed families with a recursive CTE that reduces each model to
  its last segment (`WITH RECURSIVE seg(id, s) AS (SELECT id, lower(model) FROM models UNION ALL
  SELECT id, substr(s, instr(s, '/') + 1) FROM seg WHERE instr(s, '/') > 0) UPDATE models SET
  family = (SELECT CASE WHEN s LIKE 'claude%' OR ... THEN 'anthropic' ... END FROM seg WHERE
  seg.id = models.id AND instr(s, '/') = 0)`).
- [ ] **Step 4:** Implement `taxonomy` and `catalog` changes and the two CLI flags; run the tests.
- [ ] **Step 5:** Regenerate the template: `uv run chanchi db migrate --template`.
- [ ] **Step 6:** Update the `models` entry of `FEATURE_MAP.md` (`--family`, `family` in the
  evidence) and `README.md` (*Everyday commands* gains a `models set ... --family` line).
- [ ] **Step 7:** `scripts/check` passes.

**Verification (paste each command and its last line):**
`uv run pytest -q tests/test_db.py tests/test_catalog.py tests/test_taxonomy.py`;
`CHANCHI_DB=$(mktemp -d)/c.db sh -c 'uv run chanchi db migrate >/dev/null && uv run chanchi db status && uv run chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high'`
(`latest_migration: 5`, `template.version: 5`, `"family": "google"`); `scripts/check`.

---

### Task 2 (S2): Harness adapters, `SYNC` resolution and the roster

**Files:** create `src/chanchi/harnesses.py`, `src/chanchi/sync.py`, `tests/test_harnesses.py`,
`tests/test_sync.py`; modify `tests/test_layers.py` (`LEAVES` gains `harnesses`).

**Interfaces produced:**
- `harnesses.KEYS = ("claude", "opencode", "agy")`; unknown key → `invalid_value` with
  `valid_values`.
- `harnesses.launch(key, *, agent, model, effort, prompt) -> str`, the design's headless templates:
  claude `claude -p --agent <a> --model <m> [--effort <e>] "<prompt>" < /dev/null` (no `--effort`
  when `effort` is `None`); opencode `opencode run --agent <a> -m <model> "<prompt>" < /dev/null`
  with the catalog model as is, variants included (`effort` ignored); agy `agy --agent <a> --model
  <base> --effort <e> -p="<prompt>" < /dev/null` via `split_agy_model`.
- `harnesses.split_agy_model(model, effort) -> str`: the base of `<base>-<effort>`; `invalid_value`
  when `effort` is `None` or the id does not end in `-<effort>`.
- `harnesses.home_dir(key, *, env, home) -> Path`: claude `<home>/.claude`; opencode
  `$OPENCODE_CONFIG_DIR`, else `$XDG_CONFIG_HOME/opencode`, else `<home>/.config/opencode`; agy
  `<home>/.gemini`. `harnesses.installed(key, *, env, home) -> bool` (that folder exists).
- `harnesses.user_agent_path(key, name, *, env, home) -> Path`: claude
  `<home>/.claude/agents/<n>.md`; opencode `<opencode dir>/agents/<n>.md`; agy
  `<home>/.gemini/config/agents/<n>/agent.md` (decision D1).
- `harnesses.available(key, which=shutil.which) -> bool` (binary on `PATH`).
- `sync.sync_dir(env=os.environ, *, repo_root: Path | None = None) -> Path | None`:
  `CHANCHI_SYNC` when set; else `projects.main_worktree(repo_root or Path(__file__).resolve().parents[2]) / "SYNC"`;
  `None` when there is no main checkout or the directory does not exist (decision D2).
- `sync.BUILTIN_ROSTER`: the four entries of the design's TOML block, in order.
  `sync.roster(env=os.environ, *, repo_root=None) -> list[dict]`: entries `{harness, model, effort}`
  from `<sync_dir>/config/auditors.toml` (`[[auditor]]` tables, `tomllib`) when the file exists,
  else `BUILTIN_ROSTER`. A malformed file → `invalid_value` naming the file and the entry index; an
  unknown harness → `invalid_value` with `valid_values`.

- [ ] **Step 1:** Failing tests: launch strings for each harness (agy splits
  `gemini-4-neon-high` + `high` into `--model gemini-4-neon --effort high`; a mismatched or missing
  effort is refused; claude without effort omits the flag); `home_dir` honours
  `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME`; `available` uses the injected `which`; `sync_dir`
  with `CHANCHI_SYNC`, from the main checkout and from a `git worktree` of a temporary repository
  passed as `repo_root` (both resolve to the same `SYNC`), and missing; roster from a temporary
  `auditors.toml`, the built-in fallback, and a malformed file.
- [ ] **Step 2:** Implement; add `harnesses` to `LEAVES`.
- [ ] **Step 3:** `scripts/check` passes.

### Task 3 (S2): `chanchi audit open | unavailable | show | list`

**Files:** create `src/chanchi/audits.py`, `tests/test_audits.py`; modify `src/chanchi/cli.py`,
`src/chanchi/errors.py` (code `unknown_audit`), `FEATURE_MAP.md` (new `audit` entry; S3 extends it),
`README.md` (new *Audits* section).

**Interfaces produced:**
- `audits.open_audit(conn, *, kind, ref, author, commit=None, version=None, change=None,
  project_id=None, roster, which=shutil.which, now=None) -> dict`. Exactly one of `commit` /
  `version` (`invalid_value` otherwise). Creates the audit and round 1 with `subject_at` = the
  commit or version, then fills three seats. `change` and `project_id` follow D5; `author` follows
  D6.
- **Seat filling** `_fill(conn, round_id, seat_numbers, roster, *, audit_id, which)`: walk the
  roster in order; an entry is *available* when `harnesses.available(harness)`, its
  `harness:model` row is in the catalog and active, the spec is not marked unavailable in this
  audit, and **the spec is not already seated in this round** (an `assigned` or `voted` seat). First
  pass: available entries whose family is known and not yet among the seated families. Second pass:
  the next available entries in roster order, any family. Output per call: `seated` and `skipped`,
  each skipped entry with a reason (`not_on_path`; `not_in_catalog` with the hint
  `chanchi models add --agent <h> --model <m> --cost <1-3>`; `inactive`; `unavailable`;
  `already_seated`) and, for every seated or skipped model with an unknown family, the hint
  `chanchi models set <h>:<m> --family <name>`.
- `degraded` = fewer than three distinct known families among the round's seats whose status is not
  `unavailable` (decision D8).
- **Quorum at open:** when fewer than two seats can be filled, the round closes at once: outcome
  `escalated`, escalation `quorum`, `closed_at` set on the round and on the audit, and `open`
  returns that outcome. The same rule applies to `next_round` (Task 4).
- Output of `open`: audit id, round, `degraded`, `outcome` (null unless escalated), `skipped`,
  and per seat `{seat, spec, family, effort, status, launch}`, where `launch` is
  `harnesses.launch(harness, agent="agent-chanchi-auditor", model=..., effort=...,
  prompt="<prompt>")`.
- `audits.mark_unavailable(conn, audit_id, *, round, seat, reason, roster, which)`: refused
  (`invalid_transition`) on a closed round or a seat that is not `assigned`; sets the seat
  `unavailable` with `reason`, inserts a new seat row with the same number from the roster (the
  partial index allows it), recomputes `degraded`, prints the new seat or `null` when the roster is
  exhausted.
- `audits.show(conn, audit_id) -> dict` (every round, every seat row including unavailable ones,
  vote, dissent, outcome, escalation, degraded; `unknown_audit` for a bad id) and
  `audits.list_audits(conn, *, kind=None, ref=None)` (id, kind, ref, rounds, last outcome).
- CLI: `chanchi audit open --kind <k> --ref <ref> --author <spec> (--commit <sha> | --version
  <x.y.z>) [--change <ref>]` built with `leaf(..., project=True)` so `--project` comes from the
  shared parent (no second flag); `chanchi audit unavailable <id> --round <n> --seat <n> --reason
  "<error>"`, `chanchi audit show <id>`, `chanchi audit list [--kind <k>] [--ref <ref>]` with
  `project=False`. Each loads the roster with `sync.roster()`.

- [ ] **Step 1:** Failing tests (scratch DB, injected `which`, `CHANCHI_SYNC` pointing at a scratch
  folder so the machine's `SYNC` never leaks in): three families seat three distinct families; with
  the opencode binary missing, seat 3 gets `agy:gemini-4-hydrogen-high` and the round is degraded; an
  unknown-family model never counts as distinct (degraded) and is named with the hint; a roster
  entry not in the catalog is skipped with the `models add` hint; a roster with one usable spec
  never seats it twice and escalates with `quorum`, with `closed_at` set; `unavailable` refills
  the same seat number, never with an already-seated spec, and recomputes `degraded`; `unavailable`
  on a voted seat or a closed round is refused; `--change` without a project is refused with the
  `--project` hint; `show` lists the unavailable row and its replacement.
- [ ] **Step 2:** Implement `audits.py` and the CLI; add the `audit` entry to `FEATURE_MAP.md`
  (sub-features `audit open`, `audit unavailable`, `audit show`, `audit list`; the scratch setup
  registers the three roster models with `uv run chanchi models add`) and the README section. Docs
  show launch commands with `<agent>` (Global constraints, names that do not exist yet).
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S2):** `uv run pytest -q tests/test_harnesses.py tests/test_sync.py tests/test_audits.py tests/test_layers.py tests/test_no_network.py`;
the `audit` entry of `FEATURE_MAP.md` driven with `uv run chanchi` on a scratch database (paste the
`open` output's seat list); `scripts/check`.

---

### Task 4 (S3): `chanchi audit vote | dissent | close | round`

**Files:** modify `src/chanchi/audits.py`, `src/chanchi/cli.py`, `tests/test_audits.py`,
`FEATURE_MAP.md` (`audit` entry), `README.md`.

**Interfaces produced:**
- `audits.vote(conn, audit_id, *, round, seat, verdict, blocking, major, minor, report)`: refused
  (`invalid_transition`) on a closed round or a seat not `assigned`; a `pass` with `blocking > 0`
  or `major > 0` is refused (`invalid_value`, `field: "verdict"`, hint: vote `pass_with_fixes`).
- `audits.dissent(conn, audit_id, *, round, seat, finding, severity, decision, evidence)`: refused
  (`invalid_transition`) on a closed round or a seat that has not voted; `finding` and `evidence`
  non-blank.
- `audits.outcome(votes, dissents, round_no) -> tuple[str, str | None]`: a pure function, rows in
  this order, the first match wins:
  1. fewer than two voted → (`escalated`, `quorum`), whatever the round;
  2. at least two `fail` → `rework`;
  3. at least two **approvals** (a `pass`, or a `pass_with_fixes` with `blocking == 0 and
     major == 0`) and no `confirmed` dissent of severity `blocking` or `major` → `accepted`;
  4. otherwise `fix`;
  then, only when rows 2-4 gave `rework` or `fix` and `round_no == 3`, (`escalated`, `round_cap`).
- `audits.close_round(conn, audit_id, *, round)`: refused while any seat is `assigned`; stores
  outcome and escalation on the round, the outcome on the audit, and `closed_at` on the round and,
  for `accepted` or `escalated`, on the audit. For `accepted` it lists the minor findings to fix:
  each approving seat's minor count and each confirmed lone minor dissent.
- `audits.next_round(conn, audit_id, *, commit=None, version=None, roster, which)`: refused
  (`invalid_transition`) unless the last round is closed with `fix` or `rework` and is below 3;
  re-seats each of the last round's non-unavailable specs in the same seat number when still
  available, refills the others with `_fill`, recomputes `degraded`, applies the quorum rule.
- CLI (all `project=False`): `chanchi audit vote <id> --round <n> --seat <n> --verdict <v>
  --blocking <n> --major <n> --minor <n> --report <path>`, `chanchi audit dissent <id> --round <n>
  --seat <n> --finding "<id: text>" --severity <s> --decision <d> --evidence "<why>"`,
  `chanchi audit close <id> --round <n>`, `chanchi audit round <id> (--commit <sha> | --version
  <x.y.z>)`.

- [ ] **Step 1:** Failing tests for `outcome()`, table-driven, one row per rule plus: a
  `pass_with_fixes` with zero blocking and zero major is an approval (owner's rule, 2026-11-21);
  two approvals plus a confirmed lone major → `fix`; a rejected lone major does not block; round 3
  `fix` → `escalated`/`round_cap`; round 3 with one voter → `escalated`/`quorum` (not
  `round_cap`); two voters, both approving → `accepted`. Lifecycle tests: vote and dissent refused
  on a closed round; `pass` with a major refused; close refused with an assigned seat; `round`
  refused after `accepted` and after round 3; round numbers continue across commits.
- [ ] **Step 2:** A **reproduction test** of the design's history (verification plan item 2) with
  the counts of Task 8's table (decision D9): round 1 at `953ac5a` → `fix`; round 2 at `a7a1a20` →
  `fix`; round 3 at `e40d275` with the two confirmed lone major dissents of seat 3 (`R3-01`,
  `R3-02`) → `escalated`/`round_cap`.
- [ ] **Step 3:** Implement; extend the `audit` entry of `FEATURE_MAP.md` (sub-features `audit
  vote`, `audit dissent`, `audit close`, `audit round`) and README.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S3):** `uv run pytest -q tests/test_audits.py`; the full `audit` entry of
`FEATURE_MAP.md` driven with `uv run chanchi` on a scratch database through `close` and `round`
(paste `audit show`); `scripts/check`.

---

### Task 5 (S4): `install` key and `chanchi agents link --user`

**Files:** modify `src/chanchi/agents_sync.py`, `src/chanchi/cli.py` (agents group),
`tests/test_agents_sync.py`, `FEATURE_MAP.md` (`agents` entry), `README.md` (*Agents*).

**Interfaces produced:**
- `AgentSource.install: str` from the optional frontmatter key `install` (`repo|user`, default
  `repo`; anything else → `invalid_value`, `valid_values`). `agents sync` still compiles every
  agent into the repository wrappers, byte-identical to today for existing sources.
- `render_by_kind(source, header: str) -> dict[str, str]` keyed by harness kind (`claude`,
  `opencode`, `agy`). `render(source)` keeps its signature and output (repository paths, repository
  header) as a thin wrapper: `{REPO_TARGETS[kind](source.name): text for kind, text in
  render_by_kind(source, _header(source)).items()}`. Existing tests stay unchanged and green.
- `USER_HEADER = "# generated by chanchi agents link --user from agents/{name}/AGENT.md; do not edit"`,
  formatted with the source name.
- `agents_sync.link_user(root, *, env, home, db_dir, check=False, remove=False) -> dict`
  (`check` and `remove` exclusive): for every source with `install: user`, for every harness with
  `harnesses.installed`, writes `render_by_kind(source, USER_HEADER...)[kind]` to
  `harnesses.user_agent_path(...)`, creating parent folders (`mkdir(parents=True,
  exist_ok=True)`). Reports `written`, `unchanged`, `removed`, `conflicts`, `skipped_harnesses`.
- **Manifest** `db_dir / "mirror.json"` (decision D3; `db_dir` is the folder of
  `db.operational_path()`, created if missing): `{"version": 1, "entries": [{"owner":
  "agents-link", "root", "path", "kind", "sha256"}]}`. The command writes or updates only paths
  listed with owner `agents-link`; a file at a target path that is not in the manifest is a
  conflict, and when any conflict exists nothing is written (`link_conflict`, the paths in
  `details`). Entries of another owner are preserved byte for byte. An `agents-link` entry with the
  same `root` whose source no longer has `install: user` is removed; entries of another `root` are
  left alone.
- `--check` writes nothing and fails with `stale_wrappers` when an owned file is missing or its
  hash differs, a wanted file is not written yet, an owned entry is orphaned, or a conflict exists.
  `--remove` deletes every `agents-link` entry of this `root` (and an agy `<n>/` folder left empty)
  and drops them from the manifest.
- CLI: `chanchi agents link --user [--check | --remove] [<root>]`, `<root>` defaulting to chanchi's
  repository (decision D4); without `--user` → `invalid_value`, hint `chanchi agents link --user`.

- [ ] **Step 1:** Failing tests with a temporary `HOME`, a scratch `CHANCHI_DB` folder and a
  temporary root holding two sources (one `install: user`): all three harness folders present →
  three files with the user header (agy at `.gemini/config/agents/<n>/agent.md`, its parents
  created); opencode folder missing → `skipped_harnesses: ["opencode"]`; `OPENCODE_CONFIG_DIR`
  honoured; second run all `unchanged`; hand edit → `--check` fails, a normal run repairs it; a
  foreign file at a target path → `link_conflict`, file untouched, nothing else written; an
  `items-mirror` entry and an entry of another root survive `link` and `--remove`; `--remove` leaves
  no owned file and no empty agy folder; `install: bogus` refused; `--check --remove` refused; the
  repository's own `agents sync --check` still passes.
- [ ] **Step 2:** Refactor first (`render_by_kind`, `REPO_TARGETS`, `render` wrapper) with the
  existing `test_agents_sync.py` green, then `link_user` and the CLI.
- [ ] **Step 3:** Update the `agents` entry of `FEATURE_MAP.md` (sub-feature `agents link`, driven
  with `HOME` and `CHANCHI_DB` set to scratch folders, never the real home) and README.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S4):** `uv run pytest -q tests/test_agents_sync.py`; the `agents` entry of
`FEATURE_MAP.md` driven with `uv run chanchi` in a scratch `HOME` (paste the `link` output);
`uv run chanchi agents sync --check`; `scripts/check`.

---

### Task 6 (S5): `agent-chanchi-auditor`, `skill-chanchi-audit-rounds` and pointers

**Files:** create `agents/agent-chanchi-auditor/AGENT.md`,
`skills/skill-chanchi-audit-rounds/SKILL.md`; modify `agents/agent-chanchi-orchestrator/AGENT.md`,
the generated wrappers (`uv run chanchi agents sync`), `skills/skill-chanchi-verify/SKILL.md`
(*Helpers*), `skills/skill-chanchi-item-authoring/SKILL.md` (*Agent source*: the `install` key),
`tests/test_skills_content.py`, `AGENTS.md` (one pointer), `README.md` (*Agents* list and the
*Audits* section may now name the auditor). Follow `skill-chanchi-item-authoring`.

**Content:**
- `agent-chanchi-auditor`: frontmatter `name`, `description` (audits one subject against a brief
  and writes one report; never edits the subject, never reads other auditors' reports), `scope:
  both`, `profile: read-only`, `install: user`, `skills: []`. Body, harness neutral and without a
  model: read the brief; check the subject against the request and the evidence, re-running cheap
  facts locally; edit no file; create only the report, at the private path the prompt gives (on
  opencode, write it with the shell, as the researcher does: the read-only profile denies the edit
  and write tools there); first line `VERDICT: PASS`, `VERDICT: PASS WITH FIXES` or
  `VERDICT: FAIL`; then a table `id | severity (blocking/major/minor) | where | problem | evidence |
  fix`; a `PASS` carries no blocking or major finding; in a later round, re-check its own earlier
  findings as RESOLVED/PARTIAL/OPEN first and count only open ones; never read another auditor's
  report path or the current round's reports; never write a home path or a reference-project name;
  the reporter line of `skill-chanchi-lessons`.
- `skill-chanchi-audit-rounds` (≤ 300 lines; description starts "Use when ..."): what needs an audit
  (everything the orchestrator writes; global item versions, adoption decisions and replication
  plans from later phases); one brief for three seats (request, evidence, subject at a commit, the
  private report path per seat); `chanchi audit open`, launching each seat's `launch` command with
  the brief as prompt, keeping reports in private scratch paths and moving them into
  `docs/designs/reviews/<topic>/` only after every seat voted; `audit vote` with the counts of open
  findings; `audit unavailable` when a harness fails (paste its error); `audit dissent` for every
  finding raised by exactly one auditor; `audit close`; `audit round` with the fix commit; one
  consolidation file per round; stop at `accepted` or `escalated` and give the human the
  disagreement report; an `accepted` round's minor fixes are applied without a new round. Every
  `chanchi` command it names must exist (`tests/test_skills_content.py`).
- `agent-chanchi-orchestrator`: `skills` gains `skill-chanchi-audit-rounds`; rule 4 of the body
  points to it.
- `AGENTS.md` § Working Conventions: the audit sentence's "Procedure:" names
  `skill-chanchi-audit-rounds` next to the design. Stay ≤ 150 lines.
- `skill-chanchi-verify` *Helpers*: after a harness upgrade, re-run each adapter's launch template
  once with `agent-chanchi-auditor` and a trivial prompt, and run `chanchi agents link --user
  --check`.
- `tests/test_skills_content.py::test_all_skills_exist`: the list is sorted by path, so
  `skill-chanchi-audit-rounds` goes **first**.

- [ ] **Step 1:** `uv run pytest -q tests/test_skills_content.py` fails on the missing skill; write
  the agent and the skill; `uv run chanchi agents sync`; tests pass.
- [ ] **Step 2:** `scripts/check` passes (rules budget, items, privacy, agent rules).

**Verification (S5):** `uv run pytest -q tests/test_skills_content.py tests/test_items.py tests/test_rules_budget.py tests/test_agent_rules.py`;
`uv run chanchi agents sync --check`; `scripts/check`.

---

### Task 7 (S6): Harness-side verification (read-only)

**Precondition (orchestrator, real home):** after S5 merges, from the main checkout:
`chanchi skills link --global` and `chanchi agents link --user`, pasting both outputs into the
session log. The items count as delivered only when the harnesses load them.

The researcher, from a scratch folder outside any repository, writes nothing but its report:
1. Runs each command below and quotes the reply (expected: the agent name and `VERDICT:`):
   - `claude -p --agent agent-chanchi-auditor --model sonnet --effort low "State your agent name and the first line format of your reports, then stop." < /dev/null`
   - `opencode run --agent agent-chanchi-auditor -m opencode-go/minimax-m3 "State your agent name and the first line format of your reports, then stop." < /dev/null`
   - `agy --agent agent-chanchi-auditor --model gemini-4-hydrogen --effort medium -p="State your agent name and the first line format of your reports, then stop." < /dev/null`
2. Asks each harness, with the same three launch forms but the default agent, "Is a skill named
   skill-chanchi-audit-rounds available to you? Answer yes or no and quote the first words of its
   description." and quotes the answers; also lists `agy agents` and `opencode debug agents` output
   lines naming `agent-chanchi-auditor`.
3. Runs `chanchi agents link --user --check` (expected `ok: true`).
4. Reports VERIFIED/UNVERIFIED per item.

### Task 8 (orchestrator): Backfill and acceptance signal

On the **operational database**, after S5 merges (independent of S6):
1. Check `chanchi models list` shows `claude:sonnet` (`anthropic`), `agy:gemini-4-neon-high`
   (`google`) and `opencode:opencode-go/minimax-m3` (`minimax`).
2. Run with `CHANCHI_SYNC` pointing at a scratch folder whose `config/auditors.toml` lists exactly
   those three specs in seat order 1, 2, 3, so the seats match history; if a binary is missing on
   `PATH`, stop and report it — never add `unavailable` rows that did not happen.
3. `chanchi audit open --kind design --ref docs/designs/global-items.md --author claude:opus:high
   --commit 953ac5a`, then per round the votes below, a dissent for each lone finding the round's
   consolidation marks (severity from that auditor's report, decision as recorded), `audit close`,
   and `audit round --commit <next>`. Report paths are the files in
   `docs/designs/reviews/global-items/`.

| Round | Commit | Seat 1 claude:sonnet:medium | Seat 2 agy:gemini-4-neon-high:high | Seat 3 opencode:opencode-go/minimax-m3 | Expected |
|---|---|---|---|---|---|
| 1 | `953ac5a` | pass_with_fixes 0/8/12 | pass_with_fixes 3/5/4 | pass_with_fixes 2/6/10 | fix |
| 2 | `a7a1a20` | pass_with_fixes 0/2/8 | pass_with_fixes 0/5/2 (4 new major, 1 minor, partial F6 major and F10 minor) | pass_with_fixes 1/3/6 (3 new major, 3 minor, partial GI-02 blocking and GI-15/16/17 minor) | fix |
| 3 | `e40d275` | pass_with_fixes 0/0/6 | pass 0/0/2 | pass_with_fixes 0/2/2, dissents R3-01 and R3-02 major confirmed | escalated, round_cap |

4. Backfill this plan's own hand-run rounds the same way (kind `other`, ref
   `docs/superpowers/plans/2026-11-21-global-items-phase1.md`), from
   `docs/designs/reviews/global-items-phase1-plan/`.
5. `chanchi audit show <id>` must reproduce each round's outcome (the phase-1 signal). Then
   `chanchi change close global-items-phase1` and `chanchi show global-items-phase1`.

**Out of this plan:** the design's second phase-1 signal ("the next design is audited with the
commands") is met by the next design, which runs `skill-chanchi-audit-rounds` end to end. Lessons
#1-#4 stay pending on purpose (owner's request); this plan neither reviews nor applies them.

## Risks

| Risk | Mitigation |
|---|---|
| The SQL seeding and `family_for` drift | D7 test compares them on fixed and multi-segment ids |
| A refactor of `agents_sync` changes committed wrappers | `render` wrapper unchanged; `agents sync --check` in the gate |
| `agents link --user` overwrites a user's own agent, or drops chanchi's when run elsewhere | manifest ownership with `root`; foreign files are conflicts; root defaults to chanchi's repository |
| agy's "read-only" tool list includes `write_to_file` and `run_command` | accepted: the auditor must write its report; the brief and the auditor body forbid editing the subject; a hook-based guard is out of scope |
| Parallel S3 and S4 edit `cli.py`, `FEATURE_MAP.md`, `README.md` | different sections; the orchestrator merges S3 first and resolves S4 |
| Backfill seats differ from history | Task 8 step 2: a scratch roster in history's order; stop rather than invent rows |
