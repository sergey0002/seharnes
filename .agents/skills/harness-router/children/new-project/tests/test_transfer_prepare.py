import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_backup import write_backup
from transfer_diff import FileState
from transfer_inventory import capture_file, snapshot_files
from transfer_journal import TransferJournal
from transfer_prepare import prepare_replacement
from transfer_process_lock import ProcessLock
from transfer_recovery import inspect_journal_recovery


class PrepareTest(unittest.TestCase):
    def test_locked_backup_is_prepared_before_any_target_change(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'file').write_bytes(b'before')
            before, content = capture_file(target, 'file', max_file_bytes=100)
            self.assertEqual(content, b'before')
            after = FileState('b' * 64, before.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            lock = ProcessLock(root / 'lock')
            with self.assertRaises(ValueError):
                prepare_replacement(journal, lease, lock, target, backup, 'file', before, after, max_file_bytes=100)
            with lock:
                result = prepare_replacement(journal, lease, lock, target, backup, 'file', before, after,
                                             max_file_bytes=100)
                self.assertEqual(result['status'], 'prepared_only')
                self.assertFalse(result['write_authorized'])
                self.assertEqual((target / 'file').read_bytes(), b'before')
                self.assertEqual(journal.file_records(lease)[0][-1], 'prepared')
                report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
                self.assertEqual(report['steps'][0]['action'], 'mark_restored')

    def test_concurrent_change_leaves_no_prepared_record(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'file').write_bytes(b'before')
            before = snapshot_files(target, ['file'], max_file_bytes=100)['file']
            after = FileState('b' * 64, before.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            def mutate(*args, **kwargs):
                result = write_backup(*args, **kwargs)
                (target / 'file').write_bytes(b'external change')
                return result
            with ProcessLock(root / 'lock') as lock, patch('transfer_prepare.write_backup', side_effect=mutate):
                with self.assertRaisesRegex(ValueError, 'target changed during backup'):
                    prepare_replacement(journal, lease, lock, target, backup, 'file', before, after,
                                        max_file_bytes=100)
            self.assertEqual(journal.file_records(lease), [])
            self.assertEqual((target / 'file').read_bytes(), b'external change')
            self.assertEqual(len(list(backup.iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
