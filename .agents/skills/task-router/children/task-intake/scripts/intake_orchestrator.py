#!/usr/bin/env python3
"""Run the deterministic part of task intake.

Combines the state preflight, Jira export, tracker ingest and diff into one
call. It never writes documentation, business rules or reports and never
switches a branch. Each step is skipped when its artifact is already fresh.
The agent gets one compact JSON with what ran, what failed and what to do next.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intake_state  # noqa: E402

TAIL = 600


def powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


def run(command, cwd, timeout):
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, type(exc).__name__ + ": " + str(exc)
    tail = (proc.stdout + proc.stderr).strip()
    return proc.returncode, tail


def step(steps, name, code, tail):
    steps.append({"name": name, "status": "ok" if code == 0 else "failed",
                  "exit": code, "tail": tail[-TAIL:] if code else ""})
    return code == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--task", required=True, help="task number, digits")
    parser.add_argument("--force", action="store_true",
                        help="run export and diff even when artifacts exist")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--skip-diff", action="store_true")
    parser.add_argument("--no-network", action="store_true",
                        help="pass -SkipFetch to task-diff")
    args = parser.parse_args()

    import re
    if not re.fullmatch(r"[0-9]+", args.task or ""):
        print(json.dumps({"status": "error", "error": "task must be digits"},
                         ensure_ascii=False))
        return 2
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "error": "root not found"},
                         ensure_ascii=False))
        return 2

    powershell_exe = powershell()
    gototask = root / ".agents/skills/task-router/children/gototask/scripts/gototask.ps1"
    task_diff = root / ".agents/skills/task-router/children/task-diff/scripts/task-diff.ps1"
    jsondoc = root / ".agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py"

    steps = []
    errors = []
    state = intake_state.build_state(root, args.task)
    export_needed = (args.force or state.get("next_action") == "fetch"
                     or not state["files"]["task.md"])
    if export_needed:
        if args.skip_export:
            steps.append({"name": "export", "status": "skipped", "exit": 0,
                          "tail": ""})
        elif not powershell_exe or not gototask.is_file():
            errors.append("export unavailable: PowerShell or gototask.ps1 missing")
            steps.append({"name": "export", "status": "failed", "exit": 127,
                          "tail": errors[-1]})
        else:
            code, tail = run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(gototask), "-TaskNumber", args.task,
                 "-Action", "export-task"],
                root, 240)
            step(steps, "export", code, tail)
            if code != 0:
                errors.append("export failed")
            else:
                try:
                    result = json.loads(tail)
                    exported = result.get("taskExport")
                    ingest = result.get("jsondocIngest")
                    if not isinstance(exported, dict) or exported.get("ok") is not True:
                        errors.append("export failed")
                        steps[-1]["status"] = "failed"
                    if not isinstance(ingest, dict):
                        ingest = {"status": "error", "reason": "missing ingest result"}
                    steps.append({"name": "ingest-tracker", **ingest})
                    if ingest.get("status") != "success":
                        errors.append("ingest-tracker " + str(ingest.get("status", "error")))
                except (ValueError, AttributeError):
                    errors.append("export result invalid")
                    steps[-1]["status"] = "failed"
                state = intake_state.build_state(root, args.task)

        if (not errors and args.skip_export and not state["files"]["task.json"]
                and state["files"]["task.md"] and jsondoc.is_file()):
            tracker = (root / ".doc/tasks" / args.task
                       / "_jsondoc/work/tracker.json")
            if tracker.is_file():
                code, tail = run(
                    [sys.executable, str(jsondoc), "--root", str(root),
                     "ingest-tracker", "--task", args.task,
                     "--input", str(tracker)],
                    root, 120)
                step(steps, "ingest-tracker", code, tail)
                if code != 0:
                    errors.append("ingest-tracker failed")
                state = intake_state.build_state(root, args.task)

    diff_missing = (not state["files"]["diff.md"]
                    or state["freshness"].get("diff_vs_task") == "stale")
    diff_needed = (args.force or diff_missing
                   or state.get("next_action") in ("fetch", "diff"))
    identity_status = state.get("identity", {}).get("status", "unavailable")
    if identity_status != "ok":
        errors.append("identity " + identity_status)
    if diff_needed and not errors:
        if args.skip_diff:
            steps.append({"name": "diff", "status": "skipped", "exit": 0,
                          "tail": ""})
        elif not diff_missing and not args.force:
            steps.append({"name": "diff", "status": "skipped", "exit": 0,
                          "tail": "fresh"})
        elif not powershell_exe or not task_diff.is_file():
            errors.append("diff unavailable: PowerShell or task-diff.ps1 missing")
            steps.append({"name": "diff", "status": "failed", "exit": 127,
                          "tail": errors[-1]})
        else:
            command = [powershell_exe, "-NoProfile", "-ExecutionPolicy",
                       "Bypass", "-File", str(task_diff), "-TaskNumber",
                       args.task]
            if args.no_network:
                command.append("-SkipFetch")
            code, tail = run(command, root, 300)
            step(steps, "diff", code, tail)
            if code != 0:
                errors.append("diff failed")
            state = intake_state.build_state(root, args.task)

    warnings = []
    if state.get("identity", {}).get("status") != "ok":
        warnings.append("identity_" + state.get("identity", {}).get("status", "unavailable"))
    if state.get("legacy") and not state["files"]["diff.md"]:
        warnings.append("legacy_without_diff")
    if state.get("generated_views", {}).get("edit_route") != "direct":
        warnings.append("architecture_md_is_generated")

    payload = {
        "status": "error" if errors else "ok",
        "task": args.task,
        "steps": steps,
        "errors": errors,
        "warnings": warnings,
        "state": state,
        "next_action": state.get("next_action"),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
