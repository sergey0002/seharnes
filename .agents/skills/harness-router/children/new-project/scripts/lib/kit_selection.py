"""Resolve the kit file set for one profile from kit.json.

Both the dry-run preview and the real transfer use this module, so the preview
cannot report a different file set from the one the engine writes. Composition
comes from `assets/kit.json`, environment enablement from `environments.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

NEW_PROJECT = Path(__file__).resolve().parents[2]
HARNESS_CORE = NEW_PROJECT.parent / "harness-core"
ENVIRONMENT_SYNC = NEW_PROJECT.parent / "environment-sync"

sys.path.insert(0, str(HARNESS_CORE / "scripts"))
sys.path.insert(0, str(HARNESS_CORE / "scripts/lib"))
sys.path.insert(0, str(ENVIRONMENT_SYNC / "scripts"))

import environment_policy  # noqa: E402
import manifest  # noqa: E402
import profile_manifest  # noqa: E402

SOURCE_ONLY: tuple[str, ...] = ()


def enabled_environments(root: Path) -> list[str]:
    return environment_policy.enabled_ids(Path(root))


def generated_prefixes(root: Path) -> tuple[str, ...]:
    prefixes: list[str] = []
    for item in environment_policy.load(Path(root)):
        if not item.get("enabled", True):
            continue
        for path in item.get("generated", []):
            prefixes.append(path.rstrip("/"))
    return tuple(prefixes)


def kit_manifest(root: Path) -> dict[str, str]:
    with (HARNESS_CORE / "assets/kit.json").open(encoding="utf-8") as stream:
        return manifest.build(Path(root), json.load(stream))


def select(root: Path, profile: str) -> tuple[list[str], list[str]]:
    """Return kit files for a profile, split into transferable and target-generated."""
    files, _ = profile_manifest.build(Path(root), profile)
    prefixes = generated_prefixes(root)
    transferable: list[str] = []
    generated: list[str] = []
    for path in sorted(files):
        if path in SOURCE_ONLY:
            continue
        if any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes):
            generated.append(path)
        else:
            transferable.append(path)
    return transferable, generated
