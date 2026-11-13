import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_diff import FileState
from transfer_inventory import snapshot_files
from transfer_journal import TransferJournal
from transfer_prepare import prepare_replacement
from transfer_process_lock import ProcessLock
from transfer_recovery import inspect_journal_recovery
from transfer_replace import replace_prepared


class ReplaceTest(unittest.TestCase):
    def test_replace_new_and_delete_single_files(self):
        for operation in ('replace', 'new', 'delete'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
                root = Path(directory)
                target, backup = root / 'target', root / 'backup'
                target.mkdir()
                backup.mkdir()
                (target / 'probe').write_bytes(b'probe')
                mode = snapshot_files(target, ['probe'], max_file_bytes=100)['probe'].mode
                if operation != 'new':
                    (target / 'file').write_bytes(b'before')
                before = snapshot_files(target, ['file'], max_file_bytes=100).get('file')
                content = None if operation == 'delete' else b'after'
                after = None if content is None else FileState(hashlib.sha256(content).hexdigest(), mode)
                journal = TransferJournal(db)
                lease = journal.acquire()
                journal.transition(lease, 'backed_up')
                journal.transition(lease, 'replacing')
                with ProcessLock(root / 'lock') as lock:
                    prepare_replacement(journal, lease, lock, target, backup, 'file', before, after,
                                        max_file_bytes=100)
                    result = replace_prepared(journal, lease, lock, target, backup, 'file', content,
                                              max_file_bytes=100)
                    self.assertFalse(result['transfer_committed'])
                    self.assertEqual(journal.file_records(lease)[0][-1], 'replaced')
                    self.assertEqual(snapshot_files(target, ['file'], max_file_bytes=100).get('file'), after)
                    report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
                    expected = 'remove_new_file' if operation == 'new' else 'restore_backup'
                    self.assertEqual(report['steps'][0]['action'], expected)

    def test_changed_target_blocks_and_postreplace_failure_retains_prepared(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'file').write_bytes(b'before')
            before = snapshot_files(target, ['file'], max_file_bytes=100)['file']
            after = FileState(hashlib.sha256(b'after').hexdigest(), before.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with ProcessLock(root / 'lock') as lock:
                prepare_replacement(journal, lease, lock, target, backup, 'file', before, after, max_file_bytes=100)
                (target / 'file').write_bytes(b'external')
                with self.assertRaisesRegex(ValueError, 'target changed'):
                    replace_prepared(journal, lease, lock, target, backup, 'file', b'after', max_file_bytes=100)
                (target / 'file').write_bytes(b'before')
                with patch.object(journal, 'mark_file', side_effect=RuntimeError('simulated crash')):
                    with self.assertRaises(RuntimeError):
                        replace_prepared(journal, lease, lock, target, backup, 'file', b'after', max_file_bytes=100)
                self.assertEqual(journal.file_records(lease)[0][-1], 'prepared')
                report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
                self.assertEqual(report['steps'][0]['action'], 'restore_backup')


if __name__ == '__main__':
    unittest.main()
