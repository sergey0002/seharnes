#!/usr/bin/env python3
"""Install a local skill into the harness canon with documentation.

The script accepts a skill that already exists in the canon or in one of the
environment mirrors, validates its structure, creates missing README/skill.json,
adds the documentation card and registry entry, updates router metadata and
runs the sync and validators.

Usage:
  python3 add_skill.py --root . --name my-skill --yes
  python3 add_skill.py --root . --name my-skill --from codex --yes
  python3 add_skill.py --root . --all --yes
  python3 add_skill.py --root . --name my-skill --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import scan_local_skills as scanlib  # noqa: E402

ALLOWED_DIRS = {"scripts", "references", "assets", "tests", "children"}
SKIP_PARTS = {".git", "__pycache__", ".data", ".state", "node_modules", "vendor"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_RE = re.compile(
    r"(sgp_[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{12,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{16,})"
)
ABS_PATH_RE = re.compile(r"(?<![\w.])/(?:home|Users|var/www|mnt)/|[A-Za-z]:\\\\")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter_name(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    for line in text[3:end].splitlines():
        match = re.match(r"^name:\s*(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return ""


def frontmatter_description(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    for line in text[3:end].splitlines():
        match = re.match(r"^description:\s*(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("\"'")
    return ""


def text_files(path: Path) -> list[Path]:
    result = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if any(part in SKIP_PARTS or part.startswith(".") for part in relative.parts):
            continue
        if item.suffix.lower() in {".md", ".json", ".jsonc", ".py", ".sh", ".ps1", ".js", ".mjs", ".txt", ".yml", ".yaml"}:
            result.append(item)
    return result


def validate_skill(skill_dir: Path, allow_absolute_paths: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not skill_dir.is_dir():
        return ["папка скила не найдена"], warnings
    if not NAME_RE.match(skill_dir.name):
        errors.append(f"имя папки неверное: {skill_dir.name}")
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["нет SKILL.md"], warnings
    name = frontmatter_name(read_text(skill_md))
    if name != skill_dir.name:
        errors.append(f"frontmatter name={name!r} не совпадает с папкой {skill_dir.name!r}")
    for item in sorted(skill_dir.rglob("*")):
        if item.is_symlink():
            errors.append(f"симлинк запрещен: {item.relative_to(skill_dir).as_posix()}")
        if item.is_dir() and item.parent == skill_dir and item.name not in ALLOWED_DIRS:
            errors.append(f"посторонний каталог: {item.name}")
    for item in text_files(skill_dir):
        text = read_text(item)
        if SECRET_RE.search(text):
            errors.append(f"похоже на секрет: {item.relative_to(skill_dir).as_posix()}")
        if ABS_PATH_RE.search(text) and not allow_absolute_paths:
            warnings.append(f"абсолютный путь: {item.relative_to(skill_dir).as_posix()}")
    manifest = skill_dir / "skill.json"
    if manifest.is_file():
        try:
            data = json.loads(read_text(manifest))
        except json.JSONDecodeError as error:
            errors.append(f"skill.json невалиден: {error}")
        else:
            if data.get("name") != skill_dir.name:
                errors.append("skill.json name не совпадает с папкой")
            if data.get("schema") != 1:
                errors.append("skill.json schema должен быть 1")
    return errors, warnings


def ensure_readme(skill_dir: Path) -> bool:
    readme = skill_dir / "README.md"
    if readme.is_file():
        return False
    text = read_text(skill_dir / "SKILL.md")
    description = frontmatter_description(text) or ""
    purpose = description or "Заполнить: назначение скила в 2-4 предложениях."
    content = (
        f"# {skill_dir.name}\n\n"
        f"{purpose}\n\n"
        "Заполнить: как работает, 3-6 предложений без флагов и команд.\n"
    )
    readme.write_text(content, encoding="utf-8", newline="\n")
    return True


def resource_list(skill_dir: Path, name: str) -> list[str]:
    folder = skill_dir / name
    if not folder.is_dir():
        return []
    return sorted(
        item.relative_to(skill_dir).as_posix()
        for item in folder.rglob("*")
        if item.is_file() and not any(part in SKIP_PARTS or part.startswith(".") for part in item.relative_to(skill_dir).parts)
    )


def ensure_manifest(skill_dir: Path) -> bool:
    manifest = skill_dir / "skill.json"
    if manifest.is_file():
        return False
    children = []
    children_root = skill_dir / "children"
    if children_root.is_dir():
        children = sorted(
            "children/" + item.name
            for item in children_root.iterdir()
            if item.is_dir() and (item / "SKILL.md").is_file()
        )
    payload = {
        "schema": 1,
        "name": skill_dir.name,
        "kind": "leaf",
        "entry": "SKILL.md",
        "readme": "README.md",
        "resources": {
            "scripts": resource_list(skill_dir, "scripts"),
            "references": resource_list(skill_dir, "references"),
            "assets": resource_list(skill_dir, "assets"),
        },
        "tests": resource_list(skill_dir, "tests"),
        "children": children,
        "dependencies": {"skills": [], "project": []},
        "generated": [],
    }
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def update_state(root: Path, name: str, skill_dir: Path) -> bool:
    path = root / ".doc" / "harnes" / "state" / "02-skills.md"
    if not path.is_file():
        return False
    text = read_text(path)
    relative = skill_dir.relative_to(root / ".agents" / "skills").as_posix()
    row = f"| {name} | [{name}](../../../.agents/skills/{relative}/README.md) | `../../../.agents/skills/{relative}/SKILL.md` |"
    marker = "## 5. Локальные скилы проекта"
    if marker not in text:
        section = (
            f"{marker}\n\n"
            "| Скил | Карточка | Канон |\n"
            "|---|---|---|\n"
            f"{row}\n\n"
            "---\n\n"
        )
        anchor = "## Реестр и валидаторы"
        if anchor in text:
            text = text.replace(anchor, section + anchor, 1)
        else:
            text = text.rstrip() + "\n\n" + section
    elif row not in text:
        start = text.index(marker)
        separator = text.find("|---|---|---|", start)
        if separator == -1:
            text = text[:start] + marker + "\n\n" + row + "\n" + text[start + len(marker):]
        else:
            insert_at = text.find("\n", separator) + 1
            text = text[:insert_at] + row + "\n" + text[insert_at:]
    else:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def update_index(root: Path, name: str, skill_dir: Path) -> bool:
    path = root / ".doc" / "harnes" / "index.md"
    if not path.is_file():
        return False
    relative = skill_dir.relative_to(root).as_posix()
    text = read_text(path)
    link = f"[{name}](../../{relative}/README.md)"
    if link in text:
        return False
    row = f"| Локальные скилы проекта | {link} |\n"
    marker = "### Группировка менеджеров"
    if marker in text:
        text = text.replace(marker, row + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n" + row
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def update_registry(root: Path, name: str, skill_dir: Path) -> bool:
    path = root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json"
    if not path.is_file():
        return False
    data = json.loads(read_text(path))
    components = data.setdefault("components", {})
    if name in components:
        return False
    relative = skill_dir.relative_to(root).as_posix()
    components[name] = {
        "required_files": [
            f"{relative}/SKILL.md",
            f"{relative}/README.md",
            f"{relative}/skill.json",
        ],
        "config_paths": [],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def update_parent_router(root: Path, skill_dir: Path) -> bool:
    if skill_dir.parent.name != "children":
        return False
    parent = skill_dir.parent.parent
    parent_manifest = parent / "skill.json"
    if not parent_manifest.is_file():
        return False
    data = json.loads(read_text(parent_manifest))
    relative = "children/" + skill_dir.name
    children = data.setdefault("children", [])
    if relative in children:
        return False
    children.append(relative)
    children.sort()
    parent_manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def run_command(command: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)


def backup_tree(source: Path, root: Path, name: str) -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / ".doc/skil_data/harness-core/install-backup" / stamp / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


def copy_skill(source: Path, target: Path, force: bool, root: Path) -> Path | None:
    if target.exists():
        if not force:
            raise RuntimeError(f"канон уже содержит {target.relative_to(root).as_posix()}; используйте --force")
        backup = backup_tree(target, root, target.name)
        shutil.rmtree(target)
    else:
        backup = None
    shutil.copytree(source, target)
    return backup


def choose_source(item: dict, from_env: str) -> Path:
    sources = item.get("sources") or []
    if from_env:
        for source in sources:
            if source["env"] == from_env:
                return Path(source["path"])
        raise RuntimeError(f"у скила {item['id']} нет источника {from_env}")
    if not sources:
        raise RuntimeError(f"у скила {item['id']} нет источника")
    return Path(sources[0]["path"])


def install_one(root: Path, item: dict, from_env: str, force: bool, dry_run: bool,
                allow_absolute_paths: bool) -> dict:
    action = {"id": item["id"], "name": item["name"], "kind": item.get("kind", ""), "actions": [], "warnings": []}
    if "sources" in item:
        source = root / choose_source(item, from_env)
    else:
        source = Path(item["path"])
        if not source.is_absolute():
            source = root / source
    target = root / ".agents" / "skills" / item["id"]
    action["source"] = str(source)
    action["target"] = str(target.relative_to(root))

    errors, warnings = validate_skill(source, allow_absolute_paths)
    action["warnings"].extend(warnings)
    if errors:
        action["errors"] = errors
        return action
    if not NAME_RE.match(target.name):
        action["errors"] = [f"недопустимое имя папки: {target.name}"]
        return action
    if dry_run:
        action["actions"].append("validate")
        action["actions"].append("copy" if source.resolve() != target.resolve() else "use-canon")
        action["actions"].append("docs")
        return action

    backup = None
    if source.resolve() != target.resolve():
        try:
            backup = copy_skill(source, target, force, root)
        except RuntimeError as error:
            action["errors"] = [str(error)]
            return action
        action["actions"].append("copy")
        if backup:
            action["backup"] = str(backup.relative_to(root))
    else:
        action["actions"].append("use-canon")

    if ensure_readme(target):
        action["actions"].append("readme")
    if ensure_manifest(target):
        action["actions"].append("skill.json")

    if update_state(root, target.name, target):
        action["actions"].append("state")
    if update_index(root, target.name, target):
        action["actions"].append("index")
    if update_registry(root, target.name, target):
        action["actions"].append("registry")
    if update_parent_router(root, target):
        action["actions"].append("parent-router")
    return action


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--name", action="append", default=[], help="skill name or relative id; repeatable")
    parser.add_argument("--all", action="store_true", help="install all unambiguous local skills")
    parser.add_argument("--from", dest="from_env", default="", choices=["codex", "qoder", "qwen", "kilo", "agents"],
                        help="source environment for a view-local or conflicting skill")
    parser.add_argument("--force", action="store_true", help="replace an existing canon skill")
    parser.add_argument("--allow-absolute-paths", action="store_true", help="keep absolute paths instead of warning")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing")
    parser.add_argument("--yes", action="store_true", help="apply without an interactive prompt")
    parser.add_argument("--no-sync", action="store_true", help="skip sync-agent-views.sh")
    parser.add_argument("--no-validate", action="store_true", help="skip validators")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / ".agents" / "skills").is_dir():
        print(f"skills root not found: {root / '.agents' / 'skills'}", file=sys.stderr)
        return 2

    report = scanlib.scan(root, root / scanlib.DEFAULT_BASELINE)
    selected: list[dict] = []
    by_id = {item["id"]: item for item in report["skills"]["canon_local"]}
    by_id.update({item["id"]: item for item in report["skills"]["view_local"]})
    for item in report["skills"]["conflict"]:
        by_id[item["id"]] = item
    name_index: dict[str, list[dict]] = {}
    for item in by_id.values():
        name_index.setdefault(item["name"], []).append(item)

    if args.all:
        for item in report["skills"]["canon_local"] + report["skills"]["view_local"]:
            selected.append(item)
        for item in report["skills"]["conflict"]:
            if args.from_env:
                selected.append(item)
    for name in args.name:
        matches = name_index.get(name) or [item for item in by_id.values() if item["id"] == name]
        if not matches:
            print(f"skill not found outside the package: {name}", file=sys.stderr)
            return 2
        if len(matches) > 1 and not args.from_env:
            print(f"ambiguous skill {name}: {', '.join(item['id'] for item in matches)}", file=sys.stderr)
            return 2
        selected.append(matches[0])

    if not selected:
        print(json.dumps({"status": "ok", "installed": 0, "message": "no skills selected"}, ensure_ascii=False)
              if args.json else "Нет скилов для установки.")
        return 0

    if not args.dry_run and not args.yes and sys.stdin.isatty():
        names = ", ".join(item["name"] for item in selected)
        answer = input(f"Установить в канон: {names}? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "д", "да"}:
            print("Отменено.")
            return 1
    elif not args.dry_run and not args.yes and not sys.stdin.isatty():
        print("Нужен --yes в неинтерактивном запуске.", file=sys.stderr)
        return 2

    actions = []
    errors = []
    for item in selected:
        if "sources" not in item and "kind" not in item:
            item = dict(item)
        if "sources" in item:
            item = dict(item)
            item.setdefault("kind", "view-local" if item.get("sources") else "canon-local")
        result = install_one(root, item, args.from_env, args.force, args.dry_run, args.allow_absolute_paths)
        actions.append(result)
        errors.extend(result.get("errors", []))

    if errors:
        payload = {"status": "failed", "actions": actions, "errors": errors}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    next_steps = []
    if any("parent-router" in action["actions"] for action in actions):
        next_steps.append("проверить карточку родительского скила и его README")
    if any("parent-router" in action["actions"] for action in actions) and not args.dry_run:
        code, output = run_command(
            ["python3", ".agents/skills/harness-router/children/harness-core/scripts/rebuild-routers.py", "--root", ".", "--write"],
            root,
        )
        if code != 0:
            errors.append("rebuild-routers failed: " + output[-500:])
    if not args.no_sync and not args.dry_run:
        code, output = run_command(
            ["bash", ".agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh"],
            root,
        )
        if code != 0:
            errors.append("sync failed: " + output[-500:])
    if not args.no_validate and not errors and not args.dry_run:
        commands = [
            ["python3", ".agents/skills/harness-router/children/improvement/scripts/validate_skills.py"],
            ["python3", ".agents/skills/harness-router/children/improvement/scripts/validate_registry.py"],
            ["python3", ".agents/skills/harness-router/children/harness-core/scripts/rebuild-routers.py", "--root", ".", "--check"],
        ]
        for command in commands:
            code, output = run_command(command, root)
            if code != 0:
                errors.append(" ".join(command) + ": " + output[-300:])
    payload = {
        "status": "failed" if errors else ("dry-run" if args.dry_run else "ok"),
        "installed": 0 if args.dry_run else len(actions),
        "actions": actions,
        "next_steps": next_steps,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Установка: {payload['status']}, скилов: {payload['installed']}")
        for action in actions:
            print(f"  {action.get('name', action.get('id'))}: {', '.join(action['actions'])}")
            for warning in action.get("warnings", []):
                print(f"    WARN {warning}")
            for error in action.get("errors", []):
                print(f"    ERROR {error}")
        for step in next_steps:
            print(f"  далее: {step}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
