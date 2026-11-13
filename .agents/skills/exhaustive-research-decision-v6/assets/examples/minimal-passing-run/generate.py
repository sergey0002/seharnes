#!/usr/bin/env python3
"""Regenerate the minimal PASS fixture from templates + overrides.

Run from anywhere:
    python examples/minimal-passing-run/generate.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATES = ROOT / "assets" / "templates"
MANIFEST = HERE / "fixture_overrides.json"

SKIP = {"generate.py", "README.md", "fixture_overrides.json"}


def main() -> None:
    for src in sorted(TEMPLATES.iterdir()):
        if src.is_file() and src.name not in SKIP:
            shutil.copy2(src, HERE / src.name)
    overrides = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, content in overrides.items():
        (HERE / name).write_text(content, encoding="utf-8")
    print(f"fixture generated: {len(list(HERE.iterdir()))} files")


if __name__ == "__main__":
    main()
