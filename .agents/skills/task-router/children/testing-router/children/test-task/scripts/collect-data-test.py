#!/usr/bin/env python3
"""Реестр всех data-test проекта: .doc/qa/_map/data-test.tsv

Сканирует templates/ и scripts/ и собирает атрибуты в трёх формах:
  data-test="item-form-step2__name"          статический
  :data-test="'booking-slot'"                Vue-биндинг с литералом
  :data-test="`tariff-delete-btn-${id}`"     шаблонная строка -> префикс

Реестр нужен check-selectors.py: он сверяет с ним селекторы Page-объектов,
чтобы переименование атрибута в шаблоне не превращало dontSeeElement()
в ложно-зелёную проверку.

Запуск: python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py
"""

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
SCAN_DIRS = ["templates", "scripts", "admin", "frontend/src"]
SCAN_EXT = {".tpl", ".js", ".vue", ".html", ".php"}
OUT = REPO / ".doc/qa/_map/data-test.tsv"

# Сгенерированное и собранное: там копии тех же атрибутов, только
# с мусорными путями. templates_c/cache — компилированный Smarty.
SKIP_PARTS = {"node_modules", "dist", "templates_c", "cache", "vendor", "_output"}

# Статический атрибут: data-test="name", но НЕ :data-test / v-bind:data-test.
STATIC = re.compile(r'(?<![:\w-])data-test\s*=\s*"([^"{}$`+\']+)"')
# Биндинг с литералом: :data-test="'name'"
BOUND_SQ = re.compile('[:@]data-test\\s*=\\s*"\\s*\'([^\']+)\'\\s*"')
# Биндинг-выражение: :data-test="'prefix-' + id" или "`prefix-${id}`"
BOUND_PREFIX = re.compile('[:@]data-test\\s*=\\s*"\\s*[\'`]([^\'`$]+)')


def scan() -> list[tuple[str, str, int, str]]:
    rows: list[tuple[str, str, int, str]] = []

    for rel in SCAN_DIRS:
        base = REPO / rel
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_EXT:
                continue
            if SKIP_PARTS & set(path.parts):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            short = str(path.relative_to(REPO))
            for lineno, line in enumerate(text.splitlines(), 1):
                for name in STATIC.findall(line):
                    rows.append((name.strip(), "static", lineno, short))

                bound = BOUND_SQ.findall(line)
                for name in bound:
                    rows.append((name.strip(), "bound", lineno, short))
                if not bound:
                    # Выражение без чистого литерала: фиксируем только
                    # неизменяемый префикс, по нему матчится startswith.
                    for prefix in BOUND_PREFIX.findall(line):
                        if prefix.strip():
                            rows.append((prefix.strip(), "prefix", lineno, short))

    return sorted(set(rows))


def main() -> None:
    rows = scan()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# Реестр data-test. Генерируется collect-data-test.py, руками не править.\n")
        fh.write("# name\tkind\tline\tfile\n")
        for name, kind, lineno, path in rows:
            fh.write(f"{name}\t{kind}\t{lineno}\t{path}\n")

    unique = len({r[0] for r in rows})
    print(f"data-test: {unique} уникальных, {len(rows)} вхождений -> {OUT.relative_to(REPO)}")

    if unique == 0:
        print("ПУСТО: проверь SCAN_DIRS", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
