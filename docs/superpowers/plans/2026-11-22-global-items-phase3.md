# Global Items — Phase 3 (Capture and Proposal) Implementation Plan

- **Revision:** 1, to be audited with `chanchi audit` (kind `other`) by three auditors of
  different model families before any session starts.

> **For agentic workers:** each session below is one brief for `agent-chanchi-executor`. Steps use
> checkbox (`- [ ]`) syntax. Write the failing test first, then the code.

**Goal:** Ship phase 3 of `docs/designs/global-items.md` (Revision 4): migration
`006_items.sql`, `chanchi project items-dirs`, `chanchi items scan`, `chanchi items propose` and
`agent-chanchi-item-builder`. Phase 3 is done only when its signal holds: **the global skill
`skill-chanchi-global-herdr` is built from the consumer projects' copies and accepted by a
redundant audit** (design, *Adoption phases*, row 3).

**Spec:** `docs/designs/global-items.md`, sections *The improvement and promotion pipeline* (B, C,
*Data model*, E), *Where things live*, *Mirror* (name collisions), *Fitting the existing code* and
*Adoption phases* (row 3). Read them before starting any task. When this plan and the design
disagree, the design wins: stop and report the disagreement.

**Tech stack:** Python ≥ 3.11 standard library (`difflib`, `hashlib`, `json`, `os`, `pathlib`, `re`,
`tomllib`), pytest and ruff (dev only), uv.

## Global constraints

- Runtime dependencies stay empty (`[project] dependencies = []`).
- English everywhere. No home path (`/Users/<u>/`, `/home/<u>/`), email or reference-project name
  in any committed file (`tests/test_privacy.py`). Consumer projects are "a consumer project" or
  "project A/B" in committed text; real project slugs appear only in the database and in `SYNC`.
- **Run the worktree's code:** inside an executor worktree, always call `uv run chanchi ...`. A bare
  `chanchi` is the editable install of the main checkout and runs `main`'s code, not yours.
- **Executor sessions (S1-S3)** export a scratch database and a scratch `SYNC` before running
  anything: `export CHANCHI_DB="$(mktemp -d)/chanchi.db" CHANCHI_SYNC="$(mktemp -d)/SYNC"`. A
  command that writes user folders (`agents link --user`, `items mirror`) runs with a scratch home
  on that command only: `SCRATCH_HOME="$(mktemp -d)"` once, then
  `HOME="$SCRATCH_HOME" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= uv run chanchi ...`. Executors never
  touch the operational database, the main checkout's `SYNC`, the real harness folders, or any
  consumer project. Tests build their own projects as temporary git repositories and register
  them on the scratch database. Only Task 5 (the orchestrator's gate) touches the operational
  database, the real `SYNC` and the consumer projects (read-only), and it says so.
- Never launch a harness from chanchi code or tests (Principle 5).
- **Read-only on projects.** `items scan` and `items propose` open project files only for reading,
  never follow a symbolic link, and never create, modify or delete anything under a project root.
  A test asserts it (snapshot of every path, size and `mtime_ns` before and after).
- `ChanchiError` codes come from `src/chanchi/errors.py::ERROR_CODES`; this plan adds none.
- Layers (`tests/test_layers.py`): the new module `inventory.py` is a domain module; it may import
  `items`, `projects`, `sync`, `taxonomy`, `errors`, `timeutil`; `items.py` never imports
  `inventory.py` (the CLI passes scanned names into `items.check` and `items.mirror`). Only
  `projects.py` may import `subprocess`; only `cli.py` renders.
- Every new command gets a `FEATURE_MAP.md` entry or sub-feature (`tests/test_feature_map.py`) and
  a line in `README.md`. A migration commits the SQL file and the regenerated
  `src/chanchi/data/template.db` together (`uv run chanchi db migrate --template`).
- Executors never commit, merge, push or write chanchi records. They report each verification as
  the exact command plus its last output line, list every changed file, and stop at any gap.
- Last step of every session: `scripts/check` passes.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | Migration `006_items.sql` is the design's four tables verbatim (`project_item_dirs`, `project_items`, `item_proposals`, `item_decisions`), plus `CREATE INDEX project_items_name ON project_items (kind, name)` and `CREATE UNIQUE INDEX item_proposals_open ON item_proposals (kind, name) WHERE status = 'open'`. Enumerations are validated in code (`taxonomy.PROJECT_ITEM_KINDS = ("agent", "skill", "hook", "rule")`, `taxonomy.PROPOSAL_STATUSES = ("open", "built", "rejected")`), like migration 004. `item_decisions` stays empty until phase 4 | The design's model; one open proposal per name keeps later runs and the builder on the same row |
| D2 | **Scanned projects** are the registered ones (`registered_at IS NOT NULL`). Root: the first `project_locators` row (kind `path`, lowest id) whose value is an existing directory. A registered project with no existing root is listed under `missing` and its stored rows are kept unchanged | Projects move between machines; a missing root must not erase the inventory |
| D3 | **Scan roots** per project: the seven defaults `.agents/skills`, `.claude/skills`, `.opencode/skills`, `agents`, `.claude/agents`, `.opencode/agents`, `.agents/agents`, then the project's `project_item_dirs` rows, each walked only when it is a real directory (not a link). **Walk:** depth-first, sorted names, at most 4 directory levels below the root; skip entries whose name starts with `.` (below the root itself), `node_modules`, and every symbolic link (file or directory; listed under `skipped` with reason `symlink`). A directory that holds `SKILL.md` is a **skill**; one that holds `AGENT.md` is an **agent**; the walk does not descend into an item directory. In the three harness agent folders (`.claude/agents`, `.opencode/agents`, `.agents/agents`, and only directly in them) each regular `*.md` file is a single-file **agent**. Paths stored relative to the project root in POSIX form; a path reached from two roots (for example `agents/skills/x` from `agents`) is stored once | Consumer projects nest skills in category folders (`<root>/<category>/<name>/SKILL.md`) and keep canonical copies under `agents/skills`; skill links to chanchi's own skills are symbolic links and are not the project's items |
| D4 | **Fingerprint** per item: `name` = the frontmatter `name` when present and non-empty, else the directory name (skill or `AGENT.md` agent) or the file stem (single-file agent); `sha256` = `items.content_hash(<dir>)` for a directory item (a symlink inside makes it `skipped`, reason `symlink`) and the SHA-256 of the file bytes for a single-file agent; `lines` = line count of the main file (`SKILL.md`, `AGENT.md` or the file); `description` = `inventory.description(text)`, a lenient reader that never raises: the frontmatter `description` value, with an empty, `>`, `>-`, `|` or `|-` value followed by more-indented lines joined with single spaces, one pair of surrounding quotes stripped, `None` when absent or unreadable. A file that is not UTF-8 is `skipped` (reason `unreadable`). No item text other than `description` reaches the database | The design's "one fingerprint per item, never item text"; consumer descriptions use folded multi-line values, which the strict `items.read_frontmatter` refuses |
| D5 | **Scan writes** in one transaction per project: insert new paths, update changed rows (`sha256`, `lines`, `description`, `name`, `kind`), delete rows whose path is gone, set `scanned_at` on every row it saw. Output `{projects: [{project, root, items, added, changed, removed, skipped: [{path, reason}]}], missing: [slug]}`. `--project <slug>` limits the scan to one registered project (`project_not_registered` otherwise) | Idempotent; a second run reports zero added, changed and removed |
| D6 | **`project items-dirs`** runs in the project (detected from the working directory like `project show`; `--project <slug>` overrides) and requires a registered project. `--add <path>`: normalized relative POSIX path, refused (`invalid_value`, `field: "path"`) when absolute, empty, containing `..`, equal to a default root (D3), not an existing directory under the root, or a symbolic link; adding an existing row answers `added: false`. `--remove <path>` deletes the row (`invalid_value` when absent). Without flags it lists. Output `{project, defaults: [...], dirs: [...], added|removed}` | The design's agnostic folders, guarded so a scan never leaves the project |
| D7 | **Project item collisions** (design, *Mirror*, "from phase 3, when scan data exists"): `items.check(sync_root, *, own_names, project_names=())` and `items.mirror(..., project_names=())` report the new problem code `project_item_collision` for a global item whose name equals a scanned project item's name. The CLI passes `inventory.project_item_names(conn)`; `items publish` and `items mirror` refuse on it like on any check problem | Closes design verification item 7's project half |
| D8 | **Candidates** (`inventory.propose`). Copies come from `project_items` of registered projects with kind `skill` or `agent`. Excluded names: chanchi's own items (`items.own_names()`), names containing `-chanchi-global-`, and names starting with `skill-chanchi-` or `agent-chanchi-`. Per project and `(kind, lowercase name)` the **canonical copy** is the one with the most lines (ties: shortest path, then alphabetical); the others are `aliases`. Rules, in order: **same name** — the same `(kind, lowercase name)` canonical in at least two projects; **description overlap** — among canonical copies not already in a same-name candidate, same kind, different names, both descriptions with at least 5 tokens (lowercase `[a-z0-9]+` of length ≥ 4), token Jaccard ≥ 0.5, from different projects; pairs are grouped transitively and a group spanning at least two projects is one candidate named after its copy with the most lines; **lessons** — lessons with `generality = 'agnostic'`, `target_kind` in (`skill`, `role`), status `pending` or `approved`, whose `target` matches `^(skill|role|agent)\s+([a-z0-9][a-z0-9._-]*)(\s+\(new\))?$`, from at least two distinct non-null `origin_project_id`s, grouped by kind (`skill` → skill, `role`/`agent` → agent) and lowercase name. A lessons group whose name equals a same-name or overlap candidate's name joins that candidate. The design's third rule (adopters keep wrapping a global item) needs phase 4 decisions and is not built here | The design's first two rules, made checkable; text similarity of bodies is not used (design, *Independent uses*) |
| D9 | **Independent uses.** For every pair of canonical copies in a candidate, `inventory.longest_shared_block(a_lines, b_lines)` = `difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))` over the lines of the main files without their line endings; `share = size / min(len(a), len(b))`. Copies with `share >= vendored_share` are joined (union-find); `uses = number of clusters + number of approved lessons in the candidate`. `SYNC/config/promotion.toml` accepts exactly `min_uses` (integer ≥ 1, default 3) and `vendored_share` (number in (0, 1], default 0.5); any other key, type or a TOML error is `invalid_value`, `field: "promotion"`; a missing file or missing `SYNC` uses the defaults. `eligible = uses >= min_uses or owner_promoted` | The design's rule and its two keys. Measured on the consumer copies on 2026-11-22: the canonical herdr copies have 323 and 448 lines and share a 212-line block (share 0.66), so they count as one use |
| D10 | **Freshness.** `propose` reads each canonical copy's main file at `<root>/<path>` (read-only, no link followed) and recomputes its fingerprint; if a copy is missing or its `sha256` differs from the scan, `propose` stores nothing and fails with `missing_prerequisite`, `details: {"stale": [...]}`, hint `chanchi items scan` | Uses are counted from the files the scan recorded, never from a different text |
| D11 | **Storage.** Proposed name: `<kind>-chanchi-global-<name>` where `<name>` is the candidate name lowercased with every run of characters outside `[a-z0-9]` replaced by `-` and stripped of `-` at both ends. One open row per `(kind, name)` (D1): a new candidate inserts `status = 'open'`; an existing open row gets its `evidence`, `uses` and `updated_at` replaced and keeps `owner_promoted`; a candidate whose name has a `built` or `rejected` row and no open row is listed under `closed` and not stored again; an open row that this run did not produce is listed under `not_found` and left unchanged. Evidence JSON: `{"rules": [...], "copies": [{"project", "kind", "name", "path", "sha256", "lines", "aliases": [paths]}], "pairs": [{"a": "<project>:<path>", "b": "...", "block_lines", "a_start", "b_start", "share"}], "clusters": [["<project>:<path>", ...]], "lessons": [{"id", "project", "status"}], "min_uses", "vendored_share"}`; `a_start`/`b_start` are 1-based line numbers | The same candidate keeps one id across runs; the builder needs the shared block's place to keep vendored text out |
| D12 | **Owner promotion.** `items propose --owner-promote <global-name>` sets `owner_promoted = 1` on that candidate in the same run (refused with `invalid_value`, `field: "owner_promote"`, when this run produces no candidate of that name); once set it is never cleared by a later run. The design's first experiment (herdr) uses it | The design: "`items propose` records it as owner-promoted" |
| D13 | **Proposal commands.** `items propose [--owner-promote <name>]` → `{proposals: [...], closed: [...], not_found: [...], min_uses, vendored_share}`. `items proposals [--status open|built|rejected] [--id <n>]` reads stored rows; with `--id` each copy also carries `abs_path` = `<project root>/<path>` resolved at print time (`null` when the root is missing). `items proposal-status <id> --status built --global-item <name>` (the name must be an existing global item in `SYNC/ITEMS` of the proposal's kind, any status) or `--status rejected`; only `open` rows change (`invalid_transition` otherwise; unknown id is `invalid_value`, `field: "id"`). All three are `project=False` | The builder and the audit refer to a stored candidate by id; `built` links it to its global item |
| D14 | **Item audit reports** for global items live in `SYNC/reviews/<item-name>/<version>/` (round reports and consolidations), never in this repository: they quote project copies. `SYNC/reviews/` is outside `SYNC/ITEMS/`, so `items check` ignores it | Privacy (`tests/test_privacy.py`, AGENTS.md); users own their results |
| D15 | **The builder's text is part of this plan** (Task 4 below, verbatim), so the plan audit reviews it; S3 installs it unchanged | Everything the orchestrator writes is audited before merge (AGENTS.md) |
| D16 | **Publishing `skill-chanchi-global-herdr` and mirroring it are not part of phase 3.** The signal is "built and accepted". Publishing makes it visible in every project, including the consumer projects that still have their own `herdr` skill, before phase 4's adoption exists; the gate asks the owner and publishes only on a yes | Global items are available, never imposed (Principle 2); an outward-facing action is the owner's decision |

## File map

| File | Session | Responsibility |
|---|---|---|
| `src/chanchi/migrations/006_items.sql`, `src/chanchi/data/template.db`, `src/chanchi/taxonomy.py`, `src/chanchi/inventory.py` (new: dirs, walk, fingerprint, scan), `src/chanchi/items.py` (D7), `src/chanchi/cli.py`, `tests/test_inventory.py` (new), `tests/test_db.py`, `tests/test_items_global.py`, `tests/test_mirror.py`, `AGENTS.md` (one line), `FEATURE_MAP.md`, `README.md` | S1 | migration, `project items-dirs`, `items scan`, project item collisions |
| `src/chanchi/inventory.py` (propose), `src/chanchi/sync.py` (`promotion()`), `src/chanchi/cli.py`, `tests/test_propose.py` (new), `tests/test_sync.py`, `FEATURE_MAP.md`, `README.md` | S2 | `items propose`, `items proposals`, `items proposal-status`, `promotion.toml` |
| `agents/agent-chanchi-item-builder/AGENT.md` (new), generated wrappers (`.claude/agents/`, `.opencode/agents/`, `.agents/agents/`), `README.md`, `FEATURE_MAP.md` (`agents` entry gotcha only if needed) | S3 | the item builder |

## Sessions

| Session | Tasks | Depends on | task_type / complexity |
|---|---|---|---|
| S1 | 1, 2 | plan merged | `business-logic` high (migration, new domain module, CLI, items change, > 10 cases) |
| S2 | 3 | S1 merged | `business-logic` medium (one domain rule set, CLI, config reader, ~6 files) |
| S3 | 4 | plan merged (parallel with S1) | `docs` low (one agent source and its generated wrappers, README) |
| — | 5 | S1, S2, S3 merged | orchestrator: the gate (operational database, real `SYNC`, builder session, item audit) |

S1 and S3 touch disjoint files except `README.md` (different sections; the orchestrator resolves a
textual conflict at merge). S2 needs S1's tables and `inventory.py`. This plan is merged to `main`
before any worktree is created.

Session protocol (chanchi change `global-items-phase3`, available
`agy:gemini-4-hydrogen-{low,medium,high,xhigh}` and `claude:sonnet:{low,medium,high,xhigh,max}`;
explore budget `max(1, floor(3/4)) = 1`). The orchestrator re-runs `chanchi recommend` at each
dispatch and updates the line when the result changed:

- S1 `business-logic` high — chanchi: recommended agy:gemini-4-hydrogen-high:high (98.06, low confidence, task_type) · chosen claude:sonnet:high · reason: at high complexity task_type data is weak evidence; claude:sonnet:high has 12 sessions at task_type+complexity (ok confidence)
- S2 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (98.51, low confidence, task_type+complexity) · chosen agy:gemini-4-hydrogen-high:high
- S3 `docs` low — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.9, ok confidence, global) · chosen agy:gemini-4-hydrogen-medium:medium · explore: agy:gemini-4-hydrogen-medium:medium (S3 blocks no executor session; its text is fixed by this plan, so a weak result costs one retry)

Each executor works in its own worktree `.claude/worktrees/chanchi-gi3-sN` on branch
`feat/gi3-sN`, created from `main` after its dependencies merged. The orchestrator commits and
merges each session with `git merge --no-ff`.

---

### Task 1 (S1): Migration 006 and `project items-dirs`

**Files:** create `src/chanchi/migrations/006_items.sql`, `src/chanchi/inventory.py`,
`tests/test_inventory.py`; regenerate `src/chanchi/data/template.db`; modify
`src/chanchi/taxonomy.py`, `src/chanchi/cli.py` (`project items-dirs`), `tests/test_db.py` only
if it pins the latest migration number, `FEATURE_MAP.md` (`project` entry), `README.md`.

**Interfaces produced:**
- `taxonomy.PROJECT_ITEM_KINDS`, `taxonomy.PROPOSAL_STATUSES` (D1), listed by `taxonomy.describe()`.
- `inventory.DEFAULT_ROOTS` (the seven D3 roots, in that order), `inventory.AGENT_FILE_ROOTS`
  (`.claude/agents`, `.opencode/agents`, `.agents/agents`).
- `inventory.item_dirs(conn, project_id) -> list[str]`, `inventory.add_item_dir(conn, project_id,
  root: Path, path: str) -> dict`, `inventory.remove_item_dir(conn, project_id, path) -> dict` (D6).
- CLI: `chanchi project items-dirs [--add <path> | --remove <path>] [--project <slug>]`.

- [ ] **Step 1:** Failing tests: the migration creates the four tables and both indexes;
  `uv run chanchi db migrate --template` leaves `template.db` matching the migrations
  (`tests/test_db.py`); `items-dirs` lists the defaults and no rows for a fresh registered project;
  `--add docs/agents` stores `docs/agents`; adding it again answers `added: false`; `--add` of an
  absolute path, `../x`, `a/../b`, an empty string, a default root, a missing directory and a
  symbolic link to a directory are each refused with `field: "path"`; `--remove` of a stored path
  deletes it and of an unknown path is refused; an unregistered project is
  `project_not_registered`.
- [ ] **Step 2:** Implement.

### Task 2 (S1): `items scan` and project item collisions

**Files:** modify `src/chanchi/inventory.py`, `src/chanchi/items.py`, `src/chanchi/cli.py`,
`tests/test_inventory.py`, `tests/test_items_global.py`, `tests/test_mirror.py`, `AGENTS.md`,
`FEATURE_MAP.md` (`items` entry), `README.md`.

**Interfaces produced:**
- `inventory.description(text) -> str | None` (D4).
- `inventory.walk(root: Path, rel_roots: list[str]) -> tuple[list[dict], list[dict]]`: items
  `{kind, name, path, sha256, lines, description}` and skipped `{path, reason}` (D3, D4).
- `inventory.scan(conn, *, project: str | None = None, now: str | None = None) -> dict` (D2, D5).
- `inventory.project_item_names(conn) -> list[str]`: distinct names in `project_items`.
- `items.check(..., project_names=())` and `items.mirror(..., project_names=())` (D7); the CLI's
  `items check`, `items publish` and `items mirror` pass `inventory.project_item_names(conn)`.
- CLI: `chanchi items scan [--project <slug>]` (`project=False`).
- `AGENTS.md` § Items and Other Projects: the sentence "chanchi writes nothing into their
  repository except skill links" becomes "chanchi writes nothing into their repository except
  skill links, and `chanchi items scan` reads their item folders without writing".

- [ ] **Step 1:** Failing tests, on two temporary git repositories registered on the scratch
  database (project A and project B): A holds `.agents/skills/workflow/tool-x/SKILL.md` (nested
  category), a stub `.claude/skills/workflow/tool-x/SKILL.md`, `.claude/agents/helper.md`, and a
  symbolic link `.claude/skills/skill-chanchi-verify` to a folder outside the project; B holds
  `agents/skills/tool-x/SKILL.md` with a folded multi-line `description: >` and an
  `agents/reviewer/AGENT.md`, plus `.claude/skills/node_modules/x/SKILL.md` and
  `.claude/skills/.hidden/SKILL.md`. Assert: A's two `tool-x` copies, `helper` (single-file agent)
  and nothing for the link (listed `skipped`, `symlink`); B's `tool-x` with its description joined
  into one line, `reviewer` (agent), nothing under `node_modules` or `.hidden`; `agents/skills/tool-x`
  stored once; `sha256` of a directory item equals `items.content_hash`; `lines` counts the main
  file; a non-UTF-8 `SKILL.md` is `skipped` (`unreadable`); a directory five levels below a root is
  not reached; an item dir added with `items-dirs --add` is scanned; a second scan reports zero
  added, changed and removed; editing a file reports one changed row; deleting one reports one
  removed row; a registered project whose locator folder was removed is listed under `missing`
  and keeps its rows; `--project` limits the scan; the snapshot of every path, size and
  `mtime_ns` under both project roots is identical before and after `scan`. `items check`
  reports `project_item_collision` for a global item named like a scanned project item, and
  `items mirror` refuses then and writes nothing.
- [ ] **Step 2:** Implement; `AGENTS.md` line; `FEATURE_MAP.md`: `items scan` and
  `project items-dirs` sub-features, driven on scratch projects created with `git init` in
  `mktemp -d` folders and registered with `uv run chanchi project register` run inside them;
  README.
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S1):** `uv run pytest -q tests/test_inventory.py tests/test_db.py tests/test_items_global.py tests/test_mirror.py tests/test_layers.py tests/test_rules_budget.py`;
the `FEATURE_MAP.md` sub-features driven with `uv run chanchi` (paste `items scan` twice, the
second showing zero added, changed and removed); `scripts/check`.

---

### Task 3 (S2): `items propose`, `items proposals`, `items proposal-status`

**Files:** modify `src/chanchi/inventory.py`, `src/chanchi/sync.py`, `src/chanchi/cli.py`,
`tests/test_sync.py`; create `tests/test_propose.py`; modify `FEATURE_MAP.md` (`items` entry),
`README.md`.

S2 starts from a `main` that has S1.

**Interfaces produced:**
- `sync.promotion(env=None, *, repo_root=None) -> dict`: `{min_uses, vendored_share}` (D9).
- `inventory.longest_shared_block(a: list[str], b: list[str]) -> tuple[int, int, int]`:
  `(a_start, b_start, size)`, 0-based starts (D9; evidence stores them 1-based).
- `inventory.propose(conn, *, own_names, config, owner_promote=None, now=None) -> dict`
  (D8-D12).
- `inventory.proposals(conn, *, status=None, proposal_id=None) -> list[dict]` (D13).
- `inventory.set_proposal_status(conn, sync_root, proposal_id, *, status, global_item=None) -> dict`
  (D13).
- CLI: `chanchi items propose [--owner-promote <name>]`, `chanchi items proposals [--status ...]
  [--id <n>]`, `chanchi items proposal-status <id> --status built|rejected [--global-item <name>]`
  (`project=False`).

- [ ] **Step 1:** Failing tests, on registered temporary projects A, B and C:
  - `promotion()` defaults without `SYNC` and without the file; reads both keys; refuses an
    unknown key, `min_uses = 0`, `vendored_share = 1.5`, a string value, broken TOML.
  - `longest_shared_block` on hand-written lists (including no shared line → size 0).
  - Same name: `tool-x` in A and B, whose main files share a block covering ≥ 50% of the shorter
    → one candidate `skill-chanchi-global-tool-x`, `rules: ["same_name"]`, one cluster,
    `uses = 1`, `eligible: false`, evidence with the pair's 1-based starts and share; the same
    files with a block below the share → two clusters, `uses = 2`; with `promotion.toml`
    `min_uses = 2` → `eligible: true`. A's stub copy is an alias, never canonical.
  - A name present in only one project → no candidate; chanchi's own names, `skill-chanchi-*`
    and `*-chanchi-global-*` names → never candidates.
  - Description overlap: `deploy-check` in A and `release-verify` in C with descriptions of
    Jaccard ≥ 0.5 → one candidate named after the longer copy, `rules: ["description_overlap"]`;
    below 0.5, or under 5 tokens → none.
  - Lessons: two agnostic approved lessons from A and B with `target: "skill tool-y (new)"` → one
    candidate `skill-chanchi-global-tool-y`, `rules: ["lessons"]`, `uses = 2`; pending lessons
    create the candidate but add no use; lessons from one project only, `project` generality, or
    `target_kind: hook` → none; lessons naming `tool-x` join the same-name candidate.
  - Storage: a second run updates the same row (same id, new `updated_at`), never inserts a
    duplicate; `--owner-promote skill-chanchi-global-tool-x` sets `owner_promoted` and
    `eligible: true`, and a later run without the flag keeps it; `--owner-promote` of a name with
    no candidate is refused; after `proposal-status <id> --status built --global-item
    skill-chanchi-global-tool-x` (a draft fixture in the scratch `SYNC`) the next run lists the
    candidate under `closed`; `built` with a missing item, a name of another kind or no
    `--global-item`, and any change of a `built` or `rejected` row are refused.
  - Freshness: editing A's canonical copy after the scan makes `propose` fail with
    `missing_prerequisite`, `details.stale`, and store nothing.
  - `proposals --id` prints `abs_path` for each copy and `null` when the root is missing.
  - The read-only snapshot of Task 2 holds around `propose` too.
- [ ] **Step 2:** Implement; `FEATURE_MAP.md` sub-features (`items propose`, `items proposals`,
  `items proposal-status`) driven on the scratch projects of S1's entry; README (the
  `promotion.toml` keys and the owner-promotion flag).
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S2):** `uv run pytest -q tests/test_propose.py tests/test_sync.py tests/test_inventory.py tests/test_layers.py`;
the `items` sub-features driven with `uv run chanchi` through `items scan`, `items propose
--owner-promote ...`, `items proposals --id ...` and `items proposal-status ... --status rejected`
(paste each output); `scripts/check`.

---

### Task 4 (S3): `agent-chanchi-item-builder`

**Files:** create `agents/agent-chanchi-item-builder/AGENT.md` with exactly the text below; run
`uv run chanchi agents sync` and keep the generated wrappers; modify `README.md` (agents list).

```markdown
---
name: agent-chanchi-item-builder
description: Builds one global item draft in SYNC/ITEMS from a stored chanchi proposal and its evidence; never edits a project, never publishes, never writes chanchi records.
scope: both
profile: workspace-write
install: user
skills: []
---

# Item builder

You turn one chanchi proposal into one global item draft. The prompt gives you the proposal id,
the item version to write (default `0.1.0`), and a private path for your report.

## Read the evidence

1. `chanchi items proposals --id <id>`: the proposed name, kind, the project copies (with
   `abs_path`), the shared blocks between copies (`pairs`), the clusters and the lesson ids.
2. Read every copy at its `abs_path` and every alias next to it. Read each lesson with
   `chanchi lesson show <id>`. Read nothing else from a project and change nothing in it.
3. `chanchi sync status`: the `SYNC` path. The item goes in
   `SYNC/ITEMS/<kind>s/<proposed name>/` (`skills/` or `agents/`).

## Write the item

4. Keep the **shared core**: each rule or procedure that at least two copies state (in any words)
   or that a lesson asks for. Write it once, in English, harness agnostic: no project name, slug,
   repository path, home path, person, or rule that only one project needs.
5. Leave **vendored text** out. A shared block in `pairs` whose copies say they are generated
   from an upstream source (for example "vendored from `<tool> --<flag>`") is not copied, even in
   part: the item tells the agent to read that source at run time, naming the exact command, and
   says that the installed tool is the authority.
6. A skill is `SKILL.md`; an agent is `AGENT.md`. Frontmatter, one `key: value` per line:
   - skill: `name` (the directory name), `description` (one line: what it does and when to use
     it), then `metadata:` with the indented lines `  version: "<version>"` and
     `  status: "draft"`;
   - agent: `name`, `description`, `scope`, `profile`, `install: user`, `skills: [...]`,
     `version: <version>`, `status: draft`.
   Keep the body under 300 lines; move detail to `references/` inside the item.
7. `CHANGELOG.md`: a section `## <version> — <YYYY-MM-DD>` that says what the version holds and
   where it came from, naming copies only as "copy A", "copy B" and lessons by id.
8. Never write `status: published` or `retired`, never run `chanchi items publish`,
   `chanchi items mirror`, `chanchi audit` or any command that records in chanchi, and never touch
   another item. A new version of an existing item is written only when the prompt asks for it.

## Check and report

9. `chanchi items check` passes, and `chanchi items list` shows the item as `draft`.
10. Write the report at the private path: the item path, version and content hash (from
    `chanchi items list`); for each section of the item, the copies (A, B, ...) or lessons it
    came from; what you left out and why (project-specific rules, which belong in a project's
    wrapper; vendored text, with the source command); and every check you ran as the exact
    command plus its last output line.
11. No project name, slug, home path or email in the item or the report.
12. If something went wrong, say so in your report; do not record it in chanchi.
```

- [ ] **Step 1:** Create the source with the text above, byte for byte.
- [ ] **Step 2:** `uv run chanchi agents sync`; `uv run chanchi agents sync --check` passes;
  `HOME="$SCRATCH_HOME" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= uv run chanchi agents link --user`
  with `$SCRATCH_HOME/.claude`, `$SCRATCH_HOME/.config/opencode` and `$SCRATCH_HOME/.gemini`
  created first lists `agent-chanchi-item-builder` for all three harnesses.
- [ ] **Step 3:** README: the agent in the agents list with one line.
- [ ] **Step 4:** `scripts/check` passes (`tests/test_items.py`, `tests/test_agents_sync.py`,
  `tests/test_rules_budget.py`, `tests/test_privacy.py` included).

**Verification (S3):** `uv run chanchi agents sync --check`; the scratch-home `agents link --user`
output; `uv run pytest -q tests/test_items.py tests/test_agents_sync.py tests/test_privacy.py`;
`scripts/check`.

---

### Task 5 (orchestrator): The gate — the phase signal

Runs from the main checkout after S1, S2 and S3 merged, with the installed `chanchi` (`main`'s
code). It **uses the operational database, the real `SYNC` and reads the consumer projects**;
it writes nothing into any consumer project.

0. **Backup and migrate.** Copy the operational database to a scratch folder; `chanchi db
   migrate`; `chanchi db status` shows version 6. `chanchi agents link --user` installs the
   builder; `chanchi agents link --user --check` passes.
1. **Register.** In each consumer project's main checkout: save `git status --porcelain`, then
   `chanchi project register` (database only). `chanchi project list` shows both.
2. **Scan.** `chanchi items scan`. Pass: each project reports its `herdr` copies (canonical and
   stubs) and its other items; `git status --porcelain` of both projects is unchanged.
3. **Propose.** `chanchi items propose --owner-promote skill-chanchi-global-herdr`. Pass: the
   candidate exists with `rules` containing `same_name`, one cluster (share ≥ 0.5, D9),
   `uses = 1`, `owner_promoted = 1`, `eligible: true`. Record every other candidate in the gate
   record; they are evidence only and nothing is built for them in this phase.
4. **Build (session S4).** `chanchi recommend --task-type docs --complexity medium` with the
   available executors; `chanchi session start global-items-phase3 S4 --executor <chosen>
   --task-type docs --complexity medium --tasks 1 --tags agent-chanchi-item-builder`. Launch the
   builder headless from the main checkout with the proposal id, version `0.1.0` and a private
   report path under `.claude/worktrees/research/gi3-build/`, giving it read access to the two
   consumer projects and write access to the real `SYNC` target (`--add-dir` for each). Audit
   the report like any session (`skill-chanchi-session-audit`): re-run `chanchi items check` and
   `chanchi items list`; search the item for each project slug, each consumer path and `/Users/`
   (must find nothing); compute the longest shared block between the item's `SKILL.md` and each
   copy's vendored range (must be under 10 lines); confirm the item names the upstream command
   for the vendored text. Record the verdict.
5. **Item audit.** `chanchi audit open --kind item --ref skill-chanchi-global-herdr --version
   0.1.0 --author <builder spec> --change global-items-phase3`; three seats from the usual roster
   (claude sonnet, agy gemini-4-neon, opencode minimax-m3); one brief (request: the design's
   section C and this task; evidence: the proposal's copies, read-only, and the design's
   *Independent uses*); reports in private scratch paths, moved to
   `SYNC/reviews/skill-chanchi-global-herdr/0.1.0/` after all seats voted (D14). Follow
   `skill-chanchi-audit-rounds` to the end: a `fix` round is applied by a new builder attempt
   (`--retry-reason plan_fix` or `executor_failure` as the finding says) at the same version, then
   `chanchi audit round <id> --version 0.1.0` (the hash changes, the version does not); an
   escalation goes to the owner. **The phase signal holds when the audit closes `accepted`.**
6. **Close the proposal.** `chanchi items proposal-status <id> --status built --global-item
   skill-chanchi-global-herdr`. Ask the owner whether to publish and mirror now (D16); only on a
   yes: `chanchi items publish skill-chanchi-global-herdr --audit <id>` and `chanchi items
   mirror`.
7. **Record.** `docs/designs/reviews/global-items-phase3/gate.md`: each step's command and the
   relevant output, consumer projects named "project A" and "project B", no home path; then
   `chanchi change close global-items-phase3` and `chanchi show global-items-phase3`.

**Out of this plan:** phase 4 (`items inbox/decide`, `skill-chanchi-item-adoption`) and the
design's third proposal rule; editing any consumer project; lessons #1-#7, which stay pending
(this plan neither reviews nor applies any of them).

## Verification plan (phase 3)

1. Migration 006 and the template (`tests/test_db.py`).
2. `project items-dirs` refusals and storage (Task 1).
3. `items scan`: nested categories, single-file agents, symbolic links skipped, folded
   descriptions, depth limit, idempotence, missing roots, and the read-only snapshot (Task 2).
4. Project item collisions in `items check` and `items mirror` (design verification item 7, the
   project half).
5. `items propose`: the three rules built here, independent uses with vendored copies counted
   once, `promotion.toml`, owner promotion, storage across runs, freshness (Task 3).
6. The builder source compiles for all three harnesses (Task 4).
7. The gate: `skill-chanchi-global-herdr` built from the consumer copies with no project name and
   no vendored text, and accepted by a redundant item audit (Task 5).

## Risks

| Risk | Mitigation |
|---|---|
| The scan writes into a project or follows a link out of it | No link followed (D3); the snapshot test; the gate compares `git status` |
| Vendored upstream text lands in the global item | Evidence carries each shared block's place (D11); the builder leaves it out (step 5); the gate measures it |
| A project name or path leaks into the global item or this repository | Builder rules 4 and 11; the gate greps the item; item audit reports stay in `SYNC/reviews/` (D14); `tests/test_privacy.py` |
| A stale scan produces wrong uses | Freshness check (D10) |
| Description overlap produces noise | Strict thresholds (D8); a candidate is evidence, never an item |
| The global skill shadows a project's own skill before adoption exists | Distinct names (Principle 4); publishing deferred to the owner (D16) |
