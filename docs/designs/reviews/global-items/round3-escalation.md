# Round 3 — escalation report (global items design, Revision 3)

Run by hand; backfilled when `chanchi audit` exists. Subject: `docs/designs/global-items.md` at
`e40d275`. Same three seats; reports private until all voted.

| Seat | Auditor | Family | Verdict | Open blocking | Open major | Open minor |
|---|---|---|---|---|---|---|
| 1 | `claude:sonnet:medium` | anthropic | pass_with_fixes | 0 | 0 | 6 |
| 2 | `agy:gemini-4-neon-high:high` | google | **pass** | 0 | 0 | 2 |
| 3 | `opencode:opencode-go/minimax-m3` | minimax | pass_with_fixes | 0 | 2 | 2+ |

Outcome by the rule: one `pass`, fewer than two → **fix**; round 3 → **escalated (`round_cap`)**.
The human decides.

## Where the auditors disagree, and why

- **Seats 1 and 2 agree that no blocking or major problem remains**; seat 1 withholds `pass` for
  six minors. Seat 2 sees two of the same kind of minors and passes.
- **Seat 3 raises two majors no other seat raised (lone findings).** The orchestrator checked both
  against the code; both are **confirmed**, and both are wording, not design:
  1. R3-01: the design's `chanchi lesson apply ... --where "SYNC item <name>@<version>"` would be
     rejected: `--where` must contain `[lesson #<id>]` (`src/chanchi/lessons.py`), and only an
     approved, agnostic lesson can be applied at the global site. Fix: write the value as
     `SYNC/ITEMS/skills/<name>/SKILL.md [lesson #<id>] @ <version>` and state the precondition.
  2. R3-02: Principle 4 says `tests/test_items.py` already refuses own items named
     `*-chanchi-global-*`; it does not yet (it is a phase-2 deliverable). Fix: say so.
- Why seats 1 and 2 missed them: neither ran the `lesson apply` command against the code, and both
  read Principle 4 together with verification item 7, which states the check as a deliverable.
- **Remaining minors** (all three seats): the audit binds to a version and not to content (an edit
  at the same version could publish); the collision check against scanned project items needs
  phase-3 tables; the mirror manifest should follow the `CHANCHI_DB` scratch override; the
  `skills unlink` separation sentence must match `_is_own`'s current behavior; agy-only machines and
  the second agy skills folder; family inference for models added after migration 005; vote
  validation in `audit close`; vendored-text guidance and `promotion.toml` keys.

## Observation on the rule

The rule counts only `pass` toward acceptance. A `pass_with_fixes` with no blocking and no major
finding (seat 1 here) carries the same risk as a `pass` whose minor findings are fixed without a
new round, which the rule already allows for confirmed lone minors. Treating such a vote as an
approval would have accepted this round (seats 1 and 2), with the two confirmed lone majors fixed
before merge only if the rule also requires confirmed lone majors to be fixed — which it does
(they force `fix`). The owner decides whether to change the rule.
