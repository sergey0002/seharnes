"""Normalize session rows into deterministic facts.

Only the event shape is stored. Message text is never persisted: for text parts
we keep length and hash, for tool calls we keep a hash of the arguments and a
short, redacted target.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from . import db

SECRET_PATTERNS = (
    re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@"),
    re.compile(r"(?i)([?&](?:password|passwd|secret|token|access_token|refresh_token|api[_-]?key)=)[^&#\s]+"),
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)([\"']?\s*[:=]\s*)[^\n,;]+"),
    re.compile(r"(?i)(authorization\s+)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(cookie\s*[:=]\s*)[^\n]+"),
)

ALLOWED_TYPES = {"tool", "text", "patch", "file", "step-start", "step-finish", "compaction"}
EXPECTED_OUTPUT = {"bash", "read", "grep", "edit", "write", "glob", "apply_patch", "execute"}
PLAN_FILE = re.compile(r"plan\.md$")
PLAN_MARKER = re.compile(r"audit_status:\s*(passed|failed)")


def redact(text):
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "REDACTED", text)
    return text


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha1(canonical(value).encode("utf-8")).hexdigest()


def event_id(session_id, message_id, part_id):
    return hashlib.sha1(f"{session_id}|{message_id}|{part_id}".encode("utf-8")).hexdigest()[:12]


def short(value, limit=120):
    text = redact(str(value or ""))
    return text if len(text) <= limit else text[:limit] + "..."


CLI_SCRIPT = re.compile(r"((?:\./)?(?:[\w.@+-]+/)*[\w.@+-]+\.(?:py|sh|ps1|js|mjs|cjs|pl|rb))")
INTERPRETERS = {"php", "python", "python3", "node", "bash", "sh", "pwsh",
                "powershell", "perl", "ruby"}


def bash_cli(command):
    text = str(command or "")
    for segment in re.split(r"&&|\|\||;|\n", text):
        segment = segment.strip()
        if not segment:
            continue
        segment = re.sub(r"^(\w+=\S+\s+)+", "", segment)
        segment = re.sub(r"^(?:sudo|timeout\s+\d+|time)\s+", "", segment)
        if segment.startswith("cd "):
            continue
        words = segment.split()
        if not words:
            continue
        match = CLI_SCRIPT.search(segment)
        if match:
            path = match.group(1)
            if ".doc/" in path or ".cursor/" in path or path.startswith((".doc/", ".cursor/")):
                return path.rsplit("/", 1)[-1][:60]
            if words[0] in INTERPRETERS:
                return words[0]
            return path.rsplit("/", 1)[-1][:60]
        if words[0] in ("for", "if", "while", "case", "function", "do", "then"):
            return "shell"
        if words[0] in INTERPRETERS and len(words) > 1:
            return words[0]
        return words[0][:60]
    return "bash"


def target_of(tool, payload):
    if not isinstance(payload, dict):
        return ""
    for key in ("filePath", "path", "file_path"):
        if payload.get(key):
            return short(payload[key], 200)
    if tool == "glob":
        return short(payload.get("pattern"), 160)
    if tool == "grep":
        pattern = short(payload.get("pattern"), 80)
        return short(payload.get("path") or payload.get("include") or "", 120) + "::" + pattern
    if tool == "bash":
        command = str(payload.get("command") or "").strip().splitlines()
        return short(command[0] if command else "", 160)
    if tool == "edit":
        return short(payload.get("filePath") or payload.get("path"), 200)
    return ""


PLAN_TASK = re.compile(r"\.doc/tasks/(\d{2,4})/[^\s\"']*plan\.md")


def _plan_text_flags(text):
    if "plan.md" not in text:
        return False, None, False, None
    match = PLAN_TASK.search(text)
    touches = match is not None
    marker = None
    for found in PLAN_MARKER.finditer(text):
        marker = found.group(1)
    ready = marker == "passed" or bool(re.search(r"status:\s*ready", text))
    return touches, marker, ready, match.group(1) if match else None


def plan_flags(tool, payload, output):
    """Detect plan markers and the task they belong to, without storing text."""
    if not isinstance(payload, dict) or tool not in ("edit", "write", "apply_patch", "bash", "read", "grep", "open_plan"):
        return False, None, False, None
    texts = [canonical(payload)]
    if isinstance(output, str):
        texts.append(output)
    touches = marker = ready = plan_task = False
    for text in texts:
        if not text:
            continue
        hit, found, is_ready, task = _plan_text_flags(text)
        if not hit:
            continue
        touches = True
        marker = found or marker
        ready = ready or is_ready
        plan_task = task or plan_task
    return touches, marker, ready, plan_task


def build_events(parts):
    events = []
    skipped = {}
    for part in parts:
        payload = part["data"]
        kind = payload.get("type")
        if kind not in ALLOWED_TYPES:
            skipped[kind or "unknown"] = skipped.get(kind or "unknown", 0) + 1
            continue
        message_id = part["message_id"]
        base = {
            "event_id": event_id(part["session_id"], message_id, part["id"]),
            "part_id": part["id"],
            "message_id": message_id,
            "t": part["time_updated"] or part["time_created"],
            "kind": kind,
        }
        if kind == "text":
            text = str(payload.get("text") or "")
            base.update({"text_len": len(text), "text_sha": digest(text)})
        elif kind == "tool":
            state = payload.get("state") or {}
            tool = payload.get("tool") or "unknown"
            tool_input = state.get("input") or {}
            status = state.get("status") or "unknown"
            timing = state.get("time") or {}
            start, end = timing.get("start"), timing.get("end")
            output = state.get("output")
            nested = (state.get("metadata") or {}).get("toolCalls") or []
            error = None
            if status == "error":
                error = short(state.get("error") or output or "error", 200)
            touches_plan, marker, ready, plan_task = plan_flags(tool, tool_input, output)
            base.update({
                "tool": tool,
                "status": status,
                "arg_sha": digest(tool_input),
                "arg_text": short(
                    tool_input.get("command") or tool_input.get("code") or target_of(tool, tool_input),
                    240,
                ),
                "target": target_of(tool, tool_input),
                "duration_ms": (end - start) if start and end and end >= start else None,
                "output_len": len(output) if isinstance(output, str) else 0,
                "error": error,
                "plan_touch": touches_plan,
                "plan_marker": marker,
                "plan_ready": ready,
                "plan_task": plan_task,
                "skill_name": str(tool_input.get("name") or "") if tool == "skill" else "",
                "cli": bash_cli(tool_input.get("command")) if tool == "bash" else "",
                "nested": [
                    {
                        "tool": str(item.get("tool") or ""),
                        "status": str(item.get("status") or ""),
                    }
                    for item in nested
                ],
            })
        elif kind == "compaction":
            base.update({"compaction": True})
        events.append(base)
    events.sort(key=lambda item: (item["t"], item["event_id"]))
    return events, skipped


def build_messages(messages):
    result = []
    for message in messages:
        payload = message["data"] or {}
        if payload.get("role") != "assistant":
            continue
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            tokens = None
        cache = (tokens or {}).get("cache") or {}
        result.append({
            "message_id": message["id"],
            "t": message["time_created"],
            "model": payload.get("modelID"),
            "provider": payload.get("providerID"),
            "variant": payload.get("variant"),
            "cost": payload.get("cost") or 0,
            "tokens": None if tokens is None else {
                "input": int(tokens.get("input") or 0),
                "output": int(tokens.get("output") or 0),
                "reasoning": int(tokens.get("reasoning") or 0),
                "cache_read": int(cache.get("read") or 0),
                "cache_write": int(cache.get("write") or 0),
            },
        })
    return result


def parse_model(value):
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            payload = json.loads(value)
            return payload.get("id") or value
        except ValueError:
            return value
    return value


def build_session(connection, session, now_ms=None, idle_seconds=900):
    now_ms = now_ms or int(time.time() * 1000)
    parts = list(db.session_parts(connection, session["id"]))
    events, skipped = build_events(parts)
    messages = build_messages(db.session_messages(connection, session["id"]))
    last_part = max(db.max_part_time(connection, session["id"]), session["time_updated"])
    lag_seconds = max(0, int((now_ms - last_part) / 1000))
    final = lag_seconds >= idle_seconds
    warnings = []
    if any(message["tokens"] is None for message in messages):
        warnings.append("tokens_missing")
    if not session.get("cost"):
        warnings.append("cost_missing")
    return {
        "schema_version": "1.0",
        "session_id": session["id"],
        "project": session["directory"],
        "title": session["title"] or "",
        "parent_id": session.get("parent_id") or None,
        "model": parse_model(session.get("model")),
        "agent": session.get("agent"),
        "started_at": session["time_created"],
        "last_event_at": last_part,
        "final": final,
        "db_lag_seconds": lag_seconds,
        "session_totals": {
            "cost": session.get("cost") or 0,
            "tokens_input": session.get("tokens_input") or 0,
            "tokens_output": session.get("tokens_output") or 0,
            "tokens_reasoning": session.get("tokens_reasoning") or 0,
            "tokens_cache_read": session.get("tokens_cache_read") or 0,
            "tokens_cache_write": session.get("tokens_cache_write") or 0,
        },
        "events": events,
        "messages": messages,
        "skipped_types": skipped,
        "warnings": warnings,
    }
