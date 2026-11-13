#!/usr/bin/env python3
"""Small offline checks for the QA harness itself."""
from __future__ import annotations

import json
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[8]
SCRIPTS = pathlib.Path(__file__).resolve().parent


def run(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def load_helper(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_relocated_helpers() -> None:
    gates = load_helper("gates")
    for code in (0, 1):
        with patch.object(gates, "task_changed_files", return_value=["example.php"]), patch.object(
            gates, "run", return_value=subprocess.CompletedProcess([], code, "static result", "")
        ) as command:
            result = gates.g0_static("selftest")
            assert result.ok == (code == 0)
            assert pathlib.Path(command.call_args.args[0][1]) == SCRIPTS / "static-on-diff.py"
    lint = load_helper("qa-lint")
    assert lint.STATIC_SCRIPT == SCRIPTS / "static-on-diff.py"
    static = load_helper("static-on-diff")
    assert static.PHPSTAN_DIR.is_dir()
    assert static.RELEASE_CFG.is_file()
    review = load_helper("llm-review")
    with patch.dict(os.environ, {"QA_RELOCATION_SELFTEST": ""}), patch.object(
        pathlib.Path, "read_text", autospec=True, return_value="QA_RELOCATION_SELFTEST=found\n"
    ) as read:
        assert review.env_value("QA_RELOCATION_SELFTEST") == "found"
        assert read.call_args.args[0] == ROOT / ".tools/codeception/.env"


def check_eslint_json_tail() -> None:
    static = load_helper("static-on-diff")
    report = json.dumps(
        [
            {
                "filePath": "/app/scripts/module/order/view.js",
                "messages": [{"line": 3, "severity": 2, "message": "boom", "ruleId": "no-undef"}],
            }
        ]
    )
    text = (
        "yarn install v1.22.22\n[1/4] Resolving packages...\nDone in 57.52s.\n"
        + report
        + '\nwarning " > @vue/compiler-sfc@3.0.11" has incorrect peer dependency "vue@3.0.11".\n'
    )
    parsed = static.parse_eslint_json(text)
    assert parsed == [
        {"file": "scripts/module/order/view.js", "line": 3, "message": "boom", "rule": "no-undef", "severity": 2}
    ], parsed


def check_phpstan_image_policy() -> None:
    shell = r'''#!/usr/bin/env bash
    case "$1 $2" in
        "image inspect") test "$MOCK_IMAGE" = present || test -f "$MOCK_STATE" ;;
        "build -t")
            echo MOCK_BUILD >&2
            test "$MOCK_BUILD_EXIT" = 0 || exit "$MOCK_BUILD_EXIT"
            touch "$MOCK_STATE" ;;
        "run --rm") echo MOCK_RUN; exit "$MOCK_RUN_EXIT" ;;
        *) exit 99 ;;
    esac
'''
    cases = [
        ("existing", "present", "", "1", 0, 0, 0, False, True),
        ("missing", "missing", "", "1", 0, 0, 0, True, True),
        ("disabled", "missing", "", "0", 0, 0, 2, False, False),
        ("custom", "missing", "custom:tag", "1", 0, 0, 2, False, False),
        ("build failed", "missing", "", "1", 1, 0, 2, True, False),
        ("analysis failed", "present", "", "1", 0, 1, 1, False, True),
    ]
    with tempfile.TemporaryDirectory() as directory:
        docker = pathlib.Path(directory) / "docker"
        docker.write_text(shell, encoding="utf-8")
        docker.chmod(0o755)
        for index, (name, image, tag, auto, build_exit, run_exit, expected, built, ran) in enumerate(cases):
            env = dict(os.environ, MOCK_IMAGE=image, PHPSTAN_DOCKER_IMAGE=tag,
                       PHPSTAN_AUTO_BUILD=auto, MOCK_BUILD_EXIT=str(build_exit), MOCK_RUN_EXIT=str(run_exit),
                       MOCK_STATE=str(pathlib.Path(directory) / str(index)), PATH=directory + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(ROOT / ".agents/skills/phpstan-mcp/scripts/phpstan-docker.sh"), "--version"],
                                    env=env, capture_output=True, text=True)
            output = result.stdout + result.stderr
            assert (result.returncode, "MOCK_BUILD" in output, "MOCK_RUN" in output) == (expected, built, ran), (name, output)


def main() -> int:
    scripts = [
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/doctor.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/branch-audit.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-manifest.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/db-isolation.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/check-ac-matrix.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py",
        ".agents/skills/task-router/children/testing-router/children/test-task/scripts/llm-review.py",
    ]
    for script in scripts:
        code, output = run([sys.executable, "-m", "py_compile", script])
        if code:
            print(f"FAIL compile {script}\n{output}")
            return 1
    check_relocated_helpers()
    check_eslint_json_tail()
    check_phpstan_image_policy()
    validator = load_helper("check-ac-matrix")
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "ac-results.json"
        evidence = {"id": "AC-01", "status": "passed", "evidence": ["fixture checkpoint"]}
        for results, expected in (([evidence], True), ([evidence, evidence], False), ([], False)):
            path.write_text(json.dumps({"results": results}), encoding="utf-8")
            ok, errors = validator.validate_results(path.parent, [{"id": "AC-01", "layer": "cest"}])
            assert ok == expected, errors
            if len(results) == 2:
                assert any("дубликаты AC evidence" in error for error in errors), errors
    print("harness-selftest: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
