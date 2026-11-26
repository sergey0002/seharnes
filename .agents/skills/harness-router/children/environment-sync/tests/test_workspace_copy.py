#!/usr/bin/env python3
"""Contract tests for the standalone workspace copy (plan: доработкамиграции, T1-T12).

The tests build throwaway source/target fixtures and never touch a real client,
provider API, index or the PHP runtime. Fake executables replace rsync/sync gates
and the PHP toolchain where a real call is not needed.

Run: python3 -m unittest discover -s .agents/skills/harness-router/children/environment-sync/tests -p 'test_workspace_copy.py'
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
ROOT = HERE.parents[5]
SETUP = SCRIPTS / "setup-workspace.py"
GATE = SCRIPTS / "workspace-gate.py"
WRAPPER = SCRIPTS / "workspace-mcp.py"
OMP_GENERATOR = SCRIPTS / "generate-omp-config.py"
REL = Path(".agents/skills/harness-router/children/environment-sync/scripts")
TOOLCHAIN = ROOT / ".tools/mcp-servers/php-toolchain"
NODE = shutil.which("node")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(script: Path, *args: str, cwd: Path | None = None,
               env: dict | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=False, timeout=timeout)


def write(path: Path, text: str, mode: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)
    return path


def run_main(module, argv: list[str]) -> int:
    with mock.patch.object(sys, "argv", ["script", *argv]):
        try:
            module.main()
        except SystemExit as exit_code:
            return exit_code.code if isinstance(exit_code.code, int) else 1
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return 78
    return 0


def completed() -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0)


SYNC_STUB = "#!/usr/bin/env bash\nexit 0\n"
GATE_STUB = "#!/usr/bin/env python3\nimport sys\nsys.exit(int(__import__('os').environ.get('FAKE_GATE_EXIT', '0')))\n"

FAKE_RENDER = '''import json, os, sys
log = os.environ.get("FAKE_RENDER_LOG")
if log:
    with open(log, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit(int(os.environ.get("FAKE_RENDER_EXIT", "0")))
'''

DUMP_CLIENT = '''import json, os, sys
with open(os.environ["DUMP_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "env": {key: os.environ.get(key) for key in ("MCP_WORKSPACE", "MCP_ENV_FILE")},
    }) + "\\n")
'''

FAKE_PHP = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_PHP_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
args = sys.argv[1:]
if "-o" in args:
    out = args[args.index("-o") + 1]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as stream:
        stream.write("<svg/>\\n")
'''


def fake_harness_script(name: str) -> str:
    label = json.dumps(name)
    return ("#!/usr/bin/env bash\n"
            "python3 -c 'import json,os,sys; open(os.environ[\"FAKE_HARNESS_LOG\"],\"a\").write("
            "json.dumps({\"script\":" + label + ",\"argv\":sys.argv[1:],\"cwd\":os.getcwd()})+\"\\n\")' \"$@\"\n")


def stub_harness(root: Path) -> None:
    write(root / REL / "sync-agent-views.sh", SYNC_STUB, 0o755)
    write(root / REL / "workspace-gate.py", GATE_STUB)


def make_gate_fixture(root: Path, mcp_servers: dict | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / REL).mkdir(parents=True, exist_ok=True)
    for relative in (".tools/scripts/run-with-mcp-env.sh", ".tools/scripts/node-mcp.sh",
                     ".tools/mcp-servers/php-toolchain/server.js",
                     ".agents/skills/phpstan-mcp/scripts/phpstan-task.sh",
                     ".agents/skills/phpstan-mcp/scripts/phpstan-docker.sh"):
        write(root / relative, "stub\n", 0o755)
    shutil.copyfile(GATE, root / REL / "workspace-gate.py")
    shutil.copyfile(WRAPPER, root / REL / "workspace-mcp.py")
    shutil.copyfile(OMP_GENERATOR, root / REL / "generate-omp-config.py")
    write(root / REL / "render_agent_views.py", FAKE_RENDER)
    servers = mcp_servers if mcp_servers is not None else canonical_servers()
    write(root / ".cursor/mcp.json", json.dumps({"mcpServers": servers}))
    subprocess.run([sys.executable, str(root / REL / "generate-omp-config.py"),
                    "--root", str(root)], check=True, capture_output=True)
    return root


def canonical_servers() -> dict:
    return {
        "git": {"type": "stdio", "command": "uvx",
                "args": ["mcp-server-git", "--repository", "${workspaceFolder}"]},
        "phpstan-mcp": {"type": "stdio", "command": "bash",
                        "args": ["${workspaceFolder}/.tools/scripts/node-mcp.sh",
                                 "${workspaceFolder}/.tools/mcp-servers/php-toolchain/server.js"],
                        "env": {"MCP_WORKSPACE": "${workspaceFolder}"},
                        "envFile": "${workspaceFolder}/.cursor/mcp.env"},
        "php-deps-mcp": {"type": "stdio", "command": "bash",
                         "args": ["${workspaceFolder}/.tools/scripts/node-mcp.sh",
                                  "${workspaceFolder}/.tools/mcp-servers/php-toolchain/server.js"],
                         "env": {"MCP_WORKSPACE": "${workspaceFolder}"},
                         "envFile": "${workspaceFolder}/.cursor/mcp.env"},
    }


def run_gate(root: Path, source: str, command: list[str] | None = None,
             env: dict | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(root / REL / "workspace-gate.py")]
    if command is None:
        argv += ["--prepare", "--source", source]
    else:
        argv += command
    return subprocess.run(argv, cwd=root, capture_output=True, text=True,
                          check=False, env=env, timeout=120)


class SetupCopyTests(unittest.TestCase):
    def test_t1_copies_ignored_tree_without_sharing(self):
        with tempfile.TemporaryDirectory(prefix="ws copy ") as directory:
            tmp = Path(directory)
            source = tmp / "source dir"
            target = tmp / "target dir"
            source.mkdir()
            (target / ".git").mkdir(parents=True)
            write(target / ".git/HEAD", "ref: refs/heads/main\n")
            stub_harness(source)
            write(source / "vendor/pkg/a.txt", "vendor-one")
            write(source / ".cursor/mcp.env", "MCP_SECRET=top-secret-value\n")
            write(source / ".doc/notes.md", "docs")
            write(source / ".git/HEAD", "source-git\n")
            write(source / "vendor/pkg/.git/HEAD", "nested-git\n")
            result = run_script(SETUP, "--source", str(source), "--target", str(target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((target / "vendor/pkg/a.txt").read_text(), "vendor-one")
            self.assertEqual((target / ".doc/notes.md").read_text(), "docs")
            self.assertEqual((target / ".cursor/mcp.env").read_text(), "MCP_SECRET=top-secret-value\n")
            self.assertEqual((target / ".git/HEAD").read_text(), "ref: refs/heads/main\n")
            self.assertFalse((target / "vendor/pkg/.git").exists())
            self.assertNotIn("top-secret-value", result.stdout + result.stderr)
            (target / "vendor/pkg/a.txt").write_text("changed")
            self.assertEqual((source / "vendor/pkg/a.txt").read_text(), "vendor-one")
            self.assertNotEqual(os.stat(source / "vendor/pkg/a.txt").st_ino,
                                os.stat(target / "vendor/pkg/a.txt").st_ino)
            marker = json.loads((target / ".workspace-ready.json").read_text())
            self.assertEqual(marker, {"schema": 1, "root": str(target.resolve()),
                                      "source": str(source.resolve())})
            self.assertTrue((target / ".workspace-setup.started").is_file())

    def test_t2_rejects_same_nested_and_linked_targets(self):
        module = load_module("setup_t2", SETUP)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            nested_target = source / "inner"
            nested_target.mkdir()
            outer = tmp / "outer"
            outer.mkdir()
            nested_source = outer / "inner"
            nested_source.mkdir()
            physical = tmp / "physical"
            physical.mkdir()
            linked = tmp / "linked"
            os.symlink(physical, linked)
            calls = []

            def fake_run(command, *args, **kwargs):
                calls.append(command)
                return completed()

            with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                self.assertEqual(run_main(module, ["--source", str(source), "--target", str(source)]), 78)
                self.assertEqual(run_main(module, ["--source", str(source), "--target", str(nested_target)]), 78)
                self.assertEqual(run_main(module, ["--source", str(nested_source), "--target", str(outer)]), 78)
                self.assertEqual(run_main(module, ["--source", str(source), "--target", str(linked)]), 78)
            self.assertEqual(calls, [])

    def test_t3_rejects_prepared_target(self):
        module = load_module("setup_t3", SETUP)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            write(source / "note.txt", "note")
            for state in ("started", "ready", "user"):
                target = tmp / f"target-{state}"
                (target / ".git").mkdir(parents=True)
                if state == "started":
                    write(target / ".workspace-setup.started", "workspace-copy-v1\n")
                elif state == "ready":
                    write(target / ".workspace-ready.json", "{}\n")
                else:
                    write(target / "user.txt", "keep\n")
                calls = []

                def fake_run(command, *args, **kwargs):
                    calls.append(command)
                    return completed()

                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(run_main(module, ["--source", str(source), "--target", str(target)]), 78)
                self.assertEqual(calls, [], state)

    def test_t4_skips_runtime_exclusions_and_keeps_lockfiles(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            target = tmp / "target"
            source.mkdir()
            (target / ".git").mkdir(parents=True)
            stub_harness(source)
            for relative in (".tools/hermes/blocked.txt", ".tools/openhands/x.txt",
                             ".tools/disk-scan/y.txt", ".codegraph/index.db",
                             ".doc/web/state/session.json", ".workspace-setup.started",
                             ".workspace-ready.json"):
                write(source / relative, "excluded\n")
            hermes = source / ".tools/hermes"
            hermes.chmod(0o000)
            for name in ("app.pid", "app.pid.lock", "run.runtime.lock", "x.sock", "db-wal", "db-shm"):
                write(source / name, "runtime\n")
            write(source / "composer.lock", "{}\n")
            write(source / "package-lock.json", "{}\n")
            write(source / "yarn.lock", "lock\n")
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(str(source / "live.sock"))
            os.mkfifo(source / "live.fifo")
            try:
                result = run_script(SETUP, "--source", str(source), "--target", str(target))
            finally:
                sock.close()
                hermes.chmod(0o755)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for relative in (".tools/hermes", ".tools/openhands", ".tools/disk-scan", ".codegraph",
                             ".doc/web/state", "app.pid", "app.pid.lock", "run.runtime.lock",
                             "x.sock", "db-wal", "db-shm", "live.sock", "live.fifo"):
                self.assertFalse((target / relative).exists(), relative)
            self.assertEqual((target / ".workspace-setup.started").read_text(), "workspace-copy-v1\n")
            self.assertEqual(json.loads((target / ".workspace-ready.json").read_text())["source"],
                             str(source.resolve()))
            for relative in ("composer.lock", "package-lock.json", "yarn.lock"):
                self.assertTrue((target / relative).is_file(), relative)

    def test_t5_symlink_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            good = tmp / "good"
            good.mkdir()
            stub_harness(good)
            write(good / "targets/real.txt", "real")
            os.symlink("targets/real.txt", good / "rel.txt")
            good_target = tmp / "good-target"
            (good_target / ".git").mkdir(parents=True)
            result = run_script(SETUP, "--source", str(good), "--target", str(good_target))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((good_target / "rel.txt").is_symlink())
            self.assertEqual((good_target / "rel.txt").read_text(), "real")

            outside = tmp / "outside.txt"
            write(outside, "outside")
            cases = {
                "absolute": lambda root: os.symlink(str(root / "plain.txt"), root / "bad"),
                "external": lambda root: os.symlink("../outside.txt", root / "bad"),
                "dangling": lambda root: os.symlink("missing.txt", root / "bad"),
                "cycle": lambda root: (os.symlink("b", root / "a"), os.symlink("a", root / "b")),
                "excluded": lambda root: os.symlink(".tools/hermes/blocked.txt", root / "bad"),
            }
            for name, build in cases.items():
                source = tmp / f"source-{name}"
                source.mkdir()
                write(source / "plain.txt", "plain")
                write(source / ".tools/hermes/blocked.txt", "blocked")
                build(source)
                target = tmp / f"target-{name}"
                (target / ".git").mkdir(parents=True)
                calls = []

                def fake_run(command, *args, **kwargs):
                    calls.append(command)
                    return completed()

                module = load_module(f"setup_t5_{name}", SETUP)
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(run_main(module, ["--source", str(source), "--target", str(target)]), 78, name)
                self.assertEqual(calls, [], name)
                self.assertFalse((target / ".workspace-setup.started").exists(), name)

    def test_t6_each_stage_failure_leaves_unfinished_copy(self):
        stages = ("rsync", "sync", "gate")
        for stage in stages:
            with tempfile.TemporaryDirectory() as directory:
                tmp = Path(directory)
                source = tmp / "source"
                source.mkdir()
                write(source / "plain.txt", "plain")
                stub_harness(source)
                target = tmp / "target"
                (target / ".git/info").mkdir(parents=True)
                write(target / ".git/HEAD", "ref: refs/heads/main\n")
                write(target / ".git/info/exclude", "# own exclude\n")

                def fake_run(command, *args, **kwargs):
                    text = " ".join(str(part) for part in command)
                    if stage == "rsync" and command and command[0] == "rsync":
                        raise subprocess.CalledProcessError(23, command)
                    if stage == "sync" and "sync-agent-views.sh" in text:
                        raise subprocess.CalledProcessError(1, command)
                    if stage == "gate" and "workspace-gate.py" in text:
                        raise subprocess.CalledProcessError(1, command)
                    return completed()

                module = load_module(f"setup_t6_{stage}", SETUP)
                with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(run_main(module, ["--source", str(source), "--target", str(target)]), 78, stage)
                self.assertFalse((target / ".workspace-ready.json").exists(), stage)
                self.assertTrue((target / ".workspace-setup.started").is_file(), stage)
                self.assertEqual((target / ".git/HEAD").read_text(), "ref: refs/heads/main\n")
                self.assertEqual((target / ".git/info/exclude").read_text(), "# own exclude\n")

                retry_calls = []

                def retry_run(command, *args, **kwargs):
                    retry_calls.append(command)
                    return completed()

                with mock.patch.object(module.subprocess, "run", side_effect=retry_run):
                    self.assertEqual(run_main(module, ["--source", str(source), "--target", str(target)]), 78, stage)
                self.assertEqual(retry_calls, [], stage)


class GateTests(unittest.TestCase):
    def test_t7_prepare_checks_local_render_and_managed_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            write(fixture / ".doc/doc.md", f"historical path {source} in prose\n")
            log = tmp / "render.log"
            env = dict(os.environ, FAKE_RENDER_LOG=str(log))
            result = run_gate(fixture, str(source), env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            recorded = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(recorded, [["--root", str(fixture), "--check"]])
            result = run_gate(fixture, str(source), ["--prepare", "--source", str(source),
                                                     "--", "x"])
            self.assertEqual(result.returncode, 78)

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            canonical = json.loads((fixture / ".cursor/mcp.json").read_text())
            canonical["mcpServers"]["git"]["args"] += ["--project-path", str(source)]
            (fixture / ".cursor/mcp.json").write_text(json.dumps(canonical))
            subprocess.run([sys.executable, str(fixture / REL / "generate-omp-config.py"),
                            "--root", str(fixture)], check=True, capture_output=True)
            result = run_gate(fixture, str(source))
            self.assertEqual(result.returncode, 78, result.stdout + result.stderr)

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            omp_path = fixture / ".omp/mcp.json"
            stale = json.loads(omp_path.read_text())
            stale["mcpServers"]["git"]["command"] = "stale"
            omp_path.write_text(json.dumps(stale))
            self.assertEqual(run_gate(fixture, str(source)).returncode, 78)

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            env = dict(os.environ, FAKE_RENDER_EXIT="1")
            self.assertEqual(run_gate(fixture, str(source), env=env).returncode, 78)

        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "copy"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "copy-two")
            self.assertEqual(run_gate(fixture, str(source)).returncode, 0)

    def test_t8_marker_and_entrypoint_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            client = write(tmp / "client.py", DUMP_CLIENT)
            log = tmp / "client.log"
            command = ["--", sys.executable, str(client)]
            env = dict(os.environ, DUMP_LOG=str(log))

            self.assertEqual(run_gate(fixture, str(source), command, env=env).returncode, 78)
            self.assertFalse(log.exists())

            marker = fixture / ".workspace-ready.json"
            write(marker, json.dumps({"schema": 1, "root": str(tmp), "source": str(source)}))
            self.assertEqual(run_gate(fixture, str(source), command, env=env).returncode, 78)
            self.assertFalse(log.exists())

            linked = tmp / "linked-ready.json"
            write(linked, json.dumps({"schema": 1, "root": str(fixture), "source": str(source)}))
            marker.unlink()
            os.symlink(linked, marker)
            self.assertEqual(run_gate(fixture, str(source), command, env=env).returncode, 78)
            self.assertFalse(log.exists())

            marker.unlink()
            write(marker, json.dumps({"schema": 1, "root": str(fixture), "source": str(source)}))
            entrypoint = fixture / ".tools/scripts/node-mcp.sh"
            replacement = write(fixture / ".tools/scripts/other.sh", "other\n", 0o755)
            entrypoint.unlink()
            os.symlink(replacement, entrypoint)
            self.assertEqual(run_gate(fixture, str(source), command, env=env).returncode, 78)
            self.assertFalse(log.exists())

            entrypoint.unlink()
            write(entrypoint, "stub\n", 0o755)
            self.assertEqual(run_gate(fixture, str(source), command, env=env).returncode, 0)
            self.assertEqual(len(log.read_text().splitlines()), 1)

    def test_t9_gate_passes_without_git_and_keeps_subject_local(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "source"
            source.mkdir()
            fixture = make_gate_fixture(tmp / "target")
            self.assertFalse((fixture / ".git").exists())
            write(fixture / ".workspace-ready.json",
                  json.dumps({"schema": 1, "root": str(fixture), "source": str(source)}))
            client = write(tmp / "client.py", DUMP_CLIENT)
            log = tmp / "client.log"
            result = run_gate(fixture, str(source), ["--", sys.executable, str(client)],
                              env=dict(os.environ, DUMP_LOG=str(log)))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(log.read_text().splitlines()), 1)
            config = json.loads((fixture / ".omp/mcp.json").read_text())
            git_args = config["mcpServers"]["git"]["args"]
            self.assertEqual(git_args[git_args.index("--repository") + 1], ".")
            self.assertNotIn(str(source), json.dumps(config))


class McpWrapperTests(unittest.TestCase):
    def make_fixture(self, root: Path, servers: dict) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / REL).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WRAPPER, root / REL / "workspace-mcp.py")
        shutil.copyfile(GATE, root / REL / "workspace-gate.py")
        write(root / ".tools/scripts/run-with-mcp-env.sh",
              (ROOT / ".tools/scripts/run-with-mcp-env.sh").read_text(), 0o755)
        write(root / ".omp/mcp.json", json.dumps({"mcpServers": servers}))
        return root

    def test_t10_allowed_names_and_disabled_server(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            dump = write(tmp / "dump.py", DUMP_CLIENT)
            log = tmp / "dump.log"
            servers = {
                name: {"type": "stdio", "enabled": True, "command": sys.executable,
                       "args": [str(dump), name]}
                for name in ("git", "phpstan-mcp", "php-deps-mcp")
            }
            fixture = self.make_fixture(tmp / "target", servers)
            fake_gate = write(fixture / REL / "workspace-gate.py", GATE_STUB)
            self.assertTrue(fake_gate.is_file())
            env = dict(os.environ, DUMP_LOG=str(log))
            for name in ("git", "phpstan-mcp", "php-deps-mcp"):
                result = run_script(fixture / REL / "workspace-mcp.py", "--server", name,
                                    cwd=fixture, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([row["argv"] for row in rows],
                             [["git"], ["phpstan-mcp"], ["php-deps-mcp"]])
            for row in rows:
                self.assertEqual(row["cwd"], str(fixture.resolve()))
                self.assertEqual(row["env"]["MCP_WORKSPACE"], str(fixture.resolve()))

            log.unlink()
            unknown = run_script(fixture / REL / "workspace-mcp.py", "--server", "other",
                                 cwd=fixture, env=env)
            self.assertEqual(unknown.returncode, 2)
            self.assertFalse(log.exists())

            servers["git"]["enabled"] = False
            (fixture / ".omp/mcp.json").write_text(json.dumps({"mcpServers": servers}))
            disabled = run_script(fixture / REL / "workspace-mcp.py", "--server", "git",
                                 cwd=fixture, env=env)
            self.assertEqual(disabled.returncode, 78)
            self.assertFalse(log.exists())

    def test_t11_wrapper_loads_env_once_and_pins_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake_source = tmp / "fake source"
            fake_source.mkdir()
            dump = write(tmp / "dump.py", DUMP_CLIENT)
            dump_log = tmp / "dump.log"
            env_log = tmp / "env.log"
            fixture = self.make_fixture(tmp / "target", {})
            write(fixture / REL / "workspace-gate.py", GATE_STUB, 0o755)
            wrapper = fixture / ".tools/scripts/run-with-mcp-env.sh"
            servers = {"git": {"type": "stdio", "enabled": True, "command": "bash",
                               "args": [str(wrapper), sys.executable, str(dump), "wrapped"]}}
            (fixture / ".omp/mcp.json").write_text(json.dumps({"mcpServers": servers}))
            write(fixture / ".cursor/mcp.env",
                  f'MCP_WORKSPACE="{fake_source}"\nMCP_ENV_FILE="{fake_source}/.cursor/mcp.env"\n'
                  f"echo loaded >> \"$FIXTURE_ENV_LOG\"\nFIXTURE_SECRET=top-secret-value\n")
            env = dict(os.environ, DUMP_LOG=str(dump_log), FIXTURE_ENV_LOG=str(env_log))
            result = run_script(fixture / REL / "workspace-mcp.py", "--server", "git",
                                cwd=fixture, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(env_log.read_text().splitlines()), 1)
            rows = [json.loads(line) for line in dump_log.read_text().splitlines()]
            self.assertEqual(rows[0]["argv"], ["wrapped"])
            self.assertEqual(rows[0]["cwd"], str(fixture.resolve()))
            self.assertEqual(rows[0]["env"]["MCP_WORKSPACE"], str(fixture.resolve()))
            self.assertIsNone(rows[0]["env"]["MCP_ENV_FILE"])
            self.assertNotIn("top-secret-value", result.stdout + result.stderr)


@unittest.skipUnless(NODE, "node is required")
class PhpRootGuardTests(unittest.TestCase):
    RESOLVE = TOOLCHAIN / "lib/resolve-php.js"

    def run_node(self, code: str, *, cwd: Path, extra_env: dict | None = None,
                 script: Path | None = None) -> subprocess.CompletedProcess:
        env = {key: value for key, value in os.environ.items() if key != "MCP_WORKSPACE"}
        env.update(extra_env or {})
        argv = ([NODE, str(script)] if script else [NODE]) + ["--input-type=module", "-e", code]
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                              check=False, timeout=60)

    def print_root(self, cwd: Path, extra_env: dict | None = None,
                   script: Path | None = None) -> subprocess.CompletedProcess:
        code = f"import {{ workspaceRoot }} from {json.dumps(self.RESOLVE.as_uri())}; console.log(workspaceRoot())"
        return self.run_node(code, cwd=cwd, extra_env=extra_env, script=script)

    def test_t11_guard_accepts_local_root(self):
        root = ROOT.resolve()
        for extra in ({}, {"MCP_WORKSPACE": ""}, {"MCP_WORKSPACE": str(root)},
                      {"MCP_WORKSPACE": "."}):
            result = self.print_root(root, extra)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), str(root), extra)
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "link"
            os.symlink(root, link)
            result = self.print_root(root, {"MCP_WORKSPACE": str(link)})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), str(root))

    def test_t11_guard_rejects_foreign_workspace_and_cwd(self):
        root = ROOT.resolve()
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory)
            for extra, cwd in ((
                    {"MCP_WORKSPACE": str(other)}, root),
                    ({"MCP_WORKSPACE": str(other)}, other)):
                result = self.print_root(cwd, extra)
                self.assertNotEqual(result.returncode, 0, extra)
                self.assertTrue("PHP MCP rejects MCP_WORKSPACE outside its local installation"
                                in result.stderr or "PHP MCP requires cwd at its local installation root"
                                in result.stderr, result.stderr)
            missing = self.print_root(root, {"MCP_WORKSPACE": str(other / "missing")})
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("ENOENT", missing.stderr)

    def test_t11_native_wrappers_source_stale_env_before_guard(self):
        root = ROOT.resolve()
        code = f"import {{ workspaceRoot }} from {json.dumps(self.RESOLVE.as_uri())}; console.log(workspaceRoot())"
        with tempfile.TemporaryDirectory(prefix="stale env ") as directory:
            tmp = Path(directory)
            env_file = write(tmp / "mcp.env", f'MCP_WORKSPACE="{tmp}"\n')
            result = subprocess.run(
                ["bash", str(root / ".tools/scripts/run-with-mcp-env.sh"), NODE,
                 "--input-type=module", "-e", code],
                cwd=root, capture_output=True, text=True, check=False, timeout=60,
                env={**{k: v for k, v in os.environ.items() if k != "MCP_WORKSPACE"},
                     "MCP_ENV_FILE": str(env_file)})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PHP MCP rejects MCP_WORKSPACE outside its local installation", result.stderr)
            result = subprocess.run(
                ["bash", str(root / ".tools/scripts/node-mcp.sh"), "--input-type=module", "-e", code],
                cwd=root, capture_output=True, text=True, check=False, timeout=60,
                env={**{k: v for k, v in os.environ.items() if k != "MCP_WORKSPACE"},
                     "MCP_WORKSPACE": str(tmp)})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PHP MCP rejects MCP_WORKSPACE outside its local installation", result.stderr)


@unittest.skipUnless(NODE, "node is required")
class PhpToolchainTests(unittest.TestCase):
    def build_toolchain(self, root: Path) -> None:
        toolchain = root / ".tools/mcp-servers/php-toolchain"
        toolchain.mkdir(parents=True)
        shutil.copyfile(TOOLCHAIN / "server.js", toolchain / "server.js")
        shutil.copyfile(TOOLCHAIN / "package.json", toolchain / "package.json")
        shutil.copytree(TOOLCHAIN / "lib", toolchain / "lib")
        os.symlink(TOOLCHAIN / "node_modules", toolchain / "node_modules")
        write(root / ".agents/skills/phpstan-mcp/scripts/phpstan-task.sh",
              fake_harness_script("phpstan-task.sh"), 0o755)
        write(root / ".agents/skills/phpstan-mcp/scripts/phpstan-docker.sh",
              fake_harness_script("phpstan-docker.sh"), 0o755)
        write(root / ".tools/scripts/run-with-mcp-env.sh",
              (ROOT / ".tools/scripts/run-with-mcp-env.sh").read_text(), 0o755)
        write(root / ".tools/scripts/node-mcp.sh",
              (ROOT / ".tools/scripts/node-mcp.sh").read_text(), 0o755)
        write(root / "vendor/bin/phpstan", "binary\n", 0o755)
        write(root / "vendor/bin/phpda", "binary\n", 0o755)
        write(root / ".cursor/tools/phpcallgraph.phar", "phar\n")
        write(root / ".cursor/tools/phpda.yml.example", "source: src\ntarget: out\n")
        write(root / "src/probe.php", "<?php echo 1;\n")
        write(root / "phpda.yml", "source: src\ntarget: out\n")
        write(root / "fake-php", FAKE_PHP, 0o755)

    def mcp_session(self, root: Path, env: dict, calls: list[dict]) -> list[dict]:
        process = subprocess.Popen(
            [NODE, str(root / ".tools/mcp-servers/php-toolchain/server.js")],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        try:
            def send(message: dict) -> None:
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()

            def receive(wanted: int) -> dict:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        raise AssertionError("MCP server closed: " + process.stderr.read())
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("id") == wanted:
                        return data

            send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "test", "version": "1"}}})
            receive(1)
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            results = []
            for index, call in enumerate(calls, start=2):
                send({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                      "params": {"name": call["name"], "arguments": call.get("arguments", {})}})
                results.append(receive(index))
            return results
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

    def test_t12_php_alias_branches_use_local_target(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            root = tmp / "target dir"
            root.mkdir()
            self.build_toolchain(root)
            fake_source = tmp / "source dir"
            write(fake_source / "src/probe.php", "<?php echo 2;\n")
            source_snapshot = sorted(p.relative_to(fake_source).as_posix()
                                     for p in fake_source.rglob("*"))
            php_log = tmp / "php.log"
            harness_log = tmp / "harness.log"
            env = {key: value for key, value in os.environ.items() if key != "MCP_WORKSPACE"}
            env.update({"PHP_BIN": str(root / "fake-php"), "FAKE_PHP_LOG": str(php_log),
                        "FAKE_HARNESS_LOG": str(harness_log), "MCP_PHP_TOOLCHAIN_MODE": "all",
                        "PHPSTAN_DOCKER_IMAGE": "fixture"})
            results = self.mcp_session(root, env, [
                {"name": "phpcallgraph_generate", "arguments": {}},
                {"name": "phpda_analyze", "arguments": {"configFile": "phpda.yml"}},
                {"name": "phpda_analyze", "arguments": {}},
                {"name": "phpstan_analyze", "arguments": {"task": 1}},
                {"name": "phpstan_analyze", "arguments": {"paths": ["src/probe.php"], "level": 2}},
            ])
            for result in results:
                payload = result["result"]
                self.assertFalse(payload.get("isError"), payload)
            php_rows = [json.loads(line) for line in php_log.read_text().splitlines()]
            self.assertEqual(php_rows[0]["cwd"], str(root.resolve()))
            self.assertIn(str(root.resolve() / "src"), php_rows[0]["argv"])
            self.assertIn(str(root.resolve() / ".cursor/artifacts/callgraph.svg"), php_rows[0]["argv"])
            self.assertTrue((root / ".cursor/artifacts/callgraph.svg").is_file())
            self.assertIn(str(root.resolve() / "phpda.yml"), php_rows[1]["argv"])
            self.assertIn(str(root.resolve() / ".cursor/tools/phpda.yml.example"), php_rows[2]["argv"])
            harness_rows = [json.loads(line) for line in harness_log.read_text().splitlines()]
            self.assertEqual(harness_rows[0]["script"], "phpstan-task.sh")
            self.assertEqual(harness_rows[0]["argv"], ["1", "0"])
            self.assertEqual(harness_rows[1]["script"], "phpstan-docker.sh")
            for row in harness_rows:
                self.assertEqual(row["cwd"], str(root.resolve()))
            self.assertIn("src/probe.php", harness_rows[1]["argv"])
            self.assertEqual(sorted(p.relative_to(fake_source).as_posix()
                                    for p in fake_source.rglob("*")), source_snapshot)


if __name__ == "__main__":
    unittest.main()
