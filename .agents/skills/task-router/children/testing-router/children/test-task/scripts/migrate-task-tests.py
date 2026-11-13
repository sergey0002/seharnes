#!/usr/bin/env python3
"""Разовый перенос Task-Cest в папки задач.

Было:  .tools/codeception/tests/Acceptance/Task/2236_QualityWarningCest.php
Стало: .doc/tasks/2236/tests/QualityWarningCest.php
       + симлинк .tools/codeception/tests/Acceptance/Task/2236 -> ../../../../../.doc/tasks/2236/tests

Зачем: тест задачи должен лежать рядом с task.md, plan.md и test-runs,
а не в общей куче. Номер задачи уходит из имени файла в неймспейс
Tests\\Acceptance\\Task\\T{N} — так два разных QualityWarningCest
не столкнутся именами классов.

    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/migrate-task-tests.py --dry-run
    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/migrate-task-tests.py
"""

import argparse
import pathlib
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
TASK_SUITE = REPO / ".tools/codeception/tests/Acceptance/Task"
TASKS = REPO / ".doc/tasks"

NAMED = re.compile(r"^(\d+)_(\w+Cest)\.php$")


def migrate(path: pathlib.Path, dry: bool) -> str | None:
    m = NAMED.match(path.name)
    if not m:
        return None

    task, cls = m.group(1), m.group(2)
    dest_dir = TASKS / task / "tests"
    dest = dest_dir / f"{cls}.php"

    text = path.read_text(encoding="utf-8")
    new_text = text.replace(
        "namespace Tests\\Acceptance\\Task;",
        f"namespace Tests\\Acceptance\\Task\\T{task};",
    )
    if new_text == text:
        print(f"  ВНИМАНИЕ {path.name}: не нашёл ожидаемый namespace, переношу как есть")

    link = TASK_SUITE / task
    rel_target = f"../../../../../.doc/tasks/{task}/tests"

    print(f"  {path.name}")
    print(f"    -> .doc/tasks/{task}/tests/{cls}.php")
    print(f"    -> симлинк Task/{task} -> {rel_target}")

    if dry:
        return task

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(new_text, encoding="utf-8")
    path.unlink()

    if link.is_symlink():
        link.unlink()
    elif link.exists():
        print(f"    ПРОПУСК симлинка: {link} существует и не симлинк")
        return task
    link.symlink_to(rel_target)

    return task


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not TASK_SUITE.is_dir():
        print(f"нет {TASK_SUITE}", file=sys.stderr)
        sys.exit(2)

    print("Перенос Task-Cest в папки задач" + (" (сухой прогон)" if args.dry_run else ""))
    moved = [t for p in sorted(TASK_SUITE.iterdir())
             if p.is_file() and (t := migrate(p, args.dry_run))]

    if not moved:
        print("  нечего переносить")
        return

    print(f"\nПеренесено задач: {len(set(moved))} ({', '.join(sorted(set(moved)))})")
    if not args.dry_run:
        print("Проверь: python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py")


if __name__ == "__main__":
    main()
