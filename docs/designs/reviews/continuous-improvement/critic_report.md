# Stage 7: Critic Review report

**Target:** `docs/designs/continuous-improvement.md`, FeatureRange lines 1-781
**Goldfish context:** `docs/designs/continuous-improvement.brief.md`
**Reviewers:** egm-design (feature-spec-standard), egm-structural (feature-spec-standard), egm-style (persona only)

Mode: uninterrupted, so this is a single audit round with no resolution step.

---

## egm-design

**Verdict: needs revision** (0 Blockers, 7 Majors, 6 Nits). Claims checked against projects.py, taxonomy.py, errors.py, db.py, modelspec.py, record.py, cli.py, 001 and 003 migrations.

### 🟡 Major D-1: Changing `ensure()` breaks the audit commands that follow it
**Scope:** 433-436, 98, 613-614; cli.py:57-58, 123; projects.py:65-91.
Only `change open` calls `ensure()` (record.py:99). `session start`, `incident add` and the rest resolve via `_pid()` → `resolve_project()` → `identify()`, slug only. In a renamed or nested registered project, `change open` lands in the registered project and the next commands fail or hit another row: the split history the change is meant to prevent. `ensure()` has no `cwd`; explicit `--project` precedence is unstated.
**Fix:** Apply the locator step in `resolve_project()`/`identify()` too; explicit `--project` always wins; add a CUJ `change open` → `session start` → `incident add` in a renamed/nested project.

### 🟡 Major D-2: Performance section contradicts the resolution order
**Scope:** 433 vs 751-753.
Slug-first would bring back the nested-repo bug when an inner repo already has a slug row. "One indexed query" is doubtful: a longest-prefix match cannot use `UNIQUE(kind, value)` unless the code queries each ancestor path. **Fix:** Locators first; say how the prefix lookup is done.

### 🟡 Major D-3: Self-review guard and `--author human` rest on caller-supplied values
**Scope:** 99-100, 105, 445-457, 485, 171, 182-187.
- The spec never says where a stage-1 agent gets its real conversation id; CUJ 1 uses `<session id>` without a source. Made-up labels let same-conversation reviews pass.
- `check_writer` passes any `--author human…`; `modelspec.parse` accepts it from anyone (modelspec.py:23-24, 30). An obedient agent "acting for the person" can bypass "unknown role is refused" (100) by mistake.
- `--author` means the lesson author's model on `add` but the actor on `review`/`apply`.
**Fix:** State the threat model for all three identity flags; say where each harness gets the conversation id in stage 1 (or issue a chanchi id via a stage-1 `run open`); consider a TTY or env opt-in for `human`; rename or document the dual-meaning flag.

### 🟡 Major D-4: No Risks and Mitigations section
Same as ST-1. Also add the forgeable-identity risk (D-3), the dedup race (D-N4) and Spanish-tuned thresholds on English text.

### 🟡 Major D-5: Alternatives rejected "by author"; B is circular; no alternative for stage-1 conversation identity
Same core as ST-2; adds the missing alternative for conversation identity.

### 🟡 Major D-6: An approved lesson that proves wrong cannot be withdrawn
**Scope:** 57-59, 469-497, 532-543.
`review`/`reopen` accept only `pending`, `postponed`, `rejected`, `duplicate`. While one site stays `applied`, the lesson keeps reaching every inbox (537). **Fix:** Add a `withdrawn` transition from `approved` (writer of scope, with reason; removes it from inboxes; `verify` flags its applied sites), or state the limit.

### 🟡 Major D-7: Stage-3 Claude Code adapter cannot deliver the fast path as described
**Scope:** 591-600, 604-607, 126-128.
The contract says the adapter calls chanchi only for commands containing `chanchi`, with no Python start-up. But the installed Claude Code entry is the chanchi command itself (604), and Claude Code matchers match tool names (`Bash`), not command text. So every Bash call starts Python, opens the DB and parses the raw payload, not the normalized `v:1` object; the `{"decision": "block"}` mapping to Claude Code's PreToolUse output is unstated (reviewer did not verify the current format). **Fix:** Specify a thin shell/JS adapter, or add command-content filtering to Q1; state the per-call overhead budget.

### 🟢 Nit D-N1: Global-origin lessons with `project`/`particular` generality have no review scope; apply targets are not validated
Lines 461-467, 226-232, 490-493. Nothing stops `apply --site` of A's `project` lesson into B, or a `particular` lesson globally.

### 🟢 Nit D-N2: Reopening a `duplicate` does not take back the occurrences moved to N; duplicate chains are possible
Lines 486-489.

### 🟢 Nit D-N3: `apply` "inserts or updates" skips `reopen-site` and is underspecified
Line 491 vs brief 255-260. Which from-states? Re-applying `retired`? One `where_` cannot track a fix spanning a role plus three wrappers.

### 🟢 Nit D-N4: Dedup check and insert are not stated to share one `BEGIN IMMEDIATE` transaction
Lines 472-479, 518-523. Parallel panes can insert two near-duplicates.

### 🟢 Nit D-N5: Path canonicalization and order
Lines 426-431, 407-409. Canonicalize the stored locator as well as the cwd (macOS `/var` vs `/private/var`); align `--project`/`--global` order with the brief; linked worktrees outside the main path fail with `--no-remote`.

### 🟢 Nit D-N6: `register` slug collision and `--name` orphaning
Lines 413-417. A second clone with `--no-remote` hits `projects.slug UNIQUE` (001_init.sql:17) with no defined error; `--name X` leaves the folder-slug row's audit history orphaned.

**Checked and consistent:** `ALL_AGENTS`, `SEVERITIES`, `modelspec.parse`, `bak-v<N>` and `schema_too_new` in db.py, the 003 precedent, migration splitter with trailing comments, `COALESCE` expression indexes.

---

## egm-structural

**Verdict: FAIL** (1 Blocker, 6 Majors). Heading hierarchy is sound. Mapping to the standard: Problem ✓, Goals/Non-Goals ✓, Architecture ✓ (Technical Plan), Alternatives ✓, **Risks & Mitigations missing**.

### 🔴 Blocker ST-1: No Risks & Mitigations section
**Scope:** whole document (nothing between 611 and 757).
The standard requires failure modes and their mitigations. The brief had a risk table (§13, brief 470-479); the spec kept only security/privacy (747-750) and schema rollback (611-620). Unhomed risks: word overlap misses rephrased duplicates (mitigation: read pending rules first); lessons pile up unreviewed (`summary` counts, stage-3 session-start line); role files keep growing; the stage-1 declared role can be wrong (only implied at 196); the method detects nothing on its own.
**Fix:** Add an H2 "Risks & Mitigations" table from brief §13 plus security and rollback rows.

### 🟡 Major ST-2: Rejection reasons credit the author instead of a trade-off
**Scope:** Alternatives A (624-630), B (632-638), K (704-710); pattern across 629-741.
"Rejected by author:" with no linked decision; A is owner preference, B is circular, K is "out of scope". The real trade-offs sit in the Cons. **Fix:** Drop the attribution or link the decision; state each reason as a trade-off.

### 🟡 Major ST-3: No Vocabulary section
Brief §1 (110-131) defined writer role, reporter, site, maintenance conversation, inbox, generality values, harness vs `agent`, conversation vs session. The spec breaks the conversation/session rule at line 171. **Fix:** Add a glossary H3; change `<session id>` to `<conversation id>` at 171.

### 🟡 Major ST-4: No States subsection
**Scope:** §1 and §3 (266-504).
The brief's two transition tables (brief §4, 233-263) are scattered into command bullets (485, `apply`, 551). Reason-code meanings (brief 246-249) are gone. **Fix:** Restore both tables and the reason-code definitions under an H3 "States".

### 🟡 Major ST-5: No command table, error-code list or severity table
**Scope:** §3 (443-504), Goals (102), skill (572).
- `lesson replaces` (494) is new and missing from the scope-of-check table (461-467).
- `project writers` syntax never given; `project list/show`, `lesson list/inbox` have no stage or guard.
- Error codes used but never listed; `invalid_transition` and `lesson_not_found` disappeared.
- Severity levels never defined (brief 192-199 did).
**Fix:** Add command-surface table (command | stage | scope checked | needs registration), error-code list, severity table.

### 🟡 Major ST-6: Hook contract (§7) is incomplete
**Scope:** 583-609.
Missing from brief §10: command matching (split on `&&`/`||`/`;`/`|`, `shlex`, ignore `echo` and quoted text); the guarded-verb list (`replaces` not included); why chanchi's exit code 2 must never reach a hook (Claude Code reads 2 as "block"); the `session-start` line and its re-send on resume/compact; the fixture-test matrix (brief 424-428).

### 🟡 Major ST-7: No staging table
**Scope:** 38-41, 77-88, 608-609.
The brief's Stage | Migration | Ships | Depends on table and its per-stage shipping rule are gone; stage 2's "no migration" appears only in a heading (528). **Fix:** Add a staging table before Rollout.

### 🟢 Nit ST-8: Diagram border broken at 255-256; `taxonomy.py` missing from the diagram (changed at 389)
### 🟢 Nit ST-9: Mixed numbered/unnumbered H3s in the Technical Plan; "(§4)" at 478 means a different section than the brief's §4
### 🟢 Nit ST-10: `---` dividers used unevenly (9, 743, 759, 780)
### 🟢 Nit ST-11: `ORDER BY <generality, severity, occurrences>` at 543 is not valid SQL; write a CASE or mark it pseudocode
### 🟢 Nit ST-12: Additional Resources (774-778) does not link the Goldfish reports or the source files
### 🟢 Nit ST-13: NFR "Rollout and rollback" bullet (757) only points back to the Technical Plan

---

## egm-style

No Blockers. The prose is mostly dry and direct. Most problems are terms and claims that depend on the brief or are not calibrated.

### 🟡 Major S-1: Undefined vocabulary and references that resolve only in the brief
**Scope:** 17, 24, 45, 99, 139, 171, 180, 569, 579, 632, 648, 673, 682, 691-692, 719, 774.
- The brief's §1 glossary (harness stored as `agent`, writer role, reporter, conversation vs session, site, maintenance run) was not carried over.
- "Agent" means the harness column at 99 and the AI actor at 17.
- Line 171 uses `--conversation <session id>` in the same CUJ as chanchi "session S3" (166, 173), merging the two words the brief keeps apart (brief 123). Use "conversation id".
- References to content not in the spec: "principle 4" (682), "record only what really went wrong" (691-692), "the five principles / five triggers" (569), "the source method" (648, 673, 719), "zoom-out v1" (632), "the seven Goldfish reports" (774).
- People are named four ways: "owner" (45, 228), "the user" (24), "the person" (17), "`human` agent" (99). Pick one term; keep `human` for the stored value.

### 🟡 Major S-2: Performance claim contradicts the design and is not measured
**Scope:** 751-754 vs 433-434.
Lookup "before" slug (433) vs "only when no slug row matches" (752). "At most one extra `git` call" ignores that steps 3 and 4 may need two calls. "A few milliseconds" has no measurement; cite one or state it as a target.

### 🟡 Major S-3: Goals state the inbox rule less precisely than the query
**Scope:** 117-119 vs 532-546.
The query also excludes lessons with an `applied` global site (540-541) and depends on `reviewed_at >= registered_at`. Add both to the Goal so tests derived from it match.

### 🟡 Major S-4: Problem statement claims go beyond the evidence
**Scope:** 46-47, 66-68, 69-70, 74-75.
"The fix is often in the wrong place" has no count; "the same kinds of failure come back" has three examples, no frequency; "the instinct is to add an instruction" speculates about motive; "the natural place" is a judgment. Reword to the observable facts.

### 🟡 Major S-5: Threshold caveat names no operator action
**Scope:** 525-526.
"Tuned on short Spanish texts" with an English stopword list (509). Connect it to the `force_new` rate in `summary` (500-501) and the fixture tests (brief 279-286): "retune when the rate exceeds X or a fixture fails". Name "the four numbers"; the section has six or more.

### 🟡 Major S-6: Skill size and context-cost goals are not measurable
**Scope:** 566, 755-756.
"Short sentences" and "kept short" cannot be tested. Give a line or word ceiling for SKILL.md. Line 566 says "Two sections" but lists three bullets.

### 🟢 Nit S-7: Absolute or loose claims
- 382-383 "will not change" → "this design does not expect to change".
- 699 "four of the facts … are unverified" does not match Q1-Q5 (about ten sub-questions) or the brief's six facts.
- 749 "`lesson add` does not read files": it reads stdin and runs `git rev-parse HEAD` (477); say it does not open target files.
- 108 "an open or applied lesson": "open" is not a status.
- 35-36 / 134 "never edits a role, skill, prompt or rules file" is accurate, but stage-3 `install` writes `~/.claude/settings.json` (604); restate the brief's explicit exception (brief 18-19).

### 🟢 Nit S-8: Alternatives boilerplate and circular reasons
**Scope:** 629-741. "Rejected by author:" repeated 15 times. A (629-630), K (709-710) and C (645-646) restate the decision instead of the deciding factor.

### 🟢 Nit S-9: Unmeasurable triggers in Future Improvements
Lines 764, 768, 769 ("real growth", "keep missing failures", "too many duplicates"). Name the signal or drop the trigger.

### 🟢 Nit S-10: Wordiness and loaded words
Line 22, 31, 56 ("has not taken hold"), 63-64 ("weak models"), 57/63 (private-project figures without the brief's "illustration" label), 112-113 (line-break hyphen in "end-of-conversation").

**Kept (not findings):** CHECK vs code split (382-387), rollback caveat (617-619), stage-1 trust caveat (195-197), Open Questions verification method (146-147).
