#!/usr/bin/env python3
"""Исправление implicit nullable параметров (PHP 8.4) по отчёту сканера.

Читает JSON от .tools/php85-scan/scan.php, находит находки категории
deprecated-8.4 и добавляет "?" к типу параметра, у которого default null.

По умолчанию работает как dry-run и печатает unified diff. Запись только с
флагом --write.

Примеры:
    python3 .tools/php85-scan/fix_implicit_nullable.py \
        --report .doc/migrations/php85/scan-report.json

    python3 .tools/php85-scan/fix_implicit_nullable.py \
        --report .doc/migrations/php85/scan-report.json --write
"""

import argparse
import difflib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

# Тип может быть: int, ?int, \DateTime, Foo\Bar, A|B, array, callable.
# Ищем "тип $param = null" в пределах одной строки сигнатуры.
PARAM_RE = re.compile(
    r"(?P<type>\\?[A-Za-z_][A-Za-z0-9_\\]*(?:\|[A-Za-z_][A-Za-z0-9_\\]*)*)"
    r"(?P<space>\s+)"
    r"(?P<ref>&?)"
    r"(?P<var>\$[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<eq>\s*=\s*null)"
)


def fix_line(line):
    def repl(match):
        type_name = match.group("type")
        if type_name.startswith("?") or type_name.lower() == "mixed":
            return match.group(0)
        return "?" + type_name + match.group("space") + match.group("ref") + match.group("var") + match.group("eq")

    return PARAM_RE.sub(repl, line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--root", default=str(REPO))
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    if not report_path.is_absolute():
        report_path = pathlib.Path(args.root) / report_path
    report = json.loads(report_path.read_text(encoding="utf-8"))

    targets = {}
    for finding in report.get("findings", []):
        if finding.get("category") != "deprecated-8.4":
            continue
        if "Implicit nullable" not in finding.get("message", ""):
            continue
        targets.setdefault(finding["file"], set()).add(int(finding["line"]))

    if not targets:
        print("No implicit nullable findings in report.")
        return 0

    changed_files = 0
    changed_lines = 0
    for rel, lines in sorted(targets.items()):
        path = pathlib.Path(args.root) / rel
        if not path.is_file():
            print(f"skip missing: {rel}", file=sys.stderr)
            continue
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        original_lines = original.splitlines(keepends=True)
        modified_lines = list(original_lines)
        for line_no in sorted(lines):
            index = line_no - 1
            if index < 0 or index >= len(modified_lines):
                continue
            before = modified_lines[index]
            after = fix_line(before)
            if after != before:
                modified_lines[index] = after
                changed_lines += 1
        if modified_lines == original_lines:
            continue
        changed_files += 1
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            n=2,
        )
        sys.stdout.writelines(diff)
        if args.write:
            path.write_text("".join(modified_lines), encoding="utf-8", errors="surrogateescape")

    mode = "written" if args.write else "dry-run"
    print(f"\n{mode}: files={changed_files}, lines={changed_lines}")
    if not args.write and changed_files:
        print("Run again with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
