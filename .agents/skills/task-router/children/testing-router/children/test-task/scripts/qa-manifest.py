#!/usr/bin/env python3
"""Build and verify the immutable inputs of a QA run.

The verdict is only meaningful for the exact code, test code and task
requirements that were used by the run.  Generated output and test-runs are
deliberately excluded from the three fingerprints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
TASK_ROOT = REPO / ".doc" / "tasks"


def git_files() -> list[pathlib.Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [REPO / line for line in out.splitlines() if line]


def existing(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    return sorted({p.resolve() for p in paths if p.is_file()})


def source_files() -> list[pathlib.Path]:
    extensions = {".php", ".js", ".vue", ".ts", ".tsx", ".css", ".scss", ".tpl", ".sql"}
    excluded = {".git", "vendor", "node_modules", "test-runs", "_output"}
    result = []
    for path in git_files():
        if path.suffix.lower() not in extensions:
            continue
        try:
            relative = path.relative_to(REPO)
        except ValueError:
            continue
        if any(part in excluded for part in relative.parts):
            continue
        if ".doc" in relative.parts or ".cursor" in relative.parts:
            continue
        result.append(path)
    return existing(result)


def test_files(task: str) -> list[pathlib.Path]:
    result = [
        REPO / ".doc" / "codeception" / "tests",
        TASK_ROOT / task / "tests",
        REPO / ".doc" / "qa",
    ]
    files: list[pathlib.Path] = []
    for root in result:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file())
    return existing([p for p in files if "test-runs" not in p.parts and "_output" not in p.parts])


def requirement_files(task: str) -> list[pathlib.Path]:
    root = TASK_ROOT / task
    if not root.is_dir():
        return []
    allowed = {"task.md", "test.md", "plan.md", "doc.md", "ac-matrix.json", "requirements.json", "diff.files.md"}
    return existing([p for p in root.iterdir() if p.is_file() and p.name in allowed])


def skill_files() -> list[pathlib.Path]:
    names = ("prepare-task-test", "test-task", "browser-verify", "prepare-plan")
    return existing([REPO / ".cursor" / "skills" / name / "SKILL.md" for name in names])


def digest(paths: list[pathlib.Path]) -> tuple[str, list[dict[str, str]]]:
    entries = []
    for path in paths:
        relative = path.relative_to(REPO).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": relative, "sha256": file_hash})
    encoded = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), entries


def environment_digest() -> tuple[str, dict[str, str]]:
    """Hash runtime identity without writing credentials into run artifacts."""
    env_path = REPO / ".doc" / "codeception" / ".env"
    selected = {"QA_PHPUNIT_CONTAINER", "QA_PHPSTAN_LEVEL", "CHROMEDRIVER_HOST",
                "CHROMEDRIVER_PORT", "CHROMEDRIVER_APP_URL", "MYSQL_HOST",
                "MYSQL_PORT", "MYSQL_DATABASE"}
    values = {key: os.environ[key] for key in sorted(selected) if key in os.environ}
    if env_path.is_file():
        values["codeception_env_sha256"] = hashlib.sha256(env_path.read_bytes()).hexdigest()
    docker = shutil.which("docker")
    if docker:
        container = os.environ.get("QA_PHPUNIT_CONTAINER", "copytrust-dev-php-apache-1")
        try:
            image = subprocess.run([docker, "inspect", "-f", "{{.Image}}", container],
                                   cwd=REPO, capture_output=True, text=True, timeout=5)
            if image.returncode == 0:
                values["php_container_image"] = image.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            values["php_container_image"] = "unavailable"
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), values


def build(task: str, group: str) -> dict:
    code_hash, code = digest(source_files())
    tests_hash, tests = digest(test_files(task))
    requirements_hash, requirements = digest(requirement_files(task))
    skills_hash, skills = digest(skill_files())
    environment_hash, environment = environment_digest()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return {
        "schema": 2,
        "task": task,
        "group": group,
        "commit": commit,
        "code_sha256": code_hash,
        "tests_sha256": tests_hash,
        "requirements_sha256": requirements_hash,
        "skills_sha256": skills_hash,
        "environment_sha256": environment_hash,
        "environment": environment,
        "code_files": code,
        "test_files": tests,
        "requirement_files": requirements,
        "skill_files": skills,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--check", help="Compare an existing manifest with current inputs")
    args = parser.parse_args()

    current = build(args.task, args.group)
    if args.check:
        expected = json.loads(pathlib.Path(args.check).read_text(encoding="utf-8"))
        fields = ("task", "group", "code_sha256", "tests_sha256", "requirements_sha256", "skills_sha256", "environment_sha256")
        ok = all(current.get(field) == expected.get(field) for field in fields)
        print(json.dumps({"ok": ok, "mismatched": [f for f in fields if current.get(f) != expected.get(f)]}, ensure_ascii=False))
        return 0 if ok else 1

    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
