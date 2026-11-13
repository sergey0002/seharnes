import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from platform_ops import path_is_local, spawn_detached, terminate


class PlatformOpsTest(unittest.TestCase):
    def test_spawn_writes_output_and_returns_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout, stderr = root / 'out.log', root / 'err.log'
            pid = spawn_detached([sys.executable, '-c', 'print("started")'], root, stdout, stderr)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and b'started' not in stdout.read_bytes():
                time.sleep(0.05)
            self.assertIn(b'started', stdout.read_bytes())
            self.assertEqual(stderr.read_bytes(), b'')
            self.assertGreater(pid, 1)

    def test_terminate_stops_detached_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pid = spawn_detached([sys.executable, '-c', 'import time; time.sleep(60)'],
                                 root, root / 'out.log', root / 'err.log')
            time.sleep(0.2)
            self.assertTrue(terminate(pid))
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_invalid_command_and_paths_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ([], [''], [sys.executable, 'bad\0arg']):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    spawn_detached(command, root, root / 'out.log', root / 'err.log')
            self.assertTrue(path_is_local(root))

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_linked_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / 'real'
            real.mkdir()
            link = root / 'link'
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                spawn_detached([sys.executable, '-c', 'print(1)'], link, root / 'out.log', root / 'err.log')


if __name__ == '__main__':
    unittest.main()
