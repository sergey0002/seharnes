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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from environment_policy import generated_paths, load, safe_path
from compact_agent_views import compact

SCRIPTS = Path(__file__).resolve().parent


class RenderError(ValueError):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


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
        raise RenderError(f"generator failed: {script.name} (exit {result.returncode})"
                          + (f": {detail}" if detail else ""), result.returncode)
    return {"script": script.name, "status": "passed"}


def _clean_views(root: Path) -> None:
    for relative in (".codex", ".kilo", ".qoder", ".qwen", ".opencode", ".omp", ".cursor", ".agents"):
        base = root / relative
        if not base.is_dir():
            continue
        for path in base.rglob("__pycache__"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
    legacy = root / ".kilo/mcp.json"
    if legacy.exists() or legacy.is_symlink():
        legacy.unlink()


def render(root: Path, *, check: bool, replace_managed_mcp: bool = False) -> dict:
    root = root.absolute()
    if not root.is_dir():
        raise RenderError("root must be an existing directory")
    if (root / "AGENTS.md").is_symlink():
        raise RenderError("linked AGENTS.md")
    entries = load(root)
    active = [entry["id"] for entry in entries if entry.get("enabled", True)]
    for relative in generated_paths(root):
        path = safe_path(root, relative)
        if path.is_symlink() and relative != ".kilo/mcp.json":
            raise RenderError(f"linked generated output: {relative}")
    steps = []
    root_args = ("--root", str(root))
    check_args = ("--check",) if check else ()
    qoder_args = ("--replace-managed-mcp",) if replace_managed_mcp and not check else ()
    cleanup = compact(root, apply=False, force=False, disabled_only=True)
    if cleanup.get("errors") or (check and cleanup["present"]):
        raise RenderError("disabled views: " + ", ".join(cleanup.get("errors") or cleanup["present"]))
    if "qoder" in active:
        steps.append(_run(SCRIPTS / "generate-qoder-config.py", *root_args, "--preflight", *qoder_args))
    steps.append(_run(SCRIPTS / "generate-agent-configs.py", str(root), *(("--check-discovery",) if check else ())))
    if "codex" in active:
        steps.append(_run(SCRIPTS / "generate-codex-mcp.py", *root_args, "--config",
                          str(root / ".codex/config.toml"), *check_args))
    for entry in entries:
        env = entry["id"]
        if entry.get("generator") and env in active:
            steps.append(_run(SCRIPTS / entry["generator"], *root_args, *check_args,
                              *(qoder_args if env == "qoder" else ())))
    if "agents" in active and not check:
        native = root / ".doc/skil_data/harness-router/antigravity_mcp_config.json"
        windows = root / ".doc/skil_data/harness-core/antigravity_mcp_config.windows-wsl.json"
        steps.append(_run(SCRIPTS / "generate-mcp-config.py", str(root), "--out", str(native)))
        steps.append(_run(SCRIPTS / "generate-mcp-config.py", str(root), "--host", "windows-wsl",
                          "--distro", os.environ.get("WSL_DISTRO_NAME", ""), "--out", str(windows)))
        for name in ("mcp.json", "mcp_config.json"):
            shutil.copyfile(native, root / ".agents" / name)
        source = root / ".cursor/scripts"
        if source.is_dir():
            import runpy
            runpy.run_path(str(SCRIPTS / "generate-agent-configs.py"))["copy_scripts_pool"](source, root / ".agents/scripts")
        source_env = root / ".cursor/mcp.env"
        if source_env.is_file():
            shutil.copyfile(source_env, root / ".agents/mcp.env")
        steps.append(_run(SCRIPTS / "generate-antigravity-rules.py", *root_args))
    elif "agents" in active:
        steps.append(_run(SCRIPTS / "generate-antigravity-rules.py", *root_args, "--check"))
    if not check:
        cleanup = compact(root, apply=True, force=False, disabled_only=True)
        if cleanup.get("errors"):
            raise RenderError("disabled views: " + ", ".join(cleanup["errors"]))
        _clean_views(root)
    return {"status": "passed" if check else "rendered", "mode": "check" if check else "write",
            "root": str(root), "steps": steps, "enabled": active, "cleanup": cleanup}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    parser.add_argument("--replace-managed-mcp", action="store_true", help="replace reviewed Qoder MCP entries")
    args = parser.parse_args(argv)
    try:
        report = render(args.root, check=args.check, replace_managed_mcp=args.replace_managed_mcp)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=False))
        return getattr(error, "code", 2)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
