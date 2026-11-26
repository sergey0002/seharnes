#!/usr/bin/env python3
"""Generate the omp (oh-my-pi) project view from the Cursor canon.

omp discovers the canon natively: it reads `.cursor/rules/*.mdc` (one level),
`.agents/skills/<name>/SKILL.md` (one level) and `AGENTS.md`. Nested rules and
nested skills are deliberately not scanned, because the root files are routers
that link to their children; the agent follows a link and reads the child by
path. Mirroring children into the root would put their bodies and descriptions
into the prompt and break that context economy.

The only thing omp cannot read from the canon is the MCP config: its Cursor
provider ignores `disabled`, `envFile`, `${workspaceFolder}` and `${env:VAR}`,
and omp drops a server named `playwright` while its built-in browser is active.
So the generator writes exactly one file, `.omp/mcp.json`, and removes the
`.omp/rules` and `.omp/skills` mirrors that earlier versions produced.

No `.omp/AGENTS.md` is written: a native project file would shadow the root
`AGENTS.md` that omp already loads.

Usage:
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-omp-config.py --root .
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-omp-config.py --root . --check
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

WRAPPER_NAME = "run-with-mcp-env.sh"
ENV_VAR_RE = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
TRANSPORTS = {"stdio", "http", "sse"}
RETIRED = (".omp/rules", ".omp/skills")

# `${workspaceFolder}` means two different things in the canon, and omp expands
# neither, so the generator must split them:
#
# - a tool path (`<root>/.tools/...`, `<root>/.agents/...`) is the shared harness
#   install; it must stay absolute, because a task worktree may not have those
#   directories at all;
# - a workspace subject (a repository to inspect, a project root to analyse) must
#   follow the current workspace, which Kandev recreates under a new random name
#   for every task. omp spawns a stdio server with the session project directory
#   as its working directory, so the subject becomes `.` or is dropped to fall
#   back to `process.cwd()`.
WORKSPACE_SUBJECT_FLAGS = {"--repository", "--root", "--project-path", "--path", "--workspace"}
WORKSPACE_SUBJECT_ENV = {"MCP_WORKSPACE", "PROJECT_ROOT", "PROJECT_PATH", "WORKSPACE_ROOT", "REPO_PATH"}
MCP_SCHEMA = ("https://raw.githubusercontent.com/can1357/oh-my-pi/main/"
              "packages/coding-agent/src/config/mcp-schema.json")


def resolve_tool(value: str, root: Path) -> str:
    """Expand ${workspaceFolder} as the shared harness install."""
    result = value.replace("${workspaceFolder}", str(root))
    return ENV_VAR_RE.sub(lambda match: "${" + match.group(1) + "}", result)


def resolve_subject(value: str) -> str:
    """Expand ${workspaceFolder} as the current workspace, i.e. the server cwd."""
    return value.replace("${workspaceFolder}", ".")


def render_args(args: list, root: Path) -> list[str]:
    rendered: list[str] = []
    subject_next = False
    for part in args:
        text = str(part)
        rendered.append(resolve_subject(text) if subject_next else resolve_tool(text, root))
        subject_next = text in WORKSPACE_SUBJECT_FLAGS
    return rendered


def render_env(source: dict, root: Path) -> dict:
    environment: dict[str, str] = {}
    for key, value in source.items():
        if not isinstance(value, str):
            environment[key] = value
            continue
        if key in WORKSPACE_SUBJECT_ENV:
            if value.strip() == "${workspaceFolder}":
                continue
            environment[key] = resolve_subject(value)
            continue
        if ENV_VAR_RE.fullmatch(value):
            continue
        environment[key] = resolve_tool(value, root)
    return environment


def render_server(source: dict, root: Path) -> dict:
    server = dict(source)
    enabled = not (server.get("enabled", True) is False or bool(server.get("disabled")))
    transport = str(server.get("type", "stdio")).lower()
    url = server.get("url") or server.get("serverUrl")
    if transport not in TRANSPORTS:
        transport = "http" if url else "stdio"
    rendered: dict = {"type": transport, "enabled": enabled}

    if transport in {"http", "sse"}:
        rendered["url"] = resolve_tool(str(url), root)
        if server.get("headers"):
            rendered["headers"] = {
                key: resolve_tool(str(value), root)
                for key, value in server["headers"].items()
            }
    else:
        argv = [str(server["command"]), *render_args(server.get("args", []), root)]
        env_file = server.get("envFile")
        if env_file and not any(WRAPPER_NAME in part for part in argv):
            argv = ["bash", str(root / ".tools" / "scripts" / WRAPPER_NAME), *argv]
        rendered["command"] = argv[0]
        if argv[1:]:
            rendered["args"] = argv[1:]
        environment = render_env(server.get("env", {}), root)
        if env_file:
            resolved_env = resolve_tool(str(env_file), root)
            if resolved_env != str(root / ".cursor" / "mcp.env"):
                environment["MCP_ENV_FILE"] = resolved_env
        if environment:
            rendered["env"] = environment
        if server.get("cwd"):
            rendered["cwd"] = resolve_subject(str(server["cwd"]))

    if server.get("timeout"):
        rendered["timeout"] = server["timeout"]
    if server.get("instructions") is False:
        rendered["instructions"] = False
    return rendered


def render_mcp(root: Path) -> dict:
    canonical = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    servers = {
        name: render_server(server, root)
        for name, server in sorted(canonical.get("mcpServers", {}).items())
    }
    return {"mcpServers": servers}


def local_servers(path: Path, generated: dict) -> dict:
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        name: value for name, value in parsed.get("mcpServers", {}).items()
        if name not in generated["mcpServers"]
    }


def check_mcp(path: Path, generated: dict) -> list[str]:
    """Compare canonical servers; local additions in `.omp/mcp.json` are allowed."""
    if not path.is_file():
        return ["missing .omp/mcp.json"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"unreadable .omp/mcp.json: {error}"]
    servers = actual.get("mcpServers") if isinstance(actual, dict) else None
    if not isinstance(servers, dict):
        return [".omp/mcp.json: no mcpServers object"]
    errors: list[str] = []
    for name, value in sorted(generated.get("mcpServers", {}).items()):
        if name not in servers:
            errors.append(f"mcp missing server {name}")
        elif servers[name] != value:
            errors.append(f"mcp stale server {name}")
    return errors


def retired_present(root: Path) -> list[str]:
    return [relative for relative in RETIRED if (root / relative).exists()]


def remove_retired(root: Path) -> None:
    for relative in RETIRED:
        path = root / relative
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the omp (oh-my-pi) project view")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cursor = root / ".cursor"
    if not (cursor / "mcp.json").is_file():
        print(f"canonical MCP config not found: {cursor / 'mcp.json'}", file=sys.stderr)
        return 2

    omp = root / ".omp"
    mcp_path = omp / "mcp.json"
    mcp = render_mcp(root)

    if args.check:
        errors = check_mcp(mcp_path, mcp)
        errors.extend(f"stale mirror {relative}: omp reads the canon natively"
                      for relative in retired_present(root))
        print(json.dumps({
            "status": "passed" if not errors else "failed",
            "errors": errors,
            "mcp_servers": len(mcp["mcpServers"]),
        }, ensure_ascii=False))
        return 0 if not errors else 1

    remove_retired(root)
    omp.mkdir(parents=True, exist_ok=True)
    keep = local_servers(mcp_path, mcp)
    payload = {"$schema": MCP_SCHEMA, "mcpServers": {**mcp["mcpServers"], **keep}}
    mcp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")

    print(json.dumps({
        "status": "written",
        "out": str(mcp_path),
        "mcp_servers": len(mcp["mcpServers"]),
        "local_servers": len(keep),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
