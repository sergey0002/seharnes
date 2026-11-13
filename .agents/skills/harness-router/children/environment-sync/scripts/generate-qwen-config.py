#!/usr/bin/env python3
"""Generate the Qwen Code project view from the Cursor canon.

Qwen Code reads project configuration from `.qwen/`:

- rules  `<project>/.qwen/rules/**/*.md` (frontmatter `paths:` makes a rule conditional)
- skills `<project>/.qwen/skills/{skill}/SKILL.md` (`.agents/skills` is read natively too)
- MCP    `<project>/.qwen/settings.json` -> `mcpServers`
- memory `<project>/QWEN.md` and `AGENTS.md` (both read natively)

Mapping from `.cursor/rules/*.mdc`:

- `alwaysApply: true` -> baseline rule (no `paths`)
- `globs` / `paths`   -> conditional rule with `paths`
- `description` only  -> generated Skill `rule-<name>`, because Qwen has no
  model-decision rule trigger and a baseline copy would sit in every request.

Qwen has no `envFile`: stdio servers go through `run-with-mcp-env.sh`, so
secrets stay in `mcp.env`. HTTP servers use `httpUrl`, SSE servers use `url`.

Usage:
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qwen-config.py --root .
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qwen-config.py --root . --check
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import rule_model

WRAPPER_NAME = "run-with-mcp-env.sh"
ENV_VAR_RE = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
SKILL_NAME_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


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
    if isinstance(value, list):
        return [str(item).strip().strip("\"'") for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip().strip("\"'") for part in value.split(",") if part.strip()]
    return []


def flat_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "mcp" and len(parts) == 2:
        return "mcp-" + parts[1]
    return "-".join(parts)


def rule_shape(front: dict) -> tuple[str, list[str]]:
    """Return (shape, paths). Shape is `baseline`, `conditional` or `skill`."""
    kind = rule_model.classify(front)
    if kind == rule_model.CONDITIONAL:
        return "conditional", rule_model.rule_paths(front)
    if kind == rule_model.AGENT_REQUESTED:
        return "skill", []
    return "baseline", []


def yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in items) + "]"


def normalized_body(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def render_rule(front: dict, body: str, paths: list[str]) -> str:
    description = str(front.get("description", "")).strip()
    lines = ["---"]
    if description:
        lines.append("description: " + json.dumps(description, ensure_ascii=False))
    if paths:
        lines.append("paths: " + yaml_list(paths))
    lines.extend(["---", ""])
    return "\n".join(lines) + normalized_body(body)


def render_skill(front: dict, body: str, name: str) -> str:
    description = str(front.get("description", "")).strip() or f"Project rule {name}"
    lines = [
        "---",
        "name: " + json.dumps(name, ensure_ascii=False),
        "description: " + json.dumps(description, ensure_ascii=False),
        "---",
        "",
    ]
    return "\n".join(lines) + normalized_body(body)


def expected_rules(source: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return (rules, skills) payloads keyed by output relative path."""
    rules: dict[str, str] = {}
    skills: dict[str, str] = {}
    for rule in sorted(source.rglob("*.mdc")):
        relative = rule.relative_to(source)
        name = flat_name(relative)
        text = rule.read_text(encoding="utf-8")
        front, body = split_frontmatter(text)
        shape, paths = rule_shape(front)
        if shape == "skill":
            skill_name = "rule-" + SKILL_NAME_RE.sub("-", name)
            target = source.parent.parent / ".qwen/skills" / skill_name / "SKILL.md"
            skills[f"{skill_name}/SKILL.md"] = render_skill(front, rule_model.rebase_links(body, rule, target), skill_name)
        else:
            target = source.parent.parent / ".qwen/rules" / (name + ".md")
            rules[name + ".md"] = render_rule(front, rule_model.rebase_links(body, rule, target), paths)
    return rules, skills


def normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def tree_payload(source: Path) -> dict[str, bytes]:
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
    excluded: list[str] = []

    for name, source in sorted(canonical.get("mcpServers", {}).items()):
        server = dict(source)
        disabled = server.get("enabled", True) is False or bool(server.get("disabled"))
        if disabled:
            excluded.append(name)
            continue
        transport = str(server.get("type", "stdio")).lower()
        url = server.get("url") or server.get("serverUrl")
        rendered: dict = {}
        if transport in {"sse", "remote"} or (url and transport not in {"stdio", "local", "http", "streamable-http"}):
            rendered["url"] = resolve_value(str(url), root, lookup)
            if server.get("headers"):
                rendered["headers"] = {
                    key: resolve_value(str(value), root, lookup)
                    for key, value in server["headers"].items()
                }
        elif transport in {"http", "streamable-http"} or url:
            rendered["httpUrl"] = resolve_value(str(url), root, lookup)
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
            if server.get("cwd"):
                rendered["cwd"] = resolve_value(str(server["cwd"]), root, lookup)

        if server.get("timeout"):
            rendered["timeout"] = server["timeout"]
        if server.get("alwaysAllow"):
            rendered["trust"] = True
        if server.get("includeTools"):
            rendered["includeTools"] = list(server["includeTools"])
        if server.get("disabledTools"):
            rendered["excludeTools"] = list(server["disabledTools"])
        servers[name] = rendered

    payload: dict = {"mcpServers": servers}
    if excluded:
        payload["mcp"] = {"excluded": excluded}
    return payload


def merge_settings(previous: object, generated: dict) -> dict:
    """Replace managed MCP fields while preserving unrelated settings."""
    if not isinstance(previous, dict):
        return generated
    result = dict(previous)
    result["mcpServers"] = generated.get("mcpServers", {})

    generated_mcp = generated.get("mcp", {})
    previous_mcp = previous.get("mcp")
    mcp = dict(previous_mcp) if isinstance(previous_mcp, dict) else {}
    canon_excluded = list(generated_mcp.get("excluded", []))
    excluded = sorted(set(canon_excluded))
    if excluded:
        mcp["excluded"] = excluded
    else:
        mcp.pop("excluded", None)
    if mcp:
        result["mcp"] = mcp
    else:
        result.pop("mcp", None)
    return result


def clear_tree(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)


def compare_files(target: Path, expected: dict[str, str], rule_skills: bool = False) -> list[str]:
    errors: list[str] = []
    actual = set()
    if target.is_dir():
        for path in target.rglob("*"):
            relative = path.relative_to(target)
            if rule_skills and not relative.parts[0].startswith("rule-"):
                continue
            if path.is_file() or path.is_symlink():
                actual.add(relative.as_posix())
    for relative in sorted(expected):
        path = target / relative
        if not path.is_file():
            errors.append(f"missing {relative}")
        elif path.is_symlink() or normalize(path.read_bytes()) != expected[relative].encode("utf-8"):
            errors.append(f"stale {relative}")
    errors.extend(f"extra {relative}" for relative in sorted(actual - set(expected)))
    return errors


def check_settings(path: Path, generated: dict) -> list[str]:
    if not path.is_file():
        return ["missing .qwen/settings.json"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"unreadable .qwen/settings.json: {error}"]
    servers = actual.get("mcpServers") if isinstance(actual, dict) else None
    if not isinstance(servers, dict):
        return [".qwen/settings.json: no mcpServers object"]
    errors: list[str] = []
    for name, value in sorted(generated.get("mcpServers", {}).items()):
        if name not in servers:
            errors.append(f"settings missing server {name}")
        elif servers[name] != value:
            errors.append(f"settings stale server {name}")
    errors.extend(f"settings extra server {name}" for name in sorted(set(servers) - set(generated.get("mcpServers", {}))))
    mcp = actual.get("mcp")
    excluded = mcp.get("excluded", []) if isinstance(mcp, dict) else []
    expected_excluded = generated.get("mcp", {}).get("excluded", [])
    if not isinstance(excluded, list) or not all(isinstance(name, str) for name in excluded) or sorted(excluded) != sorted(expected_excluded):
        errors.append("settings excluded differs from canon")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the Qwen Code project view")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    cursor = root / ".cursor"
    if not (cursor / "mcp.json").is_file():
        print(f"canonical MCP config not found: {cursor / 'mcp.json'}", file=sys.stderr)
        return 2
    if not (cursor / "rules").is_dir():
        print(f"canonical rules directory not found: {cursor / 'rules'}", file=sys.stderr)
        return 2

    qwen = root / ".qwen"
    rules, skills = expected_rules(cursor / "rules")
    expected_mcp = render_mcp(root)

    if args.check:
        errors: list[str] = []
        errors.extend(compare_files(qwen / "rules", rules))
        errors.extend(compare_files(qwen / "skills", skills, rule_skills=True))
        errors.extend(check_settings(qwen / "settings.json", expected_mcp))
        print(json.dumps({
            "status": "passed" if not errors else "failed",
            "errors": errors,
            "rules": len(rules),
            "rule_skills": len(skills),
            "mcp_servers": len(expected_mcp["mcpServers"]),
        }, ensure_ascii=False))
        return 0 if not errors else 1

    target_rules = qwen / "rules"
    clear_tree(target_rules)
    for relative, content in rules.items():
        destination = target_rules / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")

    target_skills = qwen / "skills"
    if target_skills.is_dir():
        for path in target_skills.glob("rule-*"):
            clear_tree(path)
    for relative, content in skills.items():
        destination = target_skills / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")

    qwen.mkdir(parents=True, exist_ok=True)
    settings_path = qwen / "settings.json"
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
        "out": str(qwen),
        "rules": len(rules),
        "rule_skills": len(skills),
        "mcp_servers": len(expected_mcp["mcpServers"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
