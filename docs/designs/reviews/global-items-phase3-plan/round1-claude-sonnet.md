VERDICT: PASS WITH FIXES

> Transcribed by the orchestrator from the auditor's stdout (claude-r1.log): the harness denied the write to the private path.

**Verdict: PASS WITH FIXES.** I read the plan at `0334f88` against the design and the code. I couldn't run `pytest`, which was also refused, so every check is from reading code. I did not open any consumer project.

Coverage is complete. Migration 006, `project items-dirs`, `items scan`, `items propose`, the builder and the gate each map to a task with tests. Nothing from phase 4 is pulled in, and deferring publishing (D16) is justified. The builder text parses through `agents_sync._parse`, matches the `items._inspect` rules and stays well under the 300-line budget.

Findings (ids S1-NN):

| id | severity | where | problem |
|---|---|---|---|
| S1-01 | major | D7 | The plan says `items publish` refuses project-item collisions, but `publish` goes through `_find` and `_inspect`, not `check`. The interface list only changes `check` and `mirror`, so `publish` stays unprotected. |
| S1-02 | major | D2 + D10 | A project with a missing root keeps its stored rows. The freshness check then fails the whole `propose` when any canonical copy is missing, so one moved project blocks every proposal. |
| S1-03 | major | D3/D8 | The scan would store generated agent wrappers (`.claude/agents`, `.opencode/agents`, `.agents/agents`) as copies. The canonical pick by "most lines" could choose a wrapper over the source. The agy wrapper is lowercase `agent.md` while D3 looks for `AGENT.md`, which fails on case-sensitive filesystems. |
| S1-04 | minor | D3 | Only the last path component is checked for being a symlink. A symlinked `.claude` would let the scan read outside the project. |
| S1-05 | minor | Task 4 | The builder has no rule for revising an existing draft at the same version (the gate's fix round), and none for choosing `scope` and `profile` for agent proposals. |
| S1-06 | minor | Task 4 | Vendored text is recognized only when a copy labels it. An unlabelled identical block in `pairs` would be copied. |
| S1-07 | minor | Task 5 | Reports are moved to `SYNC/reviews` after the votes, but `audit vote` has already stored the scratch path. |
| S1-08 | minor | Task 5 | Registering the consumer projects and running `agents link --user` on the real home are not marked as needing the owner. |
| S1-09 | minor | D9 | The plan measures a 212-line shared block where the design example says 209. It needs one sentence saying the design number is an example. |
| S1-10 | minor | D4 | `content_hash` raises on a symlink, so `walk` must catch that error. The S1/S3 parallel merge itself is safe. |

Rerun with write access to that path and I'll save the full table and fixes there.
