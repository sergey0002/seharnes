import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'codeprism-mcp.sh'


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        scripts = self.root / '.cursor' / 'scripts'
        scripts.mkdir(parents=True)
        self.script = scripts / SCRIPT.name
        shutil.copyfile(SCRIPT, self.script)
        self.config = self.root / '.cursor' / 'mcp.json'
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        self.marker = Path(self.temp.name) / 'called'
        proxy = self.bin / 'uvx'
        proxy.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$MARKER"\n', encoding='utf-8')
        proxy.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        CODEPRISM_TARGET=str(self.root), MARKER=str(self.marker))

    def run_bridge(self, server):
        self.config.write_text(json.dumps({'mcpServers': {'codeprism': server}}), encoding='utf-8')
        return subprocess.run(['bash', str(self.script)], env=self.env, capture_output=True, text=True)

    def test_valid_endpoint_and_symlink_target(self):
        alias = Path(self.temp.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.env['CODEPRISM_TARGET'] = str(alias)
        result = self.run_bridge({'type': 'http', 'url': 'http://127.0.0.1:9132/mcp'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.marker.read_text().splitlines(),
                         ['--offline', 'mcp-proxy', '--transport', 'streamablehttp',
                          'http://127.0.0.1:9132/mcp'])

    def test_invalid_config_fails_closed(self):
        cases = [
            {'type': 'http', 'url': 'http://127.0.0.1:9132/mcp', 'disabled': True},
            {'type': 'http', 'url': 'http://127.0.0.1:9132/mcp', 'enabled': False},
            {'type': 'stdio', 'url': 'http://127.0.0.1:9132/mcp'},
            {'type': 'http'},
            {'type': 'http', 'url': 'https://127.0.0.1:9132/mcp'},
            {'type': 'http', 'url': 'http://localhost:9132/mcp'},
            {'type': 'http', 'url': 'http://127.0.0.1@evil.example/mcp'},
            {'type': 'http', 'url': 'http://127.0.0.1:99999/mcp'},
            {'type': 'http', 'url': 'http://127.0.0.1:9132/mcp\nother'},
        ]
        for server in cases:
            with self.subTest(server=server):
                result = self.run_bridge(server)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertFalse(self.marker.exists())

    def test_wrong_target_fails_closed(self):
        self.env['CODEPRISM_TARGET'] = self.temp.name
        result = self.run_bridge({'type': 'http', 'url': 'http://127.0.0.1:9132/mcp'})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_broken_json_fails_closed(self):
        self.config.write_text('{', encoding='utf-8')
        result = subprocess.run(['bash', str(self.script)], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
