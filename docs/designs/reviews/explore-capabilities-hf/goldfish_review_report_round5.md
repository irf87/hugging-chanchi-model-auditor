# Goldfish Annotated Review Report (round 5, loop cap)

**Target:** `docs/designs/explore-capabilities-hf.md` (FeatureRange, Stage 7 round 5)
**Source findings:** `critic_report_round5.md` (0 Blocker, 1 Major, 3 Nit)

| Id | Severity | AI Suggestion | Applied edit |
| --- | --- | --- | --- |
| design-5-1 | Major | PROPOSE FIX | The rule is narrowed to "planners never pass `--capability` to `models set` or `models add`"; existing `--cost` / `--active` maintenance on the human's request stays; future tense at 371 and 397; Risks row names both commands |
| structural-5-1 | Nit | PROPOSE FIX | Points to "Before you start", item 2 |
| style-5-1 | Nit | PROPOSE FIX | Cross-cutting changes state which items belong to Phase 3 |
| style-5-2 | Nit | PROPOSE FIX | Risks row says "resolves to the real database" |
| (out of scope) | - | PROPOSE FIX | Plan: owner step defined; the map file is written by S3, not by the owner |

Stage 7 ends at the five-round cap. Trend: round 1 had 1 Blocker and 11 Majors; round 5 had 0 Blockers and 1 Major, all applied.
