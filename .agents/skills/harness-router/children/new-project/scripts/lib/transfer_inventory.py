"""Read-only snapshots of explicitly selected regular files.

This is not a release manifest, comprehensive secret scanner, or apply-time lock.
Callers must obtain selected paths from a trusted policy and revalidate before
any write. Discovery does not execute candidate code or authorize writes.
"""
from __future__ import annotations

import hashlib
import ntpath
import os
import re
import stat
import unicodedata
import types
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path

from transfer_diff import FileState


class InventoryError(ValueError):
    def __init__(self, reason: str, relative_path: str):
        self.reason = reason
        self.relative_path = relative_path
        super().__init__(f"{reason}: {relative_path}")


_RESERVED = re.compile(r"^(?:con|prn|aux|nul|conin\$|conout\$|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?$", re.I)
_INVALID = re.compile(r'[\x00-\x1f<>:"\\|?*]')
_PRIVATE_NAMES = {".env", "config.env", "mcp.env", "credentials.json", "id_rsa", "id_ed25519"}
_PRIVATE_SUFFIXES = (".token", ".pem", ".key", ".p12", ".pfx")
_PRIVATE_ROOTS = (".doc/web/state", ".doc/skil_data")
_PRIVATE_MARKER = re.compile(r"(?:^|[._-])(?:secrets?|tokens?|password|passwd|credentials?|private[-_]?key)(?:$|[._-])", re.I)


def validate_paths(paths: list[str]) -> tuple[str, ...]:
    """Validate every path before any file is opened, including Windows rules."""
    if not isinstance(paths, list):
        raise InventoryError("invalid_path_list", "")
    seen: set[str] = set()
    components: dict[str, str] = {}
    result: list[str] = []
    for path in paths:
        if not isinstance(path, str) or not path or path.startswith("/") or ntpath.splitdrive(path)[0]:
            raise InventoryError("invalid_path", str(path))
        parts = path.split("/")
        if any(not part or part in (".", "..") or part[-1:] in (".", " ")
               or _INVALID.search(part) or _RESERVED.fullmatch(part) for part in parts):
            raise InventoryError("invalid_path", path)
        folded = unicodedata.normalize("NFC", path).casefold()
        if folded in seen:
            raise InventoryError("path_collision", path)
        # A release containing both a file and a directory at the same
        # portable path cannot be represented on all supported filesystems.
        prefixes = folded.split("/")
        if folded in components or any("/".join(prefixes[:i]) in seen for i in range(1, len(prefixes))):
            raise InventoryError("path_collision", path)
        for i in range(1, len(parts)):
            actual = "/".join(parts[:i])
            key = unicodedata.normalize("NFC", actual).casefold()
            if key in components and components[key] != actual:
                raise InventoryError("path_collision", path)
            components[key] = actual
        seen.add(folded)
        lower = [part.casefold() for part in parts]
        if (".git" in lower or any(part in _PRIVATE_NAMES or part.startswith(".env.")
                                   or part.endswith(_PRIVATE_SUFFIXES) or ".local." in part
                                   or _PRIVATE_MARKER.search(part) for part in lower)
                or any(folded == prefix or folded.startswith(prefix + "/") for prefix in _PRIVATE_ROOTS)):
            raise InventoryError("private_path", path)
        result.append(path)
    return tuple(result)


def _reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


@lru_cache(maxsize=1)
def _secret_detector():
    """Use the installed Mirror's existing signature policy, never candidate code."""
    path = Path(__file__).resolve().parents[3] / "mirror/scripts/harness_mirror.py"
    module = types.ModuleType("trusted_harness_mirror_secret_policy")
    module.__file__ = str(path)
    try:
        # compile/exec avoids importlib writing __pycache__ during read-only preview.
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    except (ImportError, OSError, SyntaxError) as error:
        raise ValueError("installed secret signature policy unavailable") from error
    return module.looks_secret


def contains_known_secret(data: bytes) -> bool:
    """Detect existing Mirror signatures; this is not comprehensive secret scanning."""
    return bool(_secret_detector()(data.decode("utf-8", errors="ignore")))


def _excluded(relative: str, excludes: list[str] | None) -> bool:
    for item in excludes or []:
        item = item.rstrip("/")
        if relative == item or relative.startswith(item + "/"):
            return True
    return False


def discover_target_paths(root: Path, roots: list[str], *, max_entries: int = 2000,
                          excludes: list[str] | None = None) -> tuple[list[str], list[str]]:
    """List regular files and protected path names under explicit project roots.

    Links, reparse points, special files and unsafe names stop discovery. The
    protected paths are not traversed or opened. This path-based read-only scan
    is not a race-free authorization for any later write.
    """
    selected = validate_paths(roots)
    if not selected or type(max_entries) is not int or not 1 <= max_entries <= 2000:
        raise InventoryError("invalid_roots_or_limit", "")
    root = Path(root)
    if not root.exists():
        return [], []
    if root.is_symlink() or not root.is_dir() or _reparse(root.lstat()):
        raise InventoryError("invalid_root", "")
    files: list[str] = []
    protected: list[str] = []
    stack = []
    for relative in selected:
        if _excluded(relative, excludes):
            continue
        path = root
        try:
            for part in relative.split("/"):
                path = path / part
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or _reparse(info):
                    raise InventoryError("link_or_reparse", relative)
            stack.append((path, relative))
        except FileNotFoundError:
            continue
        except OSError as error:
            raise InventoryError("unreadable_or_unsafe", relative) from error
    visited = 0
    while stack:
        path, relative = stack.pop()
        visited += 1
        if visited > max_entries:
            raise InventoryError("entry_limit", relative)
        try:
            validate_paths([relative])
        except InventoryError as error:
            if error.reason != "private_path":
                raise
            protected.append(relative)
            continue
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or _reparse(info):
                raise InventoryError("link_or_reparse", relative)
            if stat.S_ISREG(info.st_mode):
                files.append(relative)
            elif stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    for entry in entries:
                        child = relative + "/" + entry.name
                        if entry.name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} \
                                or entry.name.endswith(".pyc"):
                            continue
                        if _excluded(child, excludes):
                            continue
                        if visited + len(stack) >= max_entries:
                            raise InventoryError("entry_limit", relative)
                        stack.append((path / entry.name, child))
            else:
                raise InventoryError("not_regular_file_or_directory", relative)
        except InventoryError:
            raise
        except OSError as error:
            raise InventoryError("unreadable_or_unsafe", relative) from error
    validate_paths(files)
    return sorted(files), sorted(protected)


def _state(fd: int, relative: str, maximum: int, *, capture: bool = False):
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or _reparse(before):
        raise InventoryError("not_regular_file", relative)
    if before.st_nlink != 1:
        raise InventoryError("hardlink", relative)
    if before.st_size > maximum:
        raise InventoryError("file_too_large", relative)
    digest = hashlib.sha256()
    total = 0
    tail = b""
    chunks = [] if capture else None
    while True:
        data = os.read(fd, min(1024 * 1024, maximum - total + 1))
        if not data:
            break
        total += len(data)
        if total > maximum:
            raise InventoryError("file_too_large", relative)
        if contains_known_secret(tail + data):
            raise InventoryError("sensitive_content", relative)
        tail = (tail + data)[-512:]
        digest.update(data)
        if chunks is not None:
            chunks.append(data)
    after = os.fstat(fd)
    if (before.st_dev, before.st_ino, before.st_mode, before.st_nlink, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_mode, after.st_nlink, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns):
        raise InventoryError("file_changed", relative)
    state = FileState(digest.hexdigest(), stat.S_IMODE(after.st_mode))
    return (state, b''.join(chunks)) if chunks is not None else state


def _snapshot_files(root: Path, paths: list[str], *, max_file_bytes: int, capture: bool) -> dict:
    selected = validate_paths(paths)
    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise InventoryError("invalid_size_limit", "")
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or _reparse(root.lstat()):
        raise InventoryError("invalid_root", "")
    root = root.resolve(strict=True)
    result: dict[str, FileState] = {}
    for relative in selected:
        parts = relative.split("/")
        try:
            with ExitStack() as stack:
                if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"):
                    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    stack.callback(os.close, directory)
                    for part in parts[:-1]:
                        directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                        stack.callback(os.close, directory)
                    fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=directory)
                else:
                    candidate = root
                    for part in parts:
                        candidate = candidate / part
                        info = candidate.lstat()
                        if stat.S_ISLNK(info.st_mode) or _reparse(info):
                            raise InventoryError("link_or_reparse", relative)
                    fd = os.open(candidate, os.O_RDONLY | getattr(os, "O_BINARY", 0))
                    opened = os.fstat(fd)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        os.close(fd)
                        raise InventoryError("file_changed", relative)
                stack.callback(os.close, fd)
                result[relative] = _state(fd, relative, max_file_bytes, capture=capture)
        except FileNotFoundError:
            continue
        except InventoryError:
            raise
        except OSError as error:
            raise InventoryError("unreadable_or_unsafe", relative) from error
    return result


def snapshot_files(root: Path, paths: list[str], *, max_file_bytes: int) -> dict[str, FileState]:
    """Snapshot selected paths; missing paths are omitted, unsafe paths fail closed."""
    return _snapshot_files(root, paths, max_file_bytes=max_file_bytes, capture=False)


def capture_file(root: Path, path: str, *, max_file_bytes: int) -> tuple[FileState, bytes] | None:
    """Read one bounded file and its state from the same verified descriptor.

    Returned bytes are sensitive in-memory data: do not log or return them to
    a UI. This snapshot is not a lock and must be revalidated before writes.
    """
    return _snapshot_files(root, [path], max_file_bytes=max_file_bytes, capture=True).get(path)
