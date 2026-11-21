# Round 1 consolidation — global items design (Revision 1)

Run by hand (the `chanchi audit` commands are phase 1 of this design; this round is backfilled when
they exist). Subject: `docs/designs/global-items.md` at `953ac5a`. Author: `claude:opus:high`.

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor |
|---|---|---|---|---|---|---|
| 1 | `claude:sonnet:medium` (as `agent-chanchi-researcher`) | anthropic | pass_with_fixes | 0 | 8 | 12 |
| 2 | `agy:gemini-4-neon-high:high` (as `agent-chanchi-researcher`) | google | pass_with_fixes | 3 | 5 | 4 |
| 3 | `opencode:opencode-go/minimax-m3` (as `agent-chanchi-researcher`) | minimax | pass_with_fixes | 2 | 6 | 10 |

Outcome: **fix** (three non-fail votes, fewer than two `pass`). Not degraded (three families).
Note: the three reports were written into this folder while the others ran; independence relied on
instruction only. Revision 2 adds private scratch paths for reports (seat 1, m8).

## Consolidated findings and how Revision 2 resolves them

| # | Finding | Raised by | Resolution in Revision 2 |
|---|---|---|---|
| 1 | Audits tied to a project change; subject text with commit restarts the round count | 3 (GI-01), 2 (F1), 1 (M3, m12) | `audits` table with subject kind and stable ref, optional change and project; rounds numbered per audit with `subject_at` |
| 2 | No tables for scans and adoption decisions | 3 (GI-02) — lone, **confirmed** | Migration 006 specified (`project_item_dirs`, `project_items`, `item_decisions`) |
| 3 | No seats: unavailable replacement and fewer-than-three cases undefined | 2 (F2) — lone, **confirmed** | `audit_seats`; refill in the same seat; fewer than two voters escalates |
| 4 | Outcome table contradicts confirmed lone findings; no dissent CLI | 2 (F3), 1 (M4) | Ordered outcome table with the lone-finding rule; `audit dissent` contract |
| 5 | Launch templates incomplete; no auditor agent | 2 (F4), 1 (M5), 3 (GI-17) | Templates with effort and stdin closed; `agent-chanchi-auditor` |
| 6 | Unknown family counts as distinct (fails open) | 1 (M6), 2 (F5) | Families seeded by name pattern; unknown fails closed and degrades the round |
| 7 | `SYNC` location in worktrees and consumers; roster before `SYNC` exists | 1 (M2), 2 (F7) | Resolution via `CHANCHI_SYNC` or the main checkout from git common dir; built-in roster fallback |
| 8 | Migration 005 collides with the lessons design | 1 (m1), 2 (F8) | This design takes 005; the lessons design notes the renumbering |
| 9 | Mirror makes global items load in every project, contradicting principle 2 | 1 (M1) — lone, **confirmed** | Principle 2 restated: available on the machine, never replacing a project item without its decision; inbox shows overlaps |
| 10 | Rule of three cannot count vendored copies; similarity not usable | 1 (M7, m11), 3 (GI-06) | Independent uses; vendored copies count once; similarity is not a criterion; herdr owner-promoted |
| 11 | Mirror duplicates `skills_link`; `agents_sync.render` returns repo paths | 1 (M8, m2), 2 (F6), 3 (GI-04, GI-11) | Generalized `skills_link`; render per harness kind with a target map and header parameter |
| 12 | Phantom "phase-2 plan" reference | 3 (GI-05) — lone, **confirmed** | Reworded as a live probe before phase 2 |
| 13 | New lesson `item` field duplicates `target_kind`/`target` | 3 (GI-07) — lone, **confirmed** | Field dropped; convention on `target` |
| 14 | `evals/` in `SYNC/ITEMS/` undefined | 3 (GI-08), 2 (F10a) | Evals out of scope for now (non-goal) |
| 15 | `retired.json` and `deprecate` have no consumers | 3 (GI-09, GI-14), 2 (F10) | Effects on mirror, inbox and check; `deprecate` follow-up and inbox behavior |
| 16 | Reserved slug guarded on one path only | 3 (GI-03, GI-15a), 2 (F9) | Guard on every slug creation and derivation |
| 17 | `AGENTS.md`: "agree" ambiguous; Items section lacks the global form | 1 (m6), 2 (F11) | Reworded; global form added |
| 18 | Hash framing and junk files | 1 (m5), 2 (F10) | Framing, exclusions and symlink rule specified |
| 19 | `metadata.version` placement | 3 (GI-13) — lone, **confirmed** (minor) | Stated as allowed by the free-form `metadata` map |
| 20 | Adding a harness overstated as "a row" | 1 (m4) — lone, **confirmed** | Full list of what a new harness needs |
| 21 | Source attributions (rule of three author; debate scope); agy reload overclaim | 1 (m7), 2 (F12) | Corrected in design and brief |
| 22 | Dangling mirror links after re-pointing or unmounting `SYNC` | 1 (m9) — lone, **confirmed** | Ownership by link text; `sync status` reports reachability |
| 23 | Adoption leaves dangling references in roles and rules | 1 (m10) — lone, **confirmed** | `adopt` and `wrap` update references |
| 24 | Rule in force before the commands exist | 3 (GI-10) — lone, **confirmed** (minor) | Manual procedure and backfill stated |
| 25 | Database path wording | 3 (GI-18) — lone, **confirmed** (minor) | `$XDG_DATA_HOME` default stated |
| 26 | Roster models vs catalog keys | 3 (GI-12) — lone, **confirmed** | Roster resolves to `harness:model` catalog rows |
| 27 | Verification plan gaps | 3 (GI-15), 1 (m12) | Plan extended (slug paths, worktree resolution, dangling links, backfill) |
| 28 | Independence of reports by instruction only | 1 (m8) — lone, **confirmed** | Private scratch paths until all seats voted |

No lone finding was rejected.
