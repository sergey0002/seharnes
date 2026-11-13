#!/usr/bin/env python3
"""Compare Decomposition reasons and scenarios with the task test matrix.

Источники плана (по приоритету):
1. plan artifacts scope=task|stage:N из task.json (JSONdoc, точный scope);
2. stage*/plan.md с ## Decomposition;
3. корневой plan.md с ## Decomposition (legacy).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
R_HEADING = re.compile(r"^###\s+(R\d+)\b.*$", re.M)
SCENARIO = re.compile(r"\b(S\d+\.\d+)\b")


def iter_plan_sources(root: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """Вернуть (scope, path) планов: task.json artifacts -> stage dirs -> plan.md."""
    found: list[tuple[str, pathlib.Path]] = []
    seen: set[str] = set()
    task_json = root / "task.json"
    if task_json.is_file():
        try:
            data = json.loads(task_json.read_text(encoding="utf-8", errors="ignore"))
        except (ValueError, OSError):
            data = None
        if isinstance(data, dict):
            for art in data.get("artifacts", []) or []:
                if not isinstance(art, dict) or art.get("role") != "plan":
                    continue
                if art.get("availability") not in (None, "present"):
                    continue
                rel = art.get("path") or ""
                p = (REPO / rel) if not rel.startswith(".doc/") else (root.parent.parent / rel)
                if not p.is_file():
                    p = root / pathlib.Path(rel).name
                scope = str(art.get("scope") or "task")
                key = str(p.resolve()) if p.is_file() else rel
                if p.is_file() and key not in seen:
                    seen.add(key)
                    found.append((scope, p))
    for stage in sorted(root.glob("stage*/plan.md")):
        key = str(stage.resolve())
        if has_decomposition(stage) and key not in seen:
            seen.add(key)
            found.append((f"stage:{stage.parent.name}", stage))
    legacy = root / "plan.md"
    if has_decomposition(legacy):
        key = str(legacy.resolve())
        if key not in seen:
            seen.add(key)
            found.append(("task", legacy))
    return found


def has_decomposition(path: pathlib.Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return re.search(r"^## Decomposition\b", text, re.M) is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    args = parser.parse_args()
    root = REPO / ".doc" / "tasks" / args.task
    matrix_path = root / "test.md"
    if not matrix_path.is_file():
        print("branch-audit: test.md is required", file=sys.stderr)
        return 2
    plans = iter_plan_sources(root)
    if not plans:
        print("branch-audit: no plan with ## Decomposition "
              "(plan.md, stage*/plan.md, task.json plan artifacts)", file=sys.stderr)
        return 2
    test = matrix_path.read_text(encoding="utf-8", errors="ignore")
    section = re.search(r"^## Ветки логики\s*(.*?)(?=^## |\Z)", test, re.M | re.S)
    if not section:
        print("branch-audit: test.md has no ## Ветки логики")
        return 2

    reasons: list[tuple[str, list[str], str]] = []
    for scope, plan_path in plans:
        plan = plan_path.read_text(encoding="utf-8", errors="ignore")
        decomposition = re.search(r"^## Decomposition\b(.*?)(?=^## |\Z)", plan, re.M | re.S)
        if not decomposition:
            continue
        for match in R_HEADING.finditer(decomposition.group(1)):
            end = R_HEADING.search(decomposition.group(1), match.end())
            body = decomposition.group(1)[match.end():end.start() if end else len(decomposition.group(1))]
            scenarios = sorted(set(SCENARIO.findall(body)))
            reasons.append((match.group(1), scenarios, scope))

    rows = []
    for line in section.group(1).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"B\d+", cells[0]):
            rows.append(cells)

    missing_reasons = []
    partial_rows = []
    for reason, scenarios, scope in reasons:
        reason_rows = [row for row in rows if re.search(rf"\b{re.escape(reason)}\b", " ".join(row))]
        covered_text = " ".join(" ".join(row) for row in reason_rows)
        missing_scenarios = [scenario for scenario in scenarios if scenario not in covered_text]
        if not reason_rows:
            missing_reasons.append(reason)
        if missing_scenarios:
            missing_reasons.append(f"{reason} missing scenarios: {', '.join(missing_scenarios)}")
        for row in reason_rows:
            status = row[-1].lower().replace(" ", "")
            if status not in {"covered", "n-a", "na"}:
                partial_rows.append(f"{row[0]}={row[-1]}")
        print(f"{reason} [{scope}]: {len(scenarios)} planned S, {len(reason_rows)} branch rows, "
              f"{'partial' if missing_scenarios or any(row[-1].lower() not in {'covered','n-a','na'} for row in reason_rows) else 'closed'}")

    if missing_reasons:
        print("Missing: " + "; ".join(missing_reasons))
    if partial_rows:
        print("Partial: " + ", ".join(partial_rows))
    return 1 if missing_reasons or partial_rows else 0


if __name__ == "__main__":
    sys.exit(main())
