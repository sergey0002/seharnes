import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gototask.ps1"
PWSH = shutil.which("pwsh")
SECRET = "ingest-secret-must-not-leak"


@unittest.skipUnless(PWSH, "PowerShell is required")
class JsondocIngestTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/kilo")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        (self.root / ".git").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.put("config.json", '{"releaseBranch":"release/1.0","releaseBranchFallbacks":[]}')
        self.put(".agents/skills/task-router/children/jira/scripts/server.php", "")
        self.put(".agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py", "")
        self.put(".doc/tasks/42/_jsondoc/work/tracker.json", "{}")
        self.executable("git", 'case "$1" in\nbranch) printf "main\\n";;\nesac\nexit 0\n')

    def put(self, path, content):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
        return file

    def executable(self, name, body):
        file = self.bin / name
        file.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        file.chmod(0o755)

    def run_action(self, action, *args):
        env = dict(os.environ, PATH=str(self.bin))
        result = subprocess.run(
            [PWSH, "-NoProfile", "-File", str(SCRIPT), "-TaskNumber", "42",
             "-Action", action, "-RepoPath", str(self.root),
             "-ConfigPath", str(self.root / "config.json"), *args],
            text=True, capture_output=True, env=env, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_export_methods_and_ingest_results(self):
        for action in ("inspect", "export-task"):
            for method in ("php", "docker", "fallback"):
                for exit_code in (0, 7):
                    with self.subTest(action=action, method=method, exit_code=exit_code):
                        for name in ("php", "docker"):
                            (self.bin / name).unlink(missing_ok=True)
                        if method in ("php", "fallback"):
                            self.executable("php", 'printf "Title: exported\\n"\nexit ' + ("1" if method == "fallback" else "0") + "\n")
                        if method in ("docker", "fallback"):
                            self.executable("docker", 'printf "Title: exported\\n"\nexit 0\n')
                        self.executable("python3", f'printf "{SECRET}\\n"\nprintf "{SECRET}\\n" >&2\nexit {exit_code}\n')
                        result = self.run_action(action, "-Verbose")
                        self.assertTrue(result["taskExport"]["ok"])
                        self.assertEqual(result["taskExport"]["method"], "php" if method == "php" else "docker")
                        self.assertEqual(result["taskExport"]["output"], "Title: exported")
                        self.assertEqual(result["task"]["title"], "exported")
                        self.assertEqual(result["jsondocIngest"]["status"], "success" if exit_code == 0 else "failed")
                        self.assertEqual(result["jsondocIngest"]["exitCode"], exit_code)

    def test_skipped_ingest_and_failed_export(self):
        self.executable("php", 'printf "Title: exported\\n"\nexit 0\n')
        tracker = self.root / ".doc/tasks/42/_jsondoc/work/tracker.json"
        cli = self.root / ".agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py"
        for action in ("inspect", "export-task"):
            with self.subTest(action=action, reason="task_export_skipped"):
                result = self.run_action(action, "-SkipTaskExport")
                self.assertIsNone(result["taskExport"])
                self.assertEqual(result["jsondocIngest"]["reason"], "task_export_skipped")
            for path, reason in ((tracker, "tracker_not_found"), (cli, "jsondoc_not_found")):
                with self.subTest(action=action, reason=reason):
                    path.unlink()
                    result = self.run_action(action)
                    self.assertTrue(result["taskExport"]["ok"])
                    self.assertEqual(result["jsondocIngest"], {"status": "skipped", "reason": reason})
                    path.write_text("{}", encoding="utf-8")
            result = self.run_action(action)
            self.assertEqual(result["jsondocIngest"]["reason"], "python3_not_found")
            broken = self.bin / "python3"
            broken.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
            broken.chmod(0o755)
            result = self.run_action(action, "-Verbose")
            self.assertTrue(result["taskExport"]["ok"])
            self.assertEqual(result["jsondocIngest"], {"status": "failed", "reason": "ingest_exception"})
            broken.unlink()
            self.executable("php", "exit 1\n")
            self.executable("docker", 'printf "export failed\\n"\nexit 1\n')
            result = self.run_action(action)
            self.assertFalse(result["taskExport"]["ok"])
            self.assertEqual(result["jsondocIngest"]["reason"], "task_export_failed")
            self.executable("php", 'printf "Title: exported\\n"\nexit 0\n')
            (self.bin / "docker").unlink()


if __name__ == "__main__":
    unittest.main()
