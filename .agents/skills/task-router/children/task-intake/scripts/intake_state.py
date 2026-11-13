#!/usr/bin/env python3
"""Compact preflight for task intake.

Reads the task folder, branch refs, identity gate and artifact freshness and
prints one small JSON. It never writes project files. The agent uses
next_action to decide which intake step to run instead of issuing several
separate shell calls.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LEGACY_IMPORTED = re.compile(r"Imported from\s+<?([^>\s]+)>?", re.IGNORECASE)
LEGACY_TABLE = re.compile(r"^\|\s*Bitbucket\s*\|\s*([0-9]+)\s*\|", re.MULTILINE)
ISSUE_URL = re.compile(r"/issues/([0-9]+)")

ARTIFACTS = (
    "task.md",
    "task.json",
    "doc.md",
    "diff.md",
    "diff.files.md",
    "plan.md",
)

GENERATED_MARKER = "generated from architecture:"
NEW_GENERATED_MARKER = "generated from task:"


def run_json(command, cwd):
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True,
                              text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None, None
    try:
        return json.loads(proc.stdout), proc.returncode
    except ValueError:
        return None, proc.returncode


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def legacy_numbers(task_text):
    found = []
    match = LEGACY_TABLE.search(task_text)
    if match:
        found.append(match.group(1))
    match = LEGACY_IMPORTED.search(task_text)
    if match:
        url = ISSUE_URL.search(match.group(1))
        if url:
            found.append(url.group(1))
    return sorted(set(found))


def local_refs(root):
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "for-each-ref",
             "--format=%(refname:short)", "refs/heads", "refs/remotes"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def branch_sets(refs, task, legacy):
    exact = [ref for ref in refs if ref in (f"features/#{task}", f"bugfixes/#{task}")]
    legacy_exact = []
    for number in legacy:
        for pattern in (f"features/#{number}", f"bugfixes/#{number}",
                        f"features/{number}", f"bugfixes/{number}"):
            if pattern in refs:
                legacy_exact.append(pattern)
    variants = []
    for ref in refs:
        if ref in exact or ref in legacy_exact:
            continue
        if re.search(rf"#{re.escape(task)}([^0-9]|$)", ref):
            variants.append(ref)
            continue
        for number in legacy:
            if re.search(rf"(^|[/#_-]){re.escape(number)}([^0-9]|$)", ref):
                variants.append(ref)
                break
    return sorted(set(exact)), sorted(set(legacy_exact)), sorted(set(variants))


def freshness(task_dir):
    task_md = task_dir / "task.md"
    diff_md = task_dir / "diff.md"
    doc_md = task_dir / "doc.md"
    result = {}
    for name, current, previous in (
        ("diff_vs_task", diff_md, task_md),
        ("doc_vs_diff", doc_md, diff_md),
    ):
        if not current.is_file() or not previous.is_file():
            result[name] = "missing"
        else:
            result[name] = (
                "stale" if current.stat().st_mtime < previous.stat().st_mtime
                else "fresh"
            )
    return result


def generated_views(root):
    """Count generated markdown views. Editing them directly loses work."""
    arch = root / ".doc" / "architecture"
    total = generated = 0
    if arch.is_dir():
        for path in sorted(arch.glob("*.md")):
            total += 1
            if GENERATED_MARKER in read_text(path)[:200]:
                generated += 1
    task_dir = root / ".doc" / "tasks"
    task_generated = 0
    if task_dir.is_dir():
        for path in sorted(task_dir.glob("*/doc.md")):
            if NEW_GENERATED_MARKER in read_text(path)[:200]:
                task_generated += 1
    if generated and generated == total:
        route = "jsondoc_apply"
    elif generated:
        route = "mixed_check_path"
    else:
        route = "direct"
    return {
        "architecture_md": {"generated": generated, "total": total},
        "task_doc_md": {"generated": task_generated},
        "edit_route": route,
    }


def path_route(root, raw_path):
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return {"path": raw_path, "status": "error", "error": "path must be relative"}
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return {"path": raw_path, "status": "error", "error": "path outside root"}
    text = read_text(target)[:200] if target.is_file() else ""
    generated = (GENERATED_MARKER in text) or (NEW_GENERATED_MARKER in text)
    if generated:
        route = "jsondoc_apply"
    elif path.suffix == ".md" and path.parts[:2] == (".doc", "architecture"):
        route = "direct_after_check"
    else:
        route = "direct"
    return {"path": raw_path, "exists": target.is_file(),
            "generated": generated, "edit_route": route,
            "status": "ok"}


def build_state(root, task):
    """Return the compact preflight payload for one task."""
    task_dir = root / ".doc" / "tasks" / task
    files = {name: (task_dir / name).is_file() for name in ARTIFACTS}
    task_text = read_text(task_dir / "task.md") if files["task.md"] else ""
    legacy = legacy_numbers(task_text)

    identity = {"status": "unavailable", "exit": None}
    identity_script = root / ".agents" / "skills" / "documentation-router" / "children" / "project-doc" / "scripts" / "task-identity.py"
    if files["task.md"] and identity_script.is_file():
        payload, code = run_json(
            [sys.executable, str(identity_script), task], root)
        if not isinstance(payload, dict):
            identity = {"status": "error", "exit": code}
        else:
            identity = {
                "status": payload.get("status", "error"),
                "exit": code,
                "checks": payload.get("checks", []),
                "warnings": payload.get("warnings", []),
            }
            if identity["status"] not in ("ok", "mismatch", "incomplete") or (identity["status"] == "ok" and (code != 0 or payload.get("ok") is not True)):
                identity["status"] = "error"

    exact, legacy_exact, variants = branch_sets(
        local_refs(root), task, legacy)

    report = root / ".doc" / "tasks" / task / "reports" / "change-report" / "report.html"
    dialogs = root / ".doc" / "tasks" / task / "dialogs" / "index.json"

    if not files["task.md"] or not files["task.json"]:
        next_action = "fetch"
    elif not files["diff.md"] or freshness(task_dir).get("diff_vs_task") == "stale":
        next_action = "diff"
    elif not files["doc.md"] or freshness(task_dir).get("doc_vs_diff") == "stale":
        next_action = "doc"
    else:
        next_action = "verify"

    payload = {
        "status": "ok",
        "task": task,
        "files": files,
        "legacy": legacy,
        "identity": identity,
        "branches": {
            "exact": exact,
            "legacy_exact": legacy_exact,
            "variants": variants,
        },
        "freshness": freshness(task_dir),
        "artifacts": {
            "report_html": report.is_file(),
            "dialogs_index": dialogs.is_file(),
        },
        "generated_views": generated_views(root),
        "next_action": next_action,
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="check one planned write path")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--task", help="task number, digits")
    args = parser.parse_args()

    if not args.path and not re.fullmatch(r"[0-9]+", args.task or ""):
        print(json.dumps({"status": "error", "error": "task must be digits"},
                         ensure_ascii=False))
        return 2
    if args.path and not args.task:
        args.task = ""
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "error": "root not found",
                          "root": str(root)}, ensure_ascii=False))
        return 2
    if args.path:
        result = path_route(root, args.path)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "ok" else 2

    payload = build_state(root, args.task)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
