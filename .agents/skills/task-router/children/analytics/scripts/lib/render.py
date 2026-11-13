"""Atomic writes, per-task indexes and the run manifest."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def session_stem(session_id):
    return session_id if session_id.startswith("ses_") else f"ses_{session_id}"


def write_session(analysis, tasks_root, out_root):
    session_id = session_stem(analysis["session_id"])
    if analysis.get("task"):
        folder = Path(tasks_root) / str(analysis["task"]) / "dialogs"
    else:
        folder = Path(out_root) / "unassigned"
    target = folder / f"{session_id}.json"
    write_json(target, analysis)
    remove_session_copies(session_id, target, tasks_root, out_root)
    return target


def remove_session_copies(session_id, keep_path, tasks_root, out_root):
    """Remove stale copies of one session after attribution or detach changed."""
    stem = session_stem(session_id)
    keep = Path(keep_path).resolve()
    removed = []
    for path in Path(tasks_root).glob(f"*/dialogs/{stem}.json"):
        if path.resolve() == keep:
            continue
        path.unlink(missing_ok=True)
        removed.append(str(path))
        index_path = path.parent / "index.json"
        index = load_index(index_path)
        if index is not None:
            sessions = index.get("sessions") if isinstance(index.get("sessions"), list) else []
            kept = [item for item in sessions if item.get("session_id") != stem]
            if len(kept) != len(sessions):
                index["sessions"] = kept
                write_json(index_path, index)
    unassigned = Path(out_root) / "unassigned" / f"{stem}.json"
    if unassigned.exists() and unassigned.resolve() != keep:
        unassigned.unlink()
        removed.append(str(unassigned))
    return removed


def load_index(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def update_index(path, analysis, audits=None):
    path = Path(path)
    index = load_index(path) or {
        "schema_version": "1.0",
        "task": str(analysis.get("task") or ""),
        "sessions": [],
        "updated_at": None,
    }
    entry = {
        "session_id": analysis["session_id"],
        "date": datetime.fromtimestamp(analysis["started_at"] / 1000, timezone.utc).strftime("%Y-%m-%d"),
        "role": analysis.get("role") or "task",
        "model": analysis.get("model"),
        "cost": analysis["token_ledger"]["cost"],
        "tokens": (
            analysis["token_ledger"]["input_total"]
            + analysis["token_ledger"]["output"]
            + analysis["token_ledger"]["reasoning"]
        ),
        "tokens_in": analysis["token_ledger"]["input_total"],
        "tokens_out": analysis["token_ledger"]["output"],
        "tokens_reasoning": analysis["token_ledger"]["reasoning"],
        "requests": analysis["token_ledger"].get("requests", 0),
        "cache_read": analysis["token_ledger"]["cache_read"],
        "cache_write": analysis["token_ledger"]["cache_write"],
        "cache_hit_ratio": analysis["token_ledger"].get("cache_hit_ratio", 0.0),
        "active_ms": analysis.get("active_ms", 0),
        "duration_ms": analysis.get("duration_ms", 0),
        "final": analysis.get("final", False),
        "analysis": f"{session_stem(analysis['session_id'])}.json",
        "audits": audits or [],
    }
    sessions = [item for item in index["sessions"] if item["session_id"] != entry["session_id"]]
    sessions.append(entry)
    sessions.sort(key=lambda item: (item["date"], item["session_id"]), reverse=True)
    index["sessions"] = sessions
    index["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json(path, index)
    return index


def cleanup_orphans(tasks_root, out_root, keep_ids):
    """Remove analysis files for sessions that moved to another task or bucket."""
    removed = []
    keep = {name: Path(target).resolve() for name, target in keep_ids.items()}
    for path in Path(tasks_root).glob("*/dialogs/ses_*.json"):
        if keep.get(path.stem) == path.resolve():
            continue
        path.unlink(missing_ok=True)
        removed.append(str(path))
        index_path = path.parent / "index.json"
        index = load_index(index_path)
        if index:
            index["sessions"] = [item for item in index["sessions"] if item.get("session_id") != path.stem]
            write_json(index_path, index)
    for path in (Path(out_root) / "unassigned").glob("ses_*.json"):
        if keep.get(path.stem) == path.resolve():
            continue
        path.unlink(missing_ok=True)
        removed.append(str(path))
    return removed


def write_manifest(path, db_path, sessions, files):
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db": str(db_path),
        "db_mtime_ns": Path(db_path).stat().st_mtime_ns if Path(db_path).exists() else None,
        "sessions": sessions,
        "files": {str(name): sha256_file(name) for name in files},
    }
    write_json(path, payload)
    return payload
