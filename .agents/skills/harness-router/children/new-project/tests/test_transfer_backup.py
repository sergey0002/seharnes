import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_backup import write_backup
from transfer_diff import FileState
from transfer_inventory import snapshot_files
from transfer_journal import TransferJournal
from transfer_recovery import inspect_journal_recovery


class BackupTest(unittest.TestCase):
    def test_backup_can_be_verified_against_journal_after_replace(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'rule').write_bytes(b'before')
            old = snapshot_files(target, ['rule'], max_file_bytes=100)['rule']
            key = 'backup-' + 'd' * 32 + '.bin'
            write_backup(backup, key, b'before', old, max_file_bytes=100)
            (target / 'rule').write_bytes(b'after')
            new = snapshot_files(target, ['rule'], max_file_bytes=100)['rule']
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            journal.prepare_file(lease, 'rule', old, new, key)
            journal.mark_file(lease, 'rule', 'replaced')
            report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
            self.assertEqual(report['steps'][0]['action'], 'restore_backup')
            self.assertFalse(report['write_authorized'])
            self.assertEqual((target / 'rule').read_bytes(), b'after')

    def test_verified_backup_no_overwrite_and_changed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            backup = root / 'backup'
            backup.mkdir()
            content = b'old harness content\n'
            (source / 'file').write_bytes(content)
            state = snapshot_files(source, ['file'], max_file_bytes=100)['file']
            key = 'backup-' + 'a' * 32 + '.bin'
            result = write_backup(backup, key, content, state, max_file_bytes=100)
            self.assertEqual((backup / key).read_bytes(), content)
            self.assertEqual(result['sha256'], hashlib.sha256(content).hexdigest())
            self.assertEqual(result['power_loss_safe'], 'not_verified')
            self.assertEqual(result['directory_fsynced'], os.name != 'nt')
            with self.assertRaises(ValueError):
                write_backup(backup, key, content, state, max_file_bytes=100)
            with self.assertRaises(ValueError):
                write_backup(backup, 'backup-' + 'b' * 32 + '.bin', b'changed', state, max_file_bytes=100)
            self.assertEqual((backup / key).read_bytes(), content)

    def test_rejects_links_and_stops_before_rename_on_fsync_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b'fixture'
            source = root / 'source'
            source.write_bytes(content)
            state = snapshot_files(root, ['source'], max_file_bytes=100)['source']
            key = 'backup-' + 'a' * 32 + '.bin'
            with patch('transfer_backup.os.fsync', side_effect=OSError('simulated')):
                with self.assertRaises(OSError):
                    write_backup(root, key, content, state, max_file_bytes=100)
            self.assertFalse((root / key).exists())
            try:
                os.symlink(source, root / key)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(ValueError):
                write_backup(root, key, content, state, max_file_bytes=100)
            self.assertEqual(source.read_bytes(), content)

    def test_rejects_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = FileState(hashlib.sha256(b'x').hexdigest(), 0o600)
            for key, content, limit in [('../escape', b'x', 2), ('backup-' + 'c' * 32 + '.bin', b'x', 0),
                                        ('backup-' + 'c' * 32 + '.bin', b'xx', 1)]:
                with self.assertRaises(ValueError):
                    write_backup(root, key, content, state, max_file_bytes=limit)


if __name__ == '__main__':
    unittest.main()
