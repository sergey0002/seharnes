import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rebase_project.ps1"


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is unavailable")
class CodePrismRebaseTest(unittest.TestCase):
    def test_next_steps_include_safe_project_service_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            command = r'''
param($scriptPath, $dir)
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$f = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Write-NextSteps' }, $true)
if (-not $f) { throw 'Missing Write-NextSteps' }
. ([scriptblock]::Create($f.Extent.Text))
function Write-Ok([string]$Message) {}
Write-NextSteps -Root $dir -ProfileName 'Full' -Name 'target' -SourceName 'source'
'''
            result = subprocess.run(
                ['pwsh', '-NoProfile', '-Command', '& {' + command + '}', str(SCRIPT), directory],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            content = (Path(directory) / 'EXPORT_NEXT_STEPS.md').read_text(encoding='utf-8')
            section = content.split('### 4.3. CodePrism', 1)[1].split('### 4.4.', 1)[0]
            for expected in ('add-codeprism.py', 'systemctl --user', 'get_graph_stats',
                             'project_path', 'index_status', 'disabled', '127.0.0.1:<PORT>',
                             'без аутентификации', 'Нативная служба Windows'):
                self.assertIn(expected, section)
            self.assertLess(section.index('project_path'), section.index('снимите'))
            self.assertNotIn('__ROOT__', content)
            blocks = re.findall(r'```bash\n(.*?)\n```', section, re.DOTALL)
            self.assertGreaterEqual(len(blocks), 4)
            for block in blocks:
                parsed = subprocess.run(['bash', '-n'], input=block, capture_output=True, text=True)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
            verifier = section.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
            compile(verifier, 'codeprism-check', 'exec')

    def test_copied_and_restored_servers_are_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, servers in {
                "copied.json": {"codeprism": {"url": "http://127.0.0.1:9201/mcp", "disabled": False, "custom": ["keep"]}, "other": {"disabled": False}},
                "target.json": {"other": {"disabled": False}},
                "backup.json": {"codeprism": {"url": "http://old-target/mcp", "custom": "keep"}, "local": {"value": 1}},
                "absent.json": {"other": {"disabled": False}},
            }.items():
                (root / name).write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")

            command = r'''
param($scriptPath, $dir)
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
foreach ($name in @('Set-CodePrismPlaceholder', 'Disable-McpServers', 'Merge-McpJsonPreserveTargetOnly')) {
    $function = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (-not $function) { throw "Missing function: $name" }
    . ([scriptblock]::Create($function.Extent.Text))
}
function Write-Ok([string]$Message) {}
Disable-McpServers -McpJsonPath (Join-Path $dir 'copied.json') -ServerNames @('codeprism')
Merge-McpJsonPreserveTargetOnly -NewPath (Join-Path $dir 'target.json') -BackupPath (Join-Path $dir 'backup.json')
Disable-McpServers -McpJsonPath (Join-Path $dir 'target.json') -ServerNames @('codeprism')
Disable-McpServers -McpJsonPath (Join-Path $dir 'target.json') -ServerNames @('codeprism')
Disable-McpServers -McpJsonPath (Join-Path $dir 'absent.json') -ServerNames @('codeprism')
'''
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-Command", "& {" + command + "}", str(SCRIPT), str(root)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            copied = json.loads((root / "copied.json").read_text())["mcpServers"]
            restored = json.loads((root / "target.json").read_text())["mcpServers"]
            self.assertEqual(copied["codeprism"], {"url": "http://127.0.0.1:0/mcp", "disabled": True, "custom": ["keep"]})
            self.assertEqual(copied["other"], {"disabled": False})
            self.assertEqual(restored["codeprism"], {"url": "http://127.0.0.1:0/mcp", "disabled": True, "custom": "keep"})
            self.assertEqual(restored["local"], {"value": 1})
            self.assertEqual(restored["other"], {"disabled": False})
            self.assertEqual(json.loads((root / "absent.json").read_text())["mcpServers"], {"other": {"disabled": False}})
            self.assertNotIn("disabled", json.loads((root / "backup.json").read_text())["mcpServers"]["codeprism"])

    def test_guard_is_before_merge_and_repeated_after_merge(self):
        text = SCRIPT.read_text(encoding="utf-8")
        main = text[text.index('# --- main ---'):]
        guard = "Disable-McpServers -McpJsonPath (Join-Path $Target '.cursor\\mcp.json') -ServerNames @('codeprism')"
        positions = [i for i in range(len(main)) if main.startswith(guard, i)]
        self.assertEqual(len(positions), 2)
        merge = main.index('Merge-McpJsonPreserveTargetOnly -NewPath (Join-Path $Target')
        self.assertLess(positions[0], merge)
        self.assertGreater(positions[1], merge)

    def test_views_and_preflight_in_temporary_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in (".agents", ".qoder", ".qwen", ".kilo", ".codex", ".dsh"):
                (root / folder).mkdir()
            server = {"url": "http://127.0.0.1:9201/mcp", "disabled": False}
            for name in (".agents/mcp_config.json", ".qoder/settings.json", ".qwen/settings.json"):
                data = {"mcpServers": {"codeprism": server, "local": {"url": "http://local"}},
                        "mcp": {"enabledProjectMcpServers": ["codeprism", "local"], "excluded": ["old"]}}
                (root / name).write_text(json.dumps(data), encoding="utf-8")
            (root / ".kilo/kilo.jsonc").write_text('// generated\n' + json.dumps({"mcp": {
                "codeprism": {"type": "remote", "url": "http://127.0.0.1:9201/mcp", "enabled": True},
                "local": {"enabled": True}}}), encoding="utf-8")
            command = r'''
param($scriptPath, $dir)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
foreach ($name in @('Set-CodePrismPlaceholder', 'Disable-QwenMcpServers', 'Protect-CodePrismViews', 'Assert-CodePrismTransferSafe')) {
    $f = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    . ([scriptblock]::Create($f.Extent.Text))
}
function Write-Ok([string]$Message) {}
function Write-Warn2([string]$Message) {}
Protect-CodePrismViews -Root $dir
Protect-CodePrismViews -Root $dir
Assert-CodePrismTransferSafe -SourceRoot $dir -TargetRoot $dir
'''
            def run():
                return subprocess.run(["pwsh", "-NoProfile", "-Command", "& {" + command + "}",
                                       str(SCRIPT), str(root)], capture_output=True, text=True)

            result = run()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in (".agents/mcp_config.json", ".qoder/settings.json"):
                data = json.loads((root / name).read_text())
                self.assertTrue(data["mcpServers"]["codeprism"]["disabled"])
                self.assertEqual(data["mcpServers"]["codeprism"]["url"], "http://127.0.0.1:0/mcp")
                self.assertEqual(data["mcpServers"]["local"], {"url": "http://local"})
                self.assertEqual(data["mcp"]["enabledProjectMcpServers"], ["local"])
            qwen = json.loads((root / ".qwen/settings.json").read_text())
            self.assertNotIn("codeprism", qwen["mcpServers"])
            self.assertEqual(qwen["mcp"]["excluded"], ["old", "codeprism"])
            kilo = json.loads((root / ".kilo/kilo.jsonc").read_text().split('\n', 1)[1])
            self.assertFalse(kilo["mcp"]["codeprism"]["enabled"])
            self.assertEqual(kilo["mcp"]["codeprism"]["url"], "http://127.0.0.1:0/mcp")
            self.assertTrue(kilo["mcp"]["local"]["enabled"])
            patch = root / ".dsh/project.patch.yml"
            patch.write_text('- id: mcp-client-codeprism\n  url: http://foreign/mcp\n')
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("existing DSH patch", result.stderr)
            self.assertIn("http://foreign/mcp", patch.read_text())
            patch.unlink()
            codex = root / ".codex/config.toml"
            codex.write_text('[mcp_servers.codeprism]\nurl = "http://foreign/mcp"\n')
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("http://foreign/mcp", codex.read_text())
            codex.write_text('[mcp_servers.codeprism]\ncommand = "bridge"\n')
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('command = "bridge"', codex.read_text())

    def test_source_codeprism_url_does_not_block_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            (source / ".codex").mkdir(parents=True)
            (source / ".codex/config.toml").write_text(
                '[mcp_servers.codeprism]\nurl = "http://127.0.0.1:9201/mcp"\nenabled = false\n'
            )
            target.mkdir()
            command = r'''
param($scriptPath, $source, $target)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$f = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-CodePrismTransferSafe' }, $true)
. ([scriptblock]::Create($f.Extent.Text))
function Write-Warn2([string]$Message) {}
Assert-CodePrismTransferSafe -SourceRoot $source -TargetRoot $target
'''
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-Command", "& {" + command + "}", str(SCRIPT), str(source), str(target)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
