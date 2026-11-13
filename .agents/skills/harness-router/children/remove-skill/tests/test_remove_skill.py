import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REMOVE_ROOT = Path(__file__).resolve().parents[1]
ADD_ROOT = REMOVE_ROOT.parent / "add-skill"


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


def install_local(root: Path) -> None:
    run(ADD_ROOT / "scripts/scan_local_skills.py", "--root", str(root), "--write-baseline")
    result = run(
        ADD_ROOT / "scripts/add_skill.py", "--root", str(root), "--name", "local-helper",
        "--from", "codex", "--yes", "--no-sync", "--no-validate",
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


class RemoveSkillTest(unittest.TestCase):
    def test_remove_cleans_canon_views_and_docs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            install_local(root)
            self.assertTrue((root / ".agents/skills/local-helper").is_dir())
            result = run(
                REMOVE_ROOT / "scripts/remove_skill.py", "--root", str(root),
                "--name", "local-helper", "--yes", "--no-sync", "--no-validate",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((root / ".agents/skills/local-helper").exists())
            self.assertFalse((root / ".codex/skills/local-helper").exists())
            self.assertFalse((root / ".doc/harnes/skills/local-helper.md").exists())
            registry = json.loads((root / ".agents/skills/harness-router/children/improvement/scripts/component_registry.json").read_text(encoding="utf-8"))
            self.assertNotIn("local-helper", registry["components"])
            self.assertNotIn("local-helper", (root / ".doc/harnes/skills/README.md").read_text(encoding="utf-8"))
            self.assertNotIn("Локальные скилы проекта", (root / ".doc/harnes/state/02-skills.md").read_text(encoding="utf-8"))

    def test_dry_run_keeps_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            install_local(root)
            result = run(
                REMOVE_ROOT / "scripts/remove_skill.py", "--root", str(root),
                "--name", "local-helper", "--dry-run", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".agents/skills/local-helper").is_dir())

    def test_unknown_skill_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_project(root)
            result = run(
                REMOVE_ROOT / "scripts/remove_skill.py", "--root", str(root),
                "--name", "missing-skill", "--yes", "--no-sync", "--no-validate",
            )
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
