"""Structural merge for the two CLI-managed configuration files.

MCP keeps target servers, URLs, ports and credentials, adds upstream-only
servers disabled and keeps a conflicting upstream server under a suffixed
disabled key. AGENTS.md replaces only the marked managed block.
"""
from __future__ import annotations

import json
import re

AGENTS_BEGIN = re.compile(r"<!--\s*BEGIN HARNESS BOOTSTRAP.*?-->", re.DOTALL)
AGENTS_END = re.compile(r"<!--\s*END HARNESS BOOTSTRAP\s*-->", re.DOTALL)


class MergeError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MergeError("duplicate JSON key")
        result[key] = value
    return result


def _load(data: bytes) -> dict:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise MergeError("invalid MCP JSON") from error
    if not isinstance(value, dict):
        raise MergeError("MCP JSON must be an object")
    servers = value.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise MergeError("mcpServers must be an object")
    return value


def _dump(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _disabled(server: dict) -> dict:
    copy = json.loads(json.dumps(server, ensure_ascii=False))
    copy["disabled"] = True
    return copy


def merge_mcp(target: bytes | None, incoming: bytes) -> tuple[bytes, dict]:
    source = _load(incoming)
    if target is None:
        return incoming, {"mode": "install", "kept": [], "added_disabled": [],
                          "conflicts": [], "disabled_conflicts": []}
    current = _load(target)
    before = current.setdefault("mcpServers", {})
    incoming_servers = source.get("mcpServers", {})
    kept, added, conflicts, disabled = [], [], [], []
    for name, server in incoming_servers.items():
        if name not in before:
            before[name] = _disabled(server)
            added.append(name)
        elif before[name] == server:
            kept.append(name)
        else:
            conflicts.append(name)
            alternative = name + "__upstream"
            if alternative not in before:
                before[alternative] = _disabled(server)
                disabled.append(alternative)
    for key, value in source.items():
        if key not in current:
            current[key] = value
    return _dump(current), {"mode": "merge", "kept": sorted(kept), "added_disabled": sorted(added),
                            "conflicts": sorted(conflicts), "disabled_conflicts": sorted(disabled)}


def merge_agents(target: bytes | None, incoming: bytes) -> tuple[bytes, dict]:
    try:
        source = incoming.decode("utf-8")
    except UnicodeError as error:
        raise MergeError("AGENTS.md is not valid UTF-8") from error
    begins = list(AGENTS_BEGIN.finditer(source))
    ends = list(AGENTS_END.finditer(source))
    if len(begins) != 1 or len(ends) != 1 or begins[0].start() >= ends[0].start():
        raise MergeError("AGENTS.md needs exactly one managed block")
    block = source[begins[0].start():ends[0].end()]
    if target is None:
        return incoming, {"mode": "install", "block": "copied"}
    try:
        text = target.decode("utf-8")
    except UnicodeError as error:
        raise MergeError("target AGENTS.md is not valid UTF-8") from error
    target_begins = list(AGENTS_BEGIN.finditer(text))
    target_ends = list(AGENTS_END.finditer(text))
    if target_begins or target_ends:
        if len(target_begins) != 1 or len(target_ends) != 1 or target_begins[0].start() >= target_ends[0].start():
            raise MergeError("target AGENTS.md has an incomplete managed block")
        replaced = text[:target_begins[0].start()] + block + text[target_ends[0].end():]
        return replaced.encode("utf-8"), {"mode": "replace_block", "block": "replaced"}
    appended = text.rstrip("\n") + "\n\n" + block + "\n"
    return appended.encode("utf-8"), {"mode": "append_block", "block": "appended"}
