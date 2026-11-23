# Global Items — Phase 4 (Adoption) Implementation Plan

- **Revision:** 2, after audit round 1 (`fix`; chanchi audit 7,
  [round1-consolidation.md](../../designs/reviews/global-items-phase4-plan/round1-consolidation.md)).
  Audited with `chanchi audit` (kind `other`) by three auditors of different model families
  before any session starts.

> **For agentic workers:** each session below is one brief for `agent-chanchi-executor`. Steps use
> checkbox (`- [ ]`) syntax. Write the failing test first, then the code.

**Goal:** Ship phase 4 of `docs/designs/global-items.md` (Revision 4): `chanchi items inbox`,
`chanchi items decide` and `skill-chanchi-item-adoption`. Phase 4 is done only when its signal
holds: **each consumer project records an audited decision for the herdr skill, with the owner's
go-ahead per project** (design, *Adoption phases*, row 4).

**Spec:** `docs/designs/global-items.md`, sections *D. Adopt*, *Data model* (`item_decisions`),
*Versions and hashes* (retirement), *Redundant audits* (kind `adoption`, ref `<project>:<item>`)
and *Adoption phases* (row 4). Section D's command line gains `--audit` and the `--local` rule of
this plan (D6, D7); this plan's commit amends the design text so both agree. When this plan and the design disagree, the design wins: stop and
report the disagreement.

**Tech stack:** Python ≥ 3.11 standard library, pytest and ruff (dev only), uv.

## Global constraints

- Runtime dependencies stay empty. English everywhere. No home path, email or reference-project
  name in any committed file (`tests/test_privacy.py`); consumer projects are "project A/B".
- **Run the worktree's code:** `uv run chanchi ...` inside an executor worktree.
- **Executor sessions** export a scratch database and a scratch `SYNC` first:
  `export CHANCHI_DB="$(mktemp -d)/chanchi.db" CHANCHI_SYNC="$(mktemp -d)/SYNC"`; commands that
  write user folders run with a scratch `HOME` on that command only. Executors never touch the
  operational database, the real `SYNC`, the real harness folders or any consumer project. Only
  Task 3 (the orchestrator's gate) does, and it says so.
- Executors run unattended with their auto-approval flag (`AGENTS.md`, Working Conventions).
- `ChanchiError` codes come from `src/chanchi/errors.py::ERROR_CODES`; this plan adds none.
- Layers (`tests/test_layers.py`): the new module `adoption.py` is a domain module; it may import
  `db`, `errors`, `inventory`, `items`, `projects`, `sync`, `taxonomy`, `timeutil`; it reads the
  audit tables with SQL and never imports `audits.py`; `items.py` and `inventory.py` never import
  `adoption.py`. Only `cli.py` renders.
- Every new command gets a `FEATURE_MAP.md` sub-feature and a `README.md` line. Every new skill is
  listed in `tests/test_skills_content.py::test_all_skills_exist`, and every `chanchi <group>
  <sub>` it names must exist (`test_documented_commands_exist`).
- Executors never commit, merge, push or write chanchi records; they report each verification as
  the exact command plus its last output line and stop at any gap. Last step: `scripts/check`.

## Decisions this plan takes (the design leaves them open)

| # | Decision | Why |
|---|---|---|
| D1 | New domain module `adoption.py` holds `inbox` and `decide`; `taxonomy.ADOPTION_DECISIONS = ("adopt", "wrap", "keep", "deprecate")` and `taxonomy.INBOX_STATES = ("new", "changed", "deprecate_pending", "retired", "up_to_date")`, listed by `taxonomy.describe()` under `items` as `adoption_decisions` and `inbox_states`. `items.py` exposes `retired_entries(sync_root) -> tuple[list[dict] | None, str | None]` (today's private `_retired_entries`, kept as an alias) for `adoption.py`. No migration: `item_decisions` exists since 006 | `items.py` is already over 800 lines; one module per pipeline stage |
| D2 | **Scope.** Both commands act on one registered project: detected from the working directory or `--project <slug>` (`projects.resolve_scope`; `project=True` leaves of the `items` group, so they get the shared `--project`). An unregistered project is `project_not_registered`. Both need `SYNC` (`sync.require()`) | The design: "lists, for this project" |
| D3 | **Current decision** of `(project, global item)`: the row with the highest `id`. The inbox reads `items.load` and `items.retired_entries`; a malformed `retired.json` fails the command (`invalid_value`, `field: "items"`, hint `chanchi items check`), and an item whose `version`, `status` or `hash` is unreadable is left out and listed under `problems` (`{item, hint: "chanchi items check"}`). Only `published` and **retired** items (status `retired` or a name in `retired.json`, checked first) are considered; drafts never appear. **State, in order:** retired item — current decision `adopt` or `wrap` → `retired` (with `replaced_by` from the last `retired.json` entry of that name); `deprecate` → `deprecate_pending`; `keep` → `up_to_date`; no decision → not listed at all. Published item — no decision → `new`; current decision `deprecate` → `deprecate_pending` (with `version_changed: true` when its version differs); version differs → `changed`; otherwise `up_to_date`. Without `--all` the inbox prints every state except `up_to_date`; with `--all` it prints those too. Entries sorted by item name | The design's three inbox cases plus the deprecate follow-up ("the inbox keeps showing it until a later adopt, wrap or keep"), with one precedence |
| D4 | **Entry shape:** `{item, kind, version, hash, status, state, version_changed, replaced_by, path, decision: null or {id, decision, version, hash, local_item, reason, audit_id, decided_at}, similar: [...]}`; `path` is the item's folder `<SYNC>/ITEMS/<kind>s/<item>/` (unresolved `SYNC` path). `similar` lists this project's **current** `project_items` rows of the **same kind** whose path is either a row whose name's slug (`inventory.slug_of`) equals the global item's `<name>` part, or a `path` or `aliases` entry of this project's copies in the evidence of a proposal whose `global_item` is this item; joining on live rows means a copy removed and re-scanned disappears. Each `{kind, name, path, abs_path, lines, sha256}`, `abs_path` from `inventory.project_root` (`null` when missing), sorted by `path`. The inbox reads only the database and `SYNC`, never a project file | The adopting agent needs the project's overlapping items to compare (design D, step 2) |
| D5 | **`items decide <global-item> --decision adopt|wrap|keep|deprecate --version <x.y.z> [--local <item>] --reason "<why>" --audit <id>`.** Refusals in order: unknown global item (`invalid_value`, `field: "item"`); an item `items.load` cannot read fully (`invalid_value`, hint `chanchi items check`), or a malformed `retired.json` (same); status `draft` (`invalid_transition`); unknown decision (`invalid_value`, `field: "decision"`, `valid_values`); `--version` differs from the item's current version (`invalid_value`, `field: "version"`); a retired item takes only `keep` or `deprecate` (`invalid_transition`, hint: adopt or wrap its `replaced_by` as its own entry); blank reason (`invalid_value`, `field: "reason"`); `--local` rules (D6); the audit (D7). Recorded: project id, item, version, the item's content hash read at decision time, decision, local item, reason, audit id, `decided_at` UTC. Output: `{id, project, item, version, hash, decision, local_item, reason, audit_id, decided_at, state}`, `state` being the entry's state after the decision (D3) | The design's command and record ("the record keeps version and hash") |
| D6 | **`--local`.** `wrap` requires it, named `<kind>-chanchi-<project-slug>-<name>` where `<kind>` is the global item's kind, `<project-slug>` is `inventory.slug_of(<project slug>)` and `<name>` matches `[a-z0-9]+(-[a-z0-9]+)*` (`invalid_value`, `field: "local"`, hint with the expected prefix). On a **published** item, `keep` and `deprecate` require it (the project item kept or to be removed). On a **retired** item it is optional (a project that adopted it has no local copy: `keep` then acknowledges the retirement). `adopt` accepts it optionally (the project item that was removed). A given `--local` is never blank | The design's wrapper naming (`<item>-chanchi-<slug>-<name>`); a retirement must be acknowledgeable without inventing a name |
| D7 | **Audit link.** `--audit <id>` is required: the audit must exist (`unknown_audit`), be of kind `adoption` with `subject_ref` equal to `<project slug>:<global item>` and `project_id` equal to this project (`invalid_value`, `field: "audit"`), its last round must be `accepted` (`invalid_transition`, hint: finish the audit rounds), and no row of `item_decisions` may already carry that audit id (`invalid_value`, `field: "audit"`, hint: open a new adoption audit for this decision). Every decision therefore has its own audit | The design: "The decision is audited (kind `adoption`) ... and recorded"; an old audit cannot back a later version or a different decision |
| D8 | **The skill's text is part of this plan** (Task 2, verbatim), so the plan audit reviews it; S2 installs it unchanged. No eval case ships with it: the eval layer (`evals/`, `docs/designs/chanchi-agents-mvp.md` phase 2) does not exist yet, and `skill-chanchi-item-authoring` ties the eval rule to it | Same as phase 3 D15; the eval rule cannot be met before its layer exists |
| D9 | **Decision records** (the adopting agent's proposal with its comparison) live in `<SYNC>/reviews/<global item>/<version>/adoption-<project slug>.md`, `<SYNC>` being the path `chanchi sync status` prints; adoption audit reports next to them. Never in this repository or the project | They quote project items; users own their results (privacy) |
| D11 | **Who does what in adoption.** A delegated adopting agent (unattended) does the read-only comparison and writes the proposal (skill steps 1-3), and later applies and commits the approved change on a branch in a **git worktree of the project** created outside the project's folder (skill step 5a); it never asks the owner, opens audits or writes chanchi records. The project's orchestrating role (in the gate, this orchestrator) asks the owner (step 4), runs the adoption audit (5b) and records (6). For `keep` and `deprecate`, which change no project file, the audit's `--commit` is the project's current `HEAD` and the brief points to the proposal file | AGENTS.md: executors never write chanchi records; a headless agent cannot seat auditors; the owner's checkout stays untouched |
| D10 | **herdr 0.1.1 before adoption.** The gate builds `skill-chanchi-global-herdr` 0.1.1 with the four changes deferred in `SYNC/reviews/skill-chanchi-global-herdr/0.1.0/round2-consolidation.md` (three minor fixes and the owner's auto-approval rule), audits it (kind `item`), publishes and mirrors it, so projects decide on a published version. The owner chose this order on 2026-11-22 | A draft never reaches the inbox (D3) or the harnesses |

## Sessions

| Session | Tasks | Depends on | task_type / complexity |
|---|---|---|---|
| S1 | 1 | plan merged | `business-logic` medium (one domain module, CLI, taxonomy, ~6 files) |
| S2 | 2 | S1 merged (the skill names S1's commands; `test_documented_commands_exist`) | `docs` low (one skill, its test list, README) |
| S3 | 3 (step 1) | S1, S2 merged | `docs` medium, runs as `agent-chanchi-item-builder` (herdr 0.1.1) |
| S4, S5 | 3 (step 3) | S3 published | `docs` medium, the adopting agent in project A and project B |
| — | 3 | S1, S2 merged | orchestrator: the gate |

Session protocol (chanchi change `global-items-phase4`, available
`agy:gemini-4-hydrogen-{low,medium,high,xhigh}` and `claude:sonnet:{low,medium,high,xhigh,max}`;
planned executor sessions S1, S2; explore budget `max(1, floor(2/4)) = 1`). The orchestrator
re-runs `chanchi recommend` at each dispatch and updates the line when the result changed:

- S1 `business-logic` medium — chanchi: recommended agy:gemini-4-hydrogen-high:high (98.56, low confidence, task_type+complexity) · chosen agy:gemini-4-hydrogen-high:high
- S2 `docs` low — chanchi: recommended agy:gemini-4-hydrogen-high:high (94.92, ok confidence, global) · chosen agy:gemini-4-hydrogen-medium:medium · explore: agy:gemini-4-hydrogen-medium:medium (its text is fixed by this plan; a weak result costs one retry; it blocks only the gate)
- S3-S5 are chosen at the gate with `chanchi recommend --task-type docs --complexity medium`.

agy executors run headless from the main checkout with `--dangerously-skip-permissions --add-dir
<worktree>`, each in its own worktree `.claude/worktrees/chanchi-gi4-sN` on branch `feat/gi4-sN`.

---

### Task 1 (S1): `items inbox` and `items decide`

**Files:** create `src/chanchi/adoption.py`, `tests/test_adoption.py`; modify
`src/chanchi/items.py` (public `retired_entries`, D1), `src/chanchi/taxonomy.py`,
`src/chanchi/cli.py`, `tests/test_layers.py` (the import rules of *Global constraints*),
`FEATURE_MAP.md` (`items` entry), `README.md`.

**Interfaces produced:**
- `adoption.inbox(conn, sync_root, *, project_id, slug, all_=False) -> dict`:
  `{project, entries: [...]}` (D3, D4).
- `adoption.decide(conn, sync_root, *, project_id, slug, item, decision, version, reason, audit_id,
  local=None, now=None) -> dict` (D5-D7).
- CLI: `chanchi items inbox [--all] [--project <slug>]`, `chanchi items decide <global-item>
  --decision ... --version ... [--local ...] --reason ... --audit <id> [--project <slug>]`.

- [ ] **Step 1:** Failing tests, on a scratch `SYNC` with one published skill, one draft skill and
  one published agent, and two registered temporary projects A and B scanned with `items scan`
  (A holds a `tool-x` skill, so `similar` has it):
  - inbox of A lists the two published items as `new`, never the draft; `similar` of the skill
    lists A's `tool-x` with `abs_path`; a built proposal whose evidence names a second A copy adds
    it once; B's inbox is independent of A's decisions.
  - `decide` with an accepted `adoption` audit `A:<item>` records the row with the item's hash; the
    entry becomes `up_to_date` (absent without `--all`, present with it).
  - a new version (`0.2.0`, published) makes the entry `changed`; deciding `0.2.0` clears it.
  - `deprecate` makes it `deprecate_pending` until a later `keep`, `adopt` or `wrap`.
  - `items retire` of an adopted item → `retired` with `replaced_by`; `decide --decision adopt` on
    it is refused, `deprecate` is accepted (→ `deprecate_pending`) and `keep` clears it; a retired
    item that A kept or never decided is not listed.
  - retirement of an adopted item: `keep` without `--local` is accepted and the entry leaves the
    inbox (`up_to_date` with `--all`); `wrap` on it is refused; `replaced_by` comes from the last
    of two `retired.json` entries of that name.
  - a published item with a `deprecate` decision and a new version is `deprecate_pending` with
    `version_changed: true`.
  - refusals, one case each (D5-D7): unknown item, unreadable item (a symlink inside it),
    malformed `retired.json`, draft, unknown decision on a retired item (`invalid_value`, not
    `invalid_transition`), wrong version, blank reason, `wrap` without `--local`, `wrap` with a
    wrong prefix (`skill-chanchi-other-x`) and the right one (`skill-chanchi-<a-slug>-tool-x`),
    `keep` and `deprecate` without `--local` on a published item, blank `--local ""`, missing
    audit, audit of another kind, of another ref, of another project, audit whose last round is
    `fix`, an audit id already used by an earlier decision.
  - `similar`: a project agent named like the global skill is not listed (kind filter); two
    project skills with the same slug are both listed, sorted by path; a proposal copy removed
    from the project and re-scanned disappears.
  - scope: the same commands with `--project <slug>` from outside the project and from inside it
    (detected) give the same result; the stored `hash` equals `items.content_hash` of the item at
    decision time.
  - an unregistered project is `project_not_registered`; without `SYNC`, `missing_prerequisite`.
- [ ] **Step 2:** Implement; `FEATURE_MAP.md` sub-features (`items inbox`, `items decide`) driven
  on scratch projects and a scratch `SYNC` (publishing a fixture item through a fixture `item`
  audit, as the `items` entry already does), and a fixture `adoption` audit; README.
- [ ] **Step 3:** `scripts/check` passes.

**Verification (S1):** `uv run pytest -q tests/test_adoption.py tests/test_layers.py tests/test_taxonomy.py`;
the two sub-features driven with `uv run chanchi` (paste `items inbox` before and after `items
decide`, and `items inbox --all`); `scripts/check`.

---

### Task 2 (S2): `skill-chanchi-item-adoption`

**Files:** create `skills/skill-chanchi-item-adoption/SKILL.md` with exactly the text below;
modify `tests/test_skills_content.py` (`test_all_skills_exist` list), `README.md` (skills list).

```markdown
---
name: skill-chanchi-item-adoption
description: Use when the owner asks a project to check whether there are global items to adopt, or when chanchi items inbox lists entries for the project. Compares each global item with the project's own items, proposes adopt, wrap, keep or deprecate, applies it with the owner's go-ahead, and records the audited decision.
---

# chanchi — item adoption

Global items are available, never imposed: only this project's decision changes its own items.
Follow the project's own rules (its rules file, branches, commits) for every change in it.

**Roles.** Steps 1-3 and 5a can be done by a delegated agent running unattended; it stops after
each of them and reports. Steps 4, 5b and 6 belong to the project's orchestrating role, the only
one that asks the owner, opens audits and writes chanchi records.

## 1. Read the inbox

`chanchi items inbox` lists, for this project, every global item that needs a decision: `new` (no
decision yet), `changed` (a new version since the decision), `deprecate_pending` (a removal still
open) and `retired` (an item the project adopted or wrapped was retired; see `replaced_by`). Each
entry gives the item's folder (`path`) and `similar`: the project's own items that overlap it.
Take one entry at a time.

## 2. Compare

Read the global item in its folder and every `similar` item. Sort each rule of the project's items
into one of:

- **covered** — the global item states it (in any words);
- **particular** — only this project needs it (its paths, roles, models, runbooks, layout);
- **vendored** — text generated from an upstream source that the global item points to instead;
- **conflict** — the project's rule contradicts the global item.

## 3. Propose one decision

- **adopt** — nothing particular remains: remove the project's copies and update every reference
  to them (rules files, roles, other skills, scripts) to the global name.
- **wrap** — particular rules remain: keep them in `<kind>-chanchi-<project-slug>-<name>`, which
  starts by telling the agent to load the global item first and to follow it for everything the
  wrapper does not say; it holds only particular rules; move references to the wrapper's name and
  remove the old copies.
- **keep** — the project keeps its own item as it is; say why (for example a conflict the owner
  wants to keep).
- **deprecate** — the project's item is to be removed in a later change; name that follow-up. The
  entry stays in the inbox as `deprecate_pending` until a later adopt, wrap or keep.

A `retired` entry takes only keep (acknowledge it; no local item needed if the project adopted it)
or deprecate; its `replaced_by`, if any, is adopted or wrapped as its own entry. Vendored text and
scripts that only regenerate it are removed under adopt and wrap.

Write the proposal (decision, reason, the comparison table and every file the change touches) to
`<SYNC>/reviews/<global item>/<version>/adoption-<project slug>.md`, where `<SYNC>` is the path
`chanchi sync status` prints. Never write it inside the project.

## 4. Ask the owner

Show the owner the decision, the reason and the files it touches, with your recommendation, and
wait for a go-ahead for this project. Without it, stop here.

## 5. Apply and audit

a. Apply the approved change in a git worktree of the project, created outside the project's
   folder, on a new branch, touching only the files the proposal names, and commit it there.
   Keep and deprecate change no file: skip this step.
b. Audit it with three auditors (`skill-chanchi-audit-rounds`):
   `chanchi audit open --kind adoption --ref <project slug>:<global item> --commit <sha> --author <agent:model[:effort]> --project <project slug>`,
   where `<sha>` is the branch commit, or the project's current `HEAD` for keep and deprecate.
   The brief gives the project path, the proposal file and the diff, and asks the auditors to
   check that no covered, particular or conflicting rule was lost, that a wrapper holds only
   particular rules, and that every reference resolves.

## 6. Record

When the audit is accepted:
`chanchi items decide <global item> --decision <decision> --version <version> [--local <item>] --reason "<why>" --audit <audit id>`.
Then `chanchi items scan --project <project slug>` and confirm with `chanchi items inbox --all`
that the entry is `up_to_date` (or `deprecate_pending` after deprecate). Merging the branch
follows the project's own rules and the owner's go-ahead.

If something went wrong, the orchestrating role follows `skill-chanchi-lessons`; a delegated agent
says so in its report.
```

- [ ] **Step 1:** Create the skill with the text above, byte for byte; add it to
  `test_all_skills_exist`.
- [ ] **Step 2:** README: the skill in the skills list with one line.
- [ ] **Step 3:** `scripts/check` passes (`tests/test_skills_content.py`, `tests/test_items.py`,
  `tests/test_rules_budget.py`, `tests/test_privacy.py` included).

**Verification (S2):** `uv run pytest -q tests/test_skills_content.py tests/test_items.py tests/test_privacy.py`;
`HOME="$SCRATCH_HOME" OPENCODE_CONFIG_DIR= XDG_CONFIG_HOME= uv run chanchi skills link --global`
(with `.claude`, `.config/opencode` and `.gemini/antigravity-cli` created in the scratch home first) lists
`skill-chanchi-item-adoption`; `scripts/check`.

---

### Task 3 (orchestrator): The gate — the phase signal

Runs from the main checkout after S1 and S2 merged, with the installed `chanchi`. It uses the
operational database and the real `SYNC`, writes the mirror into the user's harness folders, and
works in the consumer projects only after the owner's go-ahead for each one.

0. **Links.** `chanchi skills link --global` (the new skill); `chanchi agents link --user --check`
   passes. Save `git status --porcelain` of the chanchi main checkout and of both consumer
   projects.
1. **herdr 0.1.1 (session S3).** Launch `agent-chanchi-item-builder` with proposal 7, version
   `0.1.1`, and the four changes of the 0.1.0 round-2 consolidation; it writes a new `CHANGELOG.md`
   section above 0.1.0 and keeps the item `draft`. Audit S3 like phase 3's S4 (projects and
   checkout unchanged, `items check` clean, no project name or home path, at most 2 lines shared
   with the vendored block). Open a new item audit (`--kind item --ref skill-chanchi-global-herdr
   --version 0.1.1 --author <builder spec> --change global-items-phase4`) and follow `skill-chanchi-audit-rounds`; minor
   fixes listed by an `accepted` round that touch hashed files go to a later version, never into
   the audited bytes.
2. **Publish and mirror.** `chanchi items publish skill-chanchi-global-herdr --audit <id>`;
   `chanchi items mirror`; `chanchi items mirror --check` passes. Owner's decision of 2026-11-22.
3. **Per project (S4 for project A, S5 for project B), one after the other.**
   a. **Proposal.** Launch the adopting agent (`chanchi recommend --task-type docs --complexity
      medium --available "<the list of S1>"` for the spec; agy headless with
      `--dangerously-skip-permissions`, or claude in another pane), from the project's main
      checkout, read-only, to run skill steps 1-3 for `skill-chanchi-global-herdr`. Pass:
      the proposal file exists in `<SYNC>/reviews/...`, and the project's `git status
      --porcelain` equals the baseline.
   b. **Go-ahead.** Ask the owner for that project, showing the proposal's decision, reason and
      file list, with a recommendation. Without a go-ahead the project records nothing and the
      phase is not done.
   c. **Apply.** For adopt or wrap, save `<baseline-sha>` (the project's `HEAD`), create a worktree
      of the project at `.claude/worktrees/research/gi4-<project>-adopt` (in chanchi's ignored
      folder, outside the project) on branch `chanchi/adopt-skill-chanchi-global-herdr`, and let
      the agent (same session or a retry) run skill step 5a there. Check: `git diff --stat
      <baseline-sha>..HEAD` in the worktree names only the proposal's files; the project's main
      checkout status equals the baseline.
   d. **Audit and record.** Run the adoption audit (skill step 5b; seats from the roster; reports in
      private scratch paths, moved to `<SYNC>/reviews/...` after all active seats finish and before
      the votes are recorded). When accepted: `chanchi items decide ...` with that audit,
      `chanchi items scan --project <slug>` (the scan reads the main checkout, so the result
      reflects the change only after the owner merges), and `chanchi items inbox --all --project
      <slug>` shows `up_to_date` (or `deprecate_pending`). Ask the owner whether to merge the
      branch in the project; the worktree is removed after the merge or the owner's decision.
4. **Record.** `docs/designs/reviews/global-items-phase4/gate.md`, redacted as in phase 3
   (projects as "project A/B", roots as `<project root>`, `<SYNC>`), then `chanchi change close
   global-items-phase4` and `chanchi show global-items-phase4`.

**Out of this plan:** phase 5 (project items) and 6 (replication); the design's third proposal
rule; lessons #1-#8 stay pending (owner's choice, 2026-11-22).

## Verification plan (phase 4)

1. `items inbox`: every state of D3, drafts never, `similar`, `--all`, per-project independence.
2. `items decide`: every refusal of D5-D7; the stored row keeps version and hash.
3. The skill installs and names only existing commands (Task 2).
4. The gate: herdr 0.1.1 published through an accepted item audit; each consumer project records
   an audited `adoption` decision with the owner's go-ahead (Task 3).

## Risks

| Risk | Mitigation |
|---|---|
| An adoption removes a rule the project needs | The comparison sorts every rule (skill step 2); the adoption audit checks for losses; the owner approves per project |
| A wrapper drifts into duplicating the global item | The skill and the audit brief require only particular rules (design, *Risks*) |
| The mirror exposes herdr in every project before they decide | Distinct names (Principle 4); publication is the owner's decision of 2026-11-22; the inbox lists the overlap |
| A consumer project's references break | The skill updates every reference; the audit checks they resolve; the change lives on a branch until the owner merges it |
