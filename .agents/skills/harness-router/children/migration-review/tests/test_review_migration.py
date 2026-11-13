import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "review_migration.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(root: Path) -> None:
    write(root / ".cursor/rules/base.mdc", "---\nname: base\ndescription: base\nalwaysApply: false\n---\n\n# base\n")
    write(root / ".agents/rules/local.md", "---\ntrigger: model_decision\ndescription: Local rule\n---\n\n# Local rule\n\nText.\n")
    write(root / ".cursor/mcp.json", json.dumps({"mcpServers": {"mysql": {"command": "node mysql.mjs"}}}, ensure_ascii=False))
    write(root / ".doc/.rebase-mcp-backup/cursor.mcp.json", json.dumps({
        "mcpServers": {
            "laravel-boost": {"command": "php artisan boost:mcp"},
            "mysql": {"command": "old mysql"},
        }
    }, ensure_ascii=False))
    write(root / ".doc/.rebase-conflicts.json", json.dumps({
        "schema": 1, "mode": "migrate", "timestamp": "20260101-000000", "backup_dir": "",
        "overwritten": [], "target_only": [], "added": [], "counts": {"overwritten": 0},
    }, ensure_ascii=False))
    write(root / ".doc/.rebase-kit.json", json.dumps({"schema": 1, "mode": "migrate"}, ensure_ascii=False))
    sync = root / ".agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh"
    write(sync, "#!/usr/bin/env bash\nexit 0\n")


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        timeout=120,
    )


class ReviewMigrationTest(unittest.TestCase):
    def test_reports_local_rule_and_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            result = run("--root", str(root), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            rules = [item for item in payload["proposals"] if item["kind"] == "rule"]
            mcp = [item for item in payload["proposals"] if item["kind"] == "mcp"]
            self.assertTrue(any(item["name"] == "local" and item["action"] == "install" for item in rules))
            self.assertTrue(any(item["name"] == "laravel-boost" and item["action"] == "install" for item in mcp))
            self.assertTrue(any(item["name"] == "mysql" and item["action"] == "manual" for item in mcp))

    def test_apply_rules_and_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            result = run("--root", str(root), "--apply-rules", "--apply-mcp", "--yes", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            target = root / ".cursor/rules/local.mdc"
            self.assertTrue(target.is_file())
            self.assertIn("Local rule", target.read_text(encoding="utf-8"))
            config = json.loads((root / ".cursor/mcp.json").read_text(encoding="utf-8"))
            self.assertIn("laravel-boost", config["mcpServers"])
            self.assertIn("mysql", config["mcpServers"])

    def test_backup_summary_and_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            backup = root / ".doc/.rebase-backup/20260101-000000/.codex/skills/local/SKILL.md"
            write(backup, "---\nname: local\ndescription: local\n---\n\n# local\n")
            conflicts = json.loads((root / ".doc/.rebase-conflicts.json").read_text(encoding="utf-8"))
            conflicts["backup_dir"] = ".doc/.rebase-backup/20260101-000000"
            conflicts["overwritten"] = [{
                "path": ".codex/skills/local/SKILL.md",
                "category": "skill",
                "backup": ".doc/.rebase-backup/20260101-000000/.codex/skills/local/SKILL.md",
            }]
            write(root / ".doc/.rebase-conflicts.json", json.dumps(conflicts, ensure_ascii=False))

            reviewed = run("--root", str(root), "--json")
            self.assertEqual(reviewed.returncode, 0, reviewed.stdout + reviewed.stderr)
            payload = json.loads(reviewed.stdout)
            self.assertEqual(payload["backup"]["files"], 1)
            self.assertEqual(payload["backup"]["by_category"], {"skill": 1})
            self.assertEqual(payload["backup"]["mcp_files"], 1)

            removed = run("--root", str(root), "--rm-backup", "--yes", "--json")
            self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
            result = json.loads(removed.stdout)
            self.assertTrue(result["backup_removed"])
            self.assertFalse((root / ".doc/.rebase-backup/20260101-000000").exists())
            self.assertFalse((root / ".doc/.rebase-mcp-backup").exists())
            saved = json.loads((root / ".doc/.rebase-conflicts.json").read_text(encoding="utf-8"))
            self.assertTrue(saved["backup_removed"])

    def test_report_only_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            before = (root / ".cursor/mcp.json").read_text(encoding="utf-8")
            result = run("--root", str(root), "--report-only", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((root / ".cursor/rules/local.mdc").exists())
            self.assertEqual(before, (root / ".cursor/mcp.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
