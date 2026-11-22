# Phase 2 gate — verification item 9

- **Date:** 2026-11-22, `main` at `5e09b1b` (S1-S3 merged), installed `chanchi` from that checkout
- **Plan:** `docs/superpowers/plans/2026-11-22-global-items-phase2.md`, Task 5
- **Harnesses:** Claude Code 2.1.330, opencode 2.3.2, agy 1.5.14
- **Result:** **PASS** in all three harnesses (with one deviation from the plan's probe, below)

Scratch `CHANCHI_DB` and scratch `CHANCHI_SYNC`; real home (mirror entries only). The probe
items' `item` audits are fixture data in the scratch database (three `pass` votes, report
`fixture`); the operational database holds none of them. Home paths are written as `~`.

## Steps

| Step | Command (summary) | Result |
|---|---|---|
| 0 | `chanchi agents link --user --check`; `ls ~/.agents/skills` | `ok: true`; the six own `skill-chanchi-*` skills present |
| 1 | `db migrate`, `sync init`, four roster models; baseline of `~/.agents/skills`, `~/.claude/skills`, `~/.gemini/antigravity-cli/skills`, `~/.claude/agents`, `$OC/agents` (`~/.config/opencode/agents`), `~/.gemini/config/agents` | baseline recorded (79 lines) |
| 2 | drafts `skill-chanchi-global-probe` and `agent-chanchi-global-probe` 0.1.0; `items check`; `items mirror` | `problems: []`; mirror `written: []`, `items: []` (drafts never appear) |
| 3 | per probe: `audit open --kind item --version 0.1.0`, 3 votes, `audit close` → `accepted`; `items publish`; `items mirror` | both `published`; 6 entries written (`~/.agents/skills`, `~/.claude/skills`, `~/.gemini/antigravity-cli/skills`, `~/.claude/agents`, `~/.config/opencode/agents`, `~/.gemini/config/agents/<n>/agent.md`); `skipped_harnesses: []`, `conflicts: []` |
| 4 | one headless run per harness (adapter launch template, below) | see *Runs* |
| 5 | hand edit of `~/.claude/agents/agent-chanchi-global-probe.md`; `items mirror --check`; `items mirror`; `--check` | `stale_wrappers`; `1 written, 5 unchanged`; `ok: true` |
| 6 | `items mirror --remove`; baseline listing again; `find ~/.agents ~/.claude "$OC" ~/.gemini -maxdepth 4 -name '*-chanchi-global-*'` | `6 removed`; listing identical to the baseline; `find` prints nothing; scratch `mirror.json` has no entries |
| 7 | `unset CHANCHI_DB CHANCHI_SYNC`; from the main checkout `chanchi agents sync --check`, `chanchi agents link --user --check` | both `ok: true` |

## Runs (step 4)

Skill token `PROBE-120e0414` (only in the mirrored skill); agent token `AGENT-ec0ed256` (only in
the mirrored agent body, version 0.1.1). Prompt: "State your agent name and the probe token."

| Harness | Launch | Reply |
|---|---|---|
| claude | `claude -p --agent agent-chanchi-global-probe --model sonnet --effort low "<prompt>" < /dev/null` | `Agent name: agent-chanchi-global-probe` · `Agent token: AGENT-ec0ed256` · `Probe token: PROBE-120e0414` |
| opencode | `opencode run --agent agent-chanchi-global-probe -m opencode-go/minimax-m3 "<prompt>" < /dev/null` | `→ Skill "skill-chanchi-global-probe"` · `agent-chanchi-global-probe · minimax-m3` · `Agent name: agent-chanchi-global-probe` · `Agent token: AGENT-ec0ed256` · `Probe token: PROBE-120e0414` |
| agy | `agy --agent agent-chanchi-global-probe --model gemini-4-hydrogen --effort low -p="<prompt>" < /dev/null` | `Agent name: agent-chanchi-global-probe` · `Agent token: AGENT-ec0ed256` · `Probe token: PROBE-120e0414` |

Both tokens in every reply: the mirrored agent's body and the mirrored skill (preloaded through
the agent's `skills`) load in all three harnesses.

## Deviation from the plan's probe

With the 0.1.0 agent of the plan (body: "State your agent name, then give the probe token from
your skill."), all three replies carried the exact skill token, but only opencode named the agent;
claude answered "I'm Claude ..." and agy "Agent name: Antigravity". A control run with
`--agent agent-chanchi-global-nope` failed in both (`not found` / `unknown agent`), and both
listed `agent-chanchi-global-probe` among their agents, so the mirrored agent was resolved. The
models could not state the name because the frontmatter `name` is metadata, not part of the
prompt. The probe agent was therefore republished as 0.1.1 with its name and an agent token in
the body (new draft, changelog section, fixture audit, `items publish`, `items mirror`: 3 written,
3 unchanged), and step 4 was re-run with the same prompt. The new draft also showed the mirror
flagging the stale published wrappers (`items mirror --check` → `stale_wrappers`) until the new
version was published.
