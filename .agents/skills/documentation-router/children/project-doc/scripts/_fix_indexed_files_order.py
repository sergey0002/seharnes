#!/usr/bin/env python3
"""Move #tags line to end after ## Indexed Files block in architecture docs."""
from __future__ import annotations

import re
from pathlib import Path

ARCH = Path(__file__).resolve().parents[1] / "architecture"
INDEXED_HEADER = "## Indexed Files"
TAGS_BEFORE_INDEXED = re.compile(r"\n(#[^\n]+)\n\n## Indexed Files")


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if INDEXED_HEADER not in text:
        return False

    m = TAGS_BEFORE_INDEXED.search(text)
    if not m:
        return False

    tags_line = m.group(1).strip()
    if not tags_line.startswith("#"):
        return False

    idx_start = text.index(INDEXED_HEADER)
    before = text[:idx_start].rstrip()
    before = before[: before.rfind("\n" + tags_line)].rstrip()
    indexed_block = text[idx_start:].rstrip()

    if indexed_block.endswith("\n" + tags_line):
        new_text = before + "\n\n" + indexed_block + "\n"
    else:
        new_text = before + "\n\n" + indexed_block + "\n\n" + tags_line + "\n"

    if new_text == text:
        return False

    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    fixed = []
    for path in sorted(ARCH.glob("*.md")):
        if path.name.startswith("_"):
            continue
        if fix_file(path):
            fixed.append(path.name)
    print("Fixed:", len(fixed))
    for name in fixed:
        print(" ", name)


if __name__ == "__main__":
    main()
