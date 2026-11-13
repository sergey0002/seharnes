"""Write a single verified backup into a private local staging directory.

Internal primitive only: not connected to transfer apply or rollback. The
caller must hold the exclusive supervisor lock, ensure a private directory on
a supported local filesystem, and revalidate source bytes before replacement.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import contains_known_secret, snapshot_files
from transfer_plan import _root_path


def write_backup(root: Path, key: str, content: bytes, expected: FileState, *, max_file_bytes: int) -> dict:
    """Write/fsync/rename a backup and re-read it, without overwriting a key.

    This does not lock root. Its exclusive no-overwrite check assumes a private
    directory and one cooperating writer; hostile concurrent rename is outside
    its security boundary. On errors files may be retained for manual review.
    """
    if not isinstance(key, str) or not re.fullmatch(r'backup-[0-9a-f]{32}\.bin', key):
        raise ValueError('invalid backup key')
    if type(max_file_bytes) is not int or max_file_bytes <= 0 or not isinstance(content, bytes):
        raise ValueError('invalid backup content or limit')
    if not isinstance(expected, FileState) or len(content) > max_file_bytes:
        raise ValueError('invalid backup state or size')
    if hashlib.sha256(content).hexdigest() != expected.sha256:
        raise ValueError('backup content does not match expected hash')
    if contains_known_secret(content):
        raise ValueError('backup content contains a known secret signature')
    directory = _root_path(Path(root), must_exist=True)
    destination = directory / key
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('backup key already exists')
    temporary = directory / ('.backup-stage-' + secrets.token_hex(16))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, expected.mode)
        else:
            os.chmod(temporary, expected.mode)
        position = 0
        while position < len(content):
            written = os.write(fd, content[position:])
            if written <= 0:
                raise OSError('backup write made no progress')
            position += written
        os.fsync(fd)
    finally:
        os.close(fd)
    # The supervisor lock and private directory must make this check stable.
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('backup key appeared during staging')
    os.replace(temporary, destination)
    if os.name != 'nt':
        dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    observed = snapshot_files(directory, [key], max_file_bytes=max_file_bytes).get(key)
    if observed != expected:
        raise ValueError('backup verification failed')
    return {'key': key, 'sha256': expected.sha256, 'mode': expected.mode,
            'directory_fsynced': os.name != 'nt', 'power_loss_safe': 'not_verified'}
