# Goldfish Annotated Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-690, Stage 7 round 1)
**Source findings:** `critic_report.md`

## Prioritized Findings & AI Suggestions

### design-1-1 [`egm-design`] - Severity: Blocker
*   **Affected Scope:** G3, Phase 1 "Budget".
*   **Discrepancy:** `over_budget` reads as `share > 0.25`, so a 2- or 3-session change with 1 explore session is flagged though it follows the rule.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Valid arithmetic gap between the skill rule and the report.
*   ***Proposed Edit:*** Define `n` = distinct `session_ref` values of the change (latest attempt only), `allowed = max(1, floor(n / 4))` when `n >= 2`, else 0, and `over_budget = exploratory > allowed`. Report `allowed` beside `share`; `share` is information only. Update G3.

### design-1-2 [`egm-design`, `egm-style`] - Severity: Major
*   **Affected Scope:** Phase 1 "Budget", G3.
*   **Discrepancy:** The history heuristic counts recommended picks, judgement picks, high-complexity sessions and new task types as exploratory.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** `sessions.tags` already exists (`001_init.sql`, `session start --tags` in `cli.py`), so exact provenance costs no migration.
*   ***Proposed Edit:*** The skill requires `chanchi session start ... --tags explore` for every session taken from `explore`. `show` counts sessions tagged `explore` (exact). The history heuristic is dropped.

### design-1-3 [`egm-design`] - Severity: Major
*   **Discrepancy:** The `excluded` hint uses a full spec; `models set` rejects efforts (`catalog.py` `set_model`).
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** The hint uses `agent:model` (effort removed). Add a test that runs the hint through `models set`.

### design-1-4 [`egm-design`, `egm-style`] - Severity: Major
*   **Discrepancy:** The editable install runs the main checkout's working tree, so checking out the branch there, or running `--write` there, goes live before review.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** State that the main checkout is production: feature work, including the fetch script's `--write`, happens only in worktrees with `CHANCHI_DB` on a scratch file; the main checkout only receives merges. Migration 003 becomes irreversible the first time the main checkout contains it and runs against the real database. CUJ 3 runs in a worktree; the snapshot goes live on merge. Fix NFR and Alternative I wording.

### design-1-5 [`egm-design`] - Severity: Major
*   **Discrepancy:** How the fetch script reads the catalog is unstated in the Technical Plan.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** File 19 already says this; the Technical Plan must too.
*   ***Proposed Edit:*** Fetch script bullet: it reads the catalog by running `chanchi models list --all` through `subprocess` (with the caller's `CHANCHI_DB`) and parsing the JSON; it never opens SQLite or imports `chanchi`.

### design-1-6 [`egm-design`, `egm-structural`] - Severity: Major
*   **Discrepancy:** No Risks and Limits section; several risks unnamed.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Add `## Risks and Limits` (table: risk, impact, mitigation) between Alternatives and NFRs, covering explore cost, snapshot staleness (`explore_signal_stale: true` when `generated_at` is older than 90 days), map drift, editable-install exposure, untrusted Hub text, ignored budget, the known leak, and scale of the hand-written map.

### design-1-7 [`egm-design`] - Severity: Major (security)
*   **Discrepancy:** Free-text `source_name` / `source_url` reach agents through `recommend`.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** `external_signals` emits only allowlisted fields: `dataset_id`, `task_id`, numeric `value`, `date`, `peers`. The snapshot keeps source fields for the owner's review, but `hfsignals` never outputs them. Add to the Security NFR and a test.

### design-1-8 [`egm-design`] - Severity: Major
*   **Discrepancy:** No-signal ranks below bottom-quartile models, and buckets outrank cost.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Unverified data should not beat cost, and weak evidence should not beat no evidence.
*   ***Proposed Edit:*** Sort order becomes: weak start last, `cost_tier`, signal bucket (no signal ranks between bucket 0 and bucket 1), `n_task_type`, spec. Keep the reserved no-signal slot.

### design-1-9 [`egm-design`] - Severity: Major
*   **Discrepancy:** One model at several efforts can take several `explore` slots.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** At most one spec per `(agent, model)` in `explore`: the first effort as written in `--available`.

### style-1-1 [`egm-style`] - Severity: Major
*   **Discrepancy:** "How recommend() picks today" misstates `prior_for` and the level fallback.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified in `scoring.py` (`prior_for`, level loop).
*   ***Proposed Edit:*** Prior = mean of sessions matching the chosen level's filters, then all sessions, then 70. If no level reaches 3 sessions, the first level with any session is used. The weak-start prior `prior_for(records, task_type, None)` is intended (task type, any complexity, matching how `n_task_type` counts).

### structural-1-2 [`egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Promote Future Improvements and Additional Resources to H2, in that order, after the NFRs.

### structural-1-4 [`egm-structural`] - Severity: Major (A), Nit (rest)
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Alternative A states the trade-off instead of "after discussion". Add one lead sentence to Alternatives linking the brief's decisions section; keep "Rejected by author" since the author is the decision maker and the brief records the decisions.

### Nits
| Id | AI Suggestion | Note |
| --- | --- | --- |
| design-1-10 | PROPOSE FIX | G1 conditions added |
| design-1-11 | PROPOSE FIX | "mapped to" |
| design-1-12 | PROPOSE FIX | AST check also covers `ImportFrom`, `importlib.import_module` and `subprocess`; wording "imports no network module" |
| design-1-13 | PROPOSE FIX | Values in (0, 1] on a percent benchmark are rejected; task ids for Verified/Multilingual are taken from the first snapshot and recorded in `hfsignals.py` before merge |
| design-1-14 | PROPOSE FIX | Name the hook in rule 3; fix rollback wording |
| design-1-15 | PROPOSE FIX | `invalid_value` with `valid_values` |
| design-1-16 | PROPOSE FIX | `external_signals: null` when the task type has no signal |
| design-1-17 | PROPOSE FIX | Rollout mentions `template.db` and the synthetic migration 3 in `tests/test_db.py` |
| structural-1-3 | PROPOSE FIX | Keep only the rules at the top and before the implementation plan |
| structural-1-5 | PROPOSE FIX | Retitle M "(fallback, not rejected)" |
| structural-1-6 | DECLINE | Wrapping only |
| structural-1-7 | PROPOSE FIX | List spacing |
| structural-1-8 | PROPOSE FIX | Relative link |
| style-1-6 to style-1-11, style-1-13, style-1-15, style-1-16 | PROPOSE FIX | Wording |
