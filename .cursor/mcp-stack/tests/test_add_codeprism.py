import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'add-codeprism.py'


class RegistrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp')
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.output = self.base / 'units'
        self.output.mkdir()
        self.project = self.base / 'project $percent% space'
        self.project.mkdir()
        python = self.project / '.cursor/tools/codeprism-ai/venv/bin/python'
        python.parent.mkdir(parents=True)
        python.write_text('python')
        python.chmod(0o755)
        server = self.project / '.agents/skills/codeprism/scripts/codeprism_serve.py'
        server.parent.mkdir(parents=True)
        server.write_text('server')
        self.env = dict(os.environ, HOME=str(self.home))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]

    def tearDown(self):
        self.tmp.cleanup()

    def run_registration(self, project=None, port=None, output=None):
        return subprocess.run([sys.executable, str(SCRIPT), str(project or self.project),
                               str(port or self.port), '--output-dir', str(output or self.output)],
                              text=True, capture_output=True, env=self.env)

    def test_repeat_symlink_and_changed_port(self):
        result = self.run_registration()
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = next(self.output.glob('*.service'))
        text = unit.read_text()
        self.assertIn('--transport http --port ' + str(self.port), text)
        self.assertIn('project $$percent%% space', text)
        alias = self.base / 'alias'
        alias.symlink_to(self.project)
        self.assertIn('unchanged:', self.run_registration(alias).stdout)
        self.assertNotEqual(self.run_registration(port=self.port % 65535 + 1).returncode, 0)
        self.assertEqual(unit.read_text(), text)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_conflicts_and_invalid_input(self):
        self.assertEqual(self.run_registration().returncode, 0)
        other = self.base / 'other'
        other.symlink_to(self.project, target_is_directory=True)
        unit = next(self.output.glob('*.service'))
        unit.write_text('foreign')
        self.assertNotEqual(self.run_registration(other).returncode, 0)
        self.assertEqual(unit.read_text(), 'foreign')
        self.assertNotEqual(self.run_registration(output=self.base / 'missing').returncode, 0)
        self.assertNotEqual(self.run_registration(port=65536).returncode, 0)

    def test_occupied_port(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            sock.listen()
            self.assertNotEqual(self.run_registration(port=sock.getsockname()[1]).returncode, 0)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_registered_port_conflict(self):
        self.assertEqual(self.run_registration().returncode, 0)
        other = self.base / 'other'
        other.mkdir()
        (other / '.cursor').symlink_to(self.project / '.cursor', target_is_directory=True)
        (other / '.agents').symlink_to(self.project / '.agents', target_is_directory=True)
        result = self.run_registration(other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already registered', result.stderr)
        self.assertEqual(len(list(self.output.glob('*.service'))), 1)

    def test_concurrent_repeat(self):
        command = [sys.executable, str(SCRIPT), str(self.project), str(self.port),
                   '--output-dir', str(self.output)]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, env=self.env) for _ in range(2)]
        results = [process.communicate() for process in processes]
        self.assertEqual([process.returncode for process in processes], [0, 0], results)
        self.assertEqual(len(list(self.output.glob('*.service'))), 1)

    def test_help(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--output-dir', result.stdout)


if __name__ == '__main__':
    unittest.main()
