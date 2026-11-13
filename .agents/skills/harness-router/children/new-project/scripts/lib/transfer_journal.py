"""Internal SQLite state machine for one future transfer writer.

This is not an updater, lock-service deployment, backup or recovery engine.
Callers must secure the database and its directory, enforce local filesystem
requirements, perform filesystem operations and verify them independently.
Never use this state machine alone to authorize an actual file replacement.
"""
from __future__ import annotations

import secrets
import sqlite3
import re
import json
from dataclasses import dataclass
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import validate_paths
from transfer_process_lock import ProcessLock
from transfer_tree import TreeSnapshot

_NEXT = {
    "locked": {"backed_up", "rolling_back"},
    "backed_up": {"replacing", "rolling_back"},
    "replacing": {"validating", "rolling_back"},
    "validating": {"committed", "rolling_back"},
    "rolling_back": {"rolled_back", "needs_manual_recovery"},
    "needs_manual_recovery": set(),
    "committed": set(),
    "rolled_back": set(),
}


@dataclass(frozen=True)
class Lease:
    run_id: str
    generation: int
    token: str


class TransferJournal:
    """Durable state only; a stale active row always blocks a new run."""

    def __init__(self, connection: sqlite3.Connection):
        if connection.in_transaction:
            raise ValueError("connection must not have an open transaction")
        self.db = connection
        self.db.isolation_level = None
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS transfer_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1), generation INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO transfer_meta (id, generation) VALUES (1, 0);
            CREATE TABLE IF NOT EXISTS transfer_runs (
                run_id TEXT PRIMARY KEY, generation INTEGER NOT NULL UNIQUE,
                token TEXT NOT NULL, state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transfer_active (
                id INTEGER PRIMARY KEY CHECK (id = 1), run_id TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS transfer_files (
                run_id TEXT NOT NULL, path TEXT NOT NULL, sequence INTEGER NOT NULL,
                before_hash TEXT, before_mode INTEGER,
                after_hash TEXT, after_mode INTEGER, backup_key TEXT, phase TEXT NOT NULL,
                PRIMARY KEY (run_id, path), UNIQUE (run_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS transfer_baselines (
                run_id TEXT PRIMARY KEY, payload TEXT NOT NULL
            );
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(transfer_files)")}
        if "sequence" not in columns:
            raise ValueError("unsupported journal schema; explicit migration is required")

    def save_tree_baseline(self, lease: Lease, snapshot: TreeSnapshot) -> None:
        """Persist one partial pre-apply tree before replacements start.

        Snapshot provenance, scope and the external process lock are caller
        gates; this is not an authenticated or complete tree baseline.
        """
        if not isinstance(snapshot, TreeSnapshot):
            raise ValueError('invalid tree snapshot')
        validate_paths(list(snapshot.roots))
        validate_paths([path for path, _ in snapshot.files])
        if not snapshot.roots or any(not isinstance(state, FileState) for _, state in snapshot.files):
            raise ValueError('invalid tree snapshot')
        if any(not isinstance(path, str) or not path or len(path) > 4096 or any(ord(c) < 32 for c in path)
               for path in snapshot.protected):
            raise ValueError('invalid protected paths')
        payload = json.dumps({'roots': snapshot.roots,
                              'files': [[path, state.sha256, state.mode] for path, state in snapshot.files],
                              'protected': snapshot.protected}, ensure_ascii=False, sort_keys=True)
        if len(payload.encode('utf-8')) > 2 * 1024 * 1024:
            raise ValueError('tree snapshot too large')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self._active_state_for(lease) not in ('locked', 'backed_up'):
                raise ValueError('baseline must precede replacement')
            if self.db.execute('SELECT 1 FROM transfer_baselines WHERE run_id = ?', (lease.run_id,)).fetchone():
                raise ValueError('tree baseline already recorded')
            self.db.execute('INSERT INTO transfer_baselines VALUES (?, ?)', (lease.run_id, payload))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def tree_baseline(self, lease: Lease) -> TreeSnapshot | None:
        self._active_state_for(lease)
        row = self.db.execute('SELECT payload FROM transfer_baselines WHERE run_id = ?', (lease.run_id,)).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row[0])
            if set(data) != {'roots', 'files', 'protected'} or not isinstance(data['roots'], list) or not isinstance(data['files'], list) or not isinstance(data['protected'], list):
                raise ValueError('invalid tree baseline')
            files = tuple((path, FileState(digest, mode)) for path, digest, mode in data['files'])
            validate_paths(data['roots'])
            validate_paths([path for path, _ in files])
            if any(not isinstance(path, str) for path in data['protected']):
                raise ValueError('invalid protected paths')
            return TreeSnapshot(tuple(data['roots']), files, tuple(data['protected']))
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError('invalid tree baseline') from error

    def acquire(self) -> Lease:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT run_id FROM transfer_active WHERE id = 1").fetchone():
                raise ValueError("active run requires completion or recovery")
            self.db.execute("UPDATE transfer_meta SET generation = generation + 1 WHERE id = 1")
            generation = self.db.execute("SELECT generation FROM transfer_meta WHERE id = 1").fetchone()[0]
            lease = Lease(secrets.token_hex(16), generation, secrets.token_hex(32))
            self.db.execute("INSERT INTO transfer_runs VALUES (?, ?, ?, 'locked')",
                            (lease.run_id, lease.generation, lease.token))
            self.db.execute("INSERT INTO transfer_active VALUES (1, ?)", (lease.run_id,))
            self.db.execute("COMMIT")
            return lease
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def takeover_for_recovery(self, lock: ProcessLock) -> Lease:
        """Fence an interrupted run and force it into rollback-only state.

        The caller must hold the persistent ``transfer.lock`` next to this
        on-disk database; all writers must cooperate with the same lock. This
        is not process liveness detection and is not safe until every writer
        and supervisor entry point enforces that lock and private state path.
        """
        if not isinstance(lock, ProcessLock):
            raise ValueError('process lock required')
        lock.assert_held()
        row = next((entry for entry in self.db.execute('PRAGMA database_list') if entry[1] == 'main'), None)
        if row is None or not row[2]:
            raise ValueError('recovery requires an on-disk journal')
        expected = Path(row[2]).absolute().parent / 'transfer.lock'
        if lock.path.absolute() != expected:
            raise ValueError('process lock is not paired with the journal')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            lock.assert_held()
            active = self.db.execute('''SELECT r.run_id, r.state FROM transfer_runs r
                                       JOIN transfer_active a ON a.run_id = r.run_id
                                       WHERE a.id = 1''').fetchone()
            if active is None:
                raise ValueError('no interrupted transfer')
            if active[1] not in ('locked', 'backed_up', 'replacing', 'validating', 'rolling_back'):
                raise ValueError('transfer requires manual recovery')
            self.db.execute('UPDATE transfer_meta SET generation = generation + 1 WHERE id = 1')
            generation = self.db.execute('SELECT generation FROM transfer_meta WHERE id = 1').fetchone()[0]
            lease = Lease(active[0], generation, secrets.token_hex(32))
            self.db.execute("UPDATE transfer_runs SET generation = ?, token = ?, state = 'rolling_back' WHERE run_id = ?",
                            (lease.generation, lease.token, lease.run_id))
            self.db.execute('COMMIT')
            return lease
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def _active_state_for(self, lease: Lease) -> str:
        if (not isinstance(lease, Lease) or not isinstance(lease.run_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", lease.run_id)
                or type(lease.generation) is not int or lease.generation <= 0
                or not isinstance(lease.token, str) or not re.fullmatch(r"[0-9a-f]{64}", lease.token)):
            raise ValueError("invalid lease")
        row = self.db.execute("""SELECT r.generation, r.token, r.state FROM transfer_runs r
                                 JOIN transfer_active a ON a.run_id = r.run_id
                                 WHERE a.id = 1 AND r.run_id = ?""", (lease.run_id,)).fetchone()
        if row is None or row[0] != lease.generation or not secrets.compare_digest(row[1], lease.token):
            raise ValueError("stale or invalid transfer lease")
        return row[2]

    def transition(self, lease: Lease, next_state: str) -> None:
        if not isinstance(next_state, str) or next_state not in _NEXT:
            raise ValueError("invalid state")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            state = self._active_state_for(lease)
            if next_state not in _NEXT.get(state, set()):
                raise ValueError("invalid transfer state transition")
            if next_state == "validating" and self.db.execute(
                    "SELECT 1 FROM transfer_files WHERE run_id = ? AND phase != 'replaced' LIMIT 1", (lease.run_id,)).fetchone():
                raise ValueError("unresolved prepared file")
            if next_state == "rolled_back" and self.db.execute(
                    "SELECT 1 FROM transfer_files WHERE run_id = ? AND phase != 'restored' LIMIT 1", (lease.run_id,)).fetchone():
                raise ValueError("unresolved file recovery")
            # The current tree snapshot intentionally excludes protected
            # contents and directory metadata. There is also no verified
            # release/receipt commit gate yet. Do not claim either terminal
            # success or release the active run on caller-supplied phase marks.
            if next_state in ('committed', 'rolled_back'):
                raise ValueError('verified finalization is not implemented')
            self.db.execute("UPDATE transfer_runs SET state = ? WHERE run_id = ?", (next_state, lease.run_id))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def finalize(self, lease: Lease, next_state: str, evidence: dict) -> None:
        """Finalize a verified run and release the active writer.

        The caller supplies a tree digest and expected digest produced by the
        trusted engine after full managed-tree verification. This method checks
        their shape and equality, file phases and state, but cannot prove that
        the caller read the filesystem. It is not a standalone trust gate.
        """
        if next_state not in ('committed', 'rolled_back') or not isinstance(evidence, dict):
            raise ValueError('invalid finalization request')
        required = {'tree_digest', 'expected_digest'}
        if next_state == 'committed':
            required.add('receipt_sha256')
        if set(evidence) != required:
            raise ValueError('invalid finalization evidence')
        for key in ('tree_digest', 'expected_digest'):
            if not isinstance(evidence[key], str) or not re.fullmatch(r'[0-9a-f]{64}', evidence[key]):
                raise ValueError('invalid finalization digest')
        if evidence['tree_digest'] != evidence['expected_digest']:
            raise ValueError('tree does not match the expected result')
        if next_state == 'committed':
            if (not isinstance(evidence['receipt_sha256'], str)
                    or not re.fullmatch(r'[0-9a-f]{64}', evidence['receipt_sha256'])):
                raise ValueError('invalid receipt digest')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            state = self._active_state_for(lease)
            expected_state = 'validating' if next_state == 'committed' else 'rolling_back'
            phase = 'replaced' if next_state == 'committed' else 'restored'
            if state != expected_state:
                raise ValueError('invalid finalization state')
            if self.db.execute('SELECT 1 FROM transfer_files WHERE run_id = ? AND phase != ? LIMIT 1',
                               (lease.run_id, phase)).fetchone():
                raise ValueError('unresolved file records')
            self.db.execute('UPDATE transfer_runs SET state = ? WHERE run_id = ?', (next_state, lease.run_id))
            self.db.execute('DELETE FROM transfer_active WHERE run_id = ?', (lease.run_id,))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def prepare_file(self, lease: Lease, path: str, before: FileState | None,
                     after: FileState | None, backup_key: str | None) -> None:
        validate_paths([path])
        if (before is not None and not isinstance(before, FileState)) or (after is not None and not isinstance(after, FileState)):
            raise ValueError("invalid file state")
        if before is None and after is None:
            raise ValueError("file absent before and after")
        if before is not None:
            if not isinstance(backup_key, str):
                raise ValueError("backup key required")
            validate_paths([backup_key])
        elif backup_key is not None:
            raise ValueError("new file cannot have backup key")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self._active_state_for(lease) != "replacing":
                raise ValueError("file preparation requires replacing state")
            if self.db.execute("SELECT 1 FROM transfer_files WHERE run_id = ? AND phase = 'prepared' LIMIT 1",
                               (lease.run_id,)).fetchone():
                raise ValueError("previous prepared file is unresolved")
            previous = [row[0] for row in self.db.execute("SELECT path FROM transfer_files WHERE run_id = ?", (lease.run_id,))]
            validate_paths(previous + [path])
            sequence = self.db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM transfer_files WHERE run_id = ?",
                                       (lease.run_id,)).fetchone()[0]
            self.db.execute("INSERT INTO transfer_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'prepared')",
                            (lease.run_id, path, sequence, before.sha256 if before else None, before.mode if before else None,
                             after.sha256 if after else None, after.mode if after else None, backup_key))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def mark_file(self, lease: Lease, path: str, phase: str) -> None:
        validate_paths([path])
        if phase not in ("replaced", "restored"):
            raise ValueError("invalid file phase")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            state = self._active_state_for(lease)
            expected = "replacing" if phase == "replaced" else "rolling_back"
            previous = ("prepared",) if phase == "replaced" else ("prepared", "replaced")
            row = self.db.execute("SELECT phase FROM transfer_files WHERE run_id = ? AND path = ?",
                                  (lease.run_id, path)).fetchone()
            if state != expected or row is None or row[0] not in previous:
                raise ValueError("invalid file phase transition")
            if phase == "restored":
                latest = self.db.execute("""SELECT path FROM transfer_files WHERE run_id = ? AND phase != 'restored'
                                            ORDER BY sequence DESC LIMIT 1""", (lease.run_id,)).fetchone()
                if latest is None or latest[0] != path:
                    raise ValueError("file recovery must follow reverse operation order")
            self.db.execute("UPDATE transfer_files SET phase = ? WHERE run_id = ? AND path = ?",
                            (phase, lease.run_id, path))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def file_records(self, lease: Lease) -> list[tuple]:
        self._active_state_for(lease)
        return self.db.execute("""SELECT path, sequence, before_hash, before_mode, after_hash, after_mode, backup_key, phase
                                  FROM transfer_files WHERE run_id = ? ORDER BY sequence""", (lease.run_id,)).fetchall()

    def active_state(self) -> tuple[str, int, str] | None:
        return self.db.execute("""SELECT r.run_id, r.generation, r.state FROM transfer_runs r
                                  JOIN transfer_active a ON a.run_id = r.run_id WHERE a.id = 1""").fetchone()
