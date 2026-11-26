"""Export safety: policy preflight, local-file preservation, path rewrite."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "harness_transfer.py"
REPO = SCRIPT.parents[6]
POLICIES = ".agents/skills/harness-router/children/harness-core/assets/policies"


def _export(source: Path, target: Path, profile: str = "developer", mode: str = "install"):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "export", "--source", str(source), "--target", str(target),
         "--profile", profile, "--mode", mode, "--skip-tools", "--skip-runtime-deps", "--yes"],
        capture_output=True, text=True, timeout=300,
    )


class ExportSafetyTest(unittest.TestCase):
    def _policy_source(self, root: Path, *, weaken: bool = False) -> Path:
        source = root / "source"
        for relative in (".doc/harnes/state/canon-paths.yaml",
                         f"{POLICIES}/skill-format.yaml", f"{POLICIES}/component-docs.yaml"):
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, path)
        if weaken:
            path = source / POLICIES / "skill-format.yaml"
            path.write_text(path.read_text(encoding="utf-8").replace("enabled: true", "enabled: false", 1),
                            encoding="utf-8")
        return source

    def test_core_missing_policy_rejected_before_target_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._policy_source(root)
            (source / POLICIES / "component-docs.yaml").unlink()
            target = root / "target"
            result = _export(source, target, profile="core")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("POLICY_MISSING", result.stdout + result.stderr)
            self.assertFalse(target.exists())

    def test_core_weakened_policy_rejected_before_target_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._policy_source(root, weaken=True)
            target = root / "target"
            result = _export(source, target, profile="core")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TRUSTED_GATE_WEAKENING", result.stdout + result.stderr)
            self.assertFalse(target.exists())

    def test_local_files_are_not_copied_and_target_local_is_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            (source / ".serena").mkdir(parents=True)
            (source / ".serena" / "project.yml").write_text('project_name: "upstream"\n', encoding="utf-8")
            (source / ".serena" / "project.local.yml").write_text("source private\n", encoding="utf-8")
            target.mkdir()
            (target / ".serena").mkdir()
            (target / ".serena" / "project.local.yml").write_text("target local\n", encoding="utf-8")
            result = _export(source, target)
            self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
            self.assertFalse((target / ".serena/project.local.yml").read_text(encoding="utf-8") == "source private\n")
            self.assertEqual((target / ".serena/project.local.yml").read_text(encoding="utf-8"), "target local\n")

    def test_path_rewrite_relocates_source_and_keeps_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            path = source / ".agents/skills/demo/main.py"
            path.parent.mkdir(parents=True)
            path.write_text(f'source = "resource"\npath = "{source}/data"\n', encoding="utf-8")
            result = _export(source, target)
            self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
            text = (target / ".agents/skills/demo/main.py").read_text(encoding="utf-8")
            self.assertIn('source = "resource"', text)
            self.assertNotIn(f'"{source}/data"', text)
            self.assertIn(str(target.resolve()), text)


if __name__ == "__main__":
    unittest.main()