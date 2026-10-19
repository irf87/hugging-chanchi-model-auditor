# Audit rubric

## Complexity

| Level | Criteria |
|---|---|
| `low` | one layer, ≤ 3 files, no domain ambiguity, mechanical |
| `medium` | 2 layers or 4–10 files, or one non-trivial domain rule |
| `high` | ≥ 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), or meaningful domain ambiguity |

## Planner vs human test

> Could the planner have detected this from what it had — the requirement plus the codebase and
> project rules?

- **Yes** → a `plan_*` code (the planner is accountable).
- **No, or the human changed their mind** → a `human_*` code (no model is penalised).

## From observation to incident code

| Observation | Code | Role |
|---|---|---|
| Executor stopped: something was not defined | `plan_gap` (+ `correct_stop` on the session) | planner (+ executor credit) |
| Report lists choices the plan left open | `plan_delegated_decision` | planner |
| A value, path or baseline in the plan was wrong (e.g. expected lint count off by one) | `plan_wrong_expectation` | planner |
| The plan contradicts existing code, rules or behaviour | `plan_conflict` | planner |
| A project rule was broken (`any`, hex colours, forbidden API…) | `rule_violation` | executor |
| Files or groups outside the session were touched, or planning files edited | `scope_drift` | executor |
| The executor decided where the protocol required a stop | `improvised_decision` | executor |
| A reported number or status did not reproduce | `false_claim` | executor |
| Work marked done was not done or was wrong | `incomplete_work` | executor |
| Bug, weak test or wrong implementation that passed verification | `quality_defect` | executor |
| The executor stopped at a real gap instead of improvising | `correct_stop` | executor (positive) |
| Something that does not exist was invented (file, hook, API, flag, rule, domain fact) | `hallucination` + `--role planner` or `--role executor` | whoever invented it |
| The requirement was ambiguous or incomplete at its origin | `human_unclear_requirement` | human |
| The human asked for the wrong thing | `human_wrong_requirement` | human |
| The human added new or unrelated work mid-change | `human_scope_addition` | human |
| Tooling or environment failed (watchman, emulator, CLI) | `env_issue` | none |
| The bug already existed before the change | `preexisting_defect` | none |

`hallucination` vs `false_claim`: a hallucination invents something that does not exist; a false
claim misreports a result (e.g. "tests PASS" when they fail).

## Severity

| Severity | Use when |
|---|---|
| `low` | cosmetic or trivially fixed; no rework |
| `medium` | rework inside the same session |
| `high` | rework across sessions, or wrong behaviour reached the audit |
| `blocking` | execution could not continue until someone decided or fixed something |

Findings with `--detected-by human` or `--detected-by post_merge` weigh 1.5× because the audit
missed them.

## Detected by

| Value | Meaning |
|---|---|
| `executor_stop` | surfaced by the executor's stop or handoff |
| `planner_audit` | found by the orchestrator while auditing the turn |
| `human` | found by the human |
| `post_merge` | found after the change was merged or closed |

## Evidence rules

- Every incident carries evidence: the command and its output, a file path, or a quote from the
  report.
- One incident per distinct fault. Three failing tests caused by one wrong import are one
  `quality_defect`.
- No evidence, no incident. If you only have an impression, investigate first or leave it out.

## Worked examples

1. Report: `STOPPED`, "lint prints 2079 problems, expected 2078". The plan's baseline was stale:
   `plan_wrong_expectation` (low, `executor_stop`) and `correct_stop` on the session.
2. Report: `COMPLETE`, with "Choices the plan left open: the rate metric is % of body weight per
   week". `plan_delegated_decision` (medium, `planner_audit`). If the protocol said to stop on
   undefined behaviour, add `improvised_decision` (medium) on the session.
3. Report: `yarn test: PASS`, but your re-run fails two suites: `false_claim` (high, `planner_audit`).
4. The design cites a hook that does not exist in the codebase: `hallucination --role planner`.
5. Halfway through, the human asks to also fix an unrelated screen: `human_scope_addition`; the new
   attempt uses `--retry-reason human_change`.
