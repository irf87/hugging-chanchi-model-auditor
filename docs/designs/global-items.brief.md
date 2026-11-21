# Global Items, Project Items and the Fractal Trust System — Brief

- **Author:** Iván R
- **Date:** 2026-11-21
- **Revision:** 1

## Request

Continue the TODO of `chanchi-agents-mvp.md`: help the projects that use chanchi replicate
chanchi's own system, and let chanchi propose **global items**.

1. **Global items are proposed, not imposed.** chanchi decides whether a proposed item deserves
   to exist and how to build it. This is where "whoever uses chanchi owns what they make" starts:
   global items live in a `SYNC` folder with an `ITEMS` folder inside. `ITEMS` uses a taxonomy like
   the one this project uses for its own items. A mechanism exports (mirrors) them into the
   configuration of every harness installed on the user's machine. They are versioned. The user is
   told that `SYNC` should be a symbolic link to a folder synchronized with the cloud (Google
   Drive, iCloud, Dropbox) or a remote git repository (GitHub, GitLab), because these files are
   never pushed with chanchi and belong to the user.
2. **Projects create their own items with chanchi's help.** chanchi knows how to build items;
   it helps each project create its own items and its own trust system.
3. **Example flows.** Projects A, B and C record, in their sessions, improvements to their own
   items and the need for a specific new item. They never propose a global rule directly. A
   process the chanchi user runs analyzes all cases and decides which global item to propose.
   Later, in each project, the user asks "check whether there are global items to adopt"; that
   process decides whether to adopt, deprecate or delete the project's item, or to adapt it: the
   project keeps only what is particular to it and wraps the global item. Example: the herdr skill
   exists in A, B and C; chanchi finds them similar enough to make one global, agnostic skill; A
   and C delete theirs; B keeps a skill with its two exclusive rules that points to the global one
   for everything else.
4. **Processes:**
   - the improvement process (what each session records) produces a proposal for a new item or
     an improvement of an existing one;
   - for global items it runs from chanchi; for a project's items it runs in the project with the
     tools and items chanchi exposes. It must be iterative and auditable, with **at most three
     iterations**;
   - chanchi's process can be exported and replicated in other projects: an agent analyzes the
     project's current process and replicates chanchi's model in the project's context (a
     **fractal** system that can be replicated in other environments).
5. **At most three iterations.** Everything done is audited. Like redundant flight computers: if
   the majority agrees, it is right; a disagreement shows what one of them did not see. Three
   iterations at most, so it never loops forever.

## Decisions taken with the owner (2026-11-21)

- Global items are named `<item>-chanchi-global-<name>`: `global` is a reserved project slug.
- Each audit round has **three auditors, one per model family**, accepted when two of three agree.
- **Harness defaults and fallback.** A harness is not always available (for example, no credits
  left in opencode): the rule stays, but the next auditor in the roster is used even if a family
  repeats. The user chooses, in the `SYNC` folder, which harnesses and models to use.
- **Scalability.** Other harnesses (Cursor, OpenAI Codex/ChatGPT) may be added later; not in this
  phase, but the design must make adding one cheap.
- The pending lessons #1-#3 stay pending: they are test data for this feature.
- The herdr skill is the first global item, built from the copies the consumer projects use.

## Facts gathered (2026-11-21)

Research ran in agy as `agent-chanchi-researcher` (`gemini-4-hydrogen-high`), reports kept local.

- **Consumer projects** keep 24 and 33 project skills, 10 and 5 roles, and hand-written wrappers
  per harness. Their herdr skills share 209 identical lines (vendored from `herdr --skill`) and add
  7 and 3 project-specific rules. Ten other skills exist in both projects, copied by hand and
  already drifted. Neither project records improvements in chanchi: they live in a "lessons learned"
  section of each role, in handoff files and in session reports.
- **Harness global locations** (verified on claude 2.1.330, opencode 2.3.2, agy 1.5.14): Claude
  Code reads `~/.claude/skills` and `~/.claude/agents`; opencode reads `~/.config/opencode/agents`
  and skills from `~/.agents/skills` and `~/.claude/skills`; agy reads `~/.gemini/config/skills`,
  `~/.gemini/antigravity-cli/skills` and `~/.gemini/config/agents`. All three follow symlinks;
  Claude Code and opencode reload changes during a session (an open agy TUI was not verified). Claude Code lets a personal skill win over a project skill of the same name, but
  a project subagent wins over a personal one (code.claude.com docs, *Skills* and *Subagents*),
  while opencode lets a project skill override a global one (opencode docs, *Skills*), so global
  and project items must never share a name.
  Claude Code rewrites `~/.claude.json`, so runtime-mutated files are never mirrored.
- **Prior art** (primary sources): promote a shared item only after repeated independent use
  ("rule of three", InnerSource extensions); no skill standard has `extends`, so wrapping is an
  explicit local item that points to the shared one; versions plus content hashes and append-only
  tombstones for retired items; redundant verification needs diverse versions because same-design
  versions fail together (Knight and Leveson 1986; the Space Shuttle's distinct backup system),
  and panels of judges from disjoint model families reduce self-preference bias (Verga et al.
  2024); multi-agent debate saturates by three to four rounds (Du et al. 2023).
