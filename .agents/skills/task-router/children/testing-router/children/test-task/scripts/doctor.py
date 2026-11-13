#!/usr/bin/env python3
"""Fail-fast diagnostics for the local CopyTrust task-test environment."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[8]
APP_CONTAINER = os.environ.get("QA_PHPUNIT_CONTAINER", "copytrust-dev-php-apache-1")
MYSQL_CONTAINER = os.environ.get("QA_MYSQL_CONTAINER", "copytrust-dev-mysql-1")


def command(args: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        result = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def http(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status < 500, f"HTTP {response.status}"
    except Exception as exc:  # noqa: BLE001 - diagnostics report connection reason
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-browser", action="store_true")
    parser.add_argument("--require-db", action="store_true")
    args = parser.parse_args()
    results: list[dict[str, str | bool]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        results.append({"check": name, "ok": ok, "detail": detail})

    docker = shutil.which("docker")
    add("docker-cli", docker is not None, docker or "docker not found")
    if docker:
        code, output = command([docker, "context", "show"])
        add("docker-context", code == 0 and output == "default", output or f"exit {code}")
        for container in (APP_CONTAINER, MYSQL_CONTAINER):
            code, output = command([docker, "inspect", "-f", "{{.State.Running}}", container])
            add(f"container:{container}", code == 0 and output == "true", output or f"exit {code}")
        code, output = command([docker, "exec", APP_CONTAINER, "sh", "-lc",
                                "test -f /var/www/html/configs/bootstrap.php && test -x /var/www/html/vendor/phpunit/phpunit/phpunit && test -x /var/www/html/vendor/doctrine/migrations/bin/doctrine-migrations && printf APP_MOUNT_OK"])
        add("app-mount-and-binaries", code == 0 and "APP_MOUNT_OK" in output, output or f"exit {code}")
        code, output = command([docker, "exec", APP_CONTAINER, "sh", "-lc",
                                "test -f /var/www/.config/.env && printf CONFIG_OK"])
        add("app-config-mount", code == 0 and "CONFIG_OK" in output, output or "expected /var/www/.config/.env")
        code, output = command([docker, "exec", APP_CONTAINER, "php", "-r", "echo PHP_VERSION;"])
        add("app-php", code == 0, output or f"exit {code}")

    app_url = os.environ.get("CHROMEDRIVER_APP_URL", "http://127.0.0.1:8030/")
    ok, detail = http(app_url)
    add("application", ok, detail)
    webdriver_ready = False
    for label, url in (("webdriver-local", "http://127.0.0.1:9515/wd/hub/status"),
                       ("webdriver-selenium", "http://127.0.0.1:4444/status")):
        ok, detail = http(url)
        if ok:
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    data = json.loads(response.read().decode())
                ok = bool(data.get("value", {}).get("ready", data.get("ready", False)))
                detail = "ready" if ok else "endpoint responds but ready=false"
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, str(exc)
        if ok:
            webdriver_ready = True
        add(label, ok, detail)
        if ok:
            break
    if not args.require_browser:
        results = [item for item in results if not item["check"].startswith("webdriver-")]
        results.append({"check": "webdriver", "ok": True,
                        "detail": "not required for this phase"})
    elif not webdriver_ready:
        results.append({"check": "webdriver", "ok": False,
                        "detail": "neither local ChromeDriver nor Selenium is ready"})
    elif not any(item["check"] == "webdriver-local" and item["ok"] for item in results):
        results.append({"check": "webdriver-local", "ok": True,
                        "detail": "local ChromeDriver is ready"})

    env_file = REPO / ".tools" / "codeception" / ".env"
    required_keys = {"MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD",
                     "CHROMEDRIVER_HOST", "CHROMEDRIVER_PORT", "CHROMEDRIVER_APP_URL"}
    present = set()
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                present.add(line.split("=", 1)[0].strip())
    missing = sorted(required_keys - present)
    add("codeception-env", not missing, f"missing keys: {', '.join(missing)}" if missing else "required keys present")

    db_required = False
    if args.task:
        matrix = REPO / ".doc" / "tasks" / args.task / "ac-matrix.json"
        try:
            db_required = json.loads(matrix.read_text()).get("db_isolation", "not_required") == "required"
        except Exception:
            pass
    if db_required and args.require_db:
        reset = os.environ.get("QA_DB_RESET_CMD", "").strip()
        cleanup = os.environ.get("QA_DB_CLEANUP_CMD", "").strip()
        no_op = {"true", ":", "echo", "echo true", "/bin/true"}
        valid = bool(reset and cleanup and reset not in no_op and cleanup not in no_op)
        add("db-isolation-hooks", valid, "real reset/cleanup configured" if valid else "required real hooks missing or no-op")

    failures = [item for item in results if not item["ok"]]
    payload = {"status": "passed" if not failures else "failed", "task": args.task, "checks": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"{'PASS' if item['ok'] else 'FAIL':4} {item['check']}: {item['detail']}")
        print(f"doctor: {payload['status']} ({len(failures)} failed checks)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
