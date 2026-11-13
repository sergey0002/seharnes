#!/usr/bin/env python3
"""Validate the machine-readable acceptance-criteria matrix and its evidence."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
METHOD = re.compile(r"^(?P<class>[A-Za-z_][A-Za-z0-9_]*)::(?P<method>[A-Za-z_][A-Za-z0-9_]*)$")


def load_matrix(task: str) -> tuple[pathlib.Path | None, dict | None, list[str]]:
    root = REPO / ".doc" / "tasks" / task
    candidates = [root / "ac-matrix.json", root / "requirements.json"]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return None, None, [f"нет {root / 'ac-matrix.json'}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return path, None, [f"невалидный JSON: {exc}"]
    return path, data, []


def php_texts(root: pathlib.Path) -> str:
    if not root.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in root.rglob("*.php"))


def test_sources(task: str) -> tuple[str, str]:
    """Cest (браузер) и tests/lib (PHPUnit). Оба слоя ищутся по Class::method."""
    cest = "\n".join(
        php_texts(root)
        for root in (
            REPO / ".doc" / "tasks" / task / "tests",
            REPO / ".tools" / "codeception" / "tests",
        )
    )
    unit = php_texts(REPO / "tests")
    return cest, unit


def method_defined(name: str, source: str) -> bool:
    return re.search(r"function\s+" + re.escape(name) + r"\s*\(", source) is not None


def validate_source(task: str, matrix: dict | None) -> tuple[bool, list[str], list[dict]]:
    errors: list[str] = []
    requirements = matrix.get("requirements") if isinstance(matrix, dict) else None
    if not isinstance(requirements, list) or not requirements:
        return False, ["requirements должен быть непустым массивом"], []
    if matrix.get("task") not in (None, int(task), task):
        errors.append(f"matrix.task не совпадает с {task}")
    ids: set[str] = set()
    cest_source, unit_source = test_sources(task)
    normalized = []
    for item in requirements:
        if not isinstance(item, dict):
            errors.append("каждый requirement должен быть объектом")
            continue
        criterion_id = str(item.get("id", ""))
        if not re.fullmatch(r"AC-[0-9]{2,}", criterion_id):
            errors.append(f"некорректный id: {criterion_id or '<empty>'}")
        if criterion_id in ids:
            errors.append(f"дублирующийся id: {criterion_id}")
        ids.add(criterion_id)
        if not str(item.get("text", "")).strip():
            errors.append(f"{criterion_id}: отсутствует text")
        test = str(item.get("test", ""))
        match = METHOD.match(test)
        layer = ""
        if not match:
            errors.append(f"{criterion_id}: test должен быть Class::method")
        else:
            method = match.group("method")
            in_cest = method_defined(method, cest_source)
            in_unit = method_defined(method, unit_source)
            if in_cest:
                layer = "cest"
            elif in_unit:
                layer = "phpunit"
            else:
                errors.append(f"{criterion_id}: метод {test} не найден в Cest и в tests/")
        expected = item.get("expected")
        if expected in (None, "", [], {}):
            errors.append(f"{criterion_id}: отсутствует expected")
    # Проверка на дубликаты вызовов recordAcceptanceCriterion в Cest
    cest_records = re.findall(r"recordAcceptanceCriterion\(\s*['\"]([^'\"]+)['\"]", cest_source)
    counts = {cid: cest_records.count(cid) for cid in set(cest_records)}
    for cid, cnt in sorted(counts.items()):
        if cnt > 1:
            errors.append(f"дубликат вызова recordAcceptanceCriterion('{cid}') в коде Cest ({cnt} вызовов)")

    neighbors = matrix.get("required_neighbors", [])
    if not isinstance(neighbors, list):
        errors.append("required_neighbors должен быть массивом")
    for neighbor in neighbors if isinstance(neighbors, list) else []:
        if not isinstance(neighbor, dict) or not str(neighbor.get("task", "")).isdigit() or not str(neighbor.get("group", "")):
            errors.append("каждый required_neighbor обязан содержать числовой task и group")
    db = matrix.get("db_isolation", "not_required")
    if db not in ("required", "not_required"):
        errors.append("db_isolation должен быть required или not_required")
    return not errors, errors, normalized


def phpunit_passed(run_dir: pathlib.Path) -> bool:
    path = run_dir / "phpunit.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("status") == "passed"


def validate_results(run_dir: pathlib.Path, ids: list[dict]) -> tuple[bool, list[str]]:
    path = run_dir / "ac-results.json"
    raw: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            raw = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            return False, [f"невалидный ac-results.json: {exc}"]
    results = raw.get("results") if isinstance(raw, dict) else None
    if results is not None and not isinstance(results, list):
        return False, ["ac-results.json.results должен быть массивом"]
    by_id = {str(item.get("id")): item for item in (results or []) if isinstance(item, dict)}
    duplicate_ids = [criterion_id for criterion_id in {
        str(item.get("id")) for item in (results or []) if isinstance(item, dict)
    } if sum(1 for item in (results or []) if isinstance(item, dict) and str(item.get("id")) == criterion_id) > 1]
    unit_ok = phpunit_passed(run_dir)
    errors = []
    if duplicate_ids:
        errors.append("дубликаты AC evidence: " + ", ".join(sorted(duplicate_ids)))
    cest_ids = [item for item in ids if item.get("layer") != "phpunit"]
    if cest_ids and not path.exists():
        return False, ["нет ac-results.json: браузерный AC должен записать результат и evidence"]
    for item in ids:
        if item.get("layer") == "phpunit":
            if not unit_ok:
                errors.append(f"{item['id']}: PHPUnit не passed (tests/lib, evidence = phpunit.json)")
            continue
        result = by_id.get(item["id"])
        if not result:
            errors.append(f"{item['id']}: нет результата")
            continue
        if result.get("status") != "passed":
            errors.append(f"{item['id']}: status не passed")
        evidence = result.get("evidence")
        if not evidence or (isinstance(evidence, list) and not any(str(x).strip() for x in evidence)):
            errors.append(f"{item['id']}: нет evidence")
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir")
    parser.add_argument("--phase", choices=("source", "result"), default="source")
    args = parser.parse_args()
    path, matrix, load_errors = load_matrix(args.task)
    ok, errors, ids = validate_source(args.task, matrix) if not load_errors else (False, load_errors, [])
    if ok and args.phase == "result":
        if not args.run_dir:
            errors.append("--run-dir обязателен для phase=result")
            ok = False
        else:
            result_ok, result_errors = validate_results(pathlib.Path(args.run_dir), ids)
            ok = ok and result_ok
            errors.extend(result_errors)
    output = {"status": "passed" if ok else "failed", "matrix": str(path) if path else None, "errors": errors}
    if args.run_dir:
        out = pathlib.Path(args.run_dir) / ("ac-source.json" if args.phase == "source" else "ac-check.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
