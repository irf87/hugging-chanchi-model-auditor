---
name: skill-chanchi-lessons
description: Use at the end of a conversation in a writer role, after an audit or a stop found a failure of the process, or in a maintenance conversation that reviews pending lessons. Records a lesson (cause and one general rule) in chanchi, or reviews and applies one. Not for a single model's weakness (record an incident with skill-chanchi-session-audit) and not for a code bug (fix the code).
---

# chanchi — lessons

A lesson records a failure of the setup that guides agents (roles, skills, rules files, workflows,
hooks) and one general rule that would have prevented it. A lesson never fixes code and never rates
a model. Model weakness is an incident (`skill-chanchi-session-audit`).

Every command takes `--as <role>`, `--author <agent:model[:effort]>` and `--conversation <id>`.
Use the harness, model and effort you run in, and the conversation id or a label you reuse for
the whole conversation. All commands print JSON; errors carry `field`, `valid_values` and `hint`.

## Principles

1. **Fix first, then record.** The fix in the work comes first. A lesson is for learning; it does
   not replace the fix.
2. **Record only what really went wrong.** Five triggers:
   - a wrong result was produced;
   - work had to be redone;
   - an existing rule was not followed;
   - a control did not stop what it should;
   - an assumption turned out false.

   A run that went well records nothing.
3. **From general to particular.** Every lesson carries a general rule that holds beyond its case.
   A rule that serves one case only is noise.
4. **The author does not judge.** A different conversation reviews. Never review or apply a lesson
   you recorded.
5. **Hard rules belong in code, not in prompts.** A rule that must never break goes in a hook, a
   permission or a CLI check.

## Record (writer roles)

Writer roles are set per project and globally (`chanchi project writers`; `planner` by default).
Other roles never record: they say what went wrong in their report.

1. Fix the failure in the work first.
2. Write the **cause**. If you cannot write the cause, you have the symptom. If you cannot write
   the rule, you do not understand the failure yet.
3. Write the **general rule**: one sentence that holds in any case of this kind.
4. Run `chanchi lesson similar "<general rule>"` and read the pending lessons it returns. If one
   already covers this failure, count it again instead of adding a new one:
   `chanchi lesson repeat <id> --as <role> --author <agent:model:effort> --conversation <id> --evidence "<what happened this time>"`.
   Otherwise go to step 5.
5. Record the lesson from a JSON body on stdin (`--json -`); an unknown key fails.
   `chanchi lesson add --as <role> --author <agent:model:effort> --conversation <id> --json -`
6. Tell the human the lesson id, the general rule and the place the fix belongs. Do not review
   or apply it.

### Field guide

**Severity** is the risk if the failure happens again, not the damage this time.

| Severity | If it happens again |
|---|---|
| `low` | a little time is lost |
| `medium` | work must be redone, or a wrong result appears that is noticed soon |
| `high` | a wrong result may go unnoticed, or a control fails to block what it should |
| `critical` | data is lost, production is touched, or a secret is exposed |

**Generality** is how far the rule holds, not where the fix goes.

| Generality | Meaning | Use |
|---|---|---|
| `agnostic` | holds in any project and any harness | the rule holds anywhere, even if the fix touches one file |
| `project` | holds in all of one project | the rule holds for this project's roles, skills or rules |
| `particular` | holds for one case only | needs `high` or `critical` severity and `particular_justification` |

**`target_kind`** is one of `role`, `skill`, `wrapper`, `rules-file`, `hook`, `permission`,
`workflow`, `tool`. **`target`** is free text naming one place, as `<kind> <name or path>`
(for example `role executor`). It is not parsed.

### Body keys

| Key | Type | Rule |
|---|---|---|
| `what_happened`, `evidence`, `cause`, `prevention`, `proposal`, `general_rule`, `target` | string | required, not blank |
| `generality`, `severity`, `target_kind` | string | required, one of the values above; `blocking` is refused, use `critical` |
| `particular_justification` | string | required when `generality` is `particular` |
| `tags` | list of strings | optional |
| `change`, `session` | string | optional; a change ref and a session ref (`S1`) of this project |
| `incidents` | list of integers | optional; incident ids of `change` (requires `change`) |
| `replaces` | list of integers | optional; existing lesson ids this one replaces |

With `--global`, the lesson must be `agnostic` and may not carry `change`, `session` or `incidents`.

Example: [references/example.md](references/example.md).

Never pass `--author human`: only the human uses it, when giving an instruction directly.

## Review (maintenance conversations)

A maintenance conversation reviews lessons recorded by another conversation.

1. `chanchi lesson summary` for counts; `chanchi lesson export` for the pending lessons, most
   urgent first (general before particular, then severity, then occurrences).
2. For each lesson, `chanchi lesson show <id>`, and decide:
   - If the lesson has 2 or more occurrences, ask first: can a check (a test, a ruff rule, a CLI check, a hook or a permission) enforce it? If yes and its `target_kind` is not `tool`, `hook` or `permission`, do not approve it: record a replacement lesson with that `target_kind`, a proposal naming the check and `replaces` listing it (add `--force-new` if it is reported as a duplicate), then review the original as `duplicate --of <new id>`. Never add its rule as prose.
   - Is the cause identified, or is it only a symptom? (`symptom_only`)
   - Does an existing rule already cover it? Then adjust that rule instead. (`covered`)
   - Does the rule hold outside the case that produced it?
   - What does the rule cost in context on every run? (`too_costly` if rare and cheap)
   - Is the cheapest place a hook, a permission or a CLI check rather than a role line?
   - Does it replace an older rule? If only one model failed, record an incident instead.
3. Decide with a reason:
   `chanchi lesson review <id> --as <role> --author <agent:model:effort> --conversation <id> --decision approve --reason "<why>"`
   Decisions are `approve`, `reject` (add `--reason-code model_weakness|covered|too_costly|symptom_only`),
   `postpone`, and `duplicate --of <id>`. A rejected lesson can come back with
   `chanchi lesson reopen <id> --reason "<why>"`.
4. Apply an approved lesson by hand: add the rule to the file and tag the line with the lesson id,
   for example `[lesson #12]`. Then record where it landed, with the commit if you have one:
   `chanchi lesson apply <id> --as <role> --author <agent:model:effort> --conversation <id> --site project --where "AGENTS.md [lesson #12] @ <commit>"`
   `--site global` records a global place and needs no project.
5. When a rule is no longer wanted at a place, retire it there. Other places are not affected:
   `chanchi lesson retire <id> --as <role> --author <agent:model:effort> --conversation <id> --site project --reason "<why>"`

## Lines to paste

Paste verbatim: the writer-role block into the planner's role file; the reporter line into every other role.

Writer-role block (planner's role file):

> You are a writer role for chanchi lessons. At the end of each conversation, or when something went wrong, follow the `skill-chanchi-lessons` skill: fix first, then record the cause and a general rule. Never review or apply a lesson you recorded.

Reporter line (every other role):

> If something went wrong, say so in your report; do not record it in chanchi.

The project-rules line that points agents to this skill is printed by `chanchi skills link`
(`suggested_config_line`). Copy it from that output; do not keep a second copy.
