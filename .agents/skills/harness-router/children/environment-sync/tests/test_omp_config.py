#!/usr/bin/env python3
"""Regression tests for the omp (oh-my-pi) view generator.

omp reads the canon natively, so the generator owns one file: `.omp/mcp.json`.
These tests lock that contract and the MCP translation rules.

Run: python3 .agents/skills/harness-router/children/environment-sync/tests/test_omp_config.py
Exit code 0 when every case passes, 1 otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
GENERATOR = SCRIPTS / "generate-omp-config.py"
COMPACT = SCRIPTS / "compact_agent_views.py"

sys.path.insert(0, str(SCRIPTS))

import environment_policy  # noqa: E402


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, check=False)


def write_fixture(root: Path) -> None:
    rules = root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "gates.mdc").write_text(
        "---\ndescription: hard gates\nalwaysApply: true\ngate: true\n---\n\n# Gates\n", encoding="utf-8")
    (rules / "nested").mkdir()
    (rules / "nested" / "tool.mdc").write_text(
        "---\ndescription: tool rule\nglobs: [\"**.php\"]\n---\n\n# Tool\n", encoding="utf-8")
    (root / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
        "local": {
            "type": "stdio",
            "command": "node",
            "args": ["${workspaceFolder}/server.js"],
            "env": {"PHP_BIN": "${env:PHP_BIN}", "MODE": "static"},
            "envFile": "${workspaceFolder}/.cursor/mcp.env",
        },
        "subject": {
            "type": "stdio",
            "command": "uvx",
            "args": ["some-server", "--repository", "${workspaceFolder}"],
            "env": {"MCP_WORKSPACE": "${workspaceFolder}", "OTHER": "${workspaceFolder}/sub"},
        },
        "remote": {
            "type": "http",
            "url": "http://127.0.0.1:7080/.api/mcp/v1",
            "headers": {"Authorization": "Bearer test"},
            "disabled": True,
        },
    }}), encoding="utf-8")
    flat = root / ".agents" / "skills" / "tool"
    flat.mkdir(parents=True)
    (flat / "SKILL.md").write_text("---\nname: tool\ndescription: flat tool\n---\n# Tool\n", encoding="utf-8")
    nested = root / ".agents" / "skills" / "router" / "children" / "child"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(
        "---\nname: child\ndescription: child workflow\n---\n# Child\n", encoding="utf-8")


def test_writes_only_mcp_json() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        result = run(GENERATOR, "--root", str(root))
        assert result.returncode == 0, result.stdout + result.stderr
        entries = sorted(path.name for path in (root / ".omp").iterdir())
        assert entries == ["mcp.json"], entries


def test_no_rule_or_skill_mirror() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        assert not (root / ".omp" / "rules").exists()
        assert not (root / ".omp" / "skills").exists()


def test_retired_mirrors_removed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        (root / ".omp" / "rules").mkdir(parents=True)
        (root / ".omp" / "rules" / "gates.md").write_text("stale\n", encoding="utf-8")
        (root / ".omp" / "skills" / "child").mkdir(parents=True)
        (root / ".omp" / "skills" / "child" / "SKILL.md").write_text("stale\n", encoding="utf-8")
        stale = run(GENERATOR, "--root", str(root), "--check")
        assert stale.returncode == 1, stale.stdout
        assert "stale mirror .omp/rules" in stale.stdout
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        assert not (root / ".omp" / "rules").exists()
        assert not (root / ".omp" / "skills").exists()


def test_mcp_shape() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        data = json.loads((root / ".omp" / "mcp.json").read_text(encoding="utf-8"))
        servers = data["mcpServers"]
        local = servers["local"]
        assert local["enabled"] is True
        assert local["command"] == "bash"
        assert str(root / ".tools" / "scripts" / "run-with-mcp-env.sh") in local["args"]
        assert local["args"][-1] == f"{root}/server.js", local["args"]
        assert local["env"] == {"MODE": "static"}, local["env"]
        remote = servers["remote"]
        assert remote["enabled"] is False
        assert remote["url"] == "http://127.0.0.1:7080/.api/mcp/v1"
        assert remote["headers"] == {"Authorization": "Bearer test"}
        blob = json.dumps(servers)
        assert "${workspaceFolder}" not in blob
        assert "${env:" not in blob


def test_workspace_subject_follows_cwd() -> None:
    """A repository or project root must track the task workspace, not the install."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        subject = json.loads((root / ".omp" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["subject"]
        assert subject["args"] == ["some-server", "--repository", "."], subject["args"]
        assert "MCP_WORKSPACE" not in subject.get("env", {}), subject.get("env")
        # Unknown env keys stay tool paths: only the workspace-subject allowlist moves.
        assert subject["env"]["OTHER"] == f"{root}/sub", subject["env"]


def test_check_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        first = (root / ".omp" / "mcp.json").read_text(encoding="utf-8")
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        assert (root / ".omp" / "mcp.json").read_text(encoding="utf-8") == first
        checked = run(GENERATOR, "--root", str(root), "--check")
        assert checked.returncode == 0, checked.stdout + checked.stderr
        path = root / ".omp" / "mcp.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["mcpServers"]["local"]["enabled"] = False
        path.write_text(json.dumps(data), encoding="utf-8")
        stale = run(GENERATOR, "--root", str(root), "--check")
        assert stale.returncode == 1, stale.stdout


def test_local_mcp_server_preserved() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        path = root / ".omp" / "mcp.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["mcpServers"]["mine"] = {"type": "stdio", "command": "echo"}
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        merged = json.loads(path.read_text(encoding="utf-8"))
        assert merged["mcpServers"]["mine"] == {"type": "stdio", "command": "echo"}
        assert merged["mcpServers"]["local"]["enabled"] is True


def test_compact_removes_omp_and_keeps_local_server() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        write_fixture(root)
        assert run(GENERATOR, "--root", str(root)).returncode == 0
        path = root / ".omp" / "mcp.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["mcpServers"]["mine"] = {"type": "stdio", "command": "echo"}
        path.write_text(json.dumps(data), encoding="utf-8")
        applied = run(COMPACT, "--root", str(root), "--apply")
        assert applied.returncode == 0, applied.stdout + applied.stderr
        remaining = json.loads(path.read_text(encoding="utf-8"))
        assert list(remaining["mcpServers"]) == ["mine"], remaining


def test_safe_path_allows_omp() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        assert environment_policy.safe_path(root, ".omp/mcp.json") == root / ".omp" / "mcp.json"
        for bad in (".omp/../outside", "/.omp/x", ".omp//x"):
            try:
                environment_policy.safe_path(root, bad)
            except ValueError:
                continue
            raise AssertionError(f"unsafe path accepted: {bad}")


def main() -> int:
    tests = [
        test_writes_only_mcp_json,
        test_no_rule_or_skill_mirror,
        test_retired_mirrors_removed,
        test_mcp_shape,
        test_workspace_subject_follows_cwd,
        test_check_and_idempotent,
        test_local_mcp_server_preserved,
        test_compact_removes_omp_and_keeps_local_server,
        test_safe_path_allows_omp,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
