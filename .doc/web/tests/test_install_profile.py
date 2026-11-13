import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]


class InstallProfileTest(unittest.TestCase):
    def fixture(self, root, service_profile="full", receipt=None):
        web = root / ".doc/web"
        web.parent.mkdir(parents=True)
        shutil.copytree(WEB, web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        service = web / "config/service.json"
        data = json.loads(service.read_text(encoding="utf-8"))
        data["profile"] = service_profile
        service.write_text(json.dumps(data), encoding="utf-8")
        if receipt is not None:
            (root / ".doc/.rebase-kit.json").write_text(receipt, encoding="utf-8")
        graph = root / ".doc/skil_data/mirror/graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("{}", encoding="utf-8")
        return web, service

    def test_service_profile_is_not_guessed_from_skill_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            web, service = self.fixture(Path(directory), "full")
            result = subprocess.run(["bash", str(web / "install.sh"), "--project"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(service.read_text())["profile"], "full")
            self.assertIn("| PROFILE | `full` |", (web / "ADAPTERS.local.md").read_text())

    def test_migration_receipt_overrides_source_service_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            web, service = self.fixture(Path(directory), "full", '{"profile":"Core","status":"pending"}')
            result = subprocess.run(["bash", str(web / "install.sh"), "--project"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(service.read_text())["profile"], "core")
            self.assertIn("| PROFILE | `core` |", (web / "ADAPTERS.local.md").read_text())

    def test_invalid_receipt_stops_before_writes(self):
        for receipt in ('{"profile":"unexpected"}', '{broken'):
            with self.subTest(receipt=receipt), tempfile.TemporaryDirectory() as directory:
                web, service = self.fixture(Path(directory), "full", receipt)
                before = service.read_bytes()
                result = subprocess.run(["bash", str(web / "install.sh"), "--project"], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid profile", result.stderr)
                self.assertEqual(service.read_bytes(), before)
                self.assertFalse((web / "state").exists())
                self.assertFalse((web / ".env").exists())

    def test_action_check_uses_receipt_and_rejects_invalid_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            web, _ = self.fixture(Path(directory), "full", '\ufeff{"profile":"Core"}')
            config = web / "config/actions.json"
            config.write_text(json.dumps({"actions": [{"id": "full_only", "profile": "full",
                                                       "script": ".agents/skills/missing.py"}]}))
            command = ["python3", str(web / "bin/build-actions.py"), "--check"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            (Path(directory) / ".doc/.rebase-kit.json").write_text('{"profile":"invalid"}')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid profile", result.stdout)


if __name__ == "__main__":
    unittest.main()
