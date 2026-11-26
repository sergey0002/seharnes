"""Export replaces the CodePrism address with a local placeholder and disables it."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "harness_transfer.py"


class CodePrismExportTest(unittest.TestCase):
    def test_codeprism_is_disabled_with_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            source.mkdir()
            (source / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")
            (source / ".cursor").mkdir()
            (source / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
                "codeprism": {"type": "http", "url": "http://127.0.0.1:9201/mcp", "disabled": False},
            }}, indent=2), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "export", "--source", str(source),
                 "--target", str(target), "--profile", "developer", "--mode", "install",
                 "--skip-tools", "--skip-runtime-deps", "--yes"],
                capture_output=True, text=True, check=False, timeout=300,
            )
            self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
            servers = json.loads((target / ".cursor/mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertTrue(servers["codeprism"]["disabled"])
            self.assertEqual(servers["codeprism"]["url"], "http://127.0.0.1:0/mcp")
            self.assertTrue((target / "EXPORT_NEXT_STEPS.md").is_file())


if __name__ == "__main__":
    unittest.main()