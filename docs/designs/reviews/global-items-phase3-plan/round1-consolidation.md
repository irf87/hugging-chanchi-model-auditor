# Phase 3 plan — audit round 1 consolidation

- **Subject:** `docs/superpowers/plans/2026-11-22-global-items-phase3.md` at `0334f88` (Revision 1)
- **chanchi audit:** 4, kind `other`, round 1, not degraded
- **Outcome:** `fix` (no approval: every vote carries major findings)

## Seats and votes

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | anthropic | pass_with_fixes | 0 | 3 | 7 | [round1-claude-sonnet.md](round1-claude-sonnet.md) |
| 2 | agy:gemini-4-neon-high:high | google | pass_with_fixes | 0 | 6 | 5 | [round1-agy-gemini-4-neon.md](round1-agy-gemini-4-neon.md) |
| 3 | opencode:opencode-go/minimax-m3 | minimax | pass_with_fixes | 0 | 7 | 10 | [round1-opencode-minimax-m3.md](round1-opencode-minimax-m3.md) |

Notes: seat 1's harness denied the write to its private path; its report is the auditor's stdout,
transcribed by the orchestrator. Seat 3's vote used the counts of its summary (7 major, 10 minor);
its table holds 6 major and 11 minor. The outcome is the same either way.

## Consolidated findings (raised by two or more seats) — all applied in Revision 2

| Finding | Seats | Fix |
|---|---|---|
| `items publish` not covered by project item collisions; the CLI would create a database in read-only commands | S1-01, S2-01, S3-08a | D7 |
| Candidate names: slug collisions, empty slugs, exclusions for lesson targets | S2-03, S3-15 | D8, D11 |
| Builder launch: `--add-dir` makes consumer roots writable; no check after the build; launch line unspecified | S2-05, S3-11, S3-12a | Task 5 step 4 |
| agy `agent.md` layout and generated wrappers scanned as copies | S1-03, S2-06 | D3 |
| A linked ancestor folder lets the scan leave the project | S1-04, S2-11 | D3, D6 |
| Builder: revising a draft, `scope`/`profile` values, changelog order, alias paths | S1-05, S2-09 | Task 4 text, D13 |
| 209 vs 212 shared lines | S1-09, S3-10 | D9 |
| `tests/test_db.py`: four tests break on migration 006 | S2-10, S3-06 | Task 1 files |
| Lenient reader needed for `name` too; `lines` definition; `db` import | S2-11, S3-03 | D4, global constraints |
| `share` division by zero; booleans and bounds in `promotion.toml` | S2-07, S3-08b, S3-09 | D9, Task 3 tests |

## Lone findings — decisions (recorded with `chanchi audit dissent`)

| Finding | Severity | Decision | Evidence |
|---|---|---|---|
| S1-02 missing project root blocks every proposal | major | confirmed | D2 keeps rows, D10 fails on any missing copy → D10 now excludes missing roots |
| S1-06 unlabelled identical blocks would be copied | minor | rejected | identical unlabelled text is the shared core; only declared vendored text is excluded (design C) |
| S1-07 vote stores the scratch report path | minor | confirmed | D14: move first, then vote with the final path |
| S1-08 register and `agents link --user` need the owner | minor | rejected | local, reversible, inside the owner's request; a clarifying sentence was added to Task 5 |
| S1-10 `walk` must catch the symlink error | minor | rejected | D4 already makes such an item `skipped` |
| S2-02 D10 conflates directory hash and main-file hash | major | confirmed | D10 rewritten |
| S2-04 accepted minors would break `items publish` | major | confirmed | Task 5 step 5: hashed minors go to 0.1.1 |
| S2-08 `proposal-status` and `proposals` edge cases | minor | confirmed | D13 |
| S3-01 committed gate record would leak slugs and paths | major | confirmed | Task 5 step 7 redaction |
| S3-02 printed proposal shape | major | confirmed | D17 |
| S3-04 no project-root interface | major | confirmed | D2, `inventory.project_root` |
| S3-05 `items` leaves have no `--project` | major | confirmed | D18 |
| S3-07 both S1 and S3 edit `FEATURE_MAP.md` | minor | confirmed | S3 no longer edits it |
| S3-12b seats hard-coded | minor | confirmed | Task 5 step 5 asserts `degraded`/`skipped` |
| S3-13 lessons joining a candidate of another kind | minor | confirmed | D8 |
| S3-14 overlap threshold vs design 0.12-0.38 | minor | confirmed | D8 note |
| S3-16 S4 missing from sessions table | minor | confirmed | Sessions table |
| S3-17 `recommend` without `--available` | minor | confirmed | Task 5 step 4 |

## Next

Round 2 audits Revision 2 with the same seats; each seat re-checks its own round-1 findings first.
