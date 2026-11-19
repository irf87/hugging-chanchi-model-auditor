# Comprehension Report: explore-capabilities-hf (Stage 6)

* **Target:** `docs/designs/explore-capabilities-hf.md`
* **Scope:** FeatureRange lines 1-620, DetailedRange lines 621-974
* **Reviewer:** `egm-comprehension` (read the persona file and the target only; no document standard)
* **Date:** 2026-11-17

## What this proposes

`chanchi recommend` gains three additions, built one after another. Phase 1 adds a deterministic
`explore` list. It holds up to 3 non-red-flagged models with fewer than 3 audited sessions of the
requested task type, and it only appears at low and medium complexity. Candidates are sorted by:
weak start last, then signal bucket, then cost tier, then session count, then spec. When the top 3
all have a signal, one slot is kept for a model with no signal. The existing evidence-based
`recommendation` stays byte-identical. Exploration is limited by a rule in the planner skill (at
most 1 in 4 sessions per change), and `chanchi show` reports it after the fact. Phase 2 adds
owner-set capabilities (only `vision` for now) in a new `model_capabilities` table without CHECK
constraints. It also adds `recommend --require`, which moves models that are not `yes` into an
`excluded` list with a hint. Phase 3 adds a maintainer-only stdlib script that turns public Hugging
Face eval rows into a committed JSON snapshot. The package reads that snapshot offline and computes
peer percentiles for three signals (`swe`, `terminal`, `tool-use`). Those signals only order
`explore` and are shown as `external_signals`, never as scores. Phase 3 is dropped if fewer than 8
opencode models get a signal. The detailed plan runs this as three exploratory sessions on one agy
model (`gemini-4-hydrogen-high`), a knowing owner override of the budget, with the planner auditing
and committing each session.

## How the existing system works, per this document

chanchi records executor sessions (agent, model, effort, task type, complexity) and their audit
scores in a global SQLite database. One editable install of the package serves every project.
`recommend()` scores each available spec using a smoothed mean against a population prior
(`prior_for`). If data at task_type+complexity is too thin, it falls back to task_type alone. A
candidate is eligible only at confidence `low` or `ok` (3 or more sessions). Among eligible
candidates within a 5-point window of the best, the cheapest wins. Models below 3 sessions are
listed but can never be recommended, so rarely used models never get picked and never get audited.
A planner skill follows `recommendation`. Migrations only go forward, a template DB is regenerated
from them, and a `schema_too_new` error stops older code from running against a newer database.

The paraphrase was possible for every section, so there is no Blocker.

## Findings

1. **Major.** Phase 1 rule 3.1, "Known leak" paragraph, Alternatives C and E. The selection rule
   that G2 depends on (cheapest-in-window, `RECOMMEND_WINDOW`, level search, `smoothed()`) is never
   stated in one place, and weak start reuses `RECOMMEND_WINDOW` without saying whether that is
   deliberate. Fix: add a "How recommend() picks today" paragraph to The Problem and state that the
   reuse is deliberate.
2. **Major.** `red_flag`. Its source, key and effect are never defined, while S2's rationale depends
   on it ("red-flagged here" vs "flags are per model"). Fix: one sentence defining it.
3. **Major.** "Protocol line". Never defined (format, location, author), and it is unclear whether
   anything parses the `· explore:` suffix. Fix: define it and say it is for humans only, if so.
4. **Major.** File 25 refers to `--capability-source`, which the design removed. Fix: remove the
   clause.
5. **Major.** Phase 3 map and file 18 name only one of the 16 repos, so S3 cannot write the map and
   the "expected count is 14" cannot be checked. Fix: include the full table.
6. **Major.** Signal derivation: what a `proxy` model gets (signal value, bucket, reserved slot) is
   unstated, and `N` and "peers equal" in the percentile formula are undefined. Fix: state both.
7. **Major.** Execution sessions: agy and herdr are not explained, and `-high` in the model name vs
   `:high` effort is confusing. Fix: one line each, plus a note on the suffix.
8. **Nit.** `match_quality` values are not defined.
9. **Nit.** Owner step: variant = effort mapping and the cost-tier rule are not stated.
10. **Nit.** CUJ 1 writes `opencode/opencode-go/glm-5.3-flash` instead of the colon form.
11. **Nit.** The Claw-Eval sentence is ambiguous (3 models or 3 rows).
12. **Nit.** The forbidden-module list differs between the Technical Plan and file 26 (`requests`).
13. **Nit.** With `--require` leaving nothing at `high` complexity, the precedence between
    `no_explorable_candidates` and `complexity_not_explorable` is unstated.
14. **Nit.** "A session that blocks other sessions" needs a short gloss.
15. **Nit.** `schema_too_new`, the `bak-v2` backup, `scoring explain`, "deferred Stage 4" and "the
    seven questions from the brief" need glosses or removal.
16. **Nit.** The deployment model (one editable checkout, one global database) should be stated
    early, in the Overview or The Problem.
