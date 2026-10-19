"""Test helpers to build realistic audit histories quickly."""

from chanchi import projects, record


def inc(code, severity="low", detected_by="planner_audit", role=None):
    data = {
        "code": code,
        "severity": severity,
        "detected_by": detected_by,
        "description": f"{code} observed",
        "evidence": "test evidence",
    }
    if role is not None:
        data["role"] = role
    return data


class Recorder:
    def __init__(self, conn):
        self.conn = conn

    def change(self, ref, planner="claude:opus:xhigh", kind="openspec"):
        slug, path = projects.identify()
        return record.open_change(
            self.conn, project_slug=slug, project_path=path, ref=ref, kind=kind, planner=planner
        )

    @property
    def pid(self):
        return projects.resolve_project(self.conn)["id"]

    def session(
        self,
        ref,
        session_ref,
        executor,
        *,
        task_type="ui-component",
        complexity="medium",
        tasks=5,
        verdict="accepted",
        status="COMPLETE",
        retry_reason=None,
        started="2026-10-01T10:00:00Z",
        ended="2026-10-01T11:00:00Z",
        incidents=(),
    ):
        pid = self.pid
        created = record.start_session(
            self.conn,
            project_id=pid,
            ref=ref,
            session_ref=session_ref,
            executor=executor,
            task_type=task_type,
            complexity=complexity,
            tasks_total=tasks,
            retry_reason=retry_reason,
            now=started,
        )
        if status is not None:
            record.report_session(
                self.conn, project_id=pid, ref=ref, session_ref=session_ref, status=status, now=ended
            )
        for incident in incidents:
            record.add_incident(self.conn, project_id=pid, ref=ref, session_ref=session_ref, **incident)
        if verdict is not None:
            record.audit_session(self.conn, project_id=pid, ref=ref, session_ref=session_ref, verdict=verdict)
        return created
