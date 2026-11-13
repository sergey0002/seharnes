#!/usr/bin/env python3
"""Mandatory lint for files changed by the task verifier."""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
NODE_IMAGE = "node:22-bookworm-slim"
ESLINT_VOLUME = "copytrust-eslint-nm"
STATIC_SCRIPT = pathlib.Path(__file__).with_name("static-on-diff.py")


def ensure_runner_image(docker: str) -> bool:
    image = "copytrust-codecept:8.3"
    code, _ = run([docker, "image", "inspect", image])
    if code == 0:
        return True
    context = REPO / ".doc" / "qa" / "docker"
    code, output = run([docker, "build", "-q", "-t", image, str(context)])
    if code != 0:
        sys.stderr.write(output + "\n")
    return code == 0


def changed_files() -> list[pathlib.Path]:
    try:
        result = subprocess.run(["git", "status", "--porcelain=v1", "-uall"], cwd=REPO, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    paths = []
    for line in result.stdout.splitlines():
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        path = REPO / value
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        return result.returncode, (result.stdout + result.stderr).strip()
    except OSError as exc:
        return 127, str(exc)


def eslint_command(files: list[pathlib.Path]) -> list[str]:
    config = REPO / ".doc" / "qa" / "eslint" / "patch-max.js"
    if not config.exists():
        config = REPO / ".eslintrc.strict.js"
    return [
        "./node_modules/.bin/eslint",
        "--no-eslintrc",
        "--ext", ".js,.vue",
        "--config", str(config.relative_to(REPO)),
        "--max-warnings=0",
        "--no-inline-config",
        "--format", "json",
        *[str(path.relative_to(REPO)) for path in files],
    ]


def run_eslint(files: list[pathlib.Path]) -> tuple[int, str, str, str]:
    command = eslint_command(files)
    local_bin = REPO / "node_modules" / ".bin" / "eslint"
    local_plugin = REPO / "node_modules" / "eslint-plugin-vue"
    if local_bin.exists() and local_plugin.exists():
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr, "host"

    docker = shutil.which("docker")
    if not docker:
        return 127, "", "ESLint is unavailable: local eslint/plugin and docker are missing", "none"

    # Do not silently skip a missing plugin. The isolated volume keeps the
    # repository clean while making the exact same strict check reproducible.
    # node:22 уже несёт yarn (corepack). Повторный npm i -g yarn → EEXIST.
    inner = (
        "set -euo pipefail; "
        "if ! command -v yarn >/dev/null 2>&1; then "
        "  npm install --global yarn@1.22.19 --force >/dev/null; "
        "fi; "
        "yarn install --frozen-lockfile; "
        + " ".join(command)
    )
    result = subprocess.run(
        [
            docker, "run", "--rm", "-v", f"{REPO}:/app",
            "-v", f"{ESLINT_VOLUME}:/app/node_modules", "-w", "/app",
            NODE_IMAGE, "bash", "-lc", inner,
        ],
        cwd=REPO, capture_output=True, text=True, timeout=900,
    )
    return result.returncode, result.stdout, result.stderr, "docker"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--run-dir")
    parser.add_argument("--with-support", action="store_true",
                        help="При --task также линтить .tools/codeception/tests/Support. "
                             "По умолчанию Support не трогаем: его покрывает "
                             "check-tests.sh (check-selectors + check-tests-load).")
    args = parser.parse_args()

    files = changed_files()
    if args.task:
        # Не линтим исторический diff.files.md на уже влитой релизе.
        task_root = REPO / ".doc" / "tasks" / args.task / "tests"
        if task_root.is_dir():
            files.extend(task_root.rglob("*.php"))
        # Shared Support проверяется отдельным чек-листом (check-tests.sh),
        # а не каждым прогоном задачи: полный rglob Support замедлял lint
        # и валил его чужими файлами. Явный --with-support возвращает старое поведение.
        if args.with_support:
            support_root = REPO / ".tools" / "codeception" / "tests"
            if support_root.is_dir():
                files.extend(support_root.rglob("*.php"))
    files = sorted(set(p for p in files if p.is_file()))
    php = [p for p in files if p.suffix == ".php" and ".doc/qa" not in p.as_posix()]
    js = [p for p in files if p.suffix in (".js", ".vue") and "node_modules" not in p.parts]
    checks: list[dict] = []
    errors: list[str] = []

    if php:
        php_bin = shutil.which("php")
        docker = shutil.which("docker")
        docker_php = None
        if not php_bin and docker:
            image = "copytrust-codecept:8.3"
            if ensure_runner_image(docker):
                docker_php = [docker, "run", "--rm", "-v", f"{REPO}:/repo", "-w", "/repo", image, "php"]
        if not php_bin and not docker_php:
            errors.append("PHP изменён, но php не найден: lint нельзя пропустить")
        else:
            if php_bin:
                for path in php:
                    code, output = run([php_bin, "-l", str(path)])
                    checks.append({"type": "php-l", "path": path.relative_to(REPO).as_posix(), "exit": code, "output": output})
                    if code != 0:
                        errors.append(f"php -l failed: {path.relative_to(REPO)}")
            else:
                # One container per run; starting the PHP image for every file
                # makes the mandatory lint needlessly slow.
                shell_script = "rc=0; for f in \"$@\"; do php -l \"$f\" || rc=1; done; exit $rc"
                command = docker_php[:-1] + ["sh", "-lc", shell_script, "--"] + ["/repo/" + p.relative_to(REPO).as_posix() for p in php]
                code, output = run(command)
                checks.append({"type": "php-l", "paths": [p.relative_to(REPO).as_posix() for p in php], "exit": code, "output": output})
                if code != 0:
                    errors.append("php -l failed")

    if js:
        try:
            code, output, error_output, runner = run_eslint(js)
        except (subprocess.TimeoutExpired, OSError) as exc:
            code, output, error_output, runner = 124, "", str(exc), "error"
        combined = (output + "\n" + error_output).strip()
        checks.append({
            "type": "eslint",
            "paths": [p.relative_to(REPO).as_posix() for p in js],
            "exit": code,
            "runner": runner,
            "output": combined[:4000],
        })
        # При --task сужаем до строк патча задачи (как static-on-diff), иначе легаси
        # вне hunk валит обязательный lint и блокирует Codeception.
        if args.task:
            try:
                from importlib.machinery import SourceFileLoader
                static_mod = SourceFileLoader(
                    "static_on_diff",
                    str(STATIC_SCRIPT),
                ).load_module()
                rels = [p.relative_to(REPO).as_posix() for p in js]
                patch = static_mod.changed_lines(rels, task=str(args.task))
                parsed = static_mod.parse_eslint_json(output)
                if parsed is None:
                    parsed = static_mod.parse_eslint_json(combined)
                if parsed is None and code != 0:
                    errors.append("ESLint failed or was unavailable; strict lint cannot be skipped")
                else:
                    all_msg = parsed or []
                    errs = [m for m in all_msg if int(m.get("severity") or 0) >= 1]
                    kept = static_mod.filter_to_patch(errs, patch, slack=0)
                    checks[-1]["patch_errors"] = len(kept)
                    checks[-1]["patch_samples"] = kept[:10]
                    if kept:
                        errors.append(f"ESLint patch-max: {len(kept)} замечаний на строках патча задачи")
            except Exception as exc:  # noqa: BLE001 — lint не должен молча пропускать сбой фильтра
                errors.append(f"ESLint patch filter failed: {exc}")
        elif code != 0:
            errors.append("ESLint failed or was unavailable; strict lint cannot be skipped")

    status = "passed" if not errors else "failed"
    result = {"status": status, "files": [p.relative_to(REPO).as_posix() for p in files], "checks": checks, "errors": errors}
    if args.run_dir:
        out = pathlib.Path(args.run_dir) / "lint.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
