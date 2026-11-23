VERDICT: PASS WITH FIXES

Scope: `git show 50a0a4e` (AGENTS.md § Working Conventions, +5/-1 lines). AGENTS.md is 133 lines (limit 150). I could not run pytest (the sandbox denied the command), so `tests/test_rules_budget.py`, `tests/test_agent_rules.py` and `tests/test_privacy.py` are unverified; I checked the line count and the text by hand. The text has no home path or reference-project name.

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| S1-01 | minor | AGENTS.md, new sentence "claude when it runs in another terminal pane" | The owner said "another herdr pane". The text says "terminal pane", which is slightly broader. The only boundary the text gives is "not as an in-process subagent". Faithful in spirit, but a claude process in a plain terminal split would also count. | Brief request: "claude (only when it runs in another herdr pane)". | Either keep it (herdr is one multiplexer and the repo is harness-agnostic, so the generic wording is defensible), or say "another terminal pane (e.g. a herdr pane)". |
| S1-02 | minor | same sentence, "their harness's skip-permissions flag" | The flag is never named, so an agent has to guess it (agy's `--dangerously-skip-permissions` is in the request). Rule 4 forbids stating harness capabilities from memory, so naming flags in AGENTS.md is risky. | The request names `--dangerously-skip-permissions` for agy only. | Leave the flag unnamed in AGENTS.md. Put the verified per-harness flags in the herdr launch material (the owner asked for "the herdr skills"), or in the memory/doc that already lists agy launch commands. |
| S1-03 | minor | placement | The owner asked for a rule "in the herdr skills". The repo has no herdr skill under `skills/`; herdr appears only in docs/designs. AGENTS.md is the single source of truth, so putting it there is acceptable. The rule is not linked from where launch commands live. | `ls skills` shows 6 skills, none for herdr. `grep -il herdr` hits only docs/designs and reviews. | Optional: add a pointer or the flags table in `skill-chanchi-audit-rounds` or a design doc, so the launch steps carry the rule. |
| S1-04 | minor | consistency with `agents/agent-chanchi-executor/AGENT.md` | No conflict. The executor profile is `workspace-write` and it already requires a worktree and a scratch `CHANCHI_DB` (step 1). That matches the justification "worktree and scratch database bound what the executor can change". The executor text does not mention the flag, which is fine since it is a launch concern. | AGENT.md lines 1-20. | None needed. |

Answers to the brief's questions:

1. **Fidelity.**
   - It covers agy and opencode "always" and claude only when it runs in another pane. It excludes the in-process subagent case.
   - It records the owner's authorization and the date.
   - It gives the reason: a permission prompt would stop the flow.
   - It adds a bounding rationale (worktree plus scratch database). That is not in the request, but it is true and harmless.
   - Nothing is missing and nothing is overreaching, apart from the "terminal" vs "herdr" wording in S1-01.
2. **Consistency.**
   - Core Rules 1-4 are unaffected.
   - It fits the existing delegating bullet and the existing "owner authorized this" style.
   - It does not contradict the rule that executors never commit, merge or write records.
3. **Clarity and size.** It is harness-agnostic (it names the harnesses by behaviour, not by feature dependency) and stays well within the line budget. Four sentences in one bullet is slightly dense but readable.
4. **Check or text.** A check could not really enforce this. The flag is chosen at launch time outside the repository, and there is nothing to assert on. Text is the right form here.
