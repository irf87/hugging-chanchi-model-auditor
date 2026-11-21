# Exploration Policy, Catalog Capabilities and Hugging Face Ordering for `chanchi recommend`

*   **Author:** Iván R
*   **Status:** Implemented (merged on 2026-11-19: Phases 1-2 in `a524f3e`, Phase 3 in `fd167b0`)
*   **Date:** 2026-11-17

--------------------------------------------------------------------------------

## Overview

`chanchi recommend` picks an `(agent, model, effort)` for a task type and complexity from audited
executor sessions. It only trusts a spec `(agent, model, effort)` after at least 3 audited
sessions, looked up from the requested task type and complexity down to all sessions. Models the owner seldom picks, mostly the open-weight models reachable through opencode,
rarely reach that threshold: they are never suggested, so they collect audits only when a planner
picks them by hand.

This design adds three things, built and verified in order:

1.  **Phase 1, exploration policy.** `recommend` returns a separate `explore` list of up to 3
    models where no listed effort has 3 audited sessions of the requested task type, for low and
    medium complexity only. The
    planner may assign one of them on purpose, within a budget, so audits produce the missing
    data. The evidence-based `recommendation` is unchanged.
2.  **Phase 2, catalog capabilities.** The owner records per-model capabilities such as `vision`
    (yes / no / unknown). `recommend --require vision` keeps only models that have it.
3.  **Phase 3, Hugging Face snapshot.** A maintainer script in this repository reads public
    Hugging Face Hub metadata into a committed JSON snapshot. chanchi reads it offline to order the
    `explore` list and to show `external_signals`. It never changes a score.

## The Problem

The owner has subscriptions that give access to about 22 models through opencode, most of them
open-weight (GLM, Kimi, MiniMax, MiMo, DeepSeek, Hy, LongCat, Step, Qwen). They want to know which
of them can do domain logic, UI work, terminal work, or read screenshots, so that work can be
spread across cheaper models. Today chanchi offers no way to learn that short of manual picks.

**How chanchi is deployed.** The owner installs this repository once with `uv tool install
--editable .`, so every project on the machine runs the same checkout of the `chanchi` package.
All projects write to one global SQLite database (`~/.local/share/chanchi/chanchi.db`). A data
file committed to this repository therefore reaches every project, and a schema migration applies
to every project at once.

Because the install is editable, the main checkout's working tree is production: whatever files
it holds, on any branch and committed or not, are what every project runs. All work for this
design, including running the fetch script with `--write`, therefore happens in git worktrees.
Code sessions set `CHANCHI_DB` to a scratch file; the fetch script never opens the database. The
main checkout only receives merges, and a change goes live for every project on the first
`chanchi` call after the merge. The exception is owner data operations (`chanchi models add`,
`chanchi models set`): they change the real catalog, so the owner runs them with the installed
`chanchi` and without `CHANCHI_DB`.

**How `recommend()` picks today** (`src/chanchi/scoring.py`):

1.  Each `--available` spec `agent:model[:effort]` is a candidate.
2.  For each candidate, chanchi looks for its audited executor sessions at the first level with at
    least 3 sessions: same task type and complexity, then same task type, then same complexity,
    then all sessions (`global`). If no level reaches 3 sessions, the first level with any session
    is used. The level used is reported as `level`.
3.  The candidate's score is a smoothed mean: `(n × mean + 3 × prior) / (n + 3)`. The prior
    (`prior_for()`) is the mean of all executor sessions matching the chosen level's filters; with
    no such session it is the mean of all executor sessions, and 70 only when there are none.
    A candidate with no session at any level uses the task type and complexity filters.
    `confidence` is `insufficient` below 3 sessions, `low` below 10, `ok` from 10.
4.  `red_flag` is true when the candidate's sessions at that level average more than 0.2 honesty
    incidents (`false_claim` or `hallucination`, recorded by the auditor) per session. It is
    computed per spec and per level, so the same model can be red-flagged for one task type and
    not another, and it clears when enough clean sessions bring the average down.
5.  Eligible candidates have confidence `low` or `ok` and no red flag. Among those within
    `RECOMMEND_WINDOW` (5 points) of the best smoothed score, the cheapest `cost_tier` wins. If no
    candidate is eligible, `recommendation` is null with reason `insufficient_data` or
    `all_candidates_red_flagged`.

Why unaudited models are stuck:

*   `recommend()` in `src/chanchi/scoring.py` (line 470) treats a candidate as eligible only when
    its confidence is `low` or `ok`. `taxonomy.confidence(n)` returns `insufficient` for
    `n < 3` (`CONFIDENCE_LOW_MIN = 3`). A model with 0 to 2 sessions is listed in `candidates`
    but can never be the `recommendation`.
*   The planner skill (`skills/chanchi-model-selection/SKILL.md`) follows the `recommendation`,
    so unaudited models are not assigned, and they stay unaudited.
*   chanchi has no record of what a model can do (for example, accept images), so a planner cannot
    ask for "a model that can read screenshots".
*   The owner has no outside information about these models in one place. Hugging Face Hub
    publishes benchmark results (`evalResults`) and a task tag (`pipeline_tag`) for most of them,
    but every observed result is unverified, results use different harnesses and units, and the
    Hub checkpoint is not the variant opencode serves.

The solution breaks the loop with an explicit, bounded exploration rule, adds owner-set
capabilities, and uses Hugging Face data only to decide which unaudited model to try first. Audit
scores stay the only evidence of quality.

## Goals

*   **G1. Models untested on a task type get suggested.** For any `recommend` call at low or
    medium complexity where `--available` includes models none of whose listed efforts has 3 or
    more audited sessions of the requested task type (whatever their total), that are not
    red-flagged on 3 or more sessions, not the `recommendation` model, and not excluded by
    `--require`, the JSON output contains an `explore` list of up to 3 of them, at most one spec
    per `(agent, model)`.
*   **G2. The evidence gate is unchanged.** For the same database and arguments, the
    `recommendation` field and its `reason` are identical before and after this change. Existing
    `tests/test_scoring.py` recommendation tests pass without edits.
*   **G3. Exploration is bounded and visible.** `explore` is empty at `high` complexity (the highest
    value in `taxonomy.COMPLEXITIES`). The planner skill limits exploration to
    `max(1, floor(n / 4))` of a change's `n` executor sessions (none when `n` is 1) and requires
    every explore session to carry the tag `explore`. `chanchi show <change>` counts the tagged
    sessions and, once the change is closed, reports `over_budget` when they exceed that limit,
    so overruns are visible after the fact.
*   **G4. Capability filtering.** `recommend --require <cap>[,<cap>...]` returns only candidates
    whose catalog value is `yes` for every listed capability. Every removed candidate appears in
    an `excluded` list with a reason (`no` or `unknown`). When no candidate is left, the output has
    `recommendation: null` and `reason: no_capable_candidates`.
*   **G5. Hub data orders exploration and is traceable.** When the snapshot has data for a
    candidate, the `explore` list is ordered using the signal mapped to the requested task type,
    and each `explore` entry shows `external_signals` with the benchmarks used, the Hub repo, the match
    quality, the fetch date and `verified: false`.
*   **G6. The package stays offline.** No module under `src/chanchi` imports a network module. A
    test enforces this. Only `scripts/fetch_hf_benchmarks.py` contacts the network, and it is not
    reachable as a `chanchi` subcommand or from any skill.
*   **G7. Every project benefits.** The snapshot ships inside the editable checkout, so every
    project's `recommend` uses it without extra setup.

## Non-Goals

*   A fourth cost tier.
*   Scores for orchestrator or auditor roles derived from benchmarks.
*   Any change to audit-based scores: `session_score`, `smoothed()`, `prior_for()`, `stats` (all
    groupings), dimension and planner scores stay as they are.
*   Benchmark data for closed models (Claude, Gemini, Grok). They take part in exploration and
    capabilities like any model, without `external_signals`.
*   A `chanchi` subcommand or skill text that fetches from the network.
*   Storing computed percentiles, priors or signals. The snapshot holds raw Hub rows only.
*   A benchmark signal for tests, unit-tests, ui-component, ui-layout-styling, docs,
    db-schema-migration, architecture-design or custom task types. For these, only exploration and
    audits produce data.
*   A bounded benchmark offset on scores (deferred, see Future Improvements).

## Open Questions

*   None at this stage. The open questions from the brief (exploration budget, list size, near
    Hub matches, catalog registration, unknown capabilities, all-excluded result, refresh
    failures) were resolved by the owner on 2026-11-17; each answer is part of the Technical Plan.

## Critical User Journeys (CUJs)

### CUJ 1: Planner explores an unaudited open model

*   **Given**: The catalog has `opencode:opencode-go/glm-5.3-flash` with 0 audited sessions and
    `claude:sonnet` with 12 audited `bugfix` sessions. The planner is planning a change with 8
    executor sessions.
*   **When**: The planner runs `chanchi recommend --task-type bugfix --complexity medium
    --available "claude:sonnet:medium,opencode:opencode-go/glm-5.3-flash:high"`.
*   **Then**: `recommendation` is `claude:sonnet:medium`, as today. `explore` lists the GLM spec
    with `n_task_type: 0`. The planner assigns GLM to at most 2 of the 8 sessions and starts them
    with `chanchi session start ... --tags explore`, at `:high`, the effort of the `explore` spec. After
    3 audited `bugfix` sessions at that effort, GLM competes for `recommendation` on its audit
    scores.

### CUJ 2: Planner needs a model that reads screenshots

*   **Given**: The owner has set `vision=yes` on three models, `vision=no` on two, and left the
    rest `unknown`.
*   **When**: The planner runs `recommend --task-type ui-component --complexity low --require
    vision --available "<all specs>"`.
*   **Then**: `candidates`, `recommendation` and `explore` only contain the three `vision=yes`
    models. `excluded` lists every other spec with reason `no` or `unknown`. If none of the
    available models has `vision=yes`, `recommendation` is null with `reason:
    no_capable_candidates`.

### CUJ 3: Owner refreshes the Hugging Face snapshot

*   **Given**: Phases 1 and 2 are merged and the real database is migrated. The owner is in the
    root of a git worktree of this repository, on a refresh branch. `HF_TOKEN` may or may not be
    set.
*   **When**: The owner runs `uv run python scripts/fetch_hf_benchmarks.py` (dry run), reviews the
    printed summary, then runs it with `--write`, reviews the git diff of the worktree's snapshot
    file, commits it and merges the branch.
*   **Then**: The snapshot contains raw rows for every mapped model. A repo that failed (404 or
    rate limit) keeps its previous rows and original fetch date, and the summary reports the
    failure. The summary lists the mapped models the Hub tags `image-text-to-text`; the owner
    compares them with `chanchi models list` and sets `vision` with the installed `chanchi`. No
    other project sees the new data until the merge; after it, every project's next `recommend`
    call uses it.

### CUJ 4: Another project's agent cannot fetch

*   **Given**: A planner agent in another project (for example a consumer project) has the chanchi skills
    linked.
*   **When**: It reads the skills or runs `chanchi --help`.
*   **Then**: No skill text and no `chanchi` subcommand mentions or performs a fetch. Running the
    script from another directory stops with an error that names this repository's root.

## Technical Plan (Architecture)

The three phases change different layers and are built and verified in order. Each phase is
backward compatible: it only adds JSON keys, CLI flags, one table and one data file.

```text
                         this repository only                         every project
                ┌──────────────────────────────────────┐     ┌──────────────────────────────┐
 Hugging Face   │ scripts/fetch_hf_benchmarks.py       │     │ chanchi recommend            │
 Hub API ──────▶│  reads scripts/hf_model_map.json     │     │  (package, no network)       │
 (public, opt.  │  writes src/chanchi/data/            │────▶│                              │
  HF_TOKEN)     │         hf_snapshot.json (committed) │ git │  candidates ── audit scores  │
                │  prints vision candidates            │     │  recommendation (unchanged)  │
                │                                      │     │  explore ◀── hfsignals.py    │
                └──────────────────────────────────────┘     │  excluded ◀── capabilities   │
                                                             └──────────────▲───────────────┘
                                                                            │
                                     global DB: models + model_capabilities ┘
```

### Phase 1: exploration policy

**Rule.** After `recommend()` builds `candidates` as today, it builds `explore`. The steps run in
this order: the filters and the model-level low-data red flag (rules 1, 2 and 5), then one spec
per model (rule 4, first sentence), then `deprioritized` on the kept spec and the sort (rule 3),
then the top 3 (rule 4).

`n_task_type` of a spec is the number of audited executor sessions of that exact spec
`(agent, model, effort)` for the requested task type, at any complexity. It is counted per
effort because eligibility for `recommendation` is: `recommend()` looks up a candidate's
sessions by `(agent, model, effort)`, so 2 sessions at `:low` and 1 at `:high` make neither spec
eligible.

1.  A model `(agent, model)` is explorable when, among its specs in `--available`:
    *   none has an `n_task_type` of 3 (`CONFIDENCE_LOW_MIN`) or more;
    *   none is red-flagged at a level with 3 or more sessions;
    *   none is the `recommendation`.

    Only listed efforts count, as in `recommend()`: chanchi judges what the planner offers. A
    model whose audits sit at an effort the planner did not list can therefore be explored at
    another effort; the selection skill will tell planners to list every effort of a model that
    the human made available, so the effort with audits competes for `recommendation` instead.
    A red flag on a well-sampled effort removes the model, not just that spec. A red flag
    computed on fewer than 3 sessions (one honesty incident in one session is enough) does not
    remove the model; instead the model gets a low-data red flag. The flag belongs to the model:
    when any of its listed specs is red-flagged on fewer than 3 sessions, the spec kept by rule 4
    carries `deprioritized: "red_flag_low_data"`, whichever effort it is, so the order of
    `--available` cannot clear it. The spec sorts in the last group (rule 3), so one incident
    cannot end exploration on every task type, while the model is offered only when fewer than 3
    explorable specs rank ahead of it.

    A model's total session count across task types does not matter. A model with 10 `bugfix`
    sessions and 0 `ui-component` sessions is explorable for `ui-component`, so the owner learns
    how it does on visual work. It may still compete for
    `recommendation` on its global data, as today; the two fields are computed separately,
    except for rule 5.
2.  Exploration only runs when `complexity` is in a new constant
    `taxonomy.EXPLORE_COMPLEXITIES = ("low", "medium")`.
3.  The remaining specs, one per model, are sorted by:
    1.  deprioritized last. A spec is deprioritized when its model has a low-data red flag
        (rule 1) or when it is a weak start: its sessions counted in `n_task_type` (1 or 2 of
        them) have a mean score more than `RECOMMEND_WINDOW` (5) points below the prior for the
        task type at any complexity (`prior_for(records, task_type, None)`, the same scope
        `n_task_type` counts), so a model that failed its first trial is not offered first
        again. Both are computed on the spec kept by rule 4. The entry's `deprioritized` field is
        `null`, `"weak_start"` or `"red_flag_low_data"`; when both apply it is
        `"red_flag_low_data"`. Deprioritized specs sort among themselves by the keys below.
        Reusing `RECOMMEND_WINDOW` is deliberate: "5 points worse" is already chanchi's measure
        of a meaningful score gap;
    2.  `cost_tier`, lowest first;
    3.  `n_task_type`, highest first, so exploration finishes a model before it starts the next
        one. With 1 or 2 explore sessions per change and many tier-1 models, lowest-first would
        spread the sessions so thin that no model reaches the 3 sessions it needs to compete for
        `recommendation`;
    4.  `spec`, for a stable order.

    Phase 3 adds an external signal key between `cost_tier` and `n_task_type` (Phase 3,
    "Ordering with signals").
4.  One spec per `(agent, model)` is kept: the effort with the highest `n_task_type`, then the
    first as written in `--available`. Keeping the effort that already has sessions lets them add
    up toward eligibility; several efforts of one model would also crowd out other models. The
    selection skill keeps every explore session of a model on the effort of the `explore` spec.
    After the sort, the first `taxonomy.EXPLORE_MAX = 3` become `explore`.
5.  No effort of the `recommendation` model appears in `explore` (rule 1), so one model is never
    offered twice.

**Output.** Two keys are added to the `recommend` result. Existing keys and their values do not
change (Goal G2).

```json
"explore": [
  {"spec": "opencode:opencode-go/glm-5.3-flash:high", "cost_tier": 1, "n_task_type": 0,
   "deprioritized": null}
],
"explore_reason": null
```

Each entry has exactly these four keys in Phase 1; Phase 3 adds `external_signals` (Phase 3,
"Explore entries with a signal"). The two keys follow `candidates` in the result.

`explore_reason` is `null` when `explore` has entries, `complexity_not_explorable` at high
complexity, and `no_explorable_candidates` when no model passes rule 1 (a listed effort with 3 or
more sessions of the task type, a spec red-flagged on 3 or more sessions, or the
`recommendation` model).
`complexity_not_explorable` takes precedence over every other reason, including after `--require`
removes all candidates.

**Known leak into `recommendation` (not changed, to keep Goal G2).** The complexity limit applies
to `explore` only. After a model collects 3 low or medium audits of a task type, the existing level
search in `recommend()` falls back from `task_type+complexity` to `task_type`, so at `high`
complexity the model becomes eligible on data from easier sessions, and the cheapest-in-window
rule can pick it. This is today's behaviour for every model; exploration only makes it happen
sooner for cheap models. The selection skill already calls `complexity` and `global` level data
weak evidence; that line is extended: at `high` complexity, a `task_type` level is weak evidence
too, and a candidate with data at `task_type+complexity` is preferred. A test pins the current behaviour so a later change to it is
deliberate.

**Budget.** `recommend` does not know which change it is planning for, so the budget is a rule in
`skills/chanchi-model-selection/SKILL.md`:

*   An explore session is an executor session started with `chanchi session start ... --tags
    explore` (the existing `sessions.tags` column). Every session that uses an `explore` spec is
    one, and a retry of it (`session start --retry-reason`) is also started with `--tags
    explore` (chanchi does not copy tags between attempts). A missed tag is fixed
    with `session update --tags <existing tags>,explore`, because the flag replaces the list.
*   For a change planned with `n` executor sessions, at most `allowed` may be explore sessions:
    `allowed = 0 if n < 2 else max(1, floor(n / 4))`.
*   Never for a session that blocks other sessions (a session whose output later sessions of the
    same change depend on).
*   The protocol line also records it as `· explore: <spec>`. The protocol line is the one line
    per executor session that the planner writes into the change's plan (for example
    `openspec/changes/<change>/tasks.md`) as step 5 of the selection skill requires:
    `chanchi: recommended <spec> (...) · chosen <spec>`. It is for humans and auditors only;
    chanchi never parses it.

chanchi does not prevent overruns, but it reports them: `chanchi show <change>` gains an
`exploration` block computed from existing columns, with no migration:

*   `sessions` (`n`): distinct `session_ref` values of the change.
*   `exploratory`: those with at least one attempt tagged `explore`, an exact count.
*   `allowed`: `0 if sessions < 2 else max(1, floor(sessions / 4))`.
*   `over_budget`: `exploratory > allowed`, but `null` until the change is closed
    (`changes.closed_at` set). While a change is in progress the recorded sessions are only part
    of the plan, so a partial count would report false overruns.

A closed change of 2 or 3 sessions with 1 explore session is within budget.

### Phase 2: catalog capabilities

**Storage (separate table, values validated in Python; see Alternatives J and K).** Migration
`003_model_capabilities.sql`:

```sql
CREATE TABLE model_capabilities (
  model_id    INTEGER NOT NULL REFERENCES models(id),
  capability  TEXT NOT NULL,
  value       TEXT NOT NULL,      -- 'yes' | 'no', validated in taxonomy.py, no CHECK
  set_at      TEXT NOT NULL,
  PRIMARY KEY (model_id, capability)
);
```

*   No row means `unknown`. Setting a capability to `unknown` deletes its row.
*   Capabilities belong to `(agent, model)`, not to an effort: if a model reads images, it does
    so at every effort.
*   `taxonomy.py` gains `CAPABILITIES = ("vision",)` and `CAPABILITY_VALUES = ("yes", "no",
    "unknown")`. Adding a capability later is a code change to that tuple, with no migration.
    `taxonomy list` reports them.
*   No CHECK constraints, so a new value never needs a table rebuild. The cost: the database does
    not reject bad values. A test asserts that every stored value is `yes` or `no` (`unknown` is
    never stored).
*   No `source` column. Every write is the owner running `models set` (the selection skill
    will forbid planners from passing `--capability`, see below), so a source of `hf` would
    only mean "the owner accepted a suggestion", which is not real provenance. If provenance is
    needed later, `ALTER TABLE model_capabilities ADD COLUMN` adds it without a rebuild; keeping
    the irreversible migration minimal is worth more now.

**CLI.**

*   `chanchi models add ... --capability vision=yes` and `chanchi models set <agent:model>
    --capability vision=no`. The flag can be repeated.
*   `models list`, `models add` and `models set` add a flat string `"capabilities":
    "vision=yes"` to each model: `name=value` pairs for the stored rows, sorted by name and
    joined with commas, `""` when the model has none (so unknown). A string keeps every row flat,
    so `--format text` still renders the models table (`render.py` treats any dict value as
    nested). `set_at` is stored but not listed.
*   `chanchi recommend ... --require vision[,<cap>...]` (AND semantics). An unknown capability
    name is an `invalid_value` error with `valid_values`, as `taxonomy.validate_choice` raises
    for other enums.

**Recommend with `--require`.** Specs from `--available` are resolved as today (so unknown or
inactive specs still raise the same errors). Then each spec is checked against the required
capabilities before scoring:

*   A spec that has `yes` for every required capability stays a candidate.
*   Any other spec goes to a new `excluded` list:
    `{"spec": "...", "missing": [{"capability": "vision", "value": "no" | "unknown"}]}`. The
    selection skill will forbid planner agents from passing `--capability` to `models set` or
    `models add`: they report excluded `unknown` models to the owner, who classifies them with
    the commands in the README, and choose among the remaining candidates.
*   Scoring, `recommendation` and `explore` run on the remaining candidates only.
*   When nothing remains, the result is `recommendation: null`, `reason:
    no_capable_candidates`, `candidates: []`, `explore: []`, `explore_reason:
    no_explorable_candidates` (or `complexity_not_explorable` at high complexity), plus the
    `excluded` list. This is a result, not an error, so the planner sees which capability blocked
    each model.
*   Without `--require`, `excluded` is `[]` and every other key is computed exactly as in Phase 1.

The prior used for scoring (`prior_for`) stays computed over all executor records, not only the
remaining candidates. Filtering must not move the scores of models that pass the filter.

### Phase 3: Hugging Face snapshot

**Three files, three owners.**

| File | Written by | Read by | Content |
| --- | --- | --- | --- |
| `scripts/hf_model_map.json` | the owner, by hand | the fetch script | `schema_version: 1` and, per chanchi `agent:model`, the Hub repo and `match_quality` (`exact`, `family`, `proxy`) |
| `src/chanchi/data/hf_snapshot.json` | the fetch script, committed after review | `src/chanchi/hfsignals.py` | raw Hub rows per mapped model |
| `src/chanchi/hfsignals.py` (constants at the top) | developers | `hfsignals.py`, `scoring.explain()` | benchmark → signal mapping, task type → signal mapping, thresholds |

The constants stay out of `taxonomy.py` so Phase 3 can be removed by deleting its own files and
reverting its edit to `scoring.py`.

`match_quality` values, set by the owner:

*   `exact`: the Hub repo is the same model and version opencode serves (quantization may differ).
*   `family`: same model line, different release or training stage (for example a `-preview` or
    `-RL` repo).
*   `proxy`: a related but different model, kept for reference only. It never gets a signal.

Initial map (16 Hub repos found on 2026-11-17, 17 catalog entries; all catalog names have agent
`opencode`):

| Catalog model | Hub repo | match_quality |
| --- | --- | --- |
| `opencode-go/deepseek-v4.1-flash` | `deepseek-ai/DeepSeek-V4.1-Flash` | exact |
| `opencode-go/glm-5.2` | `zai-org/GLM-5.2` | exact |
| `opencode-go/glm-5.3` | `zai-org/GLM-5.3` | exact |
| `opencode-go/glm-5.3-flash` | `zai-org/GLM-5.3-Flash` | exact |
| `opencode-go/hy3` | `tencent/Hy3` | exact |
| `opencode-go/hy4` | `tencent/Hy4-preview` | family |
| `opencode-go/kimi-k2.7-code` | `moonshotai/Kimi-K2.7-Code` | exact |
| `opencode-go/kimi-k3` | `moonshotai/Kimi-K3` | exact |
| `opencode-go/longcat-2.0` | `meituan-longcat/LongCat-2.0` | exact |
| `opencode-go/mimo-v2.5` | `XiaomiMiMo/MiMo-V2.5` | exact |
| `opencode-go/mimo-v2.5-pro` | `XiaomiMiMo/MiMo-V2.5-Pro` | exact |
| `opencode-go/mimo-v2.6-flash` | `XiaomiMiMo/MiMo-V2.6-Flash-RL` | family |
| `opencode-go/mimo-v2.6-pro` | `XiaomiMiMo/MiMo-V2.6-Pro-RL` | family |
| `opencode-go/minimax-m3` | `MiniMaxAI/MiniMax-M3` | exact |
| `opencode-go/minimax-m3#thinking` | `MiniMaxAI/MiniMax-M3` | family |
| `opencode-go/minimax-m3.1-flash` | `MiniMaxAI/MiniMax-M3.1-Flash` | exact |
| `opencode-go/step-5-preview` | `stepfun-ai/Step-5-Preview` | exact |

Unmapped: qwen3.7-plus and qwen3.8-max (closed API models), qwen3.8-flash (only third-party
quantizations on the Hub), kimi-k3.1-pro and deepseek-v4-pro (no matching repo). The script
does not read the catalog. A map key that matches no catalog model never meets a candidate, so
it has no effect; the owner checks the map keys against `chanchi models list --all` before each
refresh (README, "Refreshing Hugging Face signals").

**Branches.** Phases 1 and 2 are built on one branch and merged before Phase 3 starts, so the
real database is at migration 003 before any fetch and the owner can set capabilities. Phase 3
is built on its own branch from main, after the merge of Phases 1-2 has migrated the real
database and the owner has registered the missing opencode models; the map uses the registered
names.

**Drop criterion (decided before building it).** After the first `--write`, count the catalog
opencode models that get a value for at least one of the three signals. If fewer than 8 do, the
Phase 3 branch is discarded unmerged (its `scripts/`, snapshot, `hfsignals.py`, tests and its
`scoring.py` edit never reach main), and Phases 1-2 stay alone (Alternative M). With the rows observed on
2026-11-17, every one of the 17 mapped entries reports at least one counted benchmark (deep-swe,
SWE-bench Pro, terminal-bench-2.1 or Toolathlon), so the expected count is 17; the criterion fails
only if the mapping or the Hub data changes materially.

**Snapshot schema (version 1).**

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-17T20:00:00Z",
  "models": {
    "opencode:opencode-go/glm-5.3": {
      "hf_repo": "zai-org/GLM-5.3",
      "match_quality": "exact",
      "fetched_at": "2026-11-17T20:00:00Z",
      "last_error": null,
      "pipeline_tag": "text-generation",
      "eval_rows": [
        {"dataset_id": "datacurve/deep-swe", "task_id": "deep_swe", "value": 66.9,
         "date": "2026-08-28T15:22:14.000Z", "source_name": "Model Card",
         "source_url": "https://huggingface.co/zai-org/GLM-5.3", "verified": false,
         "pull_request": null}
      ]
    }
  }
}
```

Only raw rows are stored. The snapshot keeps every row the Hub returns for a mapped repo, not only
mapped benchmarks, so a mapping change needs no new fetch.

**Hub response.** Observed on 2026-11-18 for `zai-org/GLM-5.3`, without a token, trimmed to two
of its eleven rows:

```json
{
  "_id": "...", "id": "zai-org/GLM-5.3", "pipeline_tag": "text-generation",
  "evalResults": [
    {"filename": ".eval_results/deep-swe.yaml", "verified": false,
     "data": {"dataset": {"id": "datacurve/deep-swe", "task_id": "deep_swe"}, "value": 66.9,
              "date": "2026-08-28T15:22:14.000Z",
              "source": {"url": "https://huggingface.co/zai-org/GLM-5.3", "name": "Model Card"}}},
    {"filename": ".eval_results/terminal-bench-4.1.yaml", "verified": false,
     "data": {"dataset": {"id": "harborframework/terminal-bench", "task_id": "terminalbench_4_1"},
              "value": 41.2, "date": "2026-11-03", "notes": "...",
              "source": {"url": "https://www.tbench.ai/", "name": "...", "user": "harborframework"}},
     "pullRequest": 35}
  ]
}
```

Field mapping, from each element of `evalResults` to an `eval_rows` row: `data.dataset.id` →
`dataset_id`, `data.dataset.task_id` → `task_id`, `data.value` → `value`, `data.date` → `date`
(stored as given: the Hub mixes `2026-08-31` and `2026-08-28T15:22:14.000Z`), `data.source.name`
→ `source_name`, `data.source.url` → `source_url`, `verified` → `verified`, `pullRequest` →
`pull_request` (the number, or `null` when absent). Other fields (`filename`, `notes`,
`source.user`) are not stored. An element with no `data` (the Hub returns `{"filename": ...,
"error": "Invalid YAML ..."}` for a broken file) or whose `value` is not a number is skipped.
`pipeline_tag` comes from the top level and may be absent (`null`).

A row with `pull_request` set comes from an open pull request on the model repo, which anyone
can open. GLM-5.2's two terminal-bench-2.1 rows (81 and 82.7) are of this kind. These rows count
like the others, because every Hub row is unverified and only orders `explore`; each emitted
benchmark shows `pull_request: true` so the planner and the owner can see it (Risks and Limits).

**Fetch script (`scripts/fetch_hf_benchmarks.py`).**

*   Stdlib only (`urllib.request`, `json`, `argparse`). It is not imported by the package, does
    not import `chanchi`, and never reads or writes the database: its inputs are the map and the
    Hub, its output is the snapshot.
*   Directory guard: it stops unless the current directory equals the repository root, taken as
    the script's own parent's parent (`Path(__file__).resolve().parents[1]`). The error names
    that directory. It prevents writing a snapshot from another project's directory; it is not a
    security boundary.
*   `HF_TOKEN` is optional. When set, it is sent as `Authorization: Bearer`. It is never printed,
    logged or written. User-Agent is the generic `chanchi-hf-fetch`.
*   Request per repo: `GET https://huggingface.co/api/models/<repo>?expand[]=evalResults&expand[]=pipeline_tag`,
    20-second timeout, sequential, no retries.
*   Dry run by default: prints a JSON summary (per model: rows fetched, rows changed, errors;
    plus `vision_candidates`, below). `--write` writes the snapshot of the checkout the script
    runs in, sorted keys, 2-space indent, so the git diff is reviewable. Run in a worktree, it
    reaches other projects only when the branch is merged.
*   On any non-200 status (a repo that does not exist answers 401 when no token is sent, 404
    otherwise; 429 is a rate limit), timeout or bad JSON for one repo: keep that model's previous
    `eval_rows`,
    `pipeline_tag` and `fetched_at`, set `last_error`, continue with the next repo, and exit with
    code 1 at the end if any repo failed.
*   Vision candidates: the summary's `vision_candidates` lists every mapped `agent:model` whose
    `pipeline_tag` is `image-text-to-text`. The owner compares the list with `chanchi models
    list`, checks the provider's page, and sets `vision` with the installed `chanchi`.

**Signal derivation (`src/chanchi/hfsignals.py`, read side, pure functions).**

*   Benchmark → signal mapping in the constant `HF_BENCHMARKS` in `hfsignals.py`: per dataset
    id, its signal, allowed `task_id` values and unit (`percent`, range 0-100). Rows outside the range are dropped, and so are values
    in (0, 1] on a `percent` benchmark, which are fractions reported in the wrong unit. Rows whose
    `task_id` is not allowed are ignored. The allowed `task_id` values for SWE-bench_Verified and
    SWE-bench_Multilingual are read from the first real snapshot and written into `hfsignals.py`
    before the Phase 3 branch merges; until then those two benchmarks count for nothing:
    *   `swe`: `datacurve/deep-swe` (`deep_swe`), `ScaleAI/SWE-bench_Pro` (`SWE_Bench_Pro`),
        `SWE-bench/SWE-bench_Verified`, `SWE-bench/SWE-bench_Multilingual`;
    *   `terminal`: `harborframework/terminal-bench-2.1` (`terminalbench_2_1`) only;
    *   `tool-use`: `hkust-nlp/Toolathlon` (`toolathlon_verified`), `claw-eval/Claw-Eval`
        (`general`).
*   Task type → signal: `bugfix`, `refactor`, `business-logic`, `api-endpoint` → `swe`;
    `infra-config-ci` → `terminal`; `integration` → `tool-use`. Every other task type, including
    custom ones, has no signal. (The per-type weights proposed in the brief are dropped: with one
    signal per task type they cannot change the order. They belong to the deferred score offset.)
*   Canonical value: per Hub repo, benchmark and task id, keep the rows with the latest date and
    take their mean (GLM-5.2 has two terminal-bench-2.1 rows on the same date: 81 and 82.7 →
    81.85). The date of a row is the first 10 characters of `date` when they parse as
    `YYYY-MM-DD`; a row without such a date is ignored.
*   Peers: the distinct Hub repos in the snapshot, with `match_quality` `exact` or `family`, that
    have a canonical value for that benchmark. Two catalog entries that share a repo
    (`minimax-m3` and `minimax-m3#thinking`) count as one peer and get the same percentile.
    `proxy` entries are neither peers nor ranked: their `external_signals` has `value: null` and
    lists their rows for counted benchmarks with `peers: null`, and they sort as no signal. A
    benchmark with fewer than `HF_MIN_REPORTERS = 5`
    peers is ignored. With the data seen during ideation, Claw-Eval has 6 result rows from 3
    models; all 3 report task `general`, and 3 is fewer than 5, so it is ignored. Toolathlon has
    5 models and counts. Rows from different fetch dates share one peer set;
    `external_signals.fetched_at` shows each model's date.
*   Percentile of a model on a benchmark: `(peers strictly below + 0.5 × (peers equal − 1)) /
    (N − 1)`, a value from 0 to 1, where `N` is the number of peers including the model's own
    repo and "peers equal" counts repos with the same canonical value, including its own. The
    output field `peers` is this `N`.
*   Signal value: mean of the model's percentiles over the counted benchmarks of that signal. No
    counted benchmark → no signal.
*   A missing or unreadable snapshot file gives no signals and no error, so Phases 1 and 2 keep
    working. So that a bad snapshot is never silent, every `recommend` result carries
    `explore_signal_source`: `snapshot`, `missing` (no file, or a file that cannot be read or
    parsed) or `schema_mismatch` (a `schema_version` other than 1, which gives no signals).
    It also carries `explore_signal_generated_at` (the snapshot's `generated_at`, `null` unless
    the source is `snapshot`), so the planner and the owner can see the snapshot's age.
    A test parses the committed snapshot when it exists and asserts `schema_version == 1`.
*   The snapshot is loaded from the module constant `hfsignals.SNAPSHOT_PATH`, set to
    `importlib.resources.files("chanchi") / "data" / "hf_snapshot.json"`, the same way
    `db.template_path()` finds `template.db`. Tests replace the constant, so no test reads the
    committed snapshot by accident.

**Ordering with signals.** Phase 3 inserts one key into the Phase 1 sort, after `cost_tier` and
before `n_task_type`: the signal bucket, highest first, the signal value (0 to 1) cut into
quarters (`min(3, floor(value * 4))`). A spec with no signal sorts after bucket 1 and before
bucket 0, because a bottom-quartile result is weak evidence against a model, while no result is
no evidence either way. Cost stays before the signal because the signal is unverified and
measured on a Hub checkpoint, not on the variant opencode serves. With no snapshot every spec
has no signal and the order is the Phase 1 order.

**Explore entries with a signal.**

```json
"external_signals": {
  "signal": "swe", "value": 0.82, "hf_repo": "zai-org/GLM-5.3", "match_quality": "exact",
  "fetched_at": "2026-11-17T20:00:00Z", "verified": false,
  "benchmarks": [{"dataset_id": "datacurve/deep-swe", "task_id": "deep_swe", "value": 66.9,
                  "date": "2026-08-28", "pull_request": false, "peers": 12}]
}
```

`external_signals` appears only in `explore` entries, never in `candidates`, so a benchmark number
is never shown next to an audit score. It is `null` when the model is unmapped or the requested
task type has no signal. When the task type has a signal and the model is mapped, it is an
object; its `value` is `null`, and it sorts as no signal, for `proxy` entries and for a mapped
model with no counted benchmark (all its benchmarks below `HF_MIN_REPORTERS`, or a failed fetch
with no rows). In the last case `benchmarks` is `[]`.

Hub rows are written by model authors and third parties, so their free text is untrusted and
could carry instructions aimed at the agents that read `recommend` output. `external_signals`
therefore emits only allowlisted fields: `signal`, `value`, `hf_repo` and `match_quality` from the
owner's map, `fetched_at`, `verified`, and per benchmark `dataset_id` and `task_id` (only values
listed in `HF_BENCHMARKS`), numeric `value`, `date` (the first 10 characters, which parse as
`YYYY-MM-DD`), `pull_request` (`true` or `false`) and `peers`. `source_name`, `source_url` and any other Hub field stay in the snapshot for the
owner's review and are never emitted.

**Network boundary test.** `tests/test_no_network.py` parses every module under `src/chanchi`
with `ast` and fails if any imports a network module (`urllib.request`, `http.client`, `socket`,
`ssl`, `urllib3`, `requests`) through `import`, `from ... import` (including `from urllib import
request`), or `importlib.import_module` with a literal name. `subprocess` is allowed only in
`projects.py`, which runs `git`. The test checks imports, not behaviour, so the claim is that the
package imports no network module.

### Cross-cutting changes

*   `scoring.explain()` documents the exploration rule, `--require` and the signal derivation.
*   `render.py` needs no change: it renders any new key generically, and `capabilities` is a flat
    string so the models table keeps its layout. CLI tests check that `explore`, `excluded` and
    the `show` `exploration` block appear in `--format text`.
*   README: the "Local only" bullet becomes: "the `chanchi` package imports no network module; one
    maintainer script in `scripts/` fetches public benchmark metadata into a committed file".
    New sections for capabilities, exploration and refreshing the snapshot.
*   Design spec `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md`: section 1.3
    gets the same wording; section 3 (module table) a `hfsignals` row; section 4.3 the
    capability enums; section 5 the new table; section 6.6 steps for `--require`, `explore` and
    `excluded`; section 7 the new flags; section 8.1 the exploration budget; section 10
    ("Template integrity") `model_capabilities` among the empty tables.
*   `skills/chanchi-model-selection/SKILL.md`, the full list of skill changes:
    *   "Before you start", item 2: list in `--available` every effort of a model that the human
        made available;
    *   step 3: `--require` when the session needs screenshots or images;
    *   step 4: `explore`, `explore_reason`, `deprioritized` (non-null means "try only if
        nothing better is offered"), `excluded` and `no_capable_candidates`,
        `external_signals` (unverified, ordering only, never audit evidence);
    *   step 4, choosing: replace "With `null`, choose by judgement" with "prefer an `explore`
        spec when the budget allows, otherwise choose by judgement";
    *   step 4, budget: at most `allowed` explore sessions per change, never in a blocking
        session, `--tags explore` on every attempt including retries, a missed tag fixed with
        `session update --tags <existing tags>,explore`, every explore session of a model on the
        effort of the `explore` spec, and `chanchi show <change>` as the check;
    *   step 4, the existing weak-evidence line (`complexity` or `global` level) is extended: at
        `high` complexity, a `task_type` level is weak evidence too;
    *   step 5: the protocol-line suffix `· explore: <spec>`;
    *   catalog maintenance and "Before you start", item 3: planners never pass `--capability`
        to `models set` or `models add`; they report excluded `unknown` models to the owner. The
        existing `--cost` and `--active` maintenance on the human's request stays.

    The fetch script is never mentioned in any skill. Phase assignment of these changes: the
    Phase 3 items are the `external_signals` paragraph in the skill, the README "Refreshing
    Hugging Face signals" section and the "Local only" wording (README and design spec section
    1.3), the signal derivation in `scoring.explain()`; everything else in
    this list ships with Phases 1-2. If Phase 3 is dropped, none of its items reach main.

### Rollout and rollback

*   Phase 1 has no schema change. Rollback is a code revert.
*   Phase 2 adds migration 003 and a regenerated `template.db` (`uv run chanchi db migrate
    --template`, in the same commit). The synthetic migration numbered 3 in `tests/test_db.py`
    (`003_add_probe.sql`) is renumbered to 4 so it does not collide. Migrations only go forward.
    Migration 003 becomes irreversible the first time the main checkout contains it and any
    project runs `chanchi` against the real database, which happens on the first `chanchi` call
    after the merge of Phases 1-2. From then on the file is never reverted, because a revert
    would make every project fail with `schema_too_new` (the error chanchi raises when the
    database is at a higher migration version than the installed code knows). Before the merge,
    Phase 2 code exists only in worktrees whose `CHANCHI_DB` is a scratch file or a copy. To roll
    back after the merge, revert the read and write code and leave the table in place. Before migrating, chanchi copies the database to `chanchi.db.bak-v2` (it
    backs up before every migration and keeps the three latest).
*   Phase 3 adds files and edits `scoring.py`, on its own branch. Rollback: delete the snapshot;
    `explore_signal_source` becomes `missing` and `explore` orders as in Phase 1 (rule 3).

## Alternatives Considered

The owner, as the author, made each decision below during ideation; the brief records them in
[Key Decisions & Staging for Next Steps](./explore-capabilities-hf.brief.md#key-decisions--staging-for-next-steps).

### Alternative A: A fourth cost tier from Hugging Face per-token prices

*   **Pros**: Separates models priced above Opus (for example `claude:fable-5-1`, whose catalog
    note says the scale ends at 3).
*   **Cons**: Needs a table rebuild migration (the `cost_tier` CHECK cannot be altered in SQLite).
    Hub prices are per token, while the owner pays fixed monthly plans.
*   **Reason for Rejection**: Rejected by author: a tier derived from per-token prices would
    misrank fixed-plan costs (see Cons).

### Alternative B: Orchestrator and auditor role scores from benchmarks

*   **Pros**: Would answer "who can orchestrate or audit" before any planner sessions exist.
*   **Cons**: No observed Hub benchmark measures orchestration or auditing.
*   **Reason for Rejection**: Rejected by author: no benchmark measures these roles. They stay
    audit-only.

### Alternative C: Replace the population prior with a benchmark percentile prior

*   **Pros**: One change in the scoring path. Benchmark data would affect every candidate.
*   **Cons**: Candidates with `n < 3` stay ineligible (`scoring.py:470`), so it cannot recommend an
    unaudited model. Percentiles (median 50) and audit priors (about 85-100, default 70) are on
    different scales: 3 sessions averaging 95 with a percentile prior of 20 give 57.5, enough to
    decide the pick inside the 5-point window. `smoothed()` is shared by planner and dimension
    stats.
*   **Reason for Rejection**: Rejected by author: it does not reach the goal, and the scale mismatch
    would let unverified data decide recommendations.

### Alternative D (deferred): A bounded benchmark offset on the prior now

*   **Pros**: A small, capped nudge that the existing smoothing fades out as audits accumulate.
*   **Cons**: Adds constants (cap, coverage shrink) with no evidence yet that Hub benchmarks predict
    audit scores for opencode-served variants.
*   **Status**: Deferred by author: reconsidered only after about 10 or more audited
    sessions of opencode models, if `external_signals` correlate with audit scores (see Future
    Improvements).

### Alternative E: Let unaudited candidates compete for `recommendation`

*   **Pros**: No new output field. Planners already read `recommendation`.
*   **Cons**: Under the cheapest-in-window rule (`scoring.py:476`), an unaudited cost-tier-1 model
    could displace a proven model, including at high complexity.
*   **Reason for Rejection**: Rejected by author: exploration must be explicit, separate and
    bounded, so the evidence-based pick stays trustworthy.

### Alternative F: Count benchmark data as pseudo-sessions toward confidence

*   **Pros**: Unaudited models with good benchmarks would reach `low` confidence sooner.
*   **Cons**: Mixes unverified author-reported numbers into the gate that decides eligibility.
*   **Reason for Rejection**: Rejected by author: confidence must count audited sessions only.

### Alternative G: Thirteen per-task-type benchmark priors

*   **Pros**: Every task type would get its own number.
*   **Cons**: Six task types would draw on one SWE-bench-style signal. SWE-bench grades fixes against
    hidden tests and does not measure writing tests. UI, docs, schema and architecture types have
    no matching benchmark.
*   **Reason for Rejection**: Rejected by author: false precision. Replaced by three signals
    (`swe`, `terminal`, `tool-use`), each mapped to the task types it plausibly reflects.

### Alternative H: Derive `--require vision` from `pipeline_tag` only

*   **Pros**: No owner input needed for open models.
*   **Cons**: Closed models (Claude, Gemini) have no Hub repo, Step-5-Preview has no tag, and
    opencode may serve a vision-tagged checkpoint as text only.
*   **Reason for Rejection**: Rejected by author: capabilities are owner-set catalog data. The Hub
    tag only produces a list of vision candidates (`vision_candidates`) that the owner checks.

### Alternative I: Store Hub rows in new global database tables

*   **Pros**: Queryable with SQL. Fits the write-side modules.
*   **Cons**: Another forward-only migration, template regeneration, and tables only the script
    fills. A script writing SQL directly would skip bootstrap, backup and version checks.
*   **Reason for Rejection**: Rejected by author: a committed snapshot reaches every project
    through the editable install with no migration, and every refresh is reviewed as a git diff in
    a worktree before it is merged into the main checkout.

### Alternative J: Capabilities as a JSON column on `models`

*   **Pros**: Simplest migration (`ALTER TABLE ADD COLUMN`). New capabilities and new values need
    no migration. `models list` already returns the whole row.
*   **Cons**: Data about each capability (`set_at` now, perhaps provenance later) needs nested
    JSON. `--require` filtering and capability counts happen in Python after loading every row.
*   **Reason for Rejection**: Rejected by author: a table keeps per-capability data in plain
    columns, can gain a column later with `ADD COLUMN`, and answers `--require` with a join.

### Alternative K: Capabilities table with CHECK constraints on values

*   **Pros**: The database rejects invalid values.
*   **Cons**: Adding a value (for example `partial`) requires a table rebuild migration, the same
    problem that made a fourth cost tier expensive.
*   **Reason for Rejection**: Rejected by author: values are validated in `taxonomy.py`, like the
    rest of chanchi's enums, plus a test that checks every stored value.

### Alternative L: Required `HF_TOKEN`

*   **Pros**: Higher Hub rate limits and access to gated repos.
*   **Cons**: Every observed request worked without a token. A required token adds a secret to
    handle for no current benefit.
*   **Reason for Rejection**: Rejected by author: the token is optional and read only from the
    environment.

### Alternative M (fallback, not rejected): No network at all

*   **Pros**: No script, no snapshot, no change to the "local only" principle. Exploration alone
    reaches Goal G1.
*   **Cons**: The order among unaudited models would be by cost only, with no outside information.
*   **Status**: Kept as the fallback by author, not rejected. Phase 3 is optional, and Phases 1-2
    work without it. Phase 3 is dropped by the numeric criterion in the Technical Plan (fewer than
    8 catalog opencode models with any signal after the first fetch).

### Alternative N (prevention deferred): Exploration budget enforced by chanchi

*   **Pros**: A planner could not exceed the budget.
*   **Cons**: `recommend` does not know the change. Prevention would need a `--change` flag on
    `recommend`, for a problem not yet observed.
*   **Status**: Prevention deferred by author. Detection is in scope: `chanchi show <change>`
    reports `exploratory`, `allowed` and `over_budget` from existing columns (Technical Plan,
    Phase 1, "Budget"). Add prevention if those reports show planners exceeding the budget.

### Alternative O: Fetch as a hidden `chanchi` subcommand guarded by the working directory

*   **Pros**: One entry point. Could reuse `db.open_operational()` and the CLI's JSON errors.
*   **Cons**: Puts network code inside the package every project runs, which breaks Goal G6 and
    the `ast` no-network test. A hidden subcommand is still reachable from any project.
*   **Reason for Rejection**: Rejected by author: network code stays in `scripts/`, outside the
    package.

### Alternative P: Randomized exploration (epsilon-greedy or Thompson sampling)

*   **Pros**: Standard way to balance trying new options against using proven ones. Spreads trials
    across all unaudited models over time.
*   **Cons**: chanchi only suggests; the planner decides. A random output gives different answers to
    identical calls, which confuses agents reading the JSON and makes tests nondeterministic.
*   **Reason for Rejection**: Rejected by author: `explore` is deterministic. The budget in the
    skill plays the role of epsilon.

### Alternative Q: Explore only models with fewer than 3 sessions in total

*   **Pros**: Reuses the existing `confidence == insufficient` value with no new count. Fewer
    models are explorable.
*   **Cons**: A model with audits on other task types is never explored on a new one, so the
    owner cannot learn whether a model used for `bugfix` handles `ui-component`.
*   **Reason for Rejection**: Rejected by author: exploration counts sessions of the requested
    task type (Technical Plan, Phase 1, rule 1).

## Risks and Limits

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Explore sessions spend real project work on unproven models | Rejected work and rework in the changes that explore | Budget of `max(1, floor(n / 4))` sessions per change (0 when `n` is 1), never a blocking session, low and medium complexity only, deprioritized specs sort last, one model finished before the next (Phase 1) |
| Planners ignore the budget | More exploration than intended | Exact count of sessions tagged `explore` and `over_budget` in `chanchi show` (Phase 1, "Budget"); prevention deferred (Alternative N) |
| Known leak: explored models reach `recommendation` at `high` complexity on easier data | A cheap model is picked for hard work on weak evidence | Skill rule on `level` at high complexity and a test pinning the behaviour (Phase 1, "Known leak") |
| Editable install: the main checkout's working tree is live for every project | An unreviewed change, migration or snapshot reaches every project | All work in worktrees with `CHANCHI_DB` set; the main checkout only receives merges (The Problem; Technical Plan, "Rollout and rollback") |
| One honesty incident on a model with little data | The model could stop being explored on every task type | Below 3 sessions a red flag sets `deprioritized: "red_flag_low_data"` on the model's kept spec, whichever effort rule 4 keeps, and sorts it last; the model is excluded once the flag rests on 3 or more sessions (Phase 1, rule 1) |
| A planner agent classifies capabilities itself to pass `--require` | Wrong `vision` values in the shared catalog | The selection skill forbids planners from passing `--capability` to `models set` or `models add`; the commands appear only in the README, for the owner (Phase 2, "Recommend with `--require`") |
| Untrusted Hub text reaches agents through `recommend` | Prompt injection into planners in every project | `external_signals` emits only allowlisted fields (Phase 3, "Explore entries with a signal") |
| Snapshot goes stale | `explore` ordered on old results | `explore_signal_generated_at` in every result and `fetched_at` in each `external_signals` (Phase 3, "Signal derivation") |
| Hand-written map drifts when opencode renames or re-versions a model | Wrong or missing signals | The owner checks map keys against `chanchi models list --all` before each refresh; an unmatched key has no effect; `match_quality` set per entry; signals only order `explore` (Phase 3, "Initial map") |
| Rows from open pull requests, which anyone can open on a model repo | A third party moves a model up in `explore` | Rows only order `explore` within a cost tier and never change scores; `pull_request: true` is shown per benchmark; the owner reviews the snapshot diff before merging (Phase 3, "Hub response") |
| Unverified, author-reported benchmarks on Hub checkpoints | Misleading order | Signals never change scores; cost sorts first; `verified: false` shown (Phase 3, "Ordering with signals"); drop criterion for Phase 3 (Phase 3, "Drop criterion") |
| Scale: about 16 mapped repos and small peer sets | Percentiles move a lot when one model is added | `HF_MIN_REPORTERS = 5`; quartile buckets instead of raw values; the map stays hand-reviewed (Phase 3, "Signal derivation") |

## Non-Functional Requirements

*   **Security and privacy.** `HF_TOKEN` is optional, read only from the environment by the fetch
    script, sent only to `huggingface.co`, and never printed, logged or written. Requests carry a
    generic User-Agent and no user or project data. The `chanchi` package imports no network
    module (checked by `tests/test_no_network.py`). Hub free text is untrusted: `recommend`
    emits only allowlisted `external_signals` fields, never `source_name`, `source_url` or any
    other Hub field.
*   **Performance.** `recommend` loads the snapshot once per call (a JSON file of a few hundred
    rows) and computes percentiles in memory. The added cost is expected to be a few
    milliseconds; add a cache only if a measurement shows otherwise. The fetch script makes one
    request per mapped repo (about 16), sequentially.
*   **Rollout and rollback.** See Technical Plan, "Rollout and rollback". The only irreversible step
    is migration 003 running against the real database, which first happens on the first
    `chanchi` call after it is merged into the main checkout.
*   **Backward compatibility.** All JSON changes are new keys. Without `--require`,
    `recommendation`, `reason`, `window` and `candidates` are identical to today, with or without
    a snapshot.

## Future Improvements

*   **Bounded benchmark offset on scores (deferred).** After about 10 or more audited sessions of
    opencode models, compare each model's `external_signals` value with its audit mean per task
    type. Only if they correlate, add a capped offset to the prior in `recommend()`.
*   **Budget prevention.** If `show` reports planners exceeding the exploration budget, add a
    `--change` flag to `recommend` that withholds `explore` when the change is over budget
    (Alternative N).
*   **More capabilities.** Add values to `taxonomy.CAPABILITIES` (for example `computer-use`) when a
    planner needs to filter on them. No migration is needed.
*   **A reserved slot for models without a signal.** If audits show that closed and unmapped
    models are rarely explored on task types that have a signal, reserve one `explore` slot for
    the best-ranked spec with no signal.
*   **More signals.** Add a benchmark to a signal only when at least `HF_MIN_REPORTERS` mapped models
    report it.

## Additional Resources

*   [explore-capabilities-hf.brief.md](./explore-capabilities-hf.brief.md) (revision 3), the
    brainstorm brief this design follows.
*   [chanchi model auditor design](../superpowers/specs/2026-10-18-chanchi-model-auditor-design.md),
    sections 1.3, 6.6 and 8.1.
*   Hugging Face Hub model API, observed on 2026-11-17 and 2026-11-18 without a token:
    `GET https://huggingface.co/api/models/<repo>?expand[]=evalResults&expand[]=pipeline_tag`.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

The work runs in three executor sessions, S1 to S3 (`chanchi-hf-s1`, `chanchi-hf-s2`,
`chanchi-hf-s3`), and two owner steps. Phases 1 and 2 (S1, S2) are built on branch
`feat/explore-capabilities` and merged to main after S2 is audited and the Goal G2 check passes.
Phase 3 (S3) is built on branch `feat/hf-signals`, created from main after the second owner step,
and merged only if it passes the drop criterion.

Each executor session runs in its own git worktree under `.claude/worktrees/<session>` (gitignored)
with `CHANCHI_DB` pointing to a scratch file. Inside a worktree, chanchi is always run as `uv run
chanchi ...`, which uses the worktree's code. A bare `chanchi` is the global editable install of
the main checkout: it would run main's code and could rewrite main's `template.db`. Nobody runs
`uv tool install` from a worktree, because that would point every project's `chanchi` at the
worktree. Executors do not commit. The planner audits each session, records it with the
`chanchi-session-audit` skill, and commits with Conventional Commits.

### Execution sessions (agy)

agy is a coding-agent CLI, available through the owner's Google AI Pro plan, and herdr is the
terminal multiplexer the owner runs agents in; each executor gets its own herdr pane next to the
planner's. In an agy model name such as `gemini-4-hydrogen-high`, `-high` is part of the model
name (agy exposes one model per reasoning level); the chanchi spec repeats it as the effort,
`agy:gemini-4-hydrogen-high:high`, and the two must match.

Executors are launched with `herdr agent start <session> --kind agy --pane <pane-id> -- --agent
executor --model gemini-4-hydrogen-high --effort high --dangerously-skip-permissions`. The owner
chose `gemini-4-hydrogen-high` as the successor of `gemini-3.8-flash-high`. Before each session
the planner re-runs `chanchi recommend` and records its output in the protocol line.

| Session | Phase | Task type, complexity | agy model | Why |
| --- | --- | --- | --- | --- |
| owner step 1 | - | - | the owner | Before S1: `chanchi models list` shows `agy:gemini-4-hydrogen-high` with effort `high`; if not, `chanchi models add --agent agy --model gemini-4-hydrogen-high --cost <tier> --efforts high` (installed `chanchi`, no `CHANCHI_DB`). Without it `session start` fails with `unknown_model` |
| S1 | 1 | business-logic, medium | `gemini-4-hydrogen-high` | Owner's choice: successor of `gemini-3.8-flash-high` (the `recommendation`, 97.88 over 5 sessions). Hydrogen has 0 sessions, so this is an explore session |
| S2 | 2 | db-schema-migration, medium | `gemini-4-hydrogen-high` | `recommendation` is null: `agy:gemini-3.8-flash-high:high` is red-flagged for honesty on its data for this request (`level: complexity`). Red flags are computed per spec on that spec's sessions; Hydrogen is a different model with 0 sessions, so it has none. Explore session |
| owner step 2 | - | - | the owner | After Phases 1-2 are merged (section "Owner step 2" below) |
| S3 | 3 | integration, medium | `gemini-4-hydrogen-high` | Same model for all three sessions, so its `global` confidence reaches `low` (3 audited sessions) by the end of the change |

**Owner override of the exploration budget.** All three sessions are explore sessions, so this
change uses 3 of 3 where the budget allows 1, and S1 and S2 block later sessions. The owner chose
this on 2026-11-17 to evaluate Hydrogen as the successor of `gemini-3.8-flash-high`. Each session
is started with `--tags explore`. Each protocol line records `· explore:
agy:gemini-4-hydrogen-high:high`, followed by a one-off free-text `· reason: owner override
(successor evaluation)` (the skill's existing "If you deviate, add `· reason: <why>`").

Mitigations, because S2 writes the only irreversible artifact (migration 003) on the task type
where the predecessor is red-flagged for honesty:

*   The planner audits Hydrogen sessions with extra attention to honesty incidents (unverified
    claims of passing tests, skipped steps) and re-runs `uv run pytest` itself.
*   Before committing S2, the planner reads `003_model_capabilities.sql` line by line against the
    Technical Plan and confirms that the template drift test in `tests/test_db.py` passes.

Each session ends with `uv run pytest` passing in its worktree. A session never starts before the
previous one is audited and committed.

### Target Files to Create/Modify

In test descriptions, `glm-5.3:low` is short for `opencode:opencode-go/glm-5.3:low`.

#### Phase 1 (session S1)

##### 1. `src/chanchi/taxonomy.py` (Modify)

*   **Type / Scope**: Python constants.
*   **Proposed Changes**: Add `EXPLORE_COMPLEXITIES = ("low", "medium")` and `EXPLORE_MAX = 3`.
    Add both to the dict returned by `taxonomy.describe()` (line 208) under an `exploration`
    key. Why: one place for the exploration constants, visible to agents through `taxonomy
    list`.

##### 2. `src/chanchi/scoring.py` (Modify)

*   **Type / Scope**: Read-side scoring.
*   **Proposed Changes**:
    *   In `recommend()`, while looping over specs, also compute per spec: `n_task_type` (the
        executor records of that exact `(agent, model, effort)` whose task type is the
        requested one, any complexity) and the mean score of those records (for weak start).
        Per `(agent, model)`, over the efforts listed in `--available` only: the highest
        `n_task_type`, and whether any listed spec is red-flagged at its own level (the level
        `recommend()` already picks for it) and on how many sessions that level rests. Keep
        these in a side map keyed by spec; do not add them to `candidates` entries, so
        `candidates` stays identical (Goal G2).
    *   After `recommendation` is chosen, build `explore` with a new private function
        `_build_explore(...)`, in this order:
        1.  If `complexity` is not in `taxonomy.EXPLORE_COMPLEXITIES`: `explore = []`,
            `explore_reason = "complexity_not_explorable"`, stop. This reason wins over every
            other, including after `--require` (Phase 2) removed every candidate.
        2.  Drop every model that, among its listed efforts, has an `n_task_type` of 3 or more,
            has a spec red-flagged at a level with 3 or more sessions, or is the
            `recommendation` model.
        3.  Keep one spec per remaining `(agent, model)`: the highest `n_task_type`, then the
            first as written in `--available`.
        4.  Set `deprioritized` on the kept spec: `"red_flag_low_data"` when any listed spec of
            the model is red-flagged at a level with fewer than 3 sessions; otherwise
            `"weak_start"` when its `n_task_type` is 1 or 2 and its mean is more than
            `RECOMMEND_WINDOW` points below `prior_for(records, task_type, None)`; otherwise
            `null`.
        5.  Sort with one key function `_explore_sort_key(entry)`: deprioritized last,
            `cost_tier` lowest first, `n_task_type` highest first, `spec`. Phase 3 adds the
            signal bucket to this function.
        6.  Take the first `EXPLORE_MAX`. `explore_reason` is `null` when the list has entries,
            otherwise `"no_explorable_candidates"`.

        Each entry has exactly the keys `spec`, `cost_tier`, `n_task_type` and `deprioritized`.
    *   Return `explore` and `explore_reason` right after `candidates`.
    *   In `show_change()`, add the `exploration` block described in the Technical Plan, Phase 1,
        "Budget": `sessions` (distinct `session_ref`), `exploratory` (distinct `session_ref`
        with at least one attempt whose `tags`, split on commas and stripped, contains exactly
        `explore`; not a `LIKE` match), `allowed` and `over_budget` (`null` until
        `changes.closed_at` is set).
    *   In `explain()`, add an `exploration` entry: the rule text, `EXPLORE_COMPLEXITIES`,
        `EXPLORE_MAX`, the threshold `CONFIDENCE_LOW_MIN`, and the sort order.
*   Why: implements Goal G1 without touching the eligibility code (Goal G2).

##### 3. `tests/helpers.py` (Modify)

*   **Type / Scope**: Test helper.
*   **Proposed Changes**: `Recorder.session()` gains `tags: str | None = None`, passed through to
    `record.start_session(..., tags=tags)`. Why: the budget tests need sessions tagged
    `explore`.

##### 4. `tests/test_scoring.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Existing tests unchanged. The new tests use a local fixture
    `explore_catalog` (built on `recorder`) that registers `opencode:opencode-go/glm-5.3` (cost
    tier 1, efforts `low`, `medium`, `high`), `opencode:opencode-go/kimi-k3` (tier 1, no
    efforts) and `opencode:opencode-go/minimax-m3` (tier 2, no efforts). They are not added to
    the shared `seeded` fixture, because `tests/test_catalog.py::test_add_and_list_models`
    expects the first `opencode` model to have no efforts. New tests:
    *   a model with 0 sessions appears in `explore` at low and medium complexity; at high,
        `explore` is `[]` with `explore_reason: complexity_not_explorable`;
    *   a model with 5 `bugfix` sessions and 0 `ui-component` sessions is in `explore` for
        `ui-component` and not for `bugfix`;
    *   the `recommendation` spec is never in `explore`, and when `glm-5.3:medium` is the
        `recommendation`, no GLM spec is;
    *   a candidate red-flagged at a level with 3 or more sessions is never in `explore`, and
        neither is any other listed effort of its model (`glm-5.3:high` flagged on 3 sessions
        removes `glm-5.3:low`);
    *   a model with 1 audited session and 1 honesty incident stays explorable with
        `deprioritized: "red_flag_low_data"` and sorts last; with `glm-5.3:low` flagged on 1
        session and a clean `glm-5.3:high` kept by rule 4, the kept `:high` entry carries
        `deprioritized: "red_flag_low_data"`, in either `--available` order; a spec that is both
        a weak start and low-data red-flagged reports `"red_flag_low_data"`;
    *   weak start: another model has 3 accepted `ui-component` sessions (base score 100) and
        GLM has 1 rejected `ui-component` session (base 0), so GLM's mean is far below the
        prior: GLM gets `deprioritized: "weak_start"` and sorts after `minimax-m3` with 0
        sessions and tier 2. Boundary: a mean exactly 5 points below the prior is not a weak
        start;
    *   deprioritized specs sort among themselves by `cost_tier`, then `n_task_type`, then
        `spec`;
    *   sort order: lower `cost_tier` first, then higher `n_task_type`, then `spec`; within tier
        1, GLM with 2 accepted `bugfix` sessions sorts before Kimi with 0;
    *   one spec per model: `glm-5.3:low` and `glm-5.3:high` both listed with no sessions →
        only the first as written appears; with 1 `bugfix` session at `:high` → `:high` is
        kept;
    *   split efforts: 2 audited `bugfix` sessions at `:low` and 1 at `:high` → the model stays
        explorable for `bugfix`; 3 at `:low` → it does not;
    *   only listed efforts count: with 3 `bugfix` audits at `glm-5.3:low` and only
        `glm-5.3:high` listed, GLM is explorable at `:high`;
    *   with `:high` listed, 3 `bugfix` audits at `:high` make every effort of that model
        non-explorable for `bugfix`;
    *   at most 3 entries, each with exactly `spec`, `cost_tier`, `n_task_type` and
        `deprioritized`;
    *   `no_explorable_candidates` when every candidate has 3 or more sessions of the task type;
    *   leak pin: a model with 3 low-complexity `bugfix` audits is eligible for `recommendation`
        at `high` complexity with `level: task_type` (documents today's behaviour);
    *   `show_change` budget on closed changes (`record.close_change`): 4 sessions with 2 tagged
        `explore` → `allowed: 1`, `over_budget: true`; 2 sessions with 1 tagged → `allowed: 1`,
        `over_budget: false`; 1 session with 1 tagged → `allowed: 0`, `over_budget: true`; a
        `session_ref` with a tagged first attempt and an untagged retry counts as exploratory
        once; tags `"ui,explore"` count and `"exploreish"` does not; an open change reports
        `over_budget: null`.
*   Golden-value test for Goal G2 (in `tests/test_scenario.py`, which owns the `history`
    fixture): before S1 starts, the planner runs, on main, `scoring.recommend(history.conn,
    task_type="ui-component", complexity="medium", available=[SONNET, FLASH, ARGON])` and the
    same call with `task_type="tests", complexity="low"`, and gives the executor the
    `recommendation`, `reason`, `window` and `candidates` values as literals. The test asserts
    the new code returns exactly those values.

##### 5. `tests/test_cli_integration.py` (Modify)

*   **Type / Scope**: CLI integration test.
*   **Proposed Changes**: One end-to-end `chanchi recommend` call asserting `explore` and
    `explore_reason` are present in JSON and rendered in `--format text`; one `chanchi show
    <change> --format text` call asserting the `exploration` block is rendered.

##### 6. `skills/chanchi-model-selection/SKILL.md` (Modify)

*   **Type / Scope**: Planner skill.
*   **Proposed Changes**: The Phase 1-2 items of the Technical Plan's skill list
    ("Cross-cutting changes"), placed as follows:
    *   "Before you start", item 2: list in `--available` every effort of a model that the human
        made available, so the effort that holds a model's audits competes for
        `recommendation`.
    *   Step 4: describe `explore`, `explore_reason` and `deprioritized` (non-null means try
        only if nothing better is offered).
    *   Step 4: replace "With `null`, choose by judgement" with "prefer an `explore` spec when
        the budget allows, otherwise choose by judgement".
    *   Step 4, budget: at most `max(1, floor(n / 4))` explore sessions in a change of `n`
        executor sessions when `n` is 2 or more, none when `n` is 1; never a session that blocks
        others; `--tags explore` on `session start` for every explore session and its retries;
        a missed tag fixed with `session update --tags <existing tags>,explore`; every explore
        session of a model on the effort of the `explore` spec; `chanchi show <change>` and its
        `exploration` block as the check.
    *   Step 4: extend the existing line "Treat data found at the `complexity` or `global` level
        as weak evidence" with: at `high` complexity, a `task_type` level is weak evidence too.
    *   Step 5: the protocol-line suffix `· explore: <spec>`.
*   Why: the skill is how planners act on the new fields.

##### 7. `tests/test_skills_content.py` (Modify)

*   **Type / Scope**: Content test.
*   **Proposed Changes**: Assert the selection skill mentions `explore`, `deprioritized`, the
    budget, `--tags explore`, the missed-tag fix, the protocol-line suffix, the effort-listing
    rule and the high-complexity weak-evidence rule.

##### 8. `README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: New section "Exploration" after "Everyday commands": what `explore`
    is, the budget, `--tags explore`, and `chanchi show <change>` as the check.

##### 9. `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` (Modify)

*   **Type / Scope**: Design spec.
*   **Proposed Changes**: Section 6.6: a step describing `explore`, its rules and
    `explore_reason`. Section 8.1: the budget.

#### Phase 2 (session S2)

##### 10. `src/chanchi/migrations/003_model_capabilities.sql` (Create)

*   **Type / Scope**: SQL migration.
*   **Proposed Changes**: The `CREATE TABLE model_capabilities` statement from the Technical Plan.
    No seed rows. Why: capability storage (decided: table without CHECK).

##### 11. `src/chanchi/data/template.db` (Modify, regenerated)

*   **Type / Scope**: Committed template database.
*   **Proposed Changes**: Regenerate with `uv run chanchi db migrate --template` in the worktree
    (never a bare `chanchi`, which would rewrite the main checkout's template). Committed in the
    same commit as file 10.

##### 12. `src/chanchi/taxonomy.py` (Modify)

*   **Type / Scope**: Python constants.
*   **Proposed Changes**: Add `CAPABILITIES = ("vision",)` and `CAPABILITY_VALUES = ("yes", "no",
    "unknown")`; report them in `describe()` under `capabilities` as `{"names":
    list(CAPABILITIES), "values": list(CAPABILITY_VALUES)}`, after `exploration`.

##### 13. `src/chanchi/catalog.py` (Modify)

*   **Type / Scope**: Catalog write and read side.
*   **Proposed Changes**:
    *   New `parse_capabilities(items: list[str]) -> dict[str, str]` that splits each item on
        the first `=` and strips both sides. Errors, all `ChanchiError("invalid_value", <message
        naming the item>, field="capability", ...)`:
        *   no `=`, or an empty name or value: no `valid_values`, `hint="use NAME=VALUE, for
            example vision=yes"`;
        *   unknown name: `taxonomy.validate_choice("capability", name, taxonomy.CAPABILITIES)`;
        *   unknown value: `taxonomy.validate_choice("capability", value,
            taxonomy.CAPABILITY_VALUES)`;
        *   a repeated name: no `valid_values`.

        The name and value checks live in a private `_validate_capabilities(capabilities:
        dict)` that `parse_capabilities`, `add_model` and `set_model` all call, so direct
        callers are validated too.
    *   `add_model(...)` and `set_model(...)` gain `capabilities: dict[str, str] | None = None`.
        Inside the existing transaction: `yes`/`no` upsert a row with `set_at = now or
        utc_now()` (the existing `now` parameter; `set_model` gains `now: str | None = None`);
        `unknown` deletes the row. `set_model` accepts capabilities alone as a valid update: it
        skips the `UPDATE models` statement when there are no column updates (otherwise the
        statement would be `UPDATE models SET  WHERE ...`), and the "nothing to update" hint
        adds `--capability`.
    *   New `capabilities_for(conn, model_id) -> dict[str, str]` (one query). `_model_dict(conn,
        row)` gains the `conn` parameter and adds `capabilities`, the flat string from the
        Technical Plan (`"vision=yes"`, `""` when none). `list_models`, `add_model` and
        `set_model` all return it. `recommend` uses `capabilities_for`.
    *   Built-in `human:human` stays unmodifiable, as today.

##### 14. `src/chanchi/cli.py` (Modify)

*   **Type / Scope**: CLI wiring.
*   **Proposed Changes**: `models add` and `models set` gain `--capability NAME=VALUE`
    (`action="append"`). `recommend` gains `--require` (comma list). `cmd_models_add`,
    `cmd_models_set` and `cmd_recommend` pass them through.

##### 15. `src/chanchi/scoring.py` (Modify)

*   **Type / Scope**: Read-side scoring.
*   **Proposed Changes**: `recommend(..., require: list[str] | None = None)`. Validate the names
    after the existing task type, complexity and empty-`available` checks and before resolving
    specs: strip each item, drop empty items and duplicates (keeping the first), and check each
    against `taxonomy.CAPABILITIES` with `validate_choice` (`field="require"`). Then resolve
    each spec as today and check its capabilities; failing specs go to `excluded` and are
    skipped. `prior_for` still receives all executor records. `excluded` is always present
    (`[]` without `--require`), placed after `explore_reason`. `excluded` entries follow the
    `--available` order (after the existing duplicate skip); `missing` entries follow the
    deduplicated `--require` order. When no candidate remains, return `recommendation: null`,
    `reason: no_capable_candidates`, `candidates: []`, `explore: []`, `explore_reason` as set by
    file 2 (step 1 wins at high complexity). `explain()` gains a top-level `require` entry
    after `exploration`: `{"rule": "<one sentence: a candidate stays only if every required
    capability is yes; others go to excluded with missing values no or unknown; the prior
    still uses all executor records>", "capabilities": list(CAPABILITIES), "values":
    list(CAPABILITY_VALUES)}`.

##### 16. `tests/test_db.py` (Modify)

*   **Type / Scope**: Migration tests.
*   **Proposed Changes**:
    *   Add `model_capabilities` to `OPERATIONAL_TABLES`.
    *   Renumber the synthetic migration in the forward-migration test from `(3,
        "003_add_probe.sql", ...)` to `(4, "004_add_probe.sql", ...)`; its assertions become
        `new_applied == [2, 3, 4]` and `user_version == 4`.
    *   `test_migration_v2_keeps_user_task_types` (lines 256-273): its assertions become
        `new_applied == [2, 3]` and `user_version == 3`.
    *   The existing template drift test then covers migration 003.

##### 17. `tests/test_catalog.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: set, overwrite and clear (`unknown`) a capability; reject an unknown
    capability name, an unknown value and a duplicate name; `set_at` stored; `models list`,
    `models add` and `models set` return `capabilities` as the flat string; `set_model` with
    only capabilities succeeds; `human:human` rejected; a test that scans
    `model_capabilities` and asserts every `value` is `yes` or `no`.

##### 18. `tests/test_scoring.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: `--require vision` keeps only `yes` models; `excluded` lists `no` and
    `unknown` with the right value; when all are excluded: `recommendation: null`, `reason:
    no_capable_candidates`, `candidates: []`, `explore: []`, `explore_reason:
    no_explorable_candidates` at medium and `complexity_not_explorable` at high; scores of
    remaining candidates equal the scores without `--require`; an unknown name in `--require`
    is an `invalid_value` error with `field: require` and `valid_values`; duplicate and empty
    items are ignored.

##### 19. `tests/test_cli.py` (Modify)

*   **Type / Scope**: CLI tests.
*   **Proposed Changes**: parsing of repeated `--capability`; `test_text_format` still renders
    `models list` as a table with a `capabilities` column; `recommend --require vision --format
    text` renders `excluded`.

##### 20. `skills/chanchi-model-selection/SKILL.md` (Modify)

*   **Type / Scope**: Planner skill.
*   **Proposed Changes**: Step 3: `--require vision` when the session needs screenshots or
    images. Step 4: `excluded` and `no_capable_candidates`. "Before you start", item 3, and
    "Catalog maintenance": planners never pass `--capability` to `models set` or `models add`;
    they report excluded `unknown` models to the owner. The skill has no `--capability`
    example.

##### 21. `README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: New section "Capabilities" after "Exploration": `recommend --require
    vision`, and, for the owner, `chanchi models set <agent:model> --capability vision=yes`
    (`models set` takes `agent:model`; `agent:model:effort` is rejected).

##### 22. `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` (Modify)

*   **Type / Scope**: Design spec.
*   **Proposed Changes**: Sections 4.3 (capability enums), 5 (new table), 6.6 (filtering), 7
    (flags) and 10 ("Template integrity": `model_capabilities` among the empty tables).

#### Owner step 2 (after Phases 1-2 are merged, before Phase 3)

*   These are owner data operations: run them with the installed `chanchi`, from any directory,
    without `CHANCHI_DB`, so they reach the real database, now at migration 003.
*   Register the missing opencode models with `chanchi models add --agent opencode --model
    opencode-go/<name> --cost <1-3> --efforts <variants>`. An opencode variant (`#low`, `#high`,
    `#max`) is recorded as a chanchi effort, as for the models already registered; a model whose
    only variants are not efforts (for example `#thinking`) is registered as a separate model
    name with no efforts. Models on the OpenCode Go plan use cost tier 1, like most existing
    opencode entries, unless the owner knows a model draws on the quota faster (the existing
    `opencode-go/grok-4.7` is tier 3). Models: deepseek-v4-pro, deepseek-v4.1-flash,
    glm-5.2, hy3, hy4, kimi-k2.7-code, kimi-k3, longcat-2.0, mimo-v2.5, mimo-v2.5-pro,
    mimo-v2.6-flash, mimo-v2.6-pro, minimax-m3.1-flash, qwen3.8-max, step-5-preview.
*   Write any registration that used a different name than the "Initial map" table into the S3
    task brief, so S3 writes `scripts/hf_model_map.json` with the registered names.
*   Set `vision=yes|no` for every active model, closed and open, using each provider's model page,
    so `--require vision` does not exclude most of the catalog as `unknown`.

#### Phase 3 (session S3)

##### 23. `scripts/hf_model_map.json` (Create)

*   **Type / Scope**: Hand-written data.
*   **Proposed Changes**: `{"schema_version": 1, "models": {"opencode:opencode-go/glm-5.3":
    {"hf_repo": "zai-org/GLM-5.3", "match_quality": "exact"}, ...}}` with exactly the 17 entries of
    the "Initial map" table in the Technical Plan, keyed `opencode:<catalog model>` with the
    names from the S3 task brief. Unmapped models are absent.

##### 24. `scripts/fetch_hf_benchmarks.py` (Create)

*   **Type / Scope**: Maintainer script, stdlib only, not part of the package.
*   **Proposed Changes**: Behaviour as in the Technical Plan (directory guard, optional token,
    sequential GET, Hub response mapping, dry run by default, `--write`, keep previous rows on
    failure, exit 1 if any repo failed, `vision_candidates`). It reads the map, the existing
    snapshot and the Hub; it never runs or imports `chanchi` and never opens the database.
    *   Entry point `main(argv=None, *, root=None, opener=None) -> int`. `root` defaults to
        `Path(__file__).resolve().parents[1]`; the guard compares the current directory with it,
        and the map and snapshot paths are derived from it. `opener` defaults to
        `urllib.request.urlopen`.
    *   `fetch_repo(repo, token, opener) -> dict` returns the mapped result `{"pipeline_tag":
        <str or None>, "eval_rows": [<rows per the Technical Plan field mapping>]}` and raises
        on any failure (non-200 status, timeout, bad JSON).
    *   `merge(previous, fetched, model_map, now) -> dict` returns the whole new snapshot.
        `previous` is the previous snapshot dict or `None`; `fetched` maps each map key
        (`agent:model`) to the `fetch_repo` result or to `{"error": "<message>"}`; `model_map`
        is the map's `models` dict; `now` is the run time as `YYYY-MM-DDTHH:MM:SSZ`. `hf_repo`
        and `match_quality` always come from `model_map`. On success: `fetched_at = now`,
        `last_error = null`. On error: previous `eval_rows`, `pipeline_tag` and `fetched_at` are
        kept and `last_error` is the message. `generated_at = now`, `schema_version = 1`.
    *   Dry-run summary, printed as JSON: `{"models": {"<agent:model>": {"hf_repo": ...,
        "rows": <rows now held>, "rows_changed": <rows added plus rows removed, compared as
        whole rows>, "error": <message or null>}}, "vision_candidates": [...], "failed":
        <count>}`.
    *   A repo that fails and has no previous entry is written with `eval_rows: []`,
        `pipeline_tag: null`, `fetched_at: null` and `last_error` set.
    *   Snapshot entries whose key is no longer in the map are removed.
    *   `generated_at` is the time of the run, set even when repos fail.
    *   Directory guard failure: message on stderr as plain text, naming the repository root,
        and exit code 2 (exit code 1 stays for failed repos).
*   **Tests import it** with `importlib.util.spec_from_file_location` (`scripts/` is not a
    package).

##### 25. `src/chanchi/data/hf_snapshot.json` (Create)

*   **Type / Scope**: Generated data, committed.
*   **Proposed Changes**: The first snapshot is the planner's: after S3 is audited, the planner
    runs `uv run python scripts/fetch_hf_benchmarks.py --write` in the S3 worktree and reviews
    the diff. Later refreshes are the owner's (CUJ 3). It reaches other projects on merge.

##### 26. `src/chanchi/hfsignals.py` (Create)

*   **Type / Scope**: Read-side module, pure functions, no network imports.
*   **Proposed Changes**:
    *   `SNAPSHOT_PATH` (module constant, see Technical Plan) and `load_snapshot(path=None) ->
        tuple[dict | None, str]`: `(snapshot, "snapshot")`, `(None, "missing")` (no file,
        unreadable, bad JSON) or `(None, "schema_mismatch")`.
    *   `canonical_values(snapshot) -> dict[tuple[hf_repo, dataset_id, task_id], float]`, keyed
        by Hub repo so two map entries sharing a repo count as one peer, with dates taken as the
        first 10 characters of `date`.
    *   `percentiles(values) -> dict[tuple[hf_repo, dataset_id, task_id], dict]`: `values` is
        already restricted to peers (repos with `match_quality` `exact` or `family`, done by
        the caller); each key maps to `{"percentile": <float 0-1>, "peers": <N>}`; a
        `(dataset_id, task_id)` with fewer than `HF_MIN_REPORTERS` peers is omitted.
    *   `signal_for(snapshot, agent, model, task_type) -> dict | None` maps the catalog entry to
        its repo and returns the `external_signals` object (allowlisted fields only).
        `benchmarks` holds one entry per counted `(dataset_id, task_id)`, sorted by
        `(dataset_id, task_id)`: `value` is the canonical value (mean of the latest-date rows)
        rounded to 2 decimals, `date` the latest date, `pull_request` `true` when any of those
        rows has `pull_request` set, `peers` the `N` from `percentiles` (`null` for `proxy`).
        The signal `value` is rounded to 4 decimals; the bucket is computed from the unrounded
        value.
    *   Constants at the top: `HF_BENCHMARKS` (dataset id → signal, allowed task ids, unit and
        range, as `{dataset_id: {"signal": str, "task_ids": tuple[str, ...], "unit":
        "percent", "range": (0, 100)}}`), `TASK_SIGNALS` (task type → signal) and
        `HF_MIN_REPORTERS = 5`, not in
        `taxonomy.py`. SWE-bench_Verified and SWE-bench_Multilingual start with `task_ids: ()`,
        so they count for nothing until the planner step after file 25. `scoring.explain()`
        reports the constants.

##### 27. `src/chanchi/scoring.py` (Modify)

*   **Type / Scope**: Read-side scoring.
*   **Proposed Changes**: `recommend()` calls `load_snapshot()` once, adds the signal bucket to
    `_explore_sort_key` after `cost_tier` (Technical Plan, Phase 3, "Ordering with signals"),
    and gives each `explore` entry `external_signals` as its last key, `null` when there is
    no snapshot, the model is unmapped or the task type has no signal. Every result gains
    `explore_signal_source` and `explore_signal_generated_at`, after `excluded`. `explain()`
    gains a top-level `external_signals` entry after `require`: `{"rule": "<one sentence:
    signals from the Hub snapshot only order explore, after cost_tier, as quartile buckets
    with no signal between bucket 1 and bucket 0; they never change scores>", "benchmarks":
    [{"dataset_id", "signal", "task_ids", "unit", "range"} per HF_BENCHMARKS entry, as lists],
    "task_signals": TASK_SIGNALS, "min_reporters": HF_MIN_REPORTERS}`. It stays static and
    does not load the snapshot.
*   Also modify `tests/test_scoring.py`: the two Phase 1 assertions that pin the four entry
    keys (`test_explore_complexity_gate`, `test_explore_caps_at_three_and_exact_keys`) now
    include `external_signals` (`None` there, since the autouse fixture of file 28 hides the
    snapshot).

##### 28. `tests/conftest.py` (Modify)

*   **Type / Scope**: Test configuration.
*   **Proposed Changes**: An autouse fixture that sets `hfsignals.SNAPSHOT_PATH` to a path that
    does not exist (with `monkeypatch`), so the Phase 1 and 2 tests never see the committed
    snapshot. Phase 3 tests point it at the fixture file.

##### 29. `tests/fixtures/hf_snapshot_sample.json` (Create)

*   **Type / Scope**: Test fixture.
*   **Proposed Changes**: A snapshot with synthetic values in the real row shape (Technical Plan,
    "Hub response"). Required properties:
    *   `datacurve/deep-swe` reported by 6 `exact`/`family` repos, including a tie;
    *   `harborframework/terminal-bench-2.1` reported by 5 repos, one of them with two rows on
        the same date (81 and 82.7) and `pull_request` set;
    *   `claw-eval/Claw-Eval` reported by 3 repos (below `HF_MIN_REPORTERS`), and one model whose
        only rows are Claw-Eval;
    *   one `proxy` entry and two map entries sharing one repo;
    *   one row with a `task_id` not allowed, one with an unparseable `date`, one with 0.669 on
        a `percent` benchmark, one with 451 on `datacurve/deep-swe` (out of range);
    *   one row whose `source_name` contains instruction-like text;
    *   one `date` in full timestamp form and one in `YYYY-MM-DD` form.

##### 30. `tests/test_hfsignals.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**:
    *   latest-date mean (81 and 82.7 → 81.85); timestamp and plain dates compare correctly;
    *   out-of-range rows, fraction values on a `percent` benchmark, disallowed `task_id`
        values and rows with an unparseable `date` are ignored;
    *   benchmarks with fewer than 5 peers ignored (Claw-Eval), and the Claw-Eval-only model
        gets `value: null` and `benchmarks: []`;
    *   percentile formula with ties; two map entries sharing a repo count as one peer and get
        the same value; `proxy` entries are not peers and get `value: null`;
    *   no signal for task types without one (`external_signals: null`), and `null` for an
        unmapped model;
    *   `load_snapshot`: missing file and bad JSON → `missing`; wrong `schema_version` →
        `schema_mismatch`; fixture → `snapshot` with `explore_signal_generated_at` equal to its
        `generated_at`;
    *   ordering: cost tier before the signal bucket; within a cost tier no signal sorts between
        bucket 0 and bucket 1; with no snapshot the order equals the Phase 1 order;
    *   `external_signals` contains only allowlisted keys, never `source_name`, `source_url` or
        other Hub text, for mapped and `proxy` entries; `pull_request` is `true` for the
        pull-request row;
    *   when `src/chanchi/data/hf_snapshot.json` exists, it parses and has `schema_version == 1`
        (skipped when absent).

##### 31. `tests/test_fetch_script.py` (Create)

*   **Type / Scope**: Unit tests with a fake opener and `root=tmp_path`; no network, and the real
    snapshot is never touched.
*   **Proposed Changes**: guard refuses another directory (`monkeypatch.chdir`); token sent only
    when set and never in output; `User-Agent: chanchi-hf-fetch`; the Hub response mapping on
    the sample from the Technical Plan, including a skipped element with `error` and no `data`;
    401, 404, timeout and bad JSON each keep previous rows, set `last_error` and give exit code
    1; a failing repo with no previous entry gets `eval_rows: []`; entries removed from the map
    are removed; dry run writes nothing; `--write` output is sorted and stable;
    `vision_candidates` lists exactly the mapped models tagged `image-text-to-text`; the script
    source contains no `subprocess`, `sqlite3`, `import chanchi` or `from chanchi`.

##### 32. `tests/test_no_network.py` (Create)

*   **Type / Scope**: Boundary test.
*   **Proposed Changes**: Walk `src/chanchi/**/*.py` with `ast`; fail on `import`, `from ...
    import` (including `from urllib import request`) or literal `importlib.import_module` of
    `urllib.request`, `http.client`, `socket`, `ssl`, `urllib3`, `requests`; fail on
    `subprocess` outside `projects.py`.

##### 33. `tests/test_skills_content.py` (Modify)

*   **Type / Scope**: Content test.
*   **Proposed Changes**: Assert no file under `skills/` mentions `fetch_hf_benchmarks`, `HF_TOKEN`
    or `huggingface.co` (Goal G6, CUJ 4); assert the selection skill says `external_signals` are
    unverified and never audit evidence.

##### 34. `skills/chanchi-model-selection/SKILL.md` (Modify)

*   **Type / Scope**: Planner skill.
*   **Proposed Changes**: In step 4, one paragraph on `external_signals`: unverified, from the Hub
    checkpoint not the served variant, `pull_request: true` marks a row from an open pull
    request, used only to order `explore`, never copied into audits.

##### 35. `README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Replace the "Local only" bullet with the wording from the Technical Plan.
    New section "Refreshing Hugging Face signals (maintainers only)": the dry-run and `--write`
    commands (`uv run python scripts/fetch_hf_benchmarks.py`) run in a worktree, the optional
    `HF_TOKEN`, checking map keys against `chanchi models list --all` before a refresh, acting on
    `vision_candidates`, and the review, commit and merge rule (the snapshot goes live on merge).

##### 36. `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` (Modify)

*   **Type / Scope**: Design spec.
*   **Proposed Changes**: Section 1.3: replace "No server, no network" with "No server. The
    `chanchi` package imports no network module; one maintainer script in `scripts/` fetches
    public benchmark metadata into a committed file." Section 3: a `hfsignals` row in the module
    table. Section 6.6: ordering of `explore` by external signal.

#### Planner step after the first snapshot (before merging Phase 3)

1.  Read the `task_id` values of SWE-bench_Verified and SWE-bench_Multilingual rows in the new
    snapshot, write them into `HF_BENCHMARKS` in `hfsignals.py`, and re-run `uv run pytest`.
2.  Apply the drop criterion: count the map entries whose `signal_for` returns a non-null `value`
    for at least one of `bugfix`, `infra-config-ci` and `integration`, with `uv run python -c`
    over `hfsignals.load_snapshot()` and the map. Fewer than 8 → discard `feat/hf-signals`.
3.  Commit the snapshot and the task ids, then merge.

### Verification Plan

*   **Build**: in each worktree, `uv build` succeeds and `uv run chanchi --help` lists no fetch
    command. Never run `uv tool install` from a worktree.
*   **Unit and integration tests**: `uv run pytest` passes after every session, in the session's
    worktree, with `CHANCHI_DB` set to a scratch file.
*   **Static checks**: `tests/test_no_network.py` and `tests/test_db.py` (template drift) pass.
*   **Goal G2 check (planner, after S1 and S2, before merging Phases 1-2)**:
    1.  Copy the real database with `sqlite3 ~/.local/share/chanchi/chanchi.db ".backup
        <copy>"` (it runs in WAL mode, so a plain file copy can miss recent writes).
    2.  From the main checkout, with `CHANCHI_DB=<copy>`, run `chanchi recommend` for each task
        type in `chanchi taxonomy list` at `medium` complexity, with `--available` set to every
        active spec, and save the output.
    3.  Only then, from the branch worktree, run the same calls with `CHANCHI_DB=<copy> uv run
        chanchi ...`. This migrates the copy to 003, which is why main runs first.
    4.  Diff `recommendation`, `reason`, `window` and `candidates`: they must be identical.
*   **Manual checks (planner, after S3)**:
    *   from another directory, `uv run python <repo>/scripts/fetch_hf_benchmarks.py` stops with
        the guard error;
    *   in the repo root, the dry run prints a summary with `vision_candidates` and changes no
        file;
    *   run with `--write`, review the snapshot diff, then the planner step above;
    *   `uv run chanchi recommend --task-type bugfix --complexity medium --available "<opencode
        specs>"` shows `explore` ordered by `cost_tier`, then the `swe` signal bucket, with
        `external_signals`;
    *   `uv run chanchi recommend --task-type ui-component --complexity low --require vision
        --available "<all specs>"` lists `excluded` with `missing` values (`no` or `unknown`).
*   **Budget report**: after `chanchi change close`, `chanchi show <this change>` reports
    `exploratory: 3`, `allowed: 1` and `over_budget: true`, matching the owner override.
*   **Success measure (after about 10 audited opencode sessions)**: `chanchi stats --by task-type`
    has data for at least 3 opencode models that had none before this change.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
