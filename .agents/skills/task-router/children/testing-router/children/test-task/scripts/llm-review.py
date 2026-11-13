#!/usr/bin/env python3
"""Optional LLM review over compact QA evidence; never overrides gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone


def read_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    env = pathlib.Path(__file__).resolve().parents[8] / ".tools" / "codeception" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return default


def compact(run: pathlib.Path) -> dict:
    verdict = read_json(run / "verdict.json")
    ac = read_json(run / "ac-results.json")
    comparison = read_json(run / "comparison.json")
    prechecks = []
    if (run / "prechecks.jsonl").exists():
        for line in (run / "prechecks.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                prechecks.append(json.loads(line))
    return {
        "task": verdict.get("task"), "group": verdict.get("group"),
        "exitCode": verdict.get("exitCode"), "green": verdict.get("green"),
        "tests": verdict.get("tests", {}), "acResults": ac.get("results", []),
        "artifacts": verdict.get("artifacts", {}), "hashesMatch": verdict.get("hashesMatch"),
        "comparison": comparison, "prechecks": prechecks,
        "checkpointErrors": verdict.get("checkpoints", {}).get("consoleErrors", []),
        "errorModals": verdict.get("checkpoints", {}).get("errorModals", []),
    }


def extract_json(value: str) -> dict:
    match = re.search(r"\{.*\}", value or "", re.DOTALL)
    if not match:
        return {}
    try:
        result = json.loads(match.group(0))
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        return {}


def call_openai(prompt: str, key: str, endpoint: str, model: str) -> dict:
    body = json.dumps({"model": model, "input": prompt, "max_output_tokens": 1200}).encode()
    request = urllib.request.Request(endpoint, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode())
    output = payload.get("output_text", "")
    if not output:
        output = "\n".join(
            part.get("text", "") for item in payload.get("output", []) if isinstance(item, dict)
            for part in item.get("content", []) if isinstance(item.get("content", []), list)
            if isinstance(part, dict)
        )
    return extract_json(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run = pathlib.Path(args.run_dir)
    evidence = compact(run)
    encoded = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    required = env_value("QA_LLM_REQUIRED", "0").lower() in ("1", "true", "yes")
    key = env_value("QA_LLM_API_KEY") or env_value("OPENAI_API_KEY")
    model = env_value("QA_LLM_MODEL", "gpt-4o-mini")
    endpoint = env_value("QA_LLM_ENDPOINT", "https://api.openai.com/v1/responses")
    result = {
        "schema": 1, "task": args.task, "run": run.name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "inputSha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "model": model if key else None, "status": "skipped", "decision": "review", "findings": [],
    }
    if not key:
        result["reason"] = "LLM key is not configured; deterministic gates remain authoritative"
        if required:
            result.update(status="failed", reason="QA_LLM_REQUIRED is enabled but no API key is configured")
    else:
        prompt = (
            "Review only this QA JSON. Return JSON only: decision (pass|review|fail), "
            "confidence (0..1), findings (array with severity, evidence, recommendation), summary. "
            "Never override a deterministic failure.\n\n" + encoded
        )
        try:
            answer = call_openai(prompt, key, endpoint, model)
            if answer.get("decision") not in ("pass", "review", "fail"):
                raise ValueError("LLM returned invalid decision")
            result.update(answer, status="passed")
        except Exception as exc:
            result.update(status="failed" if required else "skipped", reason=str(exc))
    (run / "llm-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("passed", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
