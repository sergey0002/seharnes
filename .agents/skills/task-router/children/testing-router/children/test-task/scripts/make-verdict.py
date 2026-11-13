#!/usr/bin/env python3
"""Сводка прогона в verdict.json: счётчики тестов + шум из checkpoint().

Читает артефакты Codeception из каталога прогона:
  report.xml        — JUnit, счётчики и имена упавших тестов
  checkpoints.jsonl — что записал AcceptanceTester::checkpoint()
  run.log           — сырой вывод, если XML не создался

verdict.json потом читает gates.sh (гейты G3/G4) и отчёт test-runs.
Отдельный файл, а не парсинг глазами: агент не должен "на глаз"
определять, зелёный прогон или нет.
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def parse_junit(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return {}

    suites = root.iter("testsuite")
    total = failures = errors = skipped = 0
    failed_names = []
    testcases = []

    for suite in suites:
        # Вложенные testsuite дублируют счётчики родителя — берём только
        # те, у которых есть непосредственные testcase.
        cases = suite.findall("testcase")
        if not cases:
            continue
        total += len(cases)
        for case in cases:
            name = f"{case.get('class', '')}::{case.get('name', '')}"
            case_status = "passed"
            if case.find("failure") is not None:
                failures += 1
                failed_names.append(name)
                case_status = "failed"
            elif case.find("error") is not None:
                errors += 1
                failed_names.append(name)
                case_status = "error"
            elif case.find("skipped") is not None:
                skipped += 1
                case_status = "skipped"
            testcases.append({"name": name, "status": case_status, "time": case.get("time", "")})

    return {
        "total": total,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": total - failures - errors - skipped,
        "failedTests": failed_names,
        "testcases": testcases,
    }


def parse_checkpoints(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"count": 0, "consoleErrors": [], "errorModals": [], "toasted": []}

    console, modals, toasted = [], [], []
    count = 0

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        count += 1
        label = entry.get("label", "?")
        for msg in entry.get("console", []):
            console.append({"checkpoint": label, "message": msg})
        if entry.get("errorModal"):
            modals.append({"checkpoint": label, "message": entry["errorModal"]})
        for msg in entry.get("toasted", []):
            toasted.append({"checkpoint": label, "message": msg})

    return {
        "count": count,
        "consoleErrors": console,
        "errorModals": modals,
        "toasted": toasted,
    }


def fallback_from_log(path: pathlib.Path) -> dict:
    """Если XML нет — вытащить хотя бы итоговую строку Codeception."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(OK \(\d+ test|Tests: \d+|FAILURES!|ERRORS!)", text)
    return {"logTail": text[-2000:], "summaryLine": m.group(0) if m else ""}


def artifact_status(run_dir: pathlib.Path, name: str) -> str:
    path = run_dir / name
    if not path.exists():
        return "missing"
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("status", "invalid"))
    except (OSError, json.JSONDecodeError):
        return "invalid"


def manifest_matches(task: str, group: str, run_dir: pathlib.Path) -> bool:
    manifest = run_dir / "manifest.json"
    script = pathlib.Path(__file__).with_name("qa-manifest.py")
    if not manifest.exists():
        return False
    result = subprocess.run(
        [sys.executable, str(script), "--task", task, "--group", group, "--output", str(run_dir / ".manifest-current.json"), "--check", str(manifest)],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--exit-code", type=int, required=True)
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run_dir)
    junit = parse_junit(run_dir / "report.xml")
    checkpoints = parse_checkpoints(run_dir / "checkpoints.jsonl")
    screenshots = sorted(p.name for p in run_dir.glob("**/*.png"))

    statuses = {
        "static": artifact_status(run_dir, "static.json"),
        "lint": artifact_status(run_dir, "lint.json"),
        "phpunit": artifact_status(run_dir, "phpunit.json"),
        "ac": artifact_status(run_dir, "ac-check.json"),
        "db": artifact_status(run_dir, "db-isolation.json"),
    }
    hashes_match = manifest_matches(args.task, args.group, run_dir)
    comparison = artifact_status(run_dir, "comparison.json")
    llm = artifact_status(run_dir, "llm-review.json")
    neighbor_results = artifact_status(run_dir, "neighbor-results.json")
    green = (
        args.exit_code == 0
        and junit.get("total", 0) > 0
        and statuses["lint"] == "passed"
        and statuses["static"] == "passed"
        and statuses["phpunit"] in ("passed", "skipped", "baseline_failed")
        and statuses["ac"] == "passed"
        and statuses["db"] in ("passed", "not_required", "skipped")
        and neighbor_results in ("passed", "skipped")
        and comparison in ("passed", "no_baseline")
        and llm in ("passed", "skipped")
        and hashes_match
    )

    verdict = {
        "task": args.task,
        "group": args.group,
        "runDir": str(run_dir),
        "exitCode": args.exit_code,
        "green": green,
        "tests": junit or fallback_from_log(run_dir / "run.log"),
        "checkpoints": checkpoints,
        "screenshots": screenshots,
        "artifacts": statuses,
        "neighborResults": neighbor_results,
        "comparison": comparison,
        "llmReview": llm,
        "hashesMatch": hashes_match,
    }

    out = run_dir / "verdict.json"
    out.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print("== Вердикт прогона")
    if junit:
        print(f"  тестов {junit['total']}, прошло {junit['passed']}, "
              f"упало {junit['failures']}, ошибок {junit['errors']}, пропущено {junit['skipped']}")
        for name in junit["failedTests"]:
            print(f"    упал: {name}")
    else:
        print("  JUnit-отчёт не создан, смотри run.log")

    print(f"  checkpoint: {checkpoints['count']}, "
          f"ошибок консоли {len(checkpoints['consoleErrors'])}, "
          f"модалок ошибок {len(checkpoints['errorModals'])}")
    for item in checkpoints["consoleErrors"][:10]:
        print(f"    console [{item['checkpoint']}]: {item['message']}")
    for item in checkpoints["errorModals"][:10]:
        print(f"    error-modal [{item['checkpoint']}]: {item['message']}")

    print(f"  скриншотов: {len(screenshots)}")
    print(f"  green: {'да' if green else 'НЕТ'}")
    print(f"  {out}")


if __name__ == "__main__":
    main()
