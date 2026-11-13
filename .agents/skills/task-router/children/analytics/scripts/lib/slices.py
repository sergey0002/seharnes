"""Plan slices: start mask, end masks, deterministic outcome."""

from __future__ import annotations

import hashlib

DEFAULT = {
    "start_skills": ["prepare-plan"],
    "markers": ["passed", "failed"],
}


def _token_total(messages, start, end):
    total = 0
    for message in messages:
        if start <= message["t"] <= end and message.get("tokens"):
            tokens = message["tokens"]
            total += tokens["input"] + tokens["output"] + tokens["reasoning"]
    return total


def build_slices(events, messages, config=None, task=None):
    config = {**DEFAULT, **(config or {})}
    starts = [
        event for event in events
        if event.get("skill_name") in config["start_skills"]
    ]
    if not starts:
        return []
    result = []
    for index, start in enumerate(starts):
        end = starts[index + 1]["t"] if index + 1 < len(starts) else (events[-1]["t"] if events else start["t"])
        inside = [event for event in events if start["t"] <= event["t"] < end]
        markers = [
            event for event in inside
            if (event.get("plan_marker") or event.get("plan_ready"))
            and (not task or event.get("plan_task") in (None, str(task)))
        ]
        end_event = markers[-1] if markers else (inside[-1] if inside else start)
        outcome = "unknown"
        statuses = [
            event["plan_marker"] or ("ready" if event.get("plan_ready") else None)
            for event in markers
        ]
        statuses = [status for status in statuses if status]
        if statuses:
            if "failed" in statuses and statuses[-1] in ("passed", "ready"):
                outcome = "rework"
            elif statuses[-1] in ("passed", "ready") and "failed" not in statuses:
                outcome = "first-pass"
            elif statuses[-1] == "failed":
                outcome = "blocked"
        result.append({
            "slice_id": hashlib.sha1(start["event_id"].encode("utf-8")).hexdigest()[:10],
            "start_event_id": start["event_id"],
            "end_event_id": end_event["event_id"],
            "start_t": start["t"],
            "end_t": end_event["t"],
            "outcome": outcome,
            "tokens": _token_total(messages, start["t"], end_event["t"]),
            "markers": statuses,
        })
    return result
