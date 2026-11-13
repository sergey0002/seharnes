import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/render_policy_docs.py'
ROOT = Path(__file__).resolve().parents[6]
FILES = ('.doc/harnes/state/canon-paths.yaml',
         '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
         '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml',
         '.doc/harnes/skill-format.md', '.doc/harnes/component-docs.md')


class RenderPolicyDocsTest(unittest.TestCase):
    def fixture(self, base: Path) -> Path:
        for relative in FILES:
            destination = base / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        return base

    def run_script(self, root: Path, *args: str):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), *args],
                              capture_output=True, text=True, check=False)

    def test_check_and_write_generated_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            before = (root / '.doc/harnes/skill-format.md').read_text(encoding='utf-8')
            checked = self.run_script(root, '--check')
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            policy = root / FILES[1]
            policy.write_text(policy.read_text().replace('name_pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$"',
                                                         'name_pattern: "^[a-z]+$"'), encoding='utf-8')
            drifted = self.run_script(root, '--check')
            self.assertEqual(drifted.returncode, 1, drifted.stdout + drifted.stderr)
            self.assertIn('.doc/harnes/skill-format.md', json.loads(drifted.stdout)['drifted'])
            written = self.run_script(root, '--write')
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            self.assertEqual(self.run_script(root, '--check').returncode, 0)
            after = (root / '.doc/harnes/skill-format.md').read_text(encoding='utf-8')
            self.assertIn('`^[a-z]+$`', after)
            self.assertEqual(before.split('<!-- BEGIN POLICY')[0], after.split('<!-- BEGIN POLICY')[0])

    def test_missing_markers_fail_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            document = root / '.doc/harnes/component-docs.md'
            original = document.read_text(encoding='utf-8')
            document.write_text(original.replace('<!-- END POLICY component_docs -->', ''), encoding='utf-8')
            result = self.run_script(root, '--write')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('markers_missing', result.stdout)
            self.assertEqual(document.read_text(encoding='utf-8'),
                             original.replace('<!-- END POLICY component_docs -->', ''))


if __name__ == '__main__':
    unittest.main()
