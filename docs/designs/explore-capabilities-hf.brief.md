# Exploration Policy, Catalog Capabilities and Hugging Face Ordering for `chanchi recommend`
* **Author:** Iván R
* **Date:** 2026-11-17
* **Revision:** 3 (pivot after the first Goldfish review; open questions resolved)

## Overview

The owner rarely uses the open-weight models available through opencode (GLM, Kimi, MiniMax,
MiMo, DeepSeek, Hy, LongCat, Step and others). Because they are rarely used, chanchi has few or no
audited sessions for them, so `chanchi recommend` never suggests them. The owner wants to know
which of them can handle domain logic, UI work, running commands, or reading screenshots.

The first version of this concept replaced the scoring prior with Hugging Face benchmark
percentiles. Seven reviewer lenses found that it could not reach its goal (see Analysis 1-2). This
revision moves the center of the feature:

1. **Exploration policy.** `recommend` returns, next to the evidence-based `recommendation`, a
   separate `explore` field: one candidate with fewer than 3 audited sessions that the planner may
   assign on purpose, so audits produce the missing data. It applies only at low and medium
   complexity.
2. **Catalog capabilities.** The owner records capabilities such as `vision` per model
   (yes / no / unknown). `recommend --require vision` filters on them.
3. **Hugging Face snapshot for ordering only.** A maintainer script inside this repository fetches
   public Hub metadata (`evalResults`, `pipeline_tag`) into a committed JSON snapshot. chanchi reads
   it offline to order exploration candidates and to show `external_signals` with their source and
   date. It never changes an audit score.
4. **Benchmark offset on scores: deferred.** It is reconsidered only if audits show that benchmarks
   predict audit scores.

The data reaches every project because all of them run the same editable install. Only the fetch
is limited to this repository.

## Analysis

### 1. Why the first version failed: unaudited models can never be recommended
- In `src/chanchi/scoring.py` `recommend()` (line 470), a candidate is eligible only when
  `confidence in ("low", "ok")`. `taxonomy.confidence(n)` returns `"insufficient"` for n < 3
  (`CONFIDENCE_LOW_MIN = 3`).
- A model with 0 to 2 sessions is therefore never the `recommendation`, whatever its prior. A new
  prior only reorders `candidates` while `recommendation` stays null with `insufficient_data`.
- The gap is an eligibility policy, not a prior. Exploration addresses it directly and needs no
  network: the owner lacks data because the models are not used, and exploration makes them used.

### 2. Why benchmarks must not set the score
- Audit-based priors sit around 85-100 (`DEFAULT_PRIOR = 70`). A percentile has its median at 50.
  With `SMOOTHING_K = 3`, three sessions averaging 95 and a percentile prior of 20 give 57.5, and
  with `RECOMMEND_WINDOW = 5.0` that scale artifact would decide the pick.
- Every one of about 210 Hub result rows across 16 repos is unverified, reported by authors or third
  parties, in different harnesses, on mixed units (WildClawBench mixes percentages and raw counts),
  and sometimes many rows per benchmark (Kimi-K3 reports 20 agents-last-exam rows).
- The Hub checkpoint is not what opencode serves (`opencode-go/glm-5.3-flash#high`, possibly
  quantized, inside the opencode harness).
- Ordering exploration is a role where this noise is cheap: a wrong order costs one trial session,
  and the audit score stays clean.

### 3. Contradictions and how this revision resolves them

| Contradiction | Resolution |
| --- | --- |
| Hub data should influence recommendations, but the evidence gate must only trust audits. | Hub data orders `explore` candidates only. `recommendation`, `stats` and `smoothed()` stay audit-only. |
| "Local only, nothing leaves the machine", but the data comes from the network. | The `chanchi` package never uses the network. One script in `scripts/` fetches, and writes a reviewed, committed JSON snapshot that the package reads offline. |
| Every project should benefit, but only this repository may fetch. | The snapshot ships inside the editable checkout every project already uses. The fetch script is not a `chanchi` subcommand and no skill mentions it. |
| `--require vision` needs a reliable answer, but `pipeline_tag` covers only open repos and says nothing about what opencode exposes. | Capabilities are a catalog field the owner sets. The Hub tag only suggests a value in the snapshot. |
| Exploration gathers data, but it spends real sessions on unproven models. | Limit exploration to low and medium complexity and to an exploration budget (open question 1). |

### 4. What the snapshot holds and how it is read
- Raw rows only, per mapped model: Hub repo, match quality (`exact`, `family`, `proxy`), each
  `evalResults` row (dataset id, task id, value, date, source, `verified`), `pipeline_tag`, and the
  fetch timestamp. No computed percentiles, consistent with the scoring.py rule "scores are never
  stored".
- The model-to-repo table is written by hand. Name search is not reliable: no opencode name equals a
  Hub id, and several models have only near matches.
- At read time chanchi derives up to three signals (`swe`, `terminal`, `tool-use`) per model, with
  rules for duplicate rows (one canonical row per repo, dataset and task id), a minimum number of
  reporting models per benchmark, and a declared unit per benchmark so mixed-unit data is rejected
  by rule.
- `explore` candidates are ordered by the signal weighted for the requested task type, then by cost
  tier. Models with no signal (closed models, unmapped models, task types with no benchmark) are
  ordered by cost tier and fewest sessions.
- Each candidate shows its provenance: `external_signals` with benchmarks used, `hf_repo`,
  `match_quality`, `fetched_at` and `verified: false`, so agents do not record benchmark numbers
  as audit evidence.

### 5. Mechanics and risks that remain
- **Catalog capabilities need a schema change** (migration 003, SQL only, regenerate
  `src/chanchi/data/template.db`, update `tests/test_db.py`). Migrations are forward-only and one
  editable checkout serves every project, so a reverted migration causes `schema_too_new`
  everywhere. Roll back by disabling the read path, not by deleting the migration.
- **"Repo-only" is a convention.** Anyone can run `python <repo>/scripts/x.py`. A guard that the
  current directory is this repository's git root prevents accidents only. A test asserts that no
  module under `src/chanchi` imports `urllib.request` or `http.client`.
- **Token.** The public API answered every request without a token. `HF_TOKEN` is optional, read
  only from the environment, and never logged or written.
- **Snapshot freshness.** Data is as fresh as the last commit. The script defaults to a dry run that
  prints the diff summary.
- **Docs.** The README line "Nothing leaves the machine" and design spec section 1.3 must be
  reworded to: the `chanchi` package never uses the network; one maintainer script in `scripts/`
  fetches public benchmark metadata.
- **No signal for UI or screenshots.** No mapped benchmark covers ui-component, ui-layout-styling,
  docs, db-schema-migration or architecture-design. For those, only exploration and audits produce
  data, and the vision capability filter only answers "can it read images".

### 6. Ideal Final Result
- `recommend` keeps its evidence gate. Unaudited models appear in a separate `explore` field, with
  provenance, at low and medium complexity.
- Capability filters answer "can this model read screenshots" from owner-set catalog data.
- Hub metadata, fetched only by a maintainer script, decides which unaudited model to try first.
- After enough audited sessions, a measured comparison shows whether benchmarks predict audit scores,
  which decides whether a bounded score offset is ever added.

## Goals vs. Non-Goals

### In-Scope Goals
- An `explore` field in `recommend` for candidates with n < 3, limited to low and medium complexity,
  with the matching update to `skills/chanchi-model-selection/SKILL.md` step 4.
- Owner-set capabilities (yes / no / unknown) in the catalog, `models add/update --capabilities`, and
  `recommend --require <cap,...>` (AND semantics) with excluded candidates listed with a reason.
- `scripts/fetch_hf_benchmarks.py`: stdlib `urllib`, optional `HF_TOKEN`, cwd guard, dry run by
  default, writes a committed JSON snapshot of raw rows from a hand-written model-to-repo table.
- Offline, read-side derivation of `swe` / `terminal` / `tool-use` signals used only to order
  `explore` and to fill `external_signals`.
- `scoring explain` documents the exploration rule and the signal derivation.
- Offline tests with captured fixtures. No test touches the network.

### Out-of-Scope Non-Goals
- A fourth cost tier (rejected by the owner).
- Orchestrator or auditor role scores from benchmarks (rejected by the owner).
- Any change to audit scores, `smoothed()`, `prior_for()`, `stats`, dimension or planner scores
  from Hub data in this iteration.
- Benchmark data for closed models (Claude, Gemini, Grok).
- Any `chanchi` subcommand or skill text that triggers a network fetch.
- Storing computed percentiles, priors or signals.
- Benchmark signal for UI, docs, schema or architecture task types.

## Alternatives Weighed

- **Fourth cost tier from HF per-token prices.** Rejected by author: dropped after discussion, HF
  per-token prices do not reflect subscription plan cost.
- **Orchestrator/auditor role scores from benchmarks.** Rejected by author: no benchmark measures
  these roles.
- **Replace the population prior with a 0-100 benchmark percentile prior (revision 1).** Rejected by
  author after review: n < 3 models stay ineligible (scoring.py:470), the percentile scale is
  incompatible with audit scores, and `smoothed()` is shared by planner and dimension stats.
- **Bounded benchmark offset on the prior now.** Deferred by author: kept as a later stage, only if
  audits show benchmarks predict audit scores.
- **Let unaudited candidates compete directly for `recommendation`.** Rejected by author: under the
  cheapest-in-window rule (scoring.py:476) an unaudited tier-1 model could displace a proven one.
- **Count benchmark data as pseudo-sessions toward confidence.** Rejected by author: it mixes
  unverified data into the safety gate.
- **Thirteen per-task-type priors from a benchmark table.** Rejected by author: six task types drew
  on one SWE-bench signal, and SWE-bench does not measure writing tests. Replaced by three signals
  with per-type weights.
- **Derive `--require vision` from `pipeline_tag` only.** Rejected by author: it drops closed vision
  models and Step-5-Preview (no tag), and trusts a Hub tag for a variant opencode may serve as text
  only.
- **Store Hub rows in new global DB tables through a migration.** Rejected by author: a committed
  snapshot reaches every project through the editable install with no migration, is reviewable as a
  git diff, and keeps the package free of network-filled tables.
- **Required `HF_TOKEN`.** Rejected by author: the public endpoint answered without one; the token is
  optional.
- **No network at all (exploration plus an owner-set ordering per model).** Kept as the fallback if
  the snapshot turns out too sparse to order candidates usefully.

## Key Decisions & Staging for Next Steps

### Decisions resolved during ideation
- Exploration is a separate `explore` field; it never replaces or displaces `recommendation`.
- Exploration applies only at low and medium complexity.
- Hub data orders exploration and is shown as `external_signals`; it does not change any score.
- Storage is a committed JSON snapshot, not DB tables. Capabilities are the only schema change.
- `stats` stays strictly audit-based.
- `HF_TOKEN` is optional.
- UI and screenshot tasks get no benchmark signal; the owner accepts that only exploration and
  audits fill that gap.

### Staging
1. **Stage 1: exploration policy.** `explore` field in `recommend()`, SKILL.md step 4, `scoring
   explain`. No network, no migration. On its own this addresses the goal.
2. **Stage 2: catalog capabilities.** Closed capability set in `taxonomy.py`, migration 003,
   `--capabilities` on `models add/update`, `recommend --require` with an `excluded` list.
3. **Stage 3: Hub snapshot.** Fetch script, model-to-repo table, snapshot file, offline signal
   derivation, `explore` ordering, `external_signals`, README and spec wording, no-network test.
4. **Stage 4 (deferred): bounded score offset.** Only after roughly 10 or more audited sessions of
   opencode models, if `external_signals` correlate with audit scores.

### Signal mapping (planner proposal, revised after review)

| Signal | Benchmarks | Task types and weight |
| --- | --- | --- |
| `swe` | datacurve/deep-swe (12 models), ScaleAI/SWE-bench_Pro (7); SWE-bench_Verified and _Multilingual only once enough models report them | bugfix 1.0; refactor, business-logic, api-endpoint 0.5 |
| `terminal` | harborframework/terminal-bench-2.1 only (10 models); never mixed with the older terminal-bench | infra-config-ci 1.0 |
| `tool-use` | hkust-nlp/Toolathlon (5), claw-eval/Claw-Eval (6) | integration 0.5 |
| none | - | tests, unit-tests, ui-component, ui-layout-styling, docs, db-schema-migration, architecture-design, custom types |

Excluded: hle, gpqa, LEXam, MDPBench, ExtractBench, ParseBench, OmniDocBench, OmniCompass,
WildClawBench (mixed units), agents-last-exam (sub-task rows), Long-Horizon-Terminal-Bench (measures
persistence, not CI work), apex-agents (office tasks).

### Decisions on former open questions (accepted by the owner, 2026-11-17)
1. **Exploration budget.** The skill tells the planner to take `explore` for at most 1 in 4
   sessions of a change.
2. **Exploration pick.** `explore` is a ranked list of up to 3 candidates.
3. **Near matches.** MiMo `-RL` repos map to mimo-v2.6-flash/pro and `Hy4-preview` maps to hy4,
   both with `match_quality: family`. qwen3.7-plus, qwen3.8-max, qwen3.8-flash, kimi-k3.1-pro and
   deepseek-v4-pro stay unmapped.
4. **Catalog names.** The missing opencode models (deepseek, hy, longcat, mimo, step,
   kimi-k2.7-code, kimi-k3, minimax-m3.1-flash, qwen3.8-max) are registered with the owner's
   variants before Stage 3.
5. **Unknown capability.** Under `--require`, models with an unknown capability are excluded and
   listed in `excluded` with reason `unknown`.
6. **All filtered out.** When `--require` removes every candidate, `recommend` returns
   `recommendation: null` with reason `no_capable_candidates`.
7. **Refresh behavior.** When a repo returns 404 or is rate limited, the snapshot keeps its previous
   rows with their original fetch date.
