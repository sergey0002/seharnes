#!/usr/bin/env python3
"""Resolve and validate the mandatory neighboring flows declared by a task."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    matrix_path = REPO / ".doc" / "tasks" / args.task / "ac-matrix.json"
    errors = []
    neighbors = []
    if not matrix_path.exists():
        errors.append(f"нет {matrix_path}")
    else:
        try:
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            neighbors = matrix.get("required_neighbors", [])
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    seen = set()
    normalized = []
    for item in neighbors if isinstance(neighbors, list) else []:
        if not isinstance(item, dict):
            errors.append("neighbor должен быть объектом")
            continue
        task = str(item.get("task", ""))
        group = str(item.get("group", ""))
        key = (task, group)
        if not task.isdigit() or not group:
            errors.append("neighbor требует числовой task и group")
        elif task == args.task:
            errors.append("neighbor не может ссылаться на самого себя")
        elif key in seen:
            errors.append(f"дублирующийся neighbor: {task}/{group}")
        elif not (REPO / ".doc" / "tasks" / task / "tests").is_dir():
            errors.append(f"нет тестов neighbor: {task}")
        else:
            seen.add(key)
            normalized.append({"task": task, "group": group, "reason": str(item.get("reason", ""))})
    result = {"status": "passed" if not errors else "failed", "neighbors": normalized, "errors": errors}
    pathlib.Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
