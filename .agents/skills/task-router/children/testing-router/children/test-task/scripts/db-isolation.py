#!/usr/bin/env python3
"""Run an explicit, project-provided DB reset/cleanup hook.

No SQL is guessed here.  A task marked as requiring isolation must provide
QA_DB_RESET_CMD and QA_DB_CLEANUP_CMD, so test data cannot leak silently.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import re

REPO = pathlib.Path(__file__).resolve().parents[8]


def required(task: str) -> bool:
    path = REPO / ".doc" / "tasks" / task / "ac-matrix.json"
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("db_isolation", "not_required") == "required"
    except (OSError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()
    run_dir = pathlib.Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if not required(args.task):
        result = {"status": "skipped", "phase": args.phase, "reason": "matrix marks DB isolation not_required"}
    else:
        variable = "QA_DB_RESET_CMD" if args.phase == "before" else "QA_DB_CLEANUP_CMD"
        command = os.environ.get(variable, "").strip()
        if not command:
            result = {"status": "failed", "phase": args.phase, "reason": f"{variable} не задан"}
        elif re.fullmatch(r"(?:true|:|echo(?:\s+true)?|/bin/true)", command, re.IGNORECASE):
            result = {"status": "failed", "phase": args.phase,
                      "command": command, "reason": "no-op hooks are not database isolation"}
        else:
            try:
                process = subprocess.run(command, cwd=REPO, shell=True, capture_output=True, text=True, timeout=300)
                result = {"status": "passed" if process.returncode == 0 else "failed", "phase": args.phase, "command": command, "exit_code": process.returncode, "output": (process.stdout + process.stderr)[-4000:]}
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {"status": "failed", "phase": args.phase, "command": command, "reason": str(exc)}
    path = run_dir / "db-isolation.json"
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {"phases": []}
    else:
        previous = {"phases": []}
    previous.setdefault("phases", []).append(result)
    # Aggregate honestly. `not_required` means isolation never ran, so it must
    # not be reported as `passed`: G12 used to print "DB isolation confirmed"
    # over zero real phases, which is a false-green for any task touching data.
    phase_statuses = {item.get("status") for item in previous["phases"]}
    if phase_statuses <= {"skipped"}:
        previous["status"] = "not_required"
    elif "passed" in phase_statuses and phase_statuses <= {"passed", "skipped"}:
        previous["status"] = "passed"
    else:
        previous["status"] = "failed"
    path.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("passed", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
