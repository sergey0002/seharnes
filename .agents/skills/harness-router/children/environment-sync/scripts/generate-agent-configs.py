#!/usr/bin/env python3
"""Generate native Codex and Kilo views from the harness kit.

Skills canonical root is `.agents/skills` (read by Cursor, Kilo, Antigravity and
DSH and Codex). Rules and MCP canonical root remain `.cursor/`.
"""

from __future__ import annotations

import json
import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

import rule_model


ENV_VAR_RE = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
WRAPPER_NAME = "run-with-mcp-env.sh"
BOOT_START = "<!-- BEGIN HARNESS BOOTSTRAP: generated; edit .cursor/rules -->"
BOOT_END = "<!-- END HARNESS BOOTSTRAP -->"


def retire_skill_copy(root: Path, relative: str = ".codex/skills") -> None:
    target = root / relative
    if target.is_symlink():
        if target.resolve() != (root / ".agents/skills").resolve():
            raise ValueError(f"Unmanaged skills symlink: {target}")
        target.unlink()
        return
    if not target.exists():
        return
    if not target.is_dir():
        raise ValueError(f"Unexpected skills path: {target}")
    conflicts = []
    for path in target.rglob("*"):
        if path.is_file():
            rel = path.relative_to(target)
            canon = root / ".agents/skills" / rel
            if not canon.is_file() or normalize_text(path.read_bytes()) != normalize_text(canon.read_bytes()):
                conflicts.append(path)
    for path in conflicts:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        backup = root / ".doc/skil_data/environment-sync/backups" / digest / path.relative_to(root)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    shutil.rmtree(target)
    print(f"retired {relative}; backed up {len(conflicts)} differing file(s)")


def bootstrap(root: Path) -> str:
    lines = [BOOT_START, "", "## Harness startup", "",
             "Codex: before work read `.codex/rules-index.md` and every mandatory rule listed there.",
             "Use canonical skills in `.agents/skills`; do not create a second skill mirror.", ""]
    for path in sorted((root / ".cursor/rules").rglob("*.mdc")):
        if rule_model.is_gate(rule_model.rule_frontmatter(path)):
            key = path.relative_to(root / ".cursor/rules").with_suffix("").as_posix()
            lines.extend([f"<!-- harness-gate: {key} -->",
                          rule_model.rebase_links(rule_model.body_without_frontmatter(path.read_text(encoding="utf-8")), path, root / "AGENTS.md").strip(), ""])
    return "\n".join(lines + [BOOT_END])


def discovery_files(root: Path) -> dict[Path, str]:
    nested = sorted(p for p in (root / ".agents/skills").rglob("SKILL.md")
                    if len(p.relative_to(root / ".agents/skills").parts) > 2)
    result = {root / ".agents/skills.json": json.dumps({"entries": [
        {"path": p.parent.relative_to(root).as_posix()} for p in nested
    ]}, ensure_ascii=False, indent=2) + "\n"}
    for p in nested:
        fields = rule_model.parse_frontmatter(p.read_text(encoding="utf-8"))
        name = fields.get("name", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(f"Invalid skill name: {p}")
        for view in (".dsh/skills", ".qwen/skills"):
            target = root / view / name / "SKILL.md"
            if target in result:
                raise ValueError(f"Duplicate skill name: {name}")
            result[target] = ("---\nname: " + json.dumps(name) + "\ndescription: " +
                              json.dumps(fields.get("description", ""), ensure_ascii=False) +
                              "\n---\n\n<!-- generated discovery wrapper; do not edit -->\n" +
                              f"Read `{p.relative_to(root).as_posix()}` in full and follow that canonical skill. " +
                              "Resolve its supporting resources relative to the canonical skill directory.\n")
    return result


def sync_discovery(root: Path, check: bool = False) -> list[str]:
    expected = discovery_files(root)
    receipt = root / ".doc/skil_data/environment-sync/discovery.json"
    old = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    errors = []
    for path, content in expected.items():
        rel = path.relative_to(root).as_posix()
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
        if check:
            if actual != content:
                errors.append(f"discovery mismatch: {rel}")
        elif actual != content:
            if actual is not None and hashlib.sha256(actual.encode()).hexdigest() != old.get(rel):
                raise ValueError(f"Refusing to overwrite unmanaged discovery file: {rel}")
    if errors or check:
        if (root / ".codex/skills").exists():
            errors.append("duplicate Codex skill mirror")
        if (root / ".cursor/skills").exists():
            errors.append("duplicate Cursor skill mirror")
        return errors
    for rel, digest in old.items():
        path = root / rel
        if path not in expected and path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Edited obsolete discovery file: {rel}")
            path.unlink()
    for path, content in expected.items():
        write_text(path, content)
    write_text(receipt, json.dumps({p.relative_to(root).as_posix(): hashlib.sha256(c.encode()).hexdigest()
                                  for p, c in expected.items()}, indent=2))
    return []

# Text extensions normalized to LF on copy/generate. Binary and unknown
# extensions pass through byte-identical so parity never flags them.
TEXT_EXTENSIONS = frozenset({
    ".md", ".mdc", ".markdown", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".py", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts", ".txt", ".env",
    ".example", ".dist", ".xml", ".html", ".css", ".tpl",
})


def normalize_text(data: bytes) -> bytes:
    """Normalize CRLF/CR to LF. Idempotent; LF input passes through."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_rule_front_matter(text: str) -> dict:
    """Backwards-compatible alias for the shared rule model parser."""
    return rule_model.parse_frontmatter(text)


def front_list(fields: dict, name: str) -> list[str]:
    """Backwards-compatible alias for the shared list parser."""
    return rule_model.as_list(fields.get(name))


def _index_row(rel: str, description: str, globs: list[str], prefix: str) -> str:
    name = rel[:-3].replace("/", "-")
    when = description or "описание не задано"
    if globs:
        when += " (globs: " + ", ".join(f"`{glob}`" for glob in globs) + ")"
    when = when.replace("—", "-").replace("–", "-").replace("|", "\\|")
    return f"| `{name}` | {when} | `{prefix}/{rel}` |"


def render_glob_block(rows: list[tuple[str, str, list[str]]], prefix: str) -> list[str]:
    """Path triggers for environments without a glob engine.

    Kilo, Codex and DSH cannot attach a rule by path. The generated block keeps
    the mapping visible at start, so a conditional rule still fires on the same
    files as in Cursor.
    """
    if not rows:
        return []
    lines = [
        "## Триггеры по пути",
        "",
        "<!-- glob-triggers -->",
        "Среда не прикрепляет правило по globs автоматически. Если работа касается пути из таблицы, прочитай правило до действия.",
        "",
        "| Glob | Правило | Файл |",
        "|---|---|---|",
    ]
    for rel, _description, globs in rows:
        name = rel[:-3].replace("/", "-")
        for glob in globs:
            lines.append(f"| `{glob}` | `{name}` | `{prefix}/{rel}` |")
    lines.append("")
    return lines


def render_rules_index(rows: list[tuple[str, str, list[str]]],
                       prefix: str = ".kilo/rules",
                       conditional_rows: list[tuple[str, str, list[str]]] | None = None) -> str:
    """Compact index of rules Kilo does not load at start (agent-requested)."""
    lines = [
        "# Индекс правил по требованию",
        "",
        "<!-- generated by generate-agent-configs.py; do not edit -->",
        "",
        "Правила ниже не входят в стартовый промпт. Прочитай файл, когда сработал триггер.",
        "Так в Kilo передаётся Cursor-режим agent-requested (`alwaysApply: false`).",
        "",
    ]
    lines.extend(render_glob_block(conditional_rows or [], prefix))
    lines.extend([
        "| Правило | Когда читать | Файл |",
        "|---|---|---|",
    ])
    lines.extend(_index_row(rel, description, globs, prefix) for rel, description, globs in rows)
    return "\n".join(lines) + "\n"


def render_codex_rules_index(always_rows: list[tuple[str, str, list[str]]],
                             index_rows: list[tuple[str, str, list[str]]],
                             conditional_rows: list[tuple[str, str, list[str]]] | None = None) -> str:
    """Codex has no trigger engine: one page names mandatory and on-demand rules."""
    lines = [
        "# Индекс правил (Codex)",
        "",
        "<!-- generated by generate-agent-configs.py; do not edit -->",
        "",
        "Codex не подключает `.codex/rules/*.md` автоматически. Обязательные правила",
        "прочитай до начала работы, остальные - когда сработал триггер.",
        "",
        "## Обязательные (alwaysApply: true)",
        "",
        "| Правило | Файл |",
        "|---|---|",
    ]
    for rel, _description, _globs in always_rows:
        name = rel[:-3].replace("/", "-")
        lines.append(f"| `{name}` | `.codex/rules/{rel}` |")
    lines.extend([
        "",
        "## По требованию",
        "",
    ])
    lines.extend(render_glob_block(conditional_rows or [], ".codex/rules"))
    lines.extend([
        "| Правило | Когда читать | Файл |",
        "|---|---|---|",
    ])
    lines.extend(_index_row(rel, description, globs, ".codex/rules")
                 for rel, description, globs in index_rows)
    return "\n".join(lines) + "\n"


def copy_bytes_normalized(source: Path, target: Path) -> None:
    """Copy one file, normalizing line endings for known text types."""
    data = source.read_bytes()
    if source.suffix.lower() in TEXT_EXTENSIONS or not source.suffix:
        data = normalize_text(data)
    target.write_bytes(data)
    shutil.copystat(source, target, follow_symlinks=False)


def replace_text(value: str, root: Path) -> str:
    return value.replace("${workspaceFolder}", str(root))


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE env file (comments, `export `, quotes tolerated)."""
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
        value = value.strip().strip("'\"")
        if key:
            env[key] = value
    return env


def resolve_value(value: str, root: Path, lookup: dict[str, str]) -> str:
    """Expand ${workspaceFolder} and ${env:VAR} against root + lookup."""
    result = value.replace("${workspaceFolder}", str(root))

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in lookup:
            return lookup[name]
        return os.environ.get(name, "")

    return ENV_VAR_RE.sub(fill, result)


def resolve_node(value: object, root: Path, lookup: dict[str, str]) -> object:
    if isinstance(value, str):
        return resolve_value(value, root, lookup)
    if isinstance(value, list):
        return [resolve_node(item, root, lookup) for item in value]
    if isinstance(value, dict):
        return {key: resolve_node(item, root, lookup) for key, item in value.items()}
    return value


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Canonical directory missing: {source}")
    if target.is_symlink() or target.is_file():
        target.unlink()
    target.mkdir(parents=True, exist_ok=True)
    names = {item.name for item in source.iterdir() if not item.name.startswith(".")}
    for item in target.iterdir():
        if item.name not in names:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()
    for item in source.iterdir():
        # Dotted entries are local state (generated data, caches), not canon text.
        if item.name.startswith("."):
            continue
        destination = target / item.name
        if item.is_dir():
            copy_tree(item, destination)
        else:
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            elif destination.is_symlink():
                destination.unlink()
            copy_bytes_normalized(item, destination)


def copy_scripts_pool(source: Path, target: Path) -> None:
    """Copy the optional legacy scripts pool and drop the view when it is gone."""
    if source.is_dir():
        copy_tree(source, target)
        return
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    print(f"scripts: canonical pool absent, removed {target}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized.rstrip() + "\n", encoding="utf-8", newline="\n")


def copy_file(source: Path, target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    copy_bytes_normalized(source, target)


def generate_codex(root: Path) -> None:
    cursor = root / ".cursor"
    codex = root / ".codex"
    for source in (cursor / "rules", root / ".agents" / "skills"):
        if not source.is_dir():
            raise FileNotFoundError(f"Canonical directory missing: {source}")
    codex.mkdir(exist_ok=True)

    source_agents = root / "AGENTS.md"
    if not source_agents.is_file():
        raise FileNotFoundError(f"Canonical instructions missing: {source_agents}")
    original = source_agents.read_text(encoding="utf-8")
    if (BOOT_START in original) != (BOOT_END in original):
        raise ValueError("Incomplete harness bootstrap markers")
    original = re.sub(re.escape(BOOT_START) + r".*?" + re.escape(BOOT_END), "", original, flags=re.S).rstrip()
    legacy = codex / "AGENTS.md"
    if legacy.is_file() and legacy.read_text(encoding="utf-8").strip().endswith(
            "Codex: read `.codex/rules-index.md` for mandatory and on-demand rules."):
        digest = hashlib.sha256(legacy.read_bytes()).hexdigest()[:16]
        backup = root / ".doc/skil_data/environment-sync/backups" / digest / ".codex/AGENTS.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, backup)
        legacy.unlink()
    write_text(source_agents, original + "\n\n" + bootstrap(root))
    # Project AGENTS.md is discovered natively; do not replace built-in instructions.
    config = codex / "config.toml"
    if config.is_file():
        text = config.read_text(encoding="utf-8")
        text = re.sub(r'(?m)^model_instructions_file\s*=\s*[\"\x27]AGENTS\.md[\"\x27]\s*\n', '', text)
        write_text(config, text)
    retire_skill_copy(root)
    retire_skill_copy(root, ".cursor/skills")

    rules = codex / "rules"
    if rules.is_symlink():
        rules.unlink()
    elif rules.exists():
        shutil.rmtree(rules)
    rules.mkdir(exist_ok=True)
    canon_rules = cursor / "rules"
    canon_rels = set()
    always_rows: list[tuple[str, str, list[str]]] = []
    index_rows: list[tuple[str, str, list[str]]] = []
    conditional_rows: list[tuple[str, str, list[str]]] = []
    for rule in sorted(canon_rules.rglob("*.mdc")):
        rel = rule.relative_to(canon_rules).with_suffix(".md")
        rel_posix = rel.as_posix()
        canon_rels.add(rel_posix)
        content = rule.read_text(encoding="utf-8")
        fields = rule_model.parse_frontmatter(content)
        write_text(rules / rel, rule_model.rebase_links(rule_model.body_without_frontmatter(content), rule, rules / rel))
        row = (
            rel_posix,
            str(fields.get("description", "")).strip(),
            rule_model.rule_paths(fields),
        )
        kind = rule_model.classify(fields)
        if kind == rule_model.ALWAYS:
            always_rows.append(row)
        else:
            index_rows.append(row)
            if kind == rule_model.CONDITIONAL:
                conditional_rows.append(row)
    codex_index = codex / "rules-index.md"
    if always_rows or index_rows:
        write_text(codex_index, render_codex_rules_index(always_rows, index_rows, conditional_rows))
    elif codex_index.exists():
        codex_index.unlink()
    print(f"codex: rules {len(always_rows) + len(index_rows)} "
          f"(always {len(always_rows)}), index {codex_index.name}")
    for path in sorted(rules.rglob("*"), reverse=True):
        if path.is_symlink() or path.is_file():
            if path.relative_to(rules).as_posix() not in canon_rels:
                path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    copy_scripts_pool(cursor / "scripts", codex / "scripts")
    source_env = cursor / "mcp.env"
    if source_env.exists():
        copy_file(source_env, codex / "mcp.env")
    else:
        print("codex: kept existing .codex/mcp.env (canon env missing)")

    source_mcp = cursor / "mcp.json"
    if source_mcp.exists():
        config = json.loads(source_mcp.read_text(encoding="utf-8"))
        write_text(codex / "mcp.json", json.dumps(config, indent=2, ensure_ascii=False))
    else:
        print("codex: kept existing .codex/mcp.json (canon config missing)")


def _to_workspace(value: str, root: Path) -> str:
    """Normalize an absolute path under root to ${workspaceFolder} form."""
    prefix = str(root) + "/"
    if value.startswith(prefix):
        return "${workspaceFolder}/" + value[len(prefix):]
    return value


def generate_kilo(root: Path) -> None:
    cursor = root / ".cursor"
    kilo = root / ".kilo"
    for source in (cursor / "rules",):
        if not source.is_dir():
            raise FileNotFoundError(f"Canonical directory missing: {source}")
    kilo.mkdir(exist_ok=True)
    rules = kilo / "rules"
    if rules.is_symlink():
        rules.unlink()
    elif rules.exists():
        shutil.rmtree(rules)
    rules.mkdir(exist_ok=True)
    canon_rules = cursor / "rules"
    canon_rels = set()
    always_rels: list[str] = []
    index_rows: list[tuple[str, str, list[str]]] = []
    conditional_rows: list[tuple[str, str, list[str]]] = []
    for rule in sorted(canon_rules.rglob("*.mdc")):
        rel = rule.relative_to(canon_rules).with_suffix(".md")
        rel_posix = rel.as_posix()
        canon_rels.add(rel_posix)
        content = rule.read_text(encoding="utf-8")
        fields = rule_model.parse_frontmatter(content)
        body = rule_model.body_without_frontmatter(content)
        target = rules / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text(target, rule_model.rebase_links(body, rule, target))
        kind = rule_model.classify(fields)
        if kind == rule_model.ALWAYS:
            always_rels.append(rel_posix)
        else:
            row = (
                rel_posix,
                str(fields.get("description", "")).strip(),
                rule_model.rule_paths(fields),
            )
            index_rows.append(row)
            if kind == rule_model.CONDITIONAL:
                conditional_rows.append(row)
    for path in sorted(rules.rglob("*"), reverse=True):
        if path.is_symlink() or path.is_file():
            if path.relative_to(rules).as_posix() not in canon_rels:
                path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    # Kilo reads `.agents/skills` by default. A legacy `.kilo/skills` copy is no
    # longer generated, but if it exists it may hold local files: keep it.
    if (kilo / "skills").exists() or (kilo / "skills").is_symlink():
        print("kilo: kept existing .kilo/skills (Kilo reads .agents/skills)")
    copy_scripts_pool(cursor / "scripts", kilo / "scripts")
    source_env = cursor / "mcp.env"
    if source_env.exists():
        copy_file(source_env, kilo / "mcp.env")
    else:
        print("kilo: kept existing .kilo/mcp.env (canon env missing)")
    global_env = parse_env_file(cursor / "mcp.env")

    # Kilo uses JSONC and a named MCP object with command arrays.
    # - stdio servers map to type local with the same argv.
    # - http/sse servers map to Kilo remote (url + headers), not dropped,
    #   so Tier 3 full-text search survives in Kilo.
    # - Cursor envFile/${env:VAR} has no Kilo equivalent: the shared shell
    #   wrapper loads the project-local env file at runtime, so ${env:VAR}
    #   values are intentionally NOT inlined (secrets stay in mcp.env).
    # - ${workspaceFolder} is expanded to the absolute project root because
    #   Kilo does not expand VS Code variables (else serena starts with a
    #   literal '${workspaceFolder}' project and fails activation).
    # - alwaysAllow/disabledTools have no Kilo MCP equivalent; they are
    #   recorded in the file header comment, not silently dropped.
    source_mcp = cursor / "mcp.json"
    servers = json.loads(source_mcp.read_text(encoding="utf-8")).get("mcpServers", {})
    native: dict = {"$schema": "https://app.kilo.ai/config.json", "instructions": [], "mcp": {}}
    # Kilo has no alwaysApply/globs triggers: only always-on rules go into
    # `instructions`, the rest are listed in `.kilo/rules-index.md` and read on
    # demand, the same way Cursor attaches agent-requested rules.
    instruction_rels = sorted(always_rels)
    native["instructions"] = [f".kilo/rules/{path}" for path in instruction_rels]
    index_path = kilo / "rules-index.md"
    if index_rows:
        write_text(index_path, render_rules_index(index_rows, conditional_rows=conditional_rows))
        native["instructions"].append(".kilo/rules-index.md")
    elif index_path.exists():
        index_path.unlink()
    print(f"kilo: instructions {len(instruction_rels)} rule(s), "
          f"index {len(index_rows)} rule(s)")
    skipped: dict[str, str] = {}
    permission_notes: dict[str, dict[str, list[str]]] = {}
    default_env = str(root / ".cursor" / "mcp.env")
    for name, server in servers.items():
        stype = server.get("type", "stdio")
        url = server.get("url") or server.get("serverUrl")
        if stype in {"http", "sse", "remote"} or (url and stype not in {"stdio", "local"}):
            entry: dict = {
                "type": "remote",
                "url": resolve_value(str(url), root, {**os.environ, **global_env}),
                "enabled": not (server.get("enabled", True) is False or server.get("disabled")),
            }
            if server.get("headers"):
                entry["headers"] = dict(server["headers"])
            native["mcp"][name] = entry
            if server.get("alwaysAllow") or server.get("disabledTools"):
                permission_notes[name] = {
                    "alwaysAllow": list(server.get("alwaysAllow", [])),
                    "disabledTools": list(server.get("disabledTools", [])),
                }
            continue
        if stype not in {"stdio", "local"}:
            skipped[name] = str(stype)
            continue
        command = [resolve_value(str(part), root, {**os.environ, **global_env})
                   for part in [server["command"], *server.get("args", [])]]
        env_file = server.get("envFile")
        if env_file and not any(WRAPPER_NAME in part for part in command):
            # Single wrap only: servers whose argv already invokes the
            # wrapper (e.g. mysql) must not get a second bash layer.
            # Absolute wrapper path: Kilo does not expand ${workspaceFolder}.
            command = [
                "bash",
                str(root / ".tools" / "scripts" / WRAPPER_NAME),
                *command,
            ]
        environment = {}
        for key, value in server.get("env", {}).items():
            if isinstance(value, str) and ENV_VAR_RE.fullmatch(value):
                continue
            environment[key] = (resolve_value(value, root, {**os.environ, **global_env})
                                if isinstance(value, str) else value)
        if env_file:
            resolved_env = resolve_value(str(env_file), root, {**os.environ, **global_env})
            if resolved_env != default_env:
                # Non-default env file: point the wrapper
                # at it, otherwise it would load .cursor/mcp.env instead.
                environment["MCP_ENV_FILE"] = resolved_env
        if server.get("alwaysAllow") or server.get("disabledTools"):
            permission_notes[name] = {
                "alwaysAllow": list(server.get("alwaysAllow", [])),
                "disabledTools": list(server.get("disabledTools", [])),
            }
        native["mcp"][name] = {
            "type": "local",
            "command": command,
            "enabled": not (server.get("enabled", True) is False or server.get("disabled")),
        }
        if environment:
            native["mcp"][name]["environment"] = environment
    header = [
        "// Generated from .cursor/mcp.json by .agents/skills/harness-router/children/environment-sync/scripts/generate-agent-configs.py.",
        "// Do not edit: re-run .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh.",
        "// ${env:VAR} values are provided at runtime via run-with-mcp-env.sh + mcp.env,",
        "// not inlined here, so secrets stay out of this file.",
    ]
    if skipped:
        header.append("// Skipped (unknown type): " + json.dumps(skipped, ensure_ascii=False))
    permissions: dict[str, str] = {}
    if permission_notes:
        header.append("// Cursor alwaysAllow/disabledTools have no Kilo MCP equivalent; "
                      "configure Kilo tool permissions explicitly if needed: " +
                      json.dumps(permission_notes, ensure_ascii=False))
        # P8: explicit {server}_{tool} mapping (Kilo permission keys, last match
        # wins so broad patterns go first, specific denies after).
        for server, notes in sorted(permission_notes.items()):
            for tool in notes.get("alwaysAllow", []):
                permissions[f"{server}_{tool}"] = "allow"
            for tool in notes.get("disabledTools", []):
                permissions[f"{server}_{tool}"] = "deny"
    write_text(kilo / "kilo.jsonc", "\n".join(header) + "\n" + json.dumps(native, indent=2, ensure_ascii=False))
    fragment_path = kilo / "kilo-permissions.fragment.jsonc"
    if not permissions:
        fragment_path.unlink(missing_ok=True)
    else:
        fragment = {
            "_comment": "Generated from .cursor/mcp.json alwaysAllow/disabledTools. "
                        "Merge into the top-level \"permission\" object of kilo.jsonc "
                        "manually; rules evaluate top-to-bottom, last match wins, "
                        "so keep broad patterns first. Do not edit this file.",
            "permission": permissions,
        }
        write_text(fragment_path,
                   "// " + fragment["_comment"] + "\n" +
                   json.dumps({"permission": permissions}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--check-discovery", action="store_true", help="check native skill registration and bootstrap without writing")
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / ".cursor").is_dir():
        raise SystemExit(f"Error: {root / '.cursor'} not found")
    if args.check_discovery:
        errors = sync_discovery(root, check=True)
        source = root / "AGENTS.md"
        if not source.is_file() or bootstrap(root) not in source.read_text(encoding="utf-8"):
            errors.append("missing or stale root bootstrap")
        print(json.dumps({"status": "failed" if errors else "passed", "errors": errors}))
        raise SystemExit(bool(errors))
    sync_discovery(root)
    generate_codex(root)
    generate_kilo(root)
    print(f"Generated native Codex and Kilo views in {root}")


if __name__ == "__main__":
    main()
