"""Isolated adapter regressions; never execute the transfer against a real project."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/rebase_project.ps1'


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell is unavailable')
class TransferSafetyTest(unittest.TestCase):
    def test_core_invalid_source_policy_rejected_before_target_creation(self):
        source_root = SCRIPT.parents[6]
        relatives = ('.doc/harnes/state/canon-paths.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')
        for scenario, expected in (('missing', 'POLICY_MISSING'), ('disabled', 'TRUSTED_GATE_WEAKENING')):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, target = root / 'source', root / 'target'
                source.mkdir()
                candidate_reader = source / '.agents/skills/harness-router/children/harness-core/scripts/canon_paths.py'
                candidate_reader.parent.mkdir(parents=True)
                marker = root / 'candidate-executed'
                candidate_reader.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n', encoding='utf-8')
                for relative in relatives:
                    if scenario == 'missing' and relative == relatives[-1]:
                        continue
                    path = source / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_root / relative, path)
                if scenario == 'disabled':
                    path = source / relatives[1]
                    path.write_text(path.read_text(encoding='utf-8').replace('enabled: true', 'enabled: false', 1), encoding='utf-8')
                result = subprocess.run(['pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(source),
                                         '-Target', str(target), '-Profile', 'Core', '-Yes'],
                                        capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stdout + result.stderr)
                self.assertFalse(target.exists())
                self.assertFalse(marker.exists())

    def test_conflicting_git_switches_fail_before_target_creation(self):
        for args in (('-InitGit', '-SkipGitInit'), ('-ManageGitExclude', '-SkipExclude')):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'target'
                result = subprocess.run(['pwsh', '-NoProfile', '-File', str(SCRIPT), '-Target', str(target),
                                         *args, '-Yes'], capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Conflicting Git options', result.stdout + result.stderr)
                self.assertFalse(target.exists())

    def test_core_existing_harness_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source.mkdir()
            custom = target / '.agents/skills/custom/SKILL.md'
            custom.parent.mkdir(parents=True)
            custom.write_bytes(b'local custom')
            before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            result = subprocess.run(['pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(source),
                                     '-Target', str(target), '-Profile', 'Core', '-Mode', 'update', '-Yes'],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cannot safely update an existing harness', result.stdout + result.stderr)
            after = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_core_existing_mcp_config_is_rejected_before_any_write(self):
        for relative in ('.cursor/mcp.json', '.codex/config.toml', '.qoder/settings.json', '.qwen/settings.json'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, target = root / 'source', root / 'target'
                source.mkdir()
                config = target / relative
                config.parent.mkdir(parents=True)
                config.write_bytes(b'local configuration')
                result = subprocess.run(['pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(source),
                                         '-Target', str(target), '-Profile', 'Core', '-Mode', 'migrate', '-Yes'],
                                        capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('cannot safely update an existing harness', result.stdout + result.stderr)
                self.assertEqual(config.read_bytes(), b'local configuration')
                self.assertEqual([p for p in target.rglob('*') if p.is_file()], [config])

    @unittest.skipUnless(shutil.which('rsync'), 'rsync unavailable')
    def test_copy_excludes_source_local_yaml_and_preserves_target_local_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source.mkdir(); target.mkdir()
            (source / 'canon-paths.yaml').write_text('upstream')
            (source / 'canon-paths.local.yaml').write_text('source private')
            (target / 'canon-paths.local.yaml').write_text('target local')
            self.probe(root, ['Invoke-Robo'], r'''
Invoke-Robo -From (Join-Path $root 'source') -To (Join-Path $root 'target') -ExcludeFiles @('*.local.yaml','*.local.yml') -Mirror
@{ok=$true}|ConvertTo-Json -Compress
''')
            self.assertEqual((target / 'canon-paths.yaml').read_text(), 'upstream')
            self.assertEqual((target / 'canon-paths.local.yaml').read_text(), 'target local')

    def probe(self, root, names, body):
        script = r'''
param($path,$root,$names)
$ErrorActionPreference='Stop'
$t=$null;$e=$null
$a=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$t,[ref]$e)
if($e.Count){throw $e[0]}
foreach($name in ($names -split ',')) {
$f=$a.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
if(-not $f){throw "Missing function $name"}
. ([scriptblock]::Create($f.Extent.Text))
}
function Write-Ok([string]$Message) {}
function Write-Warn2([string]$Message) {}
'''
        p = subprocess.run(['pwsh', '-NoProfile', '-Command', '& {'+script+body+'}',
                            str(SCRIPT), str(root), ','.join(names)], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        return json.loads(p.stdout)

    def test_rewrite_preserves_python_identifiers_and_relocates_paths(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'.agents/skills/demo/main.py';p.parent.mkdir(parents=True)
            p.write_text('source = "resource"\npath = "/old/source/data"\n')
            self.probe(r,['Rewrite-SourcePaths'],r'''
Rewrite-SourcePaths -Root $root -SourceRoot '/old/source' -TargetRoot $root -SourceLeaf 'source' -TargetLeaf 'changed'
@{ok=$true}|ConvertTo-Json -Compress
''')
            text=p.read_text()
            self.assertIn('source = "resource"',text)
            self.assertIn(str(r)+'/data',text)

    def test_core_retains_harness_skills_and_panel(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            for name in ['code','ponytail','task-router','harness-router/children/new-project',
                         'harness-router/children/environment-sync','harness-router/children/mirror',
                         'harness-router/children/mcp-audit']:
                p=r/'.agents/skills'/name;p.mkdir(parents=True);(p/'SKILL.md').write_text('skill')
                (p/'scripts').mkdir();(p/'scripts/tool.py').write_text('pass')
            (r/'.cursor/rules').mkdir(parents=True)
            (r/'.doc/harnes').mkdir(parents=True)
            (r/'.doc/harnes/doc_rules.md').write_text('runtime')
            (r/'.doc/harnes/skill-format.md').write_text('authoring')
            (r/'.doc/web').mkdir(parents=True)
            (r/'.doc/web/router.php').write_text('panel')
            (r/'.qoder/skills/custom').mkdir(parents=True)
            (r/'.qoder/skills/custom/SKILL.md').write_text('local custom')
            (r/'.agents/skills/harness-router/children/mirror/skill.json').write_text(
                json.dumps({'resources': {'references': ['references/ADAPTERS.local.md', 'references/portable.md']}}))
            (r/'AGENTS.md').write_text('local instructions')
            self.probe(r,['Remove-CoreOnlyNoise'],r'''
function Disable-McpServers { param($McpJsonPath,$ServerNames) }
Remove-CoreOnlyNoise -Root $root -PreserveInstructions
@{ok=$true}|ConvertTo-Json -Compress
''')
            self.assertTrue((r/'.agents/skills/code/SKILL.md').exists())
            self.assertFalse((r/'.agents/skills/task-router').exists())
            self.assertTrue((r/'.agents/skills/harness-router/children/new-project/SKILL.md').exists())
            self.assertTrue((r/'.agents/skills/harness-router/children/mirror/SKILL.md').exists())
            self.assertTrue((r/'.doc/web/router.php').exists())
            self.assertEqual((r/'.qoder/skills/custom/SKILL.md').read_text(), 'local custom')
            manifest = json.loads((r/'.agents/skills/harness-router/children/mirror/skill.json').read_text())
            self.assertEqual(manifest['resources']['references'], ['references/portable.md'])
            self.assertTrue((r/'.agents/skills/harness-router/children/environment-sync/scripts/tool.py').exists())
            self.assertEqual((r/'AGENTS.md').read_text(),'local instructions')
            self.assertFalse((r/'.doc/harnes/skill-format.md').exists())

    def test_document_links_distinguish_excluded_project_and_missing_kit(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'.doc/harnes/guide.md';p.parent.mkdir(parents=True)
            p.write_text('[Task](../tasks/42/doc.md)\n[Web](https://example.org/a.md)\n```md\n[Example](missing.md)\n```\n')
            self.probe(r,['Normalize-KitDocLinks'],r'''
Normalize-KitDocLinks -Root $root
@{ok=$true}|ConvertTo-Json -Compress
''')
            self.assertIn('не входит в kit', p.read_text())
            self.assertIn('[Web](https://example.org/a.md)', p.read_text())
            rows=json.loads((r/'.doc/.rebase-doc-links.json').read_text())
            self.assertEqual(rows[0]['excluded'], '.doc/tasks/42/doc.md')
            p.write_text('[Lost](missing.md)\n')
            data=self.probe(r,['Normalize-KitDocLinks'],r'''
try { Normalize-KitDocLinks -Root $root; @{blocked=$false}|ConvertTo-Json -Compress }
catch { @{blocked=$true}|ConvertTo-Json -Compress }
''')
            self.assertTrue(data['blocked'])

    def test_core_runtime_docs_follow_disabled_mcp_and_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            (source / '.doc/harnes/archive/mcp').mkdir(parents=True)
            (source / '.doc/harnes/archive/mcp/legacy.md').write_text('Legacy server')
            (source / '.doc/harnes/state').mkdir(parents=True)
            (source / '.doc/harnes/state/canon-paths.yaml').write_text('layout: {}\n')
            (target / '.cursor').mkdir(parents=True)
            (target / '.cursor/mcp.json').write_text(json.dumps({'mcpServers': {'legacy': {'disabled': True}}}))
            (target / '.tools/mcp-servers').mkdir(parents=True)
            self.probe(target, ['Initialize-CoreRuntimeDocs'], r'''
Initialize-CoreRuntimeDocs -Root $root -SourceRoot (Join-Path (Split-Path $root -Parent) 'source')
@{ok=$true}|ConvertTo-Json -Compress
''')
            self.assertIn('disabled in Core', (target / '.doc/harnes/archive/mcp/legacy.md').read_text())
            self.assertIn('.tools/mcp-servers', (target / '.doc/harnes/state/26-tools.md').read_text())
            self.assertEqual((target / '.doc/harnes/state/canon-paths.yaml').read_text(), 'layout: {}\n')

    def test_core_panel_profile_is_set_before_optional_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / '.doc/web/config/service.json'
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({'profile': 'full', 'writable': True}))
            self.probe(root, ['Set-CorePanelProfile'], r'''
Set-CorePanelProfile -Root $root
@{ok=$true}|ConvertTo-Json -Compress
''')
            result = json.loads(config.read_text())
            self.assertEqual(result['profile'], 'core')
            self.assertTrue(result['writable'])

    def test_core_mcp_links_preserve_missing_source_errors_and_record_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            rel = '.agents/skills/demo/docs/mcp/demo.md'
            for tree in (source, target):
                (tree / rel).parent.mkdir(parents=True)
                (tree / rel).write_text('related: [../../../../../.doc/harnes/absent.md]\n'
                                        '[known](../../../../../.doc/harnes/absent.md)\n'
                                        '[broken](../../../../../.doc/harnes/unknown.md)\n')
            (source / '.doc/harnes').mkdir(parents=True)
            (source / '.doc/harnes/absent.md').write_text('original')
            (target / '.doc').mkdir()
            self.probe(target, ['Normalize-CoreMcpLinks'], r'''
function Write-Ok { param($message) }
Normalize-CoreMcpLinks -Root $root -SourceRoot (Join-Path (Split-Path $root -Parent) 'source')
@{ok=$true}|ConvertTo-Json -Compress
''')
            rendered = (target / rel).read_text()
            self.assertIn('related: []', rendered)
            self.assertIn('не входит в Core', rendered)
            self.assertIn('[broken](../../../../../.doc/harnes/unknown.md)', rendered)
            self.assertEqual(len(json.loads((target / '.doc/.rebase-core-links.json').read_text())), 2)

    def test_backup_manifest_includes_root_and_local_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'.agents/skills/demo/ADAPTERS.local.md';p.parent.mkdir(parents=True)
            p.write_text('local');(r/'AGENTS.md').write_text('instructions')
            data=self.probe(r,['Get-KitManifest','Test-SkipName'],r'''
$m=Get-KitManifest -Root $root -Dirs @('.agents') -RootFiles @('AGENTS.md') -SkipDirs @('node_modules','vendor')
@{paths=@($m.Keys|Sort-Object)}|ConvertTo-Json -Compress
''')
            self.assertIn('agents.md',data['paths'])
            self.assertIn('.agents/skills/demo/adapters.local.md',data['paths'])


if __name__=='__main__':
    unittest.main()
