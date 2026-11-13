#!/usr/bin/env python3
"""Compare a run with the previous run of the same task.

This is a regression alarm, not a snapshot oracle. Dynamic HTML and database
IDs are not compared byte-for-byte. The comparison checks the stable contract:
test identities, AC identities, result statuses, console/error evidence and
artifact availability.

Improvements vs a broken/empty baseline (empty AC → all passed) are not failures.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def load(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def previous_run(task_dir: pathlib.Path, current: pathlib.Path) -> pathlib.Path | None:
    root = task_dir / "test-runs"
    candidates = [
        p for p in root.iterdir()
        if p.is_dir() and p != current and (p / "verdict.json").exists()
    ] if root.is_dir() else []
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def test_key(item: dict) -> str:
    return str(item.get("name") or f"{item.get('class', '')}::{item.get('method', '')}")


def stable(verdict: dict, run: pathlib.Path) -> dict:
    tests = verdict.get("tests", {})
    ac = load(run / "ac-results.json")
    return {
        "tests": sorted(
            (test_key(x), x.get("status", ""))
            for x in tests.get("testcases", []) if isinstance(x, dict)
        ) or sorted(tests.get("failedTests", [])),
        "failedTests": sorted(tests.get("failedTests", [])),
        "ac": sorted((str(x.get("id")), str(x.get("status"))) for x in ac.get("results", []) if isinstance(x, dict)),
        "consoleErrors": len(verdict.get("checkpoints", {}).get("consoleErrors", [])),
        "errorModals": len(verdict.get("checkpoints", {}).get("errorModals", [])),
        "artifacts": verdict.get("artifacts", {}),
    }


def status_map(pairs: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in pairs:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out[str(item[0])] = str(item[1])
        elif isinstance(item, str):
            out[item] = "failed"
    return out


BAD = {"failed", "error", "fail"}


def regressions(before: dict, now: dict) -> tuple[list[dict], list[dict]]:
    """Return (blocking_regressions, all_notes)."""
    blocking: list[dict] = []
    notes: list[dict] = []

    before_tests = status_map(before["tests"])
    now_tests = status_map(now["tests"])
    worse_tests = []
    if before_tests and now_tests:
        for name, status in now_tests.items():
            prev = before_tests.get(name)
            if prev and prev not in BAD and status in BAD:
                worse_tests.append({"name": name, "before": prev, "after": status})
        for name, status in before_tests.items():
            if status not in BAD and name not in now_tests:
                worse_tests.append({"name": name, "before": status, "after": "missing"})
    if worse_tests:
        blocking.append({"kind": "test-regression", "items": worse_tests})

    before_ac = status_map(before["ac"])
    now_ac = status_map(now["ac"])
    worse_ac = []
    if before_ac and now_ac:
        for acid, status in now_ac.items():
            prev = before_ac.get(acid)
            if prev and prev not in BAD and status in BAD:
                worse_ac.append({"id": acid, "before": prev, "after": status})
        for acid, status in before_ac.items():
            if status not in BAD and acid not in now_ac:
                worse_ac.append({"id": acid, "before": status, "after": "missing"})
    if worse_ac:
        blocking.append({"kind": "ac-regression", "items": worse_ac})
    elif before["ac"] != now["ac"]:
        notes.append(
            {
                "kind": "ac-results-changed",
                "informative": True,
                "before": before["ac"],
                "after": now["ac"],
            }
        )

    if now["failedTests"]:
        new_fails = sorted(set(now["failedTests"]) - set(before.get("failedTests") or []))
        if new_fails:
            blocking.append({"kind": "current-failures", "tests": now["failedTests"]})

    if now["consoleErrors"] > before["consoleErrors"] or now["errorModals"] > before["errorModals"]:
        if now["consoleErrors"] or now["errorModals"]:
            blocking.append(
                {
                    "kind": "browser-noise",
                    "consoleErrors": now["consoleErrors"],
                    "errorModals": now["errorModals"],
                }
            )

    return blocking, notes + blocking


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    current = pathlib.Path(args.run_dir)
    task_dir = current.parent.parent
    old = previous_run(task_dir, current)
    result: dict = {"schema": 1, "task": args.task, "current": str(current), "status": "no_baseline", "changes": []}

    if old is not None:
        now = stable(load(current / "verdict.json"), current)
        before = stable(load(old / "verdict.json"), old)
        blocking, all_changes = regressions(before, now)
        result.update(
            {
                "status": "failed" if blocking else "passed",
                "previous": str(old),
                "changes": all_changes,
            }
        )

    (current / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
