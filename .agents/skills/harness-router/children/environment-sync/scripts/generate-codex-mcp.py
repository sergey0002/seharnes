#!/usr/bin/env python3
"""Replace only Codex MCP settings from a Cursor MCP JSON file."""
import argparse
import collections
import json
import os
import re
import shlex
import stat
import sys
import tempfile
import tomllib
from pathlib import Path

VAR = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SECRET = re.compile(r"(secret|token|password|passwd|credential|api.?key|authorization|cookie)", re.I)


class ConfigError(Exception):
    pass


def quote(value):
    return json.dumps(value, ensure_ascii=False)


def text(value, root, allow_env=False):
    if not isinstance(value, str):
        raise ConfigError("expected string")
    value = value.replace("${workspaceFolder}", str(root))
    stripped = VAR.sub("", value) if allow_env else value
    if "${" in stripped or "\x00" in value:
        raise ConfigError("unsupported variable or invalid string")
    return value


def shell_value(value):
    parts, pos = [], 0
    for match in VAR.finditer(value):
        parts.append(shlex.quote(value[pos:match.start()]))
        parts.append('"${' + match.group(1) + ':?required environment variable missing}"')
        pos = match.end()
    parts.append(shlex.quote(value[pos:]))
    return "".join(parts)


def render_server(server, root, warnings=None):
    warnings = warnings if warnings is not None else collections.Counter()
    if not isinstance(server, dict):
        raise ConfigError("server must be an object")
    for key in ("enabled", "disabled"):
        if key in server and not isinstance(server[key], bool):
            raise ConfigError("enabled/disabled must be boolean")
    disabled = server.get("disabled", False) or not server.get("enabled", True)
    allowed = {"type", "command", "args", "env", "envFile", "url", "serverUrl", "headers", "disabled", "enabled", "alwaysAllow", "disabledTools", "cwd"}
    if set(server) - allowed:
        raise ConfigError("unsupported server field")
    if "alwaysAllow" in server and (not isinstance(server["alwaysAllow"], list) or not all(isinstance(item, str) for item in server["alwaysAllow"])):
        raise ConfigError("alwaysAllow must be a list of strings")
    if server.get("alwaysAllow"):
        warnings["alwaysAllow ignored; existing Codex approval policy retained"] += 1
    kind = server.get("type")
    remote = "url" in server or "serverUrl" in server
    if kind not in (None, "stdio", "http", "streamable-http") or (remote and kind == "stdio") or (not remote and kind in ("http", "streamable-http")):
        raise ConfigError("unsupported or conflicting transport")
    result = {}
    if remote:
        if any(k in server for k in ("command", "args", "env", "envFile", "cwd")) or ("url" in server and "serverUrl" in server and server["url"] != server["serverUrl"]):
            raise ConfigError("conflicting HTTP fields")
        url = text(server.get("url", server.get("serverUrl")), root)
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigError("HTTP URL must not contain credentials, query or fragment")
        result["url"] = url
        headers = server.get("headers", {})
        if not isinstance(headers, dict):
            raise ConfigError("headers must be an object")
        env_headers, static_headers = {}, {}
        unsafe_header = False
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ConfigError("invalid HTTP header")
            match = VAR.fullmatch(value)
            bearer = re.fullmatch(r"Bearer \$\{env:([A-Za-z_][A-Za-z0-9_]*)\}", value, re.I)
            if match:
                env_headers[key] = match.group(1)
            elif bearer and key.lower() == "authorization":
                result["bearer_token_env_var"] = bearer.group(1)
            elif key.lower() in ("accept", "content-type") and "${" not in value:
                static_headers[key] = value
            elif disabled and "${" not in value:
                unsafe_header = True
            else:
                raise ConfigError("header must reference an environment variable")
        if env_headers:
            result["env_http_headers"] = env_headers
        if static_headers:
            result["http_headers"] = static_headers
        if unsafe_header:
            warnings["disabled HTTP server has omitted literal header; inert stub prevents unauthenticated start"] += 1
            result = {"command": "/bin/sh", "args": ["-c", "exit 1"]}
    else:
        if "headers" in server:
            raise ConfigError("headers require HTTP")
        command = text(server.get("command"), root, True)
        if not command:
            raise ConfigError("empty command")
        args = server.get("args", [])
        env = server.get("env", {})
        if not isinstance(args, list) or not isinstance(env, dict):
            raise ConfigError("args must be a list and env an object")
        args = [text(v, root, True) for v in args]
        variables = {}
        for key, value in env.items():
            if not isinstance(key, str) or not ENV_NAME.fullmatch(key):
                raise ConfigError("invalid environment variable name")
            value = text(value, root, True)
            if SECRET.search(key) and not VAR.fullmatch(value):
                raise ConfigError("secret-like env values must reference an environment variable")
            variables[key] = value
        env_file = server.get("envFile")
        needs_wrapper = env_file is not None or any(VAR.search(v) for v in [command, *args, *variables.values()])
        if needs_wrapper:
            lines = ["set -eu"]
            if env_file is not None:
                path = text(env_file, root)
                if not path:
                    raise ConfigError("empty envFile")
                path = Path(path)
                if not path.is_absolute():
                    path = root / path
                lines.extend(["set -a", ". " + shlex.quote(str(path)), "set +a"])
            for key, value in sorted(variables.items()):
                lines.append("export " + key + "=" + shell_value(value))
            lines.append("exec " + " ".join(shell_value(v) for v in [command, *args]))
            result.update(command="/bin/sh", args=["-c", "\n".join(lines)])
        else:
            result.update(command=command, args=args)
            if variables:
                result["env"] = variables
        if "cwd" in server:
            result["cwd"] = text(server["cwd"], root)
    if "disabledTools" in server:
        tools = server["disabledTools"]
        if not isinstance(tools, list) or not all(isinstance(v, str) for v in tools):
            raise ConfigError("disabledTools must be a list of strings")
        result["disabled_tools"] = tools
    if disabled:
        result["enabled"] = False
    return result


def audit_canon(config, root):
    if not isinstance(config, dict) or set(config) != {"mcpServers"} or not isinstance(config["mcpServers"], dict):
        raise ConfigError("expected only mcpServers object")
    counts = collections.Counter()
    issues = collections.Counter()
    warnings = collections.Counter()
    for server in config["mcpServers"].values():
        counts["total"] += 1
        if not isinstance(server, dict):
            issues["server must be an object"] += 1
            continue
        if any(key in server and not isinstance(server[key], bool) for key in ("enabled", "disabled")):
            issues["enabled/disabled must be boolean"] += 1
        else:
            counts["disabled" if server.get("disabled", False) or not server.get("enabled", True) else "enabled"] += 1
        try:
            render_server(server, root, warnings)
        except ConfigError as exc:
            message = str(exc)
            if message != "enabled/disabled must be boolean":
                issues[message] += 1
    return {"servers": dict(sorted(counts.items())), "blockers": dict(sorted(issues.items())), "warnings": dict(sorted(warnings.items()))}


def toml_value(value):
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(quote(k) + " = " + toml_value(v) for k, v in sorted(value.items())) + " }"
    raise ConfigError("unsupported existing MCP tool policy")


def remove_mcp(source):
    try:
        before = tomllib.loads(source)
    except tomllib.TOMLDecodeError:
        raise ConfigError("invalid input TOML") from None
    # Locate table headers outside multiline strings. Verify the remaining TOML
    # semantically, so an unfamiliar syntax cannot silently remove settings.
    lines = source.splitlines(keepends=True)
    kept, skip, multiline = [], False, None
    for line in lines:
        if multiline is None:
            match = re.match(r'^\s*\[\[?\s*((?:[^\]"\']|"(?:\\.|[^"\\])*"|\'[^\']*\')+)\s*\]\]?(?:\s*#.*)?\s*$', line)
            if match:
                header = match.group(1).strip()
                try:
                    parsed = tomllib.loads('[' + header + ']\n')
                except tomllib.TOMLDecodeError:
                    raise ConfigError("unsupported TOML table header") from None
                skip = "mcp_servers" in parsed
        if not skip:
            kept.append(line)
        i = 0
        while i < len(line):
            if multiline:
                if line.startswith(multiline, i) and (multiline == "'''" or i == 0 or line[i-1] != "\\"):
                    i += 3
                    multiline = None
                else:
                    i += 1
            elif line[i] == '#':
                break
            elif line.startswith('"""', i) or line.startswith("'''", i):
                multiline = line[i:i+3]
                i += 3
            elif line[i] in "\"'":
                delim = line[i]
                i += 1
                while i < len(line) and line[i] != delim:
                    i += 2 if delim == '"' and line[i] == '\\' else 1
                i += 1
            else:
                i += 1
    result = ''.join(kept)
    try:
        after = tomllib.loads(result)
    except tomllib.TOMLDecodeError:
        raise ConfigError("cannot safely isolate MCP tables") from None
    before.pop("mcp_servers", None)
    if "mcp_servers" in after or before != after:
        raise ConfigError("cannot safely isolate MCP settings; use explicit MCP tables")
    return result


def generate(source, config, root, warnings=None):
    if not isinstance(config, dict) or set(config) != {"mcpServers"} or not isinstance(config["mcpServers"], dict):
        raise ConfigError("expected only mcpServers object")
    preserved = remove_mcp(source)
    old_servers = tomllib.loads(source).get("mcp_servers", {})
    if not isinstance(old_servers, dict):
        raise ConfigError("invalid existing MCP servers")
    blocks = []
    for name, server in sorted(config["mcpServers"].items()):
        if not isinstance(name, str) or not name:
            raise ConfigError("invalid server name")
        entry = render_server(server, root, warnings)
        old = old_servers.get(name, {})
        if not isinstance(old, dict):
            raise ConfigError("invalid existing MCP server")
        if (old.get("command") == "/bin/sh" and old.get("args") == ["-c", "exit 1"]
                and entry.get("enabled") is not False and "url" in entry
                and not entry.get("bearer_token_env_var") and not entry.get("env_http_headers")):
            raise ConfigError("enabling an inert HTTP server requires an environment-backed header")
        for field in ("default_tools_approval_mode", "tools"):
            if field in old:
                entry[field] = old[field]
        lines = ["[mcp_servers." + quote(name) + "]"]
        for key, value in entry.items():
            lines.append(key + " = " + toml_value(value))
        blocks.append('\n'.join(lines))
    output = preserved + ("\n" if preserved and not preserved.endswith("\n") else "")
    if blocks:
        output += "\n\n".join(blocks) + "\n"
    try:
        tomllib.loads(output)
    except tomllib.TOMLDecodeError:
        raise ConfigError("generated TOML is invalid") from None
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="project root containing .cursor/mcp.json")
    parser.add_argument("--config", type=Path, help="existing Codex TOML to update")
    parser.add_argument("--check", action="store_true", help="compare without writing")
    parser.add_argument("--audit-canon", action="store_true", help="report sanitized source blockers without reading or writing TOML")
    args = parser.parse_args()
    if args.audit_canon and (args.config or args.check):
        parser.error("--audit-canon cannot be combined with --config or --check")
    if not args.audit_canon and not args.config:
        parser.error("--config is required unless --audit-canon is used")
    temporary = None
    try:
        root = args.root.resolve(strict=True)
        config = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        if args.audit_canon:
            report = audit_canon(config, root)
            print(json.dumps(report, sort_keys=True))
            return 1 if report["blockers"] else 0
        target = args.config
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ConfigError("config must be a regular file, not a symlink")
        raw = target.read_bytes() if target.is_file() else b""
        warnings = collections.Counter()
        output = generate(raw.decode("utf-8"), config, root, warnings).encode("utf-8")
        for message, count in sorted(warnings.items()):
            print(f"warning: {message} ({count})", file=sys.stderr)
        if args.check:
            print("unchanged" if raw == output else "different")
            return 0 if raw == output else 1
        if raw != output:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".codex-mcp-", delete=False) as stream:
                temporary = Path(stream.name)
                mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
                os.fchmod(stream.fileno(), mode)
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            if target.is_symlink() or (target.exists() and target.read_bytes() != raw):
                raise ConfigError("config changed during generation")
            os.replace(temporary, target)
            temporary = None
        print("ok")
        return 0
    except (ConfigError, OSError, UnicodeError, ValueError, TypeError):
        error = sys.exc_info()[1]
        print("error: " + (str(error) if isinstance(error, ConfigError) else "invalid or inaccessible input/output"), file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
