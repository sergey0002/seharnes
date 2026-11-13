import asyncio
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp import Client
import httpx2
from codeprism.mcp import server
from codeprism.mcp.session import SessionManager

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codeprism_serve.py"
spec = importlib.util.spec_from_file_location("codeprism_serve", SCRIPT)
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


class CodePrismServerTests(unittest.TestCase):
    def test_paths_reject_prefix_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "project"
            root.mkdir()
            sibling = base / "project-other"
            sibling.mkdir()
            (root / "link").symlink_to(sibling, target_is_directory=True)
            self.assertEqual(wrapper.project_path(root, "inside.py"), root / "inside.py")
            for path in ("../project-other/x", str(sibling / "x"), "link/x"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    wrapper.project_path(root, path)

    def test_http_lock_and_stdio_compatibility(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            alias = Path(temp) / "alias"
            alias.symlink_to(root, target_is_directory=True)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                process = subprocess.run(
                    [sys.executable, str(SCRIPT), str(alias), "--transport", "http", "--port", "9001"],
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(process.returncode, 1)
                self.assertIn("already running for project", process.stderr)
                with patch.object(sys, "argv", [str(SCRIPT), str(alias), "--transport", "http", "--port", "9001"]), patch.object(server.mcp, "run") as run:
                    self.assertEqual(wrapper.main(), 1)
                    run.assert_not_called()
                with patch.object(sys, "argv", [str(SCRIPT), str(root)]), patch.object(server.mcp, "run") as run:
                    self.assertEqual(wrapper.main(), 0)
                    run.assert_called_once_with()
            finally:
                os.close(fd)

    def test_http_tools_and_loopback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            sibling = Path(temp) / "project-other"
            sibling.mkdir()
            (root / "safe.py").write_text("value = 1\n")
            (sibling / "outside.py").write_text("value = 2\n")
            (root / "link").symlink_to(sibling, target_is_directory=True)

            async def check_tools():
                async with Client(server.mcp) as client:
                    names = {tool.name for tool in await client.list_tools()}
                    self.assertNotIn("index_project", names)
                    self.assertIn("scan_file", names)
                    result = await client.call_tool("scan_file", {"file": "safe.py"})
                    self.assertEqual(result.data["status"], "PASS")
                    for name, arguments in (
                        ("scan_file", {"file": "../project-other/outside.py"}),
                        ("update_file", {"path": "link/outside.py"}),
                        ("record_write", {"session_id": "s", "file": str(sibling / "outside.py"), "content_before": "", "content_after": ""}),
                    ):
                        with self.subTest(name=name), self.assertRaises(Exception):
                            await client.call_tool(name, arguments)
                    with self.assertRaises(Exception):
                        await client.call_tool("index_project", {"path": str(sibling)})
                    self.assertEqual((sibling / "outside.py").read_text(), "value = 2\n")

            def run(**kwargs):
                self.assertEqual(kwargs, {"transport": "streamable-http", "host": "127.0.0.1", "port": 9001, "host_origin_protection": True, "allowed_hosts": ["127.0.0.1", "localhost", "::1"], "allowed_origins": []})
                manager = SessionManager(None, None, str(root))
                with self.assertRaises(ValueError):
                    manager._validate_path(str(sibling / "outside.py"))

                async def check_http():
                    await check_tools()
                    app = server.mcp.http_app(transport="streamable-http", host_origin_protection=True, allowed_hosts=kwargs["allowed_hosts"], allowed_origins=[])
                    async with app.router.lifespan_context(app):
                        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://127.0.0.1:9001") as client:
                            headers = {"Accept": "application/json, text/event-stream"}
                            response = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
                            self.assertEqual(response.status_code, 200)
                            headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
                            initialized = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
                            self.assertEqual(initialized.status_code, 202)
                            response = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
                            self.assertEqual(response.status_code, 200)
                            payload = json.loads(response.text.split("data: ", 1)[1]) if response.text.startswith("event:") else response.json()
                            names = {tool["name"] for tool in payload["result"]["tools"]}
                            self.assertIn("scan_file", names)
                            self.assertNotIn("index_project", names)
                            blocked = await client.post("/mcp", headers={"Host": "attacker.example", "Origin": "http://attacker.example"})
                            self.assertIn(blocked.status_code, (400, 403, 421))

                asyncio.run(check_http())

            with patch.dict(os.environ, {"CODEPRISM_NO_AUTO_INDEX": "1"}), patch.object(sys, "argv", [str(SCRIPT), str(root), "--transport", "http", "--port", "9001"]), patch.object(server.mcp, "run", side_effect=run):
                self.assertEqual(wrapper.main(), 0)
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
