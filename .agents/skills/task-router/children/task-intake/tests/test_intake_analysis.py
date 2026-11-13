import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "intake_analysis.py"


class IntakeAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def fixture(self):
        self.put(".doc/tasks/1491/task.md", """# Issue #1491: card
| Field | Value |
| --- | --- |
| State | Done |
| Created | 06.12.2019 05:40 UTC |
| Bitbucket | 599 |
""")
        self.put(".doc/tasks/1491/diff.md", """# Diff Issue #1491
## Commits (index)

- `aaa1111` | 18.12.2019 10:15:50 +0500 | one | https://tracker.example/issues/599
- `bbb2222` | 09.09.2025 16:28:27 +0300 | two | #1491 fix

## Committed changes

diff --git a/lib/a.php b/lib/a.php
--- a/lib/a.php
+++ b/lib/a.php
@@ -1 +1,2 @@
 old
+new
diff --git a/gone.tpl b/gone.tpl
--- a/gone.tpl
+++ b/gone.tpl
@@ -1 +1 @@
-a
+b
""")
        self.put(".doc/tasks/1491/diff.files.md", """# Files Issue #1491
## All files

lib/a.php
gone.tpl

## By commit

### `aaa1111` | 18.12.2019 | one

gone.tpl

### `bbb2222` | 09.09.2025 | two

lib/a.php
""")
        self.put(".doc/architecture/_map/file-registry.tsv",
                 "path\tkind\tstatus\tdomain\tdoc_refs\n"
                 "lib/a.php\tphp\tindexed\torders\torders.md\n")
        self.put("lib/a.php", "<?php\n")

    def test_scaffold_flags_and_commit_map(self):
        self.fixture()
        output = self.root / "scaffold.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "--task", "1491", "--output", str(output)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["commits"], 2)
        self.assertEqual(summary["files"], 2)
        self.assertEqual(summary["historical"], 1)
        payload = json.loads(output.read_text(encoding="utf-8"))
        by_sha = {item["sha"]: item["flags"] for item in payload["commits"]}
        self.assertIn("legacy_tracker_url", by_sha["aaa1111"])
        self.assertIn("date_outlier", by_sha["bbb2222"])
        by_path = {item["path"]: item for item in payload["files"]}
        self.assertEqual(by_path["gone.tpl"]["state"], "historical")
        self.assertIn("historical", by_path["gone.tpl"]["flags"])
        self.assertEqual(by_path["lib/a.php"]["commits"], ["bbb2222"])
        self.assertEqual(by_path["lib/a.php"]["doc_refs"], ["orders.md"])
        self.assertTrue(by_path["lib/a.php"]["diff_range"]["start"] > 0)
        self.assertGreaterEqual(by_path["lib/a.php"]["diff_range"]["end"],
                                by_path["lib/a.php"]["diff_range"]["start"])

    def test_missing_diff_returns_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "--task", "1491"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "error")


if __name__ == "__main__":
    unittest.main()
