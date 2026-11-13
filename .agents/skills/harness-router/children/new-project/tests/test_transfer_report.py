import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_report import summarize_preview


class ReportTest(unittest.TestCase):
    def test_recursive_counts_and_review(self):
        rows = [
            {'path': 'kit/a', 'target': None, 'incoming': {}, 'proposal':
             {'status': 'new_from_release', 'action': 'add', 'requires_review': True}},
            {'path': 'kit/sub/b', 'target': {}, 'incoming': None, 'proposal':
             {'status': 'local_custom', 'action': 'keep', 'requires_review': False}},
            {'path': 'other/c', 'target': {}, 'incoming': {}, 'proposal':
             {'status': 'both_modified', 'action': 'review', 'requires_review': True}},
        ]
        report = summarize_preview(rows)
        directories = report['directories']
        self.assertEqual(report['sizes'], 'not_collected')
        self.assertEqual(directories['.']['files'], 3)
        self.assertEqual(directories['.']['review_files'], 2)
        self.assertEqual(directories['kit']['files'], 2)
        self.assertEqual(directories['kit']['incoming_files'], 1)
        self.assertEqual(directories['kit/sub']['actions'], {'keep': 1})
        self.assertEqual(directories['other']['statuses'], {'both_modified': 1})

    def test_invalid_or_duplicate_paths_fail(self):
        row = {'path': 'a', 'target': None, 'incoming': None,
               'proposal': {'status': 'absent', 'action': 'none', 'requires_review': False}}
        with self.assertRaises(ValueError):
            summarize_preview([row, row])
        with self.assertRaises(ValueError):
            summarize_preview([{'path': '../escape'}])


if __name__ == '__main__':
    unittest.main()
