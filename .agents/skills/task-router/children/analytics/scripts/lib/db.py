"""Read-only access to the Kilo session database.

The database belongs to the Kilo client and is not a public contract. Every
entry point checks the required tables and columns and fails with exit code 2
instead of silently reading empty data.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".local" / "share" / "kilo" / "kilo.db"

REQUIRED_COLUMNS = {
    "session": (
        "id",
        "directory",
        "parent_id",
        "title",
        "cost",
        "tokens_input",
        "tokens_output",
        "tokens_reasoning",
        "tokens_cache_read",
        "tokens_cache_write",
        "model",
        "agent",
        "time_created",
        "time_updated",
    ),
    "message": ("id", "session_id", "time_created", "data"),
    "part": ("id", "message_id", "session_id", "time_created", "time_updated", "data"),
}


class SchemaError(RuntimeError):
    pass


def connect(path=None):
    db_path = Path(path).expanduser() if path else DEFAULT_DB
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def check_schema(connection):
    missing = []
    for table, columns in REQUIRED_COLUMNS.items():
        present = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if not present:
            missing.append(table)
            continue
        missing.extend(f"{table}.{name}" for name in columns if name not in present)
    if missing:
        raise SchemaError("database schema changed, missing: " + ", ".join(missing))


def project_directories(connection, root):
    """Return directories that belong to this repository, including worktrees."""
    resolved = str(Path(root).resolve())
    directories = {resolved}
    for row in connection.execute("SELECT directory FROM project_directory"):
        directory = row["directory"]
        if not directory:
            continue
        if directory == resolved or directory.startswith(resolved + "/"):
            directories.add(directory)
    return sorted(directories)


def select_sessions(connection, directories, session=None, latest=None,
                    after_ms=None, before_ms=None):
    placeholders = ",".join("?" for _ in directories)
    sql = (
        "SELECT * FROM session WHERE directory IN (" + placeholders + ")"
    )
    params = list(directories)
    if session:
        sql += " AND id = ?"
        params.append(session)
    if after_ms is not None:
        sql += " AND time_updated >= ?"
        params.append(int(after_ms))
    if before_ms is not None:
        sql += " AND time_updated <= ?"
        params.append(int(before_ms))
    sql += " ORDER BY time_updated DESC"
    if latest:
        sql += " LIMIT ?"
        params.append(int(latest))
    return [dict(row) for row in connection.execute(sql, params)]


def session_parts(connection, session_id):
    sql = (
        "SELECT id, message_id, session_id, time_created, time_updated, data "
        "FROM part WHERE session_id = ? ORDER BY time_created, COALESCE(time_updated, time_created)"
    )
    for row in connection.execute(sql, (session_id,)):
        try:
            payload = json.loads(row["data"])
        except (TypeError, ValueError):
            continue
        yield {
            "id": row["id"],
            "message_id": row["message_id"],
            "session_id": row["session_id"],
            "time_created": row["time_created"],
            "time_updated": row["time_updated"],
            "data": payload,
        }


def session_messages(connection, session_id):
    sql = (
        "SELECT id, session_id, time_created, data FROM message "
        "WHERE session_id = ? ORDER BY time_created, id"
    )
    for row in connection.execute(sql, (session_id,)):
        try:
            payload = json.loads(row["data"])
        except (TypeError, ValueError):
            continue
        yield {
            "id": row["id"],
            "session_id": row["session_id"],
            "time_created": row["time_created"],
            "data": payload,
        }


def max_part_time(connection, session_id):
    row = connection.execute(
        "SELECT MAX(COALESCE(time_updated, time_created)) AS ts FROM part WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row["ts"] or 0


def first_user_text(connection, session_id):
    """First user message text, used only for anchor quote matching."""
    sql = (
        "SELECT p.data FROM part p JOIN message m ON m.id = p.message_id "
        "WHERE p.session_id = ? AND json_extract(m.data, '$.role') = 'user' "
        "AND json_extract(p.data, '$.type') = 'text' "
        "ORDER BY m.time_created, p.time_created LIMIT 1"
    )
    row = connection.execute(sql, (session_id,)).fetchone()
    if not row:
        return ""
    try:
        return str(json.loads(row["data"]).get("text") or "")
    except (TypeError, ValueError):
        return ""
