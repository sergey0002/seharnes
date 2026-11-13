#!/usr/bin/env python3
"""Validate the intentionally small component registry schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if set(data) != {"version", "components"} or data["version"] != 1 or not isinstance(data["components"], dict):
        errors.append("registry must contain version=1 and components only")
    if not data.get("components"):
        errors.append("registry must contain at least one component")
    for name, entry in data.get("components", {}).items():
        allowed = {"required_files", "config_paths", "skill_dependencies"}
        if not isinstance(name, str) or not set(entry) <= allowed or "required_files" not in entry or "config_paths" not in entry:
            errors.append(f"{name}: entry must contain required_files and config_paths, optionally skill_dependencies")
        elif not all(isinstance(value, list) and all(isinstance(item, str) and item for item in value) for value in (entry["required_files"], entry["config_paths"], entry.get("skill_dependencies", []))):
            errors.append(f"{name}: paths must be lists of non-empty strings")
    known = set(data.get("components", {}))
    for name, entry in data.get("components", {}).items():
        for dep in entry.get("skill_dependencies", []):
            if dep not in known:
                errors.append(f"{name}: unknown skill dependency: {dep}")

    # A registry that only checks shape proves nothing: a renamed or deleted
    # skill kept its entry and every consumer silently pointed at a ghost.
    repo = Path(__file__).resolve().parents[6]
    for name, entry in data.get("components", {}).items():
        for group in ("required_files", "config_paths"):
            for relative in entry.get(group, []):
                target = repo / relative
                if not target.exists():
                    errors.append(f"{name}: {group} path does not exist: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", nargs="?", type=Path, default=Path(__file__).with_name("component_registry.json"))
    args = parser.parse_args()
    errors = validate(args.registry)
    report = {"status": "passed" if not errors else "failed", "registry": str(args.registry), "errors": errors}
    print(json.dumps(report, separators=(",", ":")))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
