import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_journal import TransferJournal
from transfer_tree import capture_tree, compare_trees


class TreeTest(unittest.TestCase):
    def test_snapshot_persists_across_journal_restart_and_reports_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            (target / 'kit').mkdir(parents=True)
            (target / 'kit/a').write_bytes(b'original')
            (target / 'kit/.env').write_bytes(b'do not scan secret content')
            journal_path = root / 'journal.sqlite'
            db = sqlite3.connect(journal_path)
            journal = TransferJournal(db)
            lease = journal.acquire()
            baseline = capture_tree(target, ['kit'], max_file_bytes=100)
            self.assertEqual(baseline.protected, ('kit/.env',))
            journal.save_tree_baseline(lease, baseline)
            with self.assertRaises(ValueError):
                journal.save_tree_baseline(lease, baseline)
            db.close()
            (target / 'kit/a').write_bytes(b'changed')
            (target / 'kit/extra').write_bytes(b'extra')
            with closing(sqlite3.connect(journal_path)) as db:
                journal = TransferJournal(db)
                restored = journal.tree_baseline(lease)
                self.assertEqual(restored, baseline)
                report = compare_trees(restored, capture_tree(target, ['kit'], max_file_bytes=100))
                self.assertEqual(report['added'], ['kit/extra'])
                self.assertEqual(report['changed'], ['kit/a'])
                self.assertFalse(report['full_tree_verified'])
                self.assertTrue(report['protected_contents_unchecked'])
                (target / 'kit/a').write_bytes(b'original')
                (target / 'kit/extra').unlink()
                report = compare_trees(restored, capture_tree(target, ['kit'], max_file_bytes=100))
                self.assertTrue(report['matches_scanned_files'])
                self.assertFalse(report['full_tree_verified'])

    def test_scope_mismatch_and_late_baseline_rejected(self):
        with tempfile.TemporaryDirectory() as directory, closing(sqlite3.connect(':memory:')) as db:
            root = Path(directory)
            (root / 'a').mkdir()
            (root / 'b').mkdir()
            one = capture_tree(root, ['a'], max_file_bytes=100)
            two = capture_tree(root, ['b'], max_file_bytes=100)
            with self.assertRaises(ValueError):
                compare_trees(one, two)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with self.assertRaises(ValueError):
                journal.save_tree_baseline(lease, one)


if __name__ == '__main__':
    unittest.main()
