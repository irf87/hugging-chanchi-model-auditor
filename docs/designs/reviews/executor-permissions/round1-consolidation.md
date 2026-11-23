# AGENTS.md executor-permissions rule — audit round 1 consolidation

- Subject: `AGENTS.md` at `50a0a4e`; chanchi audit 6, kind `other`. **Degraded**: seat 3 (opencode
  minimax-m3) unavailable (monthly usage limit), refilled with agy gemini-4-hydrogen-high.
- Outcome: **accepted** (three `pass_with_fixes`, 0 blocking, 0 major). Minor fixes applied without
  a new round.

| Finding | Seats | Fix |
|---|---|---|
| Name the flag per harness; opencode's is `--auto` | S1-02, S2-01, S3-01 | flags named, plus "confirm in `--help`" |
| Restore "only" for claude; scope beyond executors | S2-03, S3-02 | "Delegated agents", "only when ... never as an in-process subagent" |
| herdr vs terminal pane | S1-01 (confirmed) | "another terminal pane such as a herdr pane" |
| Overstated bound; owner's "not bypassing a rule" | S2-02 (confirmed) | "removes prompts, not limits ... checked on handoff"; owner wording kept |
| Link from herdr launch material | S1-03 (confirmed) | `skill-chanchi-global-herdr` 0.1.1 (owner decision recorded in its round-2 consolidation) |
| No conflict with the executor agent | S1-04 | rejected: no change needed |
