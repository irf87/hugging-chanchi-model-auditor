VERDICT: PASS

## Scope

Round 2 re-audit of `docs/designs/cursor-harness.md` at commit `17eab73` (branch `docs/cursor-harness-design`), against `docs/designs/cursor-harness.brief.md` and the codebase at the same commit, plus local CLI facts and AGENTS.md rules. I re-checked only my own Round 1 findings (`round1-opencode-hy4-flash-free.md`, F1–F6); no other seat's Round 2 report was read. No live LLM calls on `agent` or `claude`; no repository file was edited. All claims below were re-derived from `git show 17eab73:<path>` local reads.

## Round 1 findings — re-check (first)

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|----|--------------------------------|-------|---------|----------|-----|
| F1 | major — RESOLVED | Adopt bullet & Technical Design 2 `_cursor()` | Round 1: `readonly: true` was attributed to the bundled `create-subagent` skill as a documented, Cursor-enforced key, overstating a primary-source fact on a safety property. | Revision 2 Adopt bullet now states the bundled `create-subagent/SKILL.md` "documents only `name` and `description` and does not list `readonly`", calls Canary 3 the "sole" local verification, quotes it verbatim (*"Ask mode also forbids creating or modifying files, so `blocked.txt` was not created."*), labels the key "undocumented ... subject to recheck on Cursor upgrades", and keeps a `readonly: true` emission unit test plus smoke test 3a. | Applied; no further action. |
| F2 | major — RESOLVED | Verification Plan, automated-gate list | Round 1: plan omitted shared tests that break once `cursor` joins `harnesses.KEYS`, so the promised gate would be red. | Revision 2 now enumerates: split catch-all `else:` in `test_launch_carries_permission_flags_and_add_dirs` (`lines 73–96`) into explicit `elif key == "opencode"` / `elif key == "cursor"`; `test_agents_sync.py` kind set (`line 204`); `test_mirror.py` kind/skipped/count/index assertions (`135, 160–164, 182, 244, 486, 493`); `test_audits.py` cursor seat with a dedicated `which` recognizing `agent`. Cross-checked against the tree (`harnesses.py` catch-all `launch()` ending, `audits.py:157` hint, `agents_sync.py:172` `render_by_kind`, `items.py:758`). | Applied; no further action. |
| F3 | minor — RESOLVED | Technical Design 1 `home_dir()` snippet | Round 1: no insertion point given; placing cursor after the opencode env fallbacks would redirect all cursor folders. | Snippet now shows the cursor branch between the `agy` check and the `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` fallbacks, with prose "before the ... fallbacks so those env vars never redirect Cursor's home folder". Verification Plan adds `home_dir("cursor")` test with both env vars set. Matches `src/chanchi/harnesses.py` fallback order. | Applied; no further action. |
| F4 | minor — RESOLVED | Technical Design 1 launch line; smoke test 3b | Round 1: `--workspace` dropped without stating the cwd precondition, while the role path is relative. | Added "Working-directory precondition" paragraph: `--workspace` defaults to cwd, caller runs from repo root, relative `.cursor/agents/<agent>.md` resolves there, and `~/.cursor/agents/<agent>.md` covers consumer projects — verified in pre-merge smoke test 3b. | Applied; no further action. |
| F5 | minor — RESOLVED | Adapt "read-only profile in headless runs" | Round 1: "auditor can write only its report" overstated the guarantee on the outer `--trust --force` session. | Adapt bullet now states outer headless read-only is "behavioural (parity with `opencode run --auto`), not enforced by CLI flags" and "`readonly: true` enforces Ask mode only when Cursor delegates to the wrapper as a subagent." | Applied; no further action. |
| F6 | minor — RESOLVED | Section 7 operational docs/rules | Round 1: "Relevant skills" omitted `skill-chanchi-verify` from the per-harness agent-load checklist. | Section 7 now adds `skills/skill-chanchi-verify/SKILL.md`: update `## Helpers` with a Cursor agent-load check (`.cursor/agents/` via `agent -p --trust`, recheck `readonly: true` after a Cursor upgrade). | Applied; no further action. |

## New findings

None. Additional Round 2 checks, all consistent with the revised design:

- All four brief request items and all four owner decisions (1A, 2 deferred, 3A, 4) are addressed; Non-goals record no SQL migration, no duplicate `.cursor/skills/` links, and no MVP phase-2 branch changes.
- Automatic behaviour claims hold in code at `17eab73`: `sync._entry()` gates on `harnesses.KEYS`; `skills_link.skill_targets()` gates on `any(installed(k) for k in KEYS)` and emits only `.agents/skills/` primaries (no `.cursor/skills/` duplicate); `agents_sync.plan_agents()` and `items.mirror()` iterate KEYS + `render_by_kind` + `user_agent_path`, so adding cursor yields `~/.cursor/agents/<name>.md`; `inventory._generated()` skips wrappers whose frontmatter starts with the generated header.
- AGENTS.md is 141 lines against the 150-line budget (`tests/test_rules_budget.py`), leaving room for the three small additions; `FEATURE_MAP.md` setup lines 123/476 and evidence lines 557–558 are exactly the sites the design updates.
- `no --agent` flag, native AGENTS.md/skills discovery, `readonly: true` subagent behaviour, `--add-dir`, and the `-- "<prompt>"` launch shape remain grounded in the brief's local Canaries; no live calls were made and the evidence caveats are now explicit.

## Summary

All six Round 1 findings are RESOLVED; zero OPEN or PARTIAL findings, and no new findings. The revision correctly incorporates every shared and confirmed-lone item from the Round 1 consolidation, the design is complete and implementable against the brief and owner decisions, and no blocking or major finding remains. Verdict: PASS.
