#!/usr/bin/env python3
"""Build a profile file map from kit.json without writing Target files.

`developer` and `project` use the full kit. `core` keeps runtime skills, runtime
rules, harness tools and the panel, and drops task/tracker content. This map is
the single composition source: the export engine copies exactly these paths, so
the dry-run preview and the real transfer cannot diverge.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "harness-core"
sys.path.insert(0, str(SCRIPTS / "scripts/lib"))
import manifest

CORE_SKILLS = {
    "code", "codebase-memory-mcp", "codegraph", "codeprism", "context7", "git",
    "graphiti", "jdocmunch", "mysql", "neiroslop", "php-deps-mcp", "phpstan-mcp",
    "playwright", "ponytail", "semgrep", "serena", "harness-router",
}
CORE_RULES = {"batch-calls", "code-editing", "doc-rules", "mcp", "cbm-index-before-push",
              "temp-dir", "text-style", "gates"}
CORE_DISABLED_MCP_RULES = {"jira-task", "bitbucket-task", "sourcegraph", "deepwiki", "xdebug"}
CORE_DOCS = {
    ".doc/harnes/doc_rules.md",
    ".doc/harnes/state/canon-paths.yaml",
    ".doc/harnes/state/26-tools.md",
    ".doc/harnes/state/04-mcp.md",
    ".doc/harnes/state/05-scripts.md",
    ".doc/harnes/state/08-plan-contour.md",
    ".doc/harnes/state/15-mcp-stack.md",
    ".doc/harnes/state/13-agent-migration.md",
    ".doc/harnes/state/14-project-migration.md",
}
CORE_PANEL_PREFIX = ".doc/web/"


def _load_kit() -> dict:
    with (SCRIPTS / "assets/kit.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def _core_skill_allowed(relative: str, skill: str) -> bool:
    if not skill or skill.startswith("."):
        return True
    if skill == "harness-router":
        return True
    if skill not in CORE_SKILLS:
        return False
    if "/children/" in relative:
        return False
    return True


def _core_rule_allowed(relative: str) -> bool:
    name = relative.split("/", 1)[1] if "/" in relative else ""
    return name not in CORE_DISABLED_MCP_RULES


def _core_allowed(path: str) -> bool:
    if path.startswith(".agents/skills/"):
        parts = path.split("/")
        if len(parts) < 4:
            return True
        return _core_skill_allowed(path, parts[2])
    for prefix in (".codex/rules/", ".kilo/rules/", ".agents/rules/", ".opencode/rules/"):
        if path.startswith(prefix):
            return _core_rule_allowed(path)
    if path.startswith(".cursor/rules/"):
        if "/" in path[len(".cursor/rules/"):]:
            return _core_rule_allowed(path)
        name = path.rsplit("/", 1)[-1].removesuffix(".mdc")
        return name in CORE_RULES
    if path.startswith(".doc/harnes/"):
        if path.startswith(".doc/harnes/archive/mcp/"):
            return True
        return path in CORE_DOCS
    if path == ".doc/rebase_project.md":
        return False
    if path.startswith(".doc/"):
        return path.startswith(CORE_PANEL_PREFIX)
    if path in (".codex/go-task.ps1", ".codex/task-diff.ps1"):
        return False
    return True


def build(root: Path, profile: str) -> tuple[dict[str, str], list[str]]:
    root = Path(root).absolute()
    if profile not in ("core", "developer", "project"):
        raise ValueError("invalid profile")
    files = manifest.build(root, _load_kit())
    if profile != "core":
        return files, []
    kept = {path: digest for path, digest in files.items() if _core_allowed(path)}
    excluded = sorted(set(files) - set(kept))
    return kept, excluded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--profile", choices=("core", "developer", "project"), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        files, excluded = build(args.root, args.profile)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "profile": args.profile, "files": dict(sorted(files.items())),
                      "count": len(files), "excluded": excluded[:200],
                      "excluded_count": len(excluded)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
