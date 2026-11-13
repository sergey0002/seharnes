"""Local process exclusion primitive for a future transfer supervisor.

Not integrated with journal acquisition or recovery yet. Every writer must
hold the *same* lock for its entire critical section before it can provide
exclusion; locking by itself does not validate a filesystem or authorize writes.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from transfer_plan import _root_path

if os.name == 'nt':
    import msvcrt
else:
    import fcntl


class ProcessLock:
    """Non-blocking advisory lock on a local, dedicated persistent file.

    The parent must be private to the supervisor. Path-based ancestor checks
    are not protection against a concurrent malicious ancestor replacement.
    Network filesystems are unsupported and require an independent preflight.
    Never unlink or replace the lock file while any supervisor may run.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._fd = None

    def acquire(self) -> None:
        if self._fd is not None:
            raise ValueError('process lock is already held')
        parent = _root_path(self.path.parent, must_exist=True)
        name = self.path.name
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            raise ValueError('invalid process lock filename')
        path = parent / name
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags, 0o600)
        try:
            info = os.fstat(fd)
            after = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_ISLNK(after.st_mode)
                    or getattr(after, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
                    or (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino)):
                raise ValueError('unsafe process lock file')
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                except OSError as error:
                    raise ValueError('process lock is busy') from error
            else:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise ValueError('process lock is busy') from error
            self._fd = fd
        except BaseException:
            os.close(fd)
            raise

    def release(self) -> None:
        if self._fd is None:
            raise ValueError('process lock is not held')
        fd, self._fd = self._fd, None
        try:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def assert_held(self) -> None:
        """Fail if the open locked file no longer matches its directory entry."""
        if self._fd is None:
            raise ValueError('process lock is not held')
        try:
            opened, current = os.fstat(self._fd), self.path.lstat()
        except OSError as error:
            raise ValueError('process lock file unavailable') from error
        if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1 or
                getattr(current, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400) or
                (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
            raise ValueError('process lock file changed')

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()
