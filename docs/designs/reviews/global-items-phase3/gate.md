# Global items phase 3 — gate record (Task 5)

Date: 2026-11-22. Plan: `docs/superpowers/plans/2026-11-22-global-items-phase3.md` (Revision 3).
Consumer projects are named "project A" and "project B"; roots appear as `<project root>`, the
`SYNC` target as `<SYNC>`.

**Phase signal: met.** `skill-chanchi-global-herdr` 0.1.0 was built from the two consumer
projects' copies and accepted by a redundant item audit (chanchi audit 5, round 2 `accepted`).

## Steps

0. **Backup and migrate.** Operational database copied to a private scratch folder; `chanchi db
   status` → operational version 6, pending 0. `chanchi agents link --user` installed
   `agent-chanchi-item-builder` for claude, opencode and agy (`conflicts: []`);
   `chanchi agents link --user --check` → ok. `chanchi sync status` → link, reachable.
1. **Register.** `git status --porcelain` of both projects saved (both empty); `chanchi project
   register` in each project's main checkout → ok (database only).
2. **Scan.** `chanchi items scan` → project A: 165 items, project B: 83 items, nothing skipped,
   `missing: []`. Both projects' `git status --porcelain` unchanged.
3. **Propose.** `chanchi items propose --owner-promote skill-chanchi-global-herdr` → 16 proposals,
   `min_uses: 3`, `vendored_share: 0.5`. Proposal 7, `skill-chanchi-global-herdr`: `rules:
   ["same_name"]`, one cluster (`<A>:agents/skills/herdr`, `<B>:.agents/skills/workflow/herdr`),
   shared block 212 lines (A from line 112, B from line 237), share 0.656, `uses: 1`,
   `owner_promoted: true`, `eligible: true`. The other 15 candidates (same-name copies of
   workflow skills and agents in both projects) have `uses` 1-2 and are not eligible: evidence
   only, nothing built.
4. **Build (session S4).** `chanchi recommend --task-type docs --complexity medium` recommended
   `agy:gemini-4-hydrogen-high:high`; chosen `claude:sonnet:high` because headless agy cannot run
   in this orchestrator's environment (see *Deviations*). The builder ran as the
   `agent-chanchi-item-builder` subagent from the main checkout. Audit of attempt 1: both
   projects' `git status --porcelain` and the chanchi checkout's status equal the baselines;
   `chanchi items check` → `problems: []`; no project name, root or home path in the item; longest
   run shared with either copy's vendored block: 2 lines; the item names `herdr --skill` as the
   authority. Verdict accepted.
5. **Item audit.** `chanchi audit open --kind item --ref skill-chanchi-global-herdr --version 0.1.0
   --author claude:sonnet:high --change global-items-phase3` → audit 5, seats claude
   sonnet-medium, agy gemini-4-neon-high, opencode minimax-m3, `degraded: false`, `skipped: []`.
   - Round 1 (`0.1.0@73c1318a…`): three `pass_with_fixes`; seat 2's three lone major findings
     (paraphrased vendored mechanics, unscoped report-file rule, single-copy rules) confirmed →
     `fix`. Incident `rule_violation` recorded on S4.
   - S4 attempt 2 (`--retry-reason executor_failure`) applied the ten fixes at the same version;
     same checks as step 4 passed (projects and checkout unchanged, `items check` clean, 2-line
     maximum shared with the vendored block).
   - Round 2 (`0.1.0@c251cb0d…`): seat 3 unavailable (opencode monthly usage limit), refilled by
     chanchi with agy gemini-4-hydrogen-high → **degraded** (two google seats). Votes: pass,
     pass_with_fixes, pass_with_fixes, all with 0 blocking and 0 major → **accepted**. Three minor
     fixes touch hashed files, so they are deferred to 0.1.1 and 0.1.0 stays byte-identical to the
     audited subject.
   Reports and consolidations: `<SYNC>/reviews/skill-chanchi-global-herdr/0.1.0/` (private).
6. **Close the proposal.** `chanchi items proposal-status 7 --status built --global-item
   skill-chanchi-global-herdr` → `built`. Publishing and mirroring wait for the owner (D16).

## Deviations

- **agy executors.** Headless agy auto-denies shell commands unless started with
  `--dangerously-skip-permissions`, which this orchestrator's environment refuses. S3's agy
  attempt was recorded `BLOCKED` (`env_issue`) and retried with `claude:sonnet:medium`; S2 and S4
  ran on `claude:sonnet:high` instead of the recommended agy spec. agy auditors (read-only, report
  only) ran headless without that flag.
- **claude auditors.** The adapter's claude launch line has no edit permission mode, so claude
  seats could not write their reports (plan audit rounds 1-2, transcribed from stdout); with
  `--permission-mode acceptEdits` and `--add-dir` for the report folder and the resolved `SYNC`
  target they could.
