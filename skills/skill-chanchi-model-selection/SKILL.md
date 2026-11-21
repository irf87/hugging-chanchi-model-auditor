---
name: skill-chanchi-model-selection
description: Use when planning an OpenSpec change or any multi-session work and you must assign an agent, model and effort to each executor session. Queries the local chanchi rating for the best-value model per task type and complexity, and opens the change record.
---

# chanchi — model selection

`chanchi` is a local CLI that rates `(agent, model, effort)` triples from past audits. Use it while
planning, at the moment you assign an executor to each session. It never decides for you: it gives
evidence, you choose, and your choice becomes future data.

All commands print JSON. On failure they print `{"ok": false, "error": {...}}` to stderr with
`field`, `valid_values` and `hint` — read them and correct the call instead of guessing.

## Before you start

1. Confirm the tool works: `chanchi db status`.
2. Get the list of available executors **from the human's prompt**, as `agent:model[:effort]`
   (agents: `claude`, `agy`, `opencode`). Never assume a model is available. If the prompt does not
   list them, ask. In `--available`, list every effort of a model that the human made available,
   so the effort that holds a model's audits competes for `recommendation`.
3. Make sure each one is in the catalog: `chanchi models list`. For a missing model, ask the human
   for its cost tier (1 = $, 2 = $$, 3 = $$$) and register it:
   `chanchi models add --agent agy --model gemini-3.8-flash-high --cost 1 --efforts low,medium,high`
   (omit `--efforts` when the agent has no effort flag). Never pass `--capability` to `models add`
   or `models set` — capability values are maintained by the owner alone.

## Steps

1. **Open the change** with your own identity (use effort `unknown` if you do not know yours; use
   `human` as planner when the human gave the instructions directly):
   `chanchi change open <change-ref> --kind openspec --planner claude:opus:high`
   For work outside OpenSpec use `--kind adhoc` and a short free ref.
2. **Classify every planned session**: one `task_type` (list them with `chanchi taxonomy list`) and
   one `complexity`:
   - `low` — one layer, ≤ 3 files, no domain ambiguity, mechanical.
   - `medium` — 2 layers or 4–10 files, or one non-trivial domain rule.
   - `high` — ≥ 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), or
     meaningful domain ambiguity.
   Pick the type that dominates the session's work. If none fits, ask the human before adding one
   with `chanchi taxonomy add-type <code> --description "..."`.
3. **Ask for a recommendation per session**:
   `chanchi recommend --task-type ui-component --complexity medium --available "agy:gemini-3.8-flash-high:high,claude:sonnet:medium"`
   Add `--require vision` when the session needs to read screenshots or images.
4. **Read the result**:
   - `recommendation.spec` is the cheapest candidate within 5 points of the best smoothed score,
     excluding candidates with an honesty red flag. It is `null` when there is not enough data
     (`reason: insufficient_data`), every candidate is red-flagged (`reason: all_candidates_red_flagged`),
     or `--require` filtered out every listed spec (`reason: no_capable_candidates`).
   - `excluded` lists every spec removed by `--require` with its missing capability values (`no` or `unknown`). Report excluded `unknown` models to the owner so the owner can classify them, and choose among the remaining candidates.
   - Each candidate shows `level` (how specific the data is: `task_type+complexity`, `task_type`,
     `complexity`, `global`), `n`, `confidence` (`insufficient` < 3, `low` < 10, `ok`),
     `clean_rate`, `honesty_flags_per_session`, `retry_rate` and `top_codes`.
   - Treat data found at the `complexity` or `global` level as weak evidence: it says how the model does in general, not on this kind of task. At `high` complexity, a `task_type` level is weak evidence too (prefer a candidate with data at `task_type+complexity` when available).
   - `explore` lists up to 3 models at `low` or `medium` complexity where no listed effort has 3 or more audited sessions of the requested `task_type` (and none is red-flagged on 3 or more sessions or the `recommendation` model); `explore_reason` is `null` when `explore` has entries, `complexity_not_explorable` at `high` complexity, or `no_explorable_candidates`. Each entry carries `deprioritized`: `null`, `"weak_start"`, or `"red_flag_low_data"` (any non-null value means try it only if nothing better is offered).
   - Each `explore` entry also carries `external_signals` (`null` when unmapped or the task type has no signal). Any benchmark values there are unverified, come from the upstream Hub checkpoint rather than the served variant, and never count as audit evidence (and `pull_request: true` marks rows from an open pull request). `external_signals` only orders `explore` inside a cost tier — never copy its numbers into audits or session protocols.
   - With `recommendation: null`, prefer an `explore` spec when the budget allows, otherwise choose by judgement — that choice is how data accumulates.
   - **Exploration budget**: in a change planned with `n` executor sessions, assign at most `max(1, floor(n / 4))` explore sessions when `n >= 2`, and `0` when `n == 1`. Never assign an explore session to work that blocks later sessions. Keep every explore session of a model on the exact effort of its `explore` spec. Start every explore session and any retry of it with `chanchi session start ... --tags explore` (fix a missed tag with `chanchi session update --tags <existing tags>,explore`). Check the count and `over_budget` in the `exploration` block of `chanchi show <change>`.
5. **Write it into the session protocol** of the plan, one line per session, e.g.:
   `chanchi: recommended agy:gemini-3.8-flash-high:high (99.6, low confidence, task_type+complexity) · chosen agy:gemini-3.8-flash-high:high`
   If you deviate, add `· reason: <why>`. For an explore session, append `· explore: <spec>`.
6. Hand the change over to orchestration; the `skill-chanchi-session-audit` skill takes it from there.

## Catalog maintenance (when the human asks)

- `chanchi models set claude:sonnet --cost 2` — change a cost tier.
- `chanchi models set claude:haiku --active 0` — retire a model without losing its history.
- Never pass `--capability` to `models set` or `models add`; report excluded `unknown` models to the owner instead.
- `chanchi stats --by task-type` — see how every model performs per task type.
- `chanchi stats --by dimension` — see how every model performs per code-quality dimension (correctness, architecture, clean code, honesty, discipline). 100 means no recorded fault, not proven quality; read it with `n` and `confidence`.
- `chanchi stats --role planner` — see how planners perform.
- `chanchi scoring explain` — show the formulas and weights behind every number.
