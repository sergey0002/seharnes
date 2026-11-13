"""Read provisional, untrusted installed-file receipts for preview only.

Validation does not authenticate a receipt, its origin, or the running user.
This format is not yet the durable receipt of a completed transfer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import unicodedata
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import validate_paths


def receipt_paths_in_roots(paths: list[str], roots: list[str]) -> list[str]:
    """Select scoped receipt entries, failing on nonportable root spelling."""
    validate_paths(paths)
    validate_paths(roots)
    selected = []
    for path in paths:
        folded = unicodedata.normalize('NFC', path).casefold()
        for root in roots:
            root_folded = unicodedata.normalize('NFC', root).casefold()
            if folded == root_folded or folded.startswith(root_folded + '/'):
                if path != root and not path.startswith(root + '/'):
                    raise ValueError('receipt root differs by case or Unicode normalization')
                selected.append(path)
                break
    return selected


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate receipt key")
        result[key] = value
    return result


def read_preview_receipt(path: Path) -> tuple[dict[str, FileState], dict[str, str]]:
    """Read a bounded, stable regular JSON file; caller checks its ancestors.

    A local attacker can still replace an ancestor while it is read. This
    function must not be used to authorize any update or deletion.
    """
    data = _read_receipt_document(path)
    states = {}
    for name, item in data['files'].items():
        states[name] = FileState(item['installed_hash'], item['mode'])
    # Never echo release_url: an old or malformed config may contain credentials.
    return states, {'commit': data['commit'], 'profile': data['profile']}


def read_receipt_document(path: Path) -> dict:
    """Trusted caller variant that also returns release metadata."""
    return _read_receipt_document(path)


def _read_receipt_document(path: Path) -> dict:
    path = Path(path)
    before_path = path.lstat()
    def acceptable(info):
        return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                not (getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))
    if not acceptable(before_path):
        raise ValueError("unsafe receipt file")
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not acceptable(before) or (before.st_dev, before.st_ino) != (before_path.st_dev, before_path.st_ino):
            raise ValueError("receipt changed while opening")
        limit = 2 * 1024 * 1024
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, min(65536, limit - total + 1))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise ValueError("receipt exceeds size limit")
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if tuple(getattr(before, f) for f in fields) != tuple(getattr(after, f) for f in fields):
            raise ValueError("receipt changed while reading")
    finally:
        os.close(fd)
    try:
        data = json.loads(b''.join(chunks).decode('utf-8'), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("invalid receipt JSON") from error
    if not isinstance(data, dict) or set(data) != {'schema_version', 'release_url', 'commit', 'profile', 'files'}:
        raise ValueError("invalid receipt fields")
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError("unsupported receipt version")
    if not isinstance(data['release_url'], str) or not 1 <= len(data['release_url']) <= 2048:
        raise ValueError("invalid receipt release URL")
    if not isinstance(data['commit'], str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', data['commit']):
        raise ValueError("invalid receipt commit")
    if data['profile'] not in ('core', 'developer', 'project'):
        raise ValueError("invalid receipt profile")
    files = data['files']
    if not isinstance(files, dict) or len(files) > 2000:
        raise ValueError("invalid receipt files")
    validate_paths(list(files))
    for name, item in files.items():
        if not isinstance(item, dict) or set(item) != {'installed_hash', 'mode', 'role', 'decision'}:
            raise ValueError("invalid receipt entry")
        if item['role'] != 'owned' or item['decision'] not in ('installed', 'adopted', 'merged', 'replaced'):
            raise ValueError("unsupported receipt ownership or decision")
        if (not isinstance(item['installed_hash'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', item['installed_hash'])
                or type(item['mode']) is not int or not 0 <= item['mode'] <= 0o7777):
            raise ValueError("invalid receipt state")
    return data


def write_receipt(path: Path, *, release_url: str, commit: str, profile: str,
                  files: dict[str, dict]) -> str:
    """Write a validated receipt atomically and return its SHA-256."""
    if not isinstance(release_url, str) or not 1 <= len(release_url) <= 2048:
        raise ValueError("invalid receipt release URL")
    if not isinstance(commit, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit):
        raise ValueError("invalid receipt commit")
    if profile not in ('core', 'developer', 'project'):
        raise ValueError("invalid receipt profile")
    if not isinstance(files, dict) or len(files) > 2000:
        raise ValueError("invalid receipt files")
    validate_paths(list(files))
    for name, item in files.items():
        if (not isinstance(item, dict) or set(item) != {'installed_hash', 'mode', 'role', 'decision'}
                or item['role'] != 'owned'
                or item['decision'] not in ('installed', 'adopted', 'merged', 'replaced')
                or not isinstance(item['installed_hash'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', item['installed_hash'])
                or type(item['mode']) is not int or not 0 <= item['mode'] <= 0o7777):
            raise ValueError("invalid receipt entry")
    payload = {'schema_version': 1, 'release_url': release_url, 'commit': commit,
               'profile': profile, 'files': {name: dict(item) for name, item in sorted(files.items())}}
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    target = Path(path)
    directory = target.parent
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("receipt parent directory is missing or linked")
    temporary = directory / ('.' + target.name + '.' + secrets.token_hex(8) + '.tmp')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        position = 0
        while position < len(data):
            count = os.write(fd, data[position:])
            if count <= 0:
                raise OSError('receipt write made no progress')
            position += count
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, target)
    return hashlib.sha256(data).hexdigest()
