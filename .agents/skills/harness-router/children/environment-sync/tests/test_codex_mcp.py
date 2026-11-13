import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate-codex-mcp.py"


class CodexMcpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="codex-mcp-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".cursor").mkdir()
        self.input = self.root / ".cursor" / "mcp.json"
        self.target = self.root / "config.toml"
        self.original = 'model = "example"\nmessage = """\n[mcp_servers.fake]\nnot a table\n"""\n[mcp_servers.old.env]\nK = "v"\n[features]\nvalue = true\n'
        self.target.write_text(self.original)

    def run_generator(self, servers, *args):
        self.input.write_text(json.dumps({"mcpServers": servers}))
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--config", str(self.target), *args], capture_output=True, text=True)

    def test_preserve_remove_disabled_and_idempotence(self):
        servers = {"local": {"command": "node", "args": ["${workspaceFolder}/a"]}, "disabled": {"disabled": True, "command": "node"}, "disabled2": {"enabled": False, "url": "https://example.org/mcp"}, "remote": {"type": "http", "url": "https://example.org/mcp", "headers": {"Authorization": "Bearer ${env:API_TOKEN}", "X-Key": "${env:OTHER}", "Accept": "application/json"}, "disabledTools": ["bad"]}}
        self.assertEqual(self.run_generator(servers).returncode, 0)
        output = self.target.read_text()
        parsed = tomllib.loads(output)
        self.assertEqual(parsed["message"], "[mcp_servers.fake]\nnot a table\n")
        self.assertEqual(parsed["features"], {"value": True})
        self.assertEqual(set(parsed["mcp_servers"]), {"local", "remote", "disabled", "disabled2"})
        self.assertIs(parsed["mcp_servers"]["disabled"]["enabled"], False)
        self.assertIs(parsed["mcp_servers"]["disabled2"]["enabled"], False)
        self.assertEqual(parsed["mcp_servers"]["remote"]["bearer_token_env_var"], "API_TOKEN")
        self.assertEqual(parsed["mcp_servers"]["remote"]["env_http_headers"], {"X-Key": "OTHER"})
        self.assertEqual(parsed["mcp_servers"]["remote"]["disabled_tools"], ["bad"])
        self.assertEqual(self.run_generator(servers, "--check").returncode, 0)
        self.assertEqual(self.run_generator(servers).returncode, 0)
        self.assertEqual(output, self.target.read_text())

    def test_wrapper_loads_env_without_embedding_secrets_and_quotes_arguments(self):
        secret = "private-value-456"
        envfile = self.root / "file with space.env"
        envfile.write_text("TOKEN=" + secret + "\n")
        program = "import os,sys; print(os.environ['COPY']); print(sys.argv[1])"
        servers = {"a": {"command": sys.executable, "args": ["-c", program, "x;$(false)"], "envFile": str(envfile), "env": {"COPY": "${env:TOKEN}"}}}
        self.assertEqual(self.run_generator(servers).returncode, 0)
        content = self.target.read_text()
        self.assertNotIn(secret, content)
        server = tomllib.loads(content)["mcp_servers"]["a"]
        run = subprocess.run([server["command"], *server["args"]], capture_output=True, text=True, env={"PATH": os.environ["PATH"]})
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.stdout.splitlines(), [secret, "x;$(false)"])

    def test_errors_preserve_target_and_hide_values(self):
        bad = [{"command": "node", "mystery": "private-value"}, {"url": "https://example.test/?token=private-value"}, {"url": "https://example.test", "headers": {"Authorization": "private-value"}}, {"command": "node", "env": {"API_TOKEN": "private-value"}}, {"type": "sse", "url": "https://example.test"}]
        for entry in bad:
            with self.subTest(entry=list(entry)):
                result = self.run_generator({"a": entry})
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("private-value", result.stdout + result.stderr)
                self.assertEqual(self.original, self.target.read_text())

    def test_unsupported_inline_mcp_preserves_file(self):
        source = 'mcp_servers = { old = { command = "node" } }\nmodel = "x"\n'
        self.target.write_text(source)
        self.assertEqual(self.run_generator({}).returncode, 2)
        self.assertEqual(source, self.target.read_text())

    def test_missing_envfile_fails_at_launch_and_check_does_not_write(self):
        servers = {"a": {"command": "true", "envFile": "missing.env"}}
        self.assertEqual(self.run_generator(servers, "--check").returncode, 1)
        self.assertEqual(self.original, self.target.read_text())
        self.assertEqual(self.run_generator(servers).returncode, 0)
        entry = tomllib.loads(self.target.read_text())["mcp_servers"]["a"]
        self.assertNotEqual(subprocess.run([entry["command"], *entry["args"]], capture_output=True).returncode, 0)

    def test_malformed_input_and_permissions(self):
        self.target.chmod(0o600)
        self.input.write_text('{"mcpServers":')
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--config", str(self.target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.original, self.target.read_text())
        self.assertEqual(self.run_generator({"a": {"command": "true"}}).returncode, 0)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_symbolic_link_is_rejected(self):
        link = self.root / "link.toml"
        link.symlink_to(self.target)
        self.input.write_text('{"mcpServers": {}}')
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--config", str(link)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.original, self.target.read_text())

    def test_disabled_invalid_fields_fail_closed(self):
        for entry in ({"disabled": True, "command": "node", "unknown": "value"}, {"enabled": False, "url": "https://example.org", "headers": {"Authorization": "${env:INVALID-NAME}"}}):
            with self.subTest(keys=list(entry)):
                result = self.run_generator({"a": entry})
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("secret", result.stdout + result.stderr)
                self.assertEqual(self.original, self.target.read_text())

    def test_audit_reports_all_servers_without_names_or_values(self):
        self.input.write_text(json.dumps({"mcpServers": {"secret-server-name": {"command": "node", "alwaysAllow": ["secret-tool"]}, "disabled": {"disabled": True, "url": "https://example.org", "alwaysAllow": ["secret-tool"], "headers": {"Authorization": "secret-value"}}, "good": {"command": "node"}}}))
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), "--audit-canon"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["servers"], {"total": 3, "enabled": 2, "disabled": 1})
        self.assertEqual(report["blockers"], {})
        self.assertEqual(report["warnings"]["alwaysAllow ignored; existing Codex approval policy retained"], 2)
        self.assertEqual(report["warnings"]["disabled HTTP server has omitted literal header; inert stub prevents unauthenticated start"], 1)
        self.assertNotIn("secret", result.stdout + result.stderr)
        self.assertEqual(self.original, self.target.read_text())

    def test_audit_clean_and_invalid_allow(self):
        self.input.write_text(json.dumps({"mcpServers": {"good": {"command": "node", "alwaysAllow": []}}}))
        command = [sys.executable, str(SCRIPT), "--root", str(self.root), "--audit-canon"]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(self.run_generator({"bad": {"command": "node", "alwaysAllow": None}}).returncode, 2)

    def test_approval_policy_preserved_and_disabled_tools_enforced(self):
        self.target.write_text('approval_policy = "never"\n[mcp_servers.a]\ncommand = "old"\ndefault_tools_approval_mode = "prompt"\n[mcp_servers.a.tools.unsafe]\napproval_mode = "prompt"\noutput_token_limit = 100\n')
        servers = {"a": {"command": "node", "alwaysAllow": ["private-tool"], "disabledTools": ["unsafe"]}}
        result = self.run_generator(servers)
        self.assertEqual(result.returncode, 0)
        self.assertIn("alwaysAllow ignored", result.stderr)
        self.assertNotIn("private-tool", result.stderr)
        entry = tomllib.loads(self.target.read_text())
        self.assertEqual(entry["approval_policy"], "never")
        entry = entry["mcp_servers"]["a"]
        self.assertEqual(entry["default_tools_approval_mode"], "prompt")
        self.assertEqual(entry["tools"]["unsafe"], {"approval_mode": "prompt", "output_token_limit": 100})
        self.assertEqual(entry["disabled_tools"], ["unsafe"])
        self.assertNotIn("private-tool", self.target.read_text())
        self.assertEqual(self.run_generator(servers, "--check").returncode, 0)

    def test_disabled_literal_header_is_inert_even_when_enabled(self):
        servers = {"a": {"disabled": True, "url": "https://example.org/mcp", "headers": {"Authorization": "sensitive-value"}, "disabledTools": ["blocked"]}}
        result = self.run_generator(servers)
        self.assertEqual(result.returncode, 0)
        self.assertIn("inert stub", result.stderr)
        self.assertNotIn("sensitive-value", result.stdout + result.stderr + self.target.read_text())
        entry = tomllib.loads(self.target.read_text())["mcp_servers"]["a"]
        self.assertFalse(entry["enabled"])
        self.assertNotIn("url", entry)
        self.assertEqual(entry["disabled_tools"], ["blocked"])
        self.assertNotEqual(subprocess.run([entry["command"], *entry["args"]], capture_output=True).returncode, 0)
        self.assertEqual(self.run_generator(servers, "--check").returncode, 0)
        servers["a"]["disabled"] = False
        before = self.target.read_text()
        self.assertEqual(self.run_generator(servers).returncode, 2)
        self.assertEqual(self.target.read_text(), before)
        servers["a"]["headers"] = {}
        self.assertEqual(self.run_generator(servers).returncode, 2)
        self.assertEqual(self.target.read_text(), before)
        servers["a"]["headers"] = {"Authorization": "Bearer ${env:API_TOKEN}"}
        self.assertEqual(self.run_generator(servers).returncode, 0)
        active = tomllib.loads(self.target.read_text())["mcp_servers"]["a"]
        self.assertNotIn("enabled", active)
        self.assertEqual(active["bearer_token_env_var"], "API_TOKEN")


if __name__ == "__main__":
    unittest.main()
