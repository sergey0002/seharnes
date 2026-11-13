#!/usr/bin/env python3
"""Check canonical files and best-effort runtime registration separately."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def check(component: str, root: Path, config_paths: list[Path]) -> dict[str, object]:
    registry_path = Path(__file__).with_name("component_registry.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entry = registry.get("components", {}).get(component)
    if not entry:
        return {"status": "error", "component": component, "error": "unknown component"}
    missing = [str(root / path) for path in entry["required_files"] if not (root / path).exists()]
    file_parity = {"status": "passed" if not missing else "failed", "missing": missing}
    if not config_paths:
        runtime = {"status": "n/a", "reason": "no environment-specific config paths supplied"}
    else:
        existing = [str(path) for path in config_paths if path.exists()]
        runtime = {"status": "n/a" if existing else "fallback", "checked": [str(path) for path in config_paths], "existing": existing}
        if not existing:
            runtime["reason"] = "config paths were supplied but none exist; file checks cannot prove registration"
        else:
            runtime["reason"] = "configuration exists; no runtime discovery API was invoked"
    return {"status": "passed" if file_parity["status"] == "passed" else "failed", "component": component, "file_parity": file_parity, "runtime_registration": runtime}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--config", action="append", default=[], type=Path)
    args = parser.parse_args()
    report = check(args.component, args.root, args.config)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 2 if report.get("status") == "error" else (0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
