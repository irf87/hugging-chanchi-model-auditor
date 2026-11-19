# Goldfish Annotated Review Report (round 4)

**Target:** `docs/designs/explore-capabilities-hf.md` (FeatureRange, Stage 7 round 4)
**Source findings:** `critic_report_round4.md` (0 Blocker, 2 Major, 7 Nit)

## Prioritized Findings & AI Suggestions

### design-4-1 - Major (needs an author decision)
*   ***AI Suggestion:*** PROPOSE FIX, option (a) model-level mark
*   ***Justification:*** The intent is to penalise the model, not one effort; a per-spec mark lets `--available` order decide whether the penalty applies.
*   ***Proposed Edit:*** A model is marked `red_flag_low_data` when any of its listed specs is red-flagged on fewer than 3 sessions; the spec kept by rule 4 carries the mark. `weak_start` is computed on the kept spec after rule 4. Last group order: `weak_start` only, then `red_flag_low_data` (with or without `weak_start`). "Only when nothing else is left" becomes "only when fewer than 3 explorable specs rank ahead of it". Test with two efforts where only the dropped one is flagged.

### style-4-1 - Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Line 234 in future tense; the `SKILL.md` cross-cutting bullet becomes the full inventory of skill rules (list every effort the human made available, stay on the effort of the `explore` spec, high-complexity `level` rule, no explore in blocking sessions, budget and `--tags explore` on every attempt, protocol suffix, reading `weak_start` and `red_flag_low_data`, planners never run `models set`).

### Nits
All 7 PROPOSE FIX as written in `critic_report_round4.md` (style-4-2, design-4-2, design-4-3, design-4-4, style-4-3, style-4-4, style-4-5), plus the two out-of-scope plan lines (924, 970).
