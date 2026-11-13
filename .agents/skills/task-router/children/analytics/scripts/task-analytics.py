"""Task analytics: deterministic analysis of Kilo dialogs.

Reads kilo.db in read-only mode, builds per-session facts, attributes sessions
to tasks and writes analysis files under .doc/tasks/{N}/dialogs/.

Exit codes: 0 complete, 1 partial (open session or db lag), 2 error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import attribute, compliance, corpus, db, facts, metrics, render, slices  # noqa: E402

DEFAULT_ROOT = Path(__file__).resolve().parents[6]
DEFAULT_OUT = DEFAULT_ROOT / ".doc" / "task-analytics" / "out"


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def iso_to_ms(value):
    if not value:
        return None
    if value.isdigit():
        return int(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def detached_state_path(out_root):
    return Path(out_root) / "state" / "detached.json"


def load_detached(out_root):
    payload = render.load_index(detached_state_path(out_root)) or {}
    sessions = payload.get("sessions")
    return sessions if isinstance(sessions, dict) else {}


def role_of(facts_payload):
    skills = {event.get("skill_name") for event in facts_payload["events"] if event.get("skill_name")}
    if "prepare-plan" in skills:
        return "plan"
    if "test-task" in skills or "browser-verify" in skills or "prepare-task-test" in skills:
        return "test"
    if "send-to-git" in skills:
        return "git"
    if "task-doc" in skills:
        return "docs"
    return "implementation"


def write_plan_state(tasks_root, result):
    task = result.get("task")
    if not task:
        return
    status = None
    end_t = 0
    for slice_row in result.get("slices", []):
        if slice_row.get("markers"):
            status = slice_row["markers"][-1]
            end_t = slice_row.get("end_t", 0)
    if not status:
        return
    path = Path(tasks_root) / str(task) / "_dialogs" / "plan-state.json"
    existing = render.load_index(path) or {}
    if existing.get("status") == status and existing.get("session_id") == result["session_id"]:
        return
    if existing.get("updated_t", 0) > end_t:
        return
    render.write_json(path, {
        "task": str(task),
        "status": status,
        "outcome": result.get("slices", [{}])[-1].get("outcome"),
        "session_id": result["session_id"],
        "updated_t": end_t,
        "updated_at": datetime.fromtimestamp(end_t / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if end_t else None,
    })


def build_analysis(facts_payload, analysis, extra_findings, attribution, slice_rows, workflow, first_user_text=""):
    findings = analysis["findings"] + extra_findings
    result = {
        "schema_version": "1.0",
        "session_id": facts_payload["session_id"],
        "first_user_text": " ".join(facts.redact(first_user_text).split())[:160],
        "task": attribution["task"],
        "confidence": attribution["confidence"],
        "attribution": attribution["attribution"],
        "attribution_status": attribution["status"],
        "task_candidates": attribution["candidates"],
        "mentioned_tasks": attribution["mentioned_tasks"],
        "role": role_of(facts_payload),
        "model": facts_payload.get("model"),
        "started_at": facts_payload["started_at"],
        "last_event_at": facts_payload["last_event_at"],
        "final": facts_payload["final"],
        "db_lag_seconds": 0 if facts_payload["final"] else facts_payload["db_lag_seconds"],
        "phase_costs": {
            name: slot.get("cost", 0)
            for name, slot in analysis["token_ledger"]["by_phase"].items()
        },
        "tools": analysis["tools"],
        "findings": findings,
        "windows": analysis["windows"],
        "token_ledger": analysis["token_ledger"],
        "cli_tools": analysis["cli_tools"],
        "mcp_servers": analysis["mcp_servers"],
        "duration_ms": analysis["duration_ms"],
        "active_ms": analysis["active_ms"],
        "idle_trimmed_ms": analysis["idle_trimmed_ms"],
        "batchable_saved_calls": analysis["batchable_saved_calls"],
        "batchable_saved_ms": analysis["batchable_saved_ms"],
        "slices": slice_rows,
        "workflow": workflow,
        "context_overflows": analysis["context_overflows"],
        "files_touched": analysis["files_touched"],
        "totals": analysis["totals"],
        "warnings": facts_payload.get("warnings", []),
        "source": {"db": "kilo.db", "generated_by": "task-analytics/1.0"},
    }
    if attribution.get("detached_from"):
        result["detached_from"] = attribution["detached_from"]
    return result


def cmd_scan(args):
    root = Path(args.root).resolve()
    out_root = Path(args.out).resolve()
    tasks_root = Path(args.tasks_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    connection = db.connect(args.db)
    db.check_schema(connection)
    directories = db.project_directories(connection, root)
    sessions = db.select_sessions(
        connection, directories,
        session=args.session, latest=args.latest,
        after_ms=iso_to_ms(args.after), before_ms=iso_to_ms(args.before),
    )
    if not sessions:
        print("no sessions matched", file=sys.stderr)
        return 0

    thresholds_cfg = load_json(ROOT / "assets" / "config" / "thresholds.json", {})
    required_cfg = load_json(ROOT / "assets" / "config" / "required-calls.json", {})
    slices_cfg = load_json(ROOT / "assets" / "config" / "slices.json", {})
    anchors = attribute.load_anchors(tasks_root)
    detached = load_detached(out_root)

    collected = []
    written = []
    partial = False
    idle_seconds = int(args.idle_minutes * 60)

    for session in sessions:
        payload = facts.build_session(connection, session, idle_seconds=idle_seconds)
        analysis = metrics.analyze(payload, thresholds_cfg)
        missing = compliance.check(analysis["events"], required_cfg)
        quote = db.first_user_text(connection, session["id"])
        assignment = attribute.attribute(payload, anchors, quote)
        detached_entry = detached.get(session["id"])
        if isinstance(detached_entry, dict):
            previous_task = assignment.get("task") or ""
            assignment = dict(assignment)
            assignment["task"] = None
            assignment["status"] = "detached"
            assignment["confidence"] = 1.0
            assignment["attribution"] = [{"signal": "detached", "weight": 1.0}]
            assignment["detached_from"] = detached_entry.get("task") or previous_task
        slice_rows = slices.build_slices(analysis["events"], payload["messages"], slices_cfg, assignment["task"])
        workflow = corpus.fingerprint(payload, analysis)

        if args.task:
            if assignment["task"] != str(args.task) and str(args.task) not in assignment["mentioned_tasks"]:
                continue

        result = build_analysis(payload, analysis, missing, assignment, slice_rows, workflow, quote)
        partial = partial or not result["final"]
        collected.append({"facts": payload, "analysis": result, "workflow": workflow, "slices": slice_rows})

        if not args.dry_run:
            target = render.write_session(result, tasks_root, out_root)
            written.append(target)
            if result["task"]:
                index_path = Path(tasks_root) / result["task"] / "dialogs" / "index.json"
                render.update_index(index_path, result)
                write_plan_state(tasks_root, result)

    full_scan = not any((args.task, args.session, args.latest, args.after, args.before))
    if not args.dry_run and collected and full_scan:
        keep = {path.stem: path.resolve() for path in written}
        render.cleanup_orphans(tasks_root, out_root, keep)
        rules = corpus.aggregate(collected)
        render.write_json(out_root / "stats" / "antipatterns.json", {
            "schema_version": "antipatterns-1",
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "rules": rules,
        })
        cli = {}
        for item in collected:
            for row in item["analysis"].get("cli_tools", []):
                slot = cli.setdefault(row["name"], {
                    "name": row["name"], "calls": 0, "errors": 0,
                    "tokens": {"input": 0, "cache_read": 0, "cache_write": 0,
                               "output": 0, "reasoning": 0},
                })
                slot["calls"] += row["calls"]
                slot["errors"] += row["errors"]
                for key in slot["tokens"]:
                    slot["tokens"][key] += (row.get("tokens") or {}).get(key, 0)
        mcp = {}
        for item in collected:
            for row in item["analysis"].get("mcp_servers", []):
                slot = mcp.setdefault(row["server"], {
                    "server": row["server"], "calls": 0, "errors": 0,
                    "tokens": {"input": 0, "cache_read": 0, "cache_write": 0,
                               "output": 0, "reasoning": 0},
                })
                slot["calls"] += row["calls"]
                slot["errors"] += row["errors"]
                for key in slot["tokens"]:
                    slot["tokens"][key] += (row.get("tokens") or {}).get(key, 0)
        tools = {}
        for item in collected:
            for row in item["analysis"]["tools"]:
                slot = tools.setdefault(row["name"], {
                    "name": row["name"], "class": row["class"], "calls": 0,
                    "errors": 0, "timeouts": 0,
                })
                slot["calls"] += row["calls"]
                slot["errors"] += row["errors"]
                slot["timeouts"] += row["timeouts"]
        render.write_json(out_root / "stats" / "tools.json", {
            "schema_version": "1.0",
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": sorted(tools.values(), key=lambda item: -item["calls"]),
            "cli_tools": sorted(cli.values(), key=lambda item: -item["calls"]),
            "mcp_servers": sorted(mcp.values(), key=lambda item: -item["calls"]),
        })
        render.write_manifest(out_root / "state" / "manifest.json", args.db, len(collected), written)

    summary = {
        "status": "partial" if partial and not args.allow_partial else "ok",
        "sessions": len(collected),
        "written": len(written),
        "task": args.task,
        "partial_sessions": sum(1 for item in collected if not item["analysis"]["final"]),
        "ambiguous": sum(1 for item in collected if item["analysis"].get("attribution_status") == "ambiguous"),
        "antipatterns": len(corpus.aggregate(collected)) if (not args.dry_run and full_scan) else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if partial and not args.allow_partial:
        return 1
    return 0


def _iter_analysis(tasks_root, out_root, task=None):
    base = Path(tasks_root) / str(task) / "dialogs" if task else Path(tasks_root)
    if task:
        paths = sorted(base.glob("ses_*.json"))
    else:
        paths = sorted(base.glob("*/dialogs/ses_*.json"))
    for path in paths:
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    if not task:
        for path in sorted((Path(out_root) / "unassigned").glob("ses_*.json")):
            try:
                yield path, json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue


def cmd_report(args):
    items = list(_iter_analysis(args.tasks_root, args.out, args.task))
    if not items:
        print(json.dumps({"status": "empty", "sessions": 0}, ensure_ascii=False))
        return 0
    tokens = sum(
        item["token_ledger"]["input_total"] + item["token_ledger"]["output"] + item["token_ledger"]["reasoning"]
        for _, item in items
    )
    findings = {}
    for _, item in items:
        for finding in item["findings"]:
            findings[finding["code"]] = findings.get(finding["code"], 0) + 1
    if args.append_history and not args.task:
        history_items = [{"analysis": item, "slices": item.get("slices", [])} for _, item in items]
        line = corpus.history_line(history_items, args.stage, "task")
        appended = corpus.append_history(Path(args.out) / "stats" / "metrics-history.jsonl", line)
        print(json.dumps({"history": "appended" if appended else "duplicate"}, ensure_ascii=False))
    active = sum(item.get("active_ms", 0) for _, item in items)
    wall = sum(item.get("duration_ms", 0) for _, item in items)
    totals_in = sum(item["token_ledger"]["input_total"] for _, item in items)
    incoming = sum(item["token_ledger"].get("incoming_total", item["token_ledger"]["input_total"]) for _, item in items)
    totals_out = sum(item["token_ledger"]["output"] for _, item in items)
    totals_reasoning = sum(item["token_ledger"]["reasoning"] for _, item in items)
    cache_read = sum(item["token_ledger"].get("cache_read", 0) for _, item in items)
    cache_write = sum(item["token_ledger"].get("cache_write", 0) for _, item in items)
    saved_calls = sum(item.get("batchable_saved_calls", 0) for _, item in items)
    saved_ms = sum(item.get("batchable_saved_ms", 0) for _, item in items)
    requests = sum(item["token_ledger"].get("requests", 0) for _, item in items)
    payload = {
        "status": "ok",
        "task": args.task,
        "sessions": len(items),
        "tokens": tokens,
        "requests": requests,
        "tokens_in": totals_in,
        "incoming_total": incoming,
        "tokens_out": totals_out,
        "tokens_reasoning": totals_reasoning,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "active_minutes": round(active / 60000, 1),
        "wall_minutes": round(wall / 60000, 1),
        "batchable_saved_calls": saved_calls,
        "batchable_saved_ms": saved_ms,
        "cost": round(sum(item["token_ledger"]["cost"] for _, item in items), 6),
        "findings": dict(sorted(findings.items())),
        "unassigned": sum(1 for _, item in items if not item.get("task")),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_anchor(args):
    folder = Path(args.tasks_root) / str(args.task) / "_dialogs"
    path = folder / "anchor.json"
    payload = {
        "task": str(args.task),
        "branch": args.branch,
        "created_at": args.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quote": facts.redact(str(args.quote or ""))[:80],
    }
    existing = render.load_index(path)
    if existing == payload:
        print(json.dumps({"status": "duplicate", "path": str(path)}, ensure_ascii=False))
        return 0
    render.write_json(path, payload)
    print(json.dumps({"status": "created", "path": str(path)}, ensure_ascii=False))
    return 0


def cmd_backfill(args):
    connection = db.connect(args.db)
    db.check_schema(connection)
    created = []
    skipped = []
    branch_re = re.compile(r"(?:bugfixes|features)/[A-Za-z0-9._#\-/]*")
    for task_dir in sorted(Path(args.tasks_root).glob("*/dialogs")):
        task = task_dir.parent.name
        anchor_path = task_dir.parent / "_dialogs" / "anchor.json"
        if anchor_path.exists():
            skipped.append(task)
            continue
        index = render.load_index(task_dir / "index.json")
        if not index:
            continue
        candidates = []
        for entry in index.get("sessions", []):
            path = task_dir / entry.get("analysis", "")
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("task") == task and payload.get("confidence", 0) >= 0.9:
                candidates.append(payload)
        if not candidates:
            skipped.append(task)
            continue
        chosen = None
        quote = ""
        for candidate in sorted(candidates, key=lambda item: item["started_at"]):
            candidate_quote = facts.redact(db.first_user_text(connection, candidate["session_id"])).strip()[:80]
            if attribute.is_distinctive({"task": task, "quote": candidate_quote}):
                chosen = candidate
                quote = candidate_quote
                break
        if chosen is None:
            skipped.append(task)
            continue
        sessions = db.select_sessions(connection, db.project_directories(connection, args.root), session=chosen["session_id"])
        branch = ""
        if sessions:
            for event in facts.build_session(connection, sessions[0])["events"]:
                for match in branch_re.finditer(event.get("arg_text") or ""):
                    if task in match.group(0):
                        branch = match.group(0)
                        break
                if branch:
                    break
        payload = {
            "task": task,
            "branch": branch,
            "created_at": datetime.fromtimestamp(chosen["started_at"] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quote": quote,
        }
        render.write_json(anchor_path, payload)
        created.append(task)
    print(json.dumps({"status": "ok", "created": created, "skipped": skipped}, ensure_ascii=False))
    return 0


def cmd_assign(args):
    connection = db.connect(args.db)
    db.check_schema(connection)
    sessions = db.select_sessions(connection, db.project_directories(connection, args.root), session=args.session)
    if not sessions:
        print("session not found", file=sys.stderr)
        return 2
    session = sessions[0]
    quote = facts.redact(db.first_user_text(connection, session["id"])).strip()[:80]
    if not quote:
        print("session has no user text to match", file=sys.stderr)
        return 2
    path = Path(args.tasks_root) / str(args.task) / "_dialogs" / "anchor.json"
    existing = render.load_index(path)
    if existing and existing.get("task") != str(args.task) and not args.force:
        print(f"anchor already points to task {existing.get('task')}, use --force", file=sys.stderr)
        return 2
    payload = {
        "task": str(args.task),
        "branch": args.branch or (existing or {}).get("branch", ""),
        "created_at": datetime.fromtimestamp(session["time_created"] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quote": quote,
        "source": "manual-assign",
    }
    render.write_json(path, payload)
    print(json.dumps({"status": "created", "path": str(path), "task": str(args.task)}, ensure_ascii=False))
    return 0


def cmd_detach(args):
    out_root = Path(args.out).resolve()
    tasks_root = Path(args.tasks_root).resolve()
    path = detached_state_path(out_root)
    state = render.load_index(path) or {"schema_version": "1.0", "sessions": {}}
    sessions = state.get("sessions") if isinstance(state.get("sessions"), dict) else {}
    previous = sessions.get(args.session) if isinstance(sessions.get(args.session), dict) else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "task": str(args.task or previous.get("task") or ""),
        "reason": str(args.reason or previous.get("reason") or ""),
        "detached_at": now,
    }
    sessions[args.session] = entry
    state["schema_version"] = "1.0"
    state["sessions"] = sessions
    state["updated_at"] = now
    render.write_json(path, state)

    stem = render.session_stem(args.session)
    existing = None
    for candidate in Path(tasks_root).glob(f"*/dialogs/{stem}.json"):
        existing = candidate
        break
    if existing is None:
        unassigned = out_root / "unassigned" / f"{stem}.json"
        existing = unassigned if unassigned.exists() else None
    moved = None
    if existing is not None:
        try:
            analysis = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            analysis = None
        if analysis is not None:
            analysis["task"] = None
            analysis["attribution_status"] = "detached"
            analysis["attribution"] = [{"signal": "detached", "weight": 1.0}]
            analysis["detached_from"] = entry["task"]
            moved = str(render.write_session(analysis, tasks_root, out_root))
    print(json.dumps({
        "status": "detached",
        "session": args.session,
        "task": entry["task"],
        "state": str(path),
        "moved": moved,
    }, ensure_ascii=False))
    return 0


def cmd_validate(args):
    errors = []
    checked = 0
    for task in sorted(Path(args.tasks_root).glob("*/dialogs")):
        index_path = task / "index.json"
        index = render.load_index(index_path)
        if index is None:
            errors.append(f"{index_path}: missing or invalid")
            continue
        for entry in index.get("sessions", []):
            file_path = task / entry.get("analysis", "")
            if not file_path.exists():
                errors.append(f"{index_path}: broken link {entry.get('analysis')}")
                continue
            checked += 1
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except ValueError:
                errors.append(f"{file_path}: invalid json")
                continue
            if payload.get("schema_version") != "1.0":
                errors.append(f"{file_path}: unsupported schema_version")
            if payload.get("session_id") != entry.get("session_id"):
                errors.append(f"{file_path}: session_id mismatch")
    for path in (Path(args.out) / "unassigned").glob("ses_*.json"):
        checked += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            errors.append(f"{path}: invalid json")
    print(json.dumps({"status": "ok" if not errors else "error", "checked": checked, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(db.DEFAULT_DB))
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--tasks-root", default=str(Path(DEFAULT_ROOT) / ".doc" / "tasks"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="read the database and write analysis files")
    scan.add_argument("--task")
    scan.add_argument("--session")
    scan.add_argument("--latest", type=int)
    scan.add_argument("--after")
    scan.add_argument("--before")
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--allow-partial", action="store_true")
    scan.add_argument("--idle-minutes", type=float, default=15.0)
    scan.set_defaults(func=cmd_scan)

    report = sub.add_parser("report", help="print a task or global summary")
    report.add_argument("--task")
    report.add_argument("--append-history", action="store_true")
    report.add_argument("--stage", default="A")
    report.set_defaults(func=cmd_report)

    attribute = sub.add_parser("attribute", help="dry-run scan to inspect task attribution")
    attribute.add_argument("--task")
    attribute.add_argument("--session")
    attribute.add_argument("--latest", type=int)
    attribute.add_argument("--after")
    attribute.add_argument("--before")
    attribute.add_argument("--dry-run", action="store_true", default=True)
    attribute.add_argument("--allow-partial", action="store_true", default=True)
    attribute.add_argument("--idle-minutes", type=float, default=15.0)
    attribute.set_defaults(func=cmd_scan)

    anchor = sub.add_parser("anchor", help="write a task anchor for exact attribution")
    anchor.add_argument("--task", required=True)
    anchor.add_argument("--branch", required=True)
    anchor.add_argument("--quote", required=True)
    anchor.add_argument("--created-at")
    anchor.set_defaults(func=cmd_anchor)

    assign = sub.add_parser("assign", help="pin a session to a task manually")
    assign.add_argument("--session", required=True)
    assign.add_argument("--task", required=True)
    assign.add_argument("--branch", default="")
    assign.add_argument("--force", action="store_true")
    assign.set_defaults(func=cmd_assign)

    detach = sub.add_parser("detach", help="exclude a session from task attribution")
    detach.add_argument("--session", required=True)
    detach.add_argument("--task", default="")
    detach.add_argument("--reason", default="")
    detach.set_defaults(func=cmd_detach)

    backfill = sub.add_parser("backfill-anchors", help="create anchors for tasks with confident sessions")
    backfill.set_defaults(func=cmd_backfill)

    validate = sub.add_parser("validate", help="check written analysis files")
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (db.SchemaError, FileNotFoundError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
