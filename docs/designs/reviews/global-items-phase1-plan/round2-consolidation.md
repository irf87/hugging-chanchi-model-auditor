# Round 2 consolidation — global items phase-1 plan (Revision 2)

Run by hand; backfilled by Task 8. Subject: `docs/superpowers/plans/2026-11-21-global-items-phase1.md`
at `13cfa9a`. Same three seats as round 1; reports private until all three voted.

| Seat | Auditor | Family | Verdict | Open blocking | Open major | Open minor | Approval |
|---|---|---|---|---|---|---|---|
| 1 | `claude:sonnet` | anthropic | pass | 0 | 0 | 5 | yes |
| 2 | `agy:gemini-4-neon-high:high` | google | pass_with_fixes | 0 | 0 | 2 | yes (no blocking, no major) |
| 3 | `opencode:opencode-go/minimax-m3` | minimax | pass_with_fixes | 0 | 1 | 1 | no |

Outcome: **accepted**. Two approvals, and no confirmed **lone** blocking or major finding: seat 3's
only major (R2-01, S6 cannot run `agents link --user --check` under a scratch `CHANCHI_DB`) was also
raised by seat 2 (N2, as minor), so it is not a lone finding. Every open finding is fixed in
Revision 3 without a new round (owner's rule, 2026-11-21). Not degraded.

| # | Finding | Raised by | Fix in Revision 3 |
|---|---|---|---|
| 1 | S6 constrained to a scratch DB but must check the real manifest | 3 (R2-01, major), 2 (N2) | Constraint covers S1-S5; S6 is read-only against the real home and `mirror.json` |
| 2 | Committed round-1 report trips `tests/test_privacy.py` (a quoted home-path grep pattern) | 2 (N1) — lone, **confirmed** | The pattern is redacted in `round1-agy-gemini-4-neon.md`, marked as an orchestrator redaction |
| 3 | D5 misdescribes `resolve_project` for an omitted `--project` | 3 (R2-02) — lone, **confirmed** | D5 names the `projects` row condition |
| 4 | Task 7 never proves the opencode auditor can write; no risk row | 1 (G4 partial) — lone, **confirmed** | Task 7 step 4 and a Risks row |
| 5 | Lessons wording: the owner said #1-#3 | 1 (G17 partial, N2) — lone, **confirmed** | #1-#3 by the owner's request; #4 kept with them |
| 6 | `change close` before S6 is recorded | 1 (N1) — lone, **confirmed** | Task 8 step 6 waits for S6's audit |
| 7 | `--check` must not create the manifest folder | 1 (N3) — lone, **confirmed** | Only a normal `link` creates it |
| 8 | Manifest `root` differs between a worktree and the editable install | 1 (N4) — lone, **confirmed** | `root` normalized with `projects.main_worktree`; another root's path is a conflict |

No lone finding was rejected.
