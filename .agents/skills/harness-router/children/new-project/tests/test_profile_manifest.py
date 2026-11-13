import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/profile_manifest.py'
ROOT = Path(__file__).resolve().parents[6]


class ProfileManifestTest(unittest.TestCase):
    def build(self, profile: str) -> dict:
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(ROOT), '--profile', profile],
                                capture_output=True, text=True, check=False, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_core_keeps_runtime_and_policy_and_drops_task_content(self):
        core = self.build('core')
        developer = self.build('developer')
        project = self.build('project')
        self.assertLess(core['count'], developer['count'])
        self.assertTrue(any('assets/policies/component-docs.yaml' in path for path in core['files']))
        self.assertIn('.doc/harnes/state/26-tools.md', core['files'])
        self.assertFalse(any('gototask' in path for path in core['files']))
        self.assertTrue(any('gototask' in path for path in developer['files']))
        self.assertGreater(core['excluded_count'], 0)
        self.assertEqual(developer['excluded_count'], 0)
        self.assertEqual(project['count'], developer['count'])


if __name__ == '__main__':
    unittest.main()
