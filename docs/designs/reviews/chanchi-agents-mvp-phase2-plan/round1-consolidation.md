# MVP phase 2 plan — audit round 1 consolidation

- Subject: `docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md` at `972dec6` (Revision 1);
  chanchi audit 12, kind `other`, round 1, **degraded** (anthropic, google, google). Seat 3 was
  refilled from agy gpt-oss to agy gemini-4-hydrogen by the owner's instruction (gpt-oss is a
  fallback only).
- Seat 1's first run had no shell permission and was stopped unvoted; the seat re-ran with Bash
  allowed (change `launch-permissions`). Only the re-run is voted.
- Outcome: `fix` (one `fail`; open blocking and major findings). All fixed in Revision 2.

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass_with_fixes | 0 | 7 | 6 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 4 | 5 | 5 |
| 3 | agy:gemini-4-hydrogen-high:high | fail | 3 | 2 | 3 |

Seat 2 voted `PASS WITH FIXES` while listing 4 blocking findings; the vote is recorded with its
counts, so it is not an approval.

## Consolidated findings (two or more seats) — fixed in Revision 2

| Finding | Seats | Fix |
|---|---|---|
| D11 makes the gate red from S2 until S4 and S5 land | S2-F1, S3-F1 | D11: `GRANDFATHERED` starts with all seven skills; S4 and S5 remove theirs; D18 merge order |
| The lesson-review bullet and `review-check-first` need a `target_kind` change the CLI forbids | S2-F2, S3-F2 | D21: replacement lesson with `replaces`, original reviewed `duplicate --of`; skill bullet and grader rewritten |
| `evals/` files break ruff T20 and `test_references_resolve` (`skill-chanchi-proof`) | S2-F4, S3-F3, S1-F2 | D19 (per-file ignore, reference check skips cases and triggers); trigger prompts reworded |
| No scratch `CHANCHI_SYNC`: item adoption would read and write the real `SYNC` | S2-F3, S3-F4 | D20, D22; S3 tests it |
| `claude -p --agent` on a `scope: main` wrapper (initialPrompt) and `skills:` preload unverified; `Skill` tool not allowed | S2-F6, S3-F5, S1-F8 | D3 renders candidates as `scope: both`; S1 verifies preload, `Skill`, `--add-dir` writes |
| Judge `scope: subagent` compiles to `mainAgent: false` on agy | S2-F5, S1-F8 | D12: `scope: both` |
| `tree_hash` must recurse into subdirectories; unstaged refusal belongs to the CLI; stage before a run | S2-F8, S3-F6, S1-F13 | D10, G2 |
| Design amendments listed inconsistently; executors told the design wins | S2-F10, S3-F8, S1-F1 | Spec paragraph: numbered decisions take precedence until G5; one list (line 31) used by G5 |
| No way to re-judge after a rubric rewording | S3-F8, S1-F4 | D14 `--rejudge` over all baseline outputs; rows committed after calibration |

## Lone findings — decisions (each confirmed against the subject or the code)

| Finding | Sev. | Decision | Evidence / fix |
|---|---|---|---|
| S1-F3 runner contract missing | major | confirmed | Rev. 1 D7 gives only `grade.py <workdir>`; D22 added |
| S1-F4 baseline committed before calibration | major | confirmed | Rev. 1 G2 before G3; D14, G2-G3 |
| S1-F5 no path for failing regression cases or ceiling | major | confirmed | Rev. 1 D17; D17 rewritten |
| S1-F6 skill and wrapper cannot be blind | major | confirmed | `references/rubric.md` in the session-audit skill; D6 exemption |
| S1-F7 calibration label contract | major | confirmed | Rev. 1 D14; label against rubric only, arm hidden |
| S2-F7 smoke row, signal condition 4, all-N/A sampling, ledger formats | major | confirmed | `--no-ledger`, D9, D14, D15 |
| S2-F9 pytest unavailable in the synthetic repository | major | confirmed | S5 uses `tests/check_items.py` |
| S1-F9, S1-F10, S1-F11, S1-F12 | minor | confirmed | Sessions note, risk row, D17 budget recount, D9 triggers semantics |
| S2-F11, S2-F12, S2-F13, S2-F14 | minor | confirmed | `taxonomy.family_for`, static blinding check, agy 1.5.15, setup `models add` / explore tag / README |
| S3-F7 agy trust in temporary folders | minor | confirmed | S1 check, S3 fallback, risk row |
