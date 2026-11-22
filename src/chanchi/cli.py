"""Command-line interface. JSON by default; every failure is a structured error envelope."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from chanchi import (
    __version__,
    agents_sync,
    audits,
    catalog,
    db,
    items,
    lessons,
    projects,
    record,
    scoring,
    skills_link,
    sync,
    taxonomy,
)
from chanchi.errors import EXIT_OK, ChanchiError
from chanchi.render import render_text
from chanchi.timeutil import since_to_iso

FORMATS = ("json", "text", "md")


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
    capabilities = catalog.parse_capabilities(args.capability) if args.capability else None
    with _conn() as conn:
        return {
            "model": catalog.add_model(
                conn, agent=args.agent, model=args.model, cost_tier=args.cost,
                efforts=_split(args.efforts), notes=args.notes, capabilities=capabilities,
                family=args.family,
            )
        }


def cmd_models_list(args):
    with _conn() as conn:
        return {"models": catalog.list_models(conn, include_inactive=args.include_inactive)}


def cmd_models_set(args):
    active = None if args.active is None else bool(taxonomy.validate_choice("active", args.active, (0, 1)))
    capabilities = catalog.parse_capabilities(args.capability) if args.capability else None
    with _conn() as conn:
        return {
            "model": catalog.set_model(
                conn, spec=args.spec, cost_tier=args.cost, active=active,
                efforts=_split(args.efforts), notes=args.notes, capabilities=capabilities,
                family=args.family,
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
    return skills_link.link(_skills_base(args), global_=args.global_, compat=not args.no_compat)


def cmd_skills_unlink(args):
    return skills_link.unlink(_skills_base(args), global_=args.global_)


def cmd_agents_sync(args):
    root = Path(args.path) if args.path else projects.git_toplevel()
    if root is None:
        raise ChanchiError("invalid_value", "not inside a git repository", field="path",
                           hint="pass the repository path: chanchi agents sync <path>")
    return agents_sync.sync(root, check=args.check)


def cmd_agents_link(args):
    if not args.user:
        raise ChanchiError("invalid_value", "`chanchi agents link` requires --user in this version", field="user",
                           hint="chanchi agents link --user")
    root = Path(args.root) if args.root else agents_sync.repo_root()
    return agents_sync.link_user(root, check=args.check, remove=args.remove)


def cmd_sync_init(args):
    if args.link is not None and not args.link.strip():
        raise ChanchiError("invalid_value", "link directory must not be empty", field="link")
    link = Path(args.link) if args.link is not None else None
    return sync.init(link=link)


def cmd_sync_status(args):
    return sync.status()


def cmd_change_open(args):
    with _conn() as conn:
        slug, path = projects.identify(args.project, conn=conn)
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
            conn,
            task_type=args.task_type,
            complexity=args.complexity,
            available=_split(args.available) or [],
            require=_split(args.require),
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


# --- project and lesson handlers -------------------------------------------


def _bad(field: str, message: str, **kwargs) -> ChanchiError:
    return ChanchiError("invalid_value", message, field=field, **kwargs)


def _actor(conn, args) -> lessons.Actor:
    return lessons.make_actor(conn, args.as_role, args.author, args.conversation)


def _read_json(source: str) -> object:
    """The body of `--json -` (stdin) or `--json <file>`; anything unreadable or unparsable is invalid_value."""
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except OSError as exc:
        raise _bad("json", f"cannot read --json {source!r}: {exc.strerror or exc}", hint="use --json - or a readable file") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _bad("json", f"--json is not valid JSON: {exc}", hint="send one JSON object") from None


def _read_scope(conn, args) -> projects.Scope | None:
    """Scope of a read command: --all, --global, --project, the resolved project, else every lesson (None)."""
    if args.all:
        if args.project is not None:
            raise _bad("project", "--all cannot be combined with --project")
        return None
    if args.global_ or args.project is not None:
        return projects.resolve_scope(conn, project=args.project, global_=args.global_)
    try:
        return projects.resolve_scope(conn)
    except ChanchiError as exc:
        if exc.code != "project_not_registered":
            raise
        return None


def _project_arg(args) -> str | None:
    """The slug of `project show` and `project writers`: a positional slug wins; both given must agree."""
    slug = args.slug
    if slug is not None and args.project is not None and args.project != slug:
        raise _bad("project", f"the slug {slug!r} and --project {args.project!r} differ", hint="give only one")
    return slug if slug is not None else args.project


def cmd_project_register(args):
    with _conn() as conn:
        return projects.register(conn, name=args.name)


def cmd_project_relink(args):
    with _conn() as conn:
        return projects.relink(conn, args.slug)


def cmd_project_list(args):
    with _conn() as conn:
        return {"projects": projects.list_projects(conn)}


def cmd_project_show(args):
    with _conn() as conn:
        slug = _project_arg(args)
        if slug is None:
            slug = projects.resolve_scope(conn).slug
        return projects.show(conn, slug)


def cmd_project_writers(args):
    with _conn() as conn:
        slug = _project_arg(args)
        if args.global_ and slug is not None:
            raise _bad("global", "--global cannot be combined with a project slug")
        scope = projects.resolve_scope(conn, project=slug, global_=args.global_)
        if args.set is None:
            return {"scope": scope.slug or "global", **projects.writers_info(conn, scope.project_id)}
        for flag, value in (("as", args.as_role), ("author", args.author), ("conversation", args.conversation)):
            if value is None:
                raise _bad(flag, f"--{flag} is required with --set")
        return lessons.set_writers(conn, scope, _actor(conn, args), _split(args.set) or [])


def cmd_lesson_add(args):
    body = _read_json(args.json)
    with _conn() as conn:
        scope = projects.resolve_scope(conn, project=args.project, global_=args.global_)
        return lessons.add(conn, scope, _actor(conn, args), body, force_new=args.force_new)


def cmd_lesson_repeat(args):
    with _conn() as conn:
        return lessons.repeat(conn, _actor(conn, args), args.id, args.evidence, incident=args.incident)


def cmd_lesson_modify(args):
    body = _read_json(args.json)
    with _conn() as conn:
        return lessons.modify(conn, _actor(conn, args), args.id, body)


def cmd_lesson_review(args):
    with _conn() as conn:
        return lessons.review(
            conn, _actor(conn, args), args.id, args.decision, args.reason,
            reason_code=args.reason_code, of=args.of,
        )


def cmd_lesson_reopen(args):
    with _conn() as conn:
        return lessons.reopen(conn, _actor(conn, args), args.id, args.reason)


def _site_scope(conn, args) -> projects.Scope | None:
    """`--site project` resolves the project from --project or the working directory; `global` needs none."""
    if args.site != "project":
        return None
    return projects.resolve_scope(conn, project=args.project)


def cmd_lesson_apply(args):
    with _conn() as conn:
        return lessons.apply(
            conn, _actor(conn, args), args.id, args.site, args.where, project_scope=_site_scope(conn, args)
        )


def cmd_lesson_retire(args):
    with _conn() as conn:
        return lessons.retire(
            conn, _actor(conn, args), args.id, args.site, args.reason, project_scope=_site_scope(conn, args)
        )


def cmd_lesson_similar(args):
    with _conn() as conn:
        return lessons.similar(conn, args.text, limit=args.limit)


def cmd_lesson_list(args):
    with _conn() as conn:
        return lessons.list_lessons(
            conn, _read_scope(conn, args), status=args.status, generality=args.generality,
            target_kind=args.target_kind, limit=args.limit,
        )


def cmd_lesson_show(args):
    with _conn() as conn:
        return lessons.show(conn, args.id)


def cmd_lesson_summary(args):
    with _conn() as conn:
        return lessons.summary(conn, _read_scope(conn, args))


def cmd_lesson_export(args):
    since = since_to_iso(args.since) if args.since else None
    extra = {"status": _split(args.status)} if args.status is not None else {}
    with _conn() as conn:
        payload = lessons.export(
            conn, _read_scope(conn, args), generality=args.generality, target_kind=args.target_kind,
            since=since, limit=args.limit, **extra,
        )
    if args.format == "md":
        payload["markdown"] = lessons.export_markdown(payload["lessons"])
    return payload


# --- audit handlers ---------------------------------------------------------


def cmd_audit_open(args):
    roster = sync.roster()
    with _conn() as conn:
        return audits.open_audit(
            conn, kind=args.kind, ref=args.ref, author=args.author, commit=args.commit,
            version=args.version, change=args.change,
            project_id=audits.resolve_project_id(conn, args.project),
            roster=roster, which=shutil.which, sync_root=sync.sync_dir(),
        )


def cmd_audit_unavailable(args):
    roster = sync.roster()
    with _conn() as conn:
        return audits.mark_unavailable(
            conn, args.id, round=args.round, seat=args.seat, reason=args.reason,
            roster=roster, which=shutil.which,
        )


def cmd_audit_show(args):
    with _conn() as conn:
        return audits.show(conn, args.id)


def cmd_audit_list(args):
    with _conn() as conn:
        return {"audits": audits.list_audits(conn, kind=args.kind, ref=args.ref)}


def cmd_audit_vote(args):
    with _conn() as conn:
        return audits.vote(
            conn, args.id, round=args.round, seat=args.seat, verdict=args.verdict,
            blocking=args.blocking, major=args.major, minor=args.minor, report=args.report,
        )


def cmd_audit_dissent(args):
    with _conn() as conn:
        return audits.dissent(
            conn, args.id, round=args.round, seat=args.seat, finding=args.finding,
            severity=args.severity, decision=args.decision, evidence=args.evidence,
        )


def cmd_audit_close(args):
    with _conn() as conn:
        return audits.close_round(conn, args.id, round=args.round)


def cmd_audit_round(args):
    roster = sync.roster()
    with _conn() as conn:
        return audits.next_round(
            conn, args.id, commit=args.commit, version=args.version, roster=roster, which=shutil.which,
            sync_root=sync.sync_dir(),
        )


# --- items handlers ---------------------------------------------------------


def cmd_items_check(args):
    result = items.check(sync.require(), own_names=items.own_names())
    if result["problems"]:
        raise ChanchiError(
            "invalid_value",
            f"{len(result['problems'])} problem(s) in SYNC/ITEMS",
            field="items",
            hint="fix every listed problem, then run `chanchi items check` again",
            details={"problems": result["problems"]},
        )
    return {"items": [item.to_dict() for item in result["items"]], "problems": []}


def cmd_items_list(args):
    return {"items": items.list_items(sync.require())}


def cmd_items_publish(args):
    root = sync.require()
    with _conn() as conn:
        return items.publish(conn, root, args.name, audit_id=args.audit, own_names=items.own_names())


def cmd_items_retire(args):
    return items.retire(sync.require(), args.name, reason=args.reason, replaced_by=args.replaced_by)


def cmd_items_mirror(args):
    if args.check and args.remove:
        raise ChanchiError("invalid_value", "--check and --remove are mutually exclusive", field="check",
                           hint="pass either --check or --remove, not both")
    root = None if args.remove else sync.require()  # --remove works without SYNC
    return items.mirror(root, env=os.environ, home=Path.home(), db_dir=db.operational_path().parent,
                        own_names=items.own_names(), check=args.check, remove=args.remove)


# --- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    common.add_argument("--format", choices=FORMATS, default="json", help="output format (default: json)")
    common.add_argument(
        "--project", default=None,
        help="project slug (default: the registered project for this directory, else the git toplevel name)",
    )
    # commands that never take --project (they act on the lesson's origin, or on no project)
    fmt_only = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    fmt_only.add_argument("--format", choices=FORMATS, default="json", help="output format (default: json)")

    identity = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    identity.add_argument("--as", dest="as_role", required=True, help="the role you declare, e.g. planner")
    identity.add_argument("--author", dest="author", required=True, help="agent:model[:effort] of whoever runs this")
    identity.add_argument(
        "--conversation", dest="conversation", required=True, help="conversation id, or a label you reuse"
    )

    parser = _Parser(prog="chanchi", description="Turn planner/executor agent audits into model ratings.")
    parser.add_argument("--version", action="version", version=f"chanchi {__version__}")
    top = parser.add_subparsers(dest="group", required=True, metavar="<command>")

    def group(name: str, help_text: str):
        return top.add_parser(name, help=help_text, description=help_text).add_subparsers(
            dest="command", required=True, metavar="<subcommand>"
        )

    def leaf(subparsers, name: str, handler, help_text: str, parents=(), project: bool = True):
        p = subparsers.add_parser(
            name, parents=[common if project else fmt_only, *parents], help=help_text, description=help_text
        )
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
    p.add_argument("--family", help="model family slug (default: inferred from the model name)")
    p.add_argument(
        "--capability", action="append", metavar="NAME=VALUE",
        help="capability setting, e.g. vision=yes (repeatable)",
    )
    p = leaf(g, "list", cmd_models_list, "list active catalog models")
    p.add_argument("--all", dest="include_inactive", action="store_true", help="include inactive models")
    p = leaf(g, "set", cmd_models_set, "update a catalog model")
    p.add_argument("spec", help="agent:model (no effort)")
    p.add_argument("--cost", type=_int("cost"))
    p.add_argument("--active", type=_int("active"), help="0 or 1")
    p.add_argument("--efforts")
    p.add_argument("--notes")
    p.add_argument("--family", help="model family slug, e.g. google")
    p.add_argument(
        "--capability", action="append", metavar="NAME=VALUE",
        help="capability setting, e.g. vision=yes (repeatable)",
    )

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
        if name == "link":
            p.add_argument(
                "--no-compat", dest="no_compat", action="store_true",
                help="with --global, remove the chanchi-<n> compatibility links instead of creating them",
            )

    g = group("agents", "compile agents/<name>/AGENT.md into per-harness wrappers")
    p = leaf(g, "sync", cmd_agents_sync, "write the generated agent wrappers", project=False)
    p.add_argument("path", nargs="?", help="repository root (default: git top level)")
    p.add_argument("--check", action="store_true", help="write nothing; fail if any wrapper is stale")
    p = leaf(g, "link", cmd_agents_link, "compile install: user agents into user harness folders", project=False)
    p.add_argument("root", nargs="?", help="repository root (default: chanchi's repository)")
    p.add_argument("--user", action="store_true", help="link agents with install: user into user harness folders")
    p.add_argument("--check", action="store_true", help="write nothing; fail if user agent wrappers are stale")
    p.add_argument("--remove", action="store_true", help="remove user agent wrappers owned by this root")

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
    p.add_argument("--require", help="comma list of required capabilities, e.g. vision")

    p = leaf(top, "stats", cmd_stats, "aggregate scores")
    p.add_argument("--role", default="executor", help="executor | planner | human")
    p.add_argument(
        "--by",
        default="model",
        help="model | task-type | project | dimension (dimension is executor-only)",
    )
    p.add_argument("--since", help="YYYY-MM-DD")

    p = leaf(top, "show", cmd_show, "timeline of one change: sessions, incidents, scores")
    p.add_argument("ref")

    g = group("project", "register projects and manage who may write lessons")
    p = leaf(g, "register", cmd_project_register, "register the project that contains this directory", project=False)
    p.add_argument("--name", help="slug (default: the main worktree folder name)")
    p = leaf(g, "relink", cmd_project_relink, "add this directory as a location of a registered project", project=False)
    p.add_argument("slug")
    leaf(g, "list", cmd_project_list, "list registered projects", project=False)
    p = leaf(g, "show", cmd_project_show, "show one project: locations, writer roles, lesson counts")
    p.add_argument("slug", nargs="?", help="default: the registered project for this directory")
    p = leaf(g, "writers", cmd_project_writers, "show or set the roles that may write lessons")
    p.add_argument("slug", nargs="?", help="default: the registered project for this directory")
    p.add_argument("--global", dest="global_", action="store_true", help="the global writer roles")
    p.add_argument("--set", metavar="ROLE,...", help="replace the writer roles (needs --as, --author, --conversation)")
    p.add_argument("--as", dest="as_role", help="the role you declare (required with --set)")
    p.add_argument("--author", dest="author", help="agent:model[:effort] (required with --set)")
    p.add_argument("--conversation", dest="conversation", help="conversation id or label (required with --set)")

    def read_scope(p):
        mode = p.add_mutually_exclusive_group()
        mode.add_argument("--all", action="store_true", help="every lesson, whatever its origin")
        mode.add_argument("--global", dest="global_", action="store_true", help="only global lessons")

    g = group("lesson", "record, review and apply lessons")
    p = leaf(g, "add", cmd_lesson_add, "record a lesson from a JSON body", parents=[identity])
    p.add_argument("--json", required=True, metavar="-|FILE", help="the lesson body: '-' reads stdin, else a file")
    p.add_argument("--force-new", action="store_true", help="record even when it looks like an existing lesson")
    p.add_argument("--global", dest="global_", action="store_true", help="record a global lesson")
    p = leaf(g, "repeat", cmd_lesson_repeat, "count one more occurrence of a lesson", parents=[identity], project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--evidence", required=True)
    p.add_argument("--incident", type=_int("incident"), help="an incident of the lesson's change")
    p = leaf(g, "modify", cmd_lesson_modify, "replace the body of a pending or postponed lesson", parents=[identity], project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--json", required=True, metavar="-|FILE", help="the full lesson body: '-' reads stdin, else a file")
    p = leaf(g, "review", cmd_lesson_review, "approve, reject, postpone or mark a lesson duplicate", parents=[identity], project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--decision", required=True, choices=taxonomy.LESSON_DECISIONS)
    p.add_argument("--reason", required=True)
    p.add_argument("--reason-code", help="with reject only: " + " | ".join(taxonomy.LESSON_REASON_CODES))
    p.add_argument("--of", type=_int("of"), help="the lesson this one duplicates (required with duplicate)")
    p = leaf(g, "reopen", cmd_lesson_reopen, "send a reviewed lesson back to pending", parents=[identity], project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--reason", required=True)
    p = leaf(g, "apply", cmd_lesson_apply, "mark an approved lesson as applied at a site", parents=[identity])
    p.add_argument("id", type=_int("id"))
    p.add_argument("--site", required=True, help="global | project")
    p.add_argument("--where", required=True, help='"<path> [lesson #<id>] @ <commit>"')
    p = leaf(g, "retire", cmd_lesson_retire, "retire an applied lesson at a site", parents=[identity])
    p.add_argument("id", type=_int("id"))
    p.add_argument("--site", required=True, help="global | project")
    p.add_argument("--reason", required=True)
    p = leaf(g, "similar", cmd_lesson_similar, "find existing lessons that look like a text", project=False)
    p.add_argument("text")
    p.add_argument("--limit", type=_int("limit"), default=5)
    p = leaf(g, "list", cmd_lesson_list, "list lessons")
    p.add_argument("--status")
    p.add_argument("--generality")
    p.add_argument("--target-kind")
    p.add_argument("--limit", type=_int("limit"), default=50)
    read_scope(p)
    p = leaf(g, "show", cmd_lesson_show, "one lesson with its sites, incidents and events", project=False)
    p.add_argument("id", type=_int("id"))
    p = leaf(g, "summary", cmd_lesson_summary, "counts by status, generality and applied place")
    read_scope(p)
    p = leaf(g, "export", cmd_lesson_export, "lessons for a review conversation, most urgent first")
    p.add_argument("--status", help="comma list (default: pending,postponed)")
    p.add_argument("--generality")
    p.add_argument("--target-kind")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--limit", type=_int("limit"), default=20)
    read_scope(p)

    g = group("audit", "redundant audits: three auditors of different model families")
    p = leaf(g, "open", cmd_audit_open, "open an audit and seat three auditors from the roster")
    p.add_argument("--kind", required=True, help=" | ".join(taxonomy.AUDIT_SUBJECT_KINDS))
    p.add_argument("--ref", required=True, help="the subject: a path, an item name, <project>:<item>")
    p.add_argument("--author", required=True, help="agent:model[:effort] that made the subject")
    subject = p.add_mutually_exclusive_group(required=True)
    subject.add_argument("--commit", help="the commit the first round audits")
    subject.add_argument("--version", help="the item version the first round audits")
    p.add_argument("--change", help="a chanchi change ref of the project (needs a project)")
    p = leaf(g, "unavailable", cmd_audit_unavailable, "mark a seat's auditor unavailable and refill the seat", project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--round", required=True, type=_int("round"))
    p.add_argument("--seat", required=True, type=_int("seat"))
    p.add_argument("--reason", required=True, help="the error that stopped the auditor")
    p = leaf(g, "show", cmd_audit_show, "every round, seat, vote, dissent and outcome of one audit", project=False)
    p.add_argument("id", type=_int("id"))
    p = leaf(g, "list", cmd_audit_list, "list audits with their last outcome", project=False)
    p.add_argument("--kind")
    p.add_argument("--ref")
    p = leaf(g, "vote", cmd_audit_vote, "record a seat's verdict, finding counts and report path", project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--round", required=True, type=_int("round"))
    p.add_argument("--seat", required=True, type=_int("seat"))
    p.add_argument("--verdict", required=True, help=" | ".join(taxonomy.AUDIT_VERDICTS))
    p.add_argument("--blocking", required=True, type=_int("blocking"))
    p.add_argument("--major", required=True, type=_int("major"))
    p.add_argument("--minor", required=True, type=_int("minor"))
    p.add_argument("--report", required=True, help="path to the auditor's report")
    p = leaf(g, "dissent", cmd_audit_dissent, "record a confirmed or rejected decision on a lone finding", project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--round", required=True, type=_int("round"))
    p.add_argument("--seat", required=True, type=_int("seat"))
    p.add_argument("--finding", required=True, help='"<id: text>" of the lone finding')
    p.add_argument("--severity", required=True, help=" | ".join(taxonomy.AUDIT_SEVERITIES))
    p.add_argument("--decision", required=True, help=" | ".join(taxonomy.DISSENT_DECISIONS))
    p.add_argument("--evidence", required=True, help="why the finding is confirmed or rejected")
    p = leaf(g, "close", cmd_audit_close, "close an audit round and compute its outcome", project=False)
    p.add_argument("id", type=_int("id"))
    p.add_argument("--round", required=True, type=_int("round"))
    p = leaf(g, "round", cmd_audit_round, "open the next round with the same seats when still available", project=False)
    p.add_argument("id", type=_int("id"))
    nxt = p.add_mutually_exclusive_group(required=True)
    nxt.add_argument("--commit", help="the commit the next round audits")
    nxt.add_argument("--version", help="the item version the next round audits")

    g = group("scoring", "scoring formulas")
    leaf(g, "explain", cmd_scoring_explain, "show current weights and formulas")

    g = group("sync", "manage the user's SYNC folder for global items and configuration")
    p = leaf(g, "init", cmd_sync_init, "initialize SYNC/config and SYNC/ITEMS", project=False)
    p.add_argument("--link", metavar="DIR", help="symlink SYNC to an existing or new directory")
    leaf(g, "status", cmd_sync_status, "show SYNC location, symlink target and reachability", project=False)

    g = group("items", "global agents and skills in SYNC/ITEMS")
    leaf(g, "check", cmd_items_check, "validate SYNC/ITEMS: names, frontmatter, versions, hashes, retirements", project=False)
    leaf(g, "list", cmd_items_list, "list global items with version, status and hashes", project=False)
    p = leaf(g, "publish", cmd_items_publish, "publish a draft item after an accepted item audit", project=False)
    p.add_argument("name", help="the item: <agent|skill>-chanchi-global-<name>")
    p.add_argument("--audit", required=True, type=_int("audit"), help="the id of the accepted `item` audit")
    p = leaf(g, "retire", cmd_items_retire, "retire an item and record it in retired.json", project=False)
    p.add_argument("name", help="the item: <agent|skill>-chanchi-global-<name>")
    p.add_argument("--replaced-by", dest="replaced_by", help="the item that replaces it (same kind, not retired)")
    p.add_argument("--reason", required=True, help="why the item is retired")
    p = leaf(g, "mirror", cmd_items_mirror, "expose published items to the installed harnesses", project=False)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="write nothing; fail if the mirror is stale")
    mode.add_argument("--remove", action="store_true", help="remove every entry the mirror made")
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
    if fmt == "md" and isinstance(payload.get("markdown"), str):
        stream.write(payload["markdown"])
    elif fmt in ("text", "md"):
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
