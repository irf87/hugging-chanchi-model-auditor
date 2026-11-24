VERDICT: PASS WITH FIXES

Subject: `docs/superpowers/plans/2026-11-23-cursor-harness.md` at commit `1775ccb` (branch `docs/cursor-harness-plan`), checked against accepted design `docs/designs/cursor-harness.md`, brief `docs/designs/cursor-harness.brief.md`, Round 1 consolidation, the live code at that commit, and AGENTS.md. Audit 15, Round 2. Working tree is clean at `1775ccb`. No other seat's Round 2 report was read; no live `agent` or `claude` call was made.

## Findings table

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| F1 (RESOLVED) | major | Plan Task 1.8, line 141 | Round 1 found the `valid_values` assertion update missing. | Revision adds: update `info.value.valid_values` (`tests/test_modelspec.py:52`) to `["claude", "agy", "opencode", "cursor", "human"]`. Verified: `taxonomy.AGENTS` becomes `("claude","agy","opencode","cursor")`, `ALL_AGENTS = AGENTS + ("human",)`, so the expected list is correct. | None — applied. |
| F2 (RESOLVED) | minor | Plan Task 1.10, line 150 | Round 1 found the custom roster ambiguous. | Revision passes the explicit roster `[*sync.BUILTIN_ROSTER, {"harness":"cursor","model":"gpt-5.4-high","effort":None}]` and states seats are `anthropic`, `google`, `openai`. Verified against `_fill`/`is_degraded`: opencode drops out via `which_with("claude","agy","agent")`, the 2nd agy (google) is not re-seated, and `gpt-5.4-high` infers `openai` via `FAMILY_PREFIXES`; `degraded is False` holds. | None — applied. |
| F3 (RESOLVED) | minor | Plan "Pre-Merge Orchestrator Live Verification", smoke 3b, lines 174-183 | Round 1 found the smoke setup under-specified and hedged. | Revision seeds `cursor:auto` (`models add --agent cursor --model auto --cost 1`, family null), writes `auditors.toml` with `model = "auto"`, extracts the emitted launch line, names one concrete setup (`agents link --user` into scratch HOME), adds a single auth fallback with cleanup, and keeps the exit criteria (exit 0, `VERDICT: PASS` report, clean scratch git status). Hedges removed. | None — applied. |
| N1 (new, OPEN) | minor | Plan "S1 Verification Commands (exact)", item 3, line 164 | The scratch `auditors.toml` holds only the single Cursor entry, yet the step asserts `audit open` "prints the Cursor `launch` line". One roster entry seats one auditor; `MIN_VOTERS = 2` escalates the round and `_finalize_round_open` renders seats with `launch=None`, so no launch line is emitted. The executor following these "exact" commands will not see the stated result. | `audits.py:24` `MIN_VOTERS = 2`; `audits.py:363-371` sets `outcome="escalated"`, `escalation="quorum"` when `len(active) < 2` and calls `_seat_view(r, launch=outcome_val is None)`; `audits.py:239-259` builds `launch` only when `launch=True`. `sync.roster()` replaces rather than extends the built-in roster when `auditors.toml` exists. Smoke 3b (line 177) already recognizes this with "plus two other catalog rows so quorum >= 2 holds". | Mirror smoke 3b's fix into S1 verification item 3: seed two more catalog rows and matching `[[auditor]]` entries on the scratch DB/SYNC so at least two seats are active, then assert the Cursor seat's `launch` line (or reword the step to assert the seat is assigned with `launch: null` and `outcome: escalated`). |

## Re-check of Round 1 findings (done first)

- **F1 — RESOLVED.** The major gate-breaking gap is closed explicitly at line 141, and the expected `valid_values` list matches the post-change `taxonomy.ALL_AGENTS` ordering confirmed in `taxonomy.py:8-12` and `modelspec.py:30`.
- **F2 — RESOLVED.** Line 150 now names the exact roster. I re-traced `_candidates`/`_fill` (`audits.py:145-232`) with `cat`'s seeded claude:sonnet and agy:gemini-4-neon-high plus the new cursor:gpt-5.4-high: three distinct known families seat, so `is_degraded` is false and the asserted launch line matches `_seat_view` (`audits.py:239-259`) with `PROMPT="<prompt>"`, `REPORT_DIR="<report-dir>"`, `AUDITOR_AGENT="agent-chanchi-auditor"`.
- **F3 — RESOLVED.** Smoke 3b is now a numbered, concrete procedure with a single named setup method and a restricted fallback; every command uses `uv run chanchi` as also confirmed by the other seats' finding 185.

All Round 1 findings are RESOLVED; none is OPEN or PARTIAL, so none counts toward this round's verdict.

## New findings

- **N1 (minor, OPEN):** The only new issue. The revision sharpened S1 verification item 3 into an explicit claim that `audit open` "prints the Cursor `launch` line" while leaving a single-row roster that cannot produce one. This is the same quorum mechanism smoke 3b handles correctly; S1 verification was not updated in step. It is a clarification/verification defect, not an implementation blocker, and is fixed by aligning item 3 with smoke 3b's two-extra-rows wording. Registration of the other seats' confirmed lone findings (182-188) was also checked in the diff and applied; no defect was introduced there.

## Coverage re-confirmation

Design requirements and non-goals remain fully reflected in the plan: no SQL migration / `FAMILY_PREFIXES` change, no operational DB or `auditors.toml` rows, no `.cursor/skills` duplicate links, no claude CLI, no MVP2 branches / `run_evals.py`. Cited line numbers and counts still reproduce (`tests/test_harnesses.py:73-96,109,113,115`; `tests/test_modelspec.py:51-52`; `tests/test_agents_sync.py:81,200,204,222-223,229,269-270,303,312-315`; `tests/test_mirror.py:135,160-164,182,244,486,493`; `tests/test_inventory.py:117`; `FEATURE_MAP.md:123,134,306,476,557-558,609-614`; AGENTS.md 141 lines; `AUDIT_SUBJECT_KINDS` includes `other`; `harnesses.home_dir/user_agent_path/installed` signatures accept the plan's kwargs). Only the plan and review reports changed at `1775ccb`, so Round 1's source-level checks remain valid.

## Summary

All three Round 1 findings are RESOLVED with direct evidence at `1775ccb`. One new minor finding (N1) remains open: a verification step expects a launch line that quorum escalation suppresses. Counted open findings: 1 minor, 0 major, 0 blocking. With N1 applied, the plan faithfully realizes the accepted design and is implementation-ready. Verdict: PASS WITH FIXES.
