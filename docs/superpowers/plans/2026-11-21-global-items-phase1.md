# Global Items — Phase 1 (Redundant Audits) Implementation Plan

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
- Tests and manual runs use a scratch database: `export CHANCHI_DB="$(mktemp -d)/chanchi.db"`, and
  for `agents link --user` a scratch home: `export HOME="$(mktemp -d)"` (also unset
  `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME`, or point them inside the scratch home). Never touch
  the operational database or the real `~/.claude`, `~/.config/opencode`, `~/.gemini`.
- Never launch a harness from chanchi code or tests: chanchi only checks `shutil.which`
  (Principle 5). Tests inject the lookup; they never depend on what is installed.
- `ChanchiError` codes come from `src/chanchi/errors.py::ERROR_CODES`; add a code there when needed.
  Enum values are validated in `taxonomy.py`, not in `CHECK` constraints (as migration 004 does).
- Layers (`tests/test_layers.py`): `harnesses.py` is a leaf (imports only `chanchi.errors`; add it
  to `LEAVES`); `audits.py` and `sync.py` are domain modules; only `cli.py` renders.
- Every new command gets a `FEATURE_MAP.md` entry (`tests/test_feature_map.py` fails otherwise) and
  a line in `README.md`.
- Executors never commit, merge, push or write chanchi records. They report each verification as the
  exact command plus its last output line, list every changed file, and stop at any gap.
- Last step of every session: `scripts/check` passes.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | agy user agents go to `~/.gemini/config/agents/<n>/agent.md` | Live probe on agy 1.5.14 (2026-11-21): an agent there is listed by `agy agents` and runs headless from a non-git folder; `~/.agents/agents/` is workspace-only. `~/.gemini/antigravity-cli/agents/` also loads but the CLI changelog names `~/.gemini/config/` as the global folder. This settles the design's "verified by a live probe" item for both phase 1 and phase 2. |
| D2 | Phase 1 adds `sync.sync_dir()` only (resolution: `CHANCHI_SYNC`, else `<main checkout>/SYNC`); `sync init/status` stay in phase 2 | `chanchi audit` must read `SYNC/config/auditors.toml` when it exists and fall back to the built-in roster otherwise (design, *Locating SYNC*). |
| D3 | `agents link --user` records its entries in `mirror.json` next to the database, each with `"owner": "agents-link"`; phase 2's `items mirror` uses the same file with `"owner": "items-mirror"` and touches only its own entries | The design asks for "the same ... manifest ownership as the mirror"; one file per machine keeps one ownership rule. |
| D4 | `chanchi agents link` requires `--user` in phase 1 (repository wrappers stay `chanchi agents sync`); it also takes `--check` and `--remove` | Mirrors the `items mirror` contract; no second meaning for the bare command. |
| D5 | `audit open --project` is optional: when omitted, the project detected from git if it is registered, else none; never an error | Design: "It may link a chanchi change and a project, both optional." |
| D6 | The author's spec is stored raw; `author_model_id` is set only when it resolves to an active catalog row, never an error | Design: `author_model_id ... NULL when not in the catalog`. |
| D7 | Family seeding is one SQL `CASE` in migration 005 plus `taxonomy.family_for(model)` in Python; a test asserts both agree on a fixed list of ids and on every row of the template database | One rule, two implementations, held equal by a check instead of text. |
| D8 | A round's `degraded` is recomputed whenever its seats change (open, unavailable refill) | The design records degraded per round; refills can change it. |

## File map

| File | Session | Responsibility |
|---|---|---|
| `src/chanchi/migrations/005_audits_and_families.sql`, `src/chanchi/data/template.db` | S1 | schema and family seeding |
| `src/chanchi/taxonomy.py`, `src/chanchi/catalog.py`, `src/chanchi/cli.py` (models) | S1 | audit enums, `family_for`, `--family` on `models add/set`, `family` in model output |
| `src/chanchi/harnesses.py` (new, leaf), `src/chanchi/sync.py` (new), `src/chanchi/audits.py` (new) | S2, S3 | adapters, `SYNC` resolution, roster, audit procedure |
| `src/chanchi/cli.py` (audit group), `src/chanchi/errors.py` | S2, S3 | `chanchi audit ...` |
| `src/chanchi/agents_sync.py`, `src/chanchi/cli.py` (agents link) | S4 | per-kind render, `install`, user target map, manifest |
| `agents/agent-chanchi-auditor/AGENT.md`, `agents/agent-chanchi-orchestrator/AGENT.md`, generated wrappers, `skills/skill-chanchi-audit-rounds/SKILL.md`, `skills/skill-chanchi-verify/SKILL.md`, `AGENTS.md` | S5 | the agent, the skill, pointers |
| `FEATURE_MAP.md`, `README.md`, `tests/test_*.py` | each session | coverage of what the session adds |

## Sessions

| Session | Tasks | Depends on | task_type / complexity |
|---|---|---|---|
| S1 | 1 | — | `db-schema-migration` medium |
| S2 | 2, 3 | S1 merged | `business-logic` high |
| S3 | 4 | S2 merged | `business-logic` medium |
| S4 | 5 | S2 merged (runs in parallel with S3) | `refactor` medium |
| S5 | 6 | S3 and S4 merged | `docs` medium |
| S6 | 7 | S5 merged and linked by the orchestrator | `integration` low (read-only, `agent-chanchi-researcher`) |
| — | 8 | S6 accepted | orchestrator: backfill (records only, no executor) |

Session protocol (chanchi change `global-items-phase1`, available
`agy:gemini-4-hydrogen-{medium,high}`, `claude:sonnet:{medium,high}`; explore budget
`max(1, floor(6/4)) = 1`, spent on S6, the only session nothing depends on):

- S1 `db-schema-migration` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S2 `business-logic` high — chanchi: recommended claude:sonnet:medium (95.1, ok confidence, global) · chosen claude:sonnet:high · reason: at high complexity global data is weak evidence; claude:sonnet:high has 9 sessions at task_type+complexity (93.1)
- S3 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S4 `refactor` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S5 `docs` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.4, low confidence, complexity) · chosen agy:gemini-4-hydrogen-high:high
- S6 `integration` low — chanchi: recommended claude:sonnet:high (98.7, low confidence, task_type) · chosen agy:gemini-4-hydrogen-medium:medium · explore: agy:gemini-4-hydrogen-medium:medium

Each executor works in its own worktree `.claude/worktrees/chanchi-gi1-sN` on branch
`feat/gi1-sN`, created from `main` after its dependencies merged. The orchestrator commits and
merges each session with `git merge --no-ff`.

---

### Task 1 (S1): Migration 005 and model families

**Files:** create `src/chanchi/migrations/005_audits_and_families.sql`; modify
`src/chanchi/data/template.db` (regenerated), `src/chanchi/taxonomy.py`, `src/chanchi/catalog.py`,
`src/chanchi/cli.py` (models parsers only), `tests/test_db.py`, `tests/test_catalog.py`,
`tests/test_taxonomy.py`, `FEATURE_MAP.md` (models entry), `README.md`.

**Interfaces produced:**
- Tables `audits`, `audit_rounds`, `audit_seats` (with the partial unique index
  `audit_seats_active`), `audit_dissents` and column `models.family`, exactly as in the design's
  *Data model (migration 005)* block.
- `taxonomy.family_for(model: str) -> str | None`: take the last `/`-separated segment, drop any
  `#variant`, lowercase it, then match prefixes: `claude`, `opus`, `sonnet`, `haiku`, `fable` →
  `anthropic`; `gemini` → `google`; `gpt` → `openai`; `minimax` → `minimax`; `deepseek` →
  `deepseek`; `glm` → `zhipu`; `kimi` → `moonshot`; `qwen` → `alibaba`; `grok` → `xai`; `mimo` →
  `xiaomi`; otherwise `None`.
- `taxonomy` constants: `AUDIT_SUBJECT_KINDS = ("design", "item", "adoption", "replication",
  "other")`, `AUDIT_VERDICTS = ("pass", "pass_with_fixes", "fail")`, `AUDIT_SEVERITIES =
  ("blocking", "major", "minor")`, `DISSENT_DECISIONS = ("confirmed", "rejected")`,
  `AUDIT_OUTCOMES = ("accepted", "fix", "rework", "escalated")`, `AUDIT_ESCALATIONS = ("quorum",
  "round_cap")`, `SEAT_STATUSES = ("assigned", "voted", "unavailable")`; all listed by
  `taxonomy.describe()`.
- `catalog.add_model(..., family: str | None = None)`: when `family` is `None`, store
  `family_for(model)`; `catalog.set_model(..., family=...)`; a family is a kebab-case slug
  (`[a-z0-9]+(-[a-z0-9]+)*`), else `invalid_value` with `field: "family"`.
- `models add --family <name>`, `models set <agent:model> --family <name>`; every model dict
  carries `family` (null when unknown).

- [ ] **Step 1:** Write failing tests: (a) `family_for` on `claude`, `sonnet`, `fable-5.1`,
  `gemini-4-neon-high`, `claude-opus-5-5-high`, `opencode-go/minimax-m3#thinking`,
  `opencode-go/glm-5.3`, `opencode-go/kimi-k3`, `opencode-go/qwen3.8-max`,
  `opencode-go/grok-4.7`, `opencode-go/mimo-v2.6-pro`, `opencode-go/deepseek-v4-pro`,
  `gpt-oss-120b-medium`, `opencode-go/hy4`, `human`; (b) a migrated scratch database whose models
  were inserted before 005 gets the same families from the SQL seeding as `family_for` gives
  (insert the ids from (a) at version 4, migrate, compare); (c) `models add` infers the family and
  `--family` overrides it; `models set --family` changes it; a bad slug is refused; (d) the four
  audit tables and the index exist after `chanchi db migrate`.
- [ ] **Step 2:** Write the migration. Seed with one `UPDATE models SET family = CASE ... END`
  whose `WHEN` clauses test the last segment: `lower(model) LIKE 'p%' OR lower(model) LIKE '%/p%'`
  for each prefix `p` (ids with a `#variant` still start with the prefix, so no stripping is needed
  in SQL). Header comment names the design and says the lessons stage 3 takes the next free number.
- [ ] **Step 3:** Implement `taxonomy` and `catalog` changes and the two CLI flags; run the tests.
- [ ] **Step 4:** Regenerate the template: `uv run chanchi db migrate --template`; `chanchi db status`
  with a scratch `CHANCHI_DB` reports `latest_migration: 5`, `template.version: 5`.
- [ ] **Step 5:** Update the `models` entry of `FEATURE_MAP.md` (`--family`, `family` in the
  evidence) and `README.md` (*Everyday commands* gains a `models set ... --family` line).
- [ ] **Step 6:** `scripts/check` passes.

**Verification (paste each command and its last line):**
`uv run pytest -q tests/test_db.py tests/test_catalog.py tests/test_taxonomy.py`;
`CHANCHI_DB=$(mktemp -d)/c.db sh -c 'chanchi db migrate >/dev/null && chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high'`
(shows `"family": "google"`); `scripts/check`.

---

### Task 2 (S2): Harness adapters, `SYNC` resolution and the roster

**Files:** create `src/chanchi/harnesses.py`, `src/chanchi/sync.py`, `tests/test_harnesses.py`,
`tests/test_sync.py`; modify `tests/test_layers.py` (`LEAVES` gains `harnesses`).

**Interfaces produced:**
- `harnesses.HARNESSES`: one frozen dataclass row per key `claude`, `opencode`, `agy` with
  `binary`, `launch` (a function `(agent, model, effort, prompt_placeholder) -> str` returning the
  design's headless template: claude `claude -p --agent <a> --model <m> --effort <e> "<prompt>" <
  /dev/null`; opencode `opencode run --agent <a> -m <model> "<prompt>" < /dev/null` with the
  catalog model as is, variants included; agy `agy --agent <a> --model <base> --effort <e>
  -p="<prompt>" < /dev/null` where `<base>-<e>` is the catalog id), `home_dir(env, home) -> Path`
  (claude `~/.claude`; opencode `$OPENCODE_CONFIG_DIR`, else `$XDG_CONFIG_HOME/opencode`, else
  `~/.config/opencode`; agy `~/.gemini`), and `user_agent_path(env, home, name) -> Path` (claude
  `~/.claude/agents/<n>.md`; opencode `<opencode dir>/agents/<n>.md`; agy
  `~/.gemini/config/agents/<n>/agent.md`, decision D1).
- `harnesses.available(key, which=shutil.which) -> bool` and `harnesses.installed(key, env, home)
  -> bool` (its folder exists). Unknown key → `invalid_value`, `valid_values` the keys.
- `harnesses.split_agy_model(model, effort) -> str`: returns the base; `invalid_value` when the
  id does not end in `-<effort>` (design: "a roster effort that differs from the id's suffix is an
  error").
- `sync.sync_dir(env=os.environ) -> Path | None`: `CHANCHI_SYNC` when set; else
  `<main checkout>/SYNC` where the main checkout is the parent of
  `git rev-parse --path-format=absolute --git-common-dir` run in chanchi's source checkout
  (`Path(__file__).resolve().parents[2]`); `None` when the directory does not exist or git fails.
- `sync.roster(env=os.environ) -> list[dict]`: entries `{harness, model, effort}` from
  `SYNC/config/auditors.toml` (`[[auditor]]` tables, `tomllib`) when the file exists, else
  `sync.BUILTIN_ROSTER`, the four entries of the design's TOML block in that order. A bad file →
  `invalid_value` naming the file and the entry index; an unknown harness → `invalid_value` with
  `valid_values`.

- [ ] **Step 1:** Failing tests: launch strings for each harness (agy splits
  `gemini-4-neon-high` + `high` into `--model gemini-4-neon --effort high`; a mismatched effort is
  refused); `home_dir` honours `OPENCODE_CONFIG_DIR` and `XDG_CONFIG_HOME`; `available` uses the
  injected `which`; `sync_dir` with `CHANCHI_SYNC`, from a git worktree of a temporary repository
  (both checkouts resolve to the same `SYNC`), and missing; roster from a temporary
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
  commit or version, then fills seats.
- **Seat filling** (`_fill(conn, round_id, seats_needed, roster, excluded_specs, which)`): walk the
  roster in order; an entry is *available* when `harnesses.available(harness)`, its
  `harness:model` row is in the catalog and active, and the spec is not marked unavailable in this
  audit. First pass: take available entries whose family is known and not yet seated. Second pass:
  fill remaining seats with the next available entries in roster order (any family, including
  unknown). Each skipped entry is reported with its reason (`not_on_path`, `not_in_catalog` with
  the hint `chanchi models add --agent <h> --model <m> --cost <1-3>`, `inactive`,
  `unknown_family` with the hint `chanchi models set <h>:<m> --family <name>`, `unavailable`).
- `degraded` = fewer than three distinct known families among the seats whose status is not
  `unavailable` (decision D8: recomputed after every fill).
- When fewer than two seats can be filled at open, the round is closed immediately with outcome
  `escalated`, escalation `quorum`, and the audit's `outcome` is `escalated`.
- Output of `open`: audit id, round, `degraded`, `skipped`, and per seat `{seat, spec, family,
  effort, status, launch}` where `launch` is `harnesses.launch(... agent="agent-chanchi-auditor",
  prompt="<prompt>")`.
- `audits.mark_unavailable(conn, audit_id, *, round, seat, reason, roster, which)`: refused on a
  closed round (`invalid_transition`) or a seat that is not `assigned`; sets the seat
  `unavailable` with `reason`, inserts a new seat row with the same number from the roster (the
  partial index allows it), prints the new seat or `null` when the roster is exhausted.
- `audits.show(conn, audit_id) -> dict` (every round, seat including unavailable ones, vote,
  dissent, outcome, escalation, degraded) and `audits.list_audits(conn, *, kind=None, ref=None)`
  (id, kind, ref, rounds, last outcome).
- CLI: `chanchi audit open --kind <k> --ref <ref> --author <spec> (--commit <sha> | --version
  <x.y.z>) [--change <ref>] [--project <slug>]` (decision D5), `chanchi audit unavailable <id>
  --round <n> --seat <n> --reason "<error>"`, `chanchi audit show <id>`, `chanchi audit list
  [--kind <k>] [--ref <ref>]`. Each loads the roster with `sync.roster()`.

- [ ] **Step 1:** Failing tests (scratch DB, injected `which`): three families seat three distinct
  families; with the opencode binary missing, seat 3 gets `agy:gemini-4-hydrogen-high` and the round
  is degraded; an unknown-family model never counts as distinct (degraded) and is named with the
  hint; a roster entry not in the catalog is skipped with the `models add` hint; only one available
  auditor → `escalated`/`quorum`; `unavailable` refills the same seat number and recomputes
  `degraded`; `unavailable` on a voted seat or closed round is refused; `show` lists the
  unavailable row and its replacement.
- [ ] **Step 2:** Implement `audits.py` and the CLI; add the `audit` entry to `FEATURE_MAP.md`
  (sub-features `audit open`, `audit unavailable`, `audit show`, `audit list`; the scratch setup
  registers the three roster models with `models add`) and the README section.
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S2):** `uv run pytest -q tests/test_harnesses.py tests/test_sync.py tests/test_audits.py tests/test_layers.py`;
the `audit` entry of `FEATURE_MAP.md` driven by hand on a scratch database (paste the `open`
output's seat list); `scripts/check`.

---

### Task 4 (S3): `chanchi audit vote | dissent | close | round`

**Files:** modify `src/chanchi/audits.py`, `src/chanchi/cli.py`, `tests/test_audits.py`,
`FEATURE_MAP.md` (`audit` entry), `README.md`.

**Interfaces produced:**
- `audits.vote(conn, audit_id, *, round, seat, verdict, blocking, major, minor, report)`: refused
  on a closed round or a seat not `assigned`; a `pass` with `blocking > 0` or `major > 0` is
  refused (`invalid_value`, `field: "verdict"`, hint: vote `pass_with_fixes`).
- `audits.dissent(conn, audit_id, *, round, seat, finding, severity, decision, evidence)`: the
  seat must have voted; `finding` and `evidence` non-blank.
- `audits.outcome(votes, dissents, round_no) -> tuple[str, str | None]`: a pure function
  implementing the design's ordered table. An **approval** is `pass`, or `pass_with_fixes` with
  `blocking == 0 and major == 0`. Order: fewer than two voted → (`escalated`, `quorum`); at least
  two `fail` → `rework`; at least two approvals and no `confirmed` dissent of severity `blocking`
  or `major` → `accepted`; otherwise `fix`; then, when `round_no == 3` and the result is not
  `accepted`, (`escalated`, `round_cap`).
- `audits.close_round(conn, audit_id, *, round)`: refused while any seat is `assigned`; stores
  outcome and escalation on the round, the outcome on the audit, and `closed_at` on the audit when
  the outcome is `accepted` or `escalated`. Prints the outcome and, for `accepted`, the minor
  findings to fix (the approving votes' minor counts and the confirmed lone minors).
- `audits.next_round(conn, audit_id, *, commit=None, version=None, roster, which)`: refused unless
  the last round is closed with `fix` or `rework` and is below 3; copies the specs of the last
  round's non-unavailable seats into the same seat numbers when still available, refills the others
  from the roster, recomputes `degraded`.
- CLI: `chanchi audit vote <id> --round <n> --seat <n> --verdict <v> --blocking <n> --major <n>
  --minor <n> --report <path>`, `chanchi audit dissent <id> --round <n> --seat <n> --finding
  "<id: text>" --severity <s> --decision <d> --evidence "<why>"`, `chanchi audit close <id>
  --round <n>`, `chanchi audit round <id> (--commit <sha> | --version <x.y.z>)`.

- [ ] **Step 1:** Failing tests for `outcome()` as a table-driven test, one row per line of the
  design's table plus: a `pass_with_fixes` with zero blocking and zero major counts as an approval
  (owner's rule, 2026-11-21); two approvals plus a confirmed lone major → `fix`; a rejected lone
  major does not block; round 3 `fix` → `escalated`/`round_cap`; two voters, both approving →
  `accepted`. Then lifecycle tests: vote refused on a closed round; `pass` with a major refused;
  close refused with an assigned seat; `round` refused after `accepted` and after round 3; round
  numbers continue across commits (round 2 at a new commit is round 2, not 1).
- [ ] **Step 2:** A **reproduction test** of the design's history (verification plan item 2):
  open at `953ac5a`, three votes as in `docs/designs/reviews/global-items/round1-consolidation.md`
  → `fix`; round 2 at `a7a1a20` as in `round2-consolidation.md` → `fix`; round 3 at `e40d275` as
  in `round3-escalation.md` (seat 1 `pass_with_fixes` 0/0/6, seat 2 `pass` 0/0/2, seat 3
  `pass_with_fixes` 0/2/2, plus the two confirmed lone majors of seat 3 as dissents) →
  `escalated`/`round_cap`. The counts of rounds 1 and 2 are read from those files.
- [ ] **Step 3:** Implement; extend the `audit` entry of `FEATURE_MAP.md` (sub-features `audit
  vote`, `audit dissent`, `audit close`, `audit round`) and README.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S3):** `uv run pytest -q tests/test_audits.py`; the full `audit` entry of
`FEATURE_MAP.md` driven on a scratch database through `close` and `round` (paste `audit show`);
`scripts/check`.

---

### Task 5 (S4): `install` key and `chanchi agents link --user`

**Files:** modify `src/chanchi/agents_sync.py`, `src/chanchi/cli.py` (agents group),
`tests/test_agents_sync.py`, `FEATURE_MAP.md` (`agents` entry), `README.md` (*Agents*).

**Interfaces produced:**
- `AgentSource.install: str` from the optional frontmatter key `install` (`repo|user`, default
  `repo`; anything else → `invalid_value`, `valid_values`). `agents sync` still compiles every
  agent into the repository wrappers; the generated files do not change for existing sources
  (`chanchi agents sync --check` stays green on `main`'s sources).
- `render(source, header: str) -> dict[str, str]` keyed by harness kind (`claude`, `opencode`,
  `agy`); `REPO_TARGETS = {kind: lambda name: <relative path>}` reproduces today's paths; `sync()`
  uses them with the existing header.
- `agents_sync.link_user(root, *, env, home, db_dir, check=False, remove=False) -> dict`: for every
  source with `install: user`, for every harness whose folder exists
  (`harnesses.installed`), writes `render(source, header=USER_HEADER)[kind]` to
  `harnesses.user_agent_path(...)`, with `USER_HEADER = "# generated by chanchi agents link --user
  from agents/<n>/AGENT.md; do not edit"`. Reports `written`, `unchanged`, `removed`, `conflicts`,
  `skipped_harnesses`.
- **Manifest** `db_dir / "mirror.json"` (decision D3), where `db_dir` is the folder of
  `db.operational_path()`: `{"version": 1, "entries": [{"owner": "agents-link", "path", "kind",
  "sha256"}]}`. The command writes or updates only paths listed with owner `agents-link`; an
  existing file at a target path that is not in the manifest is a conflict and is never touched
  (`link_conflict` when any conflict exists, after writing nothing). Entries of another owner are
  preserved byte for byte. An entry whose source agent no longer has `install: user` is removed.
- `--check` writes nothing and fails with `stale_wrappers` when any owned file is missing or its
  hash differs, or a wanted file is not yet written. `--remove` deletes every `agents-link` entry
  (and the `<n>/` folder of an agy entry when empty) and drops them from the manifest.
- CLI: `chanchi agents link --user [--check | --remove] [<repo>]`; without `--user` →
  `invalid_value`, hint `chanchi agents link --user` (decision D4).

- [ ] **Step 1:** Failing tests with a temporary `HOME`, a scratch `CHANCHI_DB` folder and a
  temporary repository holding two sources (one `install: user`): all three harness folders present
  → three files with the user header; opencode folder missing → `skipped_harnesses: ["opencode"]`;
  `OPENCODE_CONFIG_DIR` honoured; second run all `unchanged`; hand edit → `--check` fails, a normal
  run repairs it; a foreign file at a target path → `link_conflict`, file untouched; a foreign
  manifest entry with owner `items-mirror` survives `link` and `--remove`; `--remove` leaves no
  owned file and no empty agy folder; `install: bogus` refused; `agents sync --check` on this
  repository's sources still passes.
- [ ] **Step 2:** Implement the refactor first (render per kind, `REPO_TARGETS`), keep existing
  `test_agents_sync.py` tests green, then `link_user` and the CLI.
- [ ] **Step 3:** Update the `agents` entry of `FEATURE_MAP.md` (sub-feature `agents link`, driven
  with `HOME` and `CHANCHI_DB` set to scratch folders, never the real home) and README.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S4):** `uv run pytest -q tests/test_agents_sync.py`; the `agents` entry of
`FEATURE_MAP.md` driven in a scratch `HOME` (paste the `link` output); `uv run chanchi agents sync
--check`; `scripts/check`.

---

### Task 6 (S5): `agent-chanchi-auditor`, `skill-chanchi-audit-rounds` and pointers

**Files:** create `agents/agent-chanchi-auditor/AGENT.md`,
`skills/skill-chanchi-audit-rounds/SKILL.md`; modify `agents/agent-chanchi-orchestrator/AGENT.md`,
the generated wrappers (`uv run chanchi agents sync`), `skills/skill-chanchi-verify/SKILL.md`
(*Helpers*), `tests/test_skills_content.py` (`test_all_skills_exist` gains the new skill),
`AGENTS.md` (one pointer), `README.md` (*Agents* list), `FEATURE_MAP.md` if a command example
changes. Follow `skill-chanchi-item-authoring`.

**Content:**
- `agent-chanchi-auditor`: frontmatter `name`, `description` (audits one subject against a brief
  and writes one report; never edits the subject, never reads other auditors' reports), `scope:
  both`, `profile: read-only`, `install: user`, `skills: []`. Body, harness neutral and without a
  model: read the brief; check the subject against the request and the evidence, re-running cheap
  facts locally; write only the report, at the private path the prompt gives; first line
  `VERDICT: PASS`, `VERDICT: PASS WITH FIXES` or `VERDICT: FAIL`; then a table `id | severity
  (blocking/major/minor) | where | problem | evidence | fix`; a `PASS` carries no blocking or major
  finding; in a later round, re-check its own earlier findings as RESOLVED/PARTIAL/OPEN first; never
  read `docs/designs/reviews/` reports of the current round nor any other auditor's path; never
  write a home path or a reference-project name; reporter line from `skill-chanchi-lessons`.
- `skill-chanchi-audit-rounds` (≤ 300 lines; description starts "Use when ..."): what needs an
  audit (everything the orchestrator writes; global item versions, adoption decisions and
  replication plans from later phases); one brief for three seats (request, evidence, subject at a
  commit, the private report path per seat); `chanchi audit open`, launching each seat's `launch`
  command headless with the brief as prompt, collecting reports in private scratch paths and moving
  them into `docs/designs/reviews/<topic>/` only after every seat voted; `audit vote`,
  `audit unavailable` when a harness fails (paste its error), `audit dissent` for every finding
  raised by exactly one auditor, `audit close`, `audit round` with the fix commit; a consolidation
  file per round; stop at `accepted` or `escalated` and give the human the disagreement report;
  an `accepted` round's minor fixes are applied without a new round. Every `chanchi` command it
  names must exist (`tests/test_skills_content.py`).
- `agent-chanchi-orchestrator`: `skills` gains `skill-chanchi-audit-rounds`; line 4 of the body
  points to it for the audit of everything it writes.
- `AGENTS.md` § Working Conventions: the audit sentence's "Procedure:" names
  `skill-chanchi-audit-rounds` next to the design. Stay ≤ 150 lines.
- `skill-chanchi-verify` *Helpers*: after a harness upgrade, re-run each adapter's launch template
  once with `agent-chanchi-auditor` and a trivial prompt, and run `chanchi agents link --user
  --check`.

- [ ] **Step 1:** `uv run pytest -q tests/test_skills_content.py tests/test_items.py` fails on the
  missing skill; write the agent and the skill; `uv run chanchi agents sync`; tests pass.
- [ ] **Step 2:** `scripts/check` passes (rules budget, items, privacy, agent rules).

**Verification (S5):** `uv run pytest -q tests/test_skills_content.py tests/test_items.py tests/test_rules_budget.py tests/test_agent_rules.py`;
`uv run chanchi agents sync --check`; `scripts/check`.

---

### Task 7 (S6): Harness-side verification (read-only)

Precondition, done by the orchestrator after S5 merges (the delivered items must load from the
harness side, not only exist in the repository): `uv tool install --editable .` if needed, then
`chanchi skills link --global` and `chanchi agents link --user` on the real home, pasting both
outputs into the session log.

The researcher, from a scratch folder outside any repository:
1. For each harness, runs `chanchi audit open` launch template for its seat with
   `agent-chanchi-auditor` and the prompt "State your agent name and the first line format your
   reports use, then stop." and quotes the reply (expected: the agent name and `VERDICT:`).
2. Confirms `skill-chanchi-audit-rounds` is visible to each harness (Claude Code: ask
   `claude -p --model sonnet "Which skill tells an orchestrator how to run audit rounds?" < /dev/null`;
   opencode: `opencode debug skill` or the equivalent listing; agy: `agy skills` or the equivalent),
   quoting the evidence.
3. Runs `chanchi agents link --user --check` (expected `ok: true`).
4. Writes nothing else; report with VERIFIED/UNVERIFIED per item.

### Task 8 (orchestrator): Backfill and acceptance signal

On the operational database, after S6 is accepted:
1. Ensure `opencode:opencode-go/minimax-m3`, `claude:sonnet` and `agy:gemini-4-neon-high` are in
   the catalog with families `minimax`, `anthropic`, `google` (`chanchi models list`).
2. `chanchi audit open --kind design --ref docs/designs/global-items.md --author claude:opus:high
   --commit 953ac5a`; record the three votes of round 1 from `round1-consolidation.md`, a dissent
   for each lone finding it marks (all confirmed), `audit close` → `fix`; `audit round --commit
   a7a1a20`, round 2 likewise → `fix`; `audit round --commit e40d275`, round 3 → `escalated`,
   `round_cap`. Report paths point at `docs/designs/reviews/global-items/`.
3. If the seats chanchi fills differ from the hand-run seats (a binary missing on this machine),
   mark the differing seat `unavailable` with reason `backfill: seat was <spec>` until the recorded
   spec is seated, so the seats match history.
4. Backfill this plan's own hand-run audit rounds the same way (kind `other`, ref
   `docs/superpowers/plans/2026-11-21-global-items-phase1.md`).
5. `chanchi audit show <id>` must reproduce each round's outcome (the phase-1 signal). Then
   `chanchi change close global-items-phase1` and `chanchi show global-items-phase1`.

## Risks

| Risk | Mitigation |
|---|---|
| The SQL seeding and `family_for` drift | D7 test compares them on fixed ids and on the template |
| A refactor of `agents_sync` changes committed wrappers | `agents sync --check` in the gate; S4 test asserts byte-identical repository output |
| `agents link --user` overwrites a user's own agent | manifest ownership; foreign files are conflicts and nothing is written |
| agy's "read-only" tool list includes `write_to_file` and `run_command` | accepted: the auditor must write its report; the brief and the auditor body forbid editing the subject; a hook-based guard is out of scope |
| Parallel S3 and S4 both edit `cli.py` | different parser groups; the orchestrator merges S3 first and resolves the S4 merge |
| Backfill seats differ from history | Task 8 step 3 |
