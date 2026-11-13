"""Check that a skill window contains its mandatory calls.

The mapping lives in assets/config/required-calls.json. A marker is a plain substring
of a command, a file target, or an MCP tool name inside an execute batch.
"""

from __future__ import annotations

from .metrics import SKILL_PHASES


def _phase(skill):
    return SKILL_PHASES.get(skill, "other")


def windows(events):
    """Yield (skill_name, start_event, [events inside the phase window]).

    The window closes on the next skill of a different phase, not on any skill.
    Sub-steps of the same phase (git-task-blame, task-diff) keep it open.
    """
    starts = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("skill_name")
    ]
    for position, (index, event) in enumerate(starts):
        phase = _phase(event["skill_name"])
        end = len(events)
        for next_index, _ in starts[position + 1:]:
            if _phase(events[next_index]["skill_name"]) != phase:
                end = next_index
                break
        yield event["skill_name"], event, events[index:end]


def _haystack(event):
    parts = [event.get("arg_text") or "", event.get("target") or ""]
    for nested in event.get("nested") or []:
        parts.append(nested.get("tool") or "")
    return " ".join(parts).lower()


def check(events, required):
    findings = []
    for skill, start, window in windows(events):
        expected = required.get(skill)
        if not expected:
            continue
        haystack = " ".join(_haystack(event) for event in window)
        for marker in expected:
            if marker.lower() not in haystack:
                findings.append({
                    "code": "mandatory_call_missing",
                    "component": skill,
                    "expected": marker,
                    "count": 1,
                    "event_ids": [start["event_id"]],
                })
    return findings
