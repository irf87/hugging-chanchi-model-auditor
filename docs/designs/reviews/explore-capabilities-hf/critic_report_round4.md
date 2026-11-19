# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-855, top of file up to but not including "## Detailed Implementation Plan" at line 856)
**Stage:** 7 (Critic Review), round 4. Mode: REVIEW.
**Standard:** `resources/document_standards/feature-spec-standard.md` (egm-design, egm-structural). egm-style used its persona's audit vectors.
**Settled items not re-raised:** Phase 3 drop criterion, no `source` column on `model_capabilities`, the owner's budget override for the Hydrogen sessions, the known leak into `recommendation` (G2), line wrapping beyond 100 columns. Round-3 decisions also not re-raised: Phases 1-2 merge on their own branch before Phase 3; a red flag excludes a model only when it rests on 3 or more sessions, otherwise `red_flag_low_data`; rule 1 counts only efforts listed in `--available`.

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `egm-design` | completed | 0 Blocker, 1 Major, 4 Nit |
| `egm-structural` | completed | 0 Blocker, 1 Major, 5 Nit |
| `egm-style` | completed | 0 Blocker, 3 Major, 5 Nit |

After deduplication: **0 Blocker, 2 Major, 7 Nit.** When two or more reviewers raised the same point, the finding keeps one id and lists the others under "Also raised by".

**Round-3 fixes.** All three reviewers checked every round-3 fix (4 Majors, 8 Nits) and found them all applied and consistent: design-3-1 (option a) in Branches, CUJ 3, the fetch guards, Rollout, Risks row 803 and the NFR; design-3-2 (option b) in G1, rule 1, rule 3, rule 4, the JSON example, `explore_reason` and Risks row 804; and every other fix. Every internal cross-reference and the brief anchor resolve. Two fixes left new problems:
* design-3-2 (`red_flag_low_data`) is marked on a spec, but rule 4 can drop that spec (design-4-1).
* structural-3-1 (listed efforts only) relies on a skill rule that does not exist yet and is missing from the skill change list (style-4-1).

**Verified by the synthesizer against source:**
* `recommend()` computes `red_flag` per spec at the chosen level, falling back to the first level with any session (`scoring.py` 441-451, 176). This underlies design-4-1.
* `skills/chanchi-model-selection/SKILL.md` has no rule to list every effort; step 2 says to take the available list from the human's prompt (line 18). This underlies style-4-1.
* `db.operational_path()` uses `$XDG_DATA_HOME/chanchi/chanchi.db` when that variable is set (`db.py` 19-24). This underlies design-4-2.
* `session start` stores only the `--tags` it receives (`record.py` 227, 263-275). Tags are not copied between attempts. This underlies design-4-4.

## Prioritized Findings (Blockers -> Major -> Nits)

### design-4-1: `red_flag_low_data` is marked on one spec, but rule 4 can drop that spec, so the model escapes the penalty. Severity: Major
* **Reviewer Lens:** `egm-design` (Major 1). Also raised by `egm-structural` (Major 1) and `egm-style` (M1, N3).
* **Affected Scope:** Lines 217-219, 236-240, 247-252, 265-266, Risks row 804.
* **Discrepancy Description:**
  * Rule 1 says "the spec is marked `red_flag_low_data: true`" (237-238) and that the model "is offered only when nothing else is left" (239-240).
  * Rule 4 then keeps one spec per model: the highest `n_task_type`, then the first written in `--available`.
  * Example: `GLM:low` has 1 `bugfix` session with a `false_claim`, so it is flagged on n=1. `GLM:high` has 1 clean `bugfix` session and is listed first. Both have `n_task_type` 1, so rule 4 keeps `:high`. The kept entry has `red_flag_low_data: false` and GLM sorts normally. Reorder `--available` and GLM sorts last.
  * The step order at 217-219 does not say when `weak_start` and `red_flag_low_data` are computed, or whether they survive rule 4. It also does not say where a spec with both marks sorts.
  * The claim "offered only when nothing else is left" is too strong even when the mark survives. The spec is offered whenever fewer than 3 explorable specs rank ahead of it.
  * Two implementers could build different behaviour, and tests written from 239-240 would fail one of them.
* **Rationale & Recommendation:** Decide which level the mark belongs to and say so in rule 1, 217-219 and Risks row 804.
  * (a) Model-level, which matches the stated intent: "a model is marked `red_flag_low_data` when any of its listed specs is red-flagged on fewer than 3 sessions; the spec kept by rule 4 carries the mark, whichever effort it is." State that `weak_start` is computed on the kept spec, and that a spec with both marks sorts with the `red_flag_low_data` group.
  * (b) Per spec: rewrite 239-240 to say that only that spec sorts last, and that a clean sibling effort kept by rule 4 clears it.

  Under either option, change "only when nothing else is left" to "only when fewer than 3 explorable specs rank ahead of it". Add a test with two listed efforts where only the effort that rule 4 drops carries the flag.

### style-4-1: Rule 1 relies on a selection-skill rule that does not exist, and the skill change list leaves out several rules the spec assigns to the skill. Severity: Major
* **Reviewer Lens:** `egm-style` (M2). Also raised by `egm-structural` (Nit 5).
* **Affected Scope:** Lines 233-235, 267-268, 301-303, 315-317, 622-626.
* **Discrepancy Description:**
  * Line 234 says, in the present tense, "the selection skill tells planners to list every effort they can run". The current `SKILL.md` has no such rule. Step 2 says to take the available list from the human's prompt (`SKILL.md`:18).
  * The rule 1 rationale depends on this rule: without it, a model whose audits sit at an unlisted effort is explored again at another effort, and its sessions stay split.
  * The `SKILL.md` bullet in "Cross-cutting changes" (622-626) is the build checklist for the skill. It leaves out these rules that the scoped text assigns to the skill:
    * list every effort of a model that the human made available (234);
    * keep every explore session of a model on the effort of the `explore` spec (267-268);
    * at `high` complexity, treat a `level` other than `task_type+complexity` as weak evidence (301-303);
    * never explore in a blocking session (315-316);
    * the `· explore: <spec>` protocol-line suffix (317);
    * how to read `weak_start` and `red_flag_low_data`.
  * A builder working from 622-626 will miss them.
* **Rationale & Recommendation:**
  * At 234, write "the selection skill will tell planners to list every effort of a model that the human made available".
  * Extend the `SKILL.md` bullet at 622-626 so it names every skill rule above, plus the existing budget and `--tags explore` item. It is then the full inventory of `SKILL.md` changes.

### Nits

| Id | Lines | Problem | Fix |
| --- | --- | --- | --- |
| style-4-2 (also structural Nit 1, Nit 2; design N3) | 410-411, 455-458, 642-643 | Rule 3 (260-262) puts the `signal_for` hook in Phase 1, so it reaches main with Phases 1-2. Line 457 lists the hook among what "never reach[es] main" if Phase 3 is dropped, and 410-411 says Phase 3 is removed by deleting the hook, which would break rule 3. Line 642 says "Phase 3 adds files only", but Phase 3 also edits `scoring.py` (the real lookup, the three `explore_signal_*` keys, the snapshot load in `explain()`) and `cli.py` (`now`). | At 410-411 and 457, replace "the `signal_for` hook" with "the code that connects the `signal_for` hook to `hfsignals`", and add that the Phase 1 hook stays and returns no signal. At 642, write: "Phase 3 adds files and edits `scoring.py` and `cli.py`, on its own branch. Rollback: delete the snapshot; `explore_signal_source` becomes `missing` and `explore` orders without the signal bucket." |
| design-4-2 (also structural Nit 3) | 47, 496-497 | The guard compares `CHANCHI_DB` with the literal `~/.local/share/chanchi/chanchi.db`. `db.operational_path()` uses `$XDG_DATA_HOME` when it is set (`db.py` 23-24), so on such a machine, or through a symlink or a relative path, `CHANCHI_DB` can name the real file and pass the guard. That is the one hazard the guard exists for. | Compute the default path the way `operational_path()` does with `CHANCHI_DB` unset, and compare `Path(...).expanduser().resolve()` of both paths. At 47, write "the real database (`~/.local/share/chanchi/chanchi.db` by default)". |
| design-4-3 (also structural Nit 4, style N4) | 453 | "after the owner step" has no referent. It could mean the migration of the real database, setting capabilities (452) or the `models add` registrations (445-449). The registrations need the map, which is a Phase 3 file, so they cannot come before Phase 3 starts. | Write "after the merge of Phases 1-2 has migrated the real database". State separately that `models add` for map entries missing from the catalog happens during Phase 3, before its first fetch. |
| design-4-4 | 311 | "a retry of it ... keeps the tag" reads as automatic. `session start` stores only the `--tags` it receives (`record.py` 227, 263-275). The budget count (327) stays correct, because one tagged attempt is enough, but a skill author could drop `--tags explore` from retries and mislabel them. | Write "a retry of it is also started with `--tags explore` (chanchi does not copy tags between attempts)". |
| style-4-3 | 240 | "Its total session count does not matter" now follows the low-data red-flag sentence, so "Its" reads as the red-flagged spec, against the 3-session threshold just stated. | Write "A model's total session count across task types does not matter", or move the sentence to just after the bullet list (231). |
| style-4-4 | 157, 268 | "the effort `explore` listed" uses "listed" for the effort returned in `explore`. Everywhere else (21, 97, 232, 290), "listed" means "in `--available`", which is now the rule-1 scope term. | Write "the effort of the `explore` spec" in both places. |
| style-4-5 | 12-13 | The Overview says chanchi "only trusts a model after at least 3 audited sessions for the requested context". `recommend()` falls back to the `global` level (`scoring.py` 441-445), so 3 sessions of any task type make a spec eligible. Lines 57-60 and 296-300 say so, and the Overview contradicts them. | Write "It only trusts a spec `(agent, model, effort)` after at least 3 audited sessions, looked up from the requested task type and complexity down to all sessions." |

## Outside the review scope

`egm-structural` noted two lines in the Detailed Implementation Plan that contradict the round-3 decision that rule 1 counts only listed efforts (scoped lines 227 and 232-235). The plan was not reviewed; these are reported only so that the plan can be aligned:
* Line 924 computes the highest `n_task_type` "over every effort in the records (not only the available ones)". Use "over the efforts listed in `--available`".
* Line 970's test ("3 `bugfix` audits at `:high` make every effort of that model non-explorable") does not say that `:high` is listed. Write "with `:high` listed". As written, it also conflicts with the plan's own test at 965-966.
