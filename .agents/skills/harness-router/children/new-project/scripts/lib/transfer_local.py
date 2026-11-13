"""Validate local ownership declarations for a read-only, scoped preview.

Historical Git paths are not a release receipt. This module cannot establish
ownership or authorize writes; callers must independently establish both.
"""
from __future__ import annotations

import unicodedata

from transfer_inventory import validate_paths

_FIELDS = {"kind", "name", "path", "owner", "docs_layout_key"}
_KINDS = {"skill", "rule", "script", "mcp", "doc"}
_DOCS_KEYS = {"layout.docs.script_skill", "layout.docs.script_tools",
              "layout.docs.mcp_skill", "layout.docs.mcp_disabled", "layout.docs.state"}


def _fold(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _overlap(a: str, b: str) -> bool:
    a, b = _fold(a), _fold(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def validate_local_extension(policy: dict, historical_paths: list[str], roots: list[str]) -> tuple[str, ...]:
    """Return component roots after validation against the *scoped* history.

    All declarations must be inside selected roots. Reject overlap with known
    history and other declarations instead of inferring ownership. An empty or
    incomplete historical set is not evidence that any path is unowned.
    """
    if not isinstance(policy, dict) or set(policy) != {"schema_version", "custom_components"}:
        raise ValueError("LOCAL_POLICY_ESCALATION: unexpected local policy fields")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise ValueError("LOCAL_POLICY_SCHEMA: schema_version must be 1")
    entries = policy["custom_components"]
    if not isinstance(entries, list) or len(entries) > 2000:
        raise ValueError("LOCAL_POLICY_SCHEMA: invalid custom_components")
    validate_paths(historical_paths)
    validate_paths(roots)
    components = []
    names = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _FIELDS:
            raise ValueError("LOCAL_POLICY_SCHEMA: invalid component fields")
        if any(not isinstance(v, str) or not v.strip() or len(v) > 1024 for v in entry.values()):
            raise ValueError("LOCAL_POLICY_SCHEMA: invalid component value")
        if entry["kind"] not in _KINDS or entry["docs_layout_key"] not in _DOCS_KEYS:
            raise ValueError("LOCAL_POLICY_SCHEMA: invalid kind or docs_layout_key")
        path = entry["path"]
        validate_paths([path])
        if not any(_fold(path) == _fold(root) or _fold(path).startswith(_fold(root) + "/") for root in roots):
            raise ValueError("LOCAL_POLICY_SCOPE: component is outside selected roots")
        if any(_overlap(path, owned) for owned in historical_paths):
            raise ValueError("LOCAL_POLICY_ESCALATION: overlaps historical path")
        name = (_fold(entry["kind"]), _fold(entry["name"]))
        if name in names or any(_overlap(path, other) for other in components):
            raise ValueError("LOCAL_POLICY_SCHEMA: duplicate or overlapping component")
        names.add(name)
        components.append(path)
    return tuple(components)


def selected_local_paths(paths: list[str], components: tuple[str, ...]) -> list[str]:
    """Select actual files beneath declared components, including collisions."""
    return [path for path in paths if any(_fold(path) == _fold(root) or
            _fold(path).startswith(_fold(root) + "/") for root in components)]
