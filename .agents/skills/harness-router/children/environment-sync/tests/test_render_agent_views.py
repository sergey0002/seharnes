import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/render_agent_views.py'
ROOT = Path(__file__).resolve().parents[6]


class RenderAgentViewsTest(unittest.TestCase):
    def test_compact_and_regenerate_all_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.cursor/rules').mkdir(parents=True)
            (root / '.cursor/rules/test.mdc').write_text('---\nalwaysApply: true\n---\nRule\n')
            (root / '.cursor/mcp.json').write_text('{"mcpServers": {}}')
            (root / '.agents/skills').mkdir(parents=True)
            (root / 'AGENTS.md').write_text('# Local\n')
            def run(script, *args, code=0):
                result = subprocess.run([sys.executable, str(script), '--root', str(root), *args],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
            run(SCRIPT)
            run(SCRIPT, '--check')
            compact = SCRIPT.with_name('compact_agent_views.py')
            run(compact, '--check', code=1)
            run(compact, '--apply')
            run(compact, '--check')
            self.assertTrue((root / '.cursor/rules/test.mdc').is_file())
            self.assertNotIn('BEGIN HARNESS BOOTSTRAP', (root / 'AGENTS.md').read_text())
            run(SCRIPT)
            run(SCRIPT, '--check')

    def test_enable_disable_check_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / '.agents/skills/harness-router/children/harness-core/assets/environments.json'
            registry.parent.mkdir(parents=True)
            (root / '.cursor/rules').mkdir(parents=True)
            (root / '.cursor/rules/test.mdc').write_text('---\nalwaysApply: true\n---\nRule\n')
            (root / '.cursor/mcp.json').write_text('{"mcpServers":{"demo":{"type":"stdio","command":"demo"}}}')
            (root / 'AGENTS.md').write_text('# Local\n')
            source = SCRIPT.parents[2] / 'harness-core/assets/environments.json'
            data = json.loads(source.read_text())
            for row in data['environments']:
                row['enabled'] = row['id'] in ('cursor', 'opencode')
            registry.write_text(json.dumps(data))
            def run(*args):
                return subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), *args],
                                      capture_output=True, text=True, timeout=30)
            write = run()
            self.assertEqual(write.returncode, 0, write.stdout + write.stderr)
            config = root / 'opencode.json'
            self.assertTrue(config.is_file())
            local = root / '.opencode/rules/local.md'
            local.write_text('authored rule\n')
            payload = json.loads(config.read_text())
            payload['theme'] = 'local'
            config.write_text(json.dumps(payload))
            for row in data['environments']:
                if row['id'] == 'opencode':
                    row['enabled'] = False
                    row['generated'] = ['AGENTS.md']
                    row['generator'] = 'not-a-trusted-generator.py'
            registry.write_text(json.dumps(data))
            self.assertNotEqual(run('--check').returncode, 0)
            self.assertTrue(config.is_file())
            drifted = json.loads(config.read_text())
            drifted['mcp']['servers']['demo']['command'] = ['local-demo']
            config.write_text(json.dumps(drifted))
            refused = run()
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('local changes or drift', refused.stdout)
            self.assertEqual(json.loads(config.read_text()), drifted)
            self.assertTrue((local.parent / 'test.md').is_file())
            config.write_text(json.dumps(payload))
            write = run()
            self.assertEqual(write.returncode, 0, write.stdout + write.stderr)
            retained = json.loads(config.read_text())
            self.assertEqual(retained['theme'], 'local')
            self.assertNotIn('instructions', retained)
            self.assertNotIn('mcp', retained)
            self.assertFalse((local.parent / 'test.md').exists())
            self.assertEqual(local.read_text(), 'authored rule\n')
            self.assertIn('# Local', (root / 'AGENTS.md').read_text())
            self.assertTrue((root / '.cursor/rules/test.mdc').is_file())
            check = run('--check')
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            again = run()
            self.assertEqual(json.loads(again.stdout)['cleanup']['removed'], [])
            for row in data['environments']:
                if row['id'] == 'opencode':
                    row['enabled'] = True
            registry.write_text(json.dumps(data))
            local.unlink()  # The enabled generator owns the rules tree.
            restored = run()
            self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
            self.assertTrue((local.parent / 'test.md').is_file())
            self.assertEqual(json.loads(config.read_text())['theme'], 'local')

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
