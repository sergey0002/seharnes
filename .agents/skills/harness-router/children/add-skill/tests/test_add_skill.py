import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def skill_md(name: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: test skill for lifecycle checks\n"
        "---\n\n"
        f"# {name}\n"
    )


def make_project(root: Path) -> None:
    write(root / ".agents/skills/base/SKILL.md", skill_md("base"))
    write(root / ".agents/skills/base/README.md", "# base\n")
    write(root / ".agents/skills/base/skill.json", json.dumps({
        "schema": 1, "name": "base", "kind": "leaf", "entry": "SKILL.md",
        "readme": "README.md",
        "resources": {"scripts": [], "references": [], "assets": []},
        "tests": [], "children": [], "dependencies": {"skills": [], "project": []},
        "generated": [],
    }))
    write(root / ".codex/skills/local-helper/SKILL.md", skill_md("local-helper"))
    write(root / ".codex/skills/local-helper/scripts/run.sh", "#!/bin/sh\necho ok\n")
    write(root / ".doc/harnes/skills/README.md", "# Скилы\n\n## Полный список карточек\n\n- [base.md](./base.md)\n")
    write(root / ".doc/harnes/state/02-skills.md", "# Скилы\n\n## 1. Базовые\n\n| Скил | Карточка | Канон |\n|---|---|---|\n| base | [base](../skills/base.md) | `base` |\n\n## Реестр и валидаторы\n\nтекст\n")
    write(root / ".doc/harnes/index.md", "# Индекс\n\n| Группа | Карточки |\n|---|---|\n| Мета | [base](./skills/base.md) |\n\n### Группировка менеджеров\n\nтекст\n")
    write(root / ".doc/harnes/skills/base.md", "# base\n")
    write(root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json",
          json.dumps({"version": 1, "components": {}}, ensure_ascii=False))


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
        timeout=120,
    )


class AddSkillTest(unittest.TestCase):
    def test_qwen_discovery_wrapper_is_not_a_local_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            canonical = ".agents/skills/router/children/demo/SKILL.md"
            write(root / canonical, skill_md("demo"))
            wrapper = root / ".qwen/skills/demo/SKILL.md"
            write(wrapper, f"<!-- generated discovery wrapper; do not edit -->\nRead `{canonical}` in full\n")
            receipt = root / ".doc/skil_data/environment-sync/discovery.json"
            write(receipt, json.dumps({wrapper.relative_to(root).as_posix(): hashlib.sha256(wrapper.read_bytes()).hexdigest()}))

            def collisions():
                result = run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                return [item["path"] for item in json.loads(result.stdout)["skills"]["name_collision"]]

            self.assertNotIn(".qwen/skills/demo", collisions())
            wrapper.write_text(wrapper.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
            self.assertIn(".qwen/skills/demo", collisions())
            write(receipt, json.dumps({wrapper.relative_to(root).as_posix(): hashlib.sha256(wrapper.read_bytes()).hexdigest()}))
            write(wrapper.parent / "custom.txt", "local data")
            self.assertIn(".qwen/skills/demo", collisions())

    def test_scan_detects_view_local_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            baseline = run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--write-baseline")
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            scan = run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--json")
            self.assertEqual(scan.returncode, 0, scan.stderr)
            payload = json.loads(scan.stdout)
            ids = [item["id"] for item in payload["skills"]["view_local"]]
            self.assertIn("local-helper", ids)
            self.assertIn("local-helper", payload["installable"])

    def test_package_view_skill_is_not_installable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--write-baseline")
            import shutil
            shutil.rmtree(root / ".agents/skills/base")
            write(root / ".qoder/skills/base/SKILL.md", skill_md("base"))
            scan = run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--json")
            self.assertEqual(scan.returncode, 0, scan.stderr)
            payload = json.loads(scan.stdout)
            self.assertEqual([item["id"] for item in payload["skills"]["package_view"]], ["base"])
            self.assertNotIn("base", payload["installable"])

    def test_add_creates_canon_docs_and_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--write-baseline")
            result = run(
                SCRIPTS / "add_skill.py", "--root", str(root), "--name", "local-helper",
                "--from", "codex", "--yes", "--no-sync", "--no-validate",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            canon = root / ".agents/skills/local-helper"
            self.assertTrue((canon / "SKILL.md").is_file())
            self.assertTrue((canon / "README.md").is_file())
            self.assertTrue((canon / "skill.json").is_file())
            self.assertFalse((root / ".doc/harnes/skills/local-helper.md").exists())
            state = (root / ".doc/harnes/state/02-skills.md").read_text(encoding="utf-8")
            self.assertIn("../../../.agents/skills/local-helper/README.md", state)
            self.assertTrue((root / ".doc/harnes/state/../../../.agents/skills/local-helper/README.md").resolve().is_file())
            self.assertIn("../../.agents/skills/local-helper/README.md", (root / ".doc/harnes/index.md").read_text(encoding="utf-8"))
            registry = json.loads((root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json").read_text(encoding="utf-8"))
            self.assertIn("local-helper", registry["components"])

    def test_dry_run_does_not_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            run(SCRIPTS / "scan_local_skills.py", "--root", str(root), "--write-baseline")
            result = run(
                SCRIPTS / "add_skill.py", "--root", str(root), "--name", "local-helper",
                "--from", "codex", "--dry-run", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".agents/skills/local-helper").exists())


if __name__ == "__main__":
    unittest.main()
