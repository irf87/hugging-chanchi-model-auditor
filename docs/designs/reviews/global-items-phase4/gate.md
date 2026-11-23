# Global items phase 4 — gate record (Task 3)

Date: 2026-11-22/23. Plan: `docs/superpowers/plans/2026-11-23-global-items-phase4.md` (Revision 3).
Consumer projects are "project A" and "project B"; roots appear as `<project root>`, the `SYNC`
target as `<SYNC>`.

**Phase signal: met.** Each consumer project recorded an audited decision for the herdr skill with
the owner's go-ahead: project A `wrap` (adoption audit 9, accepted), project B `wrap` (adoption audit
10, accepted). `chanchi items inbox --all` shows `up_to_date` for both.

## Steps

0. **Links.** `chanchi skills link --global` (adds `skill-chanchi-item-adoption`);
   `chanchi agents link --user --check` → ok. Baselines saved: chanchi checkout and both projects'
   `git status --porcelain` (all empty) and `HEAD`.
1. **herdr 0.1.1 (S3).** Built by `agent-chanchi-item-builder` (agy gemini-4-hydrogen-high, headless,
   auto-approval flag) with the four deferred changes. Item audit 8: round 1 `fix` (degraded: agy
   gpt-oss 503, refilled by agy hydrogen; the permissions text omitted the flag names and the
   "only in another pane, never in-process" boundary, and the launch shapes bracketed the flags);
   S3 attempt 2 (`plan_fix`) applied the three fixes; round 2 `accepted` (three `pass`, degraded).
   Projects and checkout unchanged; no project name or home path; at most 2 lines shared with the
   vendored block.
2. **Publish and mirror.** `chanchi items publish skill-chanchi-global-herdr --audit 8` → published
   0.1.1; `chanchi items mirror` → 3 entries, no conflicts, no skipped harness;
   `chanchi items mirror --check` → ok.
3. **Project A (S4).** Inbox: `new`, `similar` = the four herdr copies. Proposal (read-only, agy
   hydrogen-high): `wrap` as `skill-chanchi-<a>-herdr`; owner go-ahead. Applied in a worktree of the
   project outside its folder, branch `chanchi/adopt-skill-chanchi-global-herdr`: 16 files (4 created,
   5 deleted incl. the vendored copy and its sync script, 7 edited), exactly the proposal's list;
   worktree clean; main checkout unchanged. Adoption audit 9 accepted; three minor fixes committed
   on the branch. `chanchi items decide ... --decision wrap --audit 9` → `up_to_date`.
4. **Project B (S5).** Same flow. The proposal flagged a conflict: the project limits auto-approval
   by role. Owner decisions: apply `wrap`, and keep the project's exception (two roles launch without
   the flag because one can spend paid credits). 13 files (2 created, 3 deleted, 8 edited). Adoption
   audit 10 accepted (see the process note in its consolidation: opened after the reports because of
   a shell error, same seats); two minor fixes committed. `chanchi items decide ... --audit 10` →
   `up_to_date`.
5. **Pending for the owner.** Merging each project's branch `chanchi/adopt-skill-chanchi-global-herdr`
   (worktrees kept until then); after a merge, `chanchi items scan --project <slug>`.

## Deviations and notes

- Roster: opencode left out (no credits); agy gpt-oss-120b was unavailable once (503) and gave thin
  reviews (empty or 4-line reports, one audit of the wrong subject).
- Adoption consolidations and every report: `<SYNC>/reviews/skill-chanchi-global-herdr/0.1.1/`.
