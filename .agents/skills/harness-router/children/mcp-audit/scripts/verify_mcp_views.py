#!/usr/bin/env python3
"""Verify MCP server sets across agent views.

Deterministic checks, cheap enough to run on every sync:

1. Every view declares exactly the canonical server set (no drift, no orphans).
2. Enabled/disabled state matches the canon.
3. Expanded views (Antigravity, Gemini, agents) contain no unresolved
   ${workspaceFolder} or ${env:...} tokens.
4. Kilo expands ${workspaceFolder} and keeps ${env:...} out of parsed values
   (secrets stay in mcp.env, loaded by the runtime wrapper).
5. Optional Codex TOML declares the same server set.

Command semantics are intentionally not compared: adapters legitimately differ
by wrapper, absolute path or native schema. Only names, state and expansion are
invariants.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

TOKEN_RE = re.compile(r"\$\{(env:[A-Za-z0-9_]+|workspaceFolder)\}")


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside string literals."""
    out: list[str] = []
    index, length = 0, len(text)
    in_string, escaped = False, False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path}: unreadable: {error}")
        return None


def canon_servers(path: Path, errors: list[str]) -> dict:
    data = load_json(path, errors)
    if data is None:
        return {}
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        errors.append(f"{path}: no mcpServers object")
        return {}
    return servers


def compare_names(canon: dict, view: dict, label: str, errors: list[str]) -> None:
    for name in sorted(set(canon) - set(view)):
        errors.append(f"{label}: server missing {name}")
    for name in sorted(set(view) - set(canon)):
        errors.append(f"{label}: server extra {name}")


def compare_state(canon: dict, view: dict, label: str, errors: list[str], native_enabled: bool) -> None:
    """Compare enabled/disabled; Kilo uses `enabled`, other views use `disabled`."""
    for name in sorted(set(canon) & set(view)):
        canon_enabled = not (canon[name].get("enabled", True) is False or canon[name].get("disabled", False))
        if native_enabled:
            view_enabled = bool(view[name].get("enabled", True))
        else:
            view_enabled = not (view[name].get("enabled", True) is False or view[name].get("disabled", False))
        if canon_enabled != view_enabled:
            errors.append(
                f"{label}: server {name} enabled={view_enabled}, canon enabled={canon_enabled}"
            )


def scan_placeholders(value, label: str, errors: list[str]) -> None:
    """Fail on tokens the target client cannot expand."""
    for match in TOKEN_RE.finditer(json.dumps(value, ensure_ascii=False, sort_keys=True)):
        errors.append(f"{label}: unresolved placeholder ${{{match.group(1)}}}")


def check_kilo(canon: dict, path: Path, errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        errors.append(f"{path}: unreadable: {error}")
        return
    try:
        data = json.loads(strip_jsonc(text))
    except json.JSONDecodeError as error:
        errors.append(f"{path}: invalid JSON after comment strip: {error}")
        return
    servers = data.get("mcp")
    if not isinstance(servers, dict):
        errors.append(f"{path}: no mcp object")
        return
    compare_names(canon, servers, str(path), errors)
    compare_state(canon, servers, str(path), errors, native_enabled=True)
    scan_placeholders(servers, str(path), errors)


def check_expanded(canon: dict, path: Path, errors: list[str]) -> None:
    data = load_json(path, errors)
    if data is None:
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        errors.append(f"{path}: no mcpServers object")
        return
    compare_names(canon, servers, str(path), errors)
    compare_state(canon, servers, str(path), errors, native_enabled=False)
    scan_placeholders(servers, str(path), errors)


def check_qwen(canon: dict, path: Path, errors: list[str]) -> None:
    """Qwen keeps enabled servers in `mcpServers` and disabled ones in `mcp.excluded`."""
    data = load_json(path, errors)
    if data is None:
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        errors.append(f"{path}: no mcpServers object")
        return
    enabled_canon = {
        name: value for name, value in canon.items()
        if not (value.get("enabled", True) is False or value.get("disabled", False))
    }
    disabled_canon = sorted(set(canon) - set(enabled_canon))
    compare_names(enabled_canon, servers, str(path), errors)
    excluded = set((data.get("mcp") or {}).get("excluded", []))
    for name in sorted(set(enabled_canon) & excluded):
        errors.append(f"{path}: enabled server {name} is in mcp.excluded")
    for name in disabled_canon:
        if name not in excluded:
            errors.append(f"{path}: disabled server {name} missing from mcp.excluded")
    scan_placeholders(servers, str(path), errors)


def check_codex_toml(canon: dict, path: Path, errors: list[str]) -> None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        errors.append(f"{path}: unreadable or invalid TOML")
        return
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict) or not all(isinstance(value, dict) for value in servers.values()):
        errors.append(f"{path}: no valid mcp_servers object")
        return
    compare_names(canon, servers, str(path), errors)
    compare_state(canon, servers, str(path), errors, native_enabled=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--canonical", required=True, type=Path, help=".cursor/mcp.json")
    parser.add_argument("--kilo", type=Path, help=".kilo/kilo.jsonc")
    parser.add_argument("--expanded", action="append", default=[], type=Path, help="view with expanded paths (repeatable)")
    parser.add_argument("--qwen", type=Path, help=".qwen/settings.json")
    parser.add_argument("--codex-toml", type=Path, help=".codex/config.toml")
    args = parser.parse_args()

    errors: list[str] = []
    canon = canon_servers(args.canonical, errors)
    checks: list[str] = []

    if args.kilo is not None:
        checks.append(str(args.kilo))
        check_kilo(canon, args.kilo, errors)
    for path in args.expanded:
        checks.append(str(path))
        check_expanded(canon, path, errors)
    if args.qwen is not None:
        checks.append(str(args.qwen))
        check_qwen(canon, args.qwen, errors)
    if args.codex_toml is not None:
        checks.append(str(args.codex_toml))
        check_codex_toml(canon, args.codex_toml, errors)

    if not checks:
        parser.error("nothing to check: pass --kilo, --expanded or --codex-toml")

    report = {
        "canonical": str(args.canonical),
        "servers": len(canon),
        "checked": checks,
        "errors": errors,
        "status": "passed" if not errors else "failed",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
