VERDICT: PASS WITH FIXES

Audit round 2, seat 3 (opencode / minimax family). Subject: `git show 13cfa9a` on branch
`docs/global-items-phase1-plan` — `docs/superpowers/plans/2026-11-21-global-items-phase1.md`
(Revision 2) plus the round-1 reviews it adds. Spec: `docs/designs/global-items.md` (Revision 4).
My round-1 report is `r1-seat3-opencode.md` (10 findings: 2 blocking, 4 major, 4 minor). No file was
edited except this report; no home path and no reference-project name is written here.

## Re-check of my round-1 findings

| id | severity | status | evidence (one sentence) |
|---|---|---|---|
| R1-01 | blocking | RESOLVED | Revision 2 pins the counts in the plan (not the reviews): decision D9 and Task 8's table (lines 472-476) give explicit `verdict blocking/major/minor` per seat per round, and Task 4 Step 2 now says "with the counts of Task 8's table (decision D9)" — every number in that table reproduces the consolidations exactly (round 2 seat 1 `0/2/8` = `round2-claude-sonnet.md:3` "blocking 0, major 2, minor 8"; seat 2 `0/5/2` = "4 new major, 1 minor" plus partials F6 major and F10 minor from `round2-agy-gemini-4-neon.md`; seat 3 `1/3/6` = "3 new major, 3 minor" plus partials GI-02 blocking, GI-15/16/17 minor from `round2-opencode-minimax-m3.md`), so `audits.vote(...)` now has a deterministic input (VERIFIED). |
| R1-02 | blocking | RESOLVED | Task 8 step 2 replaces the invented `unavailable` rows with a real mechanism — "Run with `CHANCHI_SYNC` pointing at a scratch folder whose `config/auditors.toml` lists exactly those three specs in seat order 1, 2, 3, so the seats match history; if a binary is missing on `PATH`, stop and report it — never add `unavailable` rows that did not happen" — which uses the design's own `CHANCHI_SYNC` resolution (design L73) and never seats a spec twice, so the phase-1 signal is reproducible (VERIFIED). |
| R1-03 | major | RESOLVED | D5 now states an executable rule — "`audit open --project <slug>` resolves with `projects.resolve_project`; when omitted, the project detected from git if registered, else none. `--change <ref>` needs a project: with none, `missing_prerequisite` and the hint `--project <slug>`; an unknown ref is `unknown_change`" — and both `missing_prerequisite` and `unknown_change` are in `ERROR_CODES` (`src/chanchi/errors.py` L13, L18); the CLI no longer declares a second `--project` flag, it uses `leaf(..., project=True)` so `--project` comes from the shared parent (`src/chanchi/cli.py` L420-424), and the ref→id resolution matches the codebase convention of scoping a ref to a project (`record.py` L100-108) (VERIFIED). |
| R1-04 | major | RESOLVED | D7 now states one rule — "the last `/`-separated segment, lowercased, matched by **prefix**" — and Task 1 Step 3 replaces the old `LIKE '%/p%'` with a recursive-CTE `UPDATE` that reduces each model to its last segment; I ran that exact CTE against SQLite with the plan's own test ids and it returns `openrouter/qwen/other` → None, `deepseek/r1` → None, `claude/gemini-4` → google, `opencode-go/minimax-m3#thinking` → minimax, and `opencode-go/claude-x/z` → None, i.e. it agrees with the design's "last `/`-separated segment" rule (design L284) and with `family_for` (VERIFIED). |
| R1-05 | major | RESOLVED | Task 7 now names only commands that exist — `agy agents` ("Usage: agy agent [flags] / List available agents") and `opencode debug agents` ("SUBCOMMANDS: agents, config, heap-dump, paths") — and asks for skill visibility with the same three launch forms as the claude row instead of a listing command that does not exist; I confirmed `opencode debug` has no `skill` subcommand and `agy` has no `skills` subcommand, so the old wording would indeed have failed (VERIFIED). |
| R1-06 | major | RESOLVED | The Global constraints are now scoped to the sessions that must not touch the real machine — "Executor sessions (S1-S6) use a scratch database ... They never touch the operational database or the real `~/.claude`, `~/.config/opencode`, `~/.gemini`. Only the orchestrator's steps (the S6 precondition and Task 8) act on the real home and the operational database, and they say so" — and both exceptions say so in place ("Precondition (orchestrator, real home)", "On the **operational database**") (VERIFIED). |
| R1-07 | minor | RESOLVED | `sync.sync_dir` now resolves through git rather than a path heuristic — "`CHANCHI_SYNC` when set; else `projects.main_worktree(repo_root or Path(__file__).resolve().parents[2]) / "SYNC"`; `None` when there is no main checkout or the directory does not exist" — and `projects.main_worktree` resolves via `rev-parse --path-format=absolute --git-common-dir` (`src/chanchi/projects.py` L52-59), which I confirmed returns the main checkout from a worktree and `None` outside a repository, so the "not a git checkout" case now legitimately means `None` and the built-in roster (VERIFIED). |
| R1-08 | minor | RESOLVED | Task 6 states it outright — "`tests/test_skills_content.py::test_all_skills_exist`: the list is sorted by path, so `skill-chanchi-audit-rounds` goes **first**" — which matches `SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))` and the hard-coded expected list in `tests/test_skills_content.py` L26-33 (VERIFIED). |
| R1-09 | minor | RESOLVED | Task 5 states both gaps — `link_user` writes "creating parent folders (`mkdir(parents=True, exist_ok=True)`)" and "`--check` and `--remove` are mutually exclusive" (D4 repeats it), matching the existing `sync()` behaviour at `src/chanchi/agents_sync.py` L162 and the `add_mutually_exclusive_group` style used in `cli.py` (VERIFIED). |
| R1-10 | minor | RESOLVED | Task 6's file list now includes "`skills/skill-chanchi-item-authoring/SKILL.md` (*Agent source*: the `install` key)", so the skill the executor is told to follow no longer carries a stale frontmatter field list (VERIFIED). |

All ten round-1 findings are closed. No finding was resolved by weakening the design's outcome
rule, by editing the hand-run reviews, or by relaxing the fail-closed family rule.

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| R2-01 | major | Plan, Task 7 (S6) step 3, line 455: "Runs `chanchi agents link --user --check` (expected `ok: true`)." | The step cannot pass as written. The ownership manifest lives "in the folder of `CHANCHI_DB`" (design L164-166: "`mirror.json` next to the database (the folder of `CHANCHI_DB` when it is set, so scratch runs stay isolated)"; the plan's D3 and Task 5 repeat it: "`db_dir / "mirror.json"` ... `db_dir` is the folder of `db.operational_path()`"). But S6 is an executor session, which the plan's own Global constraints force onto a scratch database ("Executor sessions (S1-S6) use a scratch database (`export CHANCHI_DB=...`)"), and the orchestrator's precondition — the only run of `chanchi agents link --user` — writes the manifest into the **operational** database's folder. So under S6's scratch `CHANCHI_DB` the manifest is empty while the user agent file exists on the real home; `--check` then hits its own rule "a wanted file is not written yet" and fails with `stale_wrappers` instead of returning `ok: true`. The step was added by the revision-2 fix for R1-05 and R1-06 (the constraint scoping), so it is a new problem introduced by the fixes, not a carried one. | Plan lines 29-34 (scratch `CHANCHI_DB` for S1-S6), 352-353 (`db_dir / "mirror.json"`, `db_dir` = folder of `db.operational_path()`), 360-361 (`--check` "fails with `stale_wrappers` when ... a wanted file is not written yet"), 443-444 (the precondition runs `chanchi agents link --user` for real), 455 (S6 runs `--check`); design L165-166 (manifest in the folder of `CHANCHI_DB`) (VERIFIED). | Either move the check to the orchestrator's precondition (run `chanchi agents link --user --check` there, against the operational database, right after the real `link`), or state in Task 7 step 3 that S6 runs it with the operational `CHANCHI_DB` unset and the real home, as the one exception the Global constraints already allow for the orchestrator's steps. Do not weaken `--check`'s "not written yet" rule to make it pass. |
| R2-02 | minor | Plan, D5, line 62: "when omitted, the project detected from git if registered, else none." | The sentence does not describe `projects.resolve_project`, which the same sentence names as the resolver. That function has two distinct behaviours: a `projects` row with `registered_at IS NULL` (created by `change open`, never `register`) **is** returned, while **no row at all** makes it raise `ChanchiError("invalid_value", "project ... has no recorded changes yet", hint="projects are created by `chanchi change open` or `chanchi project register`")`. So "registered" is the wrong predicate (the row's existence is the right one), and "else none" needs the CLI to catch that error — the plan never says so, and the codebase's own convention for project-scoped commands (`_pid` → `resolve_project`) lets the error through. The phase-1 signal is unaffected (this repository's operational database does have the row — `projects.id = 3` — so `chanchi audit open` without `--project` resolves), but an executor writing `audit open` in a fresh project will hit the raise. | `src/chanchi/projects.py` L147-163 (`resolve_project` raises `invalid_value` when no `projects` row; `identify` falls back to the folder slug) and L179 (`registered_at IS NOT NULL` is the *registered* predicate, used by `_registered_row` only); `src/chanchi/cli.py` L68-69 (`_pid` lets the error through); plan line 62; `src/chanchi/cli.py` L510-511 (`chanchi change close` uses `_pid`) (VERIFIED). | Say: "when omitted, the project detected from git if a `projects` row exists for it (the row is created by `chanchi change open` or `chanchi project register`), else none; the CLI resolves it with `projects.resolve_project` and treats its `invalid_value` as 'no project'". This keeps the design's "both optional" and "never an error" (design L201) while matching the function the plan names. |

### Checked, no action (new material in Revision 2)

- **Task 8's table reproduces every recorded outcome under the plan's own `outcome()` rules.** I
  re-derived all three rounds from the plan's ordered rules (plan L289-296): round 1 (0/8/12,
  3/5/4, 2/6/10, no approvals) → `fix`; round 2 (0/2/8, 0/5/2, 1/3/6, no approvals) → `fix`; round 3
  (0/0/6 = approval, `pass` 0/0/2 = approval, 0/2/2 = not an approval, plus the two confirmed lone
  majors R3-01/R3-02) → `fix` → `escalated`/`round_cap`. Without the dissents round 3 would be
  `accepted`, so Task 8 step 3's "a dissent for each lone finding the round's consolidation marks"
  is load-bearing, and every lone finding in both consolidations is marked `confirmed` (VERIFIED).
- **Task 8's counts are the reviews' counts, not new numbers.** Round 1 `0/8/12, 3/5/4, 2/6/10` is
  the round-1 consolidation table verbatim; round 2 seat 1 `0/2/8` is `round2-claude-sonnet.md:3`
  ("blocking 0, major 2, minor 8"); round 3 `0/0/6`, `pass 0/0/2`, `0/2/2` is the round-3 escalation
  table. The one imprecision is that the escalation table writes seat 3's minors as "2+", and the
  plan pins `2`; the extra minor cannot change any outcome, since minor counts only feed the
  `accepted` listing (VERIFIED).
- **The Task 8 seat order is reachable.** `sync.roster()` reads `<sync_dir>/config/auditors.toml`
  and the plan's scratch `CHANCHI_SYNC` folder supplies exactly that path, so a three-entry roster
  in seat order 1, 2, 3 seats the three historical specs; the design's built-in roster has the
  same first three entries (claude/sonnet/medium, agy/gemini-4-neon-high/high,
  opencode/opencode-go/minimax-m3) (VERIFIED).
- **The launch templates are real and the Task 7 commands run.** `claude --help` shows `--agent`,
  `--model`, `--effort`; `opencode run --help` shows `--agent` and `-m provider/model#variant`;
  `agy --help` shows `--agent`, `--model`, `--effort` and `-p`; and I ran
  `agy --model gemini-4-hydrogen --effort medium -p="Say OK and stop."` → `OK`, which is the exact
  form Task 7 uses (VERIFIED).
- **The design's guards and contracts are still honoured.** `audit close` refused with an
  `assigned` seat; `vote`/`dissent`/`unavailable` refused on a closed round; `round` refused unless
  the last round is `fix`/`rework` and below 3; `already_seated` exclusion in seat filling;
  `unknown_audit`; the `models add` and `models set --family` hints; `degraded` recomputed on
  open, refill and next round; `author_model_id` nullable (D6); `invalid_transition` for lifecycle
  refusals (a code already in `ERROR_CODES`) (VERIFIED).
- **The layer and dependency rules still match the code.** `harnesses.py` as a leaf importing only
  `chanchi.errors`; `audits.py` and `sync.py` as domain modules with only `cli.py` rendering; only
  `projects.py` may import `subprocess` — and `sync.sync_dir` now calls `projects.main_worktree`
  rather than importing `subprocess` itself, which is what R1-02's fix needed (VERIFIED).
- **`render_by_kind` keeps the existing tests green.** `render(source)` is kept as a thin wrapper
  over `render_by_kind`, so `src/chanchi/agents_sync.py` L135-140 and its tests need no change
  (VERIFIED).
- **Migration numbering is coherent.** The template is at `user_version = 4`, so `005_audits_and_families.sql`
  is the next free number, and Task 1 Step 2 correctly renames the synthetic
  `005_add_probe.sql` in `tests/test_db.py` L253 to `006_add_probe.sql` and adds the four new
  tables to the hard-coded `OPERATIONAL_TABLES` tuple (L9-22) (VERIFIED).
- **No privacy leak.** The plan and the new round-1 review files contain no home path, no email and
  no reference-project name; the only match for the path patterns is the rule that forbids them.

### What must not change

- **The design is the spec.** Nothing above asks for a design change; R2-01's fix is in the plan's
  Task 7, and R2-02's fix is in D5.
- **The design's outcome table and the owner's approval rule** (`pass_with_fixes` with no blocking
  and no major = an approval), and the `quorum`/`round_cap` reason split the plan tests explicitly.
- **The three hand-run rounds and their recorded outcomes**, and the round-1 reviews, which are
  history; the plan now pins the counts instead of editing them.
- **The fail-closed family rule** and the `--check` "not written yet" rule: R2-01's fix must not
  relax either to make a step pass.
- **The privacy rule** and the session protocol's explore budget and executor duties.

OPEN: 0/1/1
