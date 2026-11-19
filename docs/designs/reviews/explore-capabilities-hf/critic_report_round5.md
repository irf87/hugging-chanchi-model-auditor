# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-883, top of file up to but not including "## Detailed Implementation Plan" at line 884)
**Stage:** 7 (Critic Review), round 5 (final round of the loop). Mode: REVIEW.
**Standard:** `resources/document_standards/feature-spec-standard.md` (egm-design, egm-structural). egm-style used its persona's audit vectors.
**Settled items not re-raised:** Phases 1-2 merge on their own branch before Phase 3; a red flag excludes a model only when it rests on 3 or more sessions, otherwise the model-level `red_flag_low_data` mark carried by the spec rule 4 keeps; rule 1 counts only efforts listed in `--available`; Phase 3 drop criterion; no `source` column on `model_capabilities`; the owner's budget override for the Hydrogen sessions; the known leak into `recommendation` (G2); line wrapping beyond 100 columns.

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `egm-design` | completed | 0 Blocker, 1 Major, 1 Nit |
| `egm-structural` | completed | 0 Blocker, 0 Major, 1 Nit |
| `egm-style` | completed | 0 Blocker, 0 Major, 3 Nit |

After deduplication: **0 Blocker, 1 Major, 3 Nit.** When two or more reviewers raised the same point, the finding keeps one id and lists the others under "Also raised by".

**Round-4 fixes.** All three reviewers checked every round-4 fix (design-4-1 to 4-4, style-4-1 to 4-5) and found each one applied, correct and consistent:
* design-4-1: step order at 218-221. The model-level mark is carried by the kept spec at 238-245, with the wording "fewer than 3 explorable specs rank ahead of it". `weak_start` is computed on the kept spec and the last group is ordered at 259-261. Risks row 832 matches. egm-design also checked that the reserved slot (278-283) cannot move a spec ahead of a `red_flag_low_data` spec, so the "fewer than 3 ahead" wording holds.
* style-4-1: future tense at 236, and a full skill inventory at 638-653. A step-number slip is covered by structural-5-1.
* style-4-2: 420-422, 470-472 and 669-671.
* design-4-2: 47 and 510-513. Risks row 831 still has older wording, see style-5-2.
* design-4-3: 462-466, consistent with 456-460.
* design-4-4: 320-321 and 645.
* style-4-3: 247.
* style-4-4: 158, 277 and 646.
* style-4-5: 12-13.

All internal cross-references and the brief anchor resolve. Code claims rechecked: `scoring.py` 470 and 476, `db.py` backups and `schema_too_new`, `db.status()`, `tests/test_db.py:240` and `catalog.py` 105-107.

**Verified by the synthesizer against source:**
* `skills/chanchi-model-selection/SKILL.md` "Catalog maintenance (when the human asks)" (lines 56-59) tells planners to run `models set ... --cost` and `--active`. "Before you start" item 3 (lines 21-24) tells them to run `models add`. These underlie design-5-1.
* In `SKILL.md`, "Steps" item 2 is "Classify every planned session" (line 32). The available list comes from "Before you start" item 2 (line 18). This underlies structural-5-1.

## Prioritized Findings (Blockers -> Major -> Nits)

### design-5-1: The planner ban on `models set` conflicts with the current skill, and capability writes through `models add` are not covered. Severity: Major
* **Reviewer Lens:** `egm-design` (Major 5-1).
* **Affected Scope:** Lines 370-371, 396-398, 650-651, Risks row 834.
* **Discrepancy Description:**
  * Lines 370-371 and 397 say, in the present tense, that "the selection skill forbids planners from running `models set`". The skill change list (650) adds the unscoped rule "planners never run `models set`".
  * The current `SKILL.md` "Catalog maintenance (when the human asks)" (56-59) tells planners to run `models set ... --cost 2` and `--active 0` when the human asks. A builder following 650 must either delete those instructions or leave a contradiction in the skill. The design does not say which.
  * "Before you start" item 3 (`SKILL.md` 21-24) tells planners to run `models add` for missing models. Phase 2 adds `--capability` to `models add` (378). A planner can therefore still write `vision=yes` while registering a model.
  * Two statements then stop holding:
    * the Risks row 834 mitigation against planners classifying capabilities;
    * the premise at 370 that "every write is the owner running `models set`".

  The no-`source`-column decision itself stays settled; only the premise stated in its support is affected.
* **Rationale & Recommendation:**
  * Scope the rule at 650 to capabilities. Write: "planners never pass `--capability` to `models set` or `models add`; they report excluded `unknown` models to the owner. The existing human-requested `--cost` and `--active` maintenance is unchanged."
  * At 370-371 and 397, write "the selection skill will forbid planners from setting capabilities".
  * In Risks row 834, name both commands.

### Nits

| Id | Lines | Problem | Fix |
| --- | --- | --- | --- |
| structural-5-1 (also design 5-2, style N1) | 639 | "step 2: list in `--available` every effort..." points at `SKILL.md` "Steps" item 2, which is "Classify every planned session" (`SKILL.md`:32). The available list is built in "Before you start" item 2 (`SKILL.md`:18). The other step numbers (3, 4, 5) at 640-649 and the reference at 329 match "Steps". | Write "'Before you start', item 2: list in `--available` every effort of a model that the human made available". |
| style-5-1 | 627-653, 669-671 | Line 669 says Phase 3 "adds files and edits `scoring.py` and `cli.py`". The cross-cutting list also gives Phase 3 content to other existing files: the README "Local only" bullet and the snapshot-refresh section (633-635), design spec section 1.3 (636-637), and the `external_signals` skill rule (643). The list does not tag items by phase. If that wording merges with Phases 1-2 and Phase 3 is then dropped (470-472), main describes a maintainer script that does not exist. | At 669, write "Phase 3 adds files and edits `scoring.py`, `cli.py`, `SKILL.md`, `README.md` and the design spec, on its own branch." Tag each cross-cutting bullet with its phase. At minimum, mark the "Local only" and section 1.3 wording and the `external_signals` skill rule as Phase 3. |
| style-5-2 | 831 | The Risks mitigation says the script stops when `CHANCHI_DB` is "unset or the default path". After design-4-2, the guard compares resolved paths against the real database path, which honours `XDG_DATA_HOME` (510-513). "The default path" reads as the `~/.local/share` literal. | Write "when `CHANCHI_DB` is unset or resolves to the real database". |

## Outside the review scope

`egm-design` and `egm-structural` both noted that the Detailed Implementation Plan still uses the "owner step" phrase that design-4-3 replaced in the spec. The plan was not reviewed. These notes are only for aligning it:
* Line 888 creates the Phase 3 branch "from main after the owner step". Align it with 464-466: "after the merge of Phases 1-2 has migrated the real database".
* The table row at 912 has the owner registering models and filling `scripts/hf_model_map.json` before the Phase 3 branch exists, although the map is a Phase 3 file. Move that work into Phase 3, before its first fetch.
* Line 1184 refers to the same step.

`egm-structural` confirmed that the round-4 plan notes (former lines 924 and 970) are fixed.
