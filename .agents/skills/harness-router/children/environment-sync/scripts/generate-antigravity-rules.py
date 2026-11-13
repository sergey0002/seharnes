#!/usr/bin/env python3
"""Generate flat Antigravity rules from the Cursor canon.

Antigravity reads only `.agents/rules/*.md` with a mandatory `trigger` field.
Cursor canon is `.cursor/rules/**/*.mdc` with `alwaysApply` and `globs`.
This script flattens nested MCP rules and maps Cursor frontmatter to Antigravity.

Usage:
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py --root .
  python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py --root . --check
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import rule_model

TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
TRIGGER_BY_KIND = {
    rule_model.ALWAYS: "always_on",
    rule_model.CONDITIONAL: "glob",
    rule_model.AGENT_REQUESTED: "model_decision",
    rule_model.MANUAL: "manual",
}


def split_frontmatter(text: str) -> tuple[dict, str]:
    return rule_model.split_frontmatter(text)


def flat_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 1:
        return parts[0] + ".md"
    if parts[0] == "mcp" and len(parts) == 2:
        return "mcp-" + parts[1] + ".md"
    return "-".join(parts) + ".md"


def render(rule: Path, relative: Path, target: Path | None = None) -> str:
    text = rule.read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    trigger = front.get("trigger", "").strip()
    if trigger not in TRIGGERS:
        trigger = TRIGGER_BY_KIND[rule_model.classify(front)]
    globs = rule_model.rule_paths(front)
    lines = ["---", f"trigger: {trigger}"]
    description = str(front.get("description", "")).strip()
    if description:
        lines.append("description: " + json.dumps(description, ensure_ascii=False))
    if trigger == "glob" and globs:
        lines.append("globs: " + json.dumps(", ".join(globs), ensure_ascii=False))
    lines.append("---")
    lines.append("")
    target = target or rule.parents[len(relative.parts) + 1] / ".agents/rules" / flat_name(relative)
    return "\n".join(lines) + "\n" + rule_model.rebase_links(body, rule, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Antigravity rules")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--rules-dir", default=".cursor/rules")
    parser.add_argument("--out", default=".agents/rules")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    source = root / args.rules_dir
    target = root / args.out
    if not source.is_dir():
        print(f"rules dir not found: {source}", file=sys.stderr)
        return 2
    resolved_target = target.resolve()
    protected = (root, source.resolve(), (root / ".agents" / "skills").resolve())
    if resolved_target == root or root not in resolved_target.parents or any(
        resolved_target == path or resolved_target in path.parents or path in resolved_target.parents
        for path in protected[1:]
    ):
        print(f"unsafe output directory: {target}", file=sys.stderr)
        return 2

    expected: dict[str, str] = {}
    for rule in sorted(source.rglob("*.mdc")):
        rel = rule.relative_to(source)
        name = flat_name(rel)
        if name in expected:
            print(f"name collision: {name}", file=sys.stderr)
            return 2
        expected[name] = render(rule, rel, target / name)

    errors = []
    if not args.check:
        target.mkdir(parents=True, exist_ok=True)
    actual = {}
    if target.is_dir():
        for path in sorted(target.rglob("*")):
            if path.is_file() or path.is_symlink():
                name = path.relative_to(target).as_posix()
                actual[name] = path
    for name, content in expected.items():
        if name not in actual:
            errors.append(f"missing {name}")
        elif actual[name].is_symlink() or actual[name].read_bytes() != content.encode("utf-8"):
            errors.append(f"mismatch {name}")
    extras = sorted(set(actual) - set(expected))
    if args.check:
        errors.extend(f"extra {name}" for name in extras)
        for message in errors:
            print(message)
        print(json.dumps({"status": "passed" if not errors else "failed", "errors": errors, "generated": len(expected)}, ensure_ascii=False))
        return 0 if not errors else 1

    for path in sorted(target.iterdir()):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name, content in expected.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "written", "rules": len(expected), "out": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
