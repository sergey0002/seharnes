#!/usr/bin/env python3
"""Remove old test run directories from task folders.

The run date is read from the run content, never from the filesystem mtime.
Dry-run is the default; deletion requires --apply.

Usage:
  python3 cleanup-test-runs.py --days 14
  python3 cleanup-test-runs.py --days 14 --apply
  python3 cleanup-test-runs.py --days 14 --task 2070 --json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

DEFAULT_DAYS = 14
JSON_FILES = ("verdict.json", "manifest.json", "history-entry.json", "ac-source.json")
DATE_KEY_ORDER = (
    "run_date", "rundir", "run_dir", "created_at", "createdat", "started_at",
    "timestamp", "date", "run", "generated_at", "finished_at",
)
ISO_RE = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
DOTTED_RE = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(20\d{2})(?!\d)")
COMPACT_RE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
DIR_NAME_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
FRONTMATTER_RUN_RE = re.compile(
    r"(?mi)^\s*(?:run|date|created_at|started_at|finished_at|generated_at)\s*:\s*(.+)$"
)
REFERENCE_RE = re.compile(r"\.doc/tasks/[0-9]+/test-runs/[^\s\"'<>)\],;]+")
REFERENCE_FILES = ("doc.md", "test.md", "task.md", "plan.md", "task.json", "diff.md", "diff.files.md")


def project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
        if (candidate / ".doc").is_dir() and (candidate / ".agents").is_dir():
            return candidate
    return start


def make_date(year: str, month: str, day: str):
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def dates_in_text(text: str) -> list[date]:
    found: list[date] = []
    for match in ISO_RE.finditer(text):
        parsed = make_date(*match.groups())
        if parsed:
            found.append(parsed)
    for match in DOTTED_RE.finditer(text):
        parsed = make_date(match.group(3), match.group(2), match.group(1))
        if parsed:
            found.append(parsed)
    for match in COMPACT_RE.finditer(text):
        parsed = make_date(*match.groups())
        if parsed:
            found.append(parsed)
    return found


def json_dates(value, key: str = "") -> list[tuple[str, date]]:
    found: list[tuple[str, date]] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            found.extend(json_dates(child_value, str(child_key)))
    elif isinstance(value, list):
        for item in value:
            found.extend(json_dates(item, key))
    elif isinstance(value, str):
        lowered = key.lower()
        if any(hint in lowered for hint in ("date", "time", "run", "created", "started", "finished", "generated")):
            found.extend((lowered, parsed) for parsed in dates_in_text(value))
    return found


def json_date(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return None
    found = json_dates(data)
    for wanted in DATE_KEY_ORDER:
        for key, parsed in found:
            if key == wanted:
                return parsed
    return found[0][1] if found else None


def report_date(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for match in FRONTMATTER_RUN_RE.finditer(text[3:end]):
                parsed = dates_in_text(match.group(1))
                if parsed:
                    return parsed[0]
    parsed = dates_in_text(text)
    return parsed[0] if parsed else None


def run_date(run_dir: Path) -> tuple[date | None, str]:
    report = run_dir / "report.md"
    if report.is_file():
        parsed = report_date(report)
        if parsed:
            return parsed, "report.md"
    for name in JSON_FILES:
        path = run_dir / name
        if path.is_file():
            parsed = json_date(path)
            if parsed:
                return parsed, name
    match = DIR_NAME_RE.search(run_dir.name)
    if match:
        parsed = make_date(*match.groups())
        if parsed:
            return parsed, "directory name"
    return None, "no date in content"


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def referenced_paths(root: Path) -> set[str]:
    refs: set[str] = set()
    tasks_root = root / ".doc" / "tasks"
    for task_dir in tasks_root.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith("."):
            continue
        files = [task_dir / name for name in REFERENCE_FILES]
        reports = task_dir / "reports"
        if reports.is_dir():
            files.extend(path for path in reports.rglob("*") if path.is_file())
        files.extend(task_dir.glob("stage*/plan.md"))
        for path in files:
            if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in REFERENCE_RE.finditer(text):
                refs.add(match.group(0).rstrip(".,;:"))
    return refs


def collect(root: Path, days: int, task_filter: str | None, include_files: bool, today: date, protect: bool):
    tasks_root = root / ".doc" / "tasks"
    if not tasks_root.is_dir():
        raise ValueError(f"нет каталога задач: {tasks_root}")
    cutoff = today - timedelta(days=days)
    refs = referenced_paths(root) if protect else set()
    candidates: list[dict] = []
    protected: list[dict] = []
    undated: list[dict] = []
    errors: list[dict] = []
    for task_dir in sorted(tasks_root.iterdir()):
        if not task_dir.is_dir() or task_dir.name.startswith("."):
            continue
        if task_filter and task_dir.name != task_filter:
            continue
        runs_root = task_dir / "test-runs"
        if not runs_root.is_dir():
            continue
        for entry in sorted(runs_root.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                errors.append({"task": task_dir.name, "path": str(entry), "reason": "symlink"})
                continue
            if entry.is_dir():
                parsed, source = run_date(entry)
            elif include_files and entry.is_file():
                parsed = report_date(entry)
                source = "file content"
            else:
                continue
            if parsed is None:
                undated.append({"task": task_dir.name, "path": str(entry), "source": source})
                continue
            age = (today - parsed).days
            item = {
                "task": task_dir.name,
                "path": str(entry),
                "date": parsed.isoformat(),
                "source": source,
                "age_days": age,
            }
            if parsed < cutoff:
                relative = entry.relative_to(root).as_posix()
                if protect and any(ref == relative or ref.startswith(relative + "/") for ref in refs):
                    protected.append(item)
                    continue
                candidates.append(item)
    return cutoff, candidates, protected, undated, errors


def remove(root: Path, item: dict) -> str | None:
    path = Path(item["path"])
    runs_root = root / ".doc" / "tasks" / item["task"] / "test-runs"
    if path.is_symlink() or not inside(path, runs_root) or path == runs_root:
        return "path outside test-runs"
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        return str(exc)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Удалить старые прогоны тестов из папок задач")
    parser.add_argument("--root", default=".", help="корень проекта")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="хранить прогоны младше N дней")
    parser.add_argument("--task", help="только эта задача")
    parser.add_argument("--include-files", action="store_true", help="учитывать файлы верхнего уровня test-runs")
    parser.add_argument("--apply", action="store_true", help="удалить найденные каталоги")
    parser.add_argument("--ignore-reports", action="store_true", help="не защищать прогоны, на которые ссылаются отчёты задач")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    parser.add_argument("--now", help="текущая дата YYYY-MM-DD для проверки")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days должен быть больше 0")
    try:
        today = date.fromisoformat(args.now) if args.now else date.today()
    except ValueError:
        parser.error("--now должен быть в формате YYYY-MM-DD")
    root = project_root(Path(args.root).resolve())
    try:
        cutoff, candidates, protected, undated, errors = collect(
            root, args.days, args.task, args.include_files, today, not args.ignore_reports)
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    removed = 0
    if args.apply:
        for item in candidates:
            failure = remove(root, item)
            item["deleted"] = failure is None
            if failure:
                item["error"] = failure
                errors.append({"task": item["task"], "path": item["path"], "reason": failure})
            else:
                removed += 1
    payload = {
        "status": "ok" if not errors else "partial",
        "root": str(root),
        "cutoff": cutoff.isoformat(),
        "days": args.days,
        "dry_run": not args.apply,
        "candidates": candidates,
        "protected": protected,
        "removed": removed,
        "undated": undated,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode} cutoff={payload['cutoff']} days={args.days} candidates={len(candidates)} protected={len(protected)}")
        for item in candidates:
            state = "deleted" if item.get("deleted") else ("failed" if item.get("error") else "would delete")
            print(f"  {state} task={item['task']} run={item['path']} date={item['date']} source={item['source']} age={item['age_days']}d")
        for item in protected:
            print(f"  keep protected task={item['task']} run={item['path']} date={item['date']}")
        for item in undated:
            print(f"  skip undated task={item['task']} run={item['path']} ({item['source']})")
        for item in errors:
            print(f"  error task={item['task']} run={item['path']}: {item['reason']}", file=sys.stderr)
        print(f"removed={removed} undated={len(undated)} errors={len(errors)}")
        if not args.apply and candidates:
            print("Для удаления повторить с --apply")
    return 0 if not errors else 3


if __name__ == "__main__":
    raise SystemExit(main())
