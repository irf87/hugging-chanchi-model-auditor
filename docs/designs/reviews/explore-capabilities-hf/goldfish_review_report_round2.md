# Goldfish Annotated Review Report (round 2)

**Target:** `docs/designs/explore-capabilities-hf.md` (FeatureRange, Stage 7 round 2)
**Source findings:** `critic_report_round2.md` (0 Blocker, 7 Major, 24 Nit)

## Prioritized Findings & AI Suggestions

### design-2-1 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified: eligibility keys records by `(agent, model, effort)` (`scoring.py` 435-451), while `n_task_type` counts across efforts. Split efforts recreate the stuck loop.
*   ***Proposed Edit:*** `n_task_type` becomes the count of the spec's own effort; a model is explorable while no available effort of it has 3 or more audited sessions of the task type. Rule 4 keeps the effort with the most task-type sessions, then the first as written. Skill rule: explore sessions of a model stay on the effort `explore` listed. CUJ 1 says "3 audited `bugfix` sessions at that effort". Test for the split case.

### design-2-2 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** State the order: filters, then per-model dedupe, then sort, then top 3. A model is not explorable when any of its specs in `--available` is red-flagged or is the `recommendation`. Weak start uses the sessions counted in `n_task_type`. G1 says "one spec per `(agent, model)`".

### design-2-3 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Catalog and capability commands (`models add`, `models set --capability`) are owner data operations, run with the installed `chanchi` and no `CHANCHI_DB`; `--capability` only after Phase 2 is merged. Fetch runs use a copy of the real database taken after those writes, never an empty scratch file. Printed commands say so. Risks row added.

### design-2-4 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Replace `hint` with `hint_commands`: two complete commands (`vision=yes` and `vision=no`). Skill rule: planners never run `models set`; they report excluded `unknown` models to the owner. Risks row "agent self-classifies capabilities". Test runs each command through `models set`.

### design-2-5 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** `src/chanchi/__main__.py` exists, so `python -m chanchi` works; `db status` does not bootstrap.
*   ***Proposed Edit:*** The script refuses to run when `CHANCHI_DB` is unset, runs `[sys.executable, "-m", "chanchi", "db", "status"]` first and stops if migrations are pending, then `models list --all` the same way. Any non-zero exit stops the script and prints chanchi's error JSON. Risks row added.

### style-2-1 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** `allowed = 0 if sessions < 2 else max(1, floor(sessions / 4))`; `share: null` with 0 sessions; `over_budget` is `null` until the change has `closed_at` (a partial count is not a verdict); a `session_ref` is exploratory when any of its attempts is tagged, and retries keep the tag. G3 mirrors this.

### style-2-2 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** The script stops and prints `chanchi models add --agent <a> --model <m> --cost <tier> [--efforts ...]` for the owner to complete; "variants" becomes "cost tier and efforts".

### Nits
All 24 Nits: PROPOSE FIX as written in `critic_report_round2.md`. design-2-8 is applied as: the CLI computes `now` and passes it to `recommend()` and `hfsignals`; tests inject it.
