"""Experimental single-file replacement for isolated transfer tests.

Not an updater and not connected to CLI or the panel. Callers still need a
trusted reviewed plan, exclusive writer across all processes, stable private
directories, full-tree checks, receipt commit and independently tested
recovery. A successful single-file operation is not a successful transfer.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import contains_known_secret, snapshot_files, validate_paths
from transfer_plan import _root_path
from transfer_process_lock import ProcessLock


def _state(digest, mode):
    if digest is None and mode is None:
        return None
    return FileState(digest, mode)


def _replace_one(journal, lease, lock, root, path, before, after, content, max_file_bytes):
    """Shared single-file operation; caller validates journal phase and backup."""
    if after is None:
        if content is not None:
            raise ValueError('deletion cannot contain staged bytes')
    else:
        if (not isinstance(content, bytes) or len(content) > max_file_bytes or
                hashlib.sha256(content).hexdigest() != after.sha256 or contains_known_secret(content)):
            raise ValueError('invalid or sensitive staged content')
    parent = _root_path(root / Path(path).parent, must_exist=True)
    destination = parent / Path(path).name
    if snapshot_files(root, [path], max_file_bytes=max_file_bytes).get(path) != before:
        raise ValueError('target changed since preparation')
    dirfd = None
    if os.name != 'nt':
        dirfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            os.fsync(dirfd)  # fail before modification if directory sync is unsupported
        except BaseException:
            os.close(dirfd)
            raise
    try:
        staged = None
        if after is not None:
            staged = parent / ('.harness-stage-' + secrets.token_hex(16))
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(staged, flags, 0o600)
            try:
                if hasattr(os, 'fchmod'):
                    os.fchmod(fd, after.mode)
                else:
                    os.chmod(staged, after.mode)
                position = 0
                while position < len(content):
                    count = os.write(fd, content[position:])
                    if count <= 0:
                        raise OSError('staged write made no progress')
                    position += count
                os.fsync(fd)
            finally:
                os.close(fd)
        lock.assert_held()
        journal.file_records(lease)
        if snapshot_files(root, [path], max_file_bytes=max_file_bytes).get(path) != before:
            raise ValueError('target changed during staging')
        if after is None:
            os.unlink(destination)
        else:
            os.replace(staged, destination)
        if dirfd is not None:
            os.fsync(dirfd)
        if snapshot_files(root, [path], max_file_bytes=max_file_bytes).get(path) != after:
            raise ValueError('replacement verification failed')
    finally:
        if dirfd is not None:
            os.close(dirfd)


def replace_prepared(journal, lease, lock: ProcessLock, target: Path, backup_root: Path,
                     path: str, content: bytes | None, *, max_file_bytes: int) -> dict:
    """Replace or delete one prepared file; retain journal on any failure.

    Directory entry checks are path-based and cannot withstand a hostile writer
    racing a rename. Every writer must cooperate with the same external lock.
    Never use this primitive to apply an unreviewed or untrusted update.
    """
    if not isinstance(lock, ProcessLock) or type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ValueError('invalid lock or file size limit')
    validate_paths([path])
    lock.assert_held()
    records = journal.file_records(lease)
    if journal.active_state() != (lease.run_id, lease.generation, 'replacing'):
        raise ValueError('journal is not in replacing state')
    matches = [row for row in records if row[0] == path and row[-1] == 'prepared']
    if len(matches) != 1:
        raise ValueError('one prepared journal record required')
    _, _, before_hash, before_mode, after_hash, after_mode, backup_key, _ = matches[0]
    before, after = _state(before_hash, before_mode), _state(after_hash, after_mode)
    root = _root_path(Path(target), must_exist=True)
    backup = _root_path(Path(backup_root), must_exist=True)
    if before is not None:
        if not backup_key or snapshot_files(backup, [backup_key], max_file_bytes=max_file_bytes).get(backup_key) != before:
            raise ValueError('backup missing or changed')
    _replace_one(journal, lease, lock, root, path, before, after, content, max_file_bytes)
    lock.assert_held()
    journal.mark_file(lease, path, 'replaced')
    return {'status': 'file_replaced', 'path': path, 'transfer_committed': False,
            'power_loss_safe': 'not_verified'}
