"""Regression: legacy tracker URLs in commit subjects must reach the task diff."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "task-diff.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


@unittest.skipUnless(PWSH, "PowerShell is not available")
class LegacyUrlMatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "harness@example.test")
        git(self.repo, "config", "user.name", "Harness")
        config = self.repo / ".cursor/skills/task-router/children/gototask/config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"releaseBranch": "release/1.0.0",
                        "releaseBranchFallbacks": []}),
            encoding="utf-8")
        task_dir = self.repo / ".doc/tasks/1489"
        task_dir.mkdir(parents=True)
        (task_dir / "task.md").write_text(
            "# Issue #1489: legacy task\n\n"
            "| Field | Value |\n| --- | --- |\n| Bitbucket | 597 |\n",
            encoding="utf-8")
        self.put("lib/example.php", "one\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "baseline")
        self.put("lib/example.php", "two\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m",
            "https://bitbucket.example/issues/597")

    def put(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def run_diff(self):
        result = subprocess.run(
            [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(SCRIPT), "-TaskNumber", "1489",
             "-RepoPath", str(self.repo), "-SkipFetch"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_legacy_issue_url_subject_is_matched(self):
        payload = self.run_diff()
        self.assertEqual(payload["branchMode"], "any-ref")
        self.assertEqual(payload["commitCount"], 1)
        self.assertEqual(payload["fileCount"], 1)
        diff = (self.repo / ".doc/tasks/1489/diff.md").read_text(encoding="utf-8")
        self.assertIn("lib/example.php", diff)

    def test_plain_number_subject_still_matched_and_neighbour_not(self):
        self.put("lib/example.php", "three\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "1489 доработка")
        self.put("lib/example.php", "four\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "1490 другая задача")
        payload = self.run_diff()
        self.assertEqual(payload["commitCount"], 2)
        diff = (self.repo / ".doc/tasks/1489/diff.md").read_text(encoding="utf-8")
        self.assertIn("1489 доработка", diff)
        self.assertNotIn("1490 другая задача", diff)


if __name__ == "__main__":
    unittest.main()
