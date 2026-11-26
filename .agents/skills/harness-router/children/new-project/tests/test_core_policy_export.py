"""Integration: Core export ships the policy declarations its validators read."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "harness_transfer.py"
SOURCE = SCRIPT.parents[6]


def _export(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "export", "--source", str(SOURCE), "--target", str(target),
         "--profile", "core", "--mode", "install", "--project-name", "policyfixture",
         "--skip-runtime-deps", "--yes"],
        capture_output=True, text=True, timeout=900,
    )


class CorePolicyExportTest(unittest.TestCase):
    def test_core_exports_policy_files_and_strict_policy_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            result = _export(target)
            self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
            self.assertFalse((target / ".git").exists())
            policies = target / ".agents/skills/harness-router/children/harness-core/assets/policies"
            for name in ("skill-format.yaml", "component-docs.yaml"):
                self.assertTrue((policies / name).is_file())
            self.assertTrue((target / ".doc/harnes/state/canon-paths.yaml").is_file())
            self.assertTrue((target / ".doc/web/README.md").is_file())
            checks = [
                (".agents/skills/harness-router/children/improvement/scripts/validate_structure.py",
                 "--require-policy", "--json"),
                (".agents/skills/harness-router/children/improvement/scripts/validate_skills.py",
                 "--policy-root", ".", "--json"),
            ]
            for args in checks:
                with self.subTest(check=args[0]):
                    check = subprocess.run([sys.executable, *args], cwd=target,
                                           capture_output=True, text=True, timeout=180)
                    self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            (policies / "component-docs.yaml").unlink()
            check = subprocess.run([sys.executable, *checks[0]], cwd=target,
                                   capture_output=True, text=True, timeout=180)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("POLICY_MISSING", check.stdout + check.stderr)

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_core_export_does_not_touch_git_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(target), "remote", "add", "origin",
                            "https://example.invalid/app.git"], check=True, capture_output=True)
            exclude = target / ".git/info/exclude"
            exclude.write_bytes(b"# local settings\n/project-private\n")

            def tree():
                return {path.relative_to(target / ".git").as_posix(): path.read_bytes()
                        for path in (target / ".git").rglob("*") if path.is_file()}

            before = tree()
            result = _export(target)
            self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
            self.assertEqual(tree(), before)


if __name__ == "__main__":
    unittest.main()