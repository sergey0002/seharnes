#!/usr/bin/env python3
"""Self-check for the panel service. Read-only, no network."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / ".doc" / "web"
CONFIG = WEB / "config"
errors: list[str] = []


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
        return None


service = load(CONFIG / "service.json")
if isinstance(service, dict):
    for key in ("schema", "name", "version", "data_dir", "state_dir", "writable"):
        if key not in service:
            errors.append(f"service.json: missing {key}")
    data = ROOT / str(service.get("data_dir", ""))
    if not (data / "graph.json").is_file():
        errors.append(f"data_dir has no graph.json: {service.get('data_dir')}")
    state = ROOT / str(service.get("state_dir", ""))
    try:
        (state / "jobs").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(f"state_dir is not writable: {exc}")

actions = load(CONFIG / "actions.json")
profile = (service or {}).get("profile", "full") if isinstance(service, dict) else "full"
if isinstance(actions, dict):
    seen = set()
    for row in actions.get("actions", []):
        rid = row.get("id")
        if not rid or rid in seen:
            errors.append(f"actions.json: bad or duplicate id {rid}")
            continue
        seen.add(rid)
        if profile == "core" and row.get("profile") == "full":
            continue
        script = ROOT / str(row.get("script", ""))
        if not script.is_file():
            errors.append(f"{rid}: missing script {row.get('script')}")
        interpreter = row.get("interpreter")
        if interpreter not in ("python3", "bash", "pwsh", "php"):
            errors.append(f"{rid}: bad interpreter {interpreter}")
        elif shutil.which(interpreter) is None:
            errors.append(f"{rid}: interpreter not found {interpreter}")

prices = load(CONFIG / "prices.json")
if isinstance(prices, dict):
    providers = prices.get("providers") or {}
    if not isinstance(providers, dict):
        errors.append("prices.json: providers is not an object")
    else:
        for pid, provider in providers.items():
            if not isinstance(provider, dict):
                errors.append(f"prices.json: bad provider {pid}")
                continue
            models = provider.get("models") or {}
            if not isinstance(models, dict):
                errors.append(f"prices.json: {pid}.models is not an object")
                continue
            for name, row in models.items():
                if not isinstance(row, dict):
                    errors.append(f"prices.json: {pid}/{name} is not an object")
                    continue
                for key in ("input", "output", "cache_read", "cache_write"):
                    if key in row and not isinstance(row[key], (int, float)):
                        errors.append(f"prices.json: {pid}/{name}.{key} is not a number")
    for name, row in (prices.get("models") or {}).items():
        if not isinstance(row, dict):
            errors.append(f"prices.json: bad model {name}")
            continue
        for key in ("input", "output", "cache_read", "cache_write"):
            if key in row and not isinstance(row[key], (int, float)):
                errors.append(f"prices.json: {name}.{key} is not a number")
else:
    errors.append("prices.json: invalid")

if shutil.which("python3") and (WEB / "bin" / "build-actions.py").is_file():
    result = subprocess.run(
        [sys.executable, str(WEB / "bin" / "build-actions.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append((result.stdout or result.stderr).strip())

print(json.dumps({"status": "ok" if not errors else "failed", "errors": errors}, ensure_ascii=False))
raise SystemExit(0 if not errors else 1)
