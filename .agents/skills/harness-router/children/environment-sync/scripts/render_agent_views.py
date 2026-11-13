#!/usr/bin/env python3
"""Render agent views with the current trusted generators.

This replaces the Bash orchestration for the project-local views. It runs the
generator scripts that belong to this installation against an explicitly
chosen root; it never executes scripts from the root being rendered. Global
home configuration and Docker/host setup are out of scope.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


class RenderError(ValueError):
    pass


def _run(script: Path, *args: str, timeout: int = 180) -> dict:
    if not script.is_file():
        raise RenderError(f"generator is missing: {script.name}")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run([sys.executable, str(script), *args], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RenderError(f"generator failed: {script.name}") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace")[-2000:].strip()
        raise RenderError(f"generator failed: {script.name}: {detail}")
    return {"script": script.name, "status": "passed"}


def _clean_views(root: Path) -> None:
    for relative in (".codex", ".kilo", ".qoder", ".qwen", ".cursor", ".agents"):
        base = root / relative
        if not base.is_dir():
            continue
        for path in base.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
    legacy = root / ".kilo/mcp.json"
    if legacy.exists() or legacy.is_symlink():
        legacy.unlink()


def render(root: Path, *, check: bool) -> dict:
    root = root.absolute()
    if not root.is_dir():
        raise RenderError("root must be an existing directory")
    steps = []
    steps.append(_run(SCRIPTS / "generate-qoder-config.py", "--root", str(root), "--preflight"))
    if check:
        steps.append(_run(SCRIPTS / "generate-qoder-config.py", "--root", str(root), "--check"))
        steps.append(_run(SCRIPTS / "generate-agent-configs.py", str(root), "--check-discovery"))
        steps.append(_run(SCRIPTS / "generate-codex-mcp.py", "--root", str(root),
                          "--config", str(root / ".codex/config.toml"), "--check"))
        steps.append(_run(SCRIPTS / "generate-qwen-config.py", "--root", str(root), "--check"))
        steps.append(_run(SCRIPTS / "generate-dsh-config.py", "--root", str(root), "--check"))
        return {"status": "passed", "mode": "check", "root": str(root), "steps": steps}
    steps.append(_run(SCRIPTS / "generate-agent-configs.py", str(root)))
    steps.append(_run(SCRIPTS / "generate-codex-mcp.py", "--root", str(root),
                      "--config", str(root / ".codex/config.toml")))
    steps.append(_run(SCRIPTS / "generate-mcp-config.py", str(root),
                      "--out", str(root / ".doc/skil_data/harness-router/antigravity_mcp_config.json")))
    steps.append(_run(SCRIPTS / "generate-qoder-config.py", "--root", str(root)))
    steps.append(_run(SCRIPTS / "generate-qwen-config.py", "--root", str(root)))
    steps.append(_run(SCRIPTS / "generate-antigravity-rules.py", "--root", str(root)))
    steps.append(_run(SCRIPTS / "generate-dsh-config.py", "--root", str(root)))
    _clean_views(root)
    return {"status": "rendered", "mode": "write", "root": str(root), "steps": steps}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)
    try:
        report = render(args.root, check=args.check)
    except RenderError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
