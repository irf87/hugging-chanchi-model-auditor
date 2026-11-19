# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-690, top of file up to but not including "## Detailed Implementation Plan")
**Stage:** 7 (Critic Review), round 1. Mode: REVIEW.
**Standard:** `resources/document_standards/feature-spec-standard.md` (egm-design, egm-structural). egm-style used its persona's audit vectors because the persona names no bundled style standard.
**Settled items not re-raised:** Phase 3 drop criterion, no `source` column, the owner's budget override for the Hydrogen sessions, the known leak into `recommendation` (G2).

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `egm-design` | completed | 1 Blocker, 8 Major, 8 Nit |
| `egm-structural` | completed | 3 Major (one split Major/Nit), 5 Nit |
| `egm-style` | completed | 4 Major, 12 Nit |

After deduplication: **1 Blocker, 11 Major, 22 Nit entries.** Several Nit entries merge points from two reviewers, and structural-1-4 also carries Nit-level items. Where two reviewers raised the same point, the finding keeps the first reviewer's id and lists the others under "Also raised by". The synthesizer checked these code claims against the source and confirmed them:
- the prior and level fallback (`scoring.py` 134-144, 441-459);
- `models set` rejecting a spec with an effort (`catalog.py` 105-108);
- the `sessions.tags` column (`001_init.sql`:51);
- the synthetic migration 3 (`tests/test_db.py` 238-244).

## Prioritized Findings (Blockers -> Major -> Nits)

### design-1-1: The budget check flags small changes that follow the rule as over budget. Severity: Blocker
* **Reviewer Lens:** `egm-design`. Also raised by `egm-style` (style-1-2, rated Major).
* **Affected Scope:** Lines 87-90 (G3), 249-262.
* **Discrepancy Description:** The skill rule allows `max(1, floor(n/4))` exploratory sessions for a change with 2 or more sessions. `show` reports `budget: 0.25` and `over_budget` with no formula, which reads as `share > 0.25`. A 2-session change with 1 explore session (share 0.5) or a 3-session change with 1 (share 0.33) follows the rule and is still reported over budget. Small changes are common, and Alternative N (lines 620-622) defers prevention on the strength of this signal. The text also does not say whether `sessions` counts session refs or attempts.
* **Rationale & Recommendation:** Define `allowed = max(1, floor(n/4)) if n >= 2 else 0` and `over_budget = exploratory > allowed`. Report `allowed` next to `share`, and keep `share` as information only. Define `n` as distinct `session_ref` values, counting only the latest attempt. Update G3 to match.

### design-1-2: "Exploratory" in `show` counts sessions that did not come from `explore`. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-style` (style-1-3).
* **Affected Scope:** Lines 258-262, G3 at 87-90.
* **Discrepancy Description:** A session counts as exploratory when its model had fewer than 3 audited sessions of the task type when it started. The heuristic therefore also catches:
  * (a) the `recommendation` itself, which can rest on `complexity` or `global` data (lines 196-198, `scoring.py` 441-451);
  * (b) judgement picks under `insufficient_data` (SKILL.md step 4);
  * (c) high-complexity sessions, where `explore` is always empty;
  * (d) every session of a new or custom task type.

  The audited-count rule ("a verdict and an `audited_at`") also differs from `executor_records`, which drops sessions superseded by a non-executor retry. Because chanchi never parses the protocol line (lines 256-257), the design has no way to tell a real `explore` pick apart.
* **Rationale & Recommendation:** Preferred fix: record provenance in the existing `sessions.tags` column (`session start --tags explore`) and count tagged sessions in `show`. This needs no migration and gives an exact count. If the heuristic stays:
  * rename the field (for example `undertested_sessions`) and describe it as an upper bound;
  * limit it to `EXPLORE_COMPLEXITIES`;
  * leave out sessions whose model was the recommendation;
  * count sessions the way `recommend` does;
  * reword G3 to match.

### design-1-3: The `excluded` hint gives a command that fails. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 305-309.
* **Discrepancy Description:** `excluded[].spec` is a full `agent:model:effort` spec, and the hint is written as `chanchi models set <spec> --capability ...`. `catalog.set_model` rejects any spec that includes an effort ("models set takes agent:model without an effort", `catalog.py` 105-108), so a copied hint returns `invalid_value`.
* **Rationale & Recommendation:** State that the hint uses `agent:model` (the spec with the effort removed). Add a test that runs the hint string through `models set`.

### design-1-4: Editable install: changes go live as soon as they are checked out or written, not when they reach main. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-style` (style-1-4).
* **Affected Scope:** Lines 35-39, 152-158 (CUJ 3), 491-499, 577-578, 661-662.
* **Discrepancy Description:** Every project runs the live working tree of this checkout.
  * **Phase 2:** once Phase 2 code is checked out in that tree, on any branch, the next `chanchi` call from any project migrates the global database to v3. Switching back to main then gives `schema_too_new` everywhere. The NFR claim "the only irreversible step is migration 003 reaching main" is therefore wrong.
  * **Snapshot:** `--write` changes every project's `explore` output immediately, before the diff review and commit described in CUJ 3. Line 578 ("every refresh is reviewable as a git diff") implies the same review gate.
* **Rationale & Recommendation:**
  * In Rollout and the NFR, state that migration 003 becomes irreversible the first time any checkout of the installed tree that contains it runs `chanchi` against the real database.
  * Require Phase 2 development to happen in worktrees with `CHANCHI_DB` pointing at a scratch file.
  * In CUJ 3, either say that a written snapshot is live before it is committed and that the dry-run summary is the only review before exposure, or add an output-path option to `--write` so the file can be reviewed before it replaces the live one.
  * Adjust line 578 to match.

### design-1-5: The doc does not say how the fetch script reads the catalog. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 360-363, 398-417.
* **Discrepancy Description:** The script must check that every map entry exists in the catalog and find models with no `vision` row. Both need the global database. The two obvious approaches both cause problems:
  * Opening SQLite directly skips bootstrap and version checks. That is the flaw the doc uses to reject Alternative I (line 576), and the queries would break against a v2 database.
  * Importing `chanchi.db` would migrate the real database through `open_operational()`, and it contradicts "not imported by the package".
* **Rationale & Recommendation:** Specify that the script runs `chanchi models list --all` through `subprocess` and parses the JSON (after Phase 2 that output includes `capabilities`). The script then stays a stdlib-only consumer of the public CLI and still gets the package's version checks.

### design-1-6: No Risks and Limits section. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-structural` (structural-1-1).
* **Affected Scope:** The whole document. Risk content is scattered across 239-247, 249-262, 285-286, 450-455, 491-501 and 652-664.
* **Discrepancy Description:** The standard requires the spec to name its failure modes, security implications, scalability limits and their mitigations. The risks that exist are spread across sections. Several are not named anywhere:
  * explore sessions spend real project work on unproven models, with possible rejected work and rework;
  * the snapshot can go stale, and there is no age threshold or warning;
  * the hand-written map can drift when opencode renames or re-versions a model;
  * the editable-install exposure (design-1-4);
  * untrusted Hub text (design-1-7);
  * planners can ignore the budget;
  * scalability: the peer-set size and the hand-maintained map.
* **Rationale & Recommendation:** Add `## Risks and Limits` between Alternatives Considered and Non-Functional Requirements, as a table with Risk, Impact and Mitigation columns. Link each row to the subsection that holds the detail. The leak (settled) only needs a row pointing to line 239. Add a staleness rule, for example `stale: true` when `generated_at` is more than N days old.

### design-1-7: Untrusted Hub text reaches planner agents in every project. Severity: Major (security)
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 386-396, 437-440, 462-466, 654-657.
* **Discrepancy Description:** The snapshot keeps every Hub row, including free-text `source_name` and `source_url` written by model authors or third parties. Proxy entries "list their raw rows" in `external_signals`, so that text flows into `recommend` JSON that agents read in every project. The only gate is the owner reading a diff of about 210 rows. The doc does not treat this as a prompt-injection channel.
* **Rationale & Recommendation:** Emit only allowlisted fields in `external_signals`, proxy entries included: `dataset_id` and `task_id` from the mapping, plus numeric `value`, `date` and `peers`. Never emit `source_name` or `source_url`. Name this risk in the Security NFR.

### design-1-8: The signal bucket puts models the Hub rates weak ahead of models with no data. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 210-213, 217-220.
* **Discrepancy Description:** The no-signal bucket ranks below bucket 0, so a bottom-quartile model (signal 0.05) is offered before any closed or unmapped model. Because buckets sort before cost, a cost-3 model in bucket 2 also beats a cost-1 model in bucket 1. The reserved slot only protects third place. This treats bottom-quartile evidence as a reason to try a model first.
* **Rationale & Recommendation:** Make no-signal a neutral bucket, for example between buckets 0 and 1. Alternatively, sort by cost first and use the bucket only to break ties within a cost tier. Add one sentence explaining the choice.

### design-1-9: One model at several efforts can fill the `explore` list. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 192-200, 203-221.
* **Discrepancy Description:** `n_task_type` is counted per `(agent, model)`, but candidates are specs that include an effort. With `--available "...glm-5.3:low,...glm-5.3:high,..."`, both GLM specs are explorable with the same signal and can take 2 of the 3 slots. That crowds out other models and works against spreading trials.
* **Rationale & Recommendation:** Keep at most one spec per `(agent, model)` in `explore`: the lowest cost tier, then the first effort as written in `--available`. State this in rule 4.

### style-1-1: "How `recommend()` picks today" misstates the prior and the level search. Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 44-49.
* **Discrepancy Description:** The text does not match `scoring.py` (verified at 134-144 and 441-459) in three ways:
  * `prior_for` is called with the filters of the chosen level, not always task type and complexity.
  * It falls back to the mean of all records before 70, so 70 applies only with no records at all.
  * When no level reaches 3 sessions, the first non-empty level is used.

  Readers rely on this section to judge the weak-start rule (205-207) and Alternative C.
* **Rationale & Recommendation:** Replace with: "...where the prior is the population mean of executor sessions matching the chosen level's filters (falling back to all sessions, then to 70 when there are none). If no level reaches 3 sessions, the first level with any session is used." Also check that line 206 (`prior_for(records, task_type, None)`) is the prior intended for weak start.

### structural-1-2: Additional Resources and Future Improvements sit under Non-Functional Requirements. Severity: Major
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Lines 668, 676.
* **Discrepancy Description:** Both are H3 headings after `## Non-Functional Requirements`, so the outline makes them NFR subsections. Lines 118 and 537-539 refer to Future Improvements as a top-level destination.
* **Rationale & Recommendation:** Promote both to H2, with Future Improvements first and Additional Resources last.

### structural-1-4: Rejection rationale attributed to "discussion" without a link. Severity: Major for Alternative A, Nit for the rest
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** Lines 511-512 (A). Nit level: 518, 529, 546, 553, 561, 569, 577, 586, 594, 602, 610, 620, 629, 638, 647, and inline at 199 and 266.
* **Discrepancy Description:** The standard forbids attributing a rejection to a maintainer without linking the issue, discussion or PR. Alternative A says "Rejected by author: dropped after discussion" and links nothing. The other alternatives give concrete reasons, so their "by author" prefixes are only unlinked attributions.
* **Rationale & Recommendation:** For A, state the trade-off itself: "Hub prices are per token while the owner pays fixed monthly plans, so a derived tier would misrank cost; it also needs a table rebuild migration." Remove "after discussion". For the rest, either drop the "Rejected by author:" prefix or link the decision record once at the top of Alternatives, pointing to the brief's "Key Decisions & Staging for Next Steps" section.

### Nits

| Id | Lines | Problem | Fix |
| --- | --- | --- | --- |
| design-1-10 (also style-1-5) | 80-83 | G1 promises up to 3 `explore` entries whenever under-tested models exist. Rules 1 and 5 and `--require` remove red-flagged candidates, the recommendation and capability-excluded specs. | Add "that are not red-flagged, not the `recommendation`, and not excluded by `--require`". |
| design-1-11 | 95-96 | G5 says "the signal weighted for the requested task type", but 430-431 drops the weights. | Use "the signal mapped to the requested task type". |
| design-1-12 (also style-1-12) | 99-100, 472-474, 656-657 | "No network I/O, a test enforces this" overstates an import blocklist. The blocklist can miss `from urllib import request`, `importlib.import_module` and `subprocess` calls. | Either say "imports no network module" or extend the AST check to `ImportFrom` and `importlib.import_module`. Reword the NFR to match. |
| design-1-13 | 421-424 | The `percent` unit range check lets a fraction (0.669) be averaged with 66.9. SWE-bench_Verified and _Multilingual have no allowed `task_id`, yet line 421 says every entry has one. | Add a fraction-detection rule (or require values above 1). List the `task_id` values for those two benchmarks. |
| design-1-14 (also style-1-14) | 328, 368, 501 | The "`signal_for` hook" is used before it is defined. Line 328 says Phase 3 is removed by "deleting its own files", but 368 also removes the hook. Line 501 says `explore` "falls back to cost order", but weak start still sorts first. | Name the hook and its call site in Phase 1 rule 3.2. Say "its own files and the `signal_for` hook". Say "orders without the signal bucket (rule 3)". |
| design-1-15 | 298 | The behaviour of `--require` with an unknown capability name is not specified. | State `invalid_value` with `valid_values`, as `taxonomy.validate_choice` does. |
| design-1-16 | 228, 459-470 | The `external_signals` shape for a mapped model on a task type with no signal (null, or an object with `signal: null`) is not specified. | Specify one shape. |
| design-1-17 | 491-499 | Phase 2 rollout leaves out two things the brief lists: regenerating `template.db`, and the collision with the synthetic migration 3 in `tests/test_db.py` 238-244. | Add both to Rollout. |
| structural-1-3 | 7, 650, 666, 689 | Horizontal rules separate only some H2 pairs. | Keep the rules at 7 and 689 and remove 650 and 666, or use a rule between every H2. |
| structural-1-5 | 605-612 | Alternative M uses "Status" under a heading that implies rejection. | Retitle it "Alternative M (fallback, not rejected)" or add a lead sentence to Alternatives. |
| structural-1-6 (also style-1-16) | 313, 361, 442, 678 (also 328) | Lines run past the roughly 100-column wrap. | Rewrap. Move the trailing sentence of the 328 table cell out of the cell, to a sentence below the table. |
| structural-1-7 | 204-216 | The nested list uses `1. ` while the parent uses `1.  `. | Match the parent's spacing. |
| structural-1-8 | 670-674 | The design spec reference at 672 is a code span, not a link. | Make it a relative link to `../superpowers/specs/2026-10-18-chanchi-model-auditor-design.md`. |
| style-1-6 | 663-664 | "before a snapshot exists" implies the snapshot can change `candidates` and `recommendation`. G2 and line 469 say it cannot. | Use "Without `--require`, ... identical to today, with or without a snapshot." |
| style-1-7 | 197-198 vs 221 | "the two fields are independent" contradicts rule 5. | Use "computed separately, except that the `recommendation` spec is never also in `explore` (rule 5)". |
| style-1-8 | 194-196 | The across-efforts rule is justified by a Phase 2 storage decision. | Delete the clause and keep the GLM example. |
| style-1-9 | 199-200 | A drafting-history parenthetical repeats Alternative Q. | Delete it. |
| style-1-10 | 30-31 vs 360 | "about 20 open-weight models" conflicts with closed Qwen models and the 22 listed entries. | Use "about 22 models through opencode, most of them open-weight". |
| style-1-11 | 13-14, 33 | Absolute claims ("never reach", "no way to learn"). Judgement picks under SKILL.md step 4 can already produce audits. | Use "rarely" and "no way short of manual picks". |
| style-1-13 | 659-660 | "under a few milliseconds" is stated as if measured. | Use "expected to be a few milliseconds; add a cache only if a measurement shows otherwise." |
| style-1-15 | 361-363 | The referent of "the missing opencode models" is ambiguous. | Use "Map entries whose models are not yet in the catalog are registered with `chanchi models add` before the first fetch." |
| style-1-16 (wording part) | 442, 558, 678 | Asides about the brief's history ("the count the brief quotes", "drew on", "Stage 4 in the brief") need context the reader lacks. | Drop the 442 aside. Rewrite 558 in the conditional. Remove the stage reference at 678 or explain it. |
