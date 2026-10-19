---
name: chanchi-session-audit
description: Use when orchestrating executor sessions of an OpenSpec change (or adhoc work) and when auditing their reports or handoffs. Records each session, every stop and audit finding as evidence-backed incidents, and the verdict, so chanchi can turn audits into model ratings.
---

# chanchi — session audit

You are the orchestrator: the only writer of audit data. Executors never rate anyone; when they hit
something undefined they stop and hand off, and you record what happened. Record facts with
evidence, not impressions. Read `references/rubric.md` before classifying anything.

The project is detected from the git repository you run in (`--project <slug>` overrides it). All
commands print JSON; errors carry `field`, `valid_values` and `hint`.

## Session lifecycle

1. **Before launching a session**:
   `chanchi session start <change-ref> S1 --executor agy:gemini-3.8-flash-high:high --task-type ui-component --complexity medium --tasks 10 --groups 8,9,10`
   Use the executor, task type and complexity written in the session protocol. `--tasks` is the
   number of tasks the session owns. Re-running a session creates a new attempt and requires
   `--retry-reason executor_failure|plan_fix|human_change|env`.
2. **When the report or handoff arrives**:
   `chanchi session report <change-ref> S1 --status STOPPED`
   (`COMPLETE`, `STOPPED` or `BLOCKED`, exactly as the executor reported). Report again with the new
   status if the same session resumes after you resolve a stop.
3. **Classify every stop** (see the rubric). A stop at a real plan gap is two incidents:
   `chanchi incident add <change-ref> --code plan_gap --severity blocking --detected-by executor_stop --task 7.3 --desc "design does not define the sort order" --evidence "report S1: STOP at 7.3"`
   `chanchi incident add <change-ref> --session S1 --code correct_stop --severity low --detected-by executor_stop --desc "stopped instead of choosing an order" --evidence "report S1: STOP at 7.3"`
   A stop caused by the human is `human_*`; an environment problem is `env_issue`.
4. **Audit the turn** — the executor's numbers are claims:
   - re-run every verification command; a number that does not reproduce → `false_claim`;
   - check the diff against the session's scope → `scope_drift`;
   - check the project's rules → `rule_violation`;
   - "choices the plan left open" in the report → `plan_delegated_decision`, plus
     `improvised_decision` on the session when the protocol required a stop;
   - invented files, APIs, flags or rules → `hallucination` with `--role executor` (or
     `--role planner` when the plan invented it).
5. **Record the verdict**:
   `chanchi session audit <change-ref> S1 --verdict accepted`
   - `accepted` — nothing had to be corrected.
   - `accepted_with_fixes` — accepted after small corrections within the turn.
   - `rejected` — the turn's work is discarded or redone as a new attempt.
6. **At archive time**: `chanchi change close <change-ref>`, then `chanchi show <change-ref>` and give
   the human the summary (session scores, planner score, incidents by role).

## Corrections and late findings

- Wrong incident: `chanchi incident void <id> --reason "..."` (nothing is ever deleted).
- Wrong classification: `chanchi session update <change-ref> S1 --complexity high`.
- A defect found after the change closed still belongs to the original session:
  `chanchi incident add <change-ref> --session S3 --code quality_defect --severity high --detected-by post_merge --desc "..." --evidence "..."`

## Rules

- No evidence, no incident. `--evidence` names the command and its output, a path, or a quote.
- One incident per distinct fault, not one per symptom.
- Apply the planner-vs-human test before blaming the plan.
- Never answer a product or plan decision on the executor's behalf; surface it to the human.
