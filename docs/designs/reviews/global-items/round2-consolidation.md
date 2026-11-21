# Round 2 consolidation — global items design (Revision 2)

Run by hand; backfilled when `chanchi audit` exists. Subject: `docs/designs/global-items.md` at
`a7a1a20`. Same three seats as round 1; reports kept in private scratch paths until all three voted.

| Seat | Auditor | Family | Verdict | Open after re-check |
|---|---|---|---|---|
| 1 | `claude:sonnet:medium` | anthropic | pass_with_fixes | 2 major, 8 minor |
| 2 | `agy:gemini-4-neon-high:high` | google | pass_with_fixes | 4 new major, 1 minor; 2 partial |
| 3 | `opencode:opencode-go/minimax-m3` | minimax | pass_with_fixes | 3 new major, 3 minor; 4 partial |

Outcome: **fix**. Not degraded. Round 3 is the last one.

| # | Finding | Raised by | Resolution in Revision 3 |
|---|---|---|---|
| 1 | Mirror ownership contradicts relative links and re-pointed `SYNC` | 1 (N1), 2 (R2-1, F6) | Ownership by a manifest in the chanchi data dir, independent of link targets |
| 2 | No draft state: unaudited items mirrored | 1 (M1) — lone, **confirmed** | `status: draft|published|retired`; `items publish` requires an accepted `item` audit at that version |
| 3 | Retired directory contradiction | 2 (R2-3), 2 (F10) | `items retire` sets status; `items check` fails when a retired name has another status |
| 4 | Family patterns miss provider-prefixed ids; built-in roster degraded | 2 (R2-2), 3 (N-05), 1 (N3b) | Match on the last `/` segment, `#variant` removed |
| 5 | Fresh catalog: built-in roster entries missing | 1 (N3a) — lone, **confirmed** | Missing entries are unavailable with a hint; quorum escalation |
| 6 | agy template contradictory (suffix vs `--effort`) | 3 (N-02) — lone, **confirmed** (re-verified: `agy --model gemini-4-neon --effort high` answers) | Adapter splits `<base>-<effort>`; mismatched roster effort is an error |
| 7 | Proposals have no table | 3 (N-01, GI-02) — lone, **confirmed** | `item_proposals` in migration 006 |
| 8 | One-name rule not enforced; precedence not cited | 3 (N-03, GI-16), 1 (m12) | Collision checks in mirror and `items check`; own items may not use `-chanchi-global-`; precedence cited |
| 9 | `skills unlink` vs mirror separation untested | 3 (N-04) — lone, **confirmed** | Separation rule and tests both ways |
| 10 | Harness detection folders unnamed; skills_link creates dirs unconditionally | 2 (R2-4a) — lone, **confirmed** | Detection folder per harness; existence check as a parameter for the mirror |
| 11 | Auditor agent needed in projects before phase 5; `audience: global` overloaded | 2 (R2-4b), 1 (m3, N2) | `install: repo|user` and `agents link --user` ship in phase 1 |
| 12 | Author must be in catalog | 3 (N-06) — lone, **confirmed** | `author_raw` plus nullable model id |
| 13 | Hash framing ambiguous with NUL in contents | 1 (N4) — lone, **confirmed** | Length framing |
| 14 | `audit round` unguarded; escalation reasons; `close` with assigned seats; `--version` | 1 (N5), 2 (R2-5) | Guards, `escalation` column, `--version` on `audit round` |
| 15 | `audit_seats.harness` duplicates `models.agent` | 2 (R2-5c) — lone, **confirmed** (minor) | Column dropped |
| 16 | Lessons not closed when an item is built from them | 1 (m1) — lone, **confirmed** | `lesson apply --site global` on publish |
| 17 | Nested `metadata.version` with a flat parser | 1 (m5) — lone, **confirmed** | Reader shape specified |
| 18 | Per-phase housekeeping (feature map, layers, README, verify) | 1 (m12) — lone, **confirmed** | "Fitting the existing code" section |
| 19 | Lessons design summary table still shows `005_runs` | 2 (R2-5d) — lone, **confirmed** | Table row updated |
| 20 | Headless load should gate phase 2 | 3 (GI-15) — lone, **confirmed** | Verification item 9 is the phase-2 gate |

No lone finding was rejected.
