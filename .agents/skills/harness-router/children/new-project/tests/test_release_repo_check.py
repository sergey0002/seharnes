import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class ReleaseRepoCheckTest(unittest.TestCase):
    def test_detects_repository_excludes_and_respects_negation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            paths = ('.agents/skills/harness-router/SKILL.md', '.cursor/rules/harness-improvement.mdc',
                     '.cursor/mcp.json', '.doc/harnes/state/canon-paths.yaml', '.doc/web/README.md', 'AGENTS.md')
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            exclude = root / '.git/info/exclude'
            exclude.write_text('/.agents/\n/.doc/\n/AGENTS.md\n', encoding='utf-8')
            script = Path(__file__).resolve().parents[1] / 'scripts/release-repo-check.py'
            def check(path):
                return subprocess.run([sys.executable, str(script), '--root', str(path)],
                                      capture_output=True, text=True, check=False)
            failed = check(root)
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
            rows = {row['path']: row for row in json.loads(failed.stdout)['files']}
            self.assertEqual(rows[paths[0]]['status'], 'ignored')
            self.assertEqual(rows[paths[0]]['rule']['source'], '.git/info/exclude')
            self.assertEqual(rows[paths[1]]['status'], 'visible')
            exclude.write_text('/AGENTS.md\n!/AGENTS.md\n', encoding='utf-8')
            result = check(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(json.loads(result.stdout)['release_safe'])
            self.assertEqual(check(root / '.doc').returncode, 2)
            (root / paths[-1]).unlink()
            self.assertEqual(check(root).returncode, 1)


if __name__ == '__main__':
    unittest.main()
