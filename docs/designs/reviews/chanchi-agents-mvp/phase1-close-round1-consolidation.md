# Phase 1 close — audit round 1 consolidation

- Subject: the status line of `docs/designs/chanchi-agents-mvp.md` and `phase1-exit.md` at
  `c975e15`; chanchi audit 11, kind `design`, round 1, **degraded** (anthropic, google, google).
  Seat 3 was refilled from agy gpt-oss to agy gemini-4-hydrogen by the owner's instruction (gpt-oss
  is a fallback only), recorded with `chanchi audit unavailable`.
- Seat 1 first ran without shell permission (its launch line had no `--allowedTools`) and could not
  read the database; that report was set aside unvoted and the seat re-ran with Bash allowed (change
  `launch-permissions`). Only the re-run is voted.
- Outcome: `accepted`.

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass | 0 | 0 | 1 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 0 | 3 |
| 3 | agy:gemini-4-hydrogen-high:high | pass | 0 | 0 | 0 |

All three seats re-read `chanchi show` and the database and confirmed the sessions, the count
(11 executor sessions, 10 with `verify:feature-map`), the consecutive change ids 81-83, and the
soundness of not counting an attempt superseded by an `env` retry.

## Minor fixes applied

| Finding | Seats | Fix |
|---|---|---|
| The reading "last attempt counts" is broader than chanchi's own rule (would excuse `executor_failure`) and does not say the retry ran on another executor | S1-F1, S2-F1 | Reading narrowed to `NON_EXECUTOR_RETRY_REASONS`; the retry's executor named; status line says it |
| Notes column mixes session notes and an incident | S2-F2 (lone, confirmed) | Column renamed "Session notes"; cell reads "(none); incident ..." |
| Excluded sessions not named | S2-F3 (lone, confirmed) | Names `global-items-phase1` S6, `global-items-phase3` S4, and `chanchi-agents-phase1` S4 as its only tagged session |
| "Phase 2 in progress" is ambiguous | S1 summary | "MVP phase 2 (layer 2, skills tested by evals) in progress" |
