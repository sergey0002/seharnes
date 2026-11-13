#!/usr/bin/env python3
"""Build a profile file map from kit.json without writing Target files.

Developer and Project use the full kit. Core keeps runtime skills, runtime
rules, harness tools and the panel, and drops task/tracker content. This is a
read-only manifest used by export dry-run; the legacy PowerShell export keeps
its own copy step until it is switched to the same map.
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
CORE_REMOVE_DIRS = (".tools/codeception", ".doc/qa", ".dsh/adapters", ".dsh/scripts", ".dsh/tests")
CORE_REMOVE_FILES = (".codex/go-task.ps1", ".codex/task-diff.ps1", ".doc/rebase_project.md")


def _load_kit() -> dict:
    with (SCRIPTS / "assets/kit.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def _core_allowed(path: str) -> bool:
    for prefix in (".qoder/skills/", ".qwen/skills/", ".dsh/skills/", ".codex/skills/"):
        if path.startswith(prefix):
            parts = path.split("/")
            return len(parts) > 2 and parts[2] in CORE_SKILLS
    for prefix in (".qoder/rules/", ".qwen/rules/", ".codex/rules/", ".kilo/rules/", ".agents/rules/"):
        if path.startswith(prefix):
            relative = path[len(prefix):]
            if "/" in relative:
                return relative.split("/", 1)[1].removesuffix(".md") not in CORE_DISABLED_MCP_RULES
            return relative.removesuffix(".md") in CORE_RULES
    if path.startswith(".agents/skills/"):
        parts = path.split("/")
        if len(parts) < 4:
            return True
        return parts[2] in CORE_SKILLS
    if path.startswith(".cursor/rules/"):
        relative = path[len(".cursor/rules/"):]
        if "/" in relative:
            return relative.split("/", 1)[1] not in CORE_DISABLED_MCP_RULES
        return relative.removesuffix(".mdc") in CORE_RULES
    if path.startswith(".doc/harnes/"):
        return path in (".doc/harnes/doc_rules.md", ".doc/harnes/state/canon-paths.yaml",
                        ".doc/harnes/state/26-tools.md") or path.startswith(".doc/harnes/archive/mcp/")
    if path.startswith(".doc/"):
        return path.startswith(".doc/web/")
    if path.startswith(CORE_REMOVE_DIRS):
        return False
    if path in CORE_REMOVE_FILES:
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
