#!/usr/bin/env python3
"""Remove generated agent views so the repository stays compact.

Generated views are recreated by sync-agent-views.sh (or harness_transfer
render). Only known managed paths are removed. Qoder's full skill tree is
removed only when it matches the canonical skill tree; discovery wrappers must
carry the generated marker.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

GENERATED = (
    ".qoder/skills",
    ".qoder/rules",
    ".qoder/settings.json",
    ".qwen/skills",
    ".qwen/rules",
    ".qwen/settings.json",
    ".dsh/skills",
    ".codex/rules",
    ".codex/rules-index.md",
    ".codex/mcp.json",
    ".codex/config.toml",
    ".kilo/rules",
    ".kilo/rules-index.md",
    ".kilo/mcp.json",
    ".kilo/kilo.jsonc",
    ".kilo/kilo-permissions.fragment.jsonc",
    ".agents/rules",
    ".agents/mcp.json",
    ".agents/mcp_config.json",
    ".agents/skills.json",
    ".cursor/tools/composer.phar",
    ".codex/tools/composer.phar",
    ".doc/skil_data/environment-sync",
    ".doc/skil_data/mirror",
    ".doc/harnes/state/.validate-rules-last.json",
    "DSH-RULES.md",
)
BOOT_START = "<!-- BEGIN HARNESS BOOTSTRAP: generated; edit .cursor/rules -->"
BOOT_END = "<!-- END HARNESS BOOTSTRAP -->"
WRAPPER_MARKER = "generated discovery wrapper"


def _digest_tree(path: Path) -> dict[str, str]:
    result = {}
    if not path.is_dir():
        return result
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _validate(root: Path) -> list[str]:
    errors = []
    qoder = root / ".qoder/skills"
    generator = Path(__file__).resolve().parent / "generate-qoder-config.py"
    if qoder.is_dir() and generator.is_file():
        result = subprocess.run([sys.executable, str(generator), "--root", str(root), "--check"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=180, check=False)
        if result.returncode:
            errors.append("Qoder view does not match the canonical skill tree")
    for relative in (".qwen/skills", ".dsh/skills"):
        view = root / relative
        if not view.is_dir():
            continue
        for entry in sorted(view.iterdir()):
            if not entry.is_dir():
                errors.append(f"unexpected file in {relative}: {entry.name}")
                continue
            if entry.name.startswith("rule-"):
                continue
            files = [item for item in entry.rglob("*") if item.is_file()]
            if len(files) != 1 or files[0].name != "SKILL.md" or files[0].parent != entry:
                errors.append(f"unexpected files in {relative}/{entry.name}")
            elif WRAPPER_MARKER not in files[0].read_text(encoding="utf-8", errors="ignore"):
                errors.append(f"not a generated wrapper: {relative}/{entry.name}")
    return errors


def _agents_state(root: Path) -> tuple[bool, str | None]:
    path = root / "AGENTS.md"
    if not path.is_file():
        return False, None
    text = path.read_text(encoding="utf-8")
    starts = text.count(BOOT_START)
    ends = text.count(BOOT_END)
    if starts != ends or starts > 1:
        raise ValueError("AGENTS.md has incomplete harness bootstrap markers")
    if not starts:
        return False, None
    return True, text[:text.index(BOOT_START)].rstrip() + "\n"


def compact(root: Path, *, apply: bool, force: bool) -> dict:
    root = Path(root).absolute()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    errors = [] if force or not apply else _validate(root)
    if errors:
        return {"status": "refused", "errors": errors, "removed": []}
    present = [relative for relative in GENERATED if (root / relative).exists()]
    agents_pending, agents_content = _agents_state(root)
    if agents_pending:
        present.append("AGENTS.md#bootstrap")
    if apply:
        if agents_pending:
            (root / "AGENTS.md").write_text(agents_content, encoding="utf-8", newline="\n")
        for relative in present:
            if relative == "AGENTS.md#bootstrap":
                continue
            path = root / relative
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    status = "compacted" if apply or not present else "pending"
    return {"status": status, "present": present, "removed": present if apply else []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="report generated paths without removing")
    action.add_argument("--apply", action="store_true", help="remove generated paths")
    parser.add_argument("--force", action="store_true", help="skip content validation")
    args = parser.parse_args(argv)
    try:
        report = compact(args.root, apply=args.apply, force=args.force)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "errors": [str(error)]}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] == "refused":
        return 2
    if args.check and report["present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
