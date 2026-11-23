# Phase 4 plan — audit round 1 consolidation

- Subject: `docs/superpowers/plans/2026-11-23-global-items-phase4.md` at `d6f951c` (Revision 1);
  chanchi audit 7, kind `other`, round 1, not degraded (anthropic, google, openai).
- Outcome: `fix` (one approval; two votes carry major findings).

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass_with_fixes | 0 | 3 | 7 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 6 | 2 |
| 3 | agy:gpt-oss-120b-medium:medium | pass | 0 | 0 | 0 |

Seat 3's report has an empty findings table and no evidence; it counts as a vote.

## Consolidated findings (two seats) — applied in Revision 2

| Finding | Seats | Fix |
|---|---|---|
| Retirement cannot be acknowledged without inventing `--local`; state precedence undefined | S1-01, S2-02 | D3 precedence, D6 optional `--local` on retired items |
| One accepted audit can back several decisions | S1-02, S2-03 | D7: an audit id is used once |
| Skill mixes the delegated agent's and the orchestrating role's steps; gate order contradictory | S1-03, S2-04, S2-05 | D11, skill *Roles* and steps, Task 3 step 3 a-d |
| Agent edits the project's main checkout | S1-04, S2-05 | worktree outside the project (D11, step 3c) |
| keep/deprecate have no commit to audit | S1-06, S2-04 | `HEAD` plus proposal file (D11, skill 5b) |
| Unreadable items and malformed `retired.json` | S1-07, S2-07 | D3, D5 |

## Lone findings — decisions

| Finding | Sev. | Decision | Evidence / fix |
|---|---|---|---|
| S2-01 refusal order | major | confirmed | D5 reordered |
| S2-06 `similar` kind filter, aliases, stale evidence | major | confirmed | D4 joins live rows of the same kind |
| S1-05 `items list` has no path | minor | confirmed | entry `path` (D4) |
| S1-08 design command differs | minor | confirmed | design section D amended in this commit |
| S1-09 no fallback for agy headless | minor | rejected | owner-authorized flag (AGENTS.md, audit 6); probe passed |
| S1-10 missing test cases | minor | confirmed | Task 1 step 1 |
| S2-08 describe keys, refs, cases, agy folder, `--author`, post-decision state | minor | confirmed | D1, Task 1-3 |
