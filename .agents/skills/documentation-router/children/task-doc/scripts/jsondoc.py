#!/usr/bin/env python3
"""JSONdoc CLI: single entry point for task/architecture knowledge JSON.

Commands are added stage by stage (see .doc/jsondoc.md section 16).
stdout is exactly one JSON envelope per invocation; diagnostics go to stderr.
Exit codes: 0 ok (incl. empty search), 1 target not found,
2 validation/CLI failure, 3 concurrency conflict, 4 recovery required.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jsondoc import verify  # noqa: E402

VERSION = "0.1.0-J00"


def build_parser():
    parser = argparse.ArgumentParser(prog="jsondoc.py", description=__doc__)
    parser.add_argument("--root", required=True, help="project containment root")
    parser.add_argument("--docs-dir", default=".doc", help="documentation directory")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("selftest", help="run test suites for a stage")
    p.add_argument("--stage", help="stage id like J04")
    p.add_argument("--through", help="run suites J00..through")
    p.add_argument("--suite", help="named suite instead of stage")
    p.add_argument("--run", required=True, help="run id, results under runs/{RUN}")

    p = sub.add_parser("execution", help="execution state machine")
    e = p.add_subparsers(dest="execution_command", required=True)
    e.add_parser("next")
    v = e.add_parser("verify-stage")
    v.add_argument("--stage", required=True)

    p = sub.add_parser("baseline", help="capture baseline hashes of harness files")
    p.add_argument("--run", required=True)

    p = sub.add_parser("get", help="read document card or selected pointers")
    p.add_argument("--task")
    p.add_argument("--arch")
    p.add_argument("--keys", action="store_true")
    p.add_argument("--select", action="append", dest="pointers")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--record-id")

    p = sub.add_parser("search", help="search tasks/architecture documents")
    p.add_argument("--kind", choices=["task", "architecture"])
    p.add_argument("--text")
    p.add_argument("--tag", action="append", dest="tags", default=[])
    p.add_argument("--tag-mode", choices=["all", "any"], default="all")
    p.add_argument("--file")
    p.add_argument("--release")
    p.add_argument("--branch")
    p.add_argument("--tasks")
    p.add_argument("--limit", type=int, default=None)

    p = sub.add_parser("related", help="related tasks profile query")
    p.add_argument("--profile", default="discovery-v1",
                   choices=["discovery-v1", "legacy-v1"])
    p.add_argument("--task")
    p.add_argument("--arch")
    p.add_argument("--limit", type=int, default=None)

    p = sub.add_parser("apply", help="apply one update envelope to a document")
    p.add_argument("--task")
    p.add_argument("--arch")
    p.add_argument("--input", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("render", help="regenerate MD view from document JSON")
    p.add_argument("--task")
    p.add_argument("--arch")

    p = sub.add_parser("validate", help="read-only schema and link validation")
    p.add_argument("--task")
    p.add_argument("--arch")
    p.add_argument("--all", action="store_true")
    p.add_argument("--links", action="store_true")

    p = sub.add_parser("batch", help="run N read calls plus one apply")
    p.add_argument("--input", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("ingest-tracker", help="apply Jira snapshot via store")
    p.add_argument("--task", required=True)
    p.add_argument("--input", required=True)

    p = sub.add_parser("ingest-git", help="local git containment snapshot")
    p.add_argument("--task", required=True)

    p = sub.add_parser("recover", help="finish hash-consistent transaction")
    p.add_argument("--task")
    p.add_argument("--arch")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print('{"status":"error","errors":[{"code":"invalid_root"}],"exit":2}')
        return 2
    docs = root / args.docs_dir
    try:
        if args.command == "selftest":
            result = verify.run_selftest(root, docs, stage=args.stage,
                                         through=args.through, suite=args.suite,
                                         run_id=args.run)
        elif args.command == "baseline":
            result = verify.capture_baseline(root, docs, run_id=args.run)
        elif args.command == "execution":
            if args.execution_command == "next":
                result = verify.execution_next(root, docs)
            else:
                result = verify.execution_verify_stage(root, docs, args.stage)
        elif args.command == "get":
            from jsondoc import search as search_mod
            if bool(args.task) == bool(args.arch):
                result = {"status": "error",
                          "errors": [{"code": "exactly_one_target_required"}],
                          "exit": 2}
            else:
                kind, key = ("task", args.task) if args.task else ("architecture", args.arch)
                try:
                    result = search_mod.get(docs, kind, key,
                                           pointers=args.pointers,
                                           record_limit=args.limit,
                                           keys_only=args.keys)
                except search_mod.QueryError as exc:
                    result = {"status": "error",
                              "errors": [{"code": exc.code, "message": str(exc)}],
                              "exit": 2}
        elif args.command == "search":
            from jsondoc import search as search_mod
            try:
                tasks = args.tasks.split(",") if args.tasks else ()
                result = search_mod.search(docs, kind=args.kind, text=args.text,
                                           tags=args.tags, tag_mode=args.tag_mode,
                                           file=args.file, release=args.release,
                                           branch=args.branch, tasks=tasks,
                                           limit=args.limit)
                result["next_action"] = "inspect matched documents"
            except Exception as exc:  # QueryError/TagError
                result = {"status": "error",
                          "errors": [{"code": getattr(exc, "code", "query_error"),
                                      "message": str(exc)}],
                          "exit": 2}
        elif args.command == "related":
            from jsondoc import search as search_mod
            try:
                result = search_mod.related(docs, args.profile,
                                            task=args.task, arch=args.arch,
                                            limit=args.limit)
            except Exception as exc:
                result = {"status": "error",
                          "errors": [{"code": getattr(exc, "code", "related_error"),
                                      "message": str(exc)}],
                          "exit": 2}
        elif args.command == "apply":
            from jsondoc.store import Store, StoreError
            if bool(args.task) == bool(args.arch):
                result = {"status": "error",
                          "errors": [{"code": "exactly_one_target_required"}],
                          "exit": 2}
            else:
                try:
                    envelope = json.loads(
                        Path(args.input).read_text(encoding="utf-8"))
                    kind = "task" if args.task else "arch"
                    key = args.task or args.arch
                    store = Store(root, docs)
                    result = store.apply(kind, key, envelope,
                                         dry_run=args.dry_run)
                    result.setdefault("status", "ok")
                    result["exit"] = 0 if result.get("status") in (
                        "applied", "noop", "duplicate") else 3
                except StoreError as exc:
                    result = {"status": "conflict"
                              if exc.code in ("CONFLICT", "VIEW_CONFLICT",
                                              "VALIDATION") else "error",
                              "errors": [{"code": exc.code,
                                          "message": str(exc),
                                          "payload": exc.payload}],
                              "exit": 3 if exc.code in ("CONFLICT",
                                                       "VIEW_CONFLICT",
                                                       "VALIDATION") else 2}
                except (OSError, json.JSONDecodeError) as exc:
                    result = {"status": "error",
                              "errors": [{"code": "input_unreadable",
                                          "message": str(exc)}], "exit": 2}
        elif args.command == "validate":
            from jsondoc.validate import validate_all, validate_target
            if args.all:
                if args.task or args.arch:
                    result = {"status": "error", "errors": [
                        {"code": "all_with_target"}], "exit": 2}
                else:
                    result = validate_all(root, docs, links=args.links)
            elif bool(args.task) == bool(args.arch):
                result = {"status": "error",
                          "errors": [{"code": "exactly_one_target_required"}],
                          "exit": 2}
            else:
                kind = "task" if args.task else "arch"
                key = args.task or args.arch
                result = validate_target(root, docs, kind, key,
                                         links=args.links)
        elif args.command == "render":
            from jsondoc.render import render_document, RenderError
            from jsondoc.store import Store
            if bool(args.task) == bool(args.arch):
                result = {"status": "error",
                          "errors": [{"code": "exactly_one_target_required"}],
                          "exit": 2}
            else:
                kind = "task" if args.task else "arch"
                render_kind = "task" if args.task else "architecture"
                key = args.task or args.arch
                store = Store(root, docs)
                doc = store.load(kind, key)
                if doc is None:
                    result = {"status": "not_found", "errors": [{"code":
                              "NOT_FOUND"}], "exit": 1}
                else:
                    try:
                        outcome = render_document(root, docs, render_kind, key, doc)
                        result = {"status": outcome.get("status", "ok"),
                                  "view_sha256": outcome.get("view_sha256"),
                                  "exit": 0}
                    except RenderError as exc:
                        result = {"status": "conflict",
                                  "errors": [{"code": exc.code,
                                              "message": str(exc)}],
                                  "exit": 3}
        elif args.command == "batch":
            from jsondoc.batch import run_batch, BatchError
            from jsondoc.store import Store
            try:
                envelope = json.loads(
                    Path(args.input).read_text(encoding="utf-8"))
                result = run_batch(docs, envelope,
                                   store=Store(root, docs)
                                   if envelope.get("apply") else None)
            except BatchError as exc:
                result = {"status": "error",
                          "errors": [{"code": exc.code, "message": str(exc)}],
                          "exit": 2}
            except (OSError, json.JSONDecodeError) as exc:
                result = {"status": "error",
                          "errors": [{"code": "input_unreadable",
                                      "message": str(exc)}], "exit": 2}
        elif args.command == "ingest-tracker":
            from jsondoc.ingest import ingest_tracker
            from jsondoc.store import Store
            try:
                payload = json.loads(
                    Path(args.input).read_text(encoding="utf-8"))
                result = ingest_tracker(Store(root, docs), args.task, payload)
                result.setdefault("status", "ok")
                result["exit"] = 0 if result.get("status") in (
                    "applied", "noop") else 2
            except (OSError, json.JSONDecodeError) as exc:
                result = {"status": "error",
                          "errors": [{"code": "input_unreadable",
                                      "message": str(exc)}], "exit": 2}
        elif args.command == "ingest-git":
            from jsondoc.ingest import ingest_git
            from jsondoc.store import Store
            result = ingest_git(Store(root, docs), args.task, root,
                                ["release/*"])
            result.setdefault("status", "ok")
            result["exit"] = {"applied": 0, "noop": 0}.get(
                result.get("status"),
                1 if result.get("status") == "not_found" else 2)
        elif args.command == "recover":
            from jsondoc.store import Store, StoreError
            if bool(args.task) == bool(args.arch):
                result = {"status": "error",
                          "errors": [{"code": "exactly_one_target_required"}],
                          "exit": 2}
            else:
                kind = "task" if args.task else "arch"
                key = args.task or args.arch
                try:
                    result = Store(root, docs).recover(kind, key)
                    result.setdefault("status", "ok")
                    result["exit"] = 0
                except StoreError as exc:
                    result = {"status": "error",
                              "errors": [{"code": exc.code,
                                          "message": str(exc)}],
                              "exit": 4 if exc.code == "RECOVERY_REQUIRED" else 2}
        else:  # pragma: no cover - argparse guards
            result = {"status": "error", "errors": [{"code": "unknown_command"}]}
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        result = {"status": "error", "errors": [{"code": "internal", "message": str(exc)}]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    code = result.get("exit", 2 if result.get("status") == "error" else 0)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
