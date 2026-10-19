"""Command-line interface. JSON by default; every failure is a structured error envelope."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from chanchi import __version__, catalog, db, projects, record, scoring, skills_link, taxonomy
from chanchi.errors import EXIT_OK, ChanchiError
from chanchi.render import render_text
from chanchi.timeutil import since_to_iso

FORMATS = ("json", "text")


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str):  # argparse calls this on bad input
        raise ChanchiError("invalid_value", message, hint=f"run `{self.prog} --help`")


def _int(field: str):
    def convert(value: str) -> int:
        try:
            val = int(value)
        except ValueError:
            raise ChanchiError("invalid_value", f"{field} must be an integer, got {value!r}", field=field) from None
        if not (0 <= val <= 1_000_000):
            raise ChanchiError(
                "invalid_value",
                f"{field} must be between 0 and 1000000, got {value!r}",
                field=field,
                hint="use an integer between 0 and 1000000",
            )
        return val

    return convert


def _split(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _conn():
    return closing(db.open_operational())


def _pid(conn, args) -> int:
    return projects.resolve_project(conn, args.project)["id"]


# --- handlers --------------------------------------------------------------


def cmd_db_status(args):
    return db.status()


def cmd_db_migrate(args):
    return db.migrate_template() if args.template else db.bootstrap()


def cmd_models_add(args):
    with _conn() as conn:
        return {
            "model": catalog.add_model(
                conn, agent=args.agent, model=args.model, cost_tier=args.cost,
                efforts=_split(args.efforts), notes=args.notes,
            )
        }


def cmd_models_list(args):
    with _conn() as conn:
        return {"models": catalog.list_models(conn, include_inactive=args.include_inactive)}


def cmd_models_set(args):
    active = None if args.active is None else bool(taxonomy.validate_choice("active", args.active, (0, 1)))
    with _conn() as conn:
        return {
            "model": catalog.set_model(
                conn, spec=args.spec, cost_tier=args.cost, active=active,
                efforts=_split(args.efforts), notes=args.notes,
            )
        }


def cmd_taxonomy_list(args):
    with _conn() as conn:
        return {"taxonomy": taxonomy.describe(), "task_types": catalog.list_task_types(conn)}


def cmd_taxonomy_add_type(args):
    with _conn() as conn:
        return {"task_type": catalog.add_task_type(conn, code=args.code, description=args.description)}


def _skills_base(args) -> Path:
    return Path.home() if args.global_ else Path(args.path)


def cmd_skills_link(args):
    return skills_link.link(_skills_base(args), global_=args.global_)


def cmd_skills_unlink(args):
    return skills_link.unlink(_skills_base(args), global_=args.global_)


def cmd_change_open(args):
    slug, path = projects.identify(args.project)
    with _conn() as conn:
        return {
            "change": record.open_change(
                conn, project_slug=slug, project_path=path, ref=args.ref, kind=args.kind,
                planner=args.planner, orchestrator=args.orchestrator,
            )
        }


def cmd_change_close(args):
    with _conn() as conn:
        return {"change": record.close_change(conn, project_id=_pid(conn, args), ref=args.ref)}


def cmd_session_start(args):
    with _conn() as conn:
        return {
            "session": record.start_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                executor=args.executor, task_type=args.task_type, complexity=args.complexity,
                tasks_total=args.tasks_total, groups=args.groups, tags=args.tags,
                retry_reason=args.retry_reason,
            )
        }


def cmd_session_report(args):
    with _conn() as conn:
        return {
            "session": record.report_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                status=args.status, attempt=args.attempt,
            )
        }


def cmd_session_audit(args):
    with _conn() as conn:
        return {
            "session": record.audit_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                verdict=args.verdict, notes=args.notes, attempt=args.attempt,
            )
        }


def cmd_session_update(args):
    with _conn() as conn:
        return {
            "session": record.update_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                attempt=args.attempt, task_type=args.task_type, complexity=args.complexity,
                tags=args.tags, tasks_total=args.tasks_total, notes=args.notes,
            )
        }


def cmd_incident_add(args):
    with _conn() as conn:
        return {
            "incident": record.add_incident(
                conn, project_id=_pid(conn, args), ref=args.ref, code=args.code,
                severity=args.severity, detected_by=args.detected_by, description=args.description,
                evidence=args.evidence, session_ref=args.session, attempt=args.attempt,
                task_ref=args.task_ref, role=args.role,
            )
        }


def cmd_incident_void(args):
    with _conn() as conn:
        return {"incident": record.void_incident(conn, incident_id=args.id, reason=args.reason)}


def cmd_recommend(args):
    with _conn() as conn:
        return scoring.recommend(
            conn, task_type=args.task_type, complexity=args.complexity, available=_split(args.available) or []
        )


def cmd_stats(args):
    since = since_to_iso(args.since) if args.since else None
    with _conn() as conn:
        project_id = projects.resolve_project(conn, args.project)["id"] if args.project else None
        return scoring.stats(conn, role=args.role, by=args.by, project_id=project_id, since=since)


def cmd_show(args):
    with _conn() as conn:
        return scoring.show_change(conn, project_id=_pid(conn, args), ref=args.ref)


def cmd_scoring_explain(args):
    return scoring.explain()


# --- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    common.add_argument("--format", choices=FORMATS, default="json", help="output format (default: json)")
    common.add_argument("--project", default=None, help="project slug (default: git toplevel name)")

    parser = _Parser(prog="chanchi", description="Turn planner/executor agent audits into model ratings.")
    parser.add_argument("--version", action="version", version=f"chanchi {__version__}")
    top = parser.add_subparsers(dest="group", required=True, metavar="<command>")

    def group(name: str, help_text: str):
        return top.add_parser(name, help=help_text, description=help_text).add_subparsers(
            dest="command", required=True, metavar="<subcommand>"
        )

    def leaf(subparsers, name: str, handler, help_text: str):
        p = subparsers.add_parser(name, parents=[common], help=help_text, description=help_text)
        p.set_defaults(handler=handler)
        return p

    g = group("db", "template and operational databases")
    leaf(g, "status", cmd_db_status, "show database paths, versions and pending migrations")
    p = leaf(g, "migrate", cmd_db_migrate, "apply pending migrations (operational database by default)")
    p.add_argument("--template", action="store_true", help="migrate the committed template (developer step)")

    g = group("models", "model catalog")
    p = leaf(g, "add", cmd_models_add, "register a model in the catalog")
    p.add_argument("--agent", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--cost", required=True, type=_int("cost"), help="1=$ 2=$$ 3=$$$")
    p.add_argument("--efforts", help="comma list of supported efforts, e.g. low,medium,high")
    p.add_argument("--notes")
    p = leaf(g, "list", cmd_models_list, "list active catalog models")
    p.add_argument("--all", dest="include_inactive", action="store_true", help="include inactive models")
    p = leaf(g, "set", cmd_models_set, "update a catalog model")
    p.add_argument("spec", help="agent:model (no effort)")
    p.add_argument("--cost", type=_int("cost"))
    p.add_argument("--active", type=_int("active"), help="0 or 1")
    p.add_argument("--efforts")
    p.add_argument("--notes")

    g = group("taxonomy", "enums, incident codes and task types")
    leaf(g, "list", cmd_taxonomy_list, "list every enum, incident code, role, weight and task type")
    p = leaf(g, "add-type", cmd_taxonomy_add_type, "add a task type")
    p.add_argument("code")
    p.add_argument("--description", required=True)

    g = group("skills", "mirror chanchi skills into a project or ~")
    for name, handler in (("link", cmd_skills_link), ("unlink", cmd_skills_unlink)):
        p = leaf(g, name, handler, f"{name} the chanchi skills")
        p.add_argument("path", nargs="?", default=".", help="project directory (default: cwd)")
        p.add_argument("--global", dest="global_", action="store_true", help="target ~ instead of a project")

    g = group("change", "OpenSpec or adhoc changes")
    p = leaf(g, "open", cmd_change_open, "open a change (creates the project on first use)")
    p.add_argument("ref")
    p.add_argument("--kind", required=True, help="openspec | adhoc")
    p.add_argument("--planner", required=True, help="agent:model[:effort] or human")
    p.add_argument("--orchestrator", help="defaults to --planner")
    p = leaf(g, "close", cmd_change_close, "close a change")
    p.add_argument("ref")

    g = group("session", "executor sessions")
    p = leaf(g, "start", cmd_session_start, "record the start of an executor session")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--executor", required=True, help="agent:model[:effort]")
    p.add_argument("--task-type", required=True)
    p.add_argument("--complexity", required=True)
    p.add_argument("--tasks", dest="tasks_total", required=True, type=_int("tasks"))
    p.add_argument("--groups")
    p.add_argument("--tags")
    p.add_argument("--retry-reason")
    p = leaf(g, "report", cmd_session_report, "record the executor's reported status")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--status", required=True, help="COMPLETE | STOPPED | BLOCKED")
    p.add_argument("--attempt", type=_int("attempt"))
    p = leaf(g, "audit", cmd_session_audit, "record the audit verdict")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--verdict", required=True, help="accepted | accepted_with_fixes | rejected")
    p.add_argument("--notes")
    p.add_argument("--attempt", type=_int("attempt"))
    p = leaf(g, "update", cmd_session_update, "correct a session's classification")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--attempt", type=_int("attempt"), help="selects, never changes, the attempt")
    p.add_argument("--task-type")
    p.add_argument("--complexity")
    p.add_argument("--tags")
    p.add_argument("--tasks", dest="tasks_total", type=_int("tasks"))
    p.add_argument("--notes")

    g = group("incident", "audit incidents")
    p = leaf(g, "add", cmd_incident_add, "record an incident with evidence")
    p.add_argument("ref")
    p.add_argument("--session")
    p.add_argument("--attempt", type=_int("attempt"))
    p.add_argument("--code", required=True)
    p.add_argument("--severity", required=True)
    p.add_argument("--detected-by", required=True)
    p.add_argument("--desc", dest="description", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--task", dest="task_ref")
    p.add_argument("--role", help="only for hallucination: planner | executor")
    p = leaf(g, "void", cmd_incident_void, "void an incident without deleting it")
    p.add_argument("id", type=_int("id"))
    p.add_argument("--reason", required=True)

    p = leaf(top, "recommend", cmd_recommend, "recommend a model for a task type and complexity")
    p.add_argument("--task-type", required=True)
    p.add_argument("--complexity", required=True)
    p.add_argument("--available", required=True, help="comma list of agent:model[:effort]")

    p = leaf(top, "stats", cmd_stats, "aggregate scores")
    p.add_argument("--role", default="executor", help="executor | planner | human")
    p.add_argument("--by", default="model", help="model | task-type | project")
    p.add_argument("--since", help="YYYY-MM-DD")

    p = leaf(top, "show", cmd_show, "timeline of one change: sessions, incidents, scores")
    p.add_argument("ref")

    g = group("scoring", "scoring formulas")
    leaf(g, "explain", cmd_scoring_explain, "show current weights and formulas")
    return parser


# --- entry point -----------------------------------------------------------


def _sniff_format(argv: list[str]) -> str:
    for index, arg in enumerate(argv):
        if arg == "--format" and index + 1 < len(argv):
            return argv[index + 1] if argv[index + 1] in FORMATS else "json"
        if arg.startswith("--format="):
            value = arg.split("=", 1)[1]
            return value if value in FORMATS else "json"
    return "json"


def _emit(payload: dict, fmt: str, stream) -> None:
    if fmt == "text":
        stream.write(render_text(payload))
    else:
        stream.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    fmt = _sniff_format(argv)
    try:
        args = build_parser().parse_args(argv)
        fmt = args.format
        payload = args.handler(args)
        _emit({"ok": True, **payload}, fmt, sys.stdout)
        return EXIT_OK
    except SystemExit as exc:  # --help and --version
        return exc.code if isinstance(exc.code, int) else EXIT_OK
    except ChanchiError as exc:
        _emit(exc.to_dict(), fmt, sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 - every failure must reach the caller as JSON
        if isinstance(exc, sqlite3.OperationalError) and ("locked" in str(exc).lower() or "busy" in str(exc).lower()):
            error = ChanchiError(
                "database_busy",
                "the database is busy; another chanchi process is writing",
                hint="retry the same command in a few seconds",
            )
        else:
            error = ChanchiError(
                "internal",
                f"{type(exc).__name__}: {exc}",
                hint="this is a chanchi bug; report the command you ran",
            )
        _emit(error.to_dict(), fmt, sys.stderr)
        return error.exit_code
