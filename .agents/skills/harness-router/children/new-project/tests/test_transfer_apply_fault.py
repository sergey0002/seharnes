import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LIB = Path(__file__).resolve().parents[1] / 'scripts/lib'
sys.path.insert(0, str(LIB))

import transfer_apply
from transfer_plan import plan_selected_update


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class ApplyFaultTest(unittest.TestCase):
    def test_failure_after_first_replacement_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'new-a')
            write(source / 'kit/b.txt', b'new-b')
            write(target / 'kit/a.txt', b'old-a')
            write(target / 'kit/b.txt', b'old-b')
            plan = plan_selected_update(source=source, target=target,
                                        paths=['kit/a.txt', 'kit/b.txt'], receipt=None, local_paths=[], max_file_bytes=8 * 1024 * 1024)
            plan['roots'] = ['kit']
            plan['excludes'] = []
            plan['source'] = {'kind': 'local_source', 'path': str(source)}
            plan['decisions_required'] = [{'path': 'kit/a.txt', 'action': 'review', 'choices': ['adopt', 'skip']}, {'path': 'kit/b.txt', 'action': 'review', 'choices': ['adopt', 'skip']}]
            plan['max_file_bytes'] = 8 * 1024 * 1024
            decisions = {'kit/a.txt': 'adopt', 'kit/b.txt': 'adopt'}
            original = transfer_apply.replace_prepared
            calls = {'count': 0}

            def flaky(*args, **kwargs):
                calls['count'] += 1
                if calls['count'] == 2:
                    raise OSError('injected replacement failure')
                return original(*args, **kwargs)

            state = root / 'state'
            with mock.patch.object(transfer_apply, 'replace_prepared', side_effect=flaky):
                result = transfer_apply.apply_plan(plan, {'decisions': decisions}, target, state,
                                                  max_file_bytes=8 * 1024 * 1024)
            self.assertIn(result['status'], {'rolled_back', 'needs_manual_recovery'})
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'old-a')
            self.assertEqual((target / 'kit/b.txt').read_bytes(), b'old-b')


if __name__ == '__main__':
    unittest.main()
