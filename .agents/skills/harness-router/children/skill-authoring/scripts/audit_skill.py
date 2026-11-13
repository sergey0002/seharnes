#!/usr/bin/env python3
"""Audit one or all harness skills against the project rules.

Checks structure, frontmatter, README, skill.json, scripts, tests, docs,
indexes, registry, parent router and dependencies.

Usage:
  python3 audit_skill.py --root . --name my-skill
  python3 audit_skill.py --root . --all
  python3 audit_skill.py --root . --name my-skill --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_DIRS = {"scripts", "references", "assets", "tests", "children", "docs"}
ALLOWED_FRONTMATTER = {
    "name", "description", "license", "compatibility", "metadata", "allowed-tools", "argument-hint",
}
SCRIPT_EXTS = {".py", ".ps1", ".sh", ".js", ".mjs", ".php", ".cmd"}
SECRET_RE = re.compile(
    r"(sgp_[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{12,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{16,})"
)
ABS_PATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|var/www|mnt)/|[A-Za-z]:\\\\")
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    data: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip().strip("\"'")
    return data


def find_skills(root: Path) -> list[Path]:
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(path.parent for path in skills_root.rglob("SKILL.md") if path.is_file())


def relative_id(root: Path, skill_dir: Path) -> str:
    return skill_dir.relative_to(root / ".agents" / "skills").as_posix()


def add(errors: list[str], warnings: list[str], message: str, severity: str = "error") -> None:
    if severity == "error":
        errors.append(message)
    else:
        warnings.append(message)


def check_manifest(root: Path, skill_dir: Path, errors: list[str], warnings: list[str]) -> dict:
    path = skill_dir / "skill.json"
    if not path.is_file():
        add(errors, warnings, "нет skill.json")
        return {}
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as error:
        add(errors, warnings, f"skill.json невалиден: {error}")
        return {}
    if data.get("schema") != 1:
        add(errors, warnings, "skill.json schema должен быть 1")
    if data.get("name") != skill_dir.name:
        add(errors, warnings, "skill.json name не совпадает с папкой")
    if data.get("entry") != "SKILL.md":
        add(errors, warnings, "skill.json entry должен быть SKILL.md")
    if data.get("readme") != "README.md":
        add(errors, warnings, "skill.json readme должен быть README.md")
    resources = data.get("resources")
    if not isinstance(resources, dict) or set(resources) != {"scripts", "references", "assets"}:
        add(errors, warnings, "skill.json resources должен содержать scripts/references/assets")
        return data
    declared_scripts = set()
    for key in ("scripts", "references", "assets"):
        values = resources.get(key)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            add(errors, warnings, f"resources.{key} должен быть массивом строк")
            continue
        if values != sorted(values):
            add(errors, warnings, f"resources.{key} не отсортирован", severity="warning")
        for relative in values:
            target = skill_dir / relative
            if not target.exists():
                add(errors, warnings, f"resources.{key}: путь не существует: {relative}")
            if key == "scripts" and target.suffix.lower() in SCRIPT_EXTS:
                declared_scripts.add(relative)
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for item in sorted(scripts_dir.rglob("*")):
            if item.is_file() and item.suffix.lower() in SCRIPT_EXTS:
                relative = item.relative_to(skill_dir).as_posix()
                if relative not in declared_scripts:
                    add(errors, warnings, f"скрипт не объявлен в skill.json: {relative}")
    for relative in data.get("tests") or []:
        target = skill_dir / relative
        if not target.exists():
            add(errors, warnings, f"тест не существует: {relative}")
    for relative in data.get("children") or []:
        target = skill_dir / relative
        if not (target / "SKILL.md").is_file():
            add(errors, warnings, f"ребенок без SKILL.md: {relative}")
    dependencies = (data.get("dependencies") or {}).get("skills") or []
    skills_root = root / ".agents" / "skills"
    for dependency in dependencies:
        name = dependency.get("name") if isinstance(dependency, dict) else ""
        if name and not any(path.parent.name == name for path in skills_root.rglob("SKILL.md")):
            add(errors, warnings, f"неизвестная зависимость: {name}")
    return data


def check_body(skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    skill_md = skill_dir / "SKILL.md"
    text = read_text(skill_md)
    front = frontmatter(text)
    if front is None:
        add(errors, warnings, "нет frontmatter")
        return
    for key in front:
        if key not in ALLOWED_FRONTMATTER:
            add(errors, warnings, f"запрещенное поле frontmatter: {key}")
    if front.get("name") != skill_dir.name:
        add(errors, warnings, "frontmatter name не совпадает с папкой")
    description = front.get("description", "")
    if not description:
        add(errors, warnings, "пустой description")
    readme = skill_dir / "README.md"
    if not readme.is_file():
        add(errors, warnings, "нет README.md")
    else:
        readme_text = read_text(readme)
        for token in ("](", "http://", "https://", "[["):
            if token in readme_text:
                add(errors, warnings, f"README содержит запрещенную ссылку: {token}")
    for item in skill_dir.rglob("*"):
        if item.is_symlink():
            add(errors, warnings, f"симлинк запрещен: {item.relative_to(skill_dir).as_posix()}")
        if item.is_dir() and item.parent == skill_dir and item.name not in ALLOWED_DIRS:
            add(errors, warnings, f"посторонний каталог: {item.name}")
        if item.suffix.lower() == ".mdc":
            add(errors, warnings, f"mdc внутри скила: {item.relative_to(skill_dir).as_posix()}")
        if item.name.startswith("test_") and item.suffix == ".py" and "tests" not in item.parts:
            add(errors, warnings, f"тест вне tests/: {item.relative_to(skill_dir).as_posix()}")


def check_text_safety(skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    for item in sorted(skill_dir.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in {".md", ".json", ".py", ".sh", ".ps1", ".js", ".mjs", ".txt"}:
            continue
        text = read_text(item)
        if SECRET_RE.search(text):
            add(errors, warnings, f"похоже на секрет: {item.relative_to(skill_dir).as_posix()}")
        if ABS_PATH_RE.search(text):
            add(errors, warnings, f"абсолютный путь: {item.relative_to(skill_dir).as_posix()}", severity="warning")


def check_links(skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    skill_md = skill_dir / "SKILL.md"
    for match in LINK_RE.finditer(read_text(skill_md)):
        link = match.group(1).split("#", 1)[0]
        if not link or link.startswith(("http://", "https://", "mailto:")):
            continue
        target = (skill_dir / link).resolve()
        if not target.exists():
            add(errors, warnings, f"битая ссылка в SKILL.md: {link}", severity="warning")


def check_docs(root: Path, skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    name = skill_dir.name
    readme = skill_dir / "README.md"
    if not readme.is_file():
        add(errors, warnings, f"нет README.md: {relative_id(root, skill_dir)}/README.md")
    else:
        text = read_text(readme)
        if re.search(r"\[[^\]]+\]\([^)]+\)", text) or re.search(r"https?://", text):
            add(errors, warnings, f"README содержит ссылки: {name}", severity="warning")
        if "## Связи" in text:
            add(errors, warnings, f"README содержит раздел Связи: {name}", severity="warning")
        if "Заполнить:" in text or "Описание уточняется" in text:
            add(errors, warnings, f"README не заполнен: {name}", severity="warning")
    index = root / ".doc/harnes/index.md"
    if index.is_file() and f"[{name}]" not in read_text(index):
        add(errors, warnings, f"нет строки в harnes/index.md: {name}", severity="warning")


def check_registry(root: Path, skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    path = root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json"
    if not path.is_file():
        return
    data = json.loads(read_text(path))
    entry = (data.get("components") or {}).get(skill_dir.name)
    if entry is None:
        add(errors, warnings, f"нет записи в component_registry.json: {skill_dir.name}", severity="warning")
        return
    for relative in entry.get("required_files") or []:
        if not (root / relative).exists():
            add(errors, warnings, f"registry: файл не существует: {relative}")


def check_router(root: Path, skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    ident = relative_id(root, skill_dir)
    if "/children/" not in ident:
        return
    parent_id, _, _ = ident.rpartition("/children/")
    parent = root / ".agents" / "skills" / parent_id
    manifest = parent / "skill.json"
    if not manifest.is_file():
        add(errors, warnings, f"нет родительского skill.json: {parent_id}")
        return
    data = json.loads(read_text(manifest))
    relative = "children/" + skill_dir.name
    if relative not in (data.get("children") or []):
        add(errors, warnings, f"родитель не содержит {relative}")
    parent_skill = parent / "SKILL.md"
    if parent_skill.is_file() and f"`{skill_dir.name}`" not in read_text(parent_skill):
        add(errors, warnings, f"нет строки роутера для {skill_dir.name}", severity="warning")


def audit_skill(root: Path, skill_dir: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    check_body(skill_dir, errors, warnings)
    check_manifest(root, skill_dir, errors, warnings)
    check_text_safety(skill_dir, errors, warnings)
    check_links(skill_dir, errors, warnings)
    check_docs(root, skill_dir, errors, warnings)
    check_registry(root, skill_dir, errors, warnings)
    check_router(root, skill_dir, errors, warnings)
    score = max(0, 100 - 15 * len(errors) - 5 * len(warnings))
    return {
        "id": relative_id(root, skill_dir),
        "name": skill_dir.name,
        "path": skill_dir.relative_to(root).as_posix(),
        "score": score,
        "status": "failed" if errors else ("warning" if warnings else "passed"),
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--name", action="append", default=[], help="skill name or relative id; repeatable")
    parser.add_argument("--all", action="store_true", help="audit all skills")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failure")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    skills = find_skills(root)
    if not skills:
        print("no skills found", file=sys.stderr)
        return 2
    if args.name:
        selected = []
        for query in args.name:
            matches = [item for item in skills if item.name == query or relative_id(root, item) == query]
            if not matches:
                print(f"skill not found: {query}", file=sys.stderr)
                return 2
            selected.extend(matches)
        skills = sorted(set(selected))
    elif not args.all:
        print("pass --name or --all", file=sys.stderr)
        return 2

    reports = [audit_skill(root, skill) for skill in skills]
    errors = sum(len(report["errors"]) for report in reports)
    warnings = sum(len(report["warnings"]) for report in reports)
    failed = [report for report in reports if report["errors"]]
    payload = {
        "status": "failed" if failed else ("warning" if warnings else "passed"),
        "checked": len(reports),
        "errors": errors,
        "warnings": warnings,
        "skills": reports,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Аудит скилов: {payload['status']}, проверено {len(reports)}, ошибок {errors}, предупреждений {warnings}")
        for report in reports:
            print(f"  {report['id']}: {report['status']}, score {report['score']}")
            for error in report["errors"]:
                print(f"    ERROR {error}")
            for warning in report["warnings"][:5]:
                print(f"    WARN {warning}")
            if len(report["warnings"]) > 5:
                print(f"    ... еще {len(report['warnings']) - 5}")
    return 1 if failed or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
