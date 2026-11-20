# Stage 1 verification record

Stage 1 merged to `main` locally (`81dafa6`) without a pull request, so the evidence the
Verification Plan asks to paste into the pull-request description is kept here.

| Check | Result |
|---|---|
| Build | `uv tool install --editable .` exits 0; `chanchi --version` prints `0.1.0` |
| Tests | `uv run pytest`: 396 passed, including the template drift check and `test_no_network.py` |
| Duplicate-check speed | `dedup.blocking_match` over 1,000 candidates: median about 32 ms (limit 100 ms) |
| Migration on real data | a copy of the operational database (v3) migrated to v4, `.bak-v3` created, and `show explore-capabilities-hf` returned identical JSON from the old build (worktree of `40e5ac0`) and the new build |
| Skill check | `chanchi skills link` into a scratch directory created `chanchi-lessons` in `.agents/skills` and `.claude/skills` |
| Manual journey | CUJs 1, 2, 3, 4 and 7, below |

## Manual journey

Run on 2026-11-19 with the installed build, in a scratch `CHANCHI_DB`. `$S` is the scratch
directory. Projects `project-a` (`$S/work/a`) and `project-b` (`$S/work/b`) are registered;
`$S/work/b/b-app` is an independent, unregistered git repository inside project B; `$S/home`
stands in for a folder outside any project.

Expected refusals (exit 2), all as the CUJs require:

- CUJ 2: review from the recording conversation → `self_review`.
- CUJ 3: `lesson add --as executor` → `not_a_writer`; nothing written.
- CUJ 7: `lesson add` outside a project without `--global` → `project_not_registered`; a global
  lesson with generality `project` → `invalid_value`.

Final database state:

| Lesson | Status | Origin | Author | Model id set | `git_head` | Events |
|---|---|---|---|---|---|---|
| #1 (CUJ 1-2) | approved | project-a | claude:opus:high | yes | yes | created, reviewed, applied |
| #2 (CUJ 4) | pending | project-b | claude:opus:high | yes | yes | created |
| #3 (CUJ 7) | approved | global | human | yes | no (outside a repository) | created, reviewed |

Site rows: #1 applied at project-a. Projects: project-a and project-b only (no `b-app` row).
Changes: `add-export` in project-a, `fix-login` in project-b (opened from inside `b-app`).

### Command log

#### Setup

```console
$ (cd work/a && chanchi models add --agent claude --model opus --cost 3 --efforts high)
{
  "ok": true,
  "model": {
    "id": 2,
    "agent": "claude",
    "model": "opus",
    "spec": "claude:opus",
    "cost_tier": 3,
    "efforts": [
      "high"
    ],
    "active": true,
    "notes": null,
    "created_at": "2026-11-20T01:41:30Z",
    "capabilities": ""
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi models add --agent claude --model haiku --cost 1)
{
  "ok": true,
  "model": {
    "id": 3,
    "agent": "claude",
    "model": "haiku",
    "spec": "claude:haiku",
    "cost_tier": 1,
    "efforts": null,
    "active": true,
    "notes": null,
    "created_at": "2026-11-20T01:41:30Z",
    "capabilities": ""
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi project register --name project-a)
{
  "ok": true,
  "project": {
    "id": 1,
    "slug": "project-a",
    "path": "$S/work/a",
    "registered_at": "2026-11-20T01:41:30Z",
    "locators": [
      "$S/work/a"
    ],
    "writers": {
      "roles": [
        "planner"
      ],
      "default": true
    },
    "lessons": {
      "pending": 0,
      "approved": 0,
      "rejected": 0,
      "postponed": 0,
      "duplicate": 0
    }
  },
  "already_registered": false,
  "adopted": false
}
# exit 0
```

```console
$ (cd work/b && chanchi project register --name project-b)
{
  "ok": true,
  "project": {
    "id": 2,
    "slug": "project-b",
    "path": "$S/work/b",
    "registered_at": "2026-11-20T01:41:30Z",
    "locators": [
      "$S/work/b"
    ],
    "writers": {
      "roles": [
        "planner"
      ],
      "default": true
    },
    "lessons": {
      "pending": 0,
      "approved": 0,
      "rejected": 0,
      "postponed": 0,
      "duplicate": 0
    }
  },
  "already_registered": false,
  "adopted": false
}
# exit 0
```

```console
$ (cd work/a && chanchi project writers)
{
  "ok": true,
  "scope": "project-a",
  "roles": [
    "planner"
  ],
  "default": true
}
# exit 0
```

#### CUJ 1: the planner records a lesson after an audit

```console
$ (cd work/a && chanchi change open add-export --kind openspec --planner claude:opus:high)
{
  "ok": true,
  "change": {
    "id": 1,
    "project": "project-a",
    "ref": "add-export",
    "kind": "openspec",
    "planner": "claude:opus:high",
    "orchestrator": "claude:opus:high",
    "opened_at": "2026-11-20T01:41:30Z",
    "closed_at": null
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi session start add-export S3 --executor claude:haiku --task-type docs --complexity low --tasks 2)
{
  "ok": true,
  "session": {
    "id": 1,
    "change": "add-export",
    "session": "S3",
    "attempt": 1,
    "retry_reason": null,
    "executor": "claude:haiku",
    "task_type": "docs",
    "complexity": "low",
    "tags": [],
    "groups": null,
    "tasks_total": 2,
    "started_at": "2026-11-20T01:41:31Z",
    "ended_at": null,
    "reported_status": null,
    "verdict": null,
    "audited_at": null,
    "notes": null
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi incident add add-export --session S3 --code false_claim --severity high --detected-by planner_audit --desc tests never ran in the right package --evidence pytest output named no package)
{
  "ok": true,
  "incident": {
    "id": 1,
    "change": "add-export",
    "session": "S3",
    "attempt": 1,
    "code": "false_claim",
    "role": "executor",
    "severity": "high",
    "task_ref": null,
    "detected_by": "planner_audit",
    "description": "tests never ran in the right package",
    "evidence": "pytest output named no package",
    "created_at": "2026-11-20T01:41:31Z",
    "voided_at": null,
    "void_reason": null
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson similar test output evidence package skipped)
{
  "ok": true,
  "scope": "all",
  "matches": []
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson add --as planner --author claude:opus:high --conversation journey-record --json -)
{
  "ok": true,
  "lesson": {
    "id": 1,
    "origin_project_id": 1,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-record",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": 1,
    "session_id": 1,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
    "evidence": "incident 1: pytest output named no package",
    "cause": "The executor treated a zero exit code as proof without reading what ran.",
    "prevention": "Ask for the collected test count and the package name in every report.",
    "proposal": "Add a line to the executor role about test evidence.",
    "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
    "generality": "agnostic",
    "severity": "high",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "pending",
    "reviewed_at": null,
    "reviewed_by_role": null,
    "review_conversation": null,
    "decision_reason": null,
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-a"
  },
  "warnings": []
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson show 1)
{
  "ok": true,
  "lesson": {
    "id": 1,
    "origin_project_id": 1,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-record",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": 1,
    "session_id": 1,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
    "evidence": "incident 1: pytest output named no package",
    "cause": "The executor treated a zero exit code as proof without reading what ran.",
    "prevention": "Ask for the collected test count and the package name in every report.",
    "proposal": "Add a line to the executor role about test evidence.",
    "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
    "generality": "agnostic",
    "severity": "high",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "pending",
    "reviewed_at": null,
    "reviewed_by_role": null,
    "review_conversation": null,
    "decision_reason": null,
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-a"
  },
  "sites": [],
  "replaces": [],
  "incidents": [
    {
      "id": 1,
      "change": "add-export",
      "session": "S3",
      "attempt": 1,
      "code": "false_claim",
      "role": "executor",
      "severity": "high",
      "task_ref": null,
      "detected_by": "planner_audit",
      "description": "tests never ran in the right package",
      "evidence": "pytest output named no package",
      "created_at": "2026-11-20T01:41:31Z",
      "voided_at": null,
      "void_reason": null
    }
  ],
  "events": [
    {
      "id": 1,
      "lesson_id": 1,
      "site": null,
      "site_project_id": null,
      "at": "2026-11-20T01:41:31Z",
      "actor_role": "planner",
      "actor_agent": "claude",
      "conversation": "journey-record",
      "action": "created",
      "from_state": null,
      "to_state": "pending",
      "note": ""
    }
  ]
}
# exit 0
```

#### CUJ 2: a maintenance conversation reviews and applies

```console
$ (cd work/a && chanchi lesson export --generality agnostic)
{
  "ok": true,
  "scope": "project-a",
  "lessons": [
    {
      "id": 1,
      "origin_project_id": 1,
      "author_role": "planner",
      "author_agent": "claude",
      "author_model_raw": "opus",
      "author_model_id": 2,
      "author_effort": "high",
      "author_conversation": "journey-record",
      "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
      "change_id": 1,
      "session_id": 1,
      "target_kind": "role",
      "target": "role executor",
      "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
      "evidence": "incident 1: pytest output named no package",
      "cause": "The executor treated a zero exit code as proof without reading what ran.",
      "prevention": "Ask for the collected test count and the package name in every report.",
      "proposal": "Add a line to the executor role about test evidence.",
      "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
      "generality": "agnostic",
      "severity": "high",
      "particular_justification": null,
      "occurrences": 1,
      "tags": [],
      "status": "pending",
      "reviewed_at": null,
      "reviewed_by_role": null,
      "review_conversation": null,
      "decision_reason": null,
      "reason_code": null,
      "duplicate_of": null,
      "created_at": "2026-11-20T01:41:31Z",
      "updated_at": "2026-11-20T01:41:31Z",
      "origin": "project-a",
      "sites": [],
      "incidents": [
        {
          "id": 1,
          "change": "add-export",
          "session": "S3",
          "attempt": 1,
          "code": "false_claim",
          "role": "executor",
          "severity": "high",
          "task_ref": null,
          "detected_by": "planner_audit",
          "description": "tests never ran in the right package",
          "evidence": "pytest output named no package",
          "created_at": "2026-11-20T01:41:31Z",
          "voided_at": null,
          "void_reason": null
        }
      ]
    }
  ]
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson review 1 --as planner --author claude:opus:high --conversation journey-record --decision approve --reason clear rule)
{
  "ok": false,
  "error": {
    "code": "self_review",
    "message": "lesson #1 was recorded in this conversation",
    "field": "conversation",
    "hint": "review it from another conversation"
  }
}
# exit 2
```

```console
$ (cd work/a && chanchi lesson review 1 --as planner --author claude:opus:high --conversation journey-maint --decision approve --reason holds outside this case and costs one line)
{
  "ok": true,
  "lesson": {
    "id": 1,
    "origin_project_id": 1,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-record",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": 1,
    "session_id": 1,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
    "evidence": "incident 1: pytest output named no package",
    "cause": "The executor treated a zero exit code as proof without reading what ran.",
    "prevention": "Ask for the collected test count and the package name in every report.",
    "proposal": "Add a line to the executor role about test evidence.",
    "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
    "generality": "agnostic",
    "severity": "high",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "approved",
    "reviewed_at": "2026-11-20T01:41:31Z",
    "reviewed_by_role": "planner",
    "review_conversation": "journey-maint",
    "decision_reason": "holds outside this case and costs one line",
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-a"
  },
  "repointed": []
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson apply 1 --as planner --author claude:opus:high --conversation journey-maint --site project --where .agents/roles/executor.md [lesson #1] @ abc123)
{
  "ok": true,
  "lesson": {
    "id": 1,
    "origin_project_id": 1,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-record",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": 1,
    "session_id": 1,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
    "evidence": "incident 1: pytest output named no package",
    "cause": "The executor treated a zero exit code as proof without reading what ran.",
    "prevention": "Ask for the collected test count and the package name in every report.",
    "proposal": "Add a line to the executor role about test evidence.",
    "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
    "generality": "agnostic",
    "severity": "high",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "approved",
    "reviewed_at": "2026-11-20T01:41:31Z",
    "reviewed_by_role": "planner",
    "review_conversation": "journey-maint",
    "decision_reason": "holds outside this case and costs one line",
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-a"
  },
  "site": {
    "site": "project",
    "project": "project-a",
    "state": "applied",
    "where_": ".agents/roles/executor.md [lesson #1] @ abc123",
    "reason": null,
    "decided_conversation": "journey-maint",
    "decided_at": "2026-11-20T01:41:31Z"
  }
}
# exit 0
```

```console
$ (cd work/a && chanchi lesson show 1)
{
  "ok": true,
  "lesson": {
    "id": 1,
    "origin_project_id": 1,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-record",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": 1,
    "session_id": 1,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The executor reported that tests passed, but pytest ran in the wrong package and collected nothing.",
    "evidence": "incident 1: pytest output named no package",
    "cause": "The executor treated a zero exit code as proof without reading what ran.",
    "prevention": "Ask for the collected test count and the package name in every report.",
    "proposal": "Add a line to the executor role about test evidence.",
    "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
    "generality": "agnostic",
    "severity": "high",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "approved",
    "reviewed_at": "2026-11-20T01:41:31Z",
    "reviewed_by_role": "planner",
    "review_conversation": "journey-maint",
    "decision_reason": "holds outside this case and costs one line",
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-a"
  },
  "sites": [
    {
      "site": "project",
      "project": "project-a",
      "state": "applied",
      "where_": ".agents/roles/executor.md [lesson #1] @ abc123",
      "reason": null,
      "decided_conversation": "journey-maint",
      "decided_at": "2026-11-20T01:41:31Z"
    }
  ],
  "replaces": [],
  "incidents": [
    {
      "id": 1,
      "change": "add-export",
      "session": "S3",
      "attempt": 1,
      "code": "false_claim",
      "role": "executor",
      "severity": "high",
      "task_ref": null,
      "detected_by": "planner_audit",
      "description": "tests never ran in the right package",
      "evidence": "pytest output named no package",
      "created_at": "2026-11-20T01:41:31Z",
      "voided_at": null,
      "void_reason": null
    }
  ],
  "events": [
    {
      "id": 1,
      "lesson_id": 1,
      "site": null,
      "site_project_id": null,
      "at": "2026-11-20T01:41:31Z",
      "actor_role": "planner",
      "actor_agent": "claude",
      "conversation": "journey-record",
      "action": "created",
      "from_state": null,
      "to_state": "pending",
      "note": ""
    },
    {
      "id": 2,
      "lesson_id": 1,
      "site": null,
      "site_project_id": null,
      "at": "2026-11-20T01:41:31Z",
      "actor_role": "planner",
      "actor_agent": "claude",
      "conversation": "journey-maint",
      "action": "reviewed",
      "from_state": "pending",
      "to_state": "approved",
      "note": "holds outside this case and costs one line"
    },
    {
      "id": 3,
      "lesson_id": 1,
      "site": "project",
      "site_project_id": 1,
      "at": "2026-11-20T01:41:31Z",
      "actor_role": "planner",
      "actor_agent": "claude",
      "conversation": "journey-maint",
      "action": "applied",
      "from_state": null,
      "to_state": "applied",
      "note": ".agents/roles/executor.md [lesson #1] @ abc123"
    }
  ]
}
# exit 0
```

#### CUJ 3: an executor tries to record a lesson

```console
$ (cd work/a && chanchi lesson add --as executor --author claude:haiku --conversation journey-exec --json -)
{
  "ok": false,
  "error": {
    "code": "not_a_writer",
    "message": "role executor cannot write lessons in project-a",
    "field": "as",
    "valid_values": [
      "planner"
    ],
    "hint": "report the failure instead; writer roles are changed with `chanchi project writers project-a --set ...`"
  }
}
# exit 2
```

```console
$ (cd work/a && chanchi lesson list)
{
  "ok": true,
  "scope": "project-a",
  "lessons": [
    {
      "id": 1,
      "status": "approved",
      "generality": "agnostic",
      "severity": "high",
      "occurrences": 1,
      "target_kind": "role",
      "target": "role executor",
      "general_rule": "test output counts as evidence only if it names what ran and what was skipped",
      "origin": "project-a",
      "sites": {
        "applied": 1,
        "declined": 0,
        "not_applicable": 0,
        "retired": 0
      }
    }
  ]
}
# exit 0
```

#### CUJ 4: commands from inside a nested repository

```console
$ (cd work/b/b-app && chanchi lesson add --as planner --author claude:opus:high --conversation journey-b --json -)
{
  "ok": true,
  "lesson": {
    "id": 2,
    "origin_project_id": 2,
    "author_role": "planner",
    "author_agent": "claude",
    "author_model_raw": "opus",
    "author_model_id": 2,
    "author_effort": "high",
    "author_conversation": "journey-b",
    "git_head": "dce7550e764fea1573e57d56edbefaf155b3028a",
    "change_id": null,
    "session_id": null,
    "target_kind": "role",
    "target": "role executor",
    "what_happened": "The login form accepted an empty password.",
    "evidence": "manual test",
    "cause": "validation only on the server path that was not used",
    "prevention": "validate in the shared form handler",
    "proposal": "add a rule to the executor role",
    "general_rule": "validate input in the shared handler, not in one caller",
    "generality": "agnostic",
    "severity": "medium",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "pending",
    "reviewed_at": null,
    "reviewed_by_role": null,
    "review_conversation": null,
    "decision_reason": null,
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "project-b"
  },
  "warnings": []
}
# exit 0
```

```console
$ (cd work/b/b-app && chanchi change open fix-login --kind adhoc --planner claude:opus:high)
{
  "ok": true,
  "change": {
    "id": 2,
    "project": "project-b",
    "ref": "fix-login",
    "kind": "adhoc",
    "planner": "claude:opus:high",
    "orchestrator": "claude:opus:high",
    "opened_at": "2026-11-20T01:41:31Z",
    "closed_at": null
  }
}
# exit 0
```

```console
$ (cd work/b/b-app && chanchi session start fix-login S1 --executor claude:haiku --task-type docs --complexity low --tasks 1)
{
  "ok": true,
  "session": {
    "id": 2,
    "change": "fix-login",
    "session": "S1",
    "attempt": 1,
    "retry_reason": null,
    "executor": "claude:haiku",
    "task_type": "docs",
    "complexity": "low",
    "tags": [],
    "groups": null,
    "tasks_total": 1,
    "started_at": "2026-11-20T01:41:31Z",
    "ended_at": null,
    "reported_status": null,
    "verdict": null,
    "audited_at": null,
    "notes": null
  }
}
# exit 0
```

```console
$ (cd work/b/b-app && chanchi project list)
{
  "ok": true,
  "projects": [
    {
      "id": 1,
      "slug": "project-a",
      "path": "$S/work/a",
      "registered_at": "2026-11-20T01:41:30Z",
      "locators": [
        "$S/work/a"
      ],
      "writers": {
        "roles": [
          "planner"
        ],
        "default": true
      },
      "lessons": {
        "pending": 0,
        "approved": 1,
        "rejected": 0,
        "postponed": 0,
        "duplicate": 0
      }
    },
    {
      "id": 2,
      "slug": "project-b",
      "path": "$S/work/b",
      "registered_at": "2026-11-20T01:41:30Z",
      "locators": [
        "$S/work/b"
      ],
      "writers": {
        "roles": [
          "planner"
        ],
        "default": true
      },
      "lessons": {
        "pending": 1,
        "approved": 0,
        "rejected": 0,
        "postponed": 0,
        "duplicate": 0
      }
    }
  ]
}
# exit 0
```

```console
$ (cd work/b/b-app && chanchi lesson list)
{
  "ok": true,
  "scope": "project-b",
  "lessons": [
    {
      "id": 2,
      "status": "pending",
      "generality": "agnostic",
      "severity": "medium",
      "occurrences": 1,
      "target_kind": "role",
      "target": "role executor",
      "general_rule": "validate input in the shared handler, not in one caller",
      "origin": "project-b",
      "sites": {
        "applied": 0,
        "declined": 0,
        "not_applicable": 0,
        "retired": 0
      }
    }
  ]
}
# exit 0
```

```console
$ (cd work/b && chanchi show fix-login)
{
  "ok": true,
  "change": {
    "id": 2,
    "project": "project-b",
    "ref": "fix-login",
    "kind": "adhoc",
    "planner": "claude:opus:high",
    "orchestrator": "claude:opus:high",
    "opened_at": "2026-11-20T01:41:31Z",
    "closed_at": null
  },
  "sessions": [
    {
      "id": 2,
      "change": "fix-login",
      "session": "S1",
      "attempt": 1,
      "retry_reason": null,
      "executor": "claude:haiku",
      "task_type": "docs",
      "complexity": "low",
      "tags": [],
      "groups": null,
      "tasks_total": 1,
      "started_at": "2026-11-20T01:41:31Z",
      "ended_at": null,
      "reported_status": null,
      "verdict": null,
      "audited_at": null,
      "notes": null,
      "score": null
    }
  ],
  "incidents": [],
  "planner_score": null,
  "incident_counts_by_role": {},
  "exploration": {
    "sessions": 1,
    "exploratory": 0,
    "allowed": 0,
    "over_budget": null
  }
}
# exit 0
```

#### CUJ 7: a global lesson from outside any project

```console
$ (cd home && chanchi lesson add --as planner --author claude:opus:high --conversation journey-global --json -)
{
  "ok": false,
  "error": {
    "code": "project_not_registered",
    "message": "this directory is not inside a registered project",
    "field": "project",
    "hint": "chanchi project register (or --global where the command allows it)"
  }
}
# exit 2
```

```console
$ (cd home && chanchi lesson add --global --as owner --author human --conversation journey-global --json -)
{
  "ok": true,
  "lesson": {
    "id": 3,
    "origin_project_id": null,
    "author_role": "owner",
    "author_agent": "human",
    "author_model_raw": "human",
    "author_model_id": 1,
    "author_effort": null,
    "author_conversation": "journey-global",
    "git_head": null,
    "change_id": null,
    "session_id": null,
    "target_kind": "skill",
    "target": "skill ~/.agents/skills/chanchi-session-audit",
    "what_happened": "An incident description was split by the shell.",
    "evidence": "incident text shows one word",
    "cause": "unquoted variable in a loop",
    "prevention": "quote --desc literally",
    "proposal": "strengthen the skill rule",
    "general_rule": "pass free text to a CLI as one quoted argument",
    "generality": "agnostic",
    "severity": "medium",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "pending",
    "reviewed_at": null,
    "reviewed_by_role": null,
    "review_conversation": null,
    "decision_reason": null,
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:31Z",
    "origin": "global"
  },
  "warnings": []
}
# exit 0
```

```console
$ (cd home && chanchi lesson add --global --as owner --author human --conversation journey-global --json -)
{
  "ok": false,
  "error": {
    "code": "invalid_value",
    "message": "a global lesson must be agnostic",
    "field": "generality",
    "valid_values": [
      "agnostic"
    ],
    "hint": "a rule that belongs to one project is recorded inside that project"
  }
}
# exit 2
```

```console
$ (cd home && chanchi lesson review 3 --as planner --author claude:opus:high --conversation journey-global-maint --decision approve --reason applies to every audit)
{
  "ok": true,
  "lesson": {
    "id": 3,
    "origin_project_id": null,
    "author_role": "owner",
    "author_agent": "human",
    "author_model_raw": "human",
    "author_model_id": 1,
    "author_effort": null,
    "author_conversation": "journey-global",
    "git_head": null,
    "change_id": null,
    "session_id": null,
    "target_kind": "skill",
    "target": "skill ~/.agents/skills/chanchi-session-audit",
    "what_happened": "An incident description was split by the shell.",
    "evidence": "incident text shows one word",
    "cause": "unquoted variable in a loop",
    "prevention": "quote --desc literally",
    "proposal": "strengthen the skill rule",
    "general_rule": "pass free text to a CLI as one quoted argument",
    "generality": "agnostic",
    "severity": "medium",
    "particular_justification": null,
    "occurrences": 1,
    "tags": [],
    "status": "approved",
    "reviewed_at": "2026-11-20T01:41:32Z",
    "reviewed_by_role": "planner",
    "review_conversation": "journey-global-maint",
    "decision_reason": "applies to every audit",
    "reason_code": null,
    "duplicate_of": null,
    "created_at": "2026-11-20T01:41:31Z",
    "updated_at": "2026-11-20T01:41:32Z",
    "origin": "global"
  },
  "repointed": []
}
# exit 0
```

```console
$ (cd home && chanchi lesson list --global)
{
  "ok": true,
  "scope": "global",
  "lessons": [
    {
      "id": 3,
      "status": "approved",
      "generality": "agnostic",
      "severity": "medium",
      "occurrences": 1,
      "target_kind": "skill",
      "target": "skill ~/.agents/skills/chanchi-session-audit",
      "general_rule": "pass free text to a CLI as one quoted argument",
      "origin": "global",
      "sites": {
        "applied": 0,
        "declined": 0,
        "not_applicable": 0,
        "retired": 0
      }
    }
  ]
}
# exit 0
```

```console
$ (cd home && chanchi lesson summary)
{
  "ok": true,
  "scope": "all",
  "by_status": {
    "pending": 1,
    "approved": 2,
    "rejected": 0,
    "postponed": 0,
    "duplicate": 0
  },
  "by_generality": {
    "agnostic": 3,
    "project": 0,
    "particular": 0
  },
  "applied_sites": {
    "project-a": 1
  },
  "force_new_rate": 0.0
}
# exit 0
```
