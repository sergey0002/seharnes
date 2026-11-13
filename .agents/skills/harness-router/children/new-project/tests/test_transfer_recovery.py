import sqlite3
import os
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_diff import FileState
from transfer_journal import TransferJournal
from transfer_recovery import analyze_recovery, inspect_journal_recovery
from transfer_inventory import snapshot_files


class RecoveryAnalysisTest(unittest.TestCase):
    def test_inspects_real_journal_target_and_backup_without_writes(self):
        with tempfile.TemporaryDirectory() as directory, closing(sqlite3.connect(':memory:')) as db:
            root = Path(directory)
            target, backup = root / 'target', root / 'backup'
            target.mkdir()
            backup.mkdir()
            (target / 'rule.md').write_bytes(b'before')
            old = snapshot_files(target, ['rule.md'], max_file_bytes=100)['rule.md']
            (backup / 'rule.md').write_bytes(b'before')
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            (target / 'rule.md').write_bytes(b'after')
            new = snapshot_files(target, ['rule.md'], max_file_bytes=100)['rule.md']
            journal.prepare_file(lease, 'rule.md', old, new, 'rule.md')
            report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
            self.assertEqual(report['steps'][0]['action'], 'restore_backup')
            self.assertFalse(report['snapshot_is_lock'])
            self.assertFalse(report['write_authorized'])
            self.assertEqual((target / 'rule.md').read_bytes(), b'after')
            self.assertEqual(journal.file_records(lease)[0][-1], 'prepared')
            (backup / 'rule.md').write_bytes(b'damaged')
            report = inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)
            self.assertEqual(report['status'], 'manual_required')
            self.assertEqual(report['steps'][0]['reason'], 'backup_missing_or_mismatch')
            (target / 'rule.md').unlink()
            try:
                os.symlink(backup / 'rule.md', target / 'rule.md')
            except (OSError, NotImplementedError):
                return  # symlink creation is often unavailable on native Windows
            with self.assertRaises(ValueError):
                inspect_journal_recovery(journal, lease, target, backup, max_file_bytes=100)

    def test_real_journal_crash_before_or_after_replace(self):
        with closing(sqlite3.connect(':memory:')) as db:
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            old, new = FileState('a' * 64, 0o644), FileState('b' * 64, 0o644)
            journal.prepare_file(lease, 'a.txt', old, new, 'backup/a')
            journal.mark_file(lease, 'a.txt', 'replaced')
            journal.prepare_file(lease, 'b.txt', None, new, None)
            records = journal.file_records(lease)
            report = analyze_recovery(records, {'a.txt': new, 'b.txt': new}, {'backup/a': old})
            self.assertEqual([s['action'] for s in report['steps']], ['remove_new_file', 'restore_backup'])
            self.assertEqual(report['status'], 'review_required')
            self.assertFalse(report['write_authorized'])
            self.assertFalse(report['full_tree_verified'])
            report = analyze_recovery(records, {'a.txt': old, 'b.txt': None}, {})
            self.assertEqual([s['action'] for s in report['steps']], ['mark_restored', 'mark_restored'])

    def test_divergence_and_missing_backup_require_manual_recovery(self):
        old, new, edited = (FileState(c * 64, 0o644) for c in 'abc')
        records = [('a', 1, old.sha256, old.mode, new.sha256, new.mode, 'backup/a', 'replaced')]
        for observed, backup, reason in [(new, {}, 'backup_missing_or_mismatch'),
                                         (edited, {'backup/a': old}, 'current_differs_from_before_and_after')]:
            report = analyze_recovery(records, {'a': observed}, backup)
            self.assertEqual(report['status'], 'manual_required')
            self.assertEqual(report['steps'][0]['reason'], reason)
        with self.assertRaises(ValueError):
            analyze_recovery(records, {}, {})
        restored = [(*records[0][:-1], 'restored')]
        self.assertEqual(analyze_recovery(restored, {'a': new}, {'backup/a': old})['steps'][0]['reason'],
                         'restored_file_changed')

    def test_deleted_file_and_invalid_records(self):
        old = FileState('a' * 64, 0o644)
        records = [('gone', 1, old.sha256, old.mode, None, None, 'backup/gone', 'prepared')]
        self.assertEqual(analyze_recovery(records, {'gone': None}, {'backup/gone': old})['steps'][0]['action'],
                         'restore_backup')
        with self.assertRaises(ValueError):
            analyze_recovery(records + records, {'gone': None}, {})


if __name__ == '__main__':
    unittest.main()
