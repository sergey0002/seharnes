import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rebase_project.ps1"
REPO = SCRIPT.parents[6]


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is unavailable")
class ExportUpdateCycleTest(unittest.TestCase):
    def _source(self, root: Path) -> Path:
        source = root / "source"
        (source / ".cursor").mkdir(parents=True)
        (source / ".codex").mkdir()
        (source / ".doc").mkdir()
        (source / ".tools").mkdir()
        (source / ".cursor/rules").mkdir()
        (source / ".cursor/rules/text-style.mdc").write_text(
            '---\nalwaysApply: true\n---\n# Style\n', encoding="utf-8")
        shutil.copytree(REPO / ".agents" / "skills" / "harness-router", source / ".agents" / "skills" / "harness-router")
        shutil.copytree(REPO / ".dsh", source / ".dsh", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / ".tools" / "scripts", source / ".tools" / "scripts")
        (source / ".tools" / "mcp-servers" / "php-toolchain").mkdir(parents=True)
        (source / ".tools" / "mcp-servers" / "php-toolchain" / "server.js").write_text("// stub\n", encoding="utf-8")
        (source / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
            "codeprism": {"type": "http", "url": "http://127.0.0.1:9201/mcp", "disabled": False},
            "codegraph": {"command": "codegraph-mcp"},
        }}), encoding="utf-8")
        (source / ".codex" / "config.toml").write_text(
            '[mcp_servers."codeprism"]\nurl = "http://127.0.0.1:9201/mcp"\nenabled = false\n'
        )
        (source / ".doc" / "rebase_project.md").write_text("# canon\n", encoding="utf-8")
        (source / "AGENTS.md").write_text("# Fixture project instructions\n", encoding="utf-8")
        return source

    def _run(self, source: Path, target: Path, mode: str):
        return subprocess.run(
            [
                "pwsh", "-NoProfile", "-File", str(SCRIPT),
                "-Source", str(source), "-Target", str(target), "-Mode", mode,
                "-ProjectName", "cycle_probe", "-SkipReview", "-SkipTools",
                "-SkipRuntimeDeps", "-SkipSiblingConfig", "-Yes",
            ],
            capture_output=True, text=True, check=False, timeout=600,
        )

    def test_export_then_update_keeps_target_only_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root)
            target = root / "target"

            first = self._run(source, target, "migrate")
            output = first.stdout + first.stderr
            self.assertNotIn("Exception", output)
            self.assertIn("EXPORT_REBASE_DONE", output)
            self.assertIn("Successfully Synced", output)
            self.assertIn(first.returncode, (0, 2))  # The deliberately minimal fixture lacks optional must files.
            self.assertFalse((target / '.git').exists())

            self.assertTrue((target / ".tools" / "scripts" / "node-mcp.sh").exists())
            for name in ('skill-format.yaml', 'component-docs.yaml'):
                self.assertTrue((target / '.agents/skills/harness-router/children/harness-core/assets/policies' / name).is_file())
            mcp = json.loads((target / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
            self.assertEqual(mcp["mcpServers"]["codeprism"]["url"], "http://127.0.0.1:0/mcp")
            self.assertTrue(mcp["mcpServers"]["codeprism"]["disabled"])
            codex = (target / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertNotIn(":9201", codex)

            mcp["mcpServers"]["laravel-boost"] = {"command": "php", "args": ["artisan", "boost:mcp"]}
            (target / ".cursor" / "mcp.json").write_text(json.dumps(mcp), encoding="utf-8")

            second = self._run(source, target, "update")
            second_output = second.stdout + second.stderr
            self.assertNotIn("Exception", second_output)
            self.assertIn("EXPORT_REBASE_DONE", second_output)
            self.assertIn("Successfully Synced", second_output)
            updated = json.loads((target / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
            self.assertIn("laravel-boost", updated["mcpServers"])
            self.assertEqual(updated["mcpServers"]["codeprism"]["url"], "http://127.0.0.1:0/mcp")


if __name__ == "__main__":
    unittest.main()
