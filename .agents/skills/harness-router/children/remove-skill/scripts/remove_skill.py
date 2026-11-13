#!/usr/bin/env python3
"""Remove a skill from the harness canon, mirrors and documentation.

The script creates a backup, removes generated copies from every view, updates
the documentation indexes and the component registry, rebuilds router tables
and runs the harness checks.

Usage:
  python3 remove_skill.py --root . --name my-skill --yes
  python3 remove_skill.py --root . --name my-skill --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TEXT_SUFFIXES = {".md", ".mdc", ".json", ".jsonc", ".yml", ".yaml", ".py", ".sh", ".ps1", ".mjs", ".js", ".txt"}
SEARCH_ROOTS = (
    ".agents/skills",
    ".cursor/rules",
    ".doc/harnes",
    ".doc/qa",
    "AGENTS.md",
    ".cursor/mcp.json",
    ".cursor/mcp.jsonc",
    ".agents/skills/harness-router/children/improvement/scripts/component_registry.json",
)
VIEW_ROOTS = (
    ("codex", ".codex/skills"),
    ("qoder", ".qoder/skills"),
    ("qwen", ".qwen/skills"),
    ("kilo", ".kilo/skills"),
)


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    env: str
    path: str

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "env": self.env, "path": self.path}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_skills(root: Path, relative_root: str, env: str) -> list[Target]:
    base = root / relative_root
    if not base.is_dir():
        return []
    result = []
    for skill_md in sorted(base.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        folder = skill_md.parent
        relative = folder.relative_to(base)
        ident = folder.name if relative == Path(".") else relative.as_posix()
        result.append(Target(
            id=ident,
            name=folder.name,
            env=env,
            path=folder.relative_to(root).as_posix(),
        ))
    return result


def find_targets(root: Path, query: str) -> list[Target]:
    canonical = find_skills(root, ".agents/skills", "agents")
    matches = [
        item for item in canonical
        if item.name == query or item.id == query or item.path == query
    ]
    if matches:
        return matches
    for env, relative_root in VIEW_ROOTS:
        for item in find_skills(root, relative_root, env):
            if item.name == query or item.id == query or item.path == query:
                matches.append(item)
    return matches


def backup_path(root: Path, item: Target) -> Path:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / ".doc/skil_data/harness-core/removed" / stamp / item.env / item.id


def backup_tree(root: Path, item: Target, dry_run: bool) -> Path | None:
    target = backup_path(root, item)
    if dry_run:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / item.path, target)
    return target


def reference_kind(path: str) -> str:
    if path.endswith("SKILL.md"):
        return "router"
    if path.startswith(".doc/harnes/skills/"):
        return "docs"
    if path.startswith(".doc/harnes/"):
        return "state"
    if path.endswith("component_registry.json"):
        return "registry"
    if "mcp" in path:
        return "mcp"
    if path.startswith(".cursor/rules/"):
        return "rule"
    return "other"


def collect_references(root: Path, target: Target, limit: int = 200) -> list[dict]:
    patterns = [re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(target.name) + r"(?![A-Za-z0-9_-])")]
    if target.id != target.name:
        patterns.append(re.compile(re.escape(target.id)))
    own = (root / target.path).resolve()
    references: list[dict] = []
    for relative in SEARCH_ROOTS:
        candidate = root / relative
        files = [candidate] if candidate.is_file() else sorted(candidate.rglob("*")) if candidate.is_dir() else []
        for path in files:
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            resolved = path.resolve()
            if own == resolved or own in resolved.parents:
                continue
            if ".doc/skil_data/harness-core/removed" in path.as_posix():
                continue
            try:
                lines = read_text(path).splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, 1):
                if any(pattern.search(line) for pattern in patterns):
                    references.append({
                        "path": path.relative_to(root).as_posix(),
                        "line": number,
                        "kind": reference_kind(path.relative_to(root).as_posix()),
                        "text": line.strip()[:240],
                    })
                    if len(references) >= limit:
                        return references
    return references


def collect_dependencies(root: Path, target: Target) -> list[dict]:
    result: list[dict] = []
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        return result
    for manifest in sorted(skills_root.rglob("skill.json")):
        if target.path in manifest.as_posix():
            continue
        try:
            data = json.loads(read_text(manifest))
        except (OSError, json.JSONDecodeError):
            continue
        dependencies = (data.get("dependencies") or {}).get("skills") or []
        for dependency in dependencies:
            if isinstance(dependency, dict) and dependency.get("name") == target.name:
                result.append({
                    "path": manifest.relative_to(root).as_posix(),
                    "line": 0,
                    "kind": "dependency",
                    "text": f"dependencies.skills: {target.name}",
                })
    return result


def remove_lines(path: Path, needles: list[str]) -> int:
    if not path.is_file():
        return 0
    lines = read_text(path).splitlines()
    kept = [line for line in lines if not any(needle in line for needle in needles)]
    if len(kept) == len(lines):
        return 0
    path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    return len(lines) - len(kept)


def remove_state_section_if_empty(path: Path) -> bool:
    if not path.is_file():
        return False
    text = read_text(path)
    marker = "## 5. Локальные скилы проекта"
    if marker not in text:
        return False
    start = text.index(marker)
    next_heading = text.find("\n## ", start + len(marker))
    end = next_heading + 1 if next_heading != -1 else len(text)
    section = text[start:end]
    rows = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith("| Скил ") and not line.startswith("|---")]
    if rows:
        return False
    text = text[:start].rstrip() + "\n\n" + text[end:].lstrip()
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def remove_registry_entry(root: Path, name: str, relative: str) -> bool:
    path = root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json"
    if not path.is_file():
        return False
    data = json.loads(read_text(path))
    components = data.get("components", {})
    changed = False
    if name in components:
        del components[name]
        changed = True
    for key in list(components):
        required = components[key].get("required_files", [])
        if any(relative + "/" in item for item in required):
            del components[key]
            changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return changed


def update_parent_router(root: Path, target: Target, dry_run: bool) -> bool:
    skill_dir = root / target.path
    if skill_dir.parent.name != "children":
        return False
    parent = skill_dir.parent.parent
    manifest = parent / "skill.json"
    if not manifest.is_file():
        return False
    data = json.loads(read_text(manifest))
    children = data.get("children", [])
    relative = "children/" + skill_dir.name
    if relative not in children:
        return False
    if not dry_run:
        data["children"] = [item for item in children if item != relative]
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True


def run_command(command: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--name", required=True, help="skill name or relative id")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing")
    parser.add_argument("--yes", action="store_true", help="apply without an interactive prompt")
    parser.add_argument("--force", action="store_true", help="remove even when the skill is used as a dependency")
    parser.add_argument("--no-backup", action="store_true", help="do not keep a backup")
    parser.add_argument("--no-sync", action="store_true", help="skip sync-agent-views.sh")
    parser.add_argument("--no-validate", action="store_true", help="skip validators")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    targets = find_targets(root, args.name)
    if not targets:
        print(f"skill not found: {args.name}", file=sys.stderr)
        return 2
    if len(targets) > 1:
        print(f"ambiguous skill {args.name}: {', '.join(item.id for item in targets)}", file=sys.stderr)
        return 2
    target = targets[0]
    dependencies = collect_dependencies(root, target)
    references = dependencies + collect_references(root, target)
    if dependencies and not args.force and not args.dry_run:
        print(
            "skill is used as dependency: "
            + ", ".join(item["path"] for item in dependencies)
            + "; update dependents or pass --force",
            file=sys.stderr,
        )
        return 1

    if not args.dry_run and not args.yes and sys.stdin.isatty():
        answer = input(f"Удалить скил {target.name} ({target.id})? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "д", "да"}:
            print("Отменено.")
            return 1
    elif not args.dry_run and not args.yes and not sys.stdin.isatty():
        print("Нужен --yes в неинтерактивном запуске.", file=sys.stderr)
        return 2

    removed: list[str] = []
    errors: list[str] = []
    backup = None
    if not args.no_backup:
        backup = backup_tree(root, target, args.dry_run)
        removed.append(f"backup:{backup.relative_to(root).as_posix()}")

    paths = [(target.env, root / target.path)]
    for env, relative_root in VIEW_ROOTS:
        if env == target.env:
            continue
        candidate = root / relative_root / target.id
        if candidate.is_dir():
            paths.append((env, candidate))
    for env, path in paths:
        if args.dry_run:
            removed.append(f"delete:{path.relative_to(root).as_posix()}")
            continue
        shutil.rmtree(path)
        removed.append(f"delete:{path.relative_to(root).as_posix()}")

    card = root / ".doc/harnes/skills" / f"{target.name}.md"
    if card.is_file() and not args.dry_run:
        card.unlink()
        removed.append(f"delete:{card.relative_to(root).as_posix()}")
    elif card.is_file():
        removed.append(f"delete:{card.relative_to(root).as_posix()}")

    index_files = [
        root / ".doc/harnes/skills/README.md",
        root / ".doc/harnes/index.md",
    ]
    for path in index_files:
        if args.dry_run:
            continue
        count = remove_lines(path, [
            f"[{target.name}.md](./{target.name}.md)",
            f"[{target.name}](./skills/{target.name}.md)",
        ])
        if count:
            removed.append(f"lines:{path.relative_to(root).as_posix()}:{count}")

    state = root / ".doc/harnes/state/02-skills.md"
    if not args.dry_run:
        count = remove_lines(state, [
            f"| {target.name} |",
            f"[{target.name}](../skills/{target.name}.md)",
        ])
        if count:
            removed.append(f"lines:{state.relative_to(root).as_posix()}:{count}")
        if remove_state_section_if_empty(state):
            removed.append(f"section:{state.relative_to(root).as_posix()}:5")

    if not args.dry_run:
        if remove_registry_entry(root, target.name, target.id):
            removed.append("registry")
        if update_parent_router(root, target, args.dry_run):
            code, output = run_command(
                ["python3", ".agents/skills/harness-router/children/harness-core/scripts/rebuild-routers.py", "--root", ".", "--write"],
                root,
            )
            if code != 0:
                errors.append("rebuild-routers failed: " + output[-500:])
            else:
                removed.append("parent-router")
    else:
        if update_parent_router(root, target, True):
            removed.append("parent-router")

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
        "skill": target.as_dict(),
        "removed": removed,
        "references": references,
        "unresolved": [
            item for item in references
            if item["kind"] in {"other", "rule", "mcp", "dependency"}
        ],
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Удаление {target.name}: {payload['status']}")
        for entry in removed:
            print(f"  {entry}")
        if references:
            print(f"  ссылки: {len(references)}")
            for item in references[:20]:
                print(f"    {item['kind']}: {item['path']}:{item['line']} {item['text']}")
            if len(references) > 20:
                print(f"    ... еще {len(references) - 20}")
        for error in errors:
            print(f"  ERROR {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
