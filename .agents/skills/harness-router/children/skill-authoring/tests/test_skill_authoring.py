import json
import shutil
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
        "description: test skill for authoring checks\n"
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
    write(root / ".doc/harnes/skills/README.md", "# Скилы\n\n## Полный список карточек\n\n- [base.md](./base.md)\n")
    write(root / ".doc/harnes/skills/base.md", "# base\n")
    write(root / ".doc/harnes/state/02-skills.md", "# Скилы\n\n## 1. Базовые\n\n| Скил | Карточка | Канон |\n|---|---|---|\n| base | [base](../skills/base.md) | `base` |\n\n## Реестр и валидаторы\n\nтекст\n")
    write(root / ".doc/harnes/index.md", "# Индекс\n\n| Группа | Карточки |\n|---|---|\n| Мета | [base](./skills/base.md) |\n\n### Группировка менеджеров\n\nтекст\n")
    write(root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json",
          json.dumps({"version": 1, "components": {}}, ensure_ascii=False))
    shutil.copytree(
        SKILL_ROOT.parent / "add-skill",
        root / ".agents/skills/harness-router/children/add-skill",
    )


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
        timeout=120,
    )


class SkillAuthoringTest(unittest.TestCase):
    def test_create_then_audit_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            created = run(
                SCRIPTS / "create_skill.py", "--root", str(root), "--name", "new-skill",
                "--description", "New skill for fixtures", "--no-validate", "--json",
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertTrue((root / ".agents/skills/new-skill/SKILL.md").is_file())
            self.assertTrue((root / ".doc/harnes/skills/new-skill.md").is_file())
            registry = json.loads((root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json").read_text(encoding="utf-8"))
            self.assertIn("new-skill", registry["components"])

            audited = run(SCRIPTS / "audit_skill.py", "--root", str(root), "--name", "new-skill", "--json")
            self.assertEqual(audited.returncode, 0, audited.stdout + audited.stderr)
            payload = json.loads(audited.stdout)
            self.assertEqual(payload["status"], "passed", payload)

    def test_audit_detects_broken_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            write(root / ".agents/skills/broken/SKILL.md", skill_md("broken"))
            audited = run(SCRIPTS / "audit_skill.py", "--root", str(root), "--name", "broken", "--json")
            self.assertEqual(audited.returncode, 1)
            payload = json.loads(audited.stdout)
            errors = " ".join(payload["skills"][0]["errors"])
            self.assertIn("README.md", errors)
            self.assertIn("skill.json", errors)

    def test_dry_run_does_not_create(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            result = run(
                SCRIPTS / "create_skill.py", "--root", str(root), "--name", "dry-skill",
                "--dry-run", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((root / ".agents/skills/dry-skill").exists())


if __name__ == "__main__":
    unittest.main()
