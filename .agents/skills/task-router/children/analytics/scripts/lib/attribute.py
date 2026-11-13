"""Attribute sessions to tasks with explicit, combinable evidence.

Signals are combined with a noisy-OR: p = 1 - product(1 - weight). Weights are
chosen so that a single weak mention cannot assign a session, while a directive
phrase or an early task file touch can. Anchors always win.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TASK_PATH = re.compile(r"\.doc/tasks/(\d{2,4})/")
BRANCH = re.compile(r"(?:bugfixes|features)/[^\s\"']*?#?(\d{2,4})")
TASK_FILE = re.compile(r"\.doc/tasks/(\d{2,4})/(?:task\.md|task\.json)")

DIRECTIVE = (
    re.compile(r"(?:перейди|перейти|переключись|переключиться|открой|открыть|займись|берись|возьми)\s+(?:в\s+)?(?:к\s+)?задач[аеиу]?\s*#?\s*(\d{2,4})", re.I),
    re.compile(r"(?:go\s+to|switch\s+to|open|work\s+on)\s+(?:the\s+)?task\s*#?\s*(\d{2,4})", re.I),
)
DECLARATIVE = re.compile(r"(?<![\w/.-])задач[аеиу]?\s*#?\s*(\d{2,4})", re.I)
CT = re.compile(r"\bCT[-_ ]?(\d{2,4})\b", re.I)
BARE = re.compile(r"(?<![\w/.-])#(\d{2,4})\b")

WEIGHTS = {
    "anchor": 1.0,
    "task_path": 0.9,
    "early_task_file": 0.8,
    "first_message_directive": 0.85,
    "first_message_declarative": 0.7,
    "first_message_ct": 0.7,
    "first_message_bare": 0.45,
    "early_branch": 0.5,
}

THRESHOLD = 0.75
MARGIN = 0.15


GENERIC = {
    "продолжи", "продолжай", "продолжаем", "давай", "да", "ок", "поехали",
    "приступай", "делай", "дальше", "что дальше", "go on", "continue",
}


def _normalize(text):
    return " ".join(str(text or "").lower().split())


def quote_has_task(quote, task):
    return re.search(rf"(?<!\d){re.escape(str(task))}(?!\d)", quote or "") is not None


def is_distinctive(anchor):
    quote = _normalize(anchor.get("quote"))
    if not quote or quote in GENERIC:
        return False
    if anchor.get("source") == "manual-assign":
        return len(quote) >= 10
    if len(quote) < 20:
        return False
    return quote_has_task(quote, anchor["task"])


def load_anchors(tasks_root):
    anchors = []
    root = Path(tasks_root)
    if not root.is_dir():
        return anchors
    for path in root.glob("*/_dialogs/anchor.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        task = str(payload.get("task") or path.parent.parent.name)
        anchors.append({
            "task": task,
            "branch": payload.get("branch") or "",
            "created_at": payload.get("created_at") or "",
            "quote": _normalize(payload.get("quote")),
        })
    return anchors


def _task_mentions(facts):
    counts = {}
    for event in facts["events"]:
        blob = f"{event.get('arg_text') or ''} {event.get('target') or ''}"
        for match in TASK_PATH.finditer(blob):
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def _first_message_weights(text):
    """Return {task: weight} using the strongest phrase per task."""
    weights = {}
    text = text or ""
    for pattern in DIRECTIVE:
        for match in pattern.finditer(text):
            weights[match.group(1)] = max(weights.get(match.group(1), 0), WEIGHTS["first_message_directive"])
    for match in DECLARATIVE.finditer(text):
        weights.setdefault(match.group(1), WEIGHTS["first_message_declarative"])
    for match in CT.finditer(text):
        weights.setdefault(match.group(1), WEIGHTS["first_message_ct"])
    for match in BARE.finditer(text):
        weights.setdefault(match.group(1), WEIGHTS["first_message_bare"])
    return weights


def _early_evidence(facts):
    weights = {}
    for event in facts["events"][:5]:
        blob = f"{event.get('arg_text') or ''} {event.get('target') or ''}"
        for match in TASK_FILE.finditer(blob):
            weights[match.group(1)] = max(weights.get(match.group(1), 0), WEIGHTS["early_task_file"])
        if "gototask" in blob.lower():
            for match in TASK_PATH.finditer(blob):
                weights[match.group(1)] = max(weights.get(match.group(1), 0), WEIGHTS["early_task_file"])
    for event in facts["events"][:10]:
        blob = f"{event.get('arg_text') or ''} {event.get('target') or ''}"
        for match in BRANCH.finditer(blob):
            weights[match.group(1)] = max(weights.get(match.group(1), 0), WEIGHTS["early_branch"])
    return weights


def _combine(weights):
    remaining = 1.0
    for weight in weights:
        remaining *= (1.0 - weight)
    return 1.0 - remaining


def attribute(facts, anchors, first_user_text=""):
    mentions = _task_mentions(facts)
    quote = _normalize(first_user_text)
    evidence = {}

    for anchor in anchors:
        if is_distinctive(anchor) and quote and quote.startswith(anchor["quote"][:120]):
            evidence.setdefault(anchor["task"], []).append(
                {"signal": "anchor", "weight": WEIGHTS["anchor"]}
            )

    total = sum(mentions.values())
    if total >= 5 and mentions:
        task, count = max(mentions.items(), key=lambda item: item[1])
        if count / total >= 0.6:
            evidence.setdefault(task, []).append(
                {"signal": "task_path", "weight": WEIGHTS["task_path"]}
            )

    for task, weight in _early_evidence(facts).items():
        signal = "early_task_file" if weight == WEIGHTS["early_task_file"] else "early_branch"
        evidence.setdefault(task, []).append({"signal": signal, "weight": weight})

    for task, weight in _first_message_weights(first_user_text).items():
        signal = {
            WEIGHTS["first_message_directive"]: "first_message_directive",
            WEIGHTS["first_message_declarative"]: "first_message_declarative",
            WEIGHTS["first_message_ct"]: "first_message_ct",
            WEIGHTS["first_message_bare"]: "first_message_bare",
        }.get(weight, "first_message")
        evidence.setdefault(task, []).append({"signal": signal, "weight": weight})

    candidates = []
    for task, signals in evidence.items():
        probability = _combine([item["weight"] for item in signals])
        candidates.append({
            "task": task,
            "probability": round(probability, 4),
            "signals": signals,
        })
    candidates.sort(key=lambda item: (-item["probability"], item["task"]))

    status = "unassigned"
    task = None
    confidence = 0.0
    if candidates:
        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        has_anchor = any(item["signal"] == "anchor" for item in top["signals"])
        gap = top["probability"] - (second["probability"] if second else 0.0)
        confidence = top["probability"]
        if has_anchor:
            status, task = "assigned", top["task"]
        elif top["probability"] >= THRESHOLD and (second is None or gap >= MARGIN):
            status, task = "assigned", top["task"]
        elif top["probability"] >= 0.6 and second is None:
            status, task = "assigned", top["task"]
        elif top["probability"] >= 0.6:
            status = "ambiguous"

    return {
        "task": task,
        "confidence": confidence,
        "status": status,
        "attribution": [item for item in (candidates[0]["signals"] if candidates and task else [])],
        "mentioned_tasks": sorted(mentions),
        "candidates": candidates[:3],
    }
