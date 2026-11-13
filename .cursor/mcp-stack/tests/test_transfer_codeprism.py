import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


STACK = Path(__file__).resolve().parents[1]
ROOT = STACK.parent.parent
SCRIPTS = ROOT / '.agents/skills/codeprism/scripts'


class TransferTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.target = self.base / 'target'
        self.home = self.base / 'home'
        for path in (self.source / '.cursor/mcp-stack',
                     self.source / '.agents/skills/codeprism/scripts',
                     self.target, self.home):
            path.mkdir(parents=True)
        for name in ('export.sh', 'restore.sh', 'verify.sh', 'add-codeprism.py'):
            shutil.copy2(STACK / name, self.source / '.cursor/mcp-stack' / name)
        for name in ('codeprism-mcp.sh', 'codeprism_serve.py'):
            shutil.copy2(SCRIPTS / name, self.source / '.agents/skills/codeprism/scripts' / name)
        (self.source / '.cursor/mcp.json').write_text(json.dumps({'mcpServers': {
            'codeprism': {'type': 'http', 'url': 'http://127.0.0.1:9201/mcp', 'disabled': False},
            'other': {'type': 'stdio', 'command': 'example'},
        }}))
        self.env = dict(os.environ, HOME=str(self.home))
        self.archive = self.base / 'stack.tar.gz'

    def run_script(self, script, *args):
        return subprocess.run(['bash', str(STACK / script), *map(str, args)],
                              env=self.env, text=True, capture_output=True)

    def export(self):
        result = subprocess.run(['bash', str(self.source / '.cursor/mcp-stack/export.sh'), str(self.archive)],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_export_restore_disables_foreign_endpoint_and_preserves_files(self):
        self.export()
        with tarfile.open(self.archive) as archive:
            names = set(archive.getnames())
        for name in ('./config/mcp-stack/add-codeprism.py', './config/scripts/codeprism/codeprism-mcp.sh',
                     './config/scripts/codeprism/codeprism_serve.py'):
            self.assertIn(name, names)
        existing = self.target / '.agents/skills/codeprism/scripts/codeprism-mcp.sh'
        existing.parent.mkdir(parents=True)
        existing.write_text('existing file\n')
        result = self.run_script('restore.sh', self.archive, self.target, '--no-start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CodePrism disabled', result.stderr)
        config = json.loads((self.target / '.cursor/mcp.json').read_text())['mcpServers']
        self.assertTrue(config['codeprism']['disabled'])
        self.assertNotIn('url', config['codeprism'])
        self.assertEqual(config['other']['command'], 'example')
        self.assertEqual(existing.read_text(), 'existing file\n')
        self.assertTrue((self.target / '.agents/skills/codeprism/scripts/codeprism_serve.py').is_file())
        self.assertTrue((self.target / '.cursor/mcp-stack/add-codeprism.py').is_file())
        second = self.run_script('restore.sh', self.archive, self.target, '--no-start')
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('refusing to overwrite', second.stderr)
        self.assertEqual(existing.read_text(), 'existing file\n')

    def test_verify_never_claims_codeprism_checked(self):
        self.export()
        result = self.run_script('restore.sh', self.archive, self.target, '--no-start')
        self.assertEqual(result.returncode, 0, result.stderr)
        fakebin = self.base / 'bin'
        fakebin.mkdir()
        for name in ('systemctl', 'curl', 'sleep'):
            path = fakebin / name
            path.write_text('#!/bin/sh\nexit 1\n')
            path.chmod(0o755)
        self.env['PATH'] = str(fakebin) + os.pathsep + self.env['PATH']
        result = self.run_script('verify.sh', self.target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CodePrism не проверен', result.stdout)
        config_path = self.target / '.cursor/mcp.json'
        config = json.loads(config_path.read_text())
        config['mcpServers']['codeprism'] = {'type': 'http', 'url': 'http://127.0.0.1:9202/mcp', 'disabled': False}
        config_path.write_text(json.dumps(config))
        result = self.run_script('verify.sh', self.target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CodePrism не проверен', result.stdout)


if __name__ == '__main__':
    unittest.main()
