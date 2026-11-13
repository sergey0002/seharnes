import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_process_lock import ProcessLock


class ProcessLockTest(unittest.TestCase):
    def test_excludes_other_process_then_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / 'lock'
            lib = str(Path(__file__).resolve().parents[1] / 'scripts/lib')
            code = ('import sys; sys.path.insert(0,sys.argv[1]); '
                    'from transfer_process_lock import ProcessLock; '
                    'x=ProcessLock(sys.argv[2]); x.acquire(); x.release()')
            with ProcessLock(lock_path):
                blocked = subprocess.run([sys.executable, '-c', code, lib, str(lock_path)],
                                         capture_output=True, timeout=15)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn(b'process lock is busy', blocked.stderr)
            allowed = subprocess.run([sys.executable, '-c', code, lib, str(lock_path)],
                                     capture_output=True, timeout=15)
            self.assertEqual(allowed.returncode, 0, allowed.stderr.decode(errors='replace'))

    def test_process_exit_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock'
            lib = str(Path(__file__).resolve().parents[1] / 'scripts/lib')
            code = ('import os,sys; sys.path.insert(0,sys.argv[1]); '
                    'from transfer_process_lock import ProcessLock; '
                    'x=ProcessLock(sys.argv[2]); x.acquire(); os._exit(17)')
            child = subprocess.run([sys.executable, '-c', code, lib, str(path)], timeout=15)
            self.assertEqual(child.returncode, 17)
            with ProcessLock(path):
                pass

    def test_hardlink_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original, link = root / 'original', root / 'lock'
            original.write_bytes(b'')
            try:
                os.link(original, link)
            except OSError:
                self.skipTest('hardlinks unavailable')
            with self.assertRaises(ValueError):
                ProcessLock(link).acquire()
            link.unlink()
            try:
                os.symlink(original, link)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises((ValueError, OSError)):
                ProcessLock(link).acquire()


if __name__ == '__main__':
    unittest.main()
