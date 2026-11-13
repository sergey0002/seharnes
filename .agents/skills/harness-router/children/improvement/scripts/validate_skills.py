#!/usr/bin/env python3
"""Validate harness skills against skill-format.md.

Usage:
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py --warn-only
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ALLOWED_DIRS = {"scripts", "docs", "references", "assets", "tests", "children"}
FORBIDDEN_DIRS = {".data", "templates", "agents"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "argument-hint",
}
REQUIRED_MANIFEST = {
    "schema",
    "name",
    "kind",
    "entry",
    "readme",
    "resources",
    "tests",
    "children",
    "dependencies",
    "generated",
}
ALLOWED_MANIFEST = REQUIRED_MANIFEST
RESOURCE_KEYS = {"scripts", "references", "assets"}
SCRIPT_EXTS = {".py", ".ps1", ".sh", ".js", ".mjs", ".php", ".cmd"}


def frontmatter(text: str):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    data = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in (">", "|", ">-", "|-"):
            parts = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt and not nxt.startswith((" ", "\t")):
                    break
                parts.append(nxt.strip())
                i += 1
            data[key] = " ".join(p for p in parts if p)
            continue
        data[key] = value.strip('"\'')
        i += 1
    return data


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def find_project_root(skills_root: Path) -> Path:
    """Resolve the repository root regardless of the --skills-root depth."""
    for candidate in (skills_root, *skills_root.parents):
        if (candidate / ".git").exists():
            return candidate
        if (candidate / ".agents").is_dir() and (candidate / ".cursor").is_dir():
            return candidate
    return skills_root.parent.parent


class Checker:
    def __init__(self, skills_root: Path, policy=None):
        self.root = skills_root
        self.project_root = find_project_root(skills_root)
        self.allowed_dirs = ALLOWED_DIRS
        self.forbidden_dirs = FORBIDDEN_DIRS
        self.allowed_frontmatter = ALLOWED_FRONTMATTER
        if policy is not None:
            rule = policy['SF02']
            if rule['name_pattern'] != NAME_RE.pattern or set(policy['SF03']['resource_keys']) != RESOURCE_KEYS:
                raise ValueError('policy may not change the trusted name or resource schema')
            # Policy can tighten, but not relax, the installed trusted rules.
            self.allowed_dirs = ALLOWED_DIRS & set(rule['allowed_directories'])
            self.forbidden_dirs = FORBIDDEN_DIRS | set(rule['forbidden_directories'])
            self.allowed_frontmatter = ALLOWED_FRONTMATTER & set(rule['allowed_frontmatter'])
        self.errors = []
        self.warnings = []
        self.skill_names = {
            p.parent.name for p in skills_root.rglob("SKILL.md") if p.is_file()
        }

    def error(self, code, path, message):
        self.errors.append({"code": code, "path": str(path), "message": message})

    def warn(self, code, path, message):
        self.warnings.append({"code": code, "path": str(path), "message": message})

    def check_readme(self, skill: Path):
        readme = skill / "README.md"
        if not readme.is_file():
            self.error("V02", readme, "нет README.md")
            return
        text = readme.read_text(encoding="utf-8", errors="ignore")
        for token in ("](", "http://", "https://", "[["):
            if token in text:
                self.error("V08", readme, f"README содержит запрещенную ссылку: {token}")
        if re.search(r"^##\s+Связи", text, re.M):
            self.error("V08", readme, "README содержит раздел Связи")

    def check_skill_md(self, skill: Path):
        path = skill / "SKILL.md"
        if not path.is_file():
            self.error("V01", path, "нет SKILL.md")
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        fm = frontmatter(text)
        if not fm:
            self.error("V05", path, "нет frontmatter")
            return
        for key in fm:
            if key not in self.allowed_frontmatter:
                self.error("V05", path, f"поле frontmatter запрещено: {key}")
        name = fm.get("name", "")
        if name != skill.name:
            self.error("V04", path, f"name={name!r} не совпадает с папкой {skill.name!r}")
        if not NAME_RE.match(name or ""):
            self.error("V04", path, f"name не соответствует шаблону: {name!r}")
        desc = fm.get("description", "")
        if not desc:
            self.error("V06", path, "пустой description")

    def check_manifest(self, skill: Path):
        path = skill / "skill.json"
        if not path.is_file():
            self.error("V03", path, "нет skill.json")
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error("V03", path, f"невалидный JSON: {exc}")
            return None
        missing = REQUIRED_MANIFEST - set(data)
        extra = set(data) - ALLOWED_MANIFEST
        if missing:
            self.error("V03", path, f"нет ключей: {', '.join(sorted(missing))}")
        if extra:
            self.error("V03", path, f"лишние ключи: {', '.join(sorted(extra))}")
        if data.get("schema") != 1:
            self.error("V03", path, "schema должен быть 1")
        if data.get("name") != skill.name:
            self.error("V04", path, "name манифеста не совпадает с папкой")
        if data.get("entry") != "SKILL.md":
            self.error("V03", path, "entry должен быть SKILL.md")
        if data.get("readme") != "README.md":
            self.error("V03", path, "readme должен быть README.md")
        resources = data.get("resources")
        if not isinstance(resources, dict) or set(resources) != RESOURCE_KEYS:
            self.error("V03", path, "resources должен содержать scripts/references/assets")
            return data
        declared_scripts = set()
        for key in RESOURCE_KEYS:
            values = resources.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                self.error("V03", path, f"resources.{key} должен быть массивом строк")
                continue
            if values != sorted(values):
                self.warn("W02", path, f"resources.{key} не отсортирован")
            for rel in values:
                target = (skill / rel)
                if not inside(skill, target):
                    self.error("V10", path, f"путь выходит за папку скила: {rel}")
                    continue
                if not target.exists():
                    self.error("V09", path, f"путь не существует: {rel}")
                if key == "scripts" and target.suffix.lower() in SCRIPT_EXTS:
                    declared_scripts.add(rel)
        for rel in data.get("tests") or []:
            target = skill / rel
            if not inside(skill, target):
                self.error("V10", path, f"тест выходит за папку скила: {rel}")
            elif not target.exists():
                self.error("V09", path, f"тест не существует: {rel}")
        for rel in data.get("children") or []:
            target = skill / rel
            if not inside(skill, target):
                self.error("V10", path, f"ребенок выходит за папку скила: {rel}")
                continue
            if not (target / "SKILL.md").is_file():
                self.error("V15", path, f"у ребенка нет SKILL.md: {rel}")
            if not (target / "README.md").is_file():
                self.error("V15", path, f"у ребенка нет README.md: {rel}")
            if not (target / "skill.json").is_file():
                self.error("V15", path, f"у ребенка нет skill.json: {rel}")
        deps = data.get("dependencies") or {}
        if not isinstance(deps, dict):
            self.error("V03", path, "dependencies должен быть объектом")
            deps = {}
        skills = deps.get("skills") or []
        for dep in skills:
            if not isinstance(dep, dict):
                self.error("V03", path, "dependencies.skills: запись должна быть объектом")
                continue
            name = dep.get("name")
            if name == skill.name:
                self.error("V17", path, "скил зависит от себя")
            elif name not in self.skill_names:
                self.error("V17", path, f"неизвестный скил: {name}")
        for dep in deps.get("project") or []:
            if not isinstance(dep, dict):
                self.error("V03", path, "dependencies.project: запись должна быть объектом")
                continue
            rel = dep.get("path", "")
            if not rel:
                self.error("V03", path, "пустой dependencies.project.path")
                continue
            if ".." in Path(rel).parts:
                self.error("V10", path, f"путь с .. запрещен: {rel}")
                continue
            target = self.project_root / rel
            if not target.exists():
                self.error("V09", path, f"проектный путь не существует: {rel}")
            if not dep.get("owner"):
                self.error("V03", path, f"пустой owner: {rel}")
        for rel in data.get("generated") or []:
            target = skill / rel
            if inside(skill, target):
                self.error("V18", path, f"generated внутри скила: {rel}")
        # Every file under scripts/ must be declared in manifest.
        scripts_dir = skill / "scripts"
        if scripts_dir.is_dir():
            for p in scripts_dir.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in SCRIPT_EXTS:
                    continue
                rel = p.relative_to(skill).as_posix()
                if rel not in declared_scripts:
                    self.error("V11", path, f"скрипт не объявлен в манифесте: {rel}")
        return data

    def check_dirs(self, skill: Path):
        for child in sorted(skill.iterdir()):
            if child.is_dir() and (child.name not in self.allowed_dirs or child.name in self.forbidden_dirs):
                code = "V18" if child.name in self.forbidden_dirs else "V20"
                self.error(code, child, f"посторонний каталог: {child.name}")
        for p in skill.rglob("*.mdc"):
            self.error("V14", p, "mdc внутри папки скила")
        for p in skill.rglob("test_*.py"):
            if "tests" not in p.parts:
                self.error("V19", p, "тест лежит вне tests/")

    def check_cycle(self, manifests):
        graph = {}
        for name, data in manifests.items():
            deps = (data.get("dependencies") or {}).get("skills") or []
            graph[name] = [d.get("name") for d in deps if d.get("name") in manifests]
        visiting = set()
        visited = set()

        def dfs(node, path):
            if node in visiting:
                self.error("V16", self.root / node, "цикл зависимостей: " + " -> ".join(path + [node]))
                return
            if node in visited:
                return
            visiting.add(node)
            for nxt in graph.get(node, []):
                dfs(nxt, path + [node])
            visiting.remove(node)
            visited.add(node)

        for name in graph:
            dfs(name, [])

    def run(self):
        manifests = {}
        skills = sorted({p.parent for p in self.root.rglob("SKILL.md") if p.is_file()})
        for skill in skills:
            self.check_skill_md(skill)
            self.check_readme(skill)
            self.check_dirs(skill)
            data = self.check_manifest(skill)
            if data:
                manifests[skill.name] = data
        self.check_cycle(manifests)
        return self.errors, self.warnings


def main():
    parser = argparse.ArgumentParser(description="Validate harness skills")
    parser.add_argument("--skills-root", default=".agents/skills")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--policy-root", help="require preliminary policy declarations from this project root")
    args = parser.parse_args()
    root = Path(args.skills_root)
    if not root.is_dir():
        print(f"skills root not found: {root}", file=sys.stderr)
        return 2
    policy = None
    if args.policy_root:
        loader = Path(__file__).resolve().parents[2] / 'harness-core/scripts/canon_paths.py'
        spec = importlib.util.spec_from_file_location('trusted_skill_policy', loader)
        try:
            if spec is None or spec.loader is None:
                raise ValueError('policy reader unavailable')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            policy = module.load_preliminary_policies(Path(args.policy_root))['skill_format']['rules']
            checker = Checker(root, policy)
        except (OSError, ValueError, KeyError, TypeError) as error:
            if args.json:
                print(json.dumps({'status': 'failed', 'errors': [{'code': 'POLICY', 'message': str(error)}], 'warnings': []}, ensure_ascii=False))
            else:
                print(f'ERROR POLICY: {error}', file=sys.stderr)
            return 1
    else:
        checker = Checker(root)
    errors, warnings = checker.run()
    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, "status": "failed" if errors else "passed"}, ensure_ascii=False, indent=2))
    else:
        for item in errors:
            print(f"ERROR {item['code']} {item['path']}: {item['message']}")
        for item in warnings:
            print(f"WARN  {item['code']} {item['path']}: {item['message']}")
        skills_count = len({p.parent for p in root.rglob("SKILL.md") if p.is_file()})
        print(f"skills: {skills_count}, errors: {len(errors)}, warnings: {len(warnings)}")
    if errors and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
