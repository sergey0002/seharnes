"""Prepare one journal record and backup without modifying the target file.

This experimental orchestration is not an update engine and does not authorize
replacement. It assumes a private, local state/backup directory and a lock used
by every potential writer; release trust and complete snapshots remain gates.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from transfer_backup import write_backup
from transfer_diff import FileState
from transfer_inventory import capture_file, snapshot_files, validate_paths
from transfer_plan import _root_path
from transfer_process_lock import ProcessLock


def prepare_replacement(journal, lease, lock: ProcessLock, target: Path, backup_root: Path,
                        path: str, before: FileState | None, after: FileState | None,
                        *, max_file_bytes: int) -> dict:
    """Persist a verified backup before the journal's `prepared` record.

    A later writer must revalidate all paths, lease and lock again immediately
    before replacement. No automatic cleanup follows failure; unreferenced
    backups are retained for review, never silently removed.
    """
    if not isinstance(lock, ProcessLock):
        raise ValueError('process lock required')
    if ((before is not None and not isinstance(before, FileState)) or
            (after is not None and not isinstance(after, FileState)) or (before is None and after is None)):
        raise ValueError('invalid replacement states')
    validate_paths([path])
    lock.assert_held()
    journal.file_records(lease)  # validates active fencing token
    active = journal.active_state()
    if active != (lease.run_id, lease.generation, 'replacing'):
        raise ValueError('journal is not in replacing state')
    root = _root_path(Path(target), must_exist=True)
    backup = _root_path(Path(backup_root), must_exist=True)
    captured = capture_file(root, path, max_file_bytes=max_file_bytes)
    observed = captured[0] if captured is not None else None
    if observed != before:
        raise ValueError('target changed since preview')
    backup_info = None
    key = None
    if captured is not None:
        key = 'backup-' + secrets.token_hex(16) + '.bin'
        backup_info = write_backup(backup, key, captured[1], before, max_file_bytes=max_file_bytes)
    lock.assert_held()
    journal.file_records(lease)
    current = snapshot_files(root, [path], max_file_bytes=max_file_bytes).get(path)
    if current != before:
        raise ValueError('target changed during backup')
    journal.prepare_file(lease, path, before, after, key)
    return {'status': 'prepared_only', 'path': path, 'backup': backup_info,
            'target_modified': False, 'write_authorized': False}
