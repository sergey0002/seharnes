import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "intake_state.py"


class IntakeStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_state(self, task="1489"):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "--task", task],
            capture_output=True, text=True, timeout=60)
        return result, (json.loads(result.stdout) if result.stdout else None)

    def put(self, path, text, mtime=None):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if mtime is not None:
            os.utime(target, (mtime, mtime))
        return target

    def test_missing_task_requests_fetch(self):
        result, payload = self.run_state()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["next_action"], "fetch")
        self.assertFalse(payload["files"]["task.md"])

    def test_identity_preserves_status_and_checks(self):
        self.put(".doc/tasks/1489/task.md", "task")
        script = ".agents/skills/documentation-router/children/project-doc/scripts/task-identity.py"
        for status in ("ok", "mismatch", "incomplete"):
            with self.subTest(status=status):
                payload = {"status": status, "ok": status == "ok",
                           "checks": [{"name": "task", "ok": False}],
                           "warnings": ["warning"]}
                self.put(script, "import json, sys\nprint(" + repr(json.dumps(payload)) + ")\nsys.exit(" + ("0" if status == "ok" else "2") + ")\n")
                _, result = self.run_state()
                self.assertEqual(result["identity"]["status"], status)
                self.assertEqual(result["identity"]["checks"], payload["checks"])
                self.assertEqual(result["identity"]["warnings"], payload["warnings"])

    def test_identity_invalid_output_is_error(self):
        self.put(".doc/tasks/1489/task.md", "task")
        self.put(".agents/skills/documentation-router/children/project-doc/scripts/task-identity.py", "print('invalid')\n")
        _, result = self.run_state()
        self.assertEqual(result["identity"]["status"], "error")

    def test_legacy_numbers_and_next_action_doc(self):
        task = self.put(".doc/tasks/1489/task.md",
                        "# Issue #1489\n\n"
                        "Imported from <https://tracker.example/issues/597>\n\n"
                        "| Field | Value |\n| --- | --- |\n| Bitbucket | 597 |\n",
                        mtime=1000)
        self.put(".doc/tasks/1489/task.json", "{}", mtime=1000)
        self.put(".doc/tasks/1489/diff.md", "diff", mtime=2000)
        self.put(".doc/tasks/1489/diff.files.md", "files", mtime=2000)
        result, payload = self.run_state()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["legacy"], ["597"])
        self.assertEqual(payload["freshness"]["diff_vs_task"], "fresh")
        self.assertEqual(payload["next_action"], "doc")
        self.assertTrue(task.is_file())

    def test_generated_views_report_json_route(self):
        self.put(".doc/architecture/orders.md",
                 "<!-- generated from architecture:orders by doc_render.py; do not edit -->\n")
        self.put(".doc/architecture/legacy.md", "# Legacy\n")
        self.put(".doc/tasks/1489/task.md", "# Issue #1489\n")
        self.put(".doc/tasks/1489/task.json", "{}")
        result, payload = self.run_state()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["generated_views"]["architecture_md"],
                         {"generated": 1, "total": 2})
        self.assertEqual(payload["generated_views"]["edit_route"],
                         "mixed_check_path")

    def test_path_check_marks_generated_write(self):
        self.put(".doc/architecture/orders.md",
                 "<!-- generated from architecture:orders by doc_render.py; do not edit -->\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "--path", ".doc/architecture/orders.md"],
            capture_output=True, text=True, timeout=60)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(payload["generated"])
        self.assertEqual(payload["edit_route"], "jsondoc_apply")

    def test_complete_task_requests_verify_without_html_report(self):
        step = 1000
        for name in ("task.md", "task.json", "diff.md", "doc.md"):
            self.put(f".doc/tasks/1489/{name}", name, mtime=step)
            step += 1000
        result, payload = self.run_state()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["freshness"]["doc_vs_diff"], "fresh")
        self.assertEqual(payload["next_action"], "verify")
        self.assertFalse(payload["artifacts"]["report_html"])


if __name__ == "__main__":
    unittest.main()
