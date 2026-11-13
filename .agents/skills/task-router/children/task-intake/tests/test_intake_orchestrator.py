import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import intake_orchestrator  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "intake_orchestrator.py"


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text, mtime=None):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if mtime is not None:
            os.utime(target, (mtime, mtime))
        return target

    def complete_task(self):
        step = 1000
        for name in ("task.md", "task.json", "diff.md", "doc.md"):
            self.put(f".doc/tasks/1489/{name}", name, mtime=step)
            step += 1000
        self.put(".doc/tasks/1489/reports/change-report/report.html", "html")

    def identity(self, status="ok"):
        payload = {"status": status, "ok": status == "ok", "checks": [], "warnings": []}
        self.put(".agents/skills/documentation-router/children/project-doc/scripts/task-identity.py",
                 "import sys\nprint(" + repr(json.dumps(payload)) + ")\nsys.exit(" + ("0" if status == "ok" else "2") + ")\n")

    def run_main(self, *args):
        out = io.StringIO()
        with mock.patch.object(sys, "argv",
                               ["intake_orchestrator.py", "--root",
                                str(self.root), *args]):
            with contextlib.redirect_stdout(out):
                code = intake_orchestrator.main()
        return code, json.loads(out.getvalue())

    def test_complete_task_runs_nothing(self):
        self.complete_task()
        self.identity()
        code, payload = self.run_main("--task", "1489")
        self.assertEqual(code, 0)
        self.assertEqual(payload["steps"], [])
        self.assertEqual(payload["next_action"], "verify")

    def test_fresh_task_md_skips_export_and_runs_diff(self):
        self.put(".doc/tasks/1489/task.md", "# Issue #1489\n", mtime=1000)
        self.put(".doc/tasks/1489/task.json", "{}", mtime=1000)
        self.identity()
        diff_script = self.put(".agents/skills/task-router/children/task-diff/scripts/task-diff.ps1", "")
        self.assertTrue(diff_script.is_file())

        def fake_run(command, cwd, timeout):
            self.assertNotIn("gototask.ps1", " ".join(command))
            self.put(".doc/tasks/1489/diff.md", "diff", mtime=5000)
            self.put(".doc/tasks/1489/diff.files.md", "files", mtime=5000)
            return 0, ""

        with mock.patch.object(intake_orchestrator, "powershell", return_value="pwsh"), mock.patch.object(intake_orchestrator, "run", side_effect=fake_run):
            code, payload = self.run_main("--task", "1489")
        self.assertEqual(code, 0)
        self.assertEqual([s["name"] for s in payload["steps"]], ["diff"])
        self.assertEqual(payload["next_action"], "doc")

    def test_export_failure_is_reported(self):
        gototask = self.put(
            ".agents/skills/task-router/children/gototask/scripts/gototask.ps1", "")
        self.assertTrue(gototask.is_file())
        with mock.patch.object(intake_orchestrator, "powershell", return_value="pwsh"), mock.patch.object(intake_orchestrator, "run",
                                return_value=(1, "jira down")):
            code, payload = self.run_main("--task", "1489")
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "error")
        self.assertIn("export failed", payload["errors"])
        export = next(s for s in payload["steps"] if s["name"] == "export")
        self.assertEqual(export["tail"], "jira down")

    def test_identity_gate_blocks_diff(self):
        self.put(".doc/tasks/1489/task.md", "task")
        self.put(".doc/tasks/1489/task.json", "{}")
        self.put(".agents/skills/task-router/children/task-diff/scripts/task-diff.ps1", "")
        for status in ("mismatch", "incomplete", "unavailable"):
            with self.subTest(status=status):
                if status != "unavailable":
                    self.identity(status)
                else:
                    (self.root / ".agents/skills/documentation-router/children/project-doc/scripts/task-identity.py").unlink()
                with mock.patch.object(intake_orchestrator, "powershell", return_value="pwsh"), mock.patch.object(intake_orchestrator, "run") as run:
                    code, payload = self.run_main("--task", "1489")
                self.assertEqual(code, 1)
                self.assertIn("identity " + status, payload["errors"])
                run.assert_not_called()

    def test_export_ingest_status_and_post_export_identity_gate(self):
        self.put(".agents/skills/task-router/children/gototask/scripts/gototask.ps1", "")
        self.put(".agents/skills/task-router/children/task-diff/scripts/task-diff.ps1", "")
        for ingest_status, identity_status, should_diff in (
            ("success", "ok", True),
            ("failed", "ok", False),
            ("skipped", "ok", False),
            ("success", "mismatch", False),
            ("success", "incomplete", False),
        ):
            with self.subTest(ingest=ingest_status, identity=identity_status):
                self.identity(identity_status)
                calls = []
                def fake_run(command, cwd, timeout):
                    calls.append(command)
                    if "export-task" in command:
                        self.put(".doc/tasks/1489/task.md", "task")
                        self.put(".doc/tasks/1489/task.json", "{}")
                        return 0, json.dumps({"taskExport": {"ok": True}, "jsondocIngest": {"status": ingest_status}})
                    return 0, ""
                with mock.patch.object(intake_orchestrator, "powershell", return_value="pwsh"), mock.patch.object(intake_orchestrator, "run", side_effect=fake_run):
                    code, payload = self.run_main("--task", "1489", "--force")
                self.assertEqual(any("task-diff.ps1" in " ".join(c) for c in calls), should_diff)
                self.assertEqual(code, 0 if should_diff else 1)
                self.assertEqual(next(s for s in payload["steps"] if s["name"] == "ingest-tracker")["status"], ingest_status)

    def test_invalid_export_result_blocks_diff(self):
        self.put(".agents/skills/task-router/children/gototask/scripts/gototask.ps1", "")
        self.put(".agents/skills/task-router/children/task-diff/scripts/task-diff.ps1", "")
        with mock.patch.object(intake_orchestrator, "powershell", return_value="pwsh"), mock.patch.object(intake_orchestrator, "run", return_value=(0, "not json")) as run:
            code, payload = self.run_main("--task", "1489")
        self.assertEqual(code, 1)
        self.assertIn("export result invalid", payload["errors"])
        self.assertEqual(run.call_count, 1)

    def test_cli_help(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--task", result.stdout)


if __name__ == "__main__":
    unittest.main()
