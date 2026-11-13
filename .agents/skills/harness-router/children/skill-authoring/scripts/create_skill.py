#!/usr/bin/env python3
"""Create a new harness skill scaffold and register it.

The script writes SKILL.md, README.md and skill.json, then calls add-skill to
add the card, indexes, registry entry and parent router metadata.

Usage:
  python3 create_skill.py --root . --name my-skill --description "What it does"
  python3 create_skill.py --root . --name my-child --parent harness-router
  python3 create_skill.py --root . --name my-skill --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DEFAULT_DESCRIPTION = "Пользовательский скил харнеса. Применять по явному запросу."
SCANNER = ".agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def skill_md(name: str, title: str, description: str) -> str:
    return f"""---
name: {name}
description: {description}
---

# {title}

## Когда применять

- пользователь явно просит выполнить работу этого скила;
- задача входит в описанную область без смежных изменений.

## Вход

- корень проекта;
- задача или данные, с которыми работает скил;
- подтверждение пользователя на изменение файлов.

## Шаги

1. Проверить входные данные и границы задачи.
2. Выполнить основную работу по назначению скила.
3. Проверить результат и записать его в ожидаемое место.
4. Сообщить, что изменилось и какие проверки выполнены.

## Выход

- результат работы скила;
- список измененных файлов и проверок;
- известные ограничения, если они есть.

## Ограничения

- Скил создан как каркас. Его шаги нужно уточнить под фактическую задачу.
- Не расширять область задачи без запроса.
"""


def readme(name: str, description: str) -> str:
    return f"""# {name}

Назначение.
{description}

Как работает.
Скил выполняет одну область работы и не заменяет соседние скилы. Шаги и
ограничения описаны в SKILL.md.

Что нужно.
Корень проекта и доступ к файлам, с которыми работает скил.

Чего не делает.
Не меняет продуктовый код без запроса и не расширяет область задачи.
"""


def manifest(name: str, kind: str, tests: list[str]) -> str:
    return json.dumps({
        "schema": 1,
        "name": name,
        "kind": kind,
        "entry": "SKILL.md",
        "readme": "README.md",
        "resources": {"scripts": [], "references": [], "assets": []},
        "tests": tests,
        "children": [],
        "dependencies": {"skills": [], "project": []},
        "generated": [],
    }, ensure_ascii=False, indent=2) + "\n"


def run(command: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)


def ensure_baseline(root: Path) -> None:
    baseline = root / ".doc/skil_data/harness-core/kit-manifest.json"
    if baseline.is_file():
        return
    scanner = root / SCANNER
    if scanner.is_file():
        run(["python3", str(scanner), "--root", str(root), "--write-baseline"], root, 120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--name", required=True, help="skill folder name")
    parser.add_argument("--title", default="", help="human title, default is name")
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION, help="frontmatter description and README purpose")
    parser.add_argument("--parent", default="", help="parent skill id, creates under parent/children")
    parser.add_argument("--kind", default="leaf", choices=["leaf", "orchestrator"])
    parser.add_argument("--with-test", action="store_true", help="create a placeholder unittest")
    parser.add_argument("--force", action="store_true", help="replace an existing scaffold")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing")
    parser.add_argument("--no-validate", action="store_true", help="skip validators after registration")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not NAME_RE.match(args.name):
        print(f"invalid skill name: {args.name}", file=sys.stderr)
        return 2
    skills_root = root / ".agents" / "skills"
    if not skills_root.is_dir():
        print(f"skills root not found: {skills_root}", file=sys.stderr)
        return 2

    if args.parent:
        parent = skills_root / args.parent
        if not (parent / "SKILL.md").is_file():
            print(f"parent skill not found: {args.parent}", file=sys.stderr)
            return 2
        target = parent / "children" / args.name
    else:
        target = skills_root / args.name

    if target.exists() and not args.force:
        print(f"skill already exists: {target.relative_to(root)}", file=sys.stderr)
        return 2

    title = args.title or args.name
    tests: list[str] = []
    test_file = target / "tests" / f"test_{args.name.replace('-', '_')}.py"
    if args.with_test:
        tests = [test_file.relative_to(target).as_posix()]

    plan = {
        "skill": args.name,
        "target": target.relative_to(root).as_posix(),
        "parent": args.parent or None,
        "kind": args.kind,
        "with_test": args.with_test,
    }
    if args.dry_run:
        result = {"status": "dry-run", "plan": plan, "errors": []}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    ensure_baseline(root)
    if target.exists() and args.force:
        import shutil
        shutil.rmtree(target)
    write_text(target / "SKILL.md", skill_md(args.name, title, args.description))
    write_text(target / "README.md", readme(args.name, args.description))
    write_text(target / "skill.json", manifest(args.name, args.kind, tests))
    if args.with_test:
        write_text(
            test_file,
            "import unittest\n\n\n"
            f"class Test{args.name.title().replace('-', '')}(unittest.TestCase):\n"
            "    def test_placeholder(self):\n"
            "        self.assertTrue(True)\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
        )

    add_script = root / ".agents/skills/harness-router/children/add-skill/scripts/add_skill.py"
    if not add_script.is_file():
        print("add-skill script not found, scaffold created without docs", file=sys.stderr)
        return 1
    command = ["python3", str(add_script), "--root", str(root), "--name", args.name, "--yes", "--no-sync"]
    if args.no_validate:
        command.append("--no-validate")
    code, output = run(command, root)
    if code != 0:
        print(output, file=sys.stderr)
        return code

    result = {"status": "ok", "plan": plan, "add_skill": output[-1200:]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
