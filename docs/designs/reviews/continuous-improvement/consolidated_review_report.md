# Consolidated review: continuous-improvement design

**Target:** `docs/designs/continuous-improvement.md` (1051 lines). FeatureRange 1-781; DetailedRange 782-1051.
**Mode:** uninterrupted (all five stages, one round each, no fixes applied).
**Goldfish context:** `docs/designs/continuous-improvement.brief.md`.
**Date:** 2026-11-19

| Stage | Report | Reviewers | Result |
|---|---|---|---|
| 5 Initial Zoom Out | [zoom_out_report.md](zoom_out_report.md) | zoom-out, inventive-catalyst | 0 🔴 · 10 🟡 · 11 🟢 |
| 6 Comprehension | [comprehension_report.md](comprehension_report.md) | comprehension | 0 🔴 · 6 🟡 · 6 🟢 |
| 7 Critic | [critic_report.md](critic_report.md) | design, structural, style | 1 🔴 · 19 🟡 · 20 🟢 |
| 8 Intermediate Zoom Out | [intermediate_zoom_out_report.md](intermediate_zoom_out_report.md) | zoom-out | 1 🔴 · 7 🟡 · 6 🟢 |
| 9 Implementation Readiness | [implementation_readiness_report.md](implementation_readiness_report.md) | implementation-readiness, codebase-details, style | 7 🔴 · 24 🟡 · 24 🟢 |

All eleven reviewer runs completed; none was "not run".

## Bottom line

The design idea holds up: no reviewer found a flaw in the staging, in keeping sites apart from decisions, or in the fail-open hook contract. **The document is not ready to implement.**
- One design error, flagged by five reviewers, is the cause of most of the trouble: project resolution was put in `ensure()`, which only `change open` calls.
- The implementation plan has four concrete build breakers. The main session confirmed three of them in the code (A2, A3, A4).
- The rest is either content that exists only in the brief, or scope to cut.

Stage 8 settled the conflicts between reviewers. This report follows its rulings, so items listed under "Declined" are deliberately not action items.

---

## 🔴 Blockers

### A1. Move project resolution into one shared resolver
**Raised by:** Stage 5 zoom-out Major 1 and Major 2; Stage 5 IC-6; Stage 7 D-1, D-2 and S-2; Stage 8 Blocker 1; Stage 9 IR-M1 and CD-B3.
**Problem:** Only `change open` reaches `ensure()` (record.py:99). Every other audit command goes through `_pid` → `resolve_project` → `identify()`, which matches by slug only (cli.py:57-58, projects.py:77-91). So in a renamed or nested registered project, `change open` works and the next `session start` fails. The doc also contradicts itself on lookup order (433 vs 752).
**Action:**
- Use one resolver for both `identify()`/`resolve_project()` and the lesson commands. Order: explicit `--project`/`--global`, then the path locator, then the folder slug (audit commands only).
- Leave `ensure()` unchanged.
- State the new signatures (a cwd, plus a flag for an explicit slug).
- Fix the Performance NFR to match. Say how the longest-prefix lookup runs: one query per ancestor path.
- Add tests that run `change open` → `session start` → `incident add` → `show` in a renamed project and in a nested one.

### A2. `export --format md` breaks every command
**Raised by:** IR-B1, CD-B4.
**Problem:** A second `--format` conflicts with the one in the `common` parent (cli.py:229-231), so argparse fails while building the parser. On top of that, `_emit` knows only json and text.
**Action:** Pick the mechanism: add `md` to `FORMATS` and `_emit`, or use a separate `--md` flag that prints raw text. Name the files this touches and the Markdown layout.

### A3. The plan breaks existing tests it does not list
**Raised by:** IR-B3, CD-B1, CD-B2. Verified by the main session.
**Problems:**
- `tests/test_db.py:240` uses a synthetic migration numbered 4, and lines 244 and 271-273 expect version 3.
- `tests/test_no_network.py:57-59` forbids `subprocess` outside `projects.py`, but the plan puts `git_head` in `lessons.py`.
**Action:**
- Add `tests/test_db.py` to the file list as Modify: move the probe to 5, expect `[2, 3, 4]` and version 4, extend `OPERATIONAL_TABLES`, and add a v3→v4 test showing existing rows keep `registered_at` NULL.
- Move `git_head` into `projects.py`.

### A4. `reopen-site` deletes a row that an event still references
**Raised by:** IR-B2.
**Problem:** `lesson_events.site_id` references `lesson_sites(id)` with no `ON DELETE`, and `foreign_keys = ON` (db.py:70).
**Action:** Decide this in migration 004. Either use `ON DELETE SET NULL`, or do not delete the row and add a `reopened` site state instead.

### A5. No Risks & Mitigations section
**Raised by:** ST-1 (Blocker), D-4, Stage 8 Major 7 (ranked lower).
**Action:** Add one short table: the five rows from brief §13, plus a forgeable-identity row (see B3) and a thresholds row. For the thresholds row, log the matched id, coverage and shared count in the `force_new` event note, and give one numeric retune trigger.

---

## 🟡 Major

### B1. Inline the brief's definitions in one "Vocabulary and states" section
**Raised by:** C-1, C-2, C-4, C-5, C-6, ST-3, ST-4, ST-5 (severity table), S-1, IS-1, IS-6, IR-N5.
**Action:** Add one section, about 60 lines copied from the brief:
- the glossary (brief §1);
- the five principles and the triggers;
- the generality table;
- the severity table;
- both state tables with the meaning of each reason code;
- two sentences on today's audit flow (change → sessions → incidents; projects created by slug).

Then:
- Change line 171 to `<conversation id>`.
- Add one sentence on the source method: it is the owner's private process, this document is complete without it, and item 17 is the full test list.

### B2. Cut scope from stage 1
**Raised by:** Stage 5 zoom-out Major 3, Major 5 and Nit 1; Stage 8 Major 2, Major 3 and Nit 13.
**Action:**
- Remove the remote locator, `normalize_remote`, `--no-remote`, `project rename` and Alternative C. Keep `kind` in `project_locators`.
- Move the `replaces` command and the retire cascade to stage 2. Keep the `lesson_replaces` table in 004, and accept `replaces: [N]` in the `add`/`modify` JSON body.

**Side effects:** This removes D-N6, IR-M4 (rename collision), the "one extra git call" claim, and the `replaces` gaps in ST-5 and ST-6.

### B3. Simplify the writer scope and write down the threat model
**Raised by:** Stage 5 zoom-out Major 4; IC-3, IC-4, D-3, C-4; Stage 8 Major 4 and Major 5.
**Action:**
- Lesson writes check the lesson's origin scope.
- Site commands check the site's scope.
- The global list governs only global-origin lessons and `--site global`.
- Add one paragraph saying that in stage 1, `--as`, `--conversation` and `--author human:…` are cooperative declarations. It should also say:
  - where a writer gets its conversation id;
  - that agents never pass `human`;
  - that `--author` names the actor on every command.

### B4. Shrink the §7 hook contract to its invariants
**Raised by:** D-7; Stage 8 Major 8. This overrides ST-6.
**Action:**
- Keep only: exit 0, fail open, no migration, actor taken from the event, and the `runs` table.
- Point to brief §10 as the draft contract.
- Add D-7 to Q1: "can a Claude Code hook filter on command text, or does every Bash call start chanchi?"

### B5. Close the plan's zero-decision gaps
**Raised by:** IR-M2 to IR-M9, IR-M12, CD-M1, CD-M2, CD-M5, CD-M6, D-N1 to D-N4, IC-5, IS-4.
**Action:** Write down each of the following:
- **Error payload:** where `duplicate_lesson`'s matched rule and tokens go (`details` field or `valid_values`), and the `field` and `hint` for each new code. `invalid_transition` needs a hint.
- **`render.py`:** drop item 10. `_render` already handles nesting.
- **`register`/`relink` edge cases:** slug collision, re-run, outside git, `--name` with an existing folder row.
- **Read commands:** for `list`, `similar`, `export` and `summary`, give the scope (all projects or resolved), the arguments, the `--since` column and the output shape.
- **`apply`:** a table of allowed (from-state, generality, site) combinations with the refusal code for each.
- **Dedup:**
  - "every site retired" requires at least one site;
  - precedence between blocking and warn-only;
  - candidate order;
  - a `warnings` output key;
  - the check runs inside the `add` transaction.
- **Event actions:** a table of command → action → from/to → `site_id`, and whether `--force-new` writes one event or two.
- **`add` JSON schema:** `change`/`session`/`incidents` on global lessons, types, unknown keys, absent effort, and whether `modify` re-runs dedup. Store empty tags as `''`, not `_csv`'s None.
- **`project show <slug>` vs `--project`:** which wins, and whether `leaf()` gains a `parents` argument.
- **`repeat` on `rejected`:** returns a `rejected_recurs` warning (brief 244).
- **`reopen` of a `duplicate`:** whether occurrences move back, and which fields clear.
- **Stage-2 `verify`:** path rules (absolute, `~`, relative), the output schema, and `unchecked` for `hook`/`permission` targets.

### B6. Split stage 1 into checkpoints and complete the test list
**Raised by:** IR-M10, IR-M11, CD-M3, IS-5.
**Action:**
- Order stage 1 in seven steps, each ending with pytest:
  1. migration and `test_db`;
  2. taxonomy and errors;
  3. projects;
  4. dedup;
  5. lessons;
  6. CLI;
  7. skill and README.
- Add the missing tests listed in IR-M11.
- Name each fixture file instead of the glob, and say whether `conftest`/`helpers` get `registered_repo` and `nested_repo`. Today's `git_repo` has no commit and no remote.
- Turn "as before" checks into concrete assertions, and capture `chanchi show` output before migrating.

### B7. Fix the claims and wording that the Goals and tests depend on
**Raised by:** S-3, S-4, S-5, S-6, IS-2, IR-N1, Stage 5 zoom-out Nit 6.
**Action:**
- Make the inbox Goal (117-119) say "not applied globally" and add the registration-date rule.
- Close the stopword list: name the source, or list every word.
- Set a line ceiling for SKILL.md and check it in `test_skills_content.py`.
- Calibrate "often" and "natural place" in the Problem section.

### B8. Give each alternative its real reason for rejection
**Raised by:** ST-2, D-5, S-8.
**Action:** Drop "Rejected by author:". State the deciding trade-off for each alternative, especially A, B and K.

---

## 🟢 Nit (batch them in one pass)

- **Reuse existing code:**
  - one `_git()` helper in projects.py (CD-M4, Stage 8 Nit 12);
  - `catalog._model_row` (CD-N1);
  - `importlib.resources` for stopwords (CD-N2);
  - `record._csv` and `cli._split`;
  - `SUGGESTED_CONFIG_LINE` as the single paste source (Stage 5 zoom-out Nit 2).
- **Withdrawing an approved lesson:** retire it at every site. Add one sentence; no new state (Stage 8 Nit 9 vs D-6).
- **Item 22:** mark it Modify, not Create (IS-N2, IR-N2, CD-N6).
- **Stage-1 skill:** leave out stage-2 commands (CD-N4).
- **Pin locations:**
  - item 13 paragraph position (CD-N7);
  - item 21 test fixture (CD-N5);
  - exact migration-check commands (CD-N8).
- **Path canonicalization:** canonicalize stored locators as well as the cwd (D-N5).
- **`lesson_events` vs review columns:** say which is the source of truth (Stage 5 zoom-out Nit 5).
- **Global-origin `project`/`particular` lessons:** define their scope (D-N1).
- **`modelspec.parse`:** document that it does not validate effort (IR-N3).
- **Formatting:**
  - diagram border (ST-8);
  - H3 numbering (ST-9);
  - dividers (ST-10);
  - pseudo-SQL `ORDER BY` (ST-11);
  - links in Additional Resources (ST-12);
  - NFR rollback pointer (ST-13).
- **Wording:**
  - S-7, S-9, S-10;
  - C-7 to C-12 (one-line glosses for agy, herdr, EGM, the launcher);
  - IS-N1 to IS-N9;
  - CD-N9;
  - IR-N6.

---

## Declined (deliberately not actions)

Stage 8 judged these to be bloat for a guard that, in stage 1, only stops a cooperative agent:

- **IC-1:** structured anchor columns. Replaced by `unchecked` in `verify`.
- **IC-2:** reading the file at `apply` time.
- **IC-3:** process fingerprint.
- **IC-4:** (project, role) grant table. Replaced by B3.
- **D-3:** a `run open` command in stage 1.
- **D-6:** a `withdrawn` state.
- **ST-6:** the full hook contract.
- **ST-5:** a separate command table. The error codes already exist at lines 828-840.
- **D-5:** a new "conversation identity" alternative.

---

## Traceability matrix

| Action | Source findings |
|---|---|
| A1 | ZO-M1, ZO-M2, IC-6, D-1, D-2, S-2, IZ-B1, IR-M1, CD-B3, ZO-N7, D-N5 (order) |
| A2 | IR-B1, CD-B4 |
| A3 | IR-B3, CD-B1, CD-B2 |
| A4 | IR-B2 |
| A5 | ST-1, D-4, IZ-M7, IC-9, S-5 |
| B1 | C-1, C-2, C-3, C-4, C-5, C-6, ST-3, ST-4, S-1, IS-1, IS-6, IR-N5, IZ-M6 |
| B2 | ZO-M3, ZO-M5, ZO-N1, IZ-M2, IZ-M3, D-N6 |
| B3 | ZO-M4, IC-3, IC-4, D-3, C-4, IZ-M4, IZ-M5 |
| B4 | D-7, ST-6, IZ-M8 |
| B5 | IR-M2…M9, IR-M12, CD-M1, CD-M2, CD-M5, CD-M6, IS-3, IS-4, D-N1…N4, IC-5, IC-1/IC-2 (as `unchecked`), IR-N4, IR-N6 |
| B6 | IR-M10, IR-M11, CD-M3, IS-5 |
| B7 | S-3, S-4, S-5, S-6, IS-2, IR-N1, ZO-N6 |
| B8 | ST-2, D-5, S-8 |
| Nits | ZO-N2…N5, IC-7, IC-8, C-7…C-12, S-7, S-9, S-10, ST-8…ST-13, IS-N1…N9, IR-N2, IR-N3, CD-M4, CD-N1…N9, IZ-N9…N14 |

Prefixes: ZO = Stage 5 zoom-out, IC = Stage 5 inventive-catalyst, C = Stage 6, D/ST/S = Stage 7 design/structural/style, IZ = Stage 8, IR/CD/IS = Stage 9 readiness/codebase/style.
