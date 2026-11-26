#!/usr/bin/env python3
"""Read the environment registry and manage generated environment views."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "harness-core/assets/environments.json"


def load(root: Path) -> list[dict]:
    path = root / ".agents/skills/harness-router/children/harness-core/assets/environments.json"
    trusted = json.loads(registry_path().read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else trusted
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("environments"), list):
        raise ValueError("invalid environments.json")
    defaults = {row["id"]: dict(row) for row in trusted["environments"]}
    seen = set()
    for item in data["environments"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("invalid environment entry")
        env = item["id"]
        if env in seen or env not in defaults or not isinstance(item.get("enabled", True), bool):
            raise ValueError(f"unknown, duplicate or invalid environment: {env}")
        seen.add(env)
        defaults[env]["enabled"] = item.get("enabled", defaults[env].get("enabled", True))
    return list(defaults.values())


def enabled_ids(root: Path) -> list[str]:
    return [item["id"] for item in load(root) if item.get("enabled", True)]


def is_enabled(root: Path, environment: str) -> bool:
    return environment in enabled_ids(root)


def generated_paths(root: Path, *, disabled_only: bool = False) -> list[str]:
    result: list[str] = []
    for item in load(root):
        if disabled_only and item.get("enabled", True):
            continue
        result.extend(str(path) for path in item.get("generated", []))
    if not disabled_only:
        result.append(".doc/skil_data/environment-sync/discovery.json")
    return sorted(set(result))


def safe_path(root: Path, relative: str) -> Path:
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\\" in relative:
        raise ValueError(f"unsafe generated path: {relative}")
    if not (relative in {"opencode.json", "DSH-RULES.md", "DSH-BOOTSTRAP.md"}
            or len(parts) > 1 and re.fullmatch(r"\.(codex|kilo|qoder|qwen|opencode|omp|dsh)", parts[0])
            or relative.startswith((".agents/rules/", ".agents/scripts/"))
            or relative in {".agents/rules", ".agents/scripts", ".agents/mcp.json", ".agents/mcp_config.json",
                            ".agents/skills.json", ".agents/mcp.env", ".cursor/tools/composer.phar",
                            ".doc/harnes/state/.validate-rules-last.json"}
            or len(parts) > 3 and parts[:3] in [[".doc", "skil_data", x] for x in
                                                  ("harness-core", "harness-router", "environment-sync")]):
        raise ValueError(f"path outside generated namespaces: {relative}")
    for parent in (root / relative).parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f"symlink parent of generated path: {relative}")
    return root / relative


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--enabled", metavar="ENV")
    parser.add_argument("--list-enabled", action="store_true")
    parser.add_argument("--list-enabled-shell", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        active = enabled_ids(root)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.enabled:
        return 0 if args.enabled in active else 1
    if args.list_enabled:
        print(json.dumps(active, ensure_ascii=False))
        return 0
    if args.list_enabled_shell:
        print(" ".join(active))
        return 0
    parser.error("one action is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
