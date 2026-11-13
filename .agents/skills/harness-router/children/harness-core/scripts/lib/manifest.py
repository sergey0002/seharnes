"""File manifests and comparisons."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _skip(relative: Path, skip_dirs: set[str], skip_files: list[str]) -> bool:
    if any(part in skip_dirs or part.startswith(".venv") or part == "__pycache__" for part in relative.parts[:-1]):
        return True
    name = relative.name
    for pattern in skip_files:
        if name == pattern or (pattern.startswith("*.") and name.endswith(pattern[1:])):
            return True
    return False


def build(root: Path, kit: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    skip_dirs = set(kit.get("skipDirs", []))
    skip_files = list(kit.get("skipFiles", []))
    for item in kit.get("copy", []):
        base = root / item
        if not base.exists():
            continue
        if base.is_file():
            relative = base.relative_to(root)
            if not _skip(relative, skip_dirs, skip_files):
                result[relative.as_posix()] = _hash(base)
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if _skip(relative, skip_dirs, skip_files):
                continue
            result[relative.as_posix()] = _hash(path)
    for item in kit.get("rootFiles", []):
        path = root / item
        if path.is_file():
            result[item] = _hash(path)
    return result


@dataclass
class Diff:
    overwritten: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    target_only: list[str] = field(default_factory=list)
    same: int = 0


def compare(source: dict[str, str], target: dict[str, str]) -> Diff:
    result = Diff()
    for relative, digest in source.items():
        if relative not in target:
            result.added.append(relative)
        elif target[relative] != digest:
            result.overwritten.append(relative)
        else:
            result.same += 1
    result.target_only = sorted(set(target) - set(source))
    result.overwritten.sort()
    result.added.sort()
    return result
