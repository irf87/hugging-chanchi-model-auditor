VERDICT: PASS

Audit 11, round 1, commit c975e15 (status line of the MVP design and `phase1-exit.md`).

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 | minor | `phase1-exit.md`, "Reading taken" | The retried session S3 of `global-items-phase3` ran on a different executor (claude sonnet medium, not agy). That is not stated. The status line also doesn't say that the claim rests on a reading of the signal, not on its literal wording. | `chanchi show global-items-phase3`: S3 attempt 1 is agy, `rejected`, `retry_reason` null. Attempt 2 is claude:sonnet:medium, `retry_reason` env, `accepted`, notes `gate:first-green`. | Optional: add "retried on a different executor" to the evidence file and "(last-attempt reading)" to the status line. |

**Check 1: citations match `chanchi show`.** All rows match.
- `global-items-phase1` has executor sessions S1–S5, all attempt 1, `accepted`, `gate:first-green verify:feature-map`. S6 is a researcher session, correctly excluded.
- `global-items-phase2` has S1–S3, all `accepted`, `gate:first-green verify:feature-map`.
- `global-items-phase3` has S1 and S2, `accepted` with both notes. S3 attempt 1 (tags `agent-chanchi-executor` and `explore`) is `rejected` with an `env_issue` incident: headless agy auto-denied the command permission. S3 attempt 2 (`retry_reason` env) is `accepted` with `gate:first-green` only. S4 is an item-builder session, correctly excluded.
- The count is 5 + 3 + 3 = 11 executor sessions on last attempt, and 10 carry `verify:feature-map`. The status line says this accurately.
- No qualifying or disqualifying session is missing. Phase 4 S4 and S5 are `accepted_with_fixes` with no notes, as the file says. `chanchi-agents-phase1` and `user-ownership-guard` are `accepted_with_fixes`; I only spot-checked these two against `chanchi show`.

**Check 2: the last-attempt reading is sound.**
- The signal says each change's executor sessions are audited `accepted`. A session is the unit, and the retry is the attempt that delivered the work.
- The first rejection was an environment limit. It carries an `env_issue` incident and `retry_reason: env`, so it is not an executor defect.
- The evidence file discloses the rejected attempt openly. It does not hide it.
- A stricter reading counting attempt 1 would disqualify `global-items-phase3`. No other run of three qualifies under that reading: phase 4 fails, and phase 1 or 2 alone are fewer than three. Under the stricter reading phase 1 would stay open.
- The owner asked for the pragmatic reading to be audited, and I find it defensible.

**Check 3: the changes are consecutive.**
- The changes table shows ids 81, 82 and 83 in project 3, with no other change between them.
- Ids 79 and 80 come before. Id 84 (`global-items-phase4`) comes after, then 85 and 86.
- Ids 81–83 were opened over 2026-11-21 to 22. The evidence file states the same.

**Check 4: the status line is accurate and short enough.**
- It is consistent with the evidence file.
- I found no home path or reference-project name in the diff. A grep for `/Users/` and `/home/` found nothing.
- The evidence file uses `~/.local/share/...`, which is not a user-specific home path.
