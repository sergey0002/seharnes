#!/usr/bin/env python3
"""Две проверки селекторов. Обе закрывают класс "ложно-зелёный тест".

1. Мёртвые data-test в Page/Step.
   Если шаблон переименовал атрибут, waitForElement() честно падает,
   а вот dontSeeElement() начинает проходить всегда. Тест зелёный,
   регрессия не ловится. Сверяем каждый data-test из Page/Step
   с реестром .doc/qa/_map/data-test.tsv.

2. Сырые селекторы в Cest задач.
   Селектор в Cest — это копипаста, которая живёт вне Page и не
   попадает под проверку 1. Все селекторы должны быть в Page/Step.

Запуск:
    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py    # сначала реестр
    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py

Код возврата 1 — гейт G10 не пройден.
"""

import pathlib
import re
import argparse
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
REGISTRY = REPO / ".doc/qa/_map/data-test.tsv"
SUPPORT = REPO / ".tools/codeception/tests/Support"
TASK_TESTS = REPO / ".doc/tasks"
# Храповик: Cest, написанные до правила. Список может только сокращаться —
# скрипт сам ругается, если файл уже чистый и его пора убрать.
LEGACY = REPO / ".doc/qa/_map/selectors-legacy.txt"

# data-test внутри сырого XPath/CSS: '//*[@data-test="foo"]', "[data-test='foo']"
DATA_TEST_IN_CODE = re.compile(r'data-test=\\?["\']([^"\'\\\]]+)')
# Объявление константы класса: private const STEP2_NAME = 'item-form-step2__name';
CONST_DECL = re.compile(r"""const\s+(\w+)\s*=\s*'([^']+)'\s*;""")
# Аргументы хелперов Page: self::test('x') / self::test(self::CONST) / self::testIn(a, b)
TEST_CALL = re.compile(r"self::testIn?\(\s*([^)]*)\)")
ARG = re.compile(r"'([^']+)'|self::(\w+)")

# Сырой селектор в Cest: XPath, scoped data-test, class-матчер, прямой DOM.
RAW_PATTERNS = [
    (re.compile(r"""['"]\(?\.{0,2}//"""), "XPath-литерал"),
    (re.compile(r"@data-test="), "селектор по data-test"),
    (re.compile(r"contains\(@class"), "селектор по классу"),
    (re.compile(r"document\.querySelector"), "прямой DOM в executeJS"),
]

# Строки, которые выглядят как селектор, но ими не являются.
RAW_ALLOW = re.compile(r"^\s*(//|\*|/\*)")


def load_registry() -> tuple[set[str], list[str]]:
    if not REGISTRY.exists():
        print(f"нет реестра {REGISTRY}: сначала collect-data-test.py", file=sys.stderr)
        sys.exit(2)

    exact: set[str] = set()
    prefixes: list[str] = []

    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, kind = parts[0], parts[1]
        if kind == "prefix":
            prefixes.append(name)
        else:
            exact.add(name)

    return exact, prefixes


def known(name: str, exact: set[str], prefixes: list[str]) -> bool:
    return name in exact or any(name.startswith(p) for p in prefixes)


def check_page_selectors(exact: set[str], prefixes: list[str]) -> list[str]:
    """Каждый data-test из Page/Step должен существовать в шаблонах."""
    problems: list[str] = []

    for path in sorted(SUPPORT.rglob("*.php")):
        if "_generated" in path.parts:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(REPO)

        # Сырые вхождения data-test= в XPath/CSS-строках.
        names = set(DATA_TEST_IN_CODE.findall(text))

        # Обращения через хелперы Page: self::test(self::STEP2_NAME).
        # Резолвим константы класса, чтобы не ругаться на имя константы.
        consts = dict(CONST_DECL.findall(text))
        for call in TEST_CALL.findall(text):
            for literal, const_name in ARG.findall(call):
                if literal:
                    names.add(literal)
                elif const_name in consts:
                    names.add(consts[const_name])

        for name in sorted(names):
            if not known(name, exact, prefixes):
                problems.append(f"{rel}: data-test \"{name}\" не найден в шаблонах")

    return problems


def load_legacy() -> set[str]:
    if not LEGACY.exists():
        return set()
    return {
        line.strip()
        for line in LEGACY.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def check_raw_selectors(legacy: set[str], task: str | None = None) -> tuple[list[str], list[str], list[str]]:
    """В Cest задач сырых селекторов быть не должно.

    `task` ограничивает проверку одной задачей. Без ограничения гейт читал Cest
    всех 180 задач, поэтому долг одной старой задачи блокировал каждую новую.
    Полный список по репозиторию доступен через --task all.

    Возвращает (блокирующие, легаси-долг, устаревшие записи храповика).
    """
    blocking: list[str] = []
    debt: list[str] = []
    dirty_files: set[str] = set()

    pattern = f"{task}/tests/**/*.php" if task else "*/tests/**/*.php"
    for path in sorted(TASK_TESTS.glob(pattern)):
        rel = str(path.relative_to(REPO))
        hits: list[str] = []

        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if RAW_ALLOW.match(line):
                continue
            for pattern, label in RAW_PATTERNS:
                if pattern.search(line):
                    hits.append(f"{rel}:{lineno}: {label}\n      {line.strip()[:110]}")
                    break

        if not hits:
            continue

        dirty_files.add(rel)
        if rel in legacy:
            debt.append(f"{rel}: {len(hits)} сырых селекторов")
        else:
            blocking.extend(hits)

    stale = sorted(legacy - dirty_files)
    return blocking, debt, stale


def main() -> None:
    parser = argparse.ArgumentParser(description="Селекторы: реестр и сырые селекторы в Cest")
    parser.add_argument(
        "--task",
        default="",
        help="проверять Cest только этой задачи; all или пусто означает весь репозиторий",
    )
    args = parser.parse_args()
    task = "" if args.task in ("", "all") else args.task
    if task and not task.isdigit():
        parser.error(f"--task: ожидался номер задачи, получено: {task}")

    exact, prefixes = load_registry()
    legacy = load_legacy()

    dead = check_page_selectors(exact, prefixes)
    blocking, debt, stale = check_raw_selectors(legacy, task or None)

    scope = f"задача {task}" if task else "весь репозиторий"
    print(f"Реестр: {len(exact)} атрибутов, {len(prefixes)} префиксов; область Cest: {scope}")

    if dead:
        print(f"\nМёртвые селекторы в Page/Step ({len(dead)}):")
        for item in dead:
            print(f"  {item}")
    else:
        print("Мёртвых селекторов в Page/Step нет")

    if blocking:
        print(f"\nСырые селекторы в Cest задач ({len(blocking)}) — вынеси в Page/Step:")
        for item in blocking:
            print(f"  {item}")
    else:
        print("Новых сырых селекторов в Cest задач нет")

    if debt:
        print(f"\nЛегаси-долг ({len(debt)} файлов, не блокирует):")
        for item in debt:
            print(f"  {item}")
        print(f"  список: {LEGACY.relative_to(REPO)}")

    if stale:
        print(f"\nХраповик протух: файлы уже чистые, убери из {LEGACY.relative_to(REPO)}:")
        for item in stale:
            print(f"  {item}")

    sys.exit(1 if (dead or blocking or stale) else 0)


if __name__ == "__main__":
    main()
