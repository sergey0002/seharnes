"""Adapter: omp.

The generated view lives in `.omp/`; the real work is done by
environment-sync/scripts/generate-omp-config.py.
"""
from __future__ import annotations

from pathlib import Path

from .base import BaseAdapter


class Adapter(BaseAdapter):
    name = "omp"

    def check(self, root: Path) -> list[str]:
        errors: list[str] = []
        if not (root / ".omp" / "rules").is_dir():
            errors.append("missing .omp/rules")
        if not (root / ".omp" / "mcp.json").is_file():
            errors.append("missing .omp/mcp.json")
        return errors
