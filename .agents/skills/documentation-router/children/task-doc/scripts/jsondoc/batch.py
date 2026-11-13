"""Batch execution: one envelope for N read calls + one apply (plan 6.5)."""

import json
from pathlib import Path

from . import search as search_mod

try:  # stages module lands at J06; batch stays importable before that
    from . import stages as stages_mod
except ImportError:  # pragma: no cover - J06 pending
    stages_mod = None

MAX_CALLS = 20
READ_COMMANDS = {"get", "search", "related", "stages", "tags_search"}


class BatchError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def _tags_search(docs, args):
    from . import tags_resolver
    text = args.get("text", "")
    fields = args.get("fields", ["label", "description", "aliases"])
    data = tags_resolver.load_dictionary(docs)
    norm = text.casefold()
    hits = []
    for tag in data["tags"]:
        searchable = {"id": tag["id"], "label": tag["label"],
                      "description": tag["description"],
                      "aliases": " ".join(tag["aliases"])}
        if not norm or any(norm in str(searchable.get(f, "")).casefold()
                           for f in fields):
            hits.append({f: searchable.get(f) for f in fields}
                        | {"id": tag["id"], "kind": tag["kind"],
                           "status": tag["status"]})
    return {"status": "ok", "data": hits[: args.get("limit", 10)],
            "counts": {"matched": len(hits)}}


def _stages_call(docs, args):
    if stages_mod is None:  # pragma: no cover - J06 pending
        return {"status": "error",
                "errors": [{"code": "stages_module_pending"}]}
    doc = search_mod.load_document(docs, "task", args.get("task"))
    if doc is None:
        return {"status": "not_found", "errors": [{"code": "NOT_FOUND"}]}
    return {"status": "ok", "data": stages_mod.stages_view(doc)}


def run_batch(docs, envelope, store=None):
    """Execute read calls on one snapshot then a single optional apply."""
    if not isinstance(envelope, dict):
        raise BatchError("invalid_envelope")
    calls = envelope.get("calls")
    if not isinstance(calls, list) or not calls:
        raise BatchError("calls_required")
    if len(calls) > MAX_CALLS:
        raise BatchError("too_many_calls", f"max {MAX_CALLS}")
    apply_spec = envelope.get("apply")
    if apply_spec is not None and not isinstance(apply_spec, dict):
        raise BatchError("invalid_apply")

    snapshot_revision = None
    results = []
    for call in calls:
        call_id = call.get("id") or f"call-{len(results)}"
        command = call.get("command")
        args = call.get("args", {}) or {}
        if command not in READ_COMMANDS:
            raise BatchError("unknown_command", str(command))
        try:
            if command == "get":
                kind = "task" if args.get("task") else "architecture"
                key = args.get("task") or args.get("arch")
                outcome = search_mod.get(docs, kind, key,
                                         pointers=args.get("select"),
                                         record_limit=args.get("limit"),
                                         keys_only=args.get("keys"))
            elif command == "search":
                outcome = search_mod.search(
                    docs, kind=args.get("kind"), text=args.get("text"),
                    tags=args.get("tag", []), tag_mode=args.get("tag_mode", "all"),
                    file=args.get("file"), release=args.get("release"),
                    branch=args.get("branch"),
                    tasks=args.get("tasks", "").split(",") if args.get("tasks") else (),
                    limit=args.get("limit"))
            elif command == "related":
                outcome = search_mod.related(docs, args.get("profile",
                                                            "discovery-v1"),
                                             task=args.get("task"),
                                             arch=args.get("arch"),
                                             limit=args.get("limit"))
            elif command == "stages":
                outcome = _stages_call(docs, args)
            else:
                outcome = _tags_search(docs, args)
        except Exception as exc:  # per-item isolation
            outcome = {"status": "error",
                       "errors": [{"code": getattr(exc, "code", "call_failed"),
                                   "message": str(exc)}]}
        if snapshot_revision is None and isinstance(outcome, dict):
            snapshot_revision = outcome.get("snapshot_revision")
        results.append({"id": call_id,
                        "status": outcome.get("status", "error"),
                        "data": outcome.get("data"),
                        "counts": outcome.get("counts"),
                        "errors": outcome.get("errors")})

    apply_summary = None
    if apply_spec is not None:
        if store is None:
            raise BatchError("store_required_for_apply")
        kind = "task" if apply_spec.get("task") else "architecture"
        key = apply_spec.get("task") or apply_spec.get("arch")
        envelope = {k: v for k, v in apply_spec.items()
                    if k not in ("task", "arch", "batch_id")}
        try:
            apply_summary = store.apply(kind, key, envelope)
        except Exception as exc:  # isolate apply failures from read results
            code = getattr(exc, "code", "apply_failed")
            if code == "VALIDATION":
                code = "CONFLICT" if "revision" in str(getattr(exc, "payload",
                                                               "")) else code
            apply_summary = {"status": "conflict" if code in
                             ("CONFLICT", "VALIDATION") else "error",
                             "code": code, "message": str(exc)}

    return {"status": "ok", "batch_id": envelope.get("batch_id"),
            "snapshot_revision": snapshot_revision,
            "results": results, "apply_summary": apply_summary,
            "counts": {"calls": len(results)}, "exit": 0}
