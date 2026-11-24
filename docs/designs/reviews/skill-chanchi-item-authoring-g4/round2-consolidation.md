# Audit 18 — Round 2 Consolidation (`skills/skill-chanchi-item-authoring/SKILL.md`)

- **Audit ID:** 18 (`kind: other`, `change: chanchi-agents-phase2`)
- **Subject:** `skills/skill-chanchi-item-authoring/SKILL.md` at commit `691472b` (`feat/mvp2-s5`)
- **Degraded:** `false` (3 distinct model families: `anthropic`, `google`, `tencent`)
- **Outcome:** **`accepted`** (3/3 `PASS`, 0 blocking, 0 major)

## Seats & Votes

| Seat | Auditor | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---|---|---|---|
| 1 | `claude:sonnet:medium` | `anthropic` | `pass` | 0 | 0 | 1 (optional) | `round2-claude-sonnet.md` |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass` | 0 | 0 | 0 | `round2-agy-gemini-4-neon.md` |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `pass` | 0 | 0 | 0 | `round2-opencode-hy4-flash-free.md` |

## Round 1 Findings Re-Check

All Round 1 findings across all three seats are `RESOLVED`:
- **Fixture-specific check leakage (`python3 tests/check_items.py` / "minimal repositories"):** Removed; replaced with generic `scripts/check` / `AGENTS.md` check guidance. Re-measured cleanly via `run_evals.py --hypothesis` (`skill-chanchi-item-authoring-4`: `verdict=kept`, `runs=6`, `regression=3/3`, `capability=1.00`, `lift=+0.33`, tree hash `cc29cabd93da0abf723ce2a5dd68ffcc3c119e55`).
- **Commit / branch / worktree rules (`## Last step`):** Blanket `never commit` removed; brief worktree/branch precedence and `AGENTS.md` never-work-on-`main` restored; direct authoring scoped strictly to an already-isolated workspace with no separate brief file; role-based commit rules explicit.
- **`## Hook source` framing:** Framed as suggested harness-agnostic layout; script generalized beyond check-only hooks; `.githooks/` softened to "git hooks in `.githooks/` or `.git/hooks/` are not chanchi items".
- **`## Eval source` precision:** Added cross-family judge rule (`chanchi.taxonomy.family_for`), `prompt.md` vs `setup.sh`/fixtures `blind_allow` distinction, and 1 regression + 1 capability default without duplicating the `Layout` table.

## Lone Findings & Dissent Decisions

| Seat | Finding | Severity | Decision | Evidence |
|---|---|---|---|---|
| 1 | `N1`: no hook exists yet so suggested layout is not validated by a test | `minor` | `rejected` | Seat 1 explicitly marks `N1` optional with fix `"None required. The text is now labelled as a suggestion"`; `hooks/` is absent by design (`docs/designs/chanchi-agents-mvp.md:85`). |

## Next Action

Archive Round 2 reports and consolidation on `feat/mvp2-s5`, rebase onto `main`, run `scripts/check`, and merge `feat/mvp2-s5` (`--no-ff`) into `main`.
