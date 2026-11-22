# Round 2 consolidation — global items phase 2 plan

- **Subject:** `docs/superpowers/plans/2026-11-22-global-items-phase2.md` at `f5b21f0` (Revision 2)
- **chanchi audit:** id 3, round 2, not degraded
- **Outcome:** `fix` — two approvals (seats 1 and 2), but seat 3's lone major S3-16 was confirmed

## Seats and votes

| Seat | Auditor | Family | Verdict | Blocking / major / minor | Report |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | anthropic | pass | 0 / 0 / 2 | [round2-claude-sonnet.md](round2-claude-sonnet.md) |
| 2 | agy:gemini-4-neon-high:high | google | pass | 0 / 0 / 2 | [round2-agy-gemini-4-neon.md](round2-agy-gemini-4-neon.md) |
| 3 | opencode:opencode-go/minimax-m3 | minimax | pass_with_fixes | 0 / 1 / 6 | [round2-opencode-minimax-m3.md](round2-opencode-minimax-m3.md) |

Every round-1 finding was re-checked as RESOLVED by its author; seat 3 retracted S3-02 after
reproducing the orchestrator's evidence, and seat 2 accepted the rejection of S2-03.

## Findings raised by more than one auditor (applied)

| Topic | Findings | Fix in Revision 3 |
|---|---|---|
| D13 narrows the design's conflict sentence without saying so | S1-R2-01, S3-18 | D13 states the reading, like D1 |

## Lone findings: decisions

| Finding | Severity | Decision | Evidence and fix |
|---|---|---|---|
| S3-16 Gate's second launch set uses the auditor agent outside its role | major | confirmed | The auditor has `skills: []` and audits a brief; the prompt gives none. The probe agent preloads the mirrored skill, which meets item 9 and phase row 2. Second set dropped |
| S3-17 Missing `status` line undefined | minor | confirmed | D3: a missing line is `bad_status`; gate drafts carry `status: draft` |
| S3-19 Gate hardcodes the opencode folder | minor | confirmed | Task 5 uses the adapter's resolution (`$OC`) |
| S3-20 Source of `own_names` | minor | confirmed | `items.own_names()`, empty outside a checkout |
| S3-21 D10 vs D5 on which hash | minor | confirmed | D10: the hash before the status flip |
| S3-22 Separation test ignores compat links | minor | confirmed | Task 4 asserts `chanchi-<n>` links too |
| S2-12 Verification `find` searches the real HOME | minor | confirmed | `find "$SCRATCH_HOME"` |
| S2-13 `_parse` errors mask specific codes | minor | confirmed | D3: specific codes first, `bad_frontmatter` for the rest |
| S1-R2-02 Gate failure from skill discovery | minor | confirmed | New risk row |

## Next

Revision 3 is committed and re-checked in round 3 (the last) by the same seats.
