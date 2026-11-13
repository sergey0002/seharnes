#!/usr/bin/env python3
"""Generate the Qoder project view from the Cursor canon.

Qoder IDE and Qoder CLI read the same project-level paths:

- rules   `<project>/.qoder/rules/**/*.md` with `trigger` frontmatter
- skills  `<project>/.qoder/skills/{skill}/SKILL.md`
- MCP     `<project>/.qoder/settings.json` -> `mcpServers`

Canon is `.cursor/rules/**/*.mdc`, `.agents/skills`, `.cursor/mcp.json`.
Cursor `alwaysApply`/`globs` are mapped to Qoder `trigger` and `glob`.
MCP `envFile` has no Qoder equivalent, so stdio servers go through the shared
`run-with-mcp-env.sh` wrapper and secrets stay in `mcp.env`.

Usage:
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qoder-config.py --root .
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qoder-config.py --root . --check
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import rule_model

TRIGGERS = {"always_on", "manual", "model_decision", "glob"}
TRIGGER_BY_KIND = {
    rule_model.ALWAYS: "always_on",
    rule_model.CONDITIONAL: "glob",
    rule_model.AGENT_REQUESTED: "model_decision",
    rule_model.MANUAL: "manual",
}
WRAPPER_NAME = "run-with-mcp-env.sh"
ENV_VAR_RE = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
TEXT_EXTENSIONS = frozenset({
    ".md", ".mdc", ".markdown", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".py", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts", ".txt", ".env",
    ".example", ".dist", ".xml", ".html", ".css", ".tpl",
})


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end]
    body = text[end + 4:]
    if body.startswith("\n"):
        body = body[1:]
    return parse_frontmatter(block), body


def parse_frontmatter(block: str) -> dict:
    """Parse the small YAML subset used by `.cursor/rules`: scalars and lists."""
    data: dict[str, object] = {}
    lines = block.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            index += 1
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in (">", "|", ">-", "|-"):
            parts = []
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if nxt and not nxt.startswith((" ", "\t")):
                    break
                parts.append(nxt.strip())
                index += 1
            data[key] = " ".join(part for part in parts if part)
            continue
        if value == "":
            items = []
            lookahead = index + 1
            while lookahead < len(lines):
                item = lines[lookahead]
                list_match = re.match(r"^\s+-\s*(.*)$", item)
                if not list_match:
                    break
                items.append(list_match.group(1).strip().strip("\"'"))
                lookahead += 1
            if items:
                data[key] = items
                index = lookahead
                continue
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value.replace("'", '"'))
            except json.JSONDecodeError:
                parsed = [part.strip().strip("\"'") for part in value[1:-1].split(",") if part.strip()]
            data[key] = parsed
        else:
            data[key] = value.strip("\"'")
        index += 1
    return data


def as_list(value: object) -> list[str]:
    return rule_model.as_list(value)


def trigger_for(front: dict) -> str:
    trigger = str(front.get("trigger", "")).strip()
    if trigger in TRIGGERS:
        return trigger
    return TRIGGER_BY_KIND[rule_model.classify(front)]


def flat_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 1:
        return parts[0] + ".md"
    if parts[0] == "mcp" and len(parts) == 2:
        return "mcp-" + parts[1] + ".md"
    return "-".join(parts) + ".md"


def render_rule(rule: Path, relative: Path) -> str:
    text = rule.read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    trigger = trigger_for(front)
    description = str(front.get("description", "")).strip()
    globs = rule_model.rule_paths(front)
    if trigger == "model_decision" and not description:
        trigger = "always_on"
    lines = ["---", f"trigger: {trigger}"]
    if description:
        lines.append("description: " + json.dumps(description, ensure_ascii=False))
    if trigger == "glob" and globs:
        lines.append("glob: " + json.dumps(globs, ensure_ascii=False))
    lines.extend(["---", ""])
    target = rule.parents[len(relative.parts) + 1] / ".qoder/rules" / flat_name(relative)
    normalized = rule_model.rebase_links(body, rule, target).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(lines) + normalized.rstrip() + "\n"


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def tree_payload(source: Path) -> dict[str, bytes]:
    """Relative path -> normalized bytes for a skill tree mirror."""
    payload: dict[str, bytes] = {}
    if not source.is_dir():
        return payload
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        payload[relative.as_posix()] = normalize(path.read_bytes())
    return payload


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        return
    for relative, data in tree_payload(source).items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            env[key] = value.strip().strip("'\"")
    return env


def resolve_value(value: str, root: Path, lookup: dict[str, str]) -> str:
    result = value.replace("${workspaceFolder}", str(root))

    def fill(match: re.Match[str]) -> str:
        return lookup.get(match.group(1), os.environ.get(match.group(1), ""))

    return ENV_VAR_RE.sub(fill, result)


def render_mcp(root: Path) -> dict:
    cursor = root / ".cursor"
    canonical = json.loads((cursor / "mcp.json").read_text(encoding="utf-8"))
    global_env = parse_env_file(cursor / "mcp.env")
    lookup = {**os.environ, **global_env}
    default_env = str(cursor / "mcp.env")
    wrapper = str(root / ".tools" / "scripts" / WRAPPER_NAME)
    servers: dict[str, dict] = {}
    enabled: list[str] = []

    for name, source in sorted(canonical.get("mcpServers", {}).items()):
        server = dict(source)
        transport = str(server.get("type", "stdio")).lower()
        url = server.get("url") or server.get("serverUrl")
        rendered: dict = {}
        if transport in {"http", "sse", "remote", "streamable-http"} or (url and transport not in {"stdio", "local"}):
            resolved_type = "http" if transport in {"http", "streamable-http"} else "sse"
            rendered["type"] = resolved_type
            rendered["url"] = resolve_value(str(url), root, lookup)
            if server.get("headers"):
                rendered["headers"] = {
                    key: resolve_value(str(value), root, lookup)
                    for key, value in server["headers"].items()
                }
        else:
            argv = [str(server["command"]), *[str(part) for part in server.get("args", [])]]
            argv = [resolve_value(part, root, lookup) for part in argv]
            env_file = server.get("envFile")
            if env_file and not any(WRAPPER_NAME in part for part in argv):
                argv = ["bash", wrapper, *argv]
            rendered["type"] = "stdio"
            rendered["command"] = argv[0]
            if argv[1:]:
                rendered["args"] = argv[1:]
            environment: dict[str, str] = {}
            for key, value in server.get("env", {}).items():
                if isinstance(value, str) and ENV_VAR_RE.fullmatch(value):
                    continue
                environment[key] = resolve_value(value, root, lookup) if isinstance(value, str) else value
            if env_file:
                resolved_env = resolve_value(str(env_file), root, lookup)
                if resolved_env != default_env:
                    environment["MCP_ENV_FILE"] = resolved_env
            if environment:
                rendered["env"] = environment

        if server.get("timeout"):
            rendered["timeout"] = server["timeout"]
        if server.get("alwaysAllow"):
            rendered["alwaysAllow"] = list(server["alwaysAllow"])
        if server.get("includeTools"):
            rendered["includeTools"] = list(server["includeTools"])
        if server.get("disabledTools"):
            rendered["excludeTools"] = list(server["disabledTools"])
        if server.get("description"):
            rendered["description"] = str(server["description"])
        if server.get("enabled", True) is False or server.get("disabled"):
            rendered["disabled"] = True
        else:
            enabled.append(name)
        servers[name] = rendered

    payload: dict = {"mcpServers": servers}
    if enabled:
        payload["mcp"] = {"enabledProjectMcpServers": enabled}
    return payload


def expected_rules(source: Path) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for rule in sorted(source.rglob("*.mdc")):
        relative = rule.relative_to(source)
        name = flat_name(relative)
        if name in rendered:
            raise SystemExit(f"name collision: {name}")
        rendered[name] = render_rule(rule, relative)
    return rendered


def compare_rules(target: Path, expected: dict[str, str]) -> list[str]:
    errors: list[str] = []
    actual: dict[str, Path] = {}
    if target.is_dir():
        for path in sorted(target.rglob("*")):
            if path.is_file() or path.is_symlink():
                actual[path.relative_to(target).as_posix()] = path
    for name in sorted(expected):
        path = actual.get(name)
        if path is None:
            errors.append(f"missing rule {name}")
        elif path.is_symlink() or normalize(path.read_bytes()) != expected[name].encode("utf-8"):
            errors.append(f"stale rule {name}")
    errors.extend(f"extra rule {name}" for name in sorted(set(actual) - set(expected)))
    return errors


def compare_tree(target: Path, expected: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    actual = {path.relative_to(target).as_posix(): path for path in target.rglob("*")
              if path.is_file() or path.is_symlink()} if target.is_dir() else {}
    for relative in sorted(expected):
        if relative not in actual:
            errors.append(f"missing skill file {relative}")
        elif actual[relative].is_symlink() or normalize(actual[relative].read_bytes()) != expected[relative]:
            errors.append(f"stale skill file {relative}")
    errors.extend(f"extra skill file {name}" for name in sorted(set(actual) - set(expected)))
    return errors


def clear_tree(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)


def preflight_view(qoder: Path, rules: dict[str, str], skills: dict[str, bytes], generated_mcp: dict,
                   replace_managed_mcp: bool = False) -> list[str]:
    """Reject unowned view data before any generated files are replaced."""
    errors: list[str] = []
    if qoder.is_symlink():
        return [f"unsafe Qoder root: {qoder}"]
    for label, expected in (("rules", rules), ("skills", skills)):
        base = qoder / label
        if base.is_symlink() or (base.exists() and not base.is_dir()):
            errors.append(f"unsafe Qoder view: {base}")
            continue
        if not base.is_dir():
            continue
        expected_dirs = {parent.as_posix() for key in expected for parent in Path(key).parents if parent != Path('.')}
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(base).as_posix()
            if path.is_symlink():
                errors.append(f"symlink in Qoder view: {label}/{relative}")
            elif path.is_dir() and relative not in expected_dirs:
                errors.append(f"unmanaged Qoder directory: {label}/{relative}")
            elif path.is_file() and relative not in expected:
                errors.append(f"unmanaged Qoder file: {label}/{relative}")
    settings = qoder / "settings.json"
    if settings.is_symlink():
        errors.append("symlink in Qoder view: settings.json")
    elif settings.exists():
        try:
            previous = json.loads(settings.read_text(encoding="utf-8"))
            if not isinstance(previous, dict) or not isinstance(previous.get("mcpServers", {}), dict):
                raise ValueError("invalid mcpServers")
            extra = set(previous.get("mcpServers", {})) - set(generated_mcp.get("mcpServers", {}))
            errors.extend(f"unmanaged Qoder MCP server: {name}" for name in sorted(extra))
            mcp = previous.get("mcp", {})
            if not isinstance(mcp, dict) or not isinstance(mcp.get("enabledProjectMcpServers", []), list):
                raise ValueError("invalid enabledProjectMcpServers")
            enabled = mcp.get("enabledProjectMcpServers", [])
            if not all(isinstance(name, str) for name in enabled):
                raise ValueError("invalid enabledProjectMcpServers")
            extra_enabled = set(enabled) - set(generated_mcp.get("mcpServers", {}))
            errors.extend(f"unmanaged Qoder enabled MCP: {name}" for name in sorted(extra_enabled))
            generated_servers = generated_mcp.get("mcpServers", {})
            existing_servers = previous.get("mcpServers", {})
            common = set(existing_servers) & set(generated_servers)
            generated_enabled = set(generated_mcp.get("mcp", {}).get("enabledProjectMcpServers", []))
            for name in sorted(common):
                if (existing_servers[name] != generated_servers[name]
                        or (name in enabled) != (name in generated_enabled)) and not replace_managed_mcp:
                    errors.append(f"Qoder MCP requires review: {name}")
        except (OSError, ValueError):
            errors.append("unreadable or invalid Qoder settings.json")
    return errors


def backup_changed_views(root: Path, qoder: Path, rules: dict[str, str], skills: dict[str, bytes], generated_mcp: dict) -> Path | None:
    changed: list[Path] = []
    for label, expected in (("rules", {k: v.encode("utf-8") for k, v in rules.items()}), ("skills", skills)):
        base = qoder / label
        for relative, payload in expected.items():
            path = base / relative
            if path.is_file() and normalize(path.read_bytes()) != normalize(payload):
                changed.append(path)
    settings = qoder / "settings.json"
    if settings.is_file():
        previous = json.loads(settings.read_text(encoding="utf-8"))
        if merge_settings(previous, generated_mcp) != previous:
            changed.append(settings)
    if not changed:
        return None
    parent = root / ".doc/skil_data/environment-sync/backups/qoder-preflight"
    for part in (root / ".doc", root / ".doc/skil_data", root / ".doc/skil_data/environment-sync", parent.parent, parent):
        if part.is_symlink():
            raise ValueError(f"unsafe backup path: {part}")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = Path(tempfile.mkdtemp(prefix="sync-", dir=parent))
    os.chmod(backup, 0o700)
    for path in changed:
        target = backup / path.relative_to(qoder)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path, target)
        os.chmod(target, 0o600)
    return backup


def merge_settings(previous: object, generated: dict) -> dict:
    """Replace managed MCP fields while preserving unrelated settings."""
    if not isinstance(previous, dict):
        return generated
    result = dict(previous)
    result["mcpServers"] = generated.get("mcpServers", {})

    generated_mcp = generated.get("mcp", {})
    previous_mcp = previous.get("mcp")
    mcp = dict(previous_mcp) if isinstance(previous_mcp, dict) else {}
    canon_enabled = list(generated_mcp.get("enabledProjectMcpServers", []))
    enabled = sorted(set(canon_enabled))
    if enabled:
        mcp["enabledProjectMcpServers"] = enabled
    else:
        mcp.pop("enabledProjectMcpServers", None)
    if mcp:
        result["mcp"] = mcp
    else:
        result.pop("mcp", None)
    return result


def check_settings(path: Path, generated: dict) -> list[str]:
    """Check all managed MCP fields against the canon."""
    if not path.is_file():
        return ["missing .qoder/settings.json"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"unreadable .qoder/settings.json: {error}"]
    servers = actual.get("mcpServers") if isinstance(actual, dict) else None
    if not isinstance(servers, dict):
        return [".qoder/settings.json: no mcpServers object"]
    errors: list[str] = []
    for name, expected in sorted(generated.get("mcpServers", {}).items()):
        if name not in servers:
            errors.append(f"settings missing server {name}")
        elif servers[name] != expected:
            errors.append(f"settings stale server {name}")
    errors.extend(f"settings extra server {name}" for name in sorted(set(servers) - set(generated.get("mcpServers", {}))))
    mcp = actual.get("mcp")
    enabled = mcp.get("enabledProjectMcpServers", []) if isinstance(mcp, dict) else []
    expected_enabled = generated.get("mcp", {}).get("enabledProjectMcpServers", [])
    if not isinstance(enabled, list) or not all(isinstance(name, str) for name in enabled) or sorted(enabled) != sorted(expected_enabled):
        errors.append("settings enabledProjectMcpServers differs from canon")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Qoder project view")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    parser.add_argument("--preflight", action="store_true", help="check for unmanaged Qoder data without writing")
    parser.add_argument("--replace-managed-mcp", action="store_true", help="replace reviewed managed MCP entries after backup")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cursor = root / ".cursor"
    if not (cursor / "mcp.json").is_file():
        print(f"canonical MCP config not found: {cursor / 'mcp.json'}", file=sys.stderr)
        return 2
    for source in (cursor / "rules", root / ".agents" / "skills"):
        if not source.is_dir():
            print(f"canonical directory not found: {source}", file=sys.stderr)
            return 2

    qoder = root / ".qoder"
    expected_rule_payload = expected_rules(cursor / "rules")
    expected_skill_payload = tree_payload(root / ".agents" / "skills")
    expected_mcp = render_mcp(root)

    if args.preflight or not args.check:
        errors = preflight_view(qoder, expected_rule_payload, expected_skill_payload, expected_mcp, args.replace_managed_mcp)
        if errors or args.preflight:
            print(json.dumps({"status": "failed_preflight" if errors else "passed", "errors": errors}, ensure_ascii=False))
            return 3 if errors else 0

    if args.check:
        errors: list[str] = []
        errors.extend(compare_rules(qoder / "rules", expected_rule_payload))
        errors.extend(compare_tree(qoder / "skills", expected_skill_payload))
        errors.extend(check_settings(qoder / "settings.json", expected_mcp))
        print(json.dumps({
            "status": "passed" if not errors else "failed",
            "errors": errors,
            "rules": len(expected_rule_payload),
            "skill_files": len(expected_skill_payload),
            "mcp_servers": len(expected_mcp["mcpServers"]),
        }, ensure_ascii=False))
        return 0 if not errors else 1

    try:
        backup = backup_changed_views(root, qoder, expected_rule_payload, expected_skill_payload, expected_mcp)
    except (OSError, ValueError) as error:
        print(f"Qoder backup failed: {error}", file=sys.stderr)
        return 3
    if backup:
        print(f"Qoder changed files backed up: {backup}")
    target_rules = qoder / "rules"
    clear_tree(target_rules)
    for name, content in expected_rule_payload.items():
        destination = target_rules / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")

    target_skills = qoder / "skills"
    clear_tree(target_skills)
    copy_tree(root / ".agents" / "skills", target_skills)

    qoder.mkdir(parents=True, exist_ok=True)
    settings_path = qoder / "settings.json"
    previous: object = {}
    if settings_path.is_file():
        try:
            previous = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    merged = merge_settings(previous, expected_mcp)
    settings_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(json.dumps({
        "status": "written",
        "out": str(qoder),
        "rules": len(expected_rule_payload),
        "skill_files": len(expected_skill_payload),
        "mcp_servers": len(expected_mcp["mcpServers"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
