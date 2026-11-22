# Round 1 consolidation — global items phase-1 plan (Revision 1)

Run by hand (the `chanchi audit` commands are what this plan builds; this round is backfilled by
Task 8). Subject: `docs/superpowers/plans/2026-11-21-global-items-phase1.md` at `8c533c6`. Author:
`claude:opus:unknown`. Reports were written to private scratch paths and moved here after all three
seats voted.

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor |
|---|---|---|---|---|---|---|
| 1 | `claude:sonnet` (as `agent-chanchi-researcher`) | anthropic | pass_with_fixes | 0 | 4 | 13 |
| 2 | `agy:gemini-4-neon-high:high` (as `agent-chanchi-researcher`) | google | pass_with_fixes | 3 | 7 | 4 |
| 3 | `opencode:opencode-go/minimax-m3` (as `agent-chanchi-researcher`) | minimax | pass_with_fixes | 2 | 4 | 4 |

Outcome: **fix** (no approval: every vote carries blocking or major findings). Not degraded.
Seat 1 ran as a Claude Code subagent (effort not set); seats 2 and 3 ran headless with the design's
launch templates.

## Consolidated findings and how Revision 2 resolves them

| # | Finding | Raised by | Resolution in Revision 2 |
|---|---|---|---|
| 1 | Bare `chanchi` in a worktree runs `main`'s code | 1 (G1), 2 (F9) | Global constraint: `uv run chanchi` in worktrees; every verification command updated |
| 2 | `sync.py` cannot import `subprocess`; `sync_dir` has no injectable root | 2 (F1), 1 (G10) | `sync_dir(env, *, repo_root)` via `projects.main_worktree`; tests pass a temporary worktree |
| 3 | `agents link --user` default root unstated; run elsewhere it would drop chanchi's agents | 2 (F2), 1 (G3) | D4: root defaults to chanchi's repository; manifest entries carry `root`; removal only within the same root |
| 4 | `render()` signature change contradicts "existing tests stay green" | 2 (F3), 1 (G7) | `render_by_kind(source, header)`; `render(source)` kept as a wrapper |
| 5 | Backfill cannot force historical seats by marking seats unavailable | 3 (R1-02), 2 (F4), 1 (G6) | Task 8 step 2: scratch `CHANCHI_SYNC` roster in history's order; stop instead of inventing rows |
| 6 | Round 1-2 counts not machine-readable | 3 (R1-01), 2 (F4), 1 (G13) | D9 and Task 8's table of counts (open findings after re-check, partials at original severity) |
| 7 | SQL `LIKE '%/p%'` is not last-segment; D7 overstated; prefix reading of opus/sonnet unstated | 2 (F5), 3 (R1-04), 1 (G12) | Recursive-CTE last segment; multi-segment test ids; D7 states the prefix rule |
| 8 | Seat filling can seat a spec twice; seated unknown-family models need the hint; quorum close details | 2 (F6) — lone, **confirmed** | `already_seated` exclusion; hint on seated and skipped unknown families; quorum closes round and audit, also in `next_round` |
| 9 | `--change` without a project; `--project` parser clash; refusal codes | 2 (F7), 3 (R1-03), 1 (G14) | D5; `leaf(..., project=True)` only on `audit open`; `invalid_transition` for lifecycle refusals |
| 10 | Round-3 cap overwrites a quorum escalation; dissent on a closed round | 2 (F8), 1 (G8) | Ordered rules with quorum first; cap only on `fix`/`rework`; dissent refused on a closed round |
| 11 | S6 names commands that do not exist and could write the operational DB | 3 (R1-05), 2 (F10), 1 (G11) | Task 7 uses the three verified launch forms, `agy agents`, `opencode debug agents`; no `audit open` |
| 12 | Global constraints contradict Tasks 7 and 8 (real home, operational DB) | 3 (R1-06) — lone, **confirmed** | Constraint scoped to executor sessions; orchestrator steps say where they act |
| 13 | Existing `test_db.py` hardcodes version 4/5; `OPERATIONAL_TABLES` lacks the new tables | 2 (F11), 1 (G15) | Task 1 step 2 |
| 14 | opencode read-only wrapper denies writing the auditor's report | 1 (G4), 2 (F12) | Auditor body: on opencode, write the report with the shell |
| 15 | `test_items.py` fails when docs name the auditor or skill before S5 | 1 (G2), 2 (F13) | Global constraint: S1-S4 docs use `<agent>`; S5 may name them |
| 16 | `launch` interface named two ways; `effort=None` | 1 (G9), 2 (F14) | One `harnesses.launch(key, *, agent, model, effort, prompt)`; effort rules per harness |
| 17 | `link_user` must create parents; `--check`/`--remove` exclusivity; `--check` scope | 3 (R1-09), 2 (F14) | Stated in Task 5 |
| 18 | item-authoring skill does not document `install` | 3 (R1-10), 2 (F14) | S5 updates *Agent source* |
| 19 | `test_all_skills_exist` order | 3 (R1-08) — lone, **confirmed** (minor) | New skill goes first |
| 20 | `sync_dir` with a non-editable install | 3 (R1-07) — lone, **confirmed** (minor) | D2: `None`, built-in roster |
| 21 | S6 "nothing depends on it" but Task 8 waited for it | 1 (G5) — lone, **confirmed** (minor) | Task 8 depends on S5 only |
| 22 | S1 complexity is high; S4 is not a refactor | 1 (G16) — lone, **confirmed** (minor) | S1 high (re-run `recommend`, chosen claude:sonnet:high); S4 `business-logic` |
| 23 | Second phase-1 signal and lessons #1-#3 not addressed | 1 (G17) — lone, **confirmed** (minor) | "Out of this plan" paragraph in Task 8 |
| 24 | S3/S4 merge risk lists only `cli.py` | 1 (G15) — lone, **confirmed** (minor) | Risks and Sessions name `FEATURE_MAP.md` and `README.md` |

No lone finding was rejected.
