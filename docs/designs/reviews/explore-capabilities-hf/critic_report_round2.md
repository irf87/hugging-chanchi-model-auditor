# Goldfish Review Report

**Target:** `docs/designs/explore-capabilities-hf.md` (lines 1-779, top of file up to but not including "## Detailed Implementation Plan" at line 780)
**Stage:** 7 (Critic Review), round 2. Mode: REVIEW.
**Standard:** `resources/document_standards/feature-spec-standard.md` (egm-design, egm-structural). egm-style used its persona's audit vectors.
**Settled items not re-raised:** Phase 3 drop criterion, no `source` column on `model_capabilities`, the owner's budget override for the Hydrogen sessions, the known leak into `recommendation` (G2), line wrapping beyond 100 columns.

## Reviewer Status

| Reviewer | Status | Raw findings |
| --- | --- | --- |
| `egm-design` | completed | 0 Blocker, 5 Major, 6 Nit |
| `egm-structural` | completed | 0 Blocker, 0 Major, 6 Nit |
| `egm-style` | completed | 0 Blocker, 3 Major, 20 Nit |

After deduplication: **0 Blocker, 7 Major, 24 Nit.** Where two reviewers raised the same point, the finding keeps one id and lists the others under "Also raised by".

**Round-1 fixes.** All three reviewers checked the applied round-1 fixes and found them in place: the budget formula, the tag-based count, the effort-free hint, the editable-install wording, the subprocess catalog read, Risks and Limits, the allowlisted `external_signals`, cost-first ordering with a neutral no-signal bucket, one spec per model, the `recommend()` description, the heading promotions, the horizontal rules, Alternative A and M, list spacing and links. Every internal cross-reference resolves. Several fixes left gaps or created new problems, and the findings below record them. design-1-16 is only partly closed (design-2-9).

**Verified by the synthesizer against source:**
- the level search keys records by `(agent, model, effort)` (`scoring.py` 435-451), which underlies design-2-1;
- `models add` requires `--cost` (`cli.py`:250), which underlies style-2-2;
- `session update --tags` replaces the whole list (`record.py` 353-354), which underlies design-2-6.

## Prioritized Findings (Blockers -> Major -> Nits)

### design-2-1: Exploration can end before any single effort is eligible, so the model gets stuck again. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-style` (style M2).
* **Affected Scope:** Lines 147-150 (CUJ 1), 207-210, 235-237 (rule 4).
* **Discrepancy Description:** The two counts use different keys:
  * `n_task_type` decides when a model leaves `explore`. It counts per `(agent, model)` across efforts.
  * Eligibility for `recommendation` counts per full spec, effort included (`scoring.py` 435-451).

  Example: GLM gets 2 audited `bugfix` sessions at `:low` and 1 at `:high`. GLM leaves `explore`, but neither spec has 3 sessions at any level, so neither can be recommended. That recreates the stuck loop the design exists to break. Rule 4 keeps "the first one as written in `--available`", and that order varies between planners, so sessions are likely to split across efforts. CUJ 1's "after 3 audited sessions, GLM competes" holds only when all 3 sessions used one effort.
* **Rationale & Recommendation:**
  * Define explorable as "no effort of this `(agent, model)` has 3 or more audited sessions of the task type".
  * In rule 4, keep the spec whose effort already has the most task-type sessions, then the first one as written.
  * Optionally add a skill rule: explore sessions of a model stay at the effort `explore` listed.
  * Change CUJ 1 to "3 audited `bugfix` sessions at one effort".
  * Add a test for the split-effort case.

### design-2-2: The one-spec-per-model rule mixes per-model and per-spec units, so red flags and rule 5 can be bypassed. Severity: Major
* **Reviewer Lens:** `egm-design`. Also raised by `egm-style` (style N5, N6).
* **Affected Scope:** Lines 59-62, 91-93 (G1), 207-209, 213-214, 218-222 (weak start), 234-241, 254-256.
* **Discrepancy Description:**
  * **Red flags.** `red_flag` is per spec, and a spec with no sessions is never red-flagged. If `GLM:high` is red-flagged, `GLM:low` is still explorable, and rule 4 may keep it.
  * **Order.** The doc does not say whether rule 1 (red-flag filter) and rule 5 run before or after the rule 4 dedupe. It also does not say whether dedupe runs before or after the sort, which breaks ties by `spec` while rule 4 keeps the first as written.
  * **Rule 5.** It excludes only the exact `recommendation` spec. When `GLM:medium` is the recommendation (resting on `complexity` or `global` data), `GLM:high` can still take an `explore` slot, so one model is offered twice.
  * **Weak start.** "its audited sessions of this task type" does not say whether these are the spec's sessions or the model's.
  * **G1 wording.** G1 says "one spec per model". Rule 4 says per `(agent, model)`.
* **Rationale & Recommendation:**
  * State the order: filters (rule 1, rule 5), then the per-model dedupe, then the sort, then the top 3.
  * Apply the red flag and rule 5 per `(agent, model)`: a model is not explorable if any of its efforts is red-flagged at its level, or if any of its efforts is the `recommendation`.
  * Define weak start as using "the sessions counted in `n_task_type`".
  * Update G1 (use `(agent, model)`), line 213-214 and `explore_reason` to match.

### design-2-3: The worktree rule conflicts with owner catalog writes that must reach the real database. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 42-46, 165-169 (CUJ 3), 322-323, 396-399, 457-459, 731.
* **Discrepancy Description:** All work happens in worktrees with `CHANCHI_DB` pointing at "a scratch file or a copy". The fetch script, run there, tells the owner to run `chanchi models add` (396-399) and `chanchi models set --capability vision=...` (457-459).
  * Run in the same shell, those writes go to the copy and are lost when the worktree is discarded.
  * A scratch file has an empty catalog, so the script would stop on every map entry. CUJ 3 says "copy" and line 44 allows either, so the two disagree.
  * `--capability` cannot be written to the real database until Phase 2 is merged, and the doc does not say capability classification waits for that.
* **Rationale & Recommendation:**
  * State that catalog and capability commands are owner data operations. They run with the installed `chanchi`, without `CHANCHI_DB`, and for `--capability` only after Phase 2 is merged. Have the script's printed commands say so.
  * Require a copy (not a scratch file) for fetch runs, refreshed after such writes.
  * Add a Risks and Limits row.

### design-2-4: The `excluded` hint cannot be pasted as written, and agents in any project are free to act on it. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 315-316, 337-340, 551-553.
* **Discrepancy Description:**
  * **Not runnable.** The hint is `chanchi models set <agent:model> --capability vision=yes|no`. Pasted into a shell, `|` pipes the output into a program named `no`. That repeats the failure round-1 design-1-3 was meant to fix.
  * **Agents can act on it.** The hint sits in `recommend` JSON that planner agents read. A planner blocked by `--require vision` has every reason to run `vision=yes` itself. Nothing in the skill changes (551-553) forbids this. That breaks the premise at 315 that "every write is a person running `models set`".
* **Rationale & Recommendation:**
  * Emit two concrete commands (for example `hint_commands` with the `yes` and `no` forms), or one command with a clearly marked placeholder.
  * Add a skill rule: planners never run `models set`. They report excluded `unknown` models to the human.
  * Add a Risks row: "agent self-classifies capabilities".
  * Keep the round-1 test, and run each emitted command through `models set`.

### design-2-5: The subprocess catalog read can still migrate the real database by accident. Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Lines 438-442, 731, 749-751.
* **Discrepancy Description:** `chanchi models list` runs `open_operational()` and then `bootstrap()`. That migrates whatever `CHANCHI_DB` points at, or the real database when it is unset (`db.py` 211-238).
  * **Scenario.** The script runs in a worktree whose branch carries the unmerged migration 003, and `CHANCHI_DB` was forgotten. The first subprocess call then makes migration 003 irreversible for every project. The NFR names this as the only irreversible step, and the only mitigation is a convention.
  * **Not specified:**
    * what the script does on a non-zero exit (for example `schema_too_new`);
    * how it finds the worktree's `chanchi`. "The `chanchi` on `PATH` is the worktree's own" holds only under `uv run`.
* **Rationale & Recommendation:**
  * Before calling `models list`, run `chanchi db status`, which is read-only and does not bootstrap (`cli.py`:64, `db.py` 256-282). Stop if `CHANCHI_DB` is unset or `operational.pending > 0`.
  * Invoke `[sys.executable, "-m", "chanchi", ...]` so the call is tied to the running interpreter, not to `PATH`.
  * On a non-zero exit, stop and print the chanchi error JSON.
  * Add the guard to Risks and Limits.

### style-2-1: `show` reports false overruns while a change is in progress, and the edge cases are undefined. Severity: Major
* **Reviewer Lens:** `egm-style`. Also raised by `egm-design` (design N2).
* **Affected Scope:** Lines 97-102 (G3), 272-277, 284-290.
* **Discrepancy Description:**
  * **Planned vs started.** The skill rule uses n as the planned session count. `show` uses sessions recorded so far. In CUJ 1 (8 planned), if the GLM session starts first, `show` sees n=1 and `allowed`=0, and reports `over_budget: true`. Another case: 2 of 8 sessions started, both explore, gives `allowed`=1 and `over_budget: true`.
  * **Undefined values.** `allowed` is defined only for n of 2 or more, but `over_budget = exploratory > allowed` is applied for every n. `share` divides by zero when the change has no sessions.
  * **Retries.** Counting only the latest attempt drops an explore attempt that failed and was retried on a proven model. `session start --retry-reason` creates a new row, and the doc does not say whether the retry must repeat `--tags explore`.
* **Rationale & Recommendation:**
  * Define `allowed = 0 if sessions < 2 else max(1, floor(sessions / 4))`.
  * Set `share: null` when `sessions` is 0.
  * Do one of the following, and mirror it in G3:
    * report `over_budget: null` until `changes.closed_at` is set; or
    * state that `over_budget` is final only once the change is closed.
  * Count a `session_ref` as exploratory if any of its attempts is tagged, and state that retries keep the tag.

### style-2-2: The "exact `chanchi models add` command" cannot be exact. Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 396-399.
* **Discrepancy Description:** `models add` requires `--cost` (`cli.py`:250). The map holds no cost tier or efforts, so the script cannot print a command that runs as written. This is the same kind of failure as round-1 design-1-3. "with the owner's variants" is undefined.
* **Rationale & Recommendation:** Write that the script "stops and prints `chanchi models add <agent:model> --cost <tier> [--efforts ...]` for the owner to complete". Replace "variants" with "cost tier and efforts".

### Nits

| Id | Lines | Problem | Fix |
| --- | --- | --- | --- |
| structural-2-1 | 487-492 | An edit left a bullet with a line holding only "from". This is a broken line, not the settled 100-column question. | Rejoin 487-492 into one normally wrapped paragraph. |
| structural-2-2 | 731, 733-736 | Risks rows 6-9 (stale snapshot, map drift, unverified benchmarks, scale) have no pointer to their detail, unlike rows 1-5. Row 731 says "(The Problem, Rollout)", which does not match the H3 title. | Add pointers: stale snapshot and scale to Phase 3 "Signal derivation"; map drift to Phase 3 "Fetch script"; unverified benchmarks to Phase 1 rule 3 and Phase 3 "Drop criterion". Change 731 to "(The Problem; Technical Plan, 'Rollout and rollback')". |
| structural-2-3 | 610, 694 | Alternatives D and N were deferred, not rejected, but still use the label **Reason for Rejection**. Alternative M uses **Status**. | Use **Status** for D and N, or add "(deferred)" to their headings. |
| structural-2-4 (also style N18) | 581-585 | Alternative A's Reason repeats its Cons almost word for word, a side effect of the structural-1-4 fix. | Shorten the Reason: "Rejected by author: a tier derived from per-token prices would misrank fixed-plan costs (see Cons)." |
| structural-2-5 (also design N6, style N1) | 690-696, 761 | Alternative N uses round-1 wording. It says `show` "reports the exploration share", but `share` is information only. The Pros say chanchi "would count exploration sessions", which `show` now does. "1-in-4 budget" does not match `max(1, floor(n / 4))`. | Reason: "`show` reports `exploratory`, `allowed` and `over_budget`." Pros: "A planner could not exceed the budget." Replace "1-in-4 budget" with "the exploration budget". |
| structural-2-6 | 294 | "Storage (decided by the author: ...)" is an inline attribution left over from structural-1-4, with no pointer. | Use "(separate table, values validated in Python; see Alternatives J and K)". |
| design-2-6 (also style N4) | 277 | `session update --tags` replaces the whole list (`record.py` 353-354), so "fixes a missed tag" can drop other tags. | Write "`session update --tags <existing>,explore` (the flag replaces the list)". |
| design-2-7 | 505, 569-570 | The rollback says "delete or empty the snapshot". An empty file breaks the test that parses an existing snapshot and asserts `schema_version == 1`. | Make the rollback "delete". |
| design-2-8 | 500-504, 710-711 | `explore_signal_stale` depends on the clock, so identical `recommend` calls give different output over time, and tests become time-dependent. Alternative P rejected randomness for the same reason. | Compute `now` in the CLI layer, pass it into `recommend()` and `hfsignals`, and state that tests inject it. |
| design-2-9 (also style N13) | 496-497, 520-523 | design-1-16 is only partly closed. The `external_signals` shape is not given for a mapped `exact` or `family` model with no counted benchmark (all rows below `HF_MIN_REPORTERS`, or `last_error` with no rows). | State: "an object with `value: null` and `benchmarks: []`; sorts as no signal". |
| design-2-10 (also style N11) | 464, 529-530 | `HF_BENCHMARKS` is first named at 529 and never defined. `notes` is not in the snapshot schema (411-428). | Name `HF_BENCHMARKS` at 464. Add `notes` to the schema example, or say "any other Hub field". |
| design-2-11 (also style N9) | 55-57 | The round-1 style-1-1 wording does not cover a candidate with no level. In that case `prior_for` uses task type and complexity (`scoring.py` 452-454). | Append "(task type and complexity when no level has sessions)". |
| style-2-3 | 100, 276, 289, 691, 728 | One concept has five names: "session taken from `explore`", "session that uses an `explore` spec", "explore session", "exploration sessions", "Explore sessions". | Define "explore session: an executor session started with `--tags explore`" once in Budget. Use only that term and the field `exploratory`. |
| style-2-4 | 728 | The Risks row gives the budget as `max(1, floor(n / 4))` without the n=1 exception. | Add "(0 when n is 1)", or align with the style-2-1 definition. |
| style-2-5 | 227-229 | With buckets sorted "highest first", "between bucket 0 and bucket 1" leaves the reader to work out the direction. | Use "sorts after bucket 1 and before bucket 0". |
| style-2-6 | 50 | The doc writes the spec as `agent:model:effort`, but the CLI accepts `agent:model[:effort]` (`cli.py`:334). | Use the optional form. |
| style-2-7 | 307, 310, 314 | "every stored value is in the taxonomy set" would accept `unknown`, which must never be stored. | Assert that stored values are in `("yes", "no")`. |
| style-2-8 | 498-504 | Three gaps in the signal-source text. An "unreadable" file maps to no `explore_signal_source` value. "reports the same" has an unclear referent. `scoring.explain()` is static today (`scoring.py`:525), and the text does not say what it newly reads. | Say "an unreadable file is reported as `missing`" (or add an `unreadable` value). Say "`chanchi scoring explain` also reports `explore_signal_source`, `generated_at` and `stale`; `explain()` gains a snapshot load". |
| style-2-9 | 493-495, 516 | The output field `peers` is not defined. | Add "`peers` is N, including the model's own repo." |
| style-2-10 | 546-547 | The proposed README text says the package "never uses the network". The design itself now claims only that it imports no network module, so this undoes design-1-12. | Use "the `chanchi` package imports no network module". |
| style-2-11 | 561-562, 750-751 | "which happens on merge" and "when it is merged" are imprecise. Nothing runs at merge time; the database migrates on the next `chanchi` call. | Use "on the first `chanchi` call after the merge". |
| style-2-12 | 443-445 | "This prevents accidents" does not say which accident. | Use "prevents writing a snapshot from another project's directory". Optionally note that the guard does not check `CHANCHI_DB` (see design-2-5). |
| style-2-13 | 13-14 | "rarely" appears twice in one sentence after the style-1-11 fix. | Use "Models the owner seldom picks ... rarely reach that threshold". |
| style-2-14 | 308-309 | "`glm-5.3-flash` reads images at every effort" reads as a factual claim about the model. | Use "for example, if a model reads images, it does so at every effort". |
