#!/usr/bin/env python3
"""Check that discovery-only skill views contain wrappers, not stale full copies.

Qoder is the only adapter that keeps a full skill tree. Qwen and DSH must keep
one generated SKILL.md wrapper per nested skill; rule-* entries are separate
generated rule skills. Unexpected content is reported as junk.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

VIEWS = (".qwen/skills", ".dsh/skills")
WRAPPER_MARKER = "generated discovery wrapper"


def check(root: Path) -> dict:
    root = Path(root).absolute()
    if not (root / ".agents/skills").is_dir():
        raise ValueError("canonical skills are missing")
    errors = []
    checked = 0
    for relative in VIEWS:
        view = root / relative
        if not view.is_dir():
            continue
        for entry in sorted(view.iterdir()):
            if not entry.is_dir():
                errors.append(f"unexpected file in {relative}: {entry.name}")
                continue
            files = [path for path in entry.rglob("*") if path.is_file()]
            if entry.name.startswith("rule-"):
                checked += 1
                continue
            if relative == ".dsh/skills" and entry.name == "dsh-router":
                checked += 1
                continue
            checked += 1
            if len(files) != 1 or files[0].name != "SKILL.md" or files[0].parent != entry:
                errors.append(f"unexpected files in discovery skill: {relative}/{entry.name}")
                continue
            try:
                text = files[0].read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.append(f"unreadable discovery skill: {relative}/{entry.name}")
                continue
            if WRAPPER_MARKER not in text:
                errors.append(f"stale full skill copy: {relative}/{entry.name}")
    return {"status": "failed" if errors else "passed", "checked": checked, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = check(args.root)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "errors": [str(error)]}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
