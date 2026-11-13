#!/usr/bin/env python3
"""Build or validate the panel action registry. Read-only over skills."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / ".doc" / "web" / "config"
ACTIONS = CONFIG / "actions.json"
DRAFT = CONFIG / "actions.draft.json"
ALLOWED_ROOTS = (".agents/skills/", ".cursor/scripts/", ".cursor/mcp-stack/", ".doc/")
INTERPRETERS = {".py": "python3", ".sh": "bash", ".ps1": "pwsh", ".php": "php"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def merge_local(base: dict) -> list[dict]:
    rows = {row["id"]: row for row in base.get("actions", []) if isinstance(row, dict) and row.get("id")}
    local = load(CONFIG / "actions.local.json")
    if isinstance(local, dict):
        for row in local.get("actions", []):
            if isinstance(row, dict) and row.get("id"):
                rows[row["id"]] = {**rows.get(row["id"], {}), **row}
    return list(rows.values())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def service_profile() -> str:
    for path in (ROOT / ".doc" / ".rebase-kit.json", CONFIG / "service.json"):
        if not path.exists():
            continue
        data = load(path)
        value = data.get("profile") if isinstance(data, dict) else None
        if not isinstance(value, str) or value.lower() not in ("core", "full"):
            raise ValueError(f"invalid profile: {path}")
        return value.lower()
    raise ValueError("profile missing")


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen = set()
    profile = service_profile()
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str) or not rid:
            errors.append("action without id")
            continue
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        if profile == "core" and row.get("profile") == "full":
            continue
        script = row.get("script")
        if not isinstance(script, str) or not script.startswith("."):
            errors.append(f"{rid}: bad script path")
            continue
        path = (ROOT / script).resolve()
        try:
            rel_path = rel(path)
        except ValueError:
            errors.append(f"{rid}: script outside root")
            continue
        if not path.is_file():
            errors.append(f"{rid}: missing {rel_path}")
            continue
        if not rel_path.startswith(ALLOWED_ROOTS):
            errors.append(f"{rid}: script outside allowed roots: {rel_path}")
        interpreter = row.get("interpreter")
        if interpreter not in ("python3", "bash", "pwsh", "php"):
            errors.append(f"{rid}: bad interpreter")
        elif shutil.which(str(interpreter)) is None:
            errors.append(f"{rid}: interpreter not found: {interpreter}")
        for arg in row.get("args", []):
            if "{task}" in str(arg) and row.get("params", {}).get("task") != "int":
                errors.append(f"{rid}: {{task}} requires params.task=int")
    return errors


def draft() -> dict:
    actions = []
    for skill_json in sorted((ROOT / ".agents" / "skills").glob("*/skill.json")):
        data = load(skill_json)
        if not isinstance(data, dict):
            continue
        skill = skill_json.parent.name
        candidates = []
        for item in data.get("resources", {}).get("scripts", []):
            candidates.append(str((skill_json.parent / item).resolve()))
        for item in data.get("dependencies", {}).get("project", []):
            if isinstance(item, dict) and item.get("path"):
                candidates.append(str((ROOT / item["path"]).resolve()))
        for abs_path in candidates:
            path = Path(abs_path)
            if not path.is_file():
                continue
            try:
                rel_path = rel(path)
            except ValueError:
                continue
            if not rel_path.startswith(ALLOWED_ROOTS):
                continue
            ext = path.suffix.lower()
            actions.append({
                "id": (skill + "_" + path.stem).lower().replace("-", "_"),
                "label": f"{skill}: {path.name}",
                "group": "task",
                "interpreter": INTERPRETERS.get(ext, "bash"),
                "script": rel_path,
                "args": [],
                "cwd": ".",
                "timeout": 300,
                "write_scope": [],
                "progress_regex": "",
                "confirm": True,
                "profile": "full",
                "enabled": False,
            })
    return {"schema": 1, "source": "skill.json", "actions": actions}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate actions.json and local overlay")
    parser.add_argument("--draft", action="store_true", help="write actions.draft.json")
    args = parser.parse_args(argv)

    if args.draft:
        payload = draft()
        DRAFT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ok", "draft": str(DRAFT.relative_to(ROOT)), "actions": len(payload["actions"])}, ensure_ascii=False))
        return 0

    base = load(ACTIONS)
    if not isinstance(base, dict):
        print(json.dumps({"status": "failed", "errors": ["actions.json missing or invalid"]}, ensure_ascii=False))
        return 1
    rows = merge_local(base)
    try:
        errors = validate(rows)
    except ValueError as error:
        errors = [str(error)]
    print(json.dumps({"status": "ok" if not errors else "failed", "actions": len(rows), "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
