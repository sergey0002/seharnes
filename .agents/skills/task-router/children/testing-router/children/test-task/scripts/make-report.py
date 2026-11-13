#!/usr/bin/env python3
"""Create the single formal Markdown report for one test run."""
from __future__ import annotations

import argparse
import json
import pathlib
import xml.etree.ElementTree as ET


def read_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def cases(run: pathlib.Path) -> list[dict]:
    path = run / "report.xml"
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    result = []
    for node in root.iter("testcase"):
        status = "passed"
        if node.find("failure") is not None:
            status = "failed"
        elif node.find("error") is not None:
            status = "error"
        elif node.find("skipped") is not None:
            status = "skipped"
        result.append({
            "test": f"{node.get('class', '')}::{node.get('name', '')}",
            "status": status,
            "time": node.get("time", ""),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run = pathlib.Path(args.run_dir)
    verdict = read_json(run / "verdict.json")
    ac = read_json(run / "ac-results.json")
    comparison = read_json(run / "comparison.json")
    llm = read_json(run / "llm-review.json")
    manifest = read_json(run / "manifest.json")
    prechecks = []
    if (run / "prechecks.jsonl").exists():
        for line in (run / "prechecks.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                prechecks.append(json.loads(line))

    test_cases = cases(run)
    lines = [
        "---",
        "type: qa-test-run",
        f"task: {args.task}",
        f"run: {run.name}",
        f"status: {'passed' if verdict.get('green') else 'failed'}",
        "---",
        "",
        f"# QA report CT-{args.task}",
        "",
        "## 1. Run identity",
        "",
        f"- Run directory: `{run}`",
        f"- Group: `{verdict.get('group', '')}`",
        f"- Exit code: `{verdict.get('exitCode', '')}`",
        f"- Code SHA-256: `{manifest.get('code_sha256', '')}`",
        f"- Tests SHA-256: `{manifest.get('tests_sha256', '')}`",
        f"- Requirements SHA-256: `{manifest.get('requirements_sha256', '')}`",
        f"- Skills SHA-256: `{manifest.get('skills_sha256', '')}`",
        f"- Hashes match at verdict: `{verdict.get('hashesMatch', False)}`",
        "",
        "## 2. Mandatory prechecks",
        "",
        "| Check | Exit code | Status |",
        "|---|---:|---|",
    ]
    for item in prechecks:
        lines.append(f"| `{item.get('name', '')}` | {item.get('exit_code', '')} | {'passed' if item.get('exit_code') == 0 else 'failed'} |")

    lines += ["", "## 3. Every test", "", "| Test | Status | Time |", "|---|---|---:|"]
    for item in test_cases:
        lines.append(f"| `{item['test']}` | {item['status']} | {item['time']} |")
    if not test_cases:
        lines.append("| Browser tests were not executed | blocked | |")

    lines += ["", "## 4. Acceptance criteria", "", "| AC-ID | Status | Evidence |", "|---|---|---|"]
    for item in ac.get("results", []):
        evidence = str(item.get("evidence", "")).replace("|", "/")
        lines.append(f"| `{item.get('id', '')}` | {item.get('status', '')} | {evidence} |")
    if not ac.get("results"):
        lines.append("| none | missing | No executable AC evidence |")

    lines += [
        "", "## 5. Regression comparison", "",
        f"- Baseline: `{comparison.get('previous', 'none')}`",
        f"- Comparison status: `{comparison.get('status', 'missing')}`",
    ]
    for change in comparison.get("changes", []):
        lines.append(f"- Change: `{json.dumps(change, ensure_ascii=False, sort_keys=True)}`")

    lines += [
        "", "## 6. Browser evidence", "",
        f"- Checkpoints: `{verdict.get('checkpoints', {}).get('count', 0)}`",
        f"- Console errors: `{len(verdict.get('checkpoints', {}).get('consoleErrors', []))}`",
        f"- Error modals: `{len(verdict.get('checkpoints', {}).get('errorModals', []))}`",
        f"- Screenshots: `{len(verdict.get('screenshots', []))}`",
        "",
        "## 7. LLM review",
        "",
        f"- Status: `{llm.get('status', 'missing')}`",
        f"- Decision: `{llm.get('decision', 'review')}`",
        f"- Input SHA-256: `{llm.get('inputSha256', '')}`",
        f"- Summary: {llm.get('summary', llm.get('reason', 'not configured'))}",
        "",
        "## 8. Final verdict",
        "",
        f"`{'PASS' if verdict.get('green') else 'FAIL'}`",
        "",
        "A green LLM review never overrides a red deterministic gate. A missing or failed mandatory layer keeps the final verdict red.",
        "",
    ]
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(run / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
