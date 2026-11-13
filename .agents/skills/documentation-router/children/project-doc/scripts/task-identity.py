#!/usr/bin/env python3
"""Verify that a task's identity files agree with each other.

`task.md`, `task.json` and the branch name are written by different tools at
different times. When they disagree an agent can plan against the wrong ticket:
16 of 184 tasks had a `metadata.title` that did not match the `task.md` heading,
and `jsondoc get` then returned the wrong title while `doc.md` was rendered from
that same JSON.

Usage:
    python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py 2622
    python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py --all --tsv

Exit codes: 0 identity ok, 2 mismatch, 4 task not found.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[6]

# Headings and titles are noisy by design: "Issue #2622: ошибка ...",
# "Задача 2622 - ...". Strip the wrappers before comparing.
HEADING_PREFIX_RE = re.compile(
    r"^\s*#\s*(?:issue|задача|task)?\s*#?\d+\s*:?\s*", re.IGNORECASE
)
NOISE_WORDS_RE = re.compile(
    r"^(?:ошибка|доработка|новдиз|прод|проблема|баг|неверно)\s+", re.IGNORECASE
)
NON_WORD_RE = re.compile(r"[^0-9a-zа-яё]+")


def normalize(value: str) -> str:
    """Lowercase, drop numbering and punctuation, collapse whitespace."""
    text = HEADING_PREFIX_RE.sub("", value or "")
    text = NOISE_WORDS_RE.sub("", text)
    text = NON_WORD_RE.sub(" ", text.lower())
    return " ".join(text.split())


def first_heading(path: pathlib.Path) -> str:
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("#"):
                    return stripped
    except OSError:
        return ""
    return ""


def same_title(left: str, right: str) -> bool:
    """Loose match so a rephrased Jira summary is not flagged."""
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Compare token prefixes: word forms change, the subject usually does not.
    a_tokens = [token[:6] for token in a.split()]
    b_tokens = [token[:6] for token in b.split()]
    if not a_tokens or not b_tokens:
        return False
    overlap = len(set(a_tokens) & set(b_tokens)) / max(len(a_tokens), len(b_tokens))
    return overlap >= 0.6


def check(task_dir: pathlib.Path) -> dict[str, object]:
    number = task_dir.name
    task_md = task_dir / "task.md"
    task_json = task_dir / "task.json"

    report: dict[str, object] = {
        "task": number,
        "ok": False,
        "status": "incomplete",
        "checks": [],
        "warnings": [],
    }
    checks: list[dict[str, object]] = report["checks"]  # type: ignore[assignment]

    def record(name: str, actual: object, expected: str, *, casefold: bool = False) -> None:
        if actual is None or actual == "":
            checks.append({"check": name, "ok": None, "detail": "данные отсутствуют"})
            return
        value = str(actual)
        matched = value.casefold() == expected.casefold() if casefold else value == expected
        checks.append({"check": name, "ok": matched, "detail": "" if matched else f"ожидался {expected}, получен {value}"})

    def finish() -> dict[str, object]:
        status = "mismatch" if any(item["ok"] is False for item in checks) else (
            "incomplete" if any(item["ok"] is None for item in checks) else "ok"
        )
        report["status"] = status
        report["ok"] = status == "ok"
        return report

    heading = first_heading(task_md)
    if not task_md.is_file():
        checks.append({"check": "task_md", "ok": False, "detail": "task.md отсутствует"})
        return finish()

    match = re.match(r"^#\s*(?:issue|задача|task)\s*#?([0-9]+)\s*:", heading, re.IGNORECASE)
    record("task_md_id", match.group(1) if match else None, number)

    if not task_json.is_file():
        checks.append({"check": "task_json", "ok": None, "detail": "task.json отсутствует"})
        return finish()

    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        checks.append({"check": "task_json", "ok": False, "detail": f"task.json не читается: {error}"})
        return finish()

    if not isinstance(data, dict):
        checks.append({"check": "task_json", "ok": False, "detail": "task.json должен содержать объект"})
        return finish()

    metadata = data.get("metadata")
    tracker = data.get("tracker")
    git = data.get("git")
    metadata = metadata if isinstance(metadata, dict) else {}
    tracker = tracker if isinstance(tracker, dict) else {}
    git = git if isinstance(git, dict) else {}
    snapshot = tracker.get("snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else {}

    record("id", data.get("id"), f"task:{number}")
    record("task_id", metadata.get("task_id"), number)
    record("issue_key", tracker.get("issue_key"), f"CT-{number}", casefold=True)
    record("snapshot_issue_key", snapshot.get("issue_key"), f"CT-{number}", casefold=True)

    title = metadata.get("title")
    title = title if isinstance(title, str) else ""
    summary = snapshot.get("summary")
    summary = summary if isinstance(summary, str) else ""
    report["task_md_heading"] = heading
    report["task_json_title"] = title
    report["tracker_summary"] = summary
    if not match or not summary:
        checks.append({"check": "tracker_summary", "ok": None, "detail": "заголовок task.md или tracker.snapshot.summary отсутствует"})
    else:
        matched = bool(normalize(heading)) and normalize(heading) == normalize(summary)
        checks.append({"check": "tracker_summary", "ok": matched, "detail": "" if matched else f"task.md: {heading!r} / tracker.snapshot.summary: {summary!r}"})

    if not title:
        report["warnings"].append("metadata.title пуст: сверка заголовка невозможна")
    elif heading and not same_title(heading, title):
        report["warnings"].append(f"metadata.title не совпадает с task.md: {title!r}")

    branch = metadata.get("branch") or git.get("branch") or data.get("branch")
    if branch:
        branch = str(branch)
        branch_ok = bool(re.search(r"(?<!\d)" + re.escape(number) + r"(?!\d)", branch))
        checks.append({"check": "branch", "ok": branch_ok, "detail": "" if branch_ok else f"ветка {branch} не содержит номер задачи {number}"})
    else:
        report["warnings"].append("ветка не указана: сверка ветки невозможна")

    return finish()


def task_dirs() -> list[pathlib.Path]:
    root = REPO / ".doc" / "tasks"
    if not root.is_dir():
        return []
    return sorted(
        (path for path in root.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", help="номер задачи")
    parser.add_argument("--all", action="store_true", help="проверить все задачи")
    parser.add_argument("--tsv", action="store_true", help="компактный вывод TSV")
    args = parser.parse_args(argv)

    if args.all:
        reports = [check(path) for path in task_dirs()]
        failures = [item for item in reports if not item["ok"]]
        if args.tsv:
            for item in reports:
                status = str(item["status"]).upper() if not item["ok"] else "ok"
                detail = ""
                for entry in item.get("checks", []):  # type: ignore[union-attr]
                    if not entry["ok"]:
                        detail = str(entry["detail"])[:120]
                        break
                print(f"{item['task']}\t{status}\t{detail}")
        else:
            print(json.dumps({"total": len(reports), "failed": len(failures), "tasks": reports}, ensure_ascii=False, indent=2))
        return 0 if not failures else 2

    if not args.task:
        parser.error("нужен номер задачи или --all")

    task_dir = REPO / ".doc" / "tasks" / args.task
    if not task_dir.is_dir():
        print(json.dumps({"task": args.task, "ok": False, "error": "task directory not found"}, ensure_ascii=False))
        return 4

    report = check(task_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
