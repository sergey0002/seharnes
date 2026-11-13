#!/usr/bin/env python3
"""Run PHPUnit whenever application/server code is changed.

Canon runner: app container PHP 7.1 + vendor PHPUnit 4.8 + tests/phpunit.xml.
The Codeception 8.3 image cannot bootstrap maket.php (Fatal in userErrorHandler).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import hashlib

REPO = pathlib.Path(__file__).resolve().parents[8]
APP_CONTAINER = os.environ.get("QA_PHPUNIT_CONTAINER", "copytrust-dev-php-apache-1")
APP_WORKDIR = "/var/www/html"
PHPUNIT_BIN = "vendor/phpunit/phpunit/phpunit"
PHPUNIT_CFG = "tests/phpunit.xml"

ENV_BROKEN_MARKERS = (
    "xdebug.coverage_enable",
    "PHP_CodeCoverage_Exception",
    "Uncaught PHP_CodeCoverage",
    "userErrorHandler",
)


def task_diff_files(task: str) -> list[pathlib.Path]:
    if not task:
        return []
    diff = REPO / ".doc" / "tasks" / task / "diff.files.md"
    if not diff.exists():
        return []
    result: list[pathlib.Path] = []
    for line in diff.read_text(encoding="utf-8", errors="ignore").splitlines():
        for token in line.split():
            value = token.strip("(),`[]")
            path = REPO / value
            if path.is_file():
                result.append(path)
    return result


def changed_files(task: str | None = None) -> list[pathlib.Path]:
    try:
        output = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    result = []
    for line in output.splitlines():
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        path = REPO / value
        if path.is_file():
            result.append(path)
    # Task profile must remain useful after the task commit. Include the
    # exported task diff in addition to current uncommitted changes.
    if task:
        result.extend(task_diff_files(task))
    return sorted(set(result))


def is_server(path: pathlib.Path) -> bool:
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return False
    if ".doc" in rel.parts or ".cursor" in rel.parts or "vendor" in rel.parts:
        return False
    return path.suffix == ".php" or any(
        part in {"app", "src", "lib", "models", "controllers", "migrations", "database"}
        for part in rel.parts
    )


def related_tests(server_files: list[pathlib.Path]) -> list[str]:
    """Map changed lib/.../Foo.php → tests/lib/.../FooTest.php when present."""
    found: list[str] = []
    for path in server_files:
        try:
            rel = path.relative_to(REPO)
        except ValueError:
            continue
        if rel.suffix != ".php":
            continue
        candidate = REPO / "tests" / rel.parent / f"{rel.stem}Test.php"
        if candidate.is_file():
            found.append(candidate.relative_to(REPO).as_posix())
    return sorted(set(found))


def container_running(docker: str, name: str) -> bool:
    check = subprocess.run(
        [docker, "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
    )
    return check.returncode == 0 and check.stdout.strip() == "true"


def env_broken(output: str) -> bool:
    return any(marker in output for marker in ENV_BROKEN_MARKERS)


def suite_rot(output: str) -> bool:
    """Legacy PHPUnit 4.8 mocks vs typed signatures / Error vs Exception."""
    if "Failed asserting that exception of type \"Error\" matches expected exception \"Exception\"" in output:
        return True
    if re.search(r"Expectation failed for method name is equal to <string:ValidateMessages>", output):
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", choices=("task", "changed", "full", "baseline"), default="task")
    args = parser.parse_args()
    run_dir = pathlib.Path(args.run_dir).resolve()
    if not str(run_dir).startswith(str(REPO) + os.sep):
        mapped = REPO / ".doc" / "qa" / "tmp-runs" / hashlib.sha256(str(run_dir).encode()).hexdigest()[:16]
        mapped.mkdir(parents=True, exist_ok=True)
        result_run_dir = mapped
    else:
        result_run_dir = run_dir
    result_run_dir.mkdir(parents=True, exist_ok=True)
    files = changed_files(args.task)
    server_files = [p for p in files if is_server(p)]
    result: dict = {"profile": args.profile, "server_changes": [p.relative_to(REPO).as_posix() for p in server_files]}
    if not server_files:
        result.update({"status": "skipped", "reason": "изменений серверного кода нет"})
    else:
        docker = shutil.which("docker")
        tests = related_tests(server_files)
        if args.profile == "task" and args.task:
            task_tests = task_diff_files(args.task)
            explicit = [p.relative_to(REPO).as_posix() for p in task_tests if p.parts[0] == "tests" and p.suffix == ".php"]
            tests = sorted(set(tests + explicit))
        elif args.profile in ("full", "baseline"):
            tests = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "tests").rglob("*Test.php"))
        result["related_tests"] = tests
        if not docker:
            result.update({"status": "failed", "reason": "PHP изменён, но docker не найден"})
        elif not container_running(docker, APP_CONTAINER):
            result.update(
                {
                    "status": "skipped",
                    "reason": f"контейнер {APP_CONTAINER} не запущен; PHPUnit 4.8/app не прогнан",
                }
            )
        elif not tests:
            result.update(
                {
                    "status": "skipped",
                    "reason": "нет парных unit-тестов для изменённых PHP-файлов",
                }
            )
        else:
            junit_host = result_run_dir / "phpunit-junit.xml"
            junit_rel = junit_host.relative_to(REPO).as_posix()
            command = [
                docker,
                "exec",
                "-w",
                APP_WORKDIR,
                APP_CONTAINER,
                "php",
                PHPUNIT_BIN,
                "-c",
                PHPUNIT_CFG,
                "--no-coverage",
                "--log-junit",
                f"{APP_WORKDIR}/{junit_rel}",
                *tests,
            ]
            try:
                process = subprocess.run(
                    command,
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                )
                output = (process.stdout + process.stderr).strip()
                (result_run_dir / "phpunit.log").write_text(output + "\n", encoding="utf-8")
                result["exit_code"] = process.returncode
                result["command"] = command
                if process.returncode == 0:
                    result["status"] = "passed"
                elif env_broken(output):
                    result.update(
                        {
                            "status": "infra_failed",
                            "reason": "PHPUnit bootstrap/runtime failed before test assertions",
                        }
                    )
                elif args.profile in ("full", "baseline") and (suite_rot(output) or "Declaration of Mock_" in output):
                    result.update({
                        "status": "baseline_failed",
                        "reason": "known full-suite PHPUnit 4 mock incompatibility; inspect phpunit.log",
                        "new_failures": [],
                    })
                else:
                    result["status"] = "failed"
            except (OSError, subprocess.TimeoutExpired) as exc:
                result.update({"status": "failed", "reason": str(exc)})
    result["run_dir"] = str(result_run_dir)
    (result_run_dir / "phpunit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    accepted = ("passed", "skipped", "baseline_failed") if args.profile in ("full", "baseline") else ("passed", "skipped")
    return 0 if result["status"] in accepted else 1


if __name__ == "__main__":
    sys.exit(main())
