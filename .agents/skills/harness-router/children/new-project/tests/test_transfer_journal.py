import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_journal import Lease, TransferJournal
from transfer_diff import FileState
from transfer_process_lock import ProcessLock


class TransferJournalTest(unittest.TestCase):
    def test_recovery_takeover_fences_old_lease_and_forces_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with closing(sqlite3.connect(root / 'journal.sqlite')) as db:
                journal = TransferJournal(db)
                old = journal.acquire()
                journal.transition(old, 'backed_up')
                journal.transition(old, 'replacing')
                journal.prepare_file(old, 'file', None, FileState('b' * 64, 0o644), None)
                with ProcessLock(root / 'wrong.lock') as wrong, self.assertRaises(ValueError):
                    journal.takeover_for_recovery(wrong)
                with ProcessLock(root / 'transfer.lock') as lock:
                    new = journal.takeover_for_recovery(lock)
                    self.assertEqual(new.run_id, old.run_id)
                    self.assertGreater(new.generation, old.generation)
                    self.assertNotEqual(new.token, old.token)
                    self.assertEqual(journal.active_state()[2], 'rolling_back')
                    with self.assertRaises(ValueError):
                        journal.mark_file(old, 'file', 'replaced')
                    with self.assertRaises(ValueError):
                        journal.transition(new, 'validating')
                    journal.mark_file(new, 'file', 'restored')
                    with self.assertRaisesRegex(ValueError, 'finalization'):
                        journal.transition(new, 'rolled_back')

    def test_process_crash_then_takeover_and_file_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'target').mkdir()
            (root / 'backup').mkdir()
            (root / 'target/file').write_bytes(b'old')
            lib = str(Path(__file__).resolve().parents[1] / 'scripts/lib')
            code = '''
import hashlib, os, sqlite3, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from transfer_diff import FileState
from transfer_inventory import snapshot_files
from transfer_journal import TransferJournal
from transfer_prepare import prepare_replacement
from transfer_process_lock import ProcessLock
from transfer_replace import replace_prepared
r=Path(sys.argv[2]); t=r/'target'; b=r/'backup'
with ProcessLock(r/'transfer.lock') as lock:
 db=sqlite3.connect(r/'journal.sqlite'); j=TransferJournal(db); lease=j.acquire()
 j.transition(lease,'backed_up'); j.transition(lease,'replacing')
 old=snapshot_files(t,['file'],max_file_bytes=100)['file']
 new=FileState(hashlib.sha256(b'new').hexdigest(),old.mode)
 prepare_replacement(j,lease,lock,t,b,'file',old,new,max_file_bytes=100)
 replace_prepared(j,lease,lock,t,b,'file',b'new',max_file_bytes=100)
 os._exit(17)
'''
            child = subprocess.run([sys.executable, '-c', code, lib, str(root)], timeout=30, capture_output=True)
            self.assertEqual(child.returncode, 17, child.stderr.decode(errors='replace'))
            self.assertEqual((root / 'target/file').read_bytes(), b'new')
            from transfer_rollback import rollback_next
            with ProcessLock(root / 'transfer.lock') as lock, closing(sqlite3.connect(root / 'journal.sqlite')) as db:
                journal = TransferJournal(db)
                lease = journal.takeover_for_recovery(lock)
                result = rollback_next(journal, lease, lock, root / 'target', root / 'backup', max_file_bytes=100)
                self.assertEqual(result['status'], 'file_restored')
                self.assertFalse(result['run_finalized'])
                self.assertEqual((root / 'target/file').read_bytes(), b'old')
                self.assertEqual(journal.active_state()[2], 'rolling_back')

    def test_one_active_writer_and_monotonic_fencing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.sqlite'
            with closing(sqlite3.connect(path)) as a, closing(sqlite3.connect(path)) as b:
                first, second = TransferJournal(a), TransferJournal(b)
                lease = first.acquire()
                self.assertEqual(second.active_state(), (lease.run_id, lease.generation, 'locked'))
                with self.assertRaises(ValueError):
                    second.acquire()
                with self.assertRaises(ValueError):
                    second.transition(Lease(lease.run_id, lease.generation, '0' * 64), 'backed_up')
                with self.assertRaises(ValueError):
                    first.transition(lease, 'committed')
                for state in ('backed_up', 'replacing', 'validating'):
                    first.transition(lease, state)
                with self.assertRaisesRegex(ValueError, 'finalization'):
                    first.transition(lease, 'committed')
                self.assertEqual(second.active_state()[2], 'validating')
                with self.assertRaises(ValueError):
                    second.acquire()

    def test_crash_and_manual_recovery_remain_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.sqlite'
            db = sqlite3.connect(path)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            db.close()
            with closing(sqlite3.connect(path)) as restarted:
                journal = TransferJournal(restarted)
                self.assertEqual(journal.active_state()[2], 'backed_up')
                with self.assertRaises(ValueError):
                    journal.acquire()
                journal.transition(lease, 'rolling_back')
                journal.transition(lease, 'needs_manual_recovery')
                with self.assertRaises(ValueError):
                    journal.acquire()
                with self.assertRaises(ValueError):
                    journal.transition(lease, 'rolled_back')
                self.assertEqual(journal.active_state()[2], 'needs_manual_recovery')

    def test_invalid_lease_and_open_transaction_fail(self):
        with closing(sqlite3.connect(':memory:')) as db:
            journal = TransferJournal(db)
            lease = journal.acquire()
            with self.assertRaises(ValueError):
                journal.transition(Lease(lease.run_id, lease.generation, None), 'backed_up')
            db.execute('BEGIN')
            with self.assertRaises(ValueError):
                TransferJournal(db)
            db.rollback()

    def test_abrupt_process_exit_keeps_active_record(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / 'journal.sqlite'
            library = str(Path(__file__).resolve().parents[1] / 'scripts/lib')
            code = ('import os, sqlite3, sys; sys.path.insert(0, sys.argv[1]); '
                    'from transfer_journal import TransferJournal; '
                    'db=sqlite3.connect(sys.argv[2]); TransferJournal(db).acquire(); os._exit(17)')
            child = subprocess.run([sys.executable, '-c', code, library, str(db_path)], check=False)
            self.assertEqual(child.returncode, 17)
            with closing(sqlite3.connect(db_path)) as db:
                journal = TransferJournal(db)
                self.assertEqual(journal.active_state()[2], 'locked')
                with self.assertRaises(ValueError):
                    journal.acquire()

    def test_file_phases_block_commit_and_unverified_rollback(self):
        with closing(sqlite3.connect(':memory:')) as db:
            journal = TransferJournal(db)
            lease = journal.acquire()
            old, new = FileState('a' * 64, 0o644), FileState('b' * 64, 0o755)
            with self.assertRaises(ValueError):
                journal.prepare_file(lease, 'rules/a.md', old, new, 'backup/a')
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            with self.assertRaises(ValueError):
                journal.prepare_file(lease, 'rules/a.md', old, new, None)
            journal.prepare_file(lease, 'rules/a.md', old, new, 'backup/a')
            self.assertEqual(journal.file_records(lease)[0][-1], 'prepared')
            with self.assertRaises(ValueError):
                journal.prepare_file(lease, 'Rules/A.md', old, new, 'backup/b')
            with self.assertRaises(ValueError):
                journal.transition(lease, 'validating')
            journal.mark_file(lease, 'rules/a.md', 'replaced')
            journal.transition(lease, 'validating')
            journal.transition(lease, 'rolling_back')
            with self.assertRaises(ValueError):
                journal.transition(lease, 'rolled_back')
            journal.mark_file(lease, 'rules/a.md', 'restored')
            with self.assertRaisesRegex(ValueError, 'finalization'):
                journal.transition(lease, 'rolled_back')
            self.assertEqual(journal.active_state()[2], 'rolling_back')

    def test_prepared_file_survives_restart_and_requires_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.sqlite'
            db = sqlite3.connect(path)
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            journal.prepare_file(lease, 'new.txt', None, FileState('c' * 64, 0o644), None)
            db.close()
            with closing(sqlite3.connect(path)) as restarted:
                journal = TransferJournal(restarted)
                self.assertEqual(journal.file_records(lease)[0][-1], 'prepared')
                with self.assertRaises(ValueError):
                    journal.transition(lease, 'validating')
                journal.transition(lease, 'rolling_back')
                with self.assertRaises(ValueError):
                    journal.transition(lease, 'rolled_back')
                journal.mark_file(lease, 'new.txt', 'restored')
                with self.assertRaisesRegex(ValueError, 'finalization'):
                    journal.transition(lease, 'rolled_back')

    def test_rollback_order_is_reverse_of_journaled_replacements(self):
        with closing(sqlite3.connect(':memory:')) as db:
            journal = TransferJournal(db)
            lease = journal.acquire()
            journal.transition(lease, 'backed_up')
            journal.transition(lease, 'replacing')
            new = FileState('a' * 64, 0o644)
            journal.prepare_file(lease, 'z.txt', None, new, None)
            with self.assertRaises(ValueError):
                journal.prepare_file(lease, 'a.txt', None, new, None)
            journal.mark_file(lease, 'z.txt', 'replaced')
            journal.prepare_file(lease, 'a.txt', None, new, None)
            self.assertEqual([(r[0], r[1]) for r in journal.file_records(lease)], [('z.txt', 1), ('a.txt', 2)])
            journal.transition(lease, 'rolling_back')
            with self.assertRaises(ValueError):
                journal.mark_file(lease, 'z.txt', 'restored')
            journal.mark_file(lease, 'a.txt', 'restored')
            journal.mark_file(lease, 'z.txt', 'restored')
            with self.assertRaisesRegex(ValueError, 'finalization'):
                journal.transition(lease, 'rolled_back')

    def test_unsupported_existing_schema_is_not_silently_reinterpreted(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE TABLE transfer_files (run_id TEXT, path TEXT)')
            db.commit()
            with self.assertRaisesRegex(ValueError, 'schema'):
                TransferJournal(db)


if __name__ == '__main__':
    unittest.main()
