# Audit 18, Round 1 — Consolidation (`skills/skill-chanchi-item-authoring/SKILL.md`)

- **Audit ID:** 18
- **Round:** 1 (subject at `4726b09` on `feat/mvp2-s5`, `degraded: false`)
- **Outcome:** `fix`

## Seats & Votes

| Seat | Spec | Family | Verdict | Blocking | Major | Minor | Report |
|---|---|---|---|---:|---:|---:|---|
| 1 | `claude:sonnet:medium` | `anthropic` | `pass_with_fixes` | 0 | 2 | 3 | [round1-claude-sonnet.md](round1-claude-sonnet.md) |
| 2 | `agy:gemini-4-neon-high:high` | `google` | `pass_with_fixes` | 0 | 2 | 2 | [round1-agy-gemini-4-neon.md](round1-agy-gemini-4-neon.md) |
| 3 | `opencode:opencode-go/hy4-flash-free` | `tencent` | `fail` | 0 | 1 | 1 | [round1-opencode-hy4-flash-free.md](round1-opencode-hy4-flash-free.md) |

## Consolidated Findings

1. **Eval fixture leakage in `## Last step` (`S1-F1`, `S2-F1`, `S3-F1` — major):**
   - `SKILL.md` cited `python3 tests/check_items.py` and "minimal repositories", which exist only in the eval fixture's `setup.sh`, not in this repository.
   - **Fix:** Remove `python3 tests/check_items.py` and "minimal repositories"; refer generically to `scripts/check` when present, otherwise the verification checks documented in the repository's `AGENTS.md` (such as its item-naming check and `chanchi agents sync --check`).
2. **Contradictory `never commit` and unqualified working-tree instruction in `## Last step` (`S1-F2`, `S2-F2` major; `S3-F2` minor):**
   - Blanket `never commit` contradicted `SKILL.md:22,34` and `agent-chanchi-orchestrator`, and the unqualified "current working tree" omitted `AGENTS.md`'s branch-per-change rule and brief worktree/branch isolation.
   - **Fix:** Preserve brief worktree/branch precedence and `AGENTS.md`'s never-work-on-`main` rule, scope direct authoring to an already-isolated workspace without a separate brief, and defer to role commit rules (executors never commit; orchestrators commit after checks pass).
3. **`## Hook source` over-prescriptive and narrowed to check-only hooks (`S1-F3`, `S2-F3` — minor):**
   - **Fix:** Frame the layout as a suggested harness-agnostic layout, broaden the script description to any guardrail (e.g. running the repository's check command), and state that git hooks in `.githooks/` or `.git/hooks/` are not chanchi items.
4. **`## Eval source` completeness (`S1-F4`, `S2-F4` — minor) & intro redundancy (`S1-F5` — lone minor, confirmed):**
   - **Fix:** Note that optional `[judge]` must use a different model family than `[candidate]`, state the 1 regression + 1 capability default (`[]` only if none exists yet), clarify that `blind_allow` covers `setup.sh`/fixtures while `prompt.md` bans blinded words unconditionally (referencing `tests/test_evals.py`), and tighten the intro line.

## Next Step
Apply all confirmed fixes to `skills/skill-chanchi-item-authoring/SKILL.md`, remove the superseded unmerged draft row `skill-chanchi-item-authoring-4`, re-measure via `scripts/run_evals.py skill-chanchi-item-authoring --hypothesis ...` to verify lift holds without fixture leakage, commit on `feat/mvp2-s5`, and open Audit 18 Round 2.
