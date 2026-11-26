"""Target adaptations applied by the export engine after files are in place.

Each step is a small, auditable transformation of files the engine has just
written. They never touch files that are not part of the selected kit set.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

TEXT_SUFFIXES = {".md", ".mdc", ".json", ".jsonc", ".mjs", ".js", ".cjs", ".ts", ".sh",
                 ".ps1", ".psm1", ".cmd", ".bat", ".toml", ".yml", ".yaml", ".txt", ".py"}

DISABLE_SERVERS = ("codeprism",)
CODEPRISM_PLACEHOLDER = "http://127.0.0.1:0/mcp"
REPLACED_TOKEN = "REPLACE_WITH_SOURCEGRAPH_MCP_TOKEN"
SCRUB_KEYS = ("PLAYWRIGHT_MCP_EXECUTABLE_PATH", "CHROME_PATH", "LD_LIBRARY_PATH")

MCP_JSON_FILES = (".cursor/mcp.json",)
REGISTRY_RELATIVE = ".agents/skills/harness-router/children/improvement/scripts/component_registry.json"

# Absolute paths in the shipped canon that name the source project by slug.
SLUG_PATTERN = re.compile(r"(?:^|[^A-Za-z0-9_-])home-newuser-projects-([A-Za-z0-9_-]+)")


@dataclass
class AdaptReport:
    files_rewritten: int = 0
    doc_links: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    disabled_servers: list[str] = field(default_factory=list)
    registry_removed: list[str] = field(default_factory=list)
    scrub_hits: int = 0


def _write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _text_files(root: Path, paths: list[str]) -> list[str]:
    result = []
    for path in paths:
        if Path(path).suffix.lower() in TEXT_SUFFIXES:
            full = root / path
            if full.is_file():
                result.append(path)
    return result


def project_slug(path: str | Path) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(path).strip("/").replace("/", "-"))


def rewrite_source_paths(root: Path, source_root: Path, target_root: Path,
                         paths: list[str], report: AdaptReport) -> None:
    forms = [str(source_root), str(source_root).replace("\\", "/"), str(source_root).replace("/", "\\")]
    forms = [form for form in dict.fromkeys(forms) if form]
    source_slug = project_slug(source_root)
    target_slug = project_slug(target_root)
    target_forms = [str(target_root), str(target_root).replace("\\", "/"),
                    str(target_root).replace("/", "\\")]
    target_form = next((form for form in target_forms if "/" in form), str(target_root))
    for relative in _text_files(root, paths):
        full = root / relative
        raw = full.read_text(encoding="utf-8", errors="surrogateescape")
        new = raw
        for form in forms:
            new = new.replace(form, target_form)
        if source_slug != target_slug:
            new = new.replace(source_slug, target_slug)
        if new != raw:
            _write_text(full, new)
            report.files_rewritten += 1


def scrub_mcp_config(root: Path, report: AdaptReport) -> None:
    for relative in MCP_JSON_FILES:
        full = root / relative
        if not full.is_file():
            continue
        try:
            data = json.loads(full.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            report.warnings.append(f"mcp config is not valid JSON: {relative}")
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        changed = False
        for server in servers.values():
            if not isinstance(server, dict):
                continue
            headers = server.get("headers")
            if isinstance(headers, dict) and "Authorization" in headers:
                if "sgp_" in str(headers["Authorization"]):
                    headers["Authorization"] = f"token {REPLACED_TOKEN}"
                    changed = True
            env = server.get("env")
            if isinstance(env, dict):
                for key in SCRUB_KEYS:
                    if env.get(key):
                        env[key] = ""
                        changed = True
                        report.scrub_hits += 1
        if changed:
            _write_text(full, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            report.files_rewritten += 1


def disable_mcp_servers(root: Path, report: AdaptReport) -> list[str]:
    disabled: list[str] = []
    for relative in MCP_JSON_FILES:
        full = root / relative
        if not full.is_file():
            continue
        try:
            data = json.loads(full.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            report.warnings.append(f"mcp config is not valid JSON: {relative}")
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            continue
        changed = False
        for name in DISABLE_SERVERS:
            server = servers.get(name)
            if not isinstance(server, dict):
                continue
            server["disabled"] = True
            if "url" in server:
                server["url"] = CODEPRISM_PLACEHOLDER
            if "command" in server:
                server.pop("command", None)
                server.pop("args", None)
            changed = True
            if name not in disabled:
                disabled.append(name)
        if changed:
            _write_text(full, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            report.files_rewritten += 1
    report.disabled_servers = disabled
    return disabled


def set_serena_project_name(root: Path, name: str, report: AdaptReport) -> None:
    full = root / ".serena/project.yml"
    if not full.is_file():
        return
    raw = full.read_text(encoding="utf-8", errors="surrogateescape")
    new = re.sub(r"(?m)^project_name:\s*\"[^\"]*\"", f'project_name: "{name}"', raw)
    if new == raw:
        new = re.sub(r"(?m)^project_name:\s*'[^']*'", f'project_name: "{name}"', raw)
    if new != raw:
        _write_text(full, new)
        report.files_rewritten += 1


def prune_registry(root: Path, report: AdaptReport) -> None:
    full = root / REGISTRY_RELATIVE
    if not full.is_file():
        return
    try:
        data = json.loads(full.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        report.warnings.append(f"component registry is not valid JSON: {REGISTRY_RELATIVE}")
        return
    components = data.get("components")
    if not isinstance(components, dict):
        return
    removed: list[str] = []
    for name in list(components):
        entry = components[name]
        if not isinstance(entry, dict):
            continue
        skill = None
        for item in entry.get("required_files") or []:
            match = re.fullmatch(r"\.agents/skills/([^/]+)/SKILL\.md", str(item))
            if match:
                skill = match.group(1)
                break
        if skill and not (root / ".agents/skills" / skill).is_dir():
            components.pop(name)
            removed.append(name)
            continue
        for group in ("required_files", "config_paths"):
            items = entry.get(group)
            if isinstance(items, list):
                entry[group] = [item for item in items
                                if isinstance(item, str) and (root / item.replace("/", "/")).exists()]
    known = set(components)
    deps_changed = False
    for entry in components.values():
        if isinstance(entry, dict) and isinstance(entry.get("skill_dependencies"), list):
            kept = [dep for dep in entry["skill_dependencies"] if dep in known]
            if len(kept) != len(entry["skill_dependencies"]):
                entry["skill_dependencies"] = kept
                deps_changed = True
    if removed or deps_changed:
        _write_text(full, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        report.files_rewritten += 1
    report.registry_removed = removed


FENCE = re.compile(r"(?ms)^```[^\n]*\n.*?^```[^\n]*(?:\n|$)")
INLINE = re.compile(r"`+[^`\n]*`+")
LINK = re.compile(r"(?<!!)\[([^\]\r\n]+)\]\(([^)\r\n]+)\)")


def prune_skill_manifests(root: Path, report: AdaptReport) -> None:
    """Drop manifest entries whose files or skills are absent from the kit."""
    skills_root = root / ".agents/skills"
    if not skills_root.is_dir():
        return
    for manifest in skills_root.rglob("skill.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            report.warnings.append(f"skill manifest is not valid JSON: {manifest}")
            continue
        if not isinstance(data, dict):
            continue
        base = manifest.parent
        changed = False
        resources = data.get("resources")
        if isinstance(resources, dict):
            for group in ("scripts", "references", "assets"):
                items = resources.get(group)
                if not isinstance(items, list):
                    continue
                kept = []
                for item in items:
                    if not isinstance(item, str):
                        continue
                    if (base / item).exists():
                        kept.append(item)
                    else:
                        changed = True
                if len(kept) != len(items):
                    resources[group] = kept
        children = data.get("children")
        if isinstance(children, list):
            kept = []
            for item in children:
                name = item.get("name") if isinstance(item, dict) else item
                if isinstance(name, str) and (base / "children" / name).is_dir():
                    kept.append(item)
                else:
                    changed = True
            if len(kept) != len(children):
                data["children"] = kept
        dependencies = data.get("dependencies")
        if isinstance(dependencies, dict):
            skills = dependencies.get("skills")
            if isinstance(skills, list):
                kept = []
                for item in skills:
                    name = item.get("name") if isinstance(item, dict) else None
                    if isinstance(name, str) and (skills_root / name).is_dir():
                        kept.append(item)
                    else:
                        changed = True
                if len(kept) != len(skills):
                    dependencies["skills"] = kept
            project = dependencies.get("project")
            if isinstance(project, list):
                kept = []
                for item in project:
                    path = item.get("path") if isinstance(item, dict) else None
                    if isinstance(path, str) and (root / path).exists():
                        kept.append(item)
                    else:
                        changed = True
                if len(kept) != len(project):
                    dependencies["project"] = kept
        if changed:
            _write_text(manifest, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            report.files_rewritten += 1


def prune_missing_mcp(root: Path, report: AdaptReport) -> None:
    """Drop MCP servers whose launcher points into an absent skill directory."""
    mcp_path = root / ".cursor/mcp.json"
    if not mcp_path.is_file():
        return
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        report.warnings.append("mcp config is not valid JSON: .cursor/mcp.json")
        return
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return
    removed: list[str] = []
    for name, server in list(servers.items()):
        if not isinstance(server, dict):
            continue
        strings = [server.get("command")] + list(server.get("args") or [])
        broken = False
        for value in strings:
            if not isinstance(value, str) or ".agents/skills/" not in value:
                continue
            match = re.search(r"(\.agents/skills/[^\s\"']+)", value)
            if not match:
                continue
            relative = match.group(1).rstrip(",;")
            if not (root / relative).exists():
                broken = True
                break
        if broken:
            servers.pop(name, None)
            removed.append(name)
            rule = root / ".cursor/rules/mcp" / f"{name}.mdc"
            if rule.is_file():
                rule.unlink()
    if removed:
        _write_text(mcp_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        report.files_rewritten += 1
        report.disabled_servers.extend(f"removed:{name}" for name in removed)


def normalize_doc_links(root: Path, paths: list[str], report: AdaptReport) -> None:
    """Turn links to files absent from the kit into plain text with a note."""
    for relative in paths:
        if not relative.endswith(".md"):
            continue
        if relative.startswith((".doc/harnes/idea/", ".doc/harnes/astra_plan/",
                                ".doc/harnes/plan/", ".doc/harnes/audit/")):
            continue
        full = root / relative
        if not full.is_file():
            continue
        raw = full.read_text(encoding="utf-8", errors="surrogateescape")
        if raw.startswith("<!-- generated"):
            continue
        changes: list[dict] = []

        def _resolve(match):
            text, href = match.group(1), match.group(2)
            if re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#|/)", href):
                return match.group(0)
            if not re.search(r"\.(?:md|mdc)(?:#.*)?$", href):
                return match.group(0)
            candidate = (full.parent / href.split("#", 1)[0]).resolve()
            try:
                resolved = candidate.relative_to(root).as_posix()
            except ValueError:
                resolved = "<outside>"
            if candidate.is_file():
                return match.group(0)
            changes.append({"file": relative, "link": href, "resolved": resolved})
            return f"{text} (`{href}`; missing in kit)"

        output = []
        inside_fence = False
        for line in raw.splitlines(keepends=True):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                inside_fence = not inside_fence
                output.append(line)
                continue
            if inside_fence:
                output.append(line)
                continue
            parts = re.split(r"(`+[^`\n]*`+)", line)
            for index in range(0, len(parts), 2):
                parts[index] = LINK.sub(_resolve, parts[index])
            output.append("".join(parts))
        updated = "".join(output)
        if changes:
            report.doc_links.extend(changes)
        if updated != raw:
            _write_text(full, updated)
            report.files_rewritten += 1


def write_doc_link_report(root: Path, report: AdaptReport) -> None:
    path = root / ".doc/.rebase-doc-links.json"
    if not report.doc_links:
        if path.is_file():
            path.unlink()
        return
    _write_text(path, json.dumps(report.doc_links, indent=2, ensure_ascii=False) + "\n")
