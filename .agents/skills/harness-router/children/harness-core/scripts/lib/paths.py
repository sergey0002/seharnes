"""Path helpers for harness management."""
from __future__ import annotations

from pathlib import Path


def project_root(start: Path | None = None) -> Path:
    """Return the nearest directory containing .cursor or .agents, else cwd."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor").is_dir() or (candidate / ".agents").is_dir():
            return candidate
    return current


def skill_root(root: Path) -> Path:
    return root / ".agents" / "skills" / "harness-router"


def ensure_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must be relative and stay inside the project: {value}")
    return path
