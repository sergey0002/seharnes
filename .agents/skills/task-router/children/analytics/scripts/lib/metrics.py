"""Deterministic metrics and findings.

Nothing here calls a model. Every finding carries the event ids it came from so
that a human or a later reviewer can check it.
"""

from __future__ import annotations

import hashlib
import statistics

SKILL_PHASES = {
    "gototask": "start",
    "prepare-plan": "plan",
    "git-task-blame": "plan",
    "task-diff": "plan",
    "test-task": "test",
    "browser-verify": "test",
    "prepare-task-test": "test",
    "send-to-git": "git",
    "task-doc": "docs",
    "project-doc": "docs",
    "doc-verify": "docs",
}

PHASE_COMPONENT = {
    "plan": "prepare-plan",
    "test": "test-task",
    "git": "send-to-git",
    "docs": "task-doc",
}

BUILTIN_TOOLS = {
    "bash", "read", "edit", "write", "grep", "glob", "execute", "todowrite",
    "skill", "question", "webfetch", "websearch", "apply_patch", "task",
    "background_process", "suggest", "open_plan", "board_read", "board_post",
    "kilo_local_recall", "kilo_memory_recall", "kilo_memory_save",
    "list_mcp_resources", "list_mcp_resource_templates", "agent_manager",
}

DEFAULT_THRESHOLDS = {
    "timeout_ms": 120000,
    "batchable_min_run": 3,
    "retry_window_ms": 120000,
    "reasoning_share": 0.5,
    "token_spike_ratio": 2.0,
    "token_spike_min_count": 10,
    "idle_gap_ms": 900000,
    "token_spike_min_delta": 50000,
    "windows_max_share": 0.2,
}

WINDOW_PRIORITY = ("error", "unpaired", "token_spike", "batchable_series",
                   "repeat_same_target", "retry_identical", "mandatory_call_missing")


def boundaries(events):
    result = []
    for event in events:
        if event.get("tool") == "skill" and event.get("skill_name"):
            result.append((event["t"], SKILL_PHASES.get(event["skill_name"], "other")))
    return result


def phase_at(timestamp, marks, default="task"):
    phase = default
    for mark_ts, mark_phase in marks:
        if mark_ts <= timestamp:
            phase = mark_phase
        else:
            break
    return phase


def _new_finding(code, events, detail, tokens=None):
    return {
        "code": code,
        "count": len(events),
        "event_ids": [event["event_id"] for event in events],
        "detail": detail,
        "tokens": tokens,
    }


def _tool_class(tool):
    if tool in BUILTIN_TOOLS:
        return "builtin"
    if "." in tool:
        return "mcp"
    return "other"


def analyze(facts, thresholds=None):
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    events = [dict(event) for event in facts["events"]]
    marks = boundaries(events)
    for event in events:
        event["phase"] = phase_at(event["t"], marks)
    messages = facts["messages"]

    tools = {}
    for event in events:
        if event["kind"] != "tool":
            continue
        name = event["tool"]
        stat = tools.setdefault(name, {
            "name": name, "class": _tool_class(name), "calls": 0,
            "errors": 0, "timeouts": 0, "durations": [],
        })
        stat["calls"] += 1
        if event["status"] == "error":
            stat["errors"] += 1
        error_text = (event.get("error") or "").lower()
        if "timeout" in error_text or "timed out" in error_text:
            stat["timeouts"] += 1
        if event.get("duration_ms"):
            stat["durations"].append(event["duration_ms"])

    tool_rows = []
    for stat in sorted(tools.values(), key=lambda item: item["name"]):
        durations = stat.pop("durations")
        if durations:
            stat["median_ms"] = int(statistics.median(durations))
            stat["p95_ms"] = int(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)])
        else:
            stat["median_ms"] = 0
            stat["p95_ms"] = 0
        tool_rows.append(stat)

    token_by_message = {
        message["message_id"]: message.get("tokens")
        for message in messages if message.get("tokens")
    }
    tools_by_message = {}
    for event in events:
        if event["kind"] == "tool":
            tools_by_message.setdefault(event.get("message_id"), []).append(event)

    cli_tools = {}
    for event in events:
        if event.get("tool") != "bash":
            continue
        name = event.get("cli") or "bash"
        slot = cli_tools.setdefault(name, {
            "name": name, "calls": 0, "errors": 0,
            "tokens": {"input": 0.0, "cache_read": 0.0, "cache_write": 0.0,
                       "output": 0.0, "reasoning": 0.0},
        })
        slot["calls"] += 1
        if event.get("status") == "error":
            slot["errors"] += 1
        message_id = event.get("message_id")
        tokens = token_by_message.get(message_id)
        peers = tools_by_message.get(message_id) or []
        if tokens and peers:
            share = 1.0 / len(peers)
            slot["tokens"]["input"] += tokens["input"] * share
            slot["tokens"]["cache_read"] += tokens["cache_read"] * share
            slot["tokens"]["cache_write"] += tokens["cache_write"] * share
            slot["tokens"]["output"] += tokens["output"] * share
            slot["tokens"]["reasoning"] += tokens["reasoning"] * share

    mcp_servers = {}
    for event in events:
        nested = event.get("nested") or []
        if not nested:
            continue
        servers = sorted({(item.get("tool") or "").split(".", 1)[0]
                          for item in nested if item.get("tool")})
        tokens = token_by_message.get(event.get("message_id"))
        share = 1.0 / len(servers) if servers else 0.0
        for item in nested:
            name = item.get("tool") or ""
            server = name.split(".", 1)[0] if "." in name else "unknown"
            slot = mcp_servers.setdefault(server, {
                "server": server, "calls": 0, "errors": 0, "tools": {},
                "tokens": {"input": 0.0, "cache_read": 0.0, "cache_write": 0.0,
                           "output": 0.0, "reasoning": 0.0},
            })
            slot["calls"] += 1
            if item.get("status") == "error":
                slot["errors"] += 1
            tool_name = name.split(".", 1)[1] if "." in name else name
            slot["tools"][tool_name] = slot["tools"].get(tool_name, 0) + 1
            if tokens and share:
                slot["tokens"]["input"] += tokens["input"] * share
                slot["tokens"]["cache_read"] += tokens["cache_read"] * share
                slot["tokens"]["cache_write"] += tokens["cache_write"] * share
                slot["tokens"]["output"] += tokens["output"] * share
                slot["tokens"]["reasoning"] += tokens["reasoning"] * share

    findings = []

    error_events = [e for e in events if e["kind"] == "tool" and e["status"] == "error"]
    if error_events:
        findings.append(_new_finding("error", error_events, "tool calls finished with error"))

    unpaired = [e for e in events if e["kind"] == "tool" and e["status"] in ("running", "pending")]
    if unpaired:
        findings.append(_new_finding("unpaired", unpaired, "tool call has no result"))

    groups = {}
    for event in events:
        if event["kind"] != "tool":
            continue
        groups.setdefault((event["tool"], event["arg_sha"]), []).append(event)
    repeats = []
    same_target = []
    for (tool, _), group in groups.items():
        if len(group) < 2:
            continue
        repeats.extend(group[1:])
        targets = {e["target"] for e in group if e["target"]}
        if tool in ("read", "edit", "write") and len(targets) == 1:
            same_target.extend(group[1:])
    if repeats:
        findings.append(_new_finding("repeat", repeats, "identical tool arguments repeated"))
    if same_target:
        findings.append(_new_finding("repeat_same_target", same_target, "same file and range touched again"))

    batchable = []
    runs = []
    run = []
    for event in events:
        eligible = (
            event["kind"] == "tool"
            and event["tool"] in ("read", "grep", "glob", "bash")
            and event["status"] == "completed"
        )
        if eligible:
            if run and run[-1]["tool"] != event["tool"]:
                if len(run) >= thresholds["batchable_min_run"]:
                    runs.append(run)
                run = []
            run.append(event)
        else:
            if len(run) >= thresholds["batchable_min_run"]:
                runs.append(run)
            run = []
    if len(run) >= thresholds["batchable_min_run"]:
        runs.append(run)
    medians = {row["name"]: row["median_ms"] for row in tool_rows}
    saved_calls = 0
    saved_ms = 0
    for group in runs:
        extra = len(group) - 1
        saved_calls += extra
        saved_ms += extra * (medians.get(group[0]["tool"], 0) or 0)
        batchable.extend(group[1:])
    distinct_targets = {e["target"] for e in batchable if e["target"]}
    if batchable and len(distinct_targets) > 1:
        finding = _new_finding("batchable_series", batchable, "consecutive calls could be batched")
        finding["saved_calls"] = saved_calls
        finding["saved_ms"] = saved_ms
        findings.append(finding)

    retries = []
    for event in error_events:
        for later in events:
            if later is event or later["kind"] != "tool":
                continue
            if later["tool"] == event["tool"] and later["arg_sha"] == event["arg_sha"]:
                if 0 <= later["t"] - event["t"] <= thresholds["retry_window_ms"]:
                    retries.append(later)
                    break
    if retries:
        findings.append(_new_finding("retry_identical", retries, "same call retried after error"))

    skill_counts = {}
    for event in events:
        if event.get("skill_name"):
            skill_counts.setdefault(event["skill_name"], []).append(event)
    reloaded = []
    for name, group in skill_counts.items():
        if len(group) > 1:
            reloaded.extend(group[1:])
    if reloaded:
        findings.append(_new_finding("skill_reloaded", reloaded, "same skill loaded more than once"))

    ledger = {
        "input_total": 0, "input_fresh": 0, "incoming_total": 0,
        "cache_read": 0, "cache_write": 0,
        "output": 0, "reasoning": 0, "cost": 0, "requests": 0,
        "by_model": {}, "by_phase": {},
    }
    previous_input = 0
    spikes = []
    for message in messages:
        tokens = message.get("tokens")
        if not tokens:
            continue
        ledger["requests"] += 1
        bucket_phase = phase_at(message["t"], marks)
        phase_slot = ledger["by_phase"].setdefault(bucket_phase, {
            "input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cost": 0,
        })
        ledger["input_total"] += tokens["input"]
        ledger["input_fresh"] += tokens["input"]
        ledger["cache_read"] += tokens["cache_read"]
        ledger["cache_write"] += tokens["cache_write"]
        ledger["incoming_total"] += tokens["input"] + tokens["cache_read"] + tokens["cache_write"]
        ledger["output"] += tokens["output"]
        ledger["reasoning"] += tokens["reasoning"]
        ledger["cost"] += message.get("cost") or 0
        model = message.get("model") or "unknown"
        model_slot = ledger["by_model"].setdefault(model, {
            "input": 0, "output": 0, "reasoning": 0,
            "cache_read": 0, "cache_write": 0, "cost": 0,
        })
        model_slot["input"] += tokens["input"]
        model_slot["output"] += tokens["output"]
        model_slot["reasoning"] += tokens["reasoning"]
        model_slot["cache_read"] += tokens["cache_read"]
        model_slot["cache_write"] += tokens["cache_write"]
        model_slot["cost"] += message.get("cost") or 0
        phase_slot["input"] += tokens["input"]
        phase_slot["output"] += tokens["output"]
        phase_slot["reasoning"] += tokens["reasoning"]
        phase_slot["cache_read"] += tokens["cache_read"]
        phase_slot["cost"] += message.get("cost") or 0
        if previous_input and tokens["input"] >= previous_input * thresholds["token_spike_ratio"]:
            if tokens["input"] - previous_input >= thresholds["token_spike_min_delta"]:
                spikes.append(message)
        previous_input = tokens["input"]
    ledger["spikes"] = len(spikes)
    if len(spikes) >= thresholds.get("token_spike_min_count", 10):
        findings.append(_new_finding(
            "token_spike", [{"event_id": message["message_id"]} for message in spikes],
            "input tokens jumped against the previous turn many times",
        ))

    denominator = ledger["incoming_total"]
    ledger["cache_hit_ratio"] = round(ledger["cache_read"] / denominator, 4) if denominator else 0.0
    total_tokens = ledger["input_total"] + ledger["output"] + ledger["reasoning"]
    if total_tokens and ledger["reasoning"] / total_tokens > thresholds["reasoning_share"]:
        findings.append(_new_finding("reasoning_heavy", [], "reasoning share above threshold"))

    stamps = sorted(event["t"] for event in events)
    duration_ms = stamps[-1] - stamps[0] if stamps else 0
    idle_gap = thresholds.get("idle_gap_ms", 900000)
    active_ms = sum(min(cur - prev, idle_gap)
                    for prev, cur in zip(stamps, stamps[1:]))
    idle_trimmed_ms = active_ms

    compactions = [e for e in events if e.get("compaction")]
    files = sorted({e["target"] for e in events if e.get("target") and e["kind"] == "tool"})

    windows = []
    used = set()
    limit = max(1, int(len(events) * thresholds["windows_max_share"]))
    ordered = sorted(findings, key=lambda item: WINDOW_PRIORITY.index(item["code"]) if item["code"] in WINDOW_PRIORITY else 99)
    for finding in ordered:
        ids = [value for value in finding["event_ids"] if value not in used]
        if not ids:
            continue
        room = limit - len(used)
        if room <= 0:
            break
        ids = ids[:room]
        used.update(ids)
        windows.append({
            "window_id": hashlib.sha1(("|".join(ids)).encode("utf-8")).hexdigest()[:10],
            "reason": finding["code"],
            "event_ids": ids,
        })

    return {
        "tools": tool_rows,
        "findings": findings,
        "windows": windows,
        "token_ledger": ledger,
        "phases": sorted(ledger["by_phase"]),
        "files_touched": files,
        "context_overflows": len(compactions),
        "cli_tools": [
            {
                **row,
                "tokens": {key: int(round(value)) for key, value in row["tokens"].items()},
            }
            for row in sorted(cli_tools.values(), key=lambda item: (-item["calls"], item["name"]))
        ],
        "mcp_servers": [
            {
                **row,
                "tokens": {key: int(round(value)) for key, value in row["tokens"].items()},
            }
            for row in sorted(mcp_servers.values(), key=lambda item: (-item["calls"], item["server"]))
        ],
        "duration_ms": duration_ms,
        "active_ms": active_ms,
        "idle_trimmed_ms": idle_trimmed_ms,
        "batchable_saved_calls": saved_calls,
        "batchable_saved_ms": saved_ms,
        "compaction_events": [e["event_id"] for e in compactions],
        "events": events,
        "totals": {
            "tool_calls": sum(row["calls"] for row in tool_rows),
            "mcp_calls": sum(len(e.get("nested") or []) for e in events),
            "errors": len(error_events),
            "timeouts": sum(row["timeouts"] for row in tool_rows),
            "unpaired": len(unpaired),
            "repeats": len(repeats),
            "retries": len(retries),
            "phases": len(ledger["by_phase"]),
            "mcp_servers": len(mcp_servers),
            "batchable_saved_calls": saved_calls,
            "batchable_saved_ms": saved_ms,
        },
    }
