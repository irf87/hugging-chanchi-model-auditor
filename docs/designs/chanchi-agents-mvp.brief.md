# chanchi Agents and the Agentic Trust MVP — Brief

- **Author:** Iván R
- **Date:** 2026-11-21
- **Revision:** 1

## Request

chanchi is part of an agentic trust system: harness elements (rules, skills, workflows, hooks,
agents) improve themselves so that human intervention keeps shrinking. The next project is to give
chanchi its own **agents**, harness agnostic, so any harness (Claude Code, opencode, agy, Codex)
can run them.

1. **Naming rule for every item this project creates:** `<item>-chanchi-<descriptive-name>`,
   for example `agent-chanchi-<name>`.
2. **Naming rule for items chanchi will later help other projects create:**
   `<item>-chanchi-<project-id>-<descriptive-name>`.
3. **This phase:** identify the elements the trust system needs, build chanchi's own agents, and
   write the guides and rules for creating chanchi's own items. How chanchi helps other projects
   build their items, and how those projects interact with chanchi, is a TODO for a later phase,
   but what is already known about that interaction goes into `AGENTS.md` now.
4. **Frame:** a minimum viable version of the autonomous engineering workflow presented by Lauren
   Tan (Cursor), in three layers:
   - **Layer 1, autonomous verification:** the agent runs the software and checks its own work;
     a feature map tells it how to reach every feature without step-by-step human instructions.
   - **Layer 2, skills plus agent evals:** observed failure patterns become skills, and skills are
     tested like unit tests: blinded candidate runs in isolated directories, graded by a judge
     from another model family against a rubric, iterated until reliable.
   - **Layer 3, hard guardrails:** rules files and skills are soft enforcement; critical
     invariants move into static checks and CI that block the merge. Guiding principle: the
     shortest path for the agent must be the correct path, and every repeated review correction
     becomes an automatic rule.
5. **Deliverable:** minimal architecture (files, what runs in the repo, CI and locally), a
   feature map format, a minimal eval flow for one to three critical skills, the five to seven
   highest-impact hard checks, what to reuse from the research versus build, and a three-phase
   adoption plan (local supervised; automatic verification and guardrails; safe parallelism) with
   the concrete signal that allows moving to the next phase. Avoid over-engineering and token
   waste.

## Decisions taken with the owner (2026-11-21)

- **Rename the existing skills** to the new rule (`chanchi-model-selection` →
  `skill-chanchi-model-selection`, and so on), with no grandfathered exception.
- **Guardrails:** one local gate script that blocks through git hooks where the orchestrator
  merges, plus a GitHub Actions workflow that runs the same script on push as a second net. The
  local merge flow (no pull requests) stays.
- **Agent shipping:** option A, one agnostic source per agent and generated per-harness wrappers
  (see the design), confirmed by independent audits.

## Facts gathered (2026-11-21)

Read-only research ran in agy (`gemini-4-hydrogen-high`). It verified the harness facts against the
installed binaries (`claude` 2.1.330, `opencode` 2.2.6, `agy` 1.5.14):

- **Where each harness reads agents:** Claude Code reads `.claude/agents/<name>.md` (and
  `~/.claude/agents/`), opencode reads `.opencode/agents/<name>.md` (and
  `~/.config/opencode/agents/`), and agy reads `.agents/agents/<name>/agent.md` (and
  `~/.gemini/config/agents/`). Neither Claude Code nor opencode reads `.agents/agents/`.
- **Frontmatter and body differ per harness.** Model names, tool lists and permission schemas are
  incompatible. Claude Code uses a non-empty body as the whole system prompt, opencode uses it as
  `system`, and agy prepends it. One Markdown file cannot serve every harness, so symlinks are not
  an option.
- **Headless invocation exists in all three:** `claude -p --agent <name>`,
  `opencode run --agent <name>` and `agy --agent <name> -p="<prompt>"` (agy needs the prompt attached
  to `-p`).
- **Two consumer projects** already keep one agnostic role file per role plus hand-written
  wrappers for each harness. Their wrappers have drifted: some roles are missing in some harnesses.
  Their role files load chanchi skills by a hardcoded path glob (`~/.agents/skills/chanchi-*`), and
  `chanchi-lessons` is not linked anywhere yet.
- **This repository** has a GitHub remote, no CI and no linter. Tests run with `uv run pytest`.

The research report on the Lauren Tan workflow (a third-party deep-research document) was
digested in the same way. Its usable content is limited to patterns: the verify-skill structure
(Launch, Doctor, Drive, Evidence, Cleanup) with per-feature reference files, the eval playbook
(blinded candidates, isolated directories, a cross-family judge, a hidden rubric of 3 to 6
criteria), the hill-climb loop (one change, one measurement, keep or revert, recorded in a
ledger), and Python-oriented static gates (import contracts, AST rules). Its star counts and
several citations look fabricated or come from aggregator sites, so the design takes no fact from
it that it does not verify locally.
