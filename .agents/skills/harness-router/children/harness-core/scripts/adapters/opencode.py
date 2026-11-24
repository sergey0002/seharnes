"""Adapter: opencode.

The generated view lives in `.opencode/` and `opencode.json`; the real work is
done by environment-sync/scripts/generate-opencode-config.py.
"""
from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class Adapter(BaseAdapter):
    name = "opencode"

    def check(self, root: Path) -> list[str]:
        errors: list[str] = []
        if not (root / "opencode.json").is_file():
            errors.append("missing opencode.json")
        if not (root / ".opencode" / "rules").is_dir():
            errors.append("missing .opencode/rules")
        return errors
