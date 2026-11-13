"""Corpus level: workflow fingerprint, antipattern candidates, metric history."""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

DOMAINS = (
    ("lib/", "lib"),
    ("admin/lib/", "admin-lib"),
    ("templates/", "templates"),
    ("frontend/", "frontend"),
    ("tests/", "tests"),
    ("sql/", "sql"),
    (".doc/tasks/", "task-docs"),
    (".doc/architecture/", "arch-docs"),
    (".cursor/", "harness"),
)


def _domains(files):
    found = set()
    for path in files:
        for prefix, name in DOMAINS:
            if prefix in path:
                found.add(name)
                break
    return sorted(found)


def fingerprint(facts, analysis):
    skills = sorted({event["skill_name"] for event in facts["events"] if event.get("skill_name")})
    classes = sorted({row["class"] for row in analysis["tools"]})
    payload = {
        "skills": skills,
        "domains": _domains(analysis["files_touched"]),
        "classes": classes,
    }
    key = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return {"key": key, **payload}


def aggregate(items):
    """items: [{'facts':..., 'analysis':..., 'workflow':...}]"""
    groups = {}
    for item in items:
        workflow = item["workflow"]["key"]
        total_tokens = (
            item["analysis"]["token_ledger"]["input_total"]
            + item["analysis"]["token_ledger"]["output"]
            + item["analysis"]["token_ledger"]["reasoning"]
        )
        for finding in item["analysis"]["findings"]:
            component = finding.get("component") or "task"
            key = (finding["code"], component)
            slot = groups.setdefault(key, {
                "fingerprint": f"{finding['code']}:{component}",
                "code": finding["code"],
                "component": component,
                "count": 0,
                "sessions": set(),
                "workflows": set(),
                "tokens": [],
            })
            slot["count"] += 1
            slot["sessions"].add(item["facts"]["session_id"])
            slot["workflows"].add(workflow)
            slot["tokens"].append(total_tokens)

    rules = []
    for slot in groups.values():
        if slot["count"] < 3:
            continue
        rules.append({
            "fingerprint": slot["fingerprint"],
            "code": slot["code"],
            "component": slot["component"],
            "count": slot["count"],
            "sessions": len(slot["sessions"]),
            "workflows": len(slot["workflows"]),
            "median_tokens": int(statistics.median(slot["tokens"])) if slot["tokens"] else 0,
            "status": "candidate",
            "evidence_session_ids": sorted(slot["sessions"])[:20],
        })
    rules.sort(key=lambda rule: (-rule["count"], rule["fingerprint"]))
    return rules


def history_line(items, stage, scope):
    tokens = []
    first_pass = 0
    rework = 0
    reasoning = 0
    total = 0
    for item in items:
        ledger = item["analysis"]["token_ledger"]
        token_total = ledger["input_total"] + ledger["output"] + ledger["reasoning"]
        tokens.append(token_total)
        reasoning += ledger["reasoning"]
        total += token_total
        for slice_ in item.get("slices", []):
            if slice_["outcome"] == "first-pass":
                first_pass += 1
            elif slice_["outcome"] == "rework":
                rework += 1
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "stage": stage,
        "scope": scope,
        "sessions": len(items),
        "median_tokens": int(statistics.median(tokens)) if tokens else 0,
        "p95_tokens": int(sorted(tokens)[max(0, int(len(tokens) * 0.95) - 1)]) if tokens else 0,
        "reasoning_share": round(reasoning / total, 4) if total else 0.0,
        "first_pass": first_pass,
        "rework": rework,
    }


def append_history(path, line):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if path.exists():
        lines = [row for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]
        if lines:
            try:
                previous = json.loads(lines[-1])
            except ValueError:
                previous = None
    if previous == line:
        return False
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    return True
