#!/usr/bin/env python3
"""Tests for DSH kit migration and its wiring in sync/rebase/smoke."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
HELPER = ROOT / ".agents" / "skills" / "harness-router" / "children" / "new-project" / "scripts" / "copy-dsh-kit.ps1"
REBASE = ROOT / ".agents" / "skills" / "harness-router" / "children" / "new-project" / "scripts" / "rebase_project.ps1"
SYNC = ROOT / ".agents" / "skills" / "harness-router" / "children" / "environment-sync" / "scripts" / "sync-agent-views.sh"
SMOKE = ROOT / ".dsh" / "scripts" / "smoke.sh"


def find_pwsh() -> str | None:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (Path.home() / ".local" / "pwsh" / "pwsh", Path("/snap/bin/pwsh")):
        if candidate.is_file():
            return str(candidate)
    return None


def write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_source(root: Path) -> Path:
    dsh = root / ".dsh"
    write(dsh / "skills" / "dsh-router" / "SKILL.md",
          "---\nname: dsh-router\ndescription: test router\n---\n")
    write(dsh / "skills" / "dsh-router" / "README.md", "# test router\n")
    write(dsh / "skills" / "dsh-router" / "skill.json",
          '{"schema": 1, "name": "dsh-router", "kind": "orchestrator", "entry": "SKILL.md", "readme": "README.md", "resources": {"scripts": [], "references": [], "assets": []}, "tests": [], "children": [], "dependencies": {"skills": [], "project": []}, "generated": []}\n')
    write(dsh / "skills" / "__pycache__" / "router.pyc", "cache")
    write(dsh / "adapters" / "prepare-plan-digest.md", "# digest\n")
    write(dsh / "adapters" / "shell.md", "# shell\n")
    write(dsh / "scripts" / "run-ps1.sh", "#!/usr/bin/env bash\n")
    write(dsh / "scripts" / "smoke.sh", "#!/usr/bin/env bash\n")
    write(dsh / "scripts" / "__pycache__" / "cache.pyc", "cache")
    write(dsh / "tests" / "test_stage_artifacts.py", "# test\n")
    write(dsh / "models.overlay.json", '{"subagent": {"model": "test"}}\n')
    files = [
        ".dsh/adapters/prepare-plan-digest.md",
        ".dsh/adapters/shell.md",
        ".dsh/models.overlay.json",
        ".dsh/scripts/run-ps1.sh",
        ".dsh/scripts/smoke.sh",
        ".dsh/skills/dsh-router/README.md",
        ".dsh/skills/dsh-router/SKILL.md",
        ".dsh/skills/dsh-router/skill.json",
        ".dsh/tests/test_stage_artifacts.py",
    ]
    write(dsh / "kit.manifest.json", json.dumps({"schema": 1, "files": files}, indent=2) + "\n")
    write(dsh / "models.overlay.json.bak-20260101", "backup\n")
    write(dsh / "project.patch.yml", "generated: true\n")
    write(root / "DSH-RULES.md", "# generated\n")
    return dsh


@unittest.skipUnless(find_pwsh(), "PowerShell is not available")
class DshKitCopyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="dsh-kit-"))
        self.source = self.tmp / "source"
        self.target = self.tmp / "target"
        self.source.mkdir()
        self.target.mkdir()
        make_source(self.source)
        self.pwsh = find_pwsh()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_helper(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(HELPER), "-Source", str(self.source),
             "-Target", str(self.target), *extra],
            capture_output=True, text=True, timeout=120,
        )

    def test_copies_portable_kit_and_skips_generated(self) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dsh = self.target / ".dsh"
        self.assertTrue((dsh / "skills" / "dsh-router" / "SKILL.md").is_file())
        self.assertTrue((dsh / "skills" / "dsh-router" / "README.md").is_file())
        self.assertTrue((dsh / "skills" / "dsh-router" / "skill.json").is_file())
        self.assertTrue((dsh / "kit.manifest.json").is_file())
        self.assertTrue((dsh / "adapters" / "prepare-plan-digest.md").is_file())
        self.assertTrue((dsh / "scripts" / "run-ps1.sh").is_file())
        self.assertTrue((dsh / "scripts" / "smoke.sh").is_file())
        self.assertTrue((dsh / "tests" / "test_stage_artifacts.py").is_file())
        self.assertTrue((dsh / "models.overlay.json").is_file())
        self.assertFalse((dsh / "project.patch.yml").exists())
        self.assertFalse((dsh / "models.overlay.json.bak-20260101").exists())
        self.assertFalse((self.target / "DSH-RULES.md").exists())
        self.assertFalse((dsh / "skills" / "__pycache__").exists())
        self.assertFalse((dsh / "scripts" / "__pycache__").exists())

    def test_check_passes_then_fails_when_kit_is_incomplete(self) -> None:
        self.assertEqual(self.run_helper().returncode, 0)
        check = self.run_helper("-Check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        (self.target / ".dsh" / "scripts" / "smoke.sh").unlink()
        broken = self.run_helper("-Check")
        self.assertEqual(broken.returncode, 1, broken.stdout + broken.stderr)

    def test_check_does_not_write(self) -> None:
        before = sorted(p.relative_to(self.target) for p in self.target.rglob("*"))
        result = self.run_helper("-Check")
        after = sorted(p.relative_to(self.target) for p in self.target.rglob("*"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before, after)

    def test_strict_sync_and_check_detect_all_file_changes(self) -> None:
        self.assertEqual(self.run_helper().returncode, 0)
        dsh = self.target / '.dsh'
        write(dsh / 'scripts' / 'extra' / 'local.txt', 'local')
        write(dsh / 'project.patch.yml', 'keep')
        self.assertEqual(self.run_helper('-Check').returncode, 1)
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertFalse((dsh / 'scripts' / 'extra').exists())
        self.assertEqual((dsh / 'project.patch.yml').read_text(), 'keep')
        write(dsh / 'scripts' / 'smoke.sh', 'modified')
        self.assertEqual(self.run_helper('-Check').returncode, 1)
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertEqual(self.run_helper('-Check').returncode, 0)

    def test_missing_source_fails_before_target_changes(self) -> None:
        self.assertEqual(self.run_helper().returncode, 0)
        marker = self.target / '.dsh' / 'scripts' / 'local.txt'
        write(marker, 'keep')
        shutil.rmtree(self.source / '.dsh' / 'tests')
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertNotEqual(self.run_helper('-Check').returncode, 0)
        self.assertEqual(marker.read_text(), 'keep')

    def test_missing_manifest_file_fails_closed(self) -> None:
        (self.source / '.dsh' / 'scripts' / 'smoke.sh').unlink()
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertFalse((self.target / '.dsh').exists())

    def test_same_source_and_target_are_rejected(self) -> None:
        result = subprocess.run(
            [self.pwsh, '-NoProfile', '-File', str(HELPER), '-Source', str(self.source),
             '-Target', str(self.source / '.')], capture_output=True, text=True, timeout=120,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.source / '.dsh' / 'scripts' / 'smoke.sh').is_file())

    def test_linked_root_and_nested_target_are_rejected(self) -> None:
        alias = self.tmp / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        for target in (alias, self.source / 'nested'):
            result = subprocess.run(
                [self.pwsh, '-NoProfile', '-File', str(HELPER), '-Source', str(self.source),
                 '-Target', str(target)], capture_output=True, text=True, timeout=120,
            )
            self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.source / '.dsh' / 'scripts' / 'smoke.sh').is_file())

    def test_managed_symlink_is_rejected(self) -> None:
        outside = self.tmp / 'outside'
        outside.mkdir()
        write(outside / 'keep', 'safe')
        (self.target / '.dsh').mkdir()
        (self.target / '.dsh' / 'scripts').symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertEqual((outside / 'keep').read_text(), 'safe')


class DshKitWiringTest(unittest.TestCase):
    def test_rebase_copies_kit_and_excludes_it_from_git(self) -> None:
        text = REBASE.read_text(encoding="utf-8")
        self.assertIn("copy-dsh-kit.ps1", text)
        self.assertIn(".dsh\\skills\\dsh-router\\SKILL.md", text)
        self.assertIn("/.dsh/", text)
        self.assertIn("/DSH-RULES.md", text)
        block = text.split('Write-Step "Копирование DSH kit (.dsh)"', 1)[1].split('if (-not $SkipTools)', 1)[0]
        self.assertIn('throw "DSH kit copy failed', block)
        self.assertIn('throw "DSH kit check failed', block)
        self.assertIn('throw "DSH kit helper not found', block)

    def test_sync_checks_dsh_outputs(self) -> None:
        text = SYNC.read_text(encoding="utf-8")
        self.assertIn('verify_step "dsh"', text)
        self.assertIn("generate-dsh-config.py", text)
        self.assertIn("--check", text)

    def test_smoke_uses_dynamic_skill_count(self) -> None:
        text = SMOKE.read_text(encoding="utf-8")
        self.assertIn("no redundant Codex mirror", text)
        self.assertNotIn('find .codex/skills', text)
        self.assertNotIn("expected 22", text)
        self.assertIn("dsh kit:", text)


if __name__ == "__main__":
    unittest.main()
