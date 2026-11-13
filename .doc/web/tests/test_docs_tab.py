import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

WEB = Path(__file__).resolve().parents[1]

MARKDOWN = """# Первый тестовый документ

<!-- meta
type: architecture
status: actual
updated: 2026-11-13
tags: [test]
-->

## Суть

Тестовый текст про перенос.
"""

JSON_DOC = {
    "metadata": {"title": "JSON документ", "status": "actual", "updated_at": "2026-11-12T00:00:00Z"},
    "sections": [{"id": "s1", "title": "Раздел JSON", "body_markdown": "Тело раздела."}],
    "findings": [{"id": "F-1", "title": "Находка", "statement": "Описание находки."}],
}


@contextmanager
def panel():
    with tempfile.TemporaryDirectory(prefix="panel-docs-test-") as directory:
        root = Path(directory)
        web = root / ".doc/web"
        web.parent.mkdir(parents=True)
        shutil.copytree(WEB, web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        docs = root / ".doc/harnes/state"
        docs.mkdir(parents=True)
        (docs / "01-test.md").write_text(MARKDOWN, encoding="utf-8")
        arch = root / ".doc/architecture"
        arch.mkdir()
        (arch / "demo.json").write_text(json.dumps(JSON_DOC), encoding="utf-8")
        (root / "SECRET.md").write_text("# SECRET\n\nне должно утечь\n", encoding="utf-8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(web), str(web / "router.php")],
                                   cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("PHP test server did not start")
            yield port
        finally:
            process.terminate()
            process.wait(timeout=5)


def get(port, **params):
    url = f"http://127.0.0.1:{port}/index.php?" + urlencode(params)
    with urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


class DocsTabTest(unittest.TestCase):
    """Вкладка «Документация» читает md-канон и JSON архитектуры, а не только architecture/*.json."""

    def test_lists_markdown_and_json(self):
        with panel() as port:
            html = get(port, tab="docs")
            self.assertIn("Первый тестовый документ", html)
            self.assertIn("JSON документ", html)
            self.assertIn("harnes/state/01-test.md", html)
            self.assertIn("architecture/demo.json", html)
            self.assertIn("Показано 2 из 2", html)

    def test_opens_markdown_document(self):
        with panel() as port:
            html = get(port, tab="docs", doc="harnes/state/01-test")
            self.assertIn("<h1>Первый тестовый документ</h1>", html)
            self.assertIn("harnes/state/01-test.md", html)
            self.assertIn("Тестовый текст про перенос.", html)
            self.assertIn("Документация</a> / Харнес / 01-test.md", html)
            self.assertEqual(1, html.count("<h1>Первый тестовый документ</h1>"))

    def test_opens_json_document(self):
        with panel() as port:
            html = get(port, tab="docs", doc="demo")
            self.assertIn("JSON документ", html)
            self.assertIn("Тело раздела.", html)
            self.assertIn("Описание находки.", html)

    def test_traversal_is_rejected(self):
        with panel() as port:
            for attempt in ("../SECRET", "harnes/../../SECRET", "/etc/passwd"):
                html = get(port, tab="docs", doc=attempt)
                self.assertNotIn("не должно утечь", html)
                self.assertIn("Показано 2 из 2", html)


if __name__ == "__main__":
    unittest.main()
