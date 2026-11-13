"""Adapter: codex."""
from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class Adapter(BaseAdapter):
    name = "codex"

    def check(self, root: Path) -> list[str]:
        errors: list[str] = []
        return errors
