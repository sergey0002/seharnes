#!/usr/bin/env python3
"""Матрица PHP-совместимости пакетов из composer.lock для перехода на PHP 8.5.

Читает composer.lock, берёт platform-требование "php" каждого пакета и
классифицирует:

    ok          - ограничение допускает PHP 8.5 и пакет явно знает про 8.x
    narrow      - верхней границы нет (>=5.5) или заявлена только старая ветка,
                  формально 8.5 проходит, но пакет её не тестировал
    unsupported - все альтернативы ограничения исключают 8.5 (^7, ~8.3.0, <8 ...)
    unknown     - пакет не объявляет требование к PHP

Запуск:
    python3 .tools/php85-scan/composer_matrix.py [composer.lock] [--json FILE] [--md FILE]
"""

import argparse
import json
import re
import sys

PHP85 = (8, 5, 0)


def _num(value):
    parts = [int(p) for p in re.findall(r"\d+", value)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _excludes_85(alt):
    """True, если альтернатива composer-констрейнта исключает 8.5."""
    a = alt.strip().lower()
    if not a:
        return False

    # Явные верхние границы
    for m in re.finditer(r"<=?\s*(\d+(?:\.\d+){0,2})", a):
        bound = _num(m.group(1))
        if m.group(0).startswith("<="):
            if bound < PHP85:
                return True
        else:
            if bound <= PHP85:
                return True

    # ^7 / ^7.1
    m = re.match(r"\^(\d+(?:\.\d+){0,2})", a)
    if m:
        return _num(m.group(1))[0] < 8

    # ~8.0.0 - строгая минорная ветка; ~8.0 - до следующего мажора
    m = re.match(r"~(\d+(?:\.\d+){1,2})", a)
    if m:
        parts = [int(p) for p in m.group(1).split(".")]
        if len(parts) >= 3:
            if parts[0] < 8:
                return True
            if parts[0] == 8 and parts[1] < 5:
                return True
        else:
            if parts[0] < 8:
                return True
            if parts[0] == 8:
                return False
        return False

    # 7.* / 8.0.*
    m = re.match(r"(\d+)\.(\d+)\.\*", a)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        return major < 8 or (major == 8 and minor < 5)

    # Только нижняя граница (>=5.5, >=7.1) - 8.5 проходит
    return False


def classify(constraint):
    if not constraint:
        return "unknown"
    alternatives = [p for p in re.split(r"\|\|?", constraint) if p.strip()]
    allows = any(not _excludes_85(alt) for alt in alternatives)
    if not allows:
        return "unsupported"
    if re.search(r"(?<!\d)8(?:\.\d+)?", constraint):
        return "ok"
    return "narrow"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", nargs="?", default="composer.lock")
    parser.add_argument("--json")
    parser.add_argument("--md")
    args = parser.parse_args()

    with open(args.lock, "r", encoding="utf-8") as fh:
        lock = json.load(fh)

    rows = []
    for section in ("packages", "packages-dev"):
        for pkg in lock.get(section, []):
            require = pkg.get("require") or {}
            constraint = require.get("php")
            rows.append({
                "name": pkg.get("name"),
                "version": pkg.get("version"),
                "section": section,
                "php": constraint,
                "status": classify(constraint),
            })

    order = {"unsupported": 0, "unknown": 1, "narrow": 2, "ok": 3}
    rows.sort(key=lambda r: (order[r["status"]], r["name"]))
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print("PHP constraint matrix (composer.lock)")
    for status in ("unsupported", "unknown", "narrow", "ok"):
        print(f"  {status}: {counts.get(status, 0)}")
    print()
    for r in rows:
        if r["status"] in ("unsupported", "unknown", "narrow"):
            print(f"{r['status']:12} {r['name']:40} {r['version']:16} php={r['php']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"counts": counts, "rows": rows}, fh, ensure_ascii=False, indent=2)
    if args.md:
        lines = [
            "| Пакет | Версия | Требование php | Статус |",
            "|---|---|---|---|",
        ]
        for r in rows:
            lines.append(f"| `{r['name']}` | {r['version']} | `{r['php'] or '-'}` | {r['status']} |")
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
