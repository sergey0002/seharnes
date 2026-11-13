"""Tests for check-doc-text.py: false positives, line info, baseline."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "check-doc-text.py")


def run_check(path: Path, *extra: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(path), *extra],
        capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


class CheckDocTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="check-doc-text-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "doc.md"

    def test_service_comment_inline_code_and_quote_are_not_errors(self):
        write(self.path, """# T

## Краткое описание

Текст с `Array.isArray(rids)` и цитатой «Удаление ОИС», достаточно длинный для проверки краткого описания без предупреждений.

## Подводные камни

<!-- updated: 2026-11-06, task: 2070 -->
- **Симптом:** проверка
- **Решение:** проверка

## История изменений

- 2026-11-06: запись
""")
        code, result = run_check(self.path)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["errors"], [])

    def test_real_dash_reports_line_and_section(self):
        write(self.path, """# T

## Заметки

Текст — с длинным тире.
""")
        code, result = run_check(self.path)
        self.assertEqual(code, 1)
        self.assertEqual(len(result["errors"]), 1)
        error = result["errors"][0]
        self.assertEqual(error["code"], "forbidden_char")
        self.assertEqual(error["section"], "Заметки")
        self.assertEqual(error["line"], 5)

    def test_array_outside_code_is_still_an_error(self):
        write(self.path, """# T

## Заметки

Array
""")
        code, result = run_check(self.path)
        self.assertEqual(code, 1)
        self.assertEqual(result["errors"][0]["code"], "php_array_leak")

    def test_baseline_skips_unchanged_sections(self):
        write(self.path, """# T

## Старая

Текст — с долгом.

## Новая

Чистый текст.
""")
        baseline = Path(self.tmp.name) / "baseline.json"
        code, result = run_check(
            self.path, "--baseline", str(baseline),
            "--write-baseline", str(baseline))
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "ok")

        write(self.path, """# T

## Старая

Текст — с долгом.

## Новая

Новый текст — с ошибкой.
""")
        code, result = run_check(self.path, "--baseline", str(baseline))
        self.assertEqual(code, 1, result)
        self.assertEqual(result["checked_sections"], 1)
        self.assertEqual(result["skipped_sections"], 1)
        self.assertEqual({e["section"] for e in result["errors"]}, {"Новая"})


if __name__ == "__main__":
    unittest.main()
