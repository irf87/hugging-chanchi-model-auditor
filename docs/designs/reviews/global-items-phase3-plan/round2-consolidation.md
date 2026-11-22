# Phase 3 plan — audit round 2 consolidation

- **Subject:** `docs/superpowers/plans/2026-11-22-global-items-phase3.md` at `b9b93d5` (Revision 2)
- **chanchi audit:** 4, kind `other`, round 2, not degraded
- **Outcome:** `accepted` (three approvals, no blocking or major finding open). Minor fixes applied
  in Revision 3 without a new round.

## Seats and votes

| Seat | Auditor | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass | 0 | 0 | 2 | [round2-claude-sonnet.md](round2-claude-sonnet.md) |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 0 | 4 | [round2-agy-gemini-4-neon.md](round2-agy-gemini-4-neon.md) |
| 3 | opencode:opencode-go/minimax-m3 | pass_with_fixes | 0 | 0 | 3 | [round2-opencode-minimax-m3.md](round2-opencode-minimax-m3.md) |

Every round-1 finding of every seat was re-checked as `RESOLVED`; no rejected finding was re-raised.
Seat 1's harness again denied the write to its private path (headless claude has no edit
permission mode in the adapter's launch line); its report is its stdout, transcribed.

## Minor fixes applied (Revision 3)

| Finding | Seats | Fix |
|---|---|---|
| Builder launch line pointed at `audit open`; agy edit mode missing | S2-15b, S3-18 | Task 5 step 4 builds the line with `harnesses.launch` for the recommended spec |
| S1-11 project-scoped chanchi names | 1 (confirmed) | D8 sentence |
| S1-12 builder stop when `SYNC` unreachable | 1 (confirmed) | builder step 3 |
| S2-12 `AGENT_FILE_ROOTS` listed `.agents/agents` | 2 (confirmed) | Task 1 interface |
| S2-13 move reports before votes | 2 (confirmed) | Task 5 step 5 |
| S2-14 injectable promotion config for `proposals` | 2 (confirmed) | Task 3 interface |
| S2-15a `owner_promoted` is a bool | 2 (confirmed) | Task 5 step 3 |
| S3-19 baseline for the chanchi checkout | 3 (confirmed) | Task 5 step 4 |
| S3-20 frontmatter block and comment lines | 3 (confirmed) | D3, D4 |
