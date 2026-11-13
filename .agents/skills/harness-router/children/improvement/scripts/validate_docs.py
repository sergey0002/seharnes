#!/usr/bin/env python3
"""Validate harness component documentation coverage.

Checks:
- every skill has README.md
- every MCP server in .cursor/mcp.json has a valid document
- script documents contain required headings
- active harness docs under .doc/harnes have no broken local links (D07)

Usage:
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py --warn-only
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness-core/scripts"))

EXTS = {".py", ".ps1", ".sh", ".js", ".mjs", ".php", ".cmd"}
SKIP = {"__pycache__", "node_modules", "vendor", ".git", ".data", ".state", ".venv", "venv", "cache", "out"}
REQUIRED_SCRIPT = ["## Суть", "## Аргументы", "## Коды выхода", "## История изменений"]
REQUIRED_MCP = ["## Суть", "## Когда вызывать", "## Конфигурация", "## Текущие значения", "## Несколько проектов"]


def policy_requirements(root: Path) -> tuple[list[str], list[str]]:
    try:
        from canon_paths import PolicyError, load_preliminary_policy_bundle
        bundle = load_preliminary_policy_bundle(root)
        rule = bundle["policies"]["component_docs"]["rules"].get("CD02", {})
        sections = rule.get("required_sections") if rule.get("enabled") else None
        if isinstance(sections, list) and sections:
            return sections, REQUIRED_MCP
    except Exception:
        pass
    return REQUIRED_SCRIPT, REQUIRED_MCP
HISTORICAL_DIRS = {"archive", "idea", "astra_plan", "plan", "audit", "hermes", "openhands"}
SKIP_STATUS = {"deprecated", "frozen"}

ALIASES = {
    "jira-task": "jira",
}


def headings(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {f"## {h}" for h in re.findall(r"^##\s+(.+)$", text, re.M)}


def skill_map(skills_root: Path) -> dict[str, Path]:
    found = {}
    if not skills_root.exists():
        return found
    for skill_md in skills_root.rglob("SKILL.md"):
        if any(part in SKIP for part in skill_md.parts):
            continue
        found[skill_md.parent.name] = skill_md.parent
    return found


def resolve_mcp_skill(server: str, skills: dict[str, Path]) -> Path | None:
    return skills.get(server) or skills.get(ALIASES.get(server, ""))


def doc_status(path: Path) -> str:
    head = path.read_text(encoding="utf-8", errors="ignore")[:800]
    match = re.search(r"^status:\s*(\S+)", head, re.M)
    return match.group(1) if match else ""


def load_link_checker(root: Path):
    checker = root / ".agents/skills/documentation-router/children/project-doc/scripts/check-links.py"
    if not checker.is_file():
        return None
    spec = importlib.util.spec_from_file_location("harness_check_links", checker)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness_link_errors(root: Path, warnings: list[dict]) -> list[dict]:
    checker = load_link_checker(root)
    harness = root / ".doc/harnes"
    if checker is None:
        warnings.append({"code": "D07", "path": ".doc/harnes", "message": "check-links.py не найден, проверка ссылок пропущена"})
        return []
    if not harness.is_dir():
        return []

    errors = []
    for path in sorted(harness.rglob("*.md")):
        rel = path.relative_to(harness)
        if set(rel.parts[:-1]) & HISTORICAL_DIRS:
            continue
        if doc_status(path) in SKIP_STATUS:
            continue
        broken = checker.check_file(path)
        if not broken:
            continue
        shown = ", ".join(broken[:5])
        suffix = "" if len(broken) <= 5 else f" и ещё {len(broken) - 5}"
        errors.append({
            "code": "D07",
            "path": str(path.relative_to(root)),
            "message": f"битых ссылок: {len(broken)}: {shown}{suffix}",
        })
    return errors


def collect(root: Path) -> tuple[list[dict], list[dict]]:
    skills_root = root / ".agents/skills"
    legacy_mcp = root / ".doc/harnes/mcp"
    archive_mcp = root / ".doc/harnes/archive/mcp"
    mcp_config = root / ".cursor/mcp.json"
    required_script, required_mcp = policy_requirements(root)

    errors = []
    warnings = []

    # 1. Skills
    skills = skill_map(skills_root)
    for name, skill_path in sorted(skills.items()):
        readme = skill_path / "README.md"
        if not readme.is_file():
            errors.append({"code": "D03", "path": str(skill_path.relative_to(root)), "message": "нет README.md"})

    # 2. MCP Servers
    if mcp_config.is_file():
        try:
            mcp_data = json.loads(mcp_config.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append({"code": "D05", "path": str(mcp_config.relative_to(root)), "message": f"ошибка чтения mcp.json: {e}"})
            mcp_data = {}

        for server, cfg in sorted((mcp_data.get("mcpServers") or {}).items()):
            skill = resolve_mcp_skill(server, skills)
            target = skill / "docs/mcp" / f"{server}.md" if skill else None
            legacy = legacy_mcp / f"{server}.md"
            archived = archive_mcp / f"{server}.md"
            is_disabled = bool(cfg.get("disabled"))

            doc: Path | None = None
            if target and target.is_file():
                doc = target
            elif legacy.is_file():
                warnings.append({"code": "D05", "path": str(legacy.relative_to(root)), "message": f"документ MCP в legacy расположении: {server}"})
                doc = legacy
            elif archived.is_file():
                doc = archived
            elif is_disabled:
                warnings.append({"code": "D05", "path": str(legacy.relative_to(root)), "message": f"отключенный MCP без legacy-документа: {server}"})
            else:
                expected_path = target.relative_to(root) if target else f".agents/skills/{server}/docs/mcp/{server}.md"
                errors.append({"code": "D05", "path": str(expected_path), "message": f"нет документа MCP для {server}"})

            if doc and doc.is_file():
                missing = [h for h in required_mcp if h not in headings(doc)]
                if missing:
                    warnings.append({"code": "D06", "path": str(doc.relative_to(root)), "message": "нет разделов: " + ", ".join(missing)})

    # 3. Existing Script documents validation
    for doc in sorted(root.glob(".agents/skills/**/docs/scripts/*.md")):
        if any(part in SKIP for part in doc.parts):
            continue
        missing = [h for h in required_script if h not in headings(doc)]
        if missing:
            warnings.append({"code": "D02", "path": str(doc.relative_to(root)), "message": "нет разделов: " + ", ".join(missing)})

    # 4. Local links in active harness docs
    errors.extend(harness_link_errors(root, warnings))

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate component docs")
    parser.add_argument("--root", default=".")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors, warnings = collect(root)

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "status": "failed" if errors else "passed"}, ensure_ascii=False, indent=2))
    else:
        for item in errors:
            print(f"ERROR {item['code']} {item['path']}: {item['message']}")
        for item in warnings:
            print(f"WARN  {item['code']} {item['path']}: {item['message']}")
        print(f"errors: {len(errors)}, warnings: {len(warnings)}")

    if errors and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
