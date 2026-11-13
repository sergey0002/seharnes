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
from transfer_replace import replace_prepared
from transfer_rollback import rollback_next, audit_recovery_tree
from transfer_tree import capture_tree


class RollbackTest(unittest.TestCase):
    def test_tree_drift_after_file_restore_blocks_recovery(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            (target / 'kit').mkdir(parents=True)
            backup.mkdir()
            (target / 'kit/file').write_bytes(b'old')
            (target / 'kit/unrelated').write_bytes(b'original')
            old = snapshot_files(target, ['kit/file'], max_file_bytes=100)['kit/file']
            new = FileState(hashlib.sha256(b'new').hexdigest(), old.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.save_tree_baseline(lease, capture_tree(target, ['kit'], max_file_bytes=100))
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with ProcessLock(root / 'lock') as lock:
                prepare_replacement(journal, lease, lock, target, backup, 'kit/file', old, new, max_file_bytes=100)
                replace_prepared(journal, lease, lock, target, backup, 'kit/file', b'new', max_file_bytes=100)
                journal.transition(lease, 'rolling_back')
                with self.assertRaisesRegex(ValueError, 'unresolved'):
                    audit_recovery_tree(journal, lease, lock, target, max_file_bytes=100)
                rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)
                partial = audit_recovery_tree(journal, lease, lock, target, max_file_bytes=100)
                self.assertEqual(partial['status'], 'partial_match')
                self.assertFalse(partial['full_tree_verified'])
                (target / 'kit/unrelated').write_bytes(b'external')
                report = audit_recovery_tree(journal, lease, lock, target, max_file_bytes=100)
                self.assertEqual(report['status'], 'needs_manual_recovery')
                self.assertEqual(report['comparison']['changed'], ['kit/unrelated'])
                self.assertEqual(journal.active_state()[2], 'needs_manual_recovery')
                with self.assertRaises(ValueError):
                    journal.acquire()

    def test_missing_baseline_requires_manual_recovery(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'rolling_back')
            with ProcessLock(root / 'lock') as lock:
                report = audit_recovery_tree(journal, lease, lock, root, max_file_bytes=100)
            self.assertEqual(report['reason'], 'baseline_missing')
            self.assertEqual(journal.active_state()[2], 'needs_manual_recovery')

    def test_reverse_order_existing_and_new_file(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'existing').write_bytes(b'old')
            old = snapshot_files(target, ['existing'], max_file_bytes=100)['existing']
            new = FileState(hashlib.sha256(b'new').hexdigest(), old.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with ProcessLock(root / 'lock') as lock:
                for path, before in [('existing', old), ('created', None)]:
                    prepare_replacement(journal, lease, lock, target, backup, path, before, new, max_file_bytes=100)
                    replace_prepared(journal, lease, lock, target, backup, path, b'new', max_file_bytes=100)
                journal.transition(lease, 'rolling_back')
                self.assertEqual(rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)['path'], 'created')
                self.assertFalse((target / 'created').exists())
                self.assertEqual(rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)['path'], 'existing')
                self.assertEqual((target / 'existing').read_bytes(), b'old')
                result = rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)
                self.assertEqual(result['status'], 'no_pending_files')
                self.assertFalse(result['run_finalized'])
                with self.assertRaisesRegex(ValueError, 'finalization'):
                    journal.transition(lease, 'rolled_back')
                with self.assertRaisesRegex(ValueError, 'active run'):
                    journal.acquire()
                self.assertEqual(journal.active_state()[2], 'rolling_back')

    def test_external_change_blocks_and_retry_after_journal_failure(self):
        with tempfile.TemporaryDirectory() as directory, sqlite3.connect(':memory:') as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'file').write_bytes(b'old')
            old = snapshot_files(target, ['file'], max_file_bytes=100)['file']
            new = FileState(hashlib.sha256(b'new').hexdigest(), old.mode)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with ProcessLock(root / 'lock') as lock:
                prepare_replacement(journal, lease, lock, target, backup, 'file', old, new, max_file_bytes=100)
                replace_prepared(journal, lease, lock, target, backup, 'file', b'new', max_file_bytes=100)
                journal.transition(lease, 'rolling_back')
                (target / 'file').write_bytes(b'external')
                with self.assertRaisesRegex(ValueError, 'manual recovery'):
                    rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)
                self.assertEqual((target / 'file').read_bytes(), b'external')
                (target / 'file').write_bytes(b'new')
                with patch.object(journal, 'mark_file', side_effect=RuntimeError('simulated crash')):
                    with self.assertRaises(RuntimeError):
                        rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)
                self.assertEqual((target / 'file').read_bytes(), b'old')
                self.assertEqual(journal.file_records(lease)[0][-1], 'replaced')
                self.assertEqual(rollback_next(journal, lease, lock, target, backup, max_file_bytes=100)['status'], 'file_restored')


if __name__ == '__main__':
    unittest.main()
