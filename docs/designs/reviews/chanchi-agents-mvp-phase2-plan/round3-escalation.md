# MVP phase 2 plan — audit round 3 escalation

- Subject: the plan at `f0004ae` (Revision 3); chanchi audit 12, round 3, **degraded** (anthropic,
  google, google). Outcome `escalated` (`round_cap`): one approval, two `pass_with_fixes` votes
  each carrying the same single major finding.

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass | 0 | 0 | 0 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 1 | 0 |
| 3 | agy:gemini-4-hydrogen-high:high | pass_with_fixes | 0 | 1 | 0 |

Every round-2 finding of every seat is `RESOLVED`. No blocking finding is open.

## The open finding (S2-R3-1 = S3-F11)

S5 `new-agent` ran `chanchi agents sync --check` on a copy of `W`'s **tracked** files. The
candidate (an executor) never commits, so its new agent and wrappers are untracked and the copy
would omit them: the regression case would pass without testing anything.

**Fix applied in Revision 4** (the one both seats proposed): the check runs in `W` itself, which is
safe because the runner's wrapper is named `worker` and does not match `agent-chanchi-*` (D3); D22
now tells graders to read changes with `git status --porcelain` and `git ls-files --cached --others
--exclude-standard`, so new untracked files count.

## Decision for the owner

Accept Revision 4 with this fix, or open a new audit for it. Orchestrator's recommendation: accept;
the fix is the text both seats proposed, it touches two sentences, and seat 1 passed everything else.

**Owner decision (2026-11-23):** accept Revision 4 (`73be6bd`) with the fix; merge the plan.
