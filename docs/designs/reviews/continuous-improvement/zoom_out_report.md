# Stage 5: Initial Zoom Out report

**Target:** `docs/designs/continuous-improvement.md`, full file (lines 1-1051)
**Goldfish context:** `docs/designs/continuous-improvement.brief.md`
**Reviewers:** egm-zoom-out (completed), egm-inventive-catalyst (see below)

---

## Part 1: egm-zoom-out

**Verdict: changes needed.** Two Majors block approval as written. Three more Majors are YAGNI or scope concerns. There are also several Nits.

The context-sufficiency check passes. The objective, motivation, staging and alignment with the brief (Revision 2) are clear. Splitting the work into stages and deferring hooks to stages 3 and 4 is a sound choice at this altitude.

### 🟡 Major 1: Project resolution is patched in the wrong component, so the stage-1 goal fails for most audit commands
**Scope:** Goals 96-98; Technical Plan §2, 433-436; Implementation #6, 847-849; #9, 889-890.

- The design adds a locator lookup inside `projects.ensure()`. That function is reached only from `record.open_change` (record.py:99), which is `change open`.
- Every other audit command goes through `cli._pid` → `projects.resolve_project` → `identify()`, which matches by slug only (cli.py:57-58, projects.py:77-91). That covers `change close`, `session start|report|audit|update`, `incident add`, `show` and `stats --project`. The design changes only the hint text of `resolve_project`.
- After a `rename` or inside a nested repository, `change open` resolves to the registered project, but the next `session start` fails ("project … has no recorded changes yet") or picks the wrong project. That breaks the stage-1 goal (lines 96-97) and is the reason Alternative B was rejected (635-636).
- `ensure(conn, slug, path)` has no cwd. When an explicit `--project` differs from the detected slug, `identify()` returns `path = None` (projects.py:62).

**Fix:** Put the locator lookup in one place: the slug/identity resolution shared by `identify()` and `resolve_project()`. Order: explicit `--project`, then path locator, then remote, then today's folder slug. `ensure()` stays unchanged.

### 🟡 Major 2: The doc contradicts itself on when the locator lookup runs
**Scope:** 433 and 848 ("before its slug lookup") versus 752 ("only when no slug row matches first").

The two orders behave differently and are tested differently (line 939). Pick one and state it once, at the shared resolver.

### 🟡 Major 3: The remote locator is speculative scope in stage 1 (YAGNI)
**Scope:** §2 410-412, 430; Alternative C 640-646; `register`/`relink`; tests 935-938.

The Problem section gives no evidence of moved folders or second clones; its evidence is nested repositories, which the path locator alone solves. The remote locator brings URL normalization, a `UNIQUE` collision rule, `--no-remote`, and fork collisions (the doc's own con, line 644). `relink` already covers a moved folder.
**Fix:** Ship stage 1 with path locators plus `relink`; keep `kind` in the schema so a remote locator can come later with no migration.

### 🟡 Major 4: Too much machinery for a stage-1 role guard that only stops a cooperative agent
**Scope:** §3 Actor and scope table 445-467; `writer_roles` / `project writers` 280-286, 438-441.

`--as` and `--conversation` are free text in stage 1; any agent can pass `--as planner` or a new conversation label (the doc admits this, 195-197, 928-929). Yet stage 1 builds per-scope writer-role tables, a five-row scope matrix and a guarded writers change. This conflicts with brief principle 5.
**Fix:** Keep `check_writer` and `writer_roles`. Simplify scope to "the lesson's origin scope", or defer agnostic-goes-global routing to stage 2. At minimum, state in Goals that the stage-1 guard stops only a cooperative agent.

### 🟡 Major 5: Cross-site retirement ships in stage 1 but pays off only in stage 2
**Scope:** `lesson_replaces`, `replaces` command, auto-retire on `apply` (490-495); CUJ 6 (217-224).

Without the stage-2 inbox, no flow applies an agnostic lesson to a second project. The `replaces` command is not in the brief's command surface (brief §6).
**Fix:** Keep the table in 004; move the cascade to stage 2; express replacement as an optional `replaces: [N]` field in the `add`/`modify` JSON body.

### 🟢 Nit 1: `project rename` (and `show`/`list`) have no CUJ
Lines 420, 845, 881-883. Trim `rename` unless a CUJ needs it.

### 🟢 Nit 2: Two sources for the rules line to paste
Lines 581, 903, 928. `skills_link.SUGGESTED_CONFIG_LINE` (skills_link.py:11-14) already holds it. Extend that constant and reference it from the skill and README.

### 🟢 Nit 3: Code-level detail in the plan
Lines 806-813 (stopword list), 856-857 (constant names), 864 (dataclass fields and raw `SELECT`).

### 🟢 Nit 4: Hedged plan entry
Implementation #10, 892-898 (`render.py`, "Modify, unless no change is needed"). Drop it.

### 🟢 Nit 5: `lesson_events` duplicates review columns on `lessons`
Lines 314-318, 362-374. State which one is the source of truth (`reopen` clears fields, line 489).

### 🟢 Nit 6: Context cost of the single skill
§6 566-581; NFR 755-756. Set a line target for SKILL.md or check its size in `test_skills_content.py`.

### 🟢 Nit 7: Resolution order differs from the brief
Lines 426-427 vs brief 329-330 (`--project` vs `--global` first). Align, or say the flags cannot be combined.

**Reuse confirmed:** `modelspec.parse`, `record._required_text`, `db.transaction`, `skills_link.available_skills`, `taxonomy.describe()`, the `003_model_capabilities.sql` precedent, and `db migrate --template` with the `bak-v<N>` backup (cli.py:250, db.py:162-174).

---

## Part 2: egm-inventive-catalyst

Advisory persona: Majors and Nits only, no Blockers. Context sufficiency passes. Real false compromises were found.

### 🟡 Major IC-1: The `[lesson #N]` text tag cannot live in the targets the method prefers
**Scope:** brief contradiction 2 (brief 89-92); §1 `lesson_sites.where_` (340, 345); §3 `apply` (490-491); §5 Verify (556-562); "cheapest place" rule (576).

The review rule favors hooks, permissions and CLI checks, which mostly live in JSON files with no comments (`~/.claude/settings.json`, `~/.gemini/config/hooks.json`) or in another codebase. So the cheapest fixes are the ones `verify` cannot see; they show as `missing_tag` forever.
**Fix:** Anchor by `target_kind`: a comment tag where the format allows it; for JSON, a JSON pointer plus the exact entry value. Store it in structured columns (`where_path`, `where_anchor_kind`, `where_anchor`, `where_commit`) instead of one string parsed by splitting on " [lesson #" (556). One checker per anchor kind.
**Cost:** more checkers; JSON anchors break on reformat or reorder; columns must be settled before 004.

### 🟡 Major IC-2: `apply` trusts `--where` without checking it
**Scope:** §3 `apply` (490-493); Verify (528-562); staging (38-41, 785).

"chanchi never edits files" does not mean it cannot read them at write time. **Fix:** `apply` reads the resolved path and refuses if the anchor is missing; `retire` warns if it is still present. Stage-2 `verify` then only catches later decay.
**Cost:** `apply` fails when run away from the checkout; widen NFR 749-750.

### 🟡 Major IC-3: "The author does not judge" rests on caller-typed strings
**Scope:** brief principles 4-5; §3 Actor, `check_writer` (445-457); `review` `self_review` (484-486); `modify` (482-483); CUJ 3 (196-197).

One conversation can record and approve a lesson with two labels. Stage 3, which should close this, depends on unverified harness facts (Q1-Q5), and may never close it for agy or opencode.
**Fix:** On `lesson add`, also record an ambient fingerprint the caller does not type (nearest harness ancestor PID + start time, plus any conversation id the harness exports; add that check to Q1-Q5). `review`/`modify` compare fingerprints too; mismatch refused or logged.
**Cost:** platform-specific; resumed conversations slip through; one tmux pane hosting two conversations gives false refusals and needs a `human` override.

### 🟡 Major IC-4: Bare role strings mix per-project and global authority
**Scope:** §3 scope table (459-467); writer roles (438-441); brief vocabulary (116); CUJ 2 (180-187).

(a) Any project's `--as planner` becomes a global reviewer. (b) A project whose writers are `lead` cannot review its own agnostic lessons unless `lead` is also added globally. CUJ 2 works only because both lists use the default.
**Fix:** Make global authority an explicit grant of (project, role) pairs, or state the rule explicitly; show effective authority in `project writers`. Decide the `writer_roles` shape before 004.

### 🟡 Major IC-5: Rejected lessons that recur are dropped silently
**Scope:** §3 `repeat` (480-481); `export` default (503); `summary` (499-501); brief §4 line 244.

The brief says a rejected lesson that recurs is reported. The design's `repeat` only increments `occurrences`, and `export` defaults to `pending,postponed`.
**Fix:** `repeat` returns a `rejected_recurs` warning with the reason code; `summary`/`export` include rejected lessons with repeats after `reviewed_at` (from `lesson_events`, no new column). No automatic reopen.

### 🟢 Nit IC-6: Locator lookup order and missing `cwd` parameter
Same issue as zoom-out Major 2. Prefer lookup only on a slug miss; name the `ensure()` signature change; have `project register` adopt a stale folder-slug row.

### 🟢 Nit IC-7: "particular requires high or critical" is a policy inside `CHECK`
Lines 326-329 vs 382-387 and Alternative M (719-726). Move it to `lessons.py`.

### 🟢 Nit IC-8: Globally applied lessons skip every inbox, even for project-only targets
§5 inbox query (540-541, 546). Exclude only target kinds that projects inherit from the home setup; keep `role` and `wrapper` targets in the inbox.

### 🟢 Nit IC-9: Dedup thresholds tuned on Spanish text, tokenizer uses English stopwords
§4 (525-526); stopwords (807-813). Record matched id, coverage and shared count in the `force_new` event note, and show near-miss scores in `similar`.

**No false compromise found in:** staging (core first, hooks after verification), separating sites from decisions, the fail-open exit-0 hook contract, and not auto-inserting models.
