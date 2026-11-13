"""Load and validate environments.json and kit.json."""
from __future__ import annotations

import json
from pathlib import Path

VALID_RULE_FORMATS = {"mdc", "flat_md", "trigger", "paths"}
VALID_SKILL_MODES = {"native", "mirror"}


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing config: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"config must be an object: {path}")
    return data


def load_environments(root: Path) -> dict:
    return _load(root / ".agents" / "skills" / "harness-router" / "children" / "harness-core" / "assets" / "environments.json")


def load_kit(root: Path) -> dict:
    return _load(root / ".agents" / "skills" / "harness-router" / "children" / "harness-core" / "assets" / "kit.json")


def validate(environments: dict, kit: dict, root: Path | None = None) -> list[str]:
    errors: list[str] = []
    envs = environments.get("environments")
    if environments.get("schema") != 1:
        errors.append("environments.schema must be 1")
    if not isinstance(envs, list) or not envs:
        errors.append("environments must be a non-empty list")
        envs = []

    ids: set[str] = set()
    for env in envs:
        if not isinstance(env, dict):
            errors.append("environment entry must be an object")
            continue
        env_id = env.get("id")
        if not env_id:
            errors.append("environment id is required")
        elif env_id in ids:
            errors.append(f"duplicate environment id: {env_id}")
        else:
            ids.add(env_id)
        if env.get("enabled", True) and not env.get("adapter"):
            errors.append(f"{env_id}: adapter is required")
        rules = env.get("rules") or {}
        if rules.get("format") and rules["format"] not in VALID_RULE_FORMATS:
            errors.append(f"{env_id}: unknown rule format {rules['format']}")
        skills = env.get("skills") or {}
        if skills.get("mode") and skills["mode"] not in VALID_SKILL_MODES:
            errors.append(f"{env_id}: unknown skills mode {skills['mode']}")

    if kit.get("schema") != 1:
        errors.append("kit.schema must be 1")
    copy = kit.get("copy")
    if not isinstance(copy, list) or not copy:
        errors.append("kit.copy must be a non-empty list")

    if root is not None:
        adapters = root / ".agents" / "skills" / "harness-router" / "children" / "harness-core" / "scripts" / "adapters"
        for env in envs:
            adapter = env.get("adapter")
            if env.get("enabled", True) and adapter and not (adapters / f"{adapter}.py").exists():
                errors.append(f"{env.get('id')}: adapter module not found: {adapter}.py")
    return errors
