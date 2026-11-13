#!/usr/bin/env python3
"""Build a deterministic scaffold for the diff analysis step.

Parses diff.md and diff.files.md, checks which files still exist, joins the
architecture file registry and flags suspicious commits. It never writes
findings, causes or decisions: those stay with the agent. The scaffold only
removes mechanical work and makes the suspicion list explicit.
"""

import argparse
import datetime as dt
import json
import re
from pathlib import Path

COMMIT_LINE = re.compile(r"^- `([0-9a-f]+)` \| ([^|]+) \| ([^|]+) \| (.*)$")
DIFF_HEAD = re.compile(r"^diff --git a/(.+?) b/(.+)$")
ISSUE_URL = re.compile(r"/issues/([0-9]+)")
TASK_NUMBER = re.compile(r"#([0-9]+)")
DATE_FORMATS = ("%d.%m.%Y %H:%M:%S %z", "%d.%m.%Y %H:%M %z", "%d.%m.%Y")


def read_text(path):
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def parse_task_header(task_text):
    data = {}
    for line in task_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] not in ("Field", "---"):
            data[cells[0]] = cells[1]
    return data


def parse_date(value):
    text = value.strip().replace(" UTC", " +0000")
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_registry(path):
    registry = {}
    text = read_text(path)
    lines = text.splitlines()
    if not lines:
        return registry
    header = lines[0].split("\t")
    for line in lines[1:]:
        cells = line.split("\t")
        if not cells or not cells[0]:
            continue
        row = dict(zip(header, cells))
        registry[cells[0]] = row
    return registry


def parse_commits(diff_text):
    commits = []
    in_index = False
    for line in diff_text.splitlines():
        if line.startswith("## Commits (index)"):
            in_index = True
            continue
        if in_index and line.startswith("## "):
            break
        if not in_index:
            continue
        match = COMMIT_LINE.match(line)
        if match:
            sha, date, author, subject = (part.strip() for part in match.groups())
            commits.append({"sha": sha, "date": date, "author": author,
                            "subject": subject})
    return commits


def parse_file_list(files_text):
    files = []
    in_all = False
    for line in files_text.splitlines():
        if line.startswith("## All files"):
            in_all = True
            continue
        if in_all and line.startswith("## "):
            break
        if in_all:
            value = line.strip()
            if value and not value.startswith("_") and not value.startswith(">"):
                files.append(value)
    return files


def parse_commit_files(files_text):
    mapping = {}
    in_by = False
    current = None
    for line in files_text.splitlines():
        if line.startswith("## By commit"):
            in_by = True
            continue
        if in_by and line.startswith("## "):
            break
        if not in_by:
            continue
        if line.startswith("### `"):
            match = re.match(r"### `([0-9a-f]+)`", line)
            current = match.group(1) if match else None
            if current:
                mapping.setdefault(current, [])
            continue
        value = line.strip()
        if current and value and not value.startswith(">"):
            mapping[current].append(value)
    return mapping


def parse_line_stats(diff_text):
    stats = {}
    current = None
    for number, line in enumerate(diff_text.splitlines(), start=1):
        match = DIFF_HEAD.match(line)
        if match:
            current = match.group(2)
            stats.setdefault(current, {"added": 0, "removed": 0,
                                       "start": number, "end": number})
            continue
        if current:
            stats[current]["end"] = number
        if current is None:
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            stats[current]["added"] += 1
        elif line.startswith("-"):
            stats[current]["removed"] += 1
    return stats


def commit_flags(commit, task, legacy, task_created):
    flags = []
    subject = commit["subject"]
    if ISSUE_URL.search(subject):
        flags.append("legacy_tracker_url")
    for number in TASK_NUMBER.findall(subject):
        if number not in {task, *legacy}:
            flags.append("foreign_task_number")
            break
    moment = parse_date(commit["date"])
    if moment and task_created:
        delta = abs((moment - task_created).days)
        if delta > 730:
            flags.append("date_outlier")
    return sorted(set(flags))


def file_flags(path, root, registry):
    flags = []
    if not (root / path).is_file():
        flags.append("historical")
    entry = registry.get(path)
    if not entry:
        flags.append("not_in_file_registry")
    elif entry.get("status") == "deleted":
        flags.append("deleted_in_file_registry")
    return flags


def build_scaffold(root, task):
    task_dir = root / ".doc" / "tasks" / task
    files_text = read_text(task_dir / "diff.files.md")
    diff_text = read_text(task_dir / "diff.md")
    task_text = read_text(task_dir / "task.md")
    if not files_text:
        return {"status": "error", "error": "diff.files.md not found",
                "task": task}

    header = parse_task_header(task_text)
    legacy = []
    if header.get("Bitbucket"):
        legacy.append(header["Bitbucket"])
    match = ISSUE_URL.search(task_text)
    if match and match.group(1) not in legacy:
        legacy.append(match.group(1))
    task_created = parse_date(header.get("Created", ""))
    registry = parse_registry(root / ".doc" / "architecture" / "_map"
                              / "file-registry.tsv")
    commits = parse_commits(diff_text)
    stats = parse_line_stats(diff_text)
    commit_files = parse_commit_files(files_text)

    for commit in commits:
        commit["flags"] = commit_flags(commit, task, legacy, task_created)

    files = []
    for path in parse_file_list(files_text):
        entry = registry.get(path, {})
        files.append({
            "path": path,
            "state": "historical" if not (root / path).is_file() else "current",
            "kind": entry.get("kind"),
            "domain": entry.get("domain"),
            "doc_refs": [ref for ref in (entry.get("doc_refs") or "").split(";") if ref],
            "lines": stats.get(path, {"added": 0, "removed": 0}),
            "diff_range": ({"start": stats[path]["start"],
                            "end": stats[path]["end"]}
                           if path in stats else None),
            "commits": [sha for sha, paths in commit_files.items()
                        if path in paths],
            "flags": file_flags(path, root, registry),
        })

    suspicions = []
    for commit in commits:
        for flag in commit["flags"]:
            suspicions.append({
                "type": flag,
                "scope": "commit",
                "ref": commit["sha"],
                "reason": f"{flag}: {commit['subject']}",
            })
    for entry in files:
        for flag in entry["flags"]:
            suspicions.append({
                "type": flag,
                "scope": "file",
                "ref": entry["path"],
                "reason": f"{flag}: {entry['path']}",
            })

    return {
        "status": "ok",
        "task": task,
        "task_created": header.get("Created"),
        "legacy": sorted(set(legacy)),
        "commits": commits,
        "files": files,
        "suspicions": suspicions,
        "findings": [],
        "decisions": [],
        "requirements": [],
        "checklist": [
            "Заполнить findings: symptom, cause, resolution только по коду и дифу.",
            "Заполнить decisions: context, choice, alternatives.",
            "Заполнить requirements: text, state и source_ids.",
            "Проверить каждый suspicion и либо объяснить связь, либо исключить.",
            "Не включать historical файлы в current scope без причины.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--task", required=True, help="task number, digits")
    parser.add_argument("--output", help="write scaffold to this path")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+", args.task or ""):
        print(json.dumps({"status": "error", "error": "task must be digits"},
                         ensure_ascii=False))
        return 2
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "error": "root not found"},
                         ensure_ascii=False))
        return 2
    payload = build_scaffold(root, args.task)
    if payload.get("status") != "ok":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    output = Path(args.output) if args.output else (
        root / ".doc" / "tasks" / args.task / "_jsondoc" / "work"
        / "intake-analysis.scaffold.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    summary = {
        "status": "ok",
        "task": args.task,
        "path": str(output),
        "commits": len(payload["commits"]),
        "files": len(payload["files"]),
        "suspicions": len(payload["suspicions"]),
        "historical": sum(1 for item in payload["files"]
                          if item["state"] == "historical"),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
