# Stage 8: Intermediate Zoom Out report

**Target:** `docs/designs/continuous-improvement.md`, full file (1-1051), not edited since Stage 5.
**Inputs:** brief, `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`.
**Reviewer:** egm-zoom-out (completed). Code checked: projects.py, cli.py (58, 123), record.py (99), db.py (81-82), skills_link.py (11-14).

**Verdict: changes needed.** Only one change is needed for correctness: move project resolution into one shared resolver. Everything else is either inlining content the brief already has, or deleting scope. Most new mechanisms proposed in Stages 5-7 would add bulk and should be declined or reduced to one sentence.

## How the earlier reports conflict, and how to settle it

- **Stage 5 cuts scope; Stage 7 adds sections.** They mostly do not collide. Stage 7's additions (vocabulary, states, severity, staging, risks) are short content the brief already has; inlining adds no features. Do both, except where Stage 7 adds scope: the full hook contract (ST-6), a separate command table (ST-5) and a `withdrawn` state (D-6).
- **Stage 6 and Stage 7 ask for the same inlining.** ST-3, ST-4, ST-5 (severity), S-1, C-1, C-2, C-4, C-5 reduce to one glossary plus the brief's §2 and §4 tables. Do it once.
- **The inventive-catalyst items conflict with Stage 5's own YAGNI findings.** IC-1, IC-3 and IC-4 add machinery to a stage-1 guard already judged too heavy. Decline the mechanisms; keep one-line statements.

## Findings

### 🔴 Blocker 1: Project resolution is in the wrong component (raised from Major)
**Scope:** 96-98, 424-436, 751-753, 847-849, 889-890; projects.py:51-91, cli.py:58, record.py:99.
Confirmed in code: `ensure()` is called only from `record.open_change`; every other audit command uses `resolve_project()` → `identify()`, slug only. It breaks the stage-1 goal (96-97), the reason Alternative B was rejected (635-636), and audit continuity in renamed or nested registered projects.
**Smallest fix:** one resolver used by `identify()`/`resolve_project()` and lesson commands. Order: explicit `--project`/`--global`, then path locator, then folder slug (audit commands only). Leave `ensure()` unchanged. This also closes Stage 5 Major 2, D-2, S-2, IC-6, Stage 5 Nit 7 and part of D-N5. D-1's new CUJ becomes a test bullet in item 15.

### 🟡 Major 2: Cut the remote locator from stage 1 (Stage 5 Major 3, ranked higher)
**Scope:** 410-412, 416, 430, 640-646, 935-938.
Removes `normalize_remote` and its six tests, `--no-remote`, Alternative C, the fork-collision con (644), the false "at most one extra git call" claim, D-N6, and step-4 precedence questions. Keep `kind` in `project_locators`.

### 🟡 Major 3: Move `replaces` and the retire cascade to stage 2 (Stage 5 Major 5, agreed)
**Scope:** 349-354, 490-495, 217-224, 868, 964.
Dissolves the `replaces` parts of ST-5 and ST-6. Keep `lesson_replaces` in 004; accept `replaces: [N]` in the `add`/`modify` JSON; remove `set_replaces` and the cascade test from stage 1.

### 🟡 Major 4: Simplify the writer-scope rule instead of a grant model (Stage 5 Major 4 + IC-4; declines IC-4's grant table)
**Scope:** 459-467, 280-286, 438-441.
`add`, `repeat`, `modify`, `review`, `reopen` check the lesson's origin scope; site commands check the site's scope; the global list governs only global-origin lessons and `--site global`. Deletes two scope-table rows and both IC-4 cases. State the one-line difference from brief §2.

### 🟡 Major 5: One threat-model paragraph for identity flags, no new machinery (D-3, IC-3, C-4)
**Scope:** 99-100, 105, 171, 195-197, 445-457.
Decline IC-3's process fingerprint and D-3's stage-1 `run open` (Alternative J already rejects it). One paragraph: in stage 1, `--as`, `--conversation` and `--author human:…` are cooperative declarations; where a writer gets its conversation id (the harness id if shown, else a label chosen once and reused); agents never pass `human` (the skill says so); `--author` names the actor on every command. Fix line 171 to `<conversation id>`.

### 🟡 Major 6: Inline the brief's definitions once, in one section
Add one H3 "Vocabulary and states" (~60 lines copied): brief §1 glossary, the five principles (brief 24-33, which also define the triggers), the §2 generality table, the severity table, both §4 state tables with reason codes, and two sentences on today's audit flow. For C-3 add: "the source method is the owner's private process; this document is complete without it; item 17's list is the full test list."

### 🟡 Major 7: A short Risks table, not a new subsystem (ST-1, ranked lower)
Five rows from brief §13, plus a forgeable-identity row (→ Major 5) and a thresholds row (IC-9 data in the `force_new` note + one numeric retune trigger from S-5). Fold the stage-1 guard caveat into it.

### 🟡 Major 8: Decline the expanded hook contract; shrink §7 (disagrees with ST-6; reduces D-7)
**Scope:** 583-609.
ST-6 would commit stage 3 before Q1-Q5 are answered, against the doc's own rule (38-41, 585). Cut §7 to invariants (exit 0, fail open, no migration, actor from the event); keep the `runs` table; point to brief §10 as the draft contract. Add D-7 to Q1: "can the hook filter on command text, or does every Bash call start chanchi?"

### 🟢 Nit 9: Decline the `withdrawn` state (disagrees with D-6)
Retiring every site removes a lesson from all inboxes (536-537), and dedup treats "approved, every site retired" as warn-only (520). Add: "to withdraw an approved lesson, retire it at every site."

### 🟢 Nit 10: IC-1/IC-2 reduce to one `verify` rule
`verify` reports `unchecked` instead of `missing_tag` for target kinds with no comment syntax (`hook`, `permission`). Decline anchor columns (SQLite can `ADD COLUMN` later) and read-at-apply.

### 🟢 Nit 11: One-line conformance items
- IC-5: `repeat` on `rejected` returns a `rejected_recurs` warning (brief 244).
- S-3: add "and not applied globally" plus the registration-date rule to the Goal (117-119).
- D-N4: state the dedup check runs inside the `add` transaction (`db.transaction` is already `BEGIN IMMEDIATE`, db.py:82).
- ST-7: replace bullets 79-88 with the brief's four-row staging table.
- ST-5 error codes: already at 828-840; cross-reference from §3.

### 🟢 Nit 12: Reuse the existing main-worktree logic (new)
`projects.detect()` already runs `git rev-parse --git-common-dir` and takes the parent (projects.py:35-45). Extract it as the helper behind `main_worktree`.

### 🟢 Nit 13: Trim surface with no CUJ
Cut `project rename`; drop the hedged `render.py` entry, the stopword list (806-813) and constant names (856-857); set a SKILL.md line ceiling checked in `test_skills_content.py`; put `chanchi-lessons` in `SUGGESTED_CONFIG_LINE` as the single paste source.

### 🟢 Nit 14: Wording-only items, batch them
ST-2/S-8, S-4, S-7, S-9, S-10, ST-8 to ST-13, C-7 to C-12. Do not add D-5's new "conversation identity" alternative; Alternative J plus Major 5 cover it.

## The smallest set of changes that makes the design sound

1. One shared resolver; `ensure()` unchanged; renamed/nested audit-chain test. (Blocker 1)
2. Remove remote locator, `normalize_remote`, `--no-remote`, `rename`, Alternative C from stage 1. (Major 2, Nit 13)
3. `replaces` command and retire cascade to stage 2; `replaces` as a JSON field. (Major 3)
4. Lesson writes check origin scope; global list only for global-origin lessons and global sites. (Major 4)
5. One threat-model paragraph for identity flags. (Major 5)
6. One "Vocabulary and states" section from the brief plus the source-method sentence. (Major 6)
7. One Risks table from brief §13. (Major 7)
8. Shrink §7 to invariants; add the D-7 question to Q1. (Major 8)
9. One-sentence fixes: withdraw by retiring, `unchecked` in verify, `rejected_recurs`, dedup inside the transaction, Goal precision. (Nits 9-11)

**Declined as bloat:** IC-1 anchor columns, IC-2 read-at-apply, IC-3 fingerprint, IC-4 grant table, D-3 stage-1 `run open`, D-6 `withdrawn` state, ST-6 full hook contract, separate ST-5 command table.
