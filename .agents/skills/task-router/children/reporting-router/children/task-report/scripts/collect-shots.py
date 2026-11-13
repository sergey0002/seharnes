#!/usr/bin/env python3
"""Скрины прогона для отчёта в Jira.

Usage (Cursor):
  python3 .cursor/skills/task-router/children/task-report/scripts/collect-shots.py TASK [MAX]
Usage (Codex):
  python3 .codex/skills/task-router/children/reporting-router/children/task-report/scripts/collect-shots.py TASK [MAX]
"""
import re
import json
import sys
from pathlib import Path


def repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".doc" / "tasks").is_dir() and (p / "AGENTS.md").is_file():
            return p
    raise SystemExit("repo root not found")


ROOT = repo_root(Path(__file__).resolve())


def caption(path: Path) -> str:
    name = path.stem
    name = re.sub(r"^\d+[a-z]?-", "", name)
    name = re.sub(r"^\d+-", "", name)
    name = re.sub(r"-", " ", name).strip()
    return name or path.name


def score(path: Path) -> int:
    n = path.stem.lower()
    plus = ("result", "view", "card", "form", "after", "done", "success", "order", "ok")
    minus = ("foreign", "fake", "login", "console", "before", "debug")
    s = 0
    for w in plus:
        if w in n:
            s += 2
    for w in minus:
        if w in n:
            s -= 2
    return s


def read_verdict_status(run_dir: Path) -> str:
    """Fallback status source when a run has no report.md."""
    verdict = run_dir / "verdict.json"
    if verdict.is_file():
        try:
            data = json.loads(verdict.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "unknown"
        if data.get("green"):
            return "passed"
        return "failed"
    return "unknown"


def read_status(report: Path) -> str:
    text = report.read_text(encoding="utf-8", errors="replace")[:800]
    m = re.search(r"^status:\s*(\S+)", text, re.M)
    if m:
        return m.group(1).strip().strip("'\"")
    if re.search(r"\bPASS\b", text):
        return "passed"
    if re.search(r"\bFAIL\b", text):
        return "failed"
    return "unknown"


def pngs(folder: Path) -> list:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.png") if p.is_file())


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("usage: collect-shots.py TASK [MAX]", file=sys.stderr)
        return 2
    task = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    base = ROOT / ".doc" / "tasks" / task
    if not base.is_dir():
        print(f"no task dir: {base}")
        return 1

    hand = []
    for rel in (base / "screenshots", base / "test-runs" / "screenshots"):
        hand.extend(pngs(rel))

    runs = []
    tr = base / "test-runs"
    if tr.is_dir():
        for d in sorted(tr.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            # report.md is the preferred source of the run status, but its
            # absence must not discard the run: some runners write only
            # verdict.json plus screenshots, and those shots were lost.
            shots = pngs(d / "debug") + pngs(d)
            if not shots:
                continue
            report = d / "report.md"
            status = read_status(report) if report.is_file() else read_verdict_status(d)
            runs.append((d.name, status, shots, d))

    passed = [r for r in runs if r[1] == "passed" and r[2]]
    chosen = passed[0] if passed else next((r for r in runs if r[2]), None)

    print(f"task: {task}")
    if hand:
        print("hand: screenshots/")
        show = hand[:limit]
        for p in show:
            print(f"SHOT\t{p.relative_to(ROOT)}\t{caption(p)}")
        if len(hand) > limit:
            print(f"more: {len(hand) - limit} in screenshots/")
        return 0

    if not chosen:
        print("run: none")
        print("shots: 0")
        return 0

    name, status, shots, folder = chosen
    ranked = sorted(shots, key=lambda p: (-score(p), p.name))
    print(f"run: {name}")
    print(f"status: {status}")
    print(f"shots: {len(shots)}")
    for p in ranked[:limit]:
        print(f"SHOT\t{p.relative_to(ROOT)}\t{caption(p)}")
    if len(shots) > limit:
        print(f"more: {len(shots) - limit} in {folder.relative_to(ROOT)}/debug")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
