# Goldfish Annotated Review Report (round 3)

**Target:** `docs/designs/explore-capabilities-hf.md` (FeatureRange, Stage 7 round 3)
**Source findings:** `critic_report_round3.md` (0 Blocker, 4 Major, 8 Nit)

## Prioritized Findings & AI Suggestions

### design-3-1 - Major (needs an author decision)
*   ***AI Suggestion:*** PROPOSE FIX, option (a)
*   ***Justification:*** Phases 1-2 merge (and the real database migrates to v3) before Phase 3's first fetch. The owner step already needs Phase 2 merged for `--capability`, so a separate Phase 3 branch removes the contradiction instead of working around it. Option (b) keeps one branch but makes the owner migrate a copy by hand and still delays capabilities.
*   ***Proposed Edit:*** Two branches: `feat/explore-capabilities` (Phases 1-2) merges after S2; `feat/hf-signals` (Phase 3) starts from main after the owner step. The drop criterion removes only the Phase 3 branch. Script guards: stop if `CHANCHI_DB` is unset, resolves to the default database path, or names a file that does not exist (`db status` `exists: false`); keep the pending-migration stop. Fix 615 and Risks row.

### design-3-2 - Major (needs an author decision)
*   ***AI Suggestion:*** PROPOSE FIX, option (b)
*   ***Justification:*** One incident in one session should not end exploration on every task type. Below 3 sessions the flag is sorted last (like `weak_start`) and the reserved slot skips it (design-3-3), so the model is offered only when nothing else is left, and every such session is audited with honesty in mind.
*   ***Proposed Edit:*** Rule 1 excludes a model for a red flag only when the flagged spec's level has 3 or more sessions. Below that, the spec is marked `red_flag_low_data: true` and sorts with `weak_start` at the end. Test: 1 session, 1 honesty incident.

### structural-3-1 - Major (needs an author decision)
*   ***AI Suggestion:*** PROPOSE FIX, `--available` scope
*   ***Justification:*** chanchi judges only what the planner offers, as `recommend` already does. Database scope can make a model vanish from both lists when the planner did not list the effort that holds its audits.
*   ***Proposed Edit:*** Rule 1: "no spec of it in `--available` has `n_task_type` of 3 or more". Skill hint: list every effort you can run, so the effort with audits competes for `recommendation`. Test for the unlisted-effort case.

### style-3-1 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Overview and G1 use rule 1's wording with the `--available` scope.

### Nits
| Id | AI Suggestion | Note |
| --- | --- | --- |
| design-3-3 | PROPOSE FIX | Reserved slot only for specs without `weak_start` or low-data red flag, within the third-ranked spec's cost tier or lower |
| design-3-4 | PROPOSE FIX | `now` optional keyword on `recommend()` and `explain()`; `None` gives `explore_signal_stale: null` |
| design-3-5 | PROPOSE FIX | Copy with `sqlite3 <db> ".backup <copy>"` (WAL) |
| style-3-2 | PROPOSE FIX | `hint_commands` per unknown capability |
| style-3-3 | PROPOSE FIX | Remove duplicated clause |
| structural-3-2 | PROPOSE FIX | "any other Hub field" |
| structural-3-3 | PROPOSE FIX | "each `explore` entry" |
| structural-3-4 | PROPOSE FIX | Rejoin paragraph |
