#!/usr/bin/env python3
"""Find where MCP server names are used across the harness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOTS = [".cursor", ".codex", ".kilo", ".qoder", ".qwen", ".agents", ".doc/harnes/mcp"]
TEXT = {".json", ".jsonc", ".toml", ".yaml", ".yml", ".md", ".mdc", ".js", ".mjs", ".ts", ".py", ".sh", ".ps1"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    canon = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    servers = sorted(canon.get("mcpServers", {}))
    usage: dict[str, list[str]] = {name: [] for name in servers}
    for item in ROOTS:
        base = root / item
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in servers:
                if name in text:
                    usage[name].append(path.relative_to(root).as_posix())
    print(json.dumps({"servers": {name: sorted(set(paths)) for name, paths in usage.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
