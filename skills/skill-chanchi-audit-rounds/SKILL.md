---
name: skill-chanchi-audit-rounds
description: Use when running redundant audits with three auditors of different model families (designs, briefs, rules, skills, agents, lessons, global item versions, adoption decisions, replication plans). Covers opening rounds, isolating reports, recording votes, unavailability and dissent, and closing or escalating.
---

# chanchi — audit rounds

Everything the orchestrator writes (designs, briefs, rules, skills, agents, lessons) is audited before merge, and from later phases so are global item versions (`item`), adoption decisions (`adoption`), and replication plans (`replication`). You coordinate up to three rounds of three auditors (`agent-chanchi-auditor`) and never judge your own work.

All `chanchi` commands print JSON. Errors carry `field`, `valid_values`, and `hint`.

## Procedure

1. **Write one brief for all three seats.** Include the request, the evidence, the subject at its commit (`--commit <sha>`) or version (`--version <x.y.z>`), and a distinct private scratch path for each seat's report (outside any shared review folder). In rounds 2 and 3, tell each seat where to find its own earlier report (or the previous round's consolidation) so it re-checks its earlier findings first while keeping the current round's reports private.

2. **Open the audit and seat three auditors:**
   `chanchi audit open --kind design --ref docs/designs/<topic>.md --author <agent:model[:effort]> --commit <sha>`
   Use `--version <x.y.z>` for an item, `--kind other` for plans or miscellaneous subjects, and optional `--change <ref>` / `--project <slug>`.
   - `chanchi` fills three seats from `SYNC/config/auditors.toml` (or the built-in roster), preferring distinct known model families.
   - Check `degraded` (`true` when fewer than three distinct known families sit; unknown families fail closed — fix with `chanchi models set <agent:model> --family <name>`) and `skipped` (register missing models with `chanchi models add --agent <harness> --model <model> --cost <1-3>`).
   - If fewer than two seats can be filled, round 1 closes immediately as `escalated` (`quorum`); stop and hand the escalation to the human.

3. **Launch each seat independently.** `chanchi` never launches harnesses. For each seat, run its `launch` command in its own conversation with the brief (and that seat's private report path) as the prompt. Keep all reports in their private scratch paths and move them into `docs/designs/reviews/<topic>/` (or the subject's review folder) **only after every active seat has voted**, so no auditor can read another's report.

4. **Replace an unavailable auditor.** If a seat's harness fails to run, record the failure and paste its error:
   `chanchi audit unavailable <audit-id> --round <n> --seat <1-3> --reason "<error>"`
   `chanchi` refills the seat from the next available roster entry (or returns `seat: null` when exhausted) and recomputes `degraded`.

5. **Record each vote:**
   `chanchi audit vote <audit-id> --round <n> --seat <1-3> --verdict pass|pass_with_fixes|fail --blocking <n> --major <n> --minor <n> --report <path>`
   - Map the report's first line (`VERDICT: PASS`, `PASS WITH FIXES`, `FAIL`) and count **open** findings only.
   - In round 2+, count `OPEN` and `PARTIAL` re-checked findings at their original severity plus new open findings; exclude `RESOLVED` findings.
   - `pass` is refused when `blocking > 0` or `major > 0`.

6. **Decide every lone finding.** For every open finding raised by **exactly one** auditor, verify it against the request, code, or evidence and record the decision:
   `chanchi audit dissent <audit-id> --round <n> --seat <1-3> --finding "<id: text>" --severity blocking|major|minor --decision confirmed|rejected --evidence "<why>"`

7. **Close the round and write one consolidation file:**
   `chanchi audit close <audit-id> --round <n>`
   Outcomes (checked in order):
   - fewer than 2 voted seats → `escalated` (`quorum`)
   - at least 2 `fail` votes → `rework`
   - at least 2 approvals (`pass`, or `pass_with_fixes` with 0 blocking and 0 major) and no confirmed lone `blocking` or `major` dissent → `accepted`
   - otherwise → `fix`
   - round 3 ending in `fix` or `rework` → `escalated` (`round_cap`)

   Write one consolidation file per round (e.g. `round<N>-consolidation.md`, or `round3-escalation.md` on escalation) recording seats, votes, consolidated findings, lone-finding dissent decisions with evidence, and outcome.

8. **Stop or open the next round:**
   - **`accepted`**: stop. Apply the minor fixes listed in `minor_fixes` (from approving votes and confirmed lone minors) without opening a new round.
   - **`escalated`**: stop. Give the human the disagreement/escalation report to decide.
   - **`fix` or `rework`** (round < 3): apply the fixes or rework, commit, and open the next round with the new commit or version so the same seats re-check their findings:
     `chanchi audit round <audit-id> --commit <next-sha>`

## Inspect

- `chanchi audit show <audit-id>` — print every round, seat, vote, dissent, and outcome.
- `chanchi audit list [--kind <k>] [--ref <ref>]` — list audits with their round count and last outcome.
