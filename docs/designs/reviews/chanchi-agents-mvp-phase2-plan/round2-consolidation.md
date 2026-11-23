# MVP phase 2 plan — audit round 2 consolidation

- Subject: the plan at `127581b` (Revision 2); chanchi audit 12, round 2, **degraded** (anthropic,
  google, google). All three seats re-checked their round-1 findings: every round-1 blocking finding
  is `RESOLVED`; seat 2's F7 is `PARTIAL` (condition 4 scope).
- Outcome: `fix` (one approval: seat 3; seats 1 and 2 carry open major findings). Fixed in Revision 3.

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass_with_fixes | 0 | 1 | 5 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 3 | 2 |
| 3 | agy:gemini-4-hydrogen-high:high | pass_with_fixes | 0 | 0 | 2 |

## Consolidated findings (two or more seats) — fixed in Revision 3

| Finding | Seats | Fix |
|---|---|---|
| Runner files inside `W` dirty `git status` and the injected `agent-chanchi-*` wrapper is an orphan for `chanchi agents sync` | S1-N1, S2-N1 | D3 neutral wrapper name `worker`; D22 runner paths in `.git/info/exclude`, graders use tracked paths; S5 `new-agent` checks a copy |
| `--rejudge` signature differs between D14 and S3; flow after it incomplete | S2-N2, S3-F9 | `--rejudge` takes no argument, prints the count, honors `--yes`/`--dry-run`, then `--calibrate` again |
| D17 changes the design's keep rule but is not in the amendment list | S1-N3, S2-N4 | D17 added to the list |
| D4 cites `harnesses.launch` flags not on the subject commit; `--` before the prompt | S2-N4, S3-F10 | `launch-permissions` merged into `main` and into this branch; D4 names `--` and covers trigger runs |

## Lone findings — decisions

| Finding | Sev. | Decision | Evidence / fix |
|---|---|---|---|
| S2-F7 condition 4 without `--all` and with `--limit 20` | major | confirmed | `src/chanchi/cli.py` defaults; D15 uses `--all --status pending --limit 1000`, S3 tests a registered project |
| S1-N2 S2 does not write the D22 contract | minor | confirmed | S2 README section and test |
| S1-N4 current `with` row undefined | minor | confirmed | D9 current-row rule, used by D15 |
| S1-N5 judge sees skill-load events | minor | confirmed | D14 strips them from the judge's transcript copy |
| S1-N6 fallback model "in chanchi's catalog" unverified | minor | rejected | `chanchi models list` shows agy `claude-sonnet-5-5-low/medium/high` |
| S2-N3 `plan_gap` is a change-level incident | minor | confirmed | S4 `stop-plan-gap` grader wording |
| S3-F10 trigger runs need the permission flags | minor | confirmed | D4 covers every claude run of the runner |
| S2-N4 S4 file list, `--force-new` in the bullet, triggers only with `--arm both` | minor | confirmed | S4 files and bullet; S3 triggers |
