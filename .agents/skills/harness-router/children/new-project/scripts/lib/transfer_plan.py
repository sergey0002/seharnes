"""Read-only update proposals for an explicit, already selected file set.

This internal building block does not discover a release, fetch Git, establish
trust, scan contents for secrets, persist approval, or apply any changes.
"""
from __future__ import annotations

import os
import stat
from dataclasses import asdict
from pathlib import Path

from transfer_diff import FileState, classify_update
from transfer_inventory import snapshot_files, validate_paths


def _root_path(path: Path, *, must_exist: bool) -> Path:
    absolute = path.absolute()
    for item in (absolute, *absolute.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ValueError("source and target roots must have accessible directory ancestors") from error
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("source and target roots must not contain links or junctions")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("source and target roots require directory ancestors")
    if must_exist and not absolute.is_dir():
        raise ValueError("source root must be an existing directory")
    if absolute.exists() and not absolute.is_dir():
        raise ValueError("target root must be a directory")
    if os.name == "nt" and str(absolute).startswith("\\\\"):
        raise ValueError("network roots are not supported")
    return absolute.resolve(strict=must_exist)


def _validate_selection(paths: list[str], receipt: dict[str, FileState] | None,
                        local_paths: list[str]) -> tuple[tuple[str, ...], set[str]]:
    selected = validate_paths(paths)
    local = set(validate_paths(local_paths))
    if not local.issubset(selected):
        raise ValueError("local paths must be selected")
    if receipt is not None:
        if not isinstance(receipt, dict):
            raise ValueError("receipt must be a mapping or None")
        validate_paths(list(receipt))
        if not set(receipt).issubset(selected) or set(receipt) & local:
            raise ValueError("receipt paths must be selected and cannot be local")
        if any(not isinstance(state, FileState) for state in receipt.values()):
            raise ValueError("receipt entries must be FileState")
    return selected, local


def _assemble(selected: tuple[str, ...], local: set[str], receipt: dict[str, FileState] | None,
              current: dict[str, FileState], incoming: dict[str, FileState]) -> dict:
    files = []
    for path in sorted(selected):
        base = receipt.get(path) if receipt is not None else None
        proposal = classify_update(base_known=base is not None, base=base,
                                   target=current.get(path), incoming=incoming.get(path),
                                   ownership="local" if path in local else "upstream")
        files.append({
            "path": path,
            "base": asdict(base) if base is not None else None,
            "target": asdict(current[path]) if path in current else None,
            "incoming": asdict(incoming[path]) if path in incoming else None,
            "proposal": asdict(proposal),
        })
    return {"schema_version": 1, "scope": "explicit_paths_only", "files": files}


def plan_selected_update(*, source: Path, target: Path, paths: list[str],
                         receipt: dict[str, FileState] | None,
                         local_paths: list[str], max_file_bytes: int) -> dict:
    """Compare selected paths with a per-file receipt, without modifying either tree.

    The caller is responsible for complete discovery, ownership and release
    provenance. A missing receipt entry is never treated as upstream-owned.
    """
    selected, local = _validate_selection(paths, receipt, local_paths)

    src = _root_path(Path(source), must_exist=True)
    dst = _root_path(Path(target), must_exist=False)
    try:
        common = Path(os.path.commonpath((str(src), str(dst))))
    except ValueError:
        common = None
    if common == src or common == dst:
        raise ValueError("source and target roots must not overlap")

    incoming = snapshot_files(src, list(selected), max_file_bytes=max_file_bytes)
    current = snapshot_files(dst, list(selected), max_file_bytes=max_file_bytes) if dst.is_dir() else {}
    return _assemble(selected, local, receipt, current, incoming)
