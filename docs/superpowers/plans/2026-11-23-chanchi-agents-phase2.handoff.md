# chanchi Agents — MVP Phase 2: handoff (2026-11-23)

The orchestrating conversation stopped here at the owner's request to save Claude quota. This file is
what the next session needs; it supersedes nothing in the plan
(`2026-11-23-chanchi-agents-phase2.md`, Revision 4) except where the owner decides the first task below.
Resume with `chanchi show chanchi-agents-phase2` and this file.

## Where things are

| Item | State |
|---|---|
| Phase 1 close | Done, audit 11 accepted, design status line updated |
| Plan | Revision 4 merged, audit 12 escalated at round 3, accepted by the owner |
| `launch-permissions` (launch lines carry permission flags) | Merged, audit 13 accepted |
| S1 research (harness isolation facts) | Accepted; facts folded into the S3 brief and `scripts/run_evals.py` |
| S2 judge agent, `tests/test_evals.py`, ledger check | Merged (`tree_hash` fixed to the git index) |
| S3 runner `scripts/run_evals.py` | Merged; `fix/eval-redact` merged after the G1 smoke run |
| S4 evals session-audit + lessons, lesson review question | Branch `feat/mvp2-s4` (worktree `.claude/worktrees/chanchi-p2s4`), not merged |
| S5 + S6 evals item-authoring + item-adoption, authoring rule | Branch `feat/mvp2-s5` (worktree `.claude/worktrees/chanchi-p2s5`), not merged |

Both branches are rebased on `main`. Never merge `main` into them: the `pre-merge-commit` hook runs the gate, which
stays red there until their baseline ledger rows exist (plan D18 was wrong on this; incident recorded).

## Measurements so far (uncommitted ledger rows in the worktrees)

| Skill | With | Without | Regression | Triggers | Note |
|---|---|---|---|---|---|
| item-adoption | 0.75 | 0.50 | 3/3 | 4/4 | complete; no judge (D16) |
| lessons | 1.00 | 0.62 | 5/6 | 3/4 | complete; one judge FAIL on criterion 4 (prose instead of a check) |
| session-audit | — | — | — | — | redo: grader `stop-plan-gap` fixed (`not_rejected`); stopped at run 12/18 |
| item-authoring | — | — | — | — | redo: capability cases replaced (ceiling at 1.0 vs 1.0, owner decision); never started |

Weaknesses found for the hill climb: lessons regression `record-failure` (criterion 4, 1 of 3 runs), item-authoring
regression `new-skill` (the candidate never creates the skill's eval, 0 of 3). About 160 of the approved 300 headless
runs are spent (including runs lost to two Claude 5-hour limits).

## First task: cut the eval cost (owner, 2026-11-23)

The owner judged the protocol unviable: about 160 of 300 runs for three skills, and worse once projects adopt it. The
next session proposes a cheaper protocol as a design amendment (audited like any rule change) before running anything.
Starting proposal, to be checked against the design's *Layer 2* and the measurements above:

1. **One run per case by default**; repeat a case (up to 3) only when its result differs from the previous ledger row
   for that case. Today: 3 runs always.
2. **The without-skill arm is measured once per frozen case set** and reused until the cases change; a skill change
   re-runs only the with-skill arm. Today the baseline runs both.
3. **Triggers run only when the skill's `description` changes**, not on every measurement.
4. **Judge only capability cases**, and only on runs whose code graders passed (a run already failing needs no judge).
5. **Fewer cases**: 1 regression + 1 capability per skill to start; add cases only when a real failure shows a gap.
6. **Cheaper or other-quota candidates**: run candidates on agy with `claude-sonnet-5-5-*` (same family, agy's quota,
   proposed to the owner and not yet decided), at low effort; cap turns if the CLI allows it (UNVERIFIED).
7. **Calibration**: keep the owner's labels but allow 6 samples per rubric (agreement ≥ 5) for small skills.

Rough cost per skill change with 1-6: 2 with-skill runs + at most 1 judge run, about 3 runs instead of 24-40. A first
baseline per skill: about 8 runs instead of 40. The same caps then apply when chanchi helps a project evaluate its own
items (MVP TODO 4).

## Remaining steps after the cut is decided

1. Amend the design and the plan (D5, D9, D14 and the run counts), audit them (`skill-chanchi-audit-rounds`).
2. Re-run the session-audit and item-authoring baselines with the new protocol (lessons and item-adoption baselines
   may be kept or redone under it; decide in step 1).
3. G3 calibration: the owner labels the sheets (`run_evals.py <item> --calibration-sheet`, then `--calibrate`);
   the lessons sheet already exists at `~/.local/share/chanchi/evals/skill-chanchi-lessons/calibration-sheet.md`.
4. Commit the ledger rows and `calibration.tsv` on each branch, merge `feat/mvp2-s4`, rebase `feat/mvp2-s5`, merge.
5. G4 hill climb for the two weak regressions; each kept skill change is audited.
6. G5: `run_evals.py --signal`, `docs/designs/reviews/chanchi-agents-mvp/phase2-exit.md`, design status line and
   amendments (audited), `chanchi change close chanchi-agents-phase2`.
7. Lessons from this conversation, recorded by the next orchestrating session (`skill-chanchi-lessons`):
   - a launch line printed by chanchi gave headless claude no permission to run commands, so auditors could not verify
     facts (fixed in code by `launch-permissions`; the rule: a launch line must grant what the role's brief asks for);
   - the plan told the orchestrator to merge `main` into branches whose gate is red by design, which the hook blocks;
   - eval cost was planned per skill without a per-change budget, so the protocol could not scale (see the first task).
