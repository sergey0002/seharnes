import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/render_agent_views.py'
ROOT = Path(__file__).resolve().parents[6]


class RenderAgentViewsTest(unittest.TestCase):
    def test_check_mode_on_installed_harness(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(ROOT), '--check'],
                                capture_output=True, text=True, check=False, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['status'], 'passed')
        self.assertEqual(payload['mode'], 'check')
        self.assertGreaterEqual(len(payload['steps']), 4)

    def test_missing_root_fails_without_writing(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(ROOT / 'missing-root')],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
