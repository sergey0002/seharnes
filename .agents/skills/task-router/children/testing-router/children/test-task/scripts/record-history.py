#!/usr/bin/env python3
"""Append a compact immutable pointer to the task run history."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def test_rows(run: pathlib.Path) -> list[dict]:
    path = run / "report.xml"
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    rows = []
    for node in root.iter("testcase"):
        status = "passed"
        if node.find("failure") is not None:
            status = "failed"
        elif node.find("error") is not None:
            status = "error"
        elif node.find("skipped") is not None:
            status = "skipped"
        rows.append({
            "test": f"{node.get('class', '')}::{node.get('name', '')}",
            "status": status,
            "time": node.get("time", ""),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run = pathlib.Path(args.run_dir)
    history = run.parent / "history.jsonl"
    verdict = run / "verdict.json"
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": args.task,
        "run": run.name,
        "verdict_sha256": sha256(verdict),
        "manifest_sha256": sha256(run / "manifest.json"),
        "comparison": json.loads((run / "comparison.json").read_text(encoding="utf-8")) if (run / "comparison.json").exists() else {},
    }
    with history.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    test_history = run.parent / "test-history.jsonl"
    with test_history.open("a", encoding="utf-8") as stream:
        for item in test_rows(run):
            stream.write(json.dumps({**row, **item}, ensure_ascii=False, sort_keys=True) + "\n")
    (run / "history-entry.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
