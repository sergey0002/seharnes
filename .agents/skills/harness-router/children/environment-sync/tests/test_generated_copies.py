import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
VERIFY = SCRIPTS / 'verify_generated_copies.py'
COMPACT = SCRIPTS / 'compact_agent_views.py'
ROOT = Path(__file__).resolve().parents[6]


def run(script: Path, *args: str):
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, check=False)


class GeneratedCopiesTest(unittest.TestCase):
    def fixture(self, base: Path) -> Path:
        shutil.copytree(ROOT / '.agents/skills', base / '.agents/skills')
        return base

    def test_full_copy_is_reported_and_compact_removes_generated_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            skill = root / '.agents/skills/git/SKILL.md'
            (root / '.qwen/skills/git').mkdir(parents=True)
            shutil.copyfile(skill, root / '.qwen/skills/git/SKILL.md')
            checked = run(VERIFY, '--root', str(root))
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertIn('stale full skill copy', checked.stdout)
            (root / '.qwen/skills/git/SKILL.md').write_text(
                '---\nname: "git"\ndescription: "x"\n---\n\n<!-- generated discovery wrapper; do not edit -->\n'
                'Read `.agents/skills/git/SKILL.md`.\n', encoding='utf-8')
            self.assertEqual(run(VERIFY, '--root', str(root)).returncode, 0)
            (root / '.qoder/skills/git').mkdir(parents=True)
            shutil.copyfile(skill, root / '.qoder/skills/git/SKILL.md')
            pending = run(COMPACT, '--root', str(root), '--check')
            self.assertEqual(pending.returncode, 1, pending.stdout + pending.stderr)
            applied = run(COMPACT, '--root', str(root), '--apply', '--force')
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertFalse((root / '.qwen/skills').exists())
            self.assertFalse((root / '.qoder/skills').exists())
            self.assertTrue((root / '.agents/skills/git/SKILL.md').is_file())

    def test_compact_strips_agents_bootstrap_and_removes_dsh_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            (root / 'DSH-RULES.md').write_text('generated rules\n', encoding='utf-8')
            (root / 'AGENTS.md').write_text(
                '# Local\n\nkeep me\n\n'
                '<!-- BEGIN HARNESS BOOTSTRAP: generated; edit .cursor/rules -->\n'
                'generated\n<!-- END HARNESS BOOTSTRAP -->\n', encoding='utf-8')
            pending = run(COMPACT, '--root', str(root), '--check')
            self.assertEqual(pending.returncode, 1, pending.stdout + pending.stderr)
            self.assertIn('AGENTS.md#bootstrap', pending.stdout)
            applied = run(COMPACT, '--root', str(root), '--apply')
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertFalse((root / 'DSH-RULES.md').exists())
            text = (root / 'AGENTS.md').read_text(encoding='utf-8')
            self.assertIn('keep me', text)
            self.assertNotIn('BEGIN HARNESS BOOTSTRAP', text)

    def test_compact_refuses_modified_qoder_tree_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            (root / '.qoder/skills/git').mkdir(parents=True)
            (root / '.qoder/skills/git/SKILL.md').write_text('local edit\n', encoding='utf-8')
            refused = run(COMPACT, '--root', str(root), '--apply')
            self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
            self.assertIn('does not match', refused.stdout)
            forced = run(COMPACT, '--root', str(root), '--apply', '--force')
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            self.assertFalse((root / '.qoder/skills').exists())


if __name__ == '__main__':
    unittest.main()
