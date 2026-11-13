"""Read-only scoped file-tree snapshots for recovery verification.

Protected paths are listed but their contents are never read. Directory
metadata and empty directories are not captured. This is not the full
pre-apply tree gate and is not authorization to commit or finalize rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import discover_target_paths, snapshot_files, validate_paths
from transfer_plan import _root_path


@dataclass(frozen=True)
class TreeSnapshot:
    roots: tuple[str, ...]
    files: tuple[tuple[str, FileState], ...]
    protected: tuple[str, ...]


def capture_tree(target: Path, roots: list[str], *, max_file_bytes: int,
                 excludes: list[str] | None = None) -> TreeSnapshot:
    """Capture regular nonprotected files twice checking directory membership.

    Reads are not atomic and cannot replace the exclusive writer lock or a
    future stable identity/full-tree gate. Roots are explicitly caller scoped.
    Excluded prefixes are not read or included in the managed tree.
    """
    selected = validate_paths(roots)
    if not selected:
        raise ValueError('snapshot requires roots')
    root = _root_path(Path(target), must_exist=True)
    files, protected = discover_target_paths(root, list(selected), excludes=excludes)
    states = snapshot_files(root, files, max_file_bytes=max_file_bytes)
    if set(states) != set(files):
        raise ValueError('tree changed during snapshot')
    if discover_target_paths(root, list(selected), excludes=excludes) != (files, protected):
        raise ValueError('tree membership changed during snapshot')
    return TreeSnapshot(tuple(sorted(selected)), tuple(sorted(states.items())), tuple(protected))


def compare_trees(before: TreeSnapshot, current: TreeSnapshot) -> dict:
    """Report exact nonprotected file differences without reporting content."""
    if not isinstance(before, TreeSnapshot) or not isinstance(current, TreeSnapshot) or before.roots != current.roots:
        raise ValueError('tree scope mismatch')
    a, b = dict(before.files), dict(current.files)
    added = sorted(b.keys() - a.keys())
    missing = sorted(a.keys() - b.keys())
    changed = sorted(path for path in a.keys() & b.keys() if a[path] != b[path])
    return {'matches_scanned_files': not (added or missing or changed), 'added': added, 'missing': missing,
            'changed': changed, 'protected_names_changed': before.protected != current.protected,
            'protected_contents_unchecked': True, 'directory_metadata_unchecked': True,
            'full_tree_verified': False}
