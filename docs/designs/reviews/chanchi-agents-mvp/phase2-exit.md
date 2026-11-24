# Phase 2 exit signal (read 2026-11-24)

**Signal** (design `docs/designs/chanchi-agents-mvp.md` Revision 4, *Adoption plan*, phase 2), read
directly from `evals/ledger.tsv` and the operational database by
`uv run python scripts/run_evals.py --signal` at `main` commit `2a115c1`:

1. If a signal skill (`signal = true` in `eval.toml`) opts into `rubric.md` + `[judge]`, its judge
   is calibrated (`total >= 6`, `agree >= total - 1`, and label contrast). Code-graded evals
   require no judge calibration — all three phase-2 signal skills run code-graded only (owner
   decision Option B, 2026-11-24).
2. Each signal skill's regression cases pass 100% of executed runs in the with-skill arm (`1/1` by
   default, `3/3` when confirmed by adaptive repeat).
3. Each signal skill's capability median with the skill beats the cached arm without it (matching
   `candidate` and `cases_sha`).
4. No pending lesson (`chanchi lesson export --all --status pending --limit 1000`) with 2 or more
   occurrences proposes a prose rule (`target_kind` outside `tool`, `hook`, `permission`).

## Command output (`uv run python scripts/run_evals.py --signal`)

Run on `main` at `2a115c1` (2026-11-24, 0 headless model runs):

```json
{
  "items": {
    "skill-chanchi-item-adoption": {
      "in_signal": false,
      "judge": "none",
      "calibrated": null,
      "regression": {"passed": 1, "runs": 1, "met": true},
      "capability": {"with": 0.75, "without": 0.25, "met": true}
    },
    "skill-chanchi-item-authoring": {
      "in_signal": true,
      "judge": "none",
      "calibrated": null,
      "regression": {"passed": 3, "runs": 3, "met": true},
      "capability": {"with": 1.0, "without": 0.67, "met": true}
    },
    "skill-chanchi-lessons": {
      "in_signal": true,
      "judge": "none",
      "calibrated": null,
      "regression": {"passed": 1, "runs": 1, "met": true},
      "capability": {"with": 1.0, "without": 0.0, "met": true}
    },
    "skill-chanchi-session-audit": {
      "in_signal": true,
      "judge": "none",
      "calibrated": null,
      "regression": {"passed": 1, "runs": 1, "met": true},
      "capability": {"with": 1.0, "without": 0.5, "met": true}
    }
  },
  "lessons": {"met": true, "flagged": []},
  "met": true,
  "reason": null
}
```

## Ledger summary (`evals/ledger.tsv`, 13 rows)

Candidate across all rows: `agy:claude-sonnet-5-5-low:low` (`anthropic` family, code-graded).

| Skill | Signal (`eval.toml`) | Current `item_sha` | Verdict | Regression | Capability (`with` vs `without`) | Lift | Triggers |
|---|---|---|---|---|---|---|---|
| `skill-chanchi-session-audit` | `true` | `465113c9...` | `baseline` | `1/1` (`stop-plan-gap:1.00`) | `1.00` vs `0.50` (`false-claim`) | `+0.50` | `4/4` |
| `skill-chanchi-lessons` | `true` | `efe7be79...` | `baseline` | `1/1` (`record-failure:1.00`) | `1.00` vs `0.00` (`review-check-first`) | `+1.00` | `4/4` |
| `skill-chanchi-item-authoring` | `true` | `cc29cabd...` | `kept` (G4 H1) | `3/3` (`new-skill:1.00`, up from `0/3`) | `1.00` vs `0.67` (`new-hook`, up from `0.67`) | `+0.33` | `3/4` |
| `skill-chanchi-item-adoption` | `false` (backlog) | `bfec1f50...` | `baseline` | `1/1` (`propose-new:1.00`) | `0.75` vs `0.25` (`retired-entry`) | `+0.50` | `4/4` |

Notes:
- `skill-chanchi-item-authoring` initially failed `new-skill` (`0/3`) and tied `new-hook` (`0.67` vs
  `0.67`) at baseline (`c690e4c4...`). Hypothesis H1 (adding `## Eval source`, `## Hook source`,
  and role-safe `## Last step` guidance; audited in chanchi audit 18, rounds 1–2, 3/3 `PASS` across
  `anthropic`, `google`, `tencent`) lifted it to `3/3` regression and `1.00` capability (`+0.33`
  over `without`).
- `tests/test_evals.py` `GRANDFATHERED` holds only the 3 pre-phase-2 skills not evaluated in phase
  2: `skill-chanchi-audit-rounds`, `skill-chanchi-model-selection`, `skill-chanchi-verify`.
- `scripts/check` on `main` at `2a115c1`: `ruff check` passed and `1026 passed` in pytest.

## Condition 4 (pending lessons)

Read on 2026-11-24 via `chanchi lesson export --all --status pending --limit 1000` (`chanchi lesson
summary`: 13 pending, 1 rejected, 0 approved/postponed/duplicate). Every pending lesson has
`occurrences: 1`, so `lessons.flagged` is `[]` and `lessons.met` is `true`.

## Eval run budget tally

Approved phase-2 ceiling: **300 headless runs** (owner decision 2026-11-23).

| Stage | Headless runs | Notes |
|---|---:|---|
| Pre-Rev-5 (S1 research + Rev 4 baselines & smoke) | ~160 | Prior to Rev 5 cost-cut amendment |
| G1b smoke (`agy:claude-sonnet-5-5-low` + `agy:gemini-4-hydrogen-high`) | 3 | 1 capability + 1 judge + 1 trigger |
| Rev-5 G2 baselines (4 skills, with judges & triggers) | 32 | Valid `triggers` & `item-adoption` rows reused in Rev 6 |
| Rev-5 G3 calibration collection (before Option B pivot) | 32 | Unused sheets under `~/.local/share/chanchi/evals/` removed |
| Rev-6 code-only G2 baselines (`session-audit`, `lessons`, `item-authoring`) | 11 | Reused 16 cached `triggers` + 3 `item-adoption` rows |
| G4 hill climb on `skill-chanchi-item-authoring` | 13 | 1 aborted on quota reset + 6 draft H1 + 6 clean H1 after Audit 18 R1 |
| **Total spent** | **~251 / 300** | **~49 runs under budget** (0 Claude CLI eval runs spent in Rev 5/6) |

## Phase 2 audits

- Audit 12 (plan Rev 1–4, 3 rounds, escalated to owner -> owner accepted Rev 4 on 2026-11-23)
- Audit 16 (design Rev 3 + plan Rev 5 eval cost-cut, 2 rounds, `accepted`, 3/3 approvals, `degraded: false`)
- Audit 17 (design Rev 4 + plan Rev 6 code-only phase-2 evals, 2 rounds, `accepted`, 3/3 approvals, `degraded: false`)
- Audit 18 (`skill-chanchi-item-authoring` G4 edit, 2 rounds, `accepted`, 3/3 `PASS`, `degraded: false`)
- Phase 2 closeout reconciliation audit: recorded in `phase2-close-round*-*.md` in this folder.
