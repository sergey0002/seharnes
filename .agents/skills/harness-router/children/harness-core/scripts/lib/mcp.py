"""MCP helpers shared by adapters and audits."""
from __future__ import annotations

import json
import re
from pathlib import Path

ENV_REF = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def load_canon(root: Path) -> dict:
    path = root / ".cursor" / "mcp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("mcpServers", {})


def server_names(canon: dict) -> list[str]:
    return sorted(canon)


def enabled(canon: dict) -> list[str]:
    return sorted(name for name, value in canon.items() if not value.get("disabled"))


def scan_placeholders(config: dict) -> list[str]:
    text = json.dumps(config)
    return sorted(set(ENV_REF.findall(text)))


def resolve_env(value: str, lookup: dict[str, str]) -> str:
    return ENV_REF.sub(lambda match: lookup.get(match.group(1), ""), value)
