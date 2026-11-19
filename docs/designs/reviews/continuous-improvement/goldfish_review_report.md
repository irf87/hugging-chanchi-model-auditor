Status: resolved

# Goldfish Annotated Review Report

**Target:** `docs/designs/continuous-improvement.md` (full file; Revision 2 after this resolution)
**Source:** [consolidated_review_report.md](consolidated_review_report.md). The finding ids below
are the ids used there.
**Decision:** the author asked to apply the consolidated actions ("aplica las correcciones"). Every
action item was resolved as PROPOSE FIX and applied. The items under "Declined" in the
consolidated report were declined, for the reasons Stage 8 gave.

## Applied fixes

| Action | Category | What changed in the design |
|---|---|---|
| A1 Shared resolver | PROPOSE FIX | §2 rewritten. `identify()` gains `conn` and checks registered path locators after an explicit `--project` and before the folder slug. `resolve_project()` and `change open` use it. `ensure()` is unchanged. The Goals cover the audit commands, CUJ 4 adds `change open` and `session start` from a nested repository, and the NFR performance text matches (no extra git call) |
| A2 `--format md` | PROPOSE FIX | `md` is added to `cli.FORMATS`; `_emit` writes `payload["markdown"]`; only `export` fills it. Item 14 names the changes |
| A3 Broken tests | PROPOSE FIX | `tests/test_db.py` is item 3, with the exact changes. `git_head` lives in `projects.py`, the only module allowed to import `subprocess` |
| A4 Event foreign key | PROPOSE FIX | `lesson_events` records `site` and `site_project_id` instead of `site_id`, so `reopen-site` can delete a row |
| A5 Risks | PROPOSE FIX | New H2 "Risks and Mitigations": brief §13 rows plus the declared-identity, thresholds and JSON-target rows |
| B1 Definitions | PROPOSE FIX | The principles and triggers are in the Overview. New H3 "Vocabulary and states" holds today's audit flow, the glossary, generality, target, severity, both state tables and the reason codes. A sentence says the source method is private and the document is complete without it. CUJ 1 uses `<conversation id>` |
| B2 Scope cuts | PROPOSE FIX | The remote locator, `normalize_remote`, `--no-remote` and `project rename` are removed (Alternative C rewritten, a Future Improvement added). The `replaces` command is removed; `replaces` is a JSON field, and the retire cascade moves to stage 2 (§5, CUJ 6) |
| B3 Writer scope and threat model | PROPOSE FIX | Lesson-level commands check the origin scope; site commands check the site scope. A new "Actor and threat model" paragraph, plus a line in the Goals |
| B4 Hook contract | PROPOSE FIX | §7 reduced to invariants, with brief §10 as the draft contract. Q1 to Q5 are marked answered from `hook-facts-2026-11-19.md`; new Q6 asks whether Claude Code can filter hooks by command text |
| B5 Zero-decision gaps | PROPOSE FIX | §3 adds the `add` JSON schema, the events table, the apply rules, the duplicate re-pointing and reopen rules, the read commands' scope, arguments and output, `rejected_recurs`, the Markdown layout, and the `--author` meaning and effort check. §4 adds the classes table, `warnings` and the transaction. §5 adds the verify path rules, `unchecked` and the output schema. Item 5 is the error table with the `details` field. Item 10 (`render.py`) is dropped |
| B6 Steps and tests | PROPOSE FIX | Stage 1 has seven steps with pytest checkpoints. Named fixtures, new `conftest.py` fixtures, complete test lists, concrete "same as before" checks and exact migration-check commands |
| B7 Goals and claims | PROPOSE FIX | Inbox Goal precision; closed stopword list; 150-line skill ceiling with a test; Problem claims calibrated; retune trigger |
| B8 Alternatives | PROPOSE FIX | "Rejected by author" removed from all 15 alternatives; each reason states the deciding trade-off |
| Nits | PROPOSE FIX (batch) | `_git` helper, `catalog._model_row`, `importlib.resources`, `record._csv`, `SUGGESTED_CONFIG_LINE` as the single paste source, the withdraw sentence, item 21 as Modify, stage-2 commands kept out of the stage-1 skill, the position of the item 18 sub-bullet, the item 20 test, canonical paths, the source of truth for review columns, global-origin lessons must be `agnostic`, `project` lessons applied only at their origin, `modelspec` effort, the diagram, valid SQL `ORDER BY`, links in Additional Resources, the NFR rollout pointer removed, "*Drafted with EGM*" removed, glosses for agy and the launcher |

## Declined

IC-1, IC-2, IC-3, IC-4, D-3, D-6, ST-6, the separate ST-5 command table, and D-5, as listed in the
consolidated report. Also declined as Nits: IC-7 (the particular rule stays in `CHECK`) and IC-8
(globally applied lessons stay out of every inbox; the global setup is loaded in every project).

## Counts

- Accepted fixes: 13 action items plus the Nit batch.
- Contested: 0. Escalated: 0.
- Declined: 11.
- Not re-audited: the revised document has not had a fresh Goldfish pass.
