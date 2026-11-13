#!/usr/bin/env python3
"""
Generate Antigravity / Gemini compatible mcp_config.json from Cursor's canonical .cursor/mcp.json.

Antigravity MCP client does not expand VS Code variables like ${workspaceFolder} or ${env:VAR},
nor does it natively support 'envFile'. This script:
1. Inlines environment variables from referenced envFiles (e.g. .cursor/mcp.env).
2. Expands ${workspaceFolder} to the absolute project root path.
3. Expands ${env:VAR} to resolved values.
4. Outputs valid mcp_config.json for Antigravity / Gemini / agents views.
"""

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path


def parse_env_file(filepath: Path) -> dict[str, str]:
    env = {}
    if not filepath.is_file():
        return env
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                env[key] = val
    return env


def resolve_string(value: str, root_path: str, lookup_env: dict[str, str]) -> str:
    res = value.replace("${workspaceFolder}", root_path)

    def repl(match):
        var_name = match.group(1)
        if var_name in lookup_env:
            return lookup_env[var_name]
        if var_name in os.environ:
            return os.environ[var_name]
        return ""

    res = re.sub(r"\$\{env:([A-Za-z0-9_]+)\}", repl, res)
    return res


def resolve_vars(value, root_path: str, lookup_env: dict[str, str]):
    if isinstance(value, str):
        return resolve_string(value, root_path, lookup_env)
    elif isinstance(value, list):
        return [resolve_vars(item, root_path, lookup_env) for item in value]
    elif isinstance(value, dict):
        return {k: resolve_vars(v, root_path, lookup_env) for k, v in value.items()}
    return value


def render_native(config: dict, root_dir: Path) -> dict:
    """Render the current Linux/WSL-native view (unchanged behavior)."""
    root_str = str(root_dir)
    global_env = parse_env_file(root_dir / ".cursor" / "mcp.env")
    servers = config.get("mcpServers", {})
    new_servers = {}

    for name, server in servers.items():
        s = dict(server)
        has_env_file = "envFile" in s
        has_inline_env = "env" in s

        server_env = {}
        if has_env_file:
            server_env.update(global_env)
            env_file_path = s["envFile"].replace("${workspaceFolder}", root_str)
            custom_env = parse_env_file(Path(env_file_path))
            server_env.update(custom_env)

        lookup = dict(os.environ)
        lookup.update(global_env)
        lookup.update(server_env)
        if has_inline_env:
            for k, v in s["env"].items():
                if isinstance(v, str) and v.startswith("${env:"):
                    continue
                lookup[k] = v

        if has_env_file:
            merged_env = dict(server_env)
            if has_inline_env:
                merged_env.update(s["env"])
            s["env"] = merged_env

        s.pop("envFile", None)
        s = resolve_vars(s, root_str, lookup)

        # Ensure remote HTTP / SSE servers have both 'serverUrl' (Antigravity standard) and 'url' (Cursor standard)
        if "url" in s and "serverUrl" not in s:
            s["serverUrl"] = s["url"]
        if "serverUrl" in s and "url" not in s:
            s["url"] = s["serverUrl"]

        # xdebug is disabled in canon by default. When it is re-enabled, the
        # Antigravity/Gemini copy gets its own port so a Cursor session and an
        # Antigravity session can debug at the same time without colliding.
        if name == "xdebug" and not (s.get("enabled", True) is False or s.get("disabled")):
            if "env" not in s or s["env"] is None:
                s["env"] = {}
            if "XDEBUG_PORT" not in s["env"]:
                s["env"]["XDEBUG_PORT"] = "9004"

        new_servers[name] = s

    return {"mcpServers": new_servers}


def build_wsl_script(root_str: str, server: dict, lookup_env: dict[str, str]) -> str:
    """Build one `bash -lc` script that reproduces a stdio server inside WSL."""
    command = [str(server["command"])]
    command.extend(str(item) for item in server.get("args", []))
    command = [resolve_string(item, root_str, lookup_env) for item in command]

    parts = [f"cd {shlex.quote(root_str)}"]
    env_file = server.get("envFile")
    if env_file:
        resolved_env = resolve_string(str(env_file), root_str, lookup_env)
        # Secrets stay in the WSL env file; they are not copied into the
        # Windows-side JSON.
        parts.extend(["set -a", ". " + shlex.quote(resolved_env)])

    for key, value in sorted(server.get("env", {}).items()):
        text = value if isinstance(value, str) else json.dumps(value)
        if text.startswith("${env:") and env_file:
            continue
        resolved = resolve_string(text, root_str, lookup_env)
        parts.append(f"export {key}={shlex.quote(resolved)}")

    parts.append("exec " + " ".join(shlex.quote(item) for item in command))
    return " && ".join(parts)


def _copy_permissions(source: dict, target: dict) -> None:
    """Keep Cursor/Antigravity tool permissions when the client understands them."""
    for key in ("alwaysAllow", "disabledTools"):
        if source.get(key):
            target[key] = list(source[key])


def render_windows_wsl(config: dict, root_dir: Path, distro: str) -> dict:
    """Render a Windows Antigravity view that runs every stdio server in WSL.

    The Antigravity language server is a Windows process even when the
    workspace is opened through WSL remote. It reads the Windows user profile
    config and spawns MCP processes on Windows, where Linux argv paths and
    `bash /home/...` do not work. HTTP servers stay plain URLs; stdio servers
    are wrapped in `wsl.exe ... bash -lc` so they reuse the same WSL toolchain
    as Cursor/Kilo.
    """
    root_str = str(root_dir)
    global_env = parse_env_file(root_dir / ".cursor" / "mcp.env")
    lookup = dict(os.environ)
    lookup.update(global_env)
    servers = config.get("mcpServers", {})
    new_servers = {}

    for name, server in servers.items():
        s = dict(server)
        is_remote = (
            s.get("type") in {"http", "sse", "remote"}
            or (("url" in s or "serverUrl" in s) and s.get("type") not in {"stdio", "local"})
        )
        if is_remote:
            url = resolve_string(str(s.get("url") or s.get("serverUrl")), root_str, lookup)
            entry = {
                "type": s.get("type", "http"),
                "url": url,
                "serverUrl": url,
                "disabled": s.get("enabled", True) is False or bool(s.get("disabled", False)),
            }
            if s.get("headers"):
                entry["headers"] = resolve_vars(s["headers"], root_str, lookup)
            _copy_permissions(server, entry)
            new_servers[name] = entry
            continue

        launch = server
        if name == "xdebug" and not (s.get("enabled", True) is False or s.get("disabled", False)):
            launch = dict(server)
            launch["env"] = dict(server.get("env", {}))
            launch["env"].setdefault("XDEBUG_PORT", "9004")
        script = build_wsl_script(root_str, launch, lookup)
        args = ["-d", distro] if distro else []
        args.extend(["--", "bash", "-lc", script])
        entry = {
            "command": "wsl.exe",
            "args": args,
            "disabled": s.get("enabled", True) is False or bool(s.get("disabled", False)),
        }
        _copy_permissions(server, entry)
        new_servers[name] = entry

    return {"mcpServers": new_servers}


def write_config(out_path: Path, out_config: dict) -> None:
    if out_path.is_symlink():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main(argv=None) -> int:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", help="project root (default: this repository)")
    parser.add_argument("out", nargs="?", help="output path (positional compatibility)")
    parser.add_argument(
        "--host",
        choices=("native", "windows-wsl"),
        default="native",
        help="native = current Linux/WSL client; windows-wsl = Windows Antigravity, stdio via wsl.exe",
    )
    parser.add_argument("--distro", default="", help="WSL distro name for --host windows-wsl")
    parser.add_argument("--out", dest="out_option", help="output path")
    args = parser.parse_args(argv)

    root_dir = Path(args.root).resolve() if args.root else script_dir.parent.parent
    cursor_mcp = root_dir / ".cursor" / "mcp.json"
    if not cursor_mcp.is_file():
        print(f"Error: {cursor_mcp} not found", file=sys.stderr)
        return 1

    with open(cursor_mcp, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.host == "windows-wsl":
        out_config = render_windows_wsl(config, root_dir, args.distro)
    else:
        out_config = render_native(config, root_dir)

    requested = args.out_option or args.out
    out_path = Path(requested).resolve() if requested else Path(root_dir) / ".doc" / "skil_data" / "harness-router" / "antigravity_mcp_config.json"

    write_config(out_path, out_config)
    print(f"Successfully generated {out_path} from {cursor_mcp} (host={args.host})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
