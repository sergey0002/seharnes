"""Single rule model shared by every environment adapter.

The canon is `.cursor/rules/**/*.mdc` with flat YAML frontmatter. Every adapter
must classify a rule the same way:

  always           alwaysApply: true             -> injected / always_on / baseline
  conditional      globs or paths                -> glob / paths
  agent_requested  description, no always/globs  -> model_decision / skill
  manual           no frontmatter signal         -> manual / baseline

`always` wins over `conditional`, which matches Cursor: an always-on rule
ignores its globs. Adapters must not reorder this precedence, otherwise the
same rule behaves differently in different environments.

Two YAML forms are supported for list fields:

  globs: ["**.php", "**.tpl"]      inline
  globs:
    - "**.php"                     block
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

ALWAYS = "always"
CONDITIONAL = "conditional"
AGENT_REQUESTED = "agent_requested"
MANUAL = "manual"

KINDS = (ALWAYS, CONDITIONAL, AGENT_REQUESTED, MANUAL)


def rebase_links(text: str, source: Path, target: Path) -> str:
    """Keep local Markdown links aimed at their canonical resource after relocation."""
    def replace(match):
        value = match.group(1)
        path, sep, anchor = value.partition("#")
        if not path or ":" in path or path.startswith("/") or " " in path:
            return match.group(0)
        resource = source.parent / path
        if not resource.exists():
            return match.group(0)
        relative = Path(os.path.relpath(resource.resolve(), target.parent.resolve())).as_posix()
        return "](" + relative + (sep + anchor if sep else "") + ")"
    return re.sub(r"\]\(([^)]+)\)", replace, text)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter fields, body without the frontmatter block)."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    return _parse_block(match.group(1)), text[match.end():]


def parse_frontmatter(text: str) -> dict:
    return split_frontmatter(text)[0]


def rule_frontmatter(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def body_without_frontmatter(text: str) -> str:
    return split_frontmatter(text)[1]


def _parse_block(block: str) -> dict:
    fields: dict = {}
    key = ""
    for line in block.splitlines():
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            item = line.strip()
            if not key:
                continue
            if item.startswith("- "):
                current = fields.get(key)
                if not isinstance(current, list):
                    current = []
                current.append(item[2:].strip().strip("\"'"))
                fields[key] = current
            elif isinstance(fields.get(key), str):
                fields[key] = (fields[key] + " " + item).strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in (">", ">-", "|", "|-"):
            fields[key] = ""
        elif value.startswith("[") and value.endswith("]"):
            fields[key] = _inline_list(value)
        else:
            fields[key] = value.strip("\"'")
    return fields


def _inline_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [part for part in value[1:-1].split(",")]
    return [str(item).strip().strip("\"'") for item in parsed if str(item).strip()]


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().strip("\"'") for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip().strip("\"'") for part in value.split(",") if part.strip()]
    return []


def rule_paths(fields: dict) -> list[str]:
    """Globs or paths that make a rule conditional."""
    return as_list(fields.get("globs")) or as_list(fields.get("paths"))


def classify(fields: dict) -> str:
    """Classify one rule into the shared kind. Precedence is fixed here."""
    if str(fields.get("alwaysApply", "")).strip().lower() == "true":
        return ALWAYS
    if rule_paths(fields):
        return CONDITIONAL
    if str(fields.get("description", "")).strip():
        return AGENT_REQUESTED
    return MANUAL


# Visibility contract, separate from the trigger kind.
#
# `gate: true` means the rule must reach the model at start in every environment:
# it precedes an action that cannot be undone cheaply. `attach: glob` means the
# rule must keep path activation. Environments with a glob engine attach it
# themselves; environments without one must publish a generated glob block.

GATE = "gate"
ATTACH_GLOB = "glob"

GLOB_ENVS = frozenset({"cursor", "qoder", "qwen", "antigravity"})


def is_gate(fields: dict) -> bool:
    return str(fields.get(GATE, "")).strip().lower() == "true"


def needs_glob(fields: dict) -> bool:
    return str(fields.get("attach", "")).strip().lower() == ATTACH_GLOB


def visibility_contract(env: str, fields: dict) -> str:
    """Return the mode an environment must provide for this rule."""
    if is_gate(fields):
        return "inline"
    if needs_glob(fields):
        return "glob" if env in GLOB_ENVS else "generated-glob-block"
    return classify(fields)
