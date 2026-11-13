"""Adapter: cursor."""
from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class Adapter(BaseAdapter):
    name = "cursor"

    def check(self, root: Path) -> list[str]:
        errors: list[str] = []
        return errors
