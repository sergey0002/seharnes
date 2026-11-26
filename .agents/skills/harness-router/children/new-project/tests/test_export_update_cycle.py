"""Export cycle: install into an empty project, then update an installed kit."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "harness_transfer.py"


def _run(source: Path, target: Path, mode: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "export", "--source", str(source), "--target", str(target),
         "--profile", "developer", "--mode", mode, "--skip-tools", "--skip-runtime-deps", "--yes"],
        capture_output=True, text=True, check=False, timeout=300,
    )


class ExportUpdateCycleTest(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        source = root / "source"
        (source / ".cursor").mkdir(parents=True)
        (source / ".doc" / "harnes").mkdir(parents=True)
        (source / ".doc" / "harnes" / "doc_rules.md").write_text("# rules\n", encoding="utf-8")
        (source / "AGENTS.md").write_text("# Fixture project instructions\n", encoding="utf-8")
        (source / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
            "codeprism": {"type": "http", "url": "http://127.0.0.1:9201/mcp", "disabled": False},
            "codegraph": {"command": "codegraph-mcp"},
        }}, indent=2), encoding="utf-8")
        return source

    def test_install_then_update_keeps_target_only_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            target = root / "target"

            first = _run(source, target, "install")
            self.assertIn(first.returncode, (0, 2), first.stdout + first.stderr)
            servers = json.loads((target / ".cursor/mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertIn("codegraph", servers)
            self.assertTrue(servers["codeprism"]["disabled"])
            self.assertEqual(servers["codeprism"]["url"], "http://127.0.0.1:0/mcp")

            local = json.loads((target / ".cursor/mcp.json").read_text(encoding="utf-8"))
            local["mcpServers"]["project-only"] = {"command": "project-mcp"}
            (target / ".cursor/mcp.json").write_text(json.dumps(local, indent=2), encoding="utf-8")

            second = _run(source, target, "update")
            self.assertIn(second.returncode, (0, 2), second.stdout + second.stderr)
            merged = json.loads((target / ".cursor/mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            self.assertIn("project-only", merged)
            self.assertIn("codegraph", merged)
            self.assertTrue((target / ".doc/.rebase-report.md").is_file())
            marker = json.loads((target / ".doc/.rebase-kit.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["mode"], "update")


if __name__ == "__main__":
    unittest.main()