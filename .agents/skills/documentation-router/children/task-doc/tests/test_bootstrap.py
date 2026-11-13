"""J00 bootstrap tests: CLI entry, sandbox discipline, execution state."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

import support

CLI = support.SCRIPTS_DIR / "jsondoc.py"


def run_cli(args):
    return subprocess.run([sys.executable, str(CLI)] + args,
                          capture_output=True, text=True, timeout=120)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root, self.docs = support.make_docs()

    def test_help_exits_zero_and_no_json_on_stdout(self):
        proc = run_cli(["--root", str(self.root), "--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("{", proc.stdout[:1])

    def test_invalid_root_returns_error_envelope(self):
        proc = run_cli(["--root", str(self.root / "missing"), "execution", "next"])
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "error")

    def test_execution_next_starts_at_j00(self):
        proc = run_cli(["--root", str(self.root), "execution", "next"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["next_stage"], "J00")

    def test_verify_stage_requires_dependency_and_evidence(self):
        proc = run_cli(["--root", str(self.root), "execution", "verify-stage",
                        "--stage", "J01"])
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["exit"], 2)
        codes = {e["code"] for e in payload["errors"]}
        self.assertIn("dependency_not_passed", codes)
        self.assertIn("missing_stage_record", codes)

    def test_selftest_selector_is_mutually_exclusive(self):
        proc = run_cli(["--root", str(self.root), "selftest",
                        "--stage", "J00", "--suite", "all-bootstrap",
                        "--run", "sel-01"])
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertIn("selector_required", payload["errors"][0]["code"])

    def test_baseline_writes_file_hashes(self):
        proc = run_cli(["--root", str(self.root), "baseline", "--run", "base-01"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertGreater(payload["files"], 0)


if __name__ == "__main__":
    unittest.main()
