"""Tests for the jsondoc.py validate command."""

import json
import subprocess
import sys
import unittest

import support
from jsondoc import validate


def task_with_links():
    root, docs = support.make_docs()
    task = support.minimal_task("2612", "Задача со ссылками")
    task["sections"] = [{
        "id": "s1", "title": "Заметки", "level": 2, "parent_id": None,
        "anchor": "заметки", "anchor_aliases": [],
        "body_markdown": "[bad](missing.md) [ok](ok.md)",
        "source_ids": [], "origin": "authored"}]
    task["section_order"] = ["s1"]
    support.write_canonical(docs / "tasks" / "2612" / "task.json", task)
    (docs / "tasks" / "2612").mkdir(parents=True, exist_ok=True)
    (docs / "tasks" / "2612" / "doc.md").write_text(
        "[bad](missing.md) [ok](ok.md)\n", encoding="utf-8")
    (docs / "tasks" / "2612" / "ok.md").write_text("ok\n", encoding="utf-8")
    return root, docs


class ValidateTests(unittest.TestCase):
    def test_schema_ok_without_links(self):
        root, docs = task_with_links()
        result = validate.validate_target(root, docs, "task", "2612")
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["errors"], [])

    def test_broken_link_is_reported(self):
        root, docs = task_with_links()
        result = validate.validate_target(root, docs, "task", "2612",
                                          links=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["broken_links"], ["missing.md"])

    def test_missing_view_is_warning(self):
        root, docs = task_with_links()
        (docs / "tasks" / "2612" / "doc.md").unlink()
        result = validate.validate_target(root, docs, "task", "2612",
                                          links=True)
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["warnings"][0]["code"], "view_missing")

    def test_validate_all_counts(self):
        root, docs = task_with_links()
        result = validate.validate_all(root, docs)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["total"], 1)

    def test_cli_validate_task(self):
        root, docs = task_with_links()
        proc = subprocess.run(
            [sys.executable, str(support.SCRIPTS_DIR / "jsondoc.py"),
             "--root", str(root), "validate", "--task", "2612", "--links"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["broken_links"], ["missing.md"])


if __name__ == "__main__":
    unittest.main()
