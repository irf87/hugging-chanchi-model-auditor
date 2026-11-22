# Global Items — Phase 2 (SYNC and ITEMS) Implementation Plan

- **Revision:** 4, accepted in audit round 3 with its minor fixes applied (rounds 1 and 2 `fix`; chanchi audit 3,
  [round1-consolidation.md](../../designs/reviews/global-items-phase2-plan/round1-consolidation.md),
  [round2-consolidation.md](../../designs/reviews/global-items-phase2-plan/round2-consolidation.md),
  [round3-consolidation.md](../../designs/reviews/global-items-phase2-plan/round3-consolidation.md))

> **For agentic workers:** each session below is one brief for `agent-chanchi-executor`. Steps use
> checkbox (`- [ ]`) syntax. Write the failing test first, then the code.

**Goal:** Ship phase 2 of `docs/designs/global-items.md` (Revision 4): `chanchi sync init/status`,
the reserved slug `global`, `chanchi items check/list/publish/retire`, versions, status and content
hashes, `retired.json`, and `chanchi items mirror` with its manifest. Phase 2 is done only when
the design's verification item 9 passes: one headless run per harness loads a published test
global skill through the mirror.

**Spec:** `docs/designs/global-items.md`, sections *Where things live* (all subsections),
*Fitting the existing code*, *Adoption phases* (row 2) and *Verification plan* items 3 to 9. Read
them before starting any task. When this plan and the design disagree, the design wins: stop and
report the disagreement.

**Tech stack:** Python ≥ 3.11 standard library (`hashlib`, `json`, `os`, `pathlib`, `re`), pytest
and ruff (dev only), uv.

## Global constraints

- Runtime dependencies stay empty (`[project] dependencies = []`).
- English everywhere. No home path (`/Users/<u>/`, `/home/<u>/`), email or reference-project name
  in any committed file (`tests/test_privacy.py`).
- **Run the worktree's code:** inside an executor worktree, always call `uv run chanchi ...`. A bare
  `chanchi` is the editable install of the main checkout and runs `main`'s code, not yours.
- **Executor sessions (S1-S3)** export a scratch database and a scratch `SYNC` before running
  anything: `export CHANCHI_DB="$(mktemp -d)/chanchi.db" CHANCHI_SYNC="$(mktemp -d)/SYNC"`. Any
  command that writes user folders (`items mirror`, `skills link`, `agents link`) runs with a
  scratch home set on that command only, so `uv` keeps its cache:
  `SCRATCH_HOME="$(mktemp -d)"` once, then `HOME="$SCRATCH_HOME" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= uv run chanchi ...`.
  They never touch the operational database, the main checkout's `SYNC`, or the real `~/.claude`,
  `~/.config/opencode`, `~/.gemini`, `~/.agents`. Tests build their own temporary folders and never
  depend on the machine. Only Task 5 (the orchestrator's gate) writes to the real home, and it says
  so.
- Never launch a harness from chanchi code or tests: chanchi only checks `shutil.which`
  (Principle 5).
- `ChanchiError` codes come from `src/chanchi/errors.py::ERROR_CODES`. Lifecycle refusals (publish
  a retired item, retire twice) use `invalid_transition`; a missing `SYNC` is
  `missing_prerequisite` with the hint `chanchi sync init`; an existing path the command must not
  replace is `link_conflict`.
- Layers (`tests/test_layers.py`): `items.py` and `sync.py` are domain modules; only `cli.py`
  renders. `items.py` never imports `audits.py` (it reads the audit tables with SQL);
  `audits.py` may import `items.py`. Only `projects.py` may import `subprocess`.
- Every new command gets a `FEATURE_MAP.md` entry (`tests/test_feature_map.py`) and a line in
  `README.md`.
- **Global item names in committed files.** `tests/test_items.py::test_references_resolve` fails
  on any `skill-chanchi-*` or `agent-chanchi-*` name in `README.md`, `FEATURE_MAP.md`, `AGENTS.md`,
  `agents/` or `skills/` that is not an item of this repository. Global items never live here, so
  S1 teaches that check to skip names of the form `<kind>-chanchi-global` and
  `<kind>-chanchi-global-<name>`. S2 and S3 start after S1 merged, so they may write concrete
  global names there. Before that skip exists, the only safe text is the fully literal
  `<item>-chanchi-global-<name>` (a literal `skill-chanchi-global-<name>` matches as
  `skill-chanchi-global` and fails the check). Test fixtures and code may use any name.
- Executors never commit, merge, push or write chanchi records. They report each verification as the
  exact command plus its last output line, list every changed file, and stop at any gap.
- Last step of every session: `scripts/check` passes.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | `sync.sync_path(env, *, repo_root)` returns where `SYNC` is or would be (`CHANCHI_SYNC`, else `<main checkout>/SYNC`), **never resolved** (a `SYNC` link stays in the path), `None` only when neither resolves; `sync_dir()` keeps its phase-1 contract (an existing directory or `None`). `sync init` creates `config/`, `ITEMS/agents/` and `ITEMS/skills/`. The design's sentence "An existing `SYNC` is never replaced: the command fails with `link_conflict`" is read as belonging to `sync init --link`, the only form that would replace `SYNC`: with `--link <dir>`, any existing entry at the `SYNC` path (directory, file or link, dangling or not) is `link_conflict`, and an existing non-directory `<dir>` is `invalid_value`. A plain `sync init` on an existing `SYNC` directory only adds the missing subfolders and replaces nothing; on a file at `SYNC` it is `link_conflict`; on a dangling link it is `missing_prerequisite` (hint `chanchi sync status`) | Under the other reading a plain re-run would fail although it replaces nothing; this reading keeps the design's guarantee (never replaced) and keeps `init` idempotent. Executors follow this reading and do not stop on it |
| D2 | The reserved slug is enforced in `projects.ensure` (every new `projects` row, which is how `change open` and an explicit `--project global` create one) and in `projects.register`; `projects.relink` only accepts a registered slug, so it inherits the guard. `register` checks an explicit `--name` before anything else, and the folder-derived slug only after the existing-locator lookup, so re-running `register` in a `global/` checkout already registered with `--name <other>` still answers `already_registered`. Error: `invalid_value`, `field: "slug"`, hint `chanchi project register --name <other>` | One choke point per row-creating path; the operational database holds no project named `global` (checked 2026-11-22) |
| D3 | Frontmatter for items: `AGENT.md` keeps `agents_sync`'s flat `key: value` lines and gains optional `version` and `status` (validated when present; never emitted into repository or user wrappers, whose bytes stay identical); `items check` first checks, on every global item, the directory name (`bad_name`), the frontmatter `name` (`name_mismatch`), `version` (required, `bad_version`) and `status` (required, `bad_status`; a missing line is `bad_status` too), and only then parses an `AGENT.md` with `agents_sync._parse`, turning any remaining `ChanchiError` (syntax, `description`, `scope`, `profile`, `skills`, `install`) into `bad_frontmatter`. `SKILL.md` carries `name`, `description` (both required, single line) and the design's `metadata:` block, read by `items.read_frontmatter(text) -> dict` (flat keys plus `metadata` as a dict; any other nesting, a folded or multi-line value, is `bad_frontmatter`). Both readers strip one pair of matching surrounding quotes from a value. Writers (`publish`, `retire`) rewrite only the `status` value and keep the line's form: unquoted in `AGENT.md`, double-quoted in the skill's `metadata:` block; a writer that meets an item with no `status` line inserts one right after `version` in the same form (such an item already fails `items check`, so `publish` and `retire` refuse it first, D10; the clause only keeps the writer total) | Two documented shapes, one reader per shape that already exists or is needed; the round-trip keeps the design's quoting |
| D4 | Valid version: `^\d+\.\d+\.\d+$`. Status: `draft`, `published`, `retired` (added to `taxonomy.py`). A global item name matches `^(agent|skill)-chanchi-global-[a-z0-9]+(-[a-z0-9]+)*$` | The design's `<x.y.z>`, its three statuses and its naming rule |
| D5 | **Published hash.** Setting `status: published` changes the item's bytes, so its hash differs from the audited (draft) hash. `items publish` checks the audit against the draft hash, flips the status, then appends to the current version's `CHANGELOG.md` section the line `Published: <YYYY-MM-DD> · audit <id> · audited <draft-hash> · sha256 <published-hash>` (`CHANGELOG.md` is outside the hash). `published_hash` is read only from the current version's section. While an item's status is `published`, `items check` reports `edited_after_publish` when its hash differs from that line and `published_without_record` when the section has no such line (a status set by hand, or copied from another machine without its changelog); a `retired` or `draft` item is exempt | Keeps the design's hash definition, lets a second machine verify a published item without the local database, and makes "an edit after the audit needs a new round or a new version" enforceable after publishing; a hand-set `published` can never reach the mirror |
| D6 | **Item audits get their subject from chanchi.** `audits.open_audit` and `audits.next_round` gain an optional keyword `sync_root: Path | None = None`; `cmd_audit_open` and `cmd_audit_round` pass `sync.sync_dir()`. For an audit of kind `item`, `audit open --kind item --ref <name> --version <x.y.z>` and `audit round <id> --version <x.y.z>` store `subject_at` as `items.subject_at(sync_root, name, version)` = `<x.y.z>@<content hash>`; refused when `sync_root` is `None` (`missing_prerequisite`, hint `chanchi sync init`), the ref is not a global item (`invalid_value`, `field: "ref"`), the version is not the item's current one (`invalid_value`, `field: "version"`), or `--commit` is given for an item (`invalid_value`). Other kinds ignore `sync_root` and work without `SYNC`. The existing tests in `tests/test_audits.py` that open `kind="item"` audits with a bare version (for example `subject_at == "1.2.0"`) switch to kind `other`, or build a `SYNC/ITEMS` fixture, keeping what they assert | The design requires `<version>@<content hash>`; a hash typed by hand could be wrong |
| D7 | `items.check(...)` never raises for item problems: it returns `{items, problems}`, each problem `{item, code, detail}`; the CLI `items check` fails once with `invalid_value`, `field: "items"`, `details: {"problems": [...]}` when the list is not empty; `publish` and `mirror` read the returned list. Problem codes: `bad_name`, `wrong_folder`, `name_mismatch`, `bad_frontmatter`, `bad_version`, `bad_status`, `missing_changelog`, `symlink`, `conflict_copy`, `retired_not_retired`, `edited_after_publish`, `published_without_record`, `own_item_collision`, `bad_retired_json`, `unexpected_entry`. Expected in `ITEMS/`: `agents/`, `skills/` and `retired.json`; names starting with `.` are ignored there and in the kind folders; anything else is `unexpected_entry` | One run shows the user everything to fix; cloud folders leave dotfiles; `retired.json` belongs in `ITEMS/` (design tree) |
| D8 | Conflict copies (`*.icloud`, names containing `conflicted copy` or `(conflict`) are excluded from the hash (design) **and** reported by `items check` as `conflict_copy` (design, *Risks*) | Both design statements hold |
| D9 | `items retire <name> [--replaced-by <name>] --reason "<why>"` rewrites the item's `status` to `retired` (D3) **and** appends the `retired.json` entry (design, *Retirement*). Refused on a retired item (`invalid_transition`), with a blank reason (`invalid_value`), with `--replaced-by` equal to the name, or naming an item that does not exist, is retired, or is of another kind (`invalid_value`); a draft may be retired. The entry's `version` is the item's current version; `date` is UTC `YYYY-MM-DD`. A missing `retired.json` is an empty list; the file is a JSON array rewritten with the new entry appended and earlier entries unchanged | The design's effects and fields; a replacement that does not exist would point projects nowhere |
| D10 | `items publish <name> --audit <id>` refusals, in order: unknown item (`invalid_value`); name in `retired.json` or status `retired` (`invalid_transition`); status `published` (`invalid_transition`, hint: write a new version as `draft`); `items check` problems for this item (`invalid_value`); audit missing (`unknown_audit`); audit kind not `item` or ref not this name (`invalid_value`, `field: "audit"`); last round not `accepted` or its `subject_at` not the item's `<version>@<hash>` as it is **before** the status flip (the draft hash, D5) (`invalid_transition`, hint: open a new round or a new version) | The design's publish rule, made checkable in order |
| D11 | Mirror manifest: the phase-1 file `mirror.json` next to the database, entries `{"owner": "items-mirror", "item", "kind", "path", ...}` with `kind` one of `skill-primary`, `skill-secondary` (plus `"link": <link text>`) or `claude`, `opencode`, `agy` (plus `"sha256"`). No `root` key: ownership does not depend on where `SYNC` points (design, *Ownership by manifest*). `agents-link` entries are preserved byte for byte, and a path owned by `agents-link` is a conflict for the mirror (and the reverse, already in phase 1) | One file, one ownership rule per owner |
| D12 | Skill primaries link to the **unresolved** item path, `<SYNC path>/ITEMS/skills/<n>` (D1's path; `os.path.abspath`, never `.resolve()`), so re-pointing `SYNC` keeps the links valid | The design's "re-pointing ... does not orphan anything" |
| D13 | `items mirror` is all or nothing: it first runs `items.check` (any problem → refused, nothing written), plans every wanted skill **and** agent entry, collects conflicts on the wanted paths (a path that exists and is not an `items-mirror` entry, including one owned by `agents-link`), and writes nothing when any conflict exists (`link_conflict`, paths in `details`). A foreign `*-chanchi-global-*` entry at a path the mirror does not want is left alone and is not a conflict: the design's sentence "an entry named `*-chanchi-global-*` that is not in it is a conflict and is never overwritten" is read as a conflict where the mirror would write (the guarantee, never overwritten, holds either way); executors follow this reading and do not stop on it. Then it writes, removes owned entries no longer wanted, and writes `mirror.json` once. `--check` writes nothing and fails with `stale_wrappers` on a check problem, a conflict, a missing or changed entry, or an owned entry no longer wanted. `--remove` deletes every `items-mirror` entry (dangling or not, and an agy `<n>/` folder left empty), drops them from the manifest, and works without `SYNC` | The design's ownership rule: a foreign global-named entry is never overwritten |
| D14 | `chanchi skills link/unlink` never treat a name containing `chanchi-global-` as theirs: `_is_own`, `_is_legacy` and `_is_compat` return `False` for it (the check is on `chanchi-global-`, so legacy-shaped names such as `chanchi-global-x` are covered too) | Verified 2026-11-22: a dangling `~/.claude/skills/skill-chanchi-global-<n>` secondary gives `_is_own == True` and `skills unlink --global` removes it, because global names start with `skill-chanchi-` |
| D15 | The gate (Task 5) uses a scratch `CHANCHI_DB` and a scratch `CHANCHI_SYNC`, with the real `HOME` (the harnesses need their real credentials). The probe items' `item` audit lives only in that scratch database as fixture data, labelled so in the session log; `items mirror --remove` with the same scratch database cleans the real home afterwards. The change records (`change close`, `show`) stay in the operational database: the gate unsets both variables and returns to the main checkout before them | The operational database never holds test audits; the harnesses can only be exercised from the real home |
| D16 | Agent writing is split into composable primitives in `agents_sync` (`read_manifest`, `write_manifest`, `remove_target`, a planner that returns wanted agent entries per installed harness, and a conflict collector); `link_user` is rebuilt on them with unchanged behaviour, and `items.mirror` plans skills and agents with them, checks every conflict, then writes | A single helper that writes agent files and the manifest in one call would either drop the mirror's skill entries as orphans or write before skill conflicts are known |

## File map

| File | Session | Responsibility |
|---|---|---|
| `src/chanchi/projects.py`, `src/chanchi/sync.py`, `src/chanchi/cli.py` (sync group), `tests/test_projects.py`, `tests/test_sync.py`, `tests/test_items.py` | S1 | reserved slug, `sync init/status`, global-name rules in the items check |
| `src/chanchi/items.py` (new), `src/chanchi/taxonomy.py`, `src/chanchi/agents_sync.py` (`version`/`status` keys), `src/chanchi/audits.py` (D6), `src/chanchi/cli.py` (items group), `tests/test_items_global.py` (new), `tests/test_audits.py`, `tests/test_agents_sync.py` | S2 | frontmatter, hash, check, list, publish, retire, item audits |
| `src/chanchi/skills_link.py`, `src/chanchi/agents_sync.py` (shared link core), `src/chanchi/items.py` (mirror), `src/chanchi/cli.py` (items mirror), `tests/test_mirror.py` (new), `tests/test_skills_link.py`, `skills/skill-chanchi-verify/SKILL.md` | S3 | the mirror and the separation from chanchi's own links |
| `FEATURE_MAP.md`, `README.md` | each session | coverage of what the session adds |

## Sessions

| Session | Tasks | Depends on | task_type / complexity |
|---|---|---|---|
| S1 | 1 | plan merged | `business-logic` medium (two modules, CLI, three test files) |
| S2 | 2, 3 | S1 merged | `business-logic` high (new domain module, audits change, CLI, > 10 cases) |
| S3 | 4 | S2 merged | `business-logic` high (links, manifest ownership, two existing modules refactored) |
| — | 5 | S3 merged | orchestrator: the gate (verification item 9), real home |

The sessions run one after the other: S2 needs S1's `sync.require()` and the global-name skip in
`tests/test_items.py`, and S3 needs S2's item model. This plan is merged to `main` before S1's
worktree is created.

Session protocol (chanchi change `global-items-phase2`, available
`agy:gemini-4-hydrogen-{low,medium,high,xhigh}` and `claude:sonnet:{low,medium,high,xhigh,max}`;
explore budget `max(1, floor(3/4)) = 1`, but every session blocks a later one, so no explore
session is assigned). The orchestrator re-runs `chanchi recommend` at each dispatch and updates the
line when the result changed:

- S1 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (98.2, low confidence, task_type+complexity) · chosen agy:gemini-4-hydrogen-high:high
- S2 `business-logic` high — chanchi: recommended agy:gemini-4-hydrogen-high:high (97.6, low confidence, task_type) · chosen claude:sonnet:high · reason: at high complexity task_type data is weak evidence; claude:sonnet:high has 10 sessions at task_type+complexity (93.8, ok confidence)
- S3 `business-logic` high — same recommendation · chosen claude:sonnet:high · reason: as S2

Each executor works in its own worktree `.claude/worktrees/chanchi-gi2-sN` on branch
`feat/gi2-sN`, created from `main` after its dependencies merged. The orchestrator commits and
merges each session with `git merge --no-ff`.

---

### Task 1 (S1): Reserved slug, `sync init/status`, global names in the items check

**Files:** modify `src/chanchi/projects.py`, `src/chanchi/sync.py`, `src/chanchi/cli.py` (new
`sync` group), `tests/test_projects.py`, `tests/test_sync.py`, `tests/test_items.py`,
`FEATURE_MAP.md` (new `sync` entry; `project` and `change` gotchas), `README.md`.

**Interfaces produced:**
- `projects.RESERVED_SLUGS = ("global",)`; `projects.check_slug(slug)` raises the D2 error.
  Called by `projects.ensure` before inserting a new row and by `projects.register` on the slug it
  will use (`--name` or the folder name).
- `sync.sync_path(env=None, *, repo_root=None) -> Path | None` (D1).
- `sync.init(env=None, *, repo_root=None, link: Path | None = None) -> dict`: without `link`,
  creates the missing folders of `SYNC/config`, `SYNC/ITEMS/agents`, `SYNC/ITEMS/skills` and
  returns `{path, created: [...], link: null}`; with `link`, refuses (`link_conflict`, hint
  `chanchi sync status`) when anything exists at the `SYNC` path, else creates `<dir>` and its three
  subfolders when missing, makes `SYNC` a symbolic link to the absolute `<dir>`, and returns
  `{path, created, link: <dir>, recommendation}` where `recommendation` says to point `<dir>` at a
  folder a cloud service synchronizes (Google Drive, iCloud Drive, Dropbox) or at a clone of a
  private git repository. A dangling `SYNC` link without `--link` is `missing_prerequisite`, hint
  `chanchi sync status`. No resolvable path (D1) is `missing_prerequisite`, hint: set
  `CHANCHI_SYNC`.
- `sync.status(env=None, *, repo_root=None) -> dict`: `{path, exists, is_link, target,
  reachable, config: bool, items: bool}`; it never creates anything; `path: null` when D1 gives
  `None`.
  `exists` is `os.path.lexists(path)` (true for a dangling link), `reachable` is
  `path.is_dir()`.
- `sync.require(env=None, *, repo_root=None) -> Path`: the `SYNC` directory as `sync_path` gives
  it (unresolved, D1), or `missing_prerequisite` with the hint `chanchi sync init` (for S2 and S3).
- CLI: `chanchi sync init [--link <dir>]`, `chanchi sync status` (`project=False`).
- `tests/test_items.py`: `REFERENCE` matches still found, but names equal to `<kind>-chanchi-global`
  or starting with `<kind>-chanchi-global-` are skipped by `test_references_resolve` (they live in
  `SYNC`); a new `test_own_items_are_not_global` fails when an item directory of this repository is
  named `*-chanchi-global-*` (design, Principle 4), with a message that states the rule and the fix.

- [ ] **Step 1:** Failing tests: `register` refuses a main checkout folder named `global` without
  `--name` and accepts it with `--name other`; `register --name global` is refused; `ensure` (via
  `chanchi change open` run inside a temporary git repository whose folder is `global`) is refused
  with the hint; `--project global` on `change open` is refused. `sync init` on a fresh
  `CHANCHI_SYNC` creates the three folders; a second run creates nothing; `--link` on a temporary
  directory creates the link and the target's folders; `--link` with an existing `SYNC` directory,
  file or dangling link is `link_conflict` and leaves it untouched; `--link` to an existing file is
  `invalid_value`; a plain `sync init` with a file at `SYNC` is `link_conflict`; re-running
  `register` without `--name` in a `global/` checkout registered with `--name other` answers
  `already_registered`; `status` reports a link whose
  target was removed as `reachable: false` and creates nothing; `sync init` resolved from a
  `git worktree` of a temporary repository (via `repo_root`) creates `SYNC` in the main checkout;
  `git check-ignore SYNC` succeeds in this repository. `tests/test_items.py`: a fixture text
  naming `skill-chanchi-global-x` is not reported, and an own item named `skill-chanchi-global-x`
  in a temporary tree is.
- [ ] **Step 2:** Implement.
- [ ] **Step 3:** `FEATURE_MAP.md`: new `sync` entry (sub-features `sync init`, `sync status`,
  driven with `CHANCHI_SYNC` set to a scratch path); a gotcha under `project` and `change` for the
  reserved slug. `README.md`: a *SYNC* section with both commands and the cloud-folder
  recommendation.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S1):** `uv run pytest -q tests/test_projects.py tests/test_sync.py tests/test_items.py`;
the `sync` entry of `FEATURE_MAP.md` driven with `uv run chanchi` (paste `sync status` after
`sync init --link`); `git check-ignore -v SYNC`; `scripts/check`.

---

### Task 2 (S2): Global item model — frontmatter, hash, `items check` and `items list`

**Files:** create `src/chanchi/items.py`, `tests/test_items_global.py`; modify
`src/chanchi/taxonomy.py` (`ITEM_STATUSES`), `src/chanchi/agents_sync.py`,
`tests/test_agents_sync.py`, `src/chanchi/cli.py` (new `items` group), `FEATURE_MAP.md` (new
`items` entry), `README.md`.

S2 starts from a `main` that has S1: the CLI gets the `SYNC` folder with `sync.require()`.

**Interfaces produced:**
- `taxonomy.ITEM_STATUSES = ("draft", "published", "retired")`, `taxonomy.ITEM_KINDS =
  {"agents": "agent", "skills": "skill"}`; listed by `taxonomy.describe()`.
- `items.read_frontmatter(text) -> dict` (D3).
- `agents_sync._parse` accepts optional `version` (D4) and `status` (`ITEM_STATUSES`), refuses bad
  values with `invalid_value`, and `AgentSource` gains `version: str | None = None` and
  `status: str | None = None`; `render`/`render_by_kind` ignore both, so
  `uv run chanchi agents sync --check` stays green and existing wrappers are byte-identical.
- `items.content_hash(item_dir) -> str` (`items.check` catches its symlink error and reports a
  `symlink` problem; it never lets it propagate): the design's SHA-256 framing exactly (relative POSIX path
  UTF-8, NUL, decimal byte length, NUL, bytes; files sorted by relative POSIX path; excluded
  `CHANGELOG.md`, any component starting with `.`, conflict copies). A symlink anywhere inside the
  item raises `invalid_value` (`field: "path"`). Bytes as stored.
- `items.load(sync_root) -> list[Item]` where `Item` holds `name, kind, path, version, status,
  hash, published_hash` (from the D5 line, else `None`).
- `items.check(sync_root, *, own_names) -> dict`: D7 (always returns `{items, problems}`),
  `own_names` being chanchi's own item names, from `items.own_names()`: the directory names under
  `agents/` and `skills/` of the checkout that holds chanchi's source
  (`Path(__file__).resolve().parents[2]`, checked like `sync._chanchi_checkout`), and an empty
  list when chanchi is not installed from a checkout (then `own_item_collision` cannot fire; never
  an `internal` error). Changelog: one
  `## <x.y.z> — <YYYY-MM-DD>` section per version, newest first; the current version must have
  one (`missing_changelog`). D5's two published problems.
- `items.list_items(sync_root) -> list[dict]`: `name, kind, version, status, hash,
  published_hash, retired` (from `retired.json`). It is the inspection command and never fails on
  an item problem: a field it cannot read (bad frontmatter, a symlink that blocks the hash, a
  malformed `retired.json`) is `null`.
- CLI: `chanchi items check`, `chanchi items list` (`project=False`).

- [ ] **Step 1:** Failing tests on temporary `SYNC` trees: the hash of a two-file item equals a
  hand-computed expected digest written in the test (framing spelled out), is unchanged by editing
  `CHANGELOG.md`, adding `.DS_Store`, `x.icloud` or `SKILL (conflicted copy).md`, and changes on a
  one-byte edit or a renamed file; a symlink inside the item fails. `items check` reports, each in
  its own case: a directory not named `<kind>-chanchi-global-<name>`; a skill under `agents/`; a
  frontmatter `name` different from the directory; `version: 1.0`; `status: live`; no changelog
  section for the current version; a conflict copy; a `retired.json` name whose status is not
  `retired`; malformed `retired.json`; an item named like one of `own_names`; a stray file in
  `ITEMS/`; a symlink inside an item (`symlink` problem, `items.check` does not raise); an
  `AGENT.md` with an unknown `profile` (`bad_frontmatter`); a `SKILL.md` without
  `description` or with a multi-line one. A valid agent and a valid skill (skill with the quoted
  `metadata:` block) pass, with `retired.json` and a `.DS_Store` present in `ITEMS/`. `list_items`
  on a tree with a broken item returns it with `null` fields. An item with no `status` line fails
  with `bad_status`; an `AGENT.md` whose frontmatter name differs from its directory gives
  `name_mismatch`, not `bad_frontmatter`. An `AGENT.md` with
  `version`/`status` parses and renders the same wrapper text as without them.
- [ ] **Step 2:** Implement.

### Task 3 (S2): `items publish`, `items retire` and item audits

**Files:** modify `src/chanchi/items.py`, `src/chanchi/audits.py`, `src/chanchi/cli.py`,
`tests/test_items_global.py`, `tests/test_audits.py`, `FEATURE_MAP.md` (`items` and `audit`
entries), `README.md`.

**Interfaces produced:**
- `items.subject_at(sync_root, name, version) -> str` (D6); `audits.open_audit` and
  `audits.next_round` take `sync_root` and call it when the audit's kind is `item`; the CLI passes
  `sync.sync_dir()`. Update the existing item-kind tests of `tests/test_audits.py` as D6 says.
- `items.publish(conn, sync_root, name, *, audit_id, own_names, today=None) -> dict` (D10, D5):
  rewrites only the `status` value (D3), appends the D5 line inside the current version's
  changelog section, returns `{name, version, status, audit_id, audited_hash, hash}`.
- `items.retire(sync_root, name, *, reason, replaced_by=None, today=None) -> dict` (D9): rewrites
  the `status` value to `retired` (D3) and appends the `retired.json` entry.
- CLI: `chanchi items publish <name> --audit <id>`, `chanchi items retire <name>
  [--replaced-by <name>] --reason "<why>"` (`project=False`).

- [ ] **Step 1:** Failing tests: an `item` audit opened on a draft records `subject_at`
  `<version>@<hash>`; `--version` different from the item's version, an unknown ref, and
  `--commit` on an item are refused; publish succeeds after a round closed `accepted` at that
  subject, flips the status, writes the D5 line, and `items check` then passes; publish is refused
  (one case per D10 row) without an audit, with a `design` audit, with a `fix` round, after a
  one-byte edit made after the audit (hash mismatch), on an already published item, and after
  `items retire`; editing a published item makes `items check` fail with `edited_after_publish`;
  a `status: published` set by hand with no `Published:` line fails with
  `published_without_record`; publishing `0.2.0` above an existing `0.1.0` section writes its line
  into the `0.2.0` section and reads `published_hash` from there; publish keeps the skill's quoted
  `metadata:` form; publish of an item with no `status` line is refused (`bad_status`, D10); retire sets `status:
  retired`, appends an entry with the D9 fields, keeps earlier entries byte for byte, and the item
  then passes `items check` (a retired published item is exempt from the published checks);
  retire twice, a blank reason, `--replaced-by` itself, an unknown, retired or other-kind item
  are refused; a retired name set back to `draft` by hand fails `items check`
  (`retired_not_retired`).
- [ ] **Step 2:** Implement; extend `FEATURE_MAP.md` (`items publish`, `items retire`; the `audit`
  entry gains the item form) and README.
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S2):** `uv run pytest -q tests/test_items_global.py tests/test_audits.py tests/test_agents_sync.py tests/test_layers.py`;
the `items` entry of `FEATURE_MAP.md` driven with `uv run chanchi` through `audit open --kind item`,
votes, `audit close` and `items publish` (paste `items list`); `uv run chanchi agents sync --check`;
`scripts/check`.

---

### Task 4 (S3): `items mirror` and its manifest

**Files:** modify `src/chanchi/skills_link.py`, `src/chanchi/agents_sync.py`,
`src/chanchi/items.py`, `src/chanchi/cli.py`, `tests/test_skills_link.py`; create
`tests/test_mirror.py`; modify `skills/skill-chanchi-verify/SKILL.md` (*Helpers*),
`FEATURE_MAP.md` (`items` entry), `README.md`.

**Interfaces produced:**
- `skills_link.skill_targets(base, names, source_dir, *, installed) -> list[tuple[Path, str,
  str]]`: `(path, link text, kind)` for each name: the primary `<base>/.agents/skills/<n>` with the
  absolute text `<source_dir>/<n>` (D12), and relative secondaries to it in
  `<base>/.claude/skills/` when `installed("claude")` and in
  `<base>/.gemini/antigravity-cli/skills/` when `installed("agy")` and
  `<base>/.gemini/antigravity-cli` is a directory (the same rule `plan_targets` applies today).
  Primaries only when any harness is installed. `plan_targets` and `link` keep their behaviour; if
  `link` is refactored onto `skill_targets`, `tests/test_skills_link.py` stays green unchanged.
- D14 in `skills_link`.
- `agents_sync`: the D16 primitives; `link_user` rebuilt on them with unchanged behaviour and
  output (its tests stay green unchanged).
  `MIRROR_HEADER = "# generated by chanchi items mirror from SYNC/ITEMS/agents/{name}/AGENT.md; do not edit"`.
- `items.mirror(sync_root, *, env, home, db_dir, own_names, check=False, remove=False) -> dict`
  (D11-D13): only `published` items; returns `{written, unchanged, removed, conflicts,
  skipped_harnesses, items}`. `sync_root` may be `None` only with `remove=True`.
- CLI: `chanchi items mirror [--check | --remove]` (`project=False`; the two flags exclusive).
- `skill-chanchi-verify` *Helpers*: after a harness upgrade, also run `chanchi items mirror
  --check`.

- [ ] **Step 1:** Failing tests (temporary `HOME` holding `.claude`, `.config/opencode`,
  `.gemini` and `.gemini/antigravity-cli`; a `CHANCHI_DB` folder; a `SYNC` with one published and
  one draft item of each kind): primary, `.claude` and `antigravity-cli` secondaries and three
  agent files with the mirror header (agy at `.gemini/config/agents/<n>/agent.md`), drafts absent;
  without `.gemini/antigravity-cli` the agy agent is written and the agy skill secondary is not
  (today's `plan_targets` rule); opencode folder missing → `skipped_harnesses: ["opencode"]`;
  second run all `unchanged`; a hand edit of a mirrored agent file → `--check` fails, a normal run
  repairs it; `--check` writes nothing; a foreign file or link at a wanted path, for a skill and
  for an agent → `link_conflict`, untouched, nothing written (no agent file, no manifest change);
  a foreign `skill-chanchi-global-*` entry at a path the mirror does not want → left alone, not a
  conflict; an `agents-link` entry survives `mirror` and `--remove` byte for byte, and a path
  owned by `agents-link` is a conflict; `SYNC` made with `sync init --link <dir>`: the primary's
  link text contains the unresolved `SYNC` path (D12), and after re-linking `SYNC` to a copy and
  removing the old folder the next `mirror` reports every entry `unchanged` and valid; dangling
  entries after removing `SYNC` → `--remove` (without `SYNC`) deletes them all and leaves no empty
  agy folder; `items retire` of a mirrored item → the next `mirror` removes its entries; an
  `items check` problem → mirror refused, nothing written. Separation (verification item 6): with
  chanchi's own skills linked by `skills_link.link(home, global_=True, skills_dir=<fixture>)` and
  the mirror applied, `skills_link.unlink(home, global_=True, ...)` leaves every mirror entry
  (including a secondary whose primary is dangling, and a legacy-shaped `chanchi-global-x` link),
  and `items mirror --remove` leaves every `skill-chanchi-*` and `chanchi-<n>` compatibility link
  of the fixture, in `.agents/skills` and `.claude/skills`.
- [ ] **Step 2:** Refactor first (`skill_targets`, the D16 primitives) with the existing
  `tests/test_skills_link.py` and `tests/test_agents_sync.py` green, then D14, then `items.mirror`
  and the CLI.
- [ ] **Step 3:** `FEATURE_MAP.md` (`items mirror`, driven with `HOME`, `CHANCHI_DB` and
  `CHANCHI_SYNC` set to scratch folders, never the real home), README, verify Helpers.
- [ ] **Step 4:** `scripts/check` passes.

**Verification (S3):** `uv run pytest -q tests/test_mirror.py tests/test_skills_link.py tests/test_agents_sync.py tests/test_skills_content.py`;
the `items` entry of `FEATURE_MAP.md` driven with `uv run chanchi` in a scratch home through
`mirror`, a hand edit, `--check`, `mirror` and `--remove` (paste each output's lists and a
`find "$SCRATCH_HOME" -name '*-chanchi-global-*'` after `--remove`, which must print nothing);
`uv run chanchi agents sync --check`; `scripts/check`.

---

### Task 5 (orchestrator): The gate — verification item 9

Runs from `main` after S3 merges, with the installed `chanchi` (now `main`'s code). **Writes to the
real home** (mirror entries only), with a scratch database and a scratch `SYNC` (D15); steps 1-6 run
from a scratch folder outside any repository. The opencode folder is the adapter's:
`OC="${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}"`, used wherever the
steps name it. Keep the scratch database folder until step 6
passes; if it is lost, remove the leftovers that step 6's `find` prints by hand.

0. **Precondition (real home, operational database, read-only):** from the main checkout,
   `chanchi agents link --user --check` passes (the auditor agent is installed) and `ls
   ~/.agents/skills` lists every own `skill-chanchi-*` skill (phase 1 linked them). If either
   fails, run `chanchi skills link --global` and `chanchi agents link --user` now, before the
   baseline, and paste their outputs.
1. `export CHANCHI_DB="$(mktemp -d)/chanchi.db" CHANCHI_SYNC="$(mktemp -d)/SYNC"`; `chanchi db
   migrate`; `chanchi sync init`; register the four roster models as in the `audit` entry of
   `FEATURE_MAP.md`. Record the baseline: for each of `~/.agents/skills`, `~/.claude/skills`,
   `~/.gemini/antigravity-cli/skills`, `~/.claude/agents`, `$OC/agents` and
   `~/.gemini/config/agents`, whether it exists and its sorted entry names.
2. Write two drafts, `$CHANCHI_SYNC/ITEMS/skills/skill-chanchi-global-probe/` and
   `$CHANCHI_SYNC/ITEMS/agents/agent-chanchi-global-probe/`, each with a frontmatter `name` equal
   to its directory, a `description`, `version: 0.1.0`, `status: draft` (quoted in the skill's
   `metadata:` block) and a changelog section:
   `skill-chanchi-global-probe` (description "Probe skill for the chanchi mirror gate"; body: "When
   asked for the probe token, answer exactly `PROBE-<random 8 hex>`.") and
   `agent-chanchi-global-probe` (description "Probe agent for the chanchi mirror gate", `scope:
   both`, `profile: read-only`, `skills:
   [skill-chanchi-global-probe]`; body: "State your agent name, then give the probe token from
   your skill."). `chanchi items check` passes; `chanchi items mirror` writes nothing for them
   (drafts never appear).
3. Fixture audits (scratch database only): for each probe, `chanchi audit open --kind item --ref
   <name> --author claude:opus:unknown --version 0.1.0`, three `pass` votes with report
   `fixture`, `audit close` (`accepted`); `chanchi items publish <name> --audit <id>`; `chanchi
   items mirror`.
4. One headless run per harness, from the scratch folder, with the adapter's launch template
   (`src/chanchi/harnesses.py`) and the prompt "State your agent name and the probe token.":
   - `claude -p --agent agent-chanchi-global-probe --model sonnet --effort low "<prompt>" < /dev/null`
   - `opencode run --agent agent-chanchi-global-probe -m opencode-go/minimax-m3 "<prompt>" < /dev/null`
   - `agy --agent agent-chanchi-global-probe --model gemini-4-hydrogen --effort low -p="<prompt>" < /dev/null`
   Pass: the reply names `agent-chanchi-global-probe` and contains the exact token, which exists only
   in the mirrored skill, so one run per harness proves both the mirrored agent and the mirrored
   skill load (design, verification item 9 and phase row 2). A harness that fails is fixed
   (adapter row, target path) in a new session of this change, not waived: phase 2 is done only
   when all three pass.
5. Hand-edit the mirrored claude agent file: `chanchi items mirror --check` fails; `chanchi items
   mirror` repairs it; `--check` passes.
6. `chanchi items mirror --remove`. Read-only checks: every baseline folder that existed has the
   same entry names as in step 1 (a folder the mirror created may remain, empty);
   `find ~/.agents ~/.claude "$OC" ~/.gemini -maxdepth 4 -name '*-chanchi-global-*'`
   prints nothing.
7. `unset CHANCHI_DB CHANCHI_SYNC`, `cd` to the main checkout, then `chanchi agents sync --check`
   and `chanchi agents link --user --check` (operational manifest) pass. Record the run (commands,
   replies, outputs) in `docs/designs/reviews/global-items-phase2/gate.md` without home paths,
   then `chanchi change close global-items-phase2` and `chanchi show global-items-phase2`.

**Out of this plan:** creating the user's real `SYNC` (and where it links) is the owner's decision;
`chanchi sync init [--link <dir>]` is ready for it. Lessons #1-#5 stay pending on purpose (owner's
request); this plan neither reviews nor applies any of them. Phases 3+ (`items scan/propose`,
migration 006) are not part of it.

## Risks

| Risk | Mitigation |
|---|---|
| Publishing changes the audited bytes | D5: audit checked on the draft hash, published hash recorded in the changelog, `edited_after_publish` and `published_without_record` |
| A mirror entry and an own-skill link removed by the wrong command | D14 (verified defect) and the two-direction tests of Task 4 |
| The refactor of `skills_link` or `agents_sync` changes current behaviour | refactor first with the existing tests unchanged; `agents sync --check` and `agents link --user --check` in the gate (step 7) |
| A cloud placeholder or conflict copy changes the hash | D8: excluded from the hash, reported by `items check` |
| The gate leaves files in the real home | scratch manifest kept until step 6; step 6 is read-only, compares entry names with the baseline and searches for leftovers |
| A gate run fails because a harness does not discover the mirrored skill, not because of the mirror | the fix session starts from the adapter row and the target paths (`harnesses.py`, `skills_link.skill_targets`), re-checked against the harness's current skill folders |
| A test global name breaks the references check | S1 teaches the check to skip global names and runs first; before that only `<item>-chanchi-global-<name>` is safe |
