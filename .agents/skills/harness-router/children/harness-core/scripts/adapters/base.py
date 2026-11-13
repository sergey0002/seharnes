"""Adapter interface for harness environments."""
from __future__ import annotations

from pathlib import Path


class BaseAdapter:
    name = "base"

    def check(self, root: Path) -> list[str]:
        return []

    def sync(self, root: Path, dry_run: bool = False) -> list[str]:
        return []
