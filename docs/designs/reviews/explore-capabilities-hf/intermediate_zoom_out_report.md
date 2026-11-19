# Intermediate Zoom Out Report (Stage 8)

**Target:** `docs/designs/explore-capabilities-hf.md` (whole document, 1325 lines)
**Reviewer:** `egm-zoom-out`, fresh context
**Verdict:** The design still solves the stated problem. Five critic rounds added mechanism at the edges, mostly for Phase 3 or rare cases. 0 Blocker, 7 Major, 6 Nit. Goals G1-G7 stay satisfied if the cuts are adopted.

## Findings and AI suggestions

| Id | Severity | Finding | Proposed change | AI Suggestion |
| --- | --- | --- | --- | --- |
| zoom-8-1 | Major | `n_task_type` lowest first spreads trials thin (about 45 explore sessions per task type before any tier-1 model is eligible) and contradicts rule 4's "add up toward eligibility" | Sort `n_task_type` highest first among non-deprioritized specs (depth-first), so models get finished | PROPOSE FIX |
| zoom-8-2 | Major | Phase 1 ships the signal bucket, the `signal_for` hook and the reserved slot, which can never act without Phase 3 | Phase 1 sorts by (deprioritized group, `cost_tier`, `n_task_type`, `spec`); the bucket key and the lookup move to Phase 3 | PROPOSE FIX |
| zoom-8-3 | Major | The reserved no-signal slot rarely fires once cost sorts first, and costs three guards and tests | Cut; add to Future Improvements | PROPOSE FIX |
| zoom-8-4 | Major | `hint_commands` puts runnable `--capability` commands in front of agents that the skill forbids to run them; the skill teaches agents to act on hints | Remove `hint_commands`; `missing` with `value: unknown` plus the skill rule is enough | PROPOSE FIX |
| zoom-8-5 | Major | File 17 adds a `--capability` example to the skill's catalog maintenance section while the skill forbids it | Example only in the README; the skill states the prohibition | PROPOSE FIX |
| zoom-8-6 | Major | The fetch script's catalog access (subprocess, DB guards, `XDG_DATA_HOME` path logic, `.backup` copy, 2 Risk rows, 4 tests) buys two small benefits | Script becomes map plus network only. Keep vision suggestions computed from the snapshot alone: print a line for every mapped model tagged `image-text-to-text`, for the owner to compare with the catalog | PROPOSE FIX (modified: keep suggestions without catalog access) |
| zoom-8-7 | Major | Staleness adds three keys to every result, `now` plumbing, `HF_STALE_DAYS`, a non-static `explain()`, and a dead `now` parameter in Phase 1 | Keep `explore_signal_source` and `explore_signal_generated_at`; drop `explore_signal_stale`, `HF_STALE_DAYS` and `now` | PROPOSE FIX |
| zoom-8-8 | Nit | `weak_start` and `red_flag_low_data` mean the same to a planner, plus an internal sub-order | One field `deprioritized`: `null`, `weak_start` or `red_flag_low_data` (the latter wins when both apply); the group sorts by the normal keys | PROPOSE FIX |
| zoom-8-9 | Nit | `share` is derived and adds a null case | Drop `share` | PROPOSE FIX |
| zoom-8-10 | Nit | The `· explore: <spec>` protocol suffix repeats the tag | Keep: the protocol line is the human-readable trail in the change plan, and it carries the owner-override reason for S1-S3 | DECLINE |
| zoom-8-11 | Nit | The high-complexity rule overlaps the skill's existing weak-evidence line | Extend the existing line instead of adding a rule | PROPOSE FIX |
| zoom-8-12 | Nit | The cwd guard is "not a security boundary" | Keep: the owner required that the fetch run only from this project, and CUJ 4 depends on it; the cost is one check and one test | DECLINE |
| zoom-8-13 | Nit | File 5 omits the marks that the cross-cutting list assigns to Phase 1 | Add `deprioritized` to file 5 (follows zoom-8-8) | PROPOSE FIX |

## Author decision

Accepted as suggested on 2026-11-18: every PROPOSE FIX applied, zoom-8-10 and zoom-8-12 declined.
Applied with 56 edits across Overview, CUJ 3, Technical Plan (Phases 1-3, cross-cutting,
rollout), Risks, Future Improvements and the Detailed Implementation Plan (files 2, 3, 5, 13,
16, 17, 19-22, 24, 25, 29 and the Verification Plan).
