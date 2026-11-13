#!/usr/bin/env python3
"""Isolated DSH generator regression tests. No real credentials or profiles used."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import os
import stat

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'generate-dsh-config.py'
spec = importlib.util.spec_from_file_location('dsh_generator', SCRIPT)
gen = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPT.parent))
try:
    spec.loader.exec_module(gen)
finally:
    sys.path.pop(0)


class DshConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rules = self.root / '.cursor/rules'
        self.rules.mkdir(parents=True)
        (self.rules / 'always.mdc').write_text('---\ndescription: safety\nalwaysApply: true\n---\nFULL RULE BODY\n')
        (self.rules / 'optional.mdc').write_text('---\ndescription: optional\n---\nOPTIONAL BODY\n')
        (self.rules / 'path-rule.mdc').write_text(
            '---\ndescription: path rule\nglobs:\n  - ".doc/**/*.md"\nalwaysApply: false\n---\nPATH RULE BODY\n'
        )
        names = set().union(*(v for v in gen.MCP_PROFILES.values() if v))
        self.servers = {n: {'command': 'fixture', 'args': []} for n in sorted(names)}
        self.servers['disabled'] = {'command': 'fixture', 'disabled': True}
        self.servers['extra'] = {'command': 'fixture', 'env': {'TOKEN': 'SECRET_FIXTURE'}}
        (self.root / '.cursor/mcp.json').write_text(json.dumps({'mcpServers': self.servers}))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], capture_output=True, text=True)

    def test_default_full_compatibility(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0)
        patch = self.root / '.dsh/project.patch.yml'
        first = patch.read_bytes()
        self.assertIn(b'DSH-RULES.md', first)
        self.assertEqual((self.root / 'DSH-RULES.md').read_text(), gen.emit_rules_index(self.rules, self.root))
        rules_text = (self.root / 'DSH-RULES.md').read_text()
        self.assertIn('<!-- glob-triggers -->', rules_text)
        self.assertIn('| `.doc/**/*.md` | `path-rule` | `.cursor/rules/path-rule.mdc` |', rules_text)
        self.assertNotIn('SECRET_FIXTURE', result.stdout + result.stderr)
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(first, patch.read_bytes())

    def test_stage_profiles_and_isolation(self):
        self.assertEqual(self.run_cli().returncode, 0)
        defaults = {p: p.read_bytes() for p in [self.root / 'DSH-RULES.md', self.root / '.dsh/project.patch.yml', self.root / '.cursor/mcp.json']}
        for profile in ('research', 'implementation', 'verification'):
            result = self.run_cli('--mcp-profile', profile, '--rules-mode', 'compact')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(json.loads(result.stdout)['mcp_servers']), gen.MCP_PROFILES[profile])
            patch = (self.root / f'.dsh/project.{profile}-compact.patch.yml').read_text()
            self.assertIn('DSH-BOOTSTRAP.md', patch)
            self.assertNotIn('DSH-RULES.md', patch)
            self.assertNotIn('mcp-client-extra', patch)
        for path, content in defaults.items():
            self.assertEqual(path.read_bytes(), content)
        compact = (self.root / 'DSH-BOOTSTRAP.md').read_text()
        self.assertIn('Canonical rules remain mandatory', compact)
        self.assertIn('always.mdc', compact)
        self.assertIn('optional.mdc', compact)
        self.assertNotIn('FULL RULE BODY', compact)

    def test_allow_exclude_disable(self):
        result = self.run_cli('--mcp-profile', 'research', '--servers', 'mysql,extra,disabled', '--exclude', 'extra')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['mcp_servers'], ['mysql'])

    def test_invalid_selection_no_outputs(self):
        result = self.run_cli('--servers', 'typo')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / '.dsh').exists())

    def test_profile_check_readonly_and_secret_safe(self):
        args = ('--mcp-profile', 'research', '--rules-mode', 'compact')
        self.assertEqual(self.run_cli(*args, '--check').returncode, 1)
        self.assertFalse((self.root / '.dsh').exists())
        self.assertEqual(self.run_cli(*args).returncode, 0)
        self.assertEqual(self.run_cli(*args, '--check').returncode, 0)
        patch = self.root / '.dsh/project.research-compact.patch.yml'
        patch.write_text(patch.read_text() + '\nSECRET_DRIFT\n')
        before = patch.read_bytes()
        result = self.run_cli(*args, '--check')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before, patch.read_bytes())
        self.assertNotIn('SECRET_DRIFT', result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)['runtime_verified'])

    def test_check_invalid_utf8(self):
        self.assertEqual(self.run_cli().returncode, 0)
        target = self.root / '.dsh/project.patch.yml'
        target.write_bytes(b'SECRET_INVALID\xff')
        result = self.run_cli('--check')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_bytes(), b'SECRET_INVALID\xff')
        self.assertNotIn('SECRET_INVALID', result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')

    def test_check_rejects_hand_maintained_patch_even_if_rules_match(self):
        self.assertEqual(self.run_cli().returncode, 0)
        target = self.root / '.dsh/project.patch.yml'
        target.write_text('manual secret fixture\n')
        result = self.run_cli('--check')
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)['patch_skipped'])
        self.assertNotIn('manual secret fixture', result.stdout + result.stderr)
        self.assertEqual(target.read_text(), 'manual secret fixture\n')
        self.assertEqual(self.run_cli('--check', '--force').returncode, 1)

    def test_selection_requires_explicit_patch_output(self):
        self.assertEqual(self.run_cli().returncode, 0)
        target = self.root / '.dsh/project.patch.yml'
        original = target.read_bytes()
        for args in (('--servers', 'extra'), ('--exclude', 'extra'), ('--no-mcp',),
                     ('--no-llm',), ('--no-model-selection',),
                     ('--overlay', str(self.root / 'overlay.json'))):
            for check in ((), ('--check',)):
                with self.subTest(args=args, check=check):
                    result = self.run_cli(*args, *check)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn('--patch-out', result.stderr)
                    self.assertEqual(target.read_bytes(), original)
        alternative = self.root / 'selected.patch.yml'
        self.assertEqual(self.run_cli('--servers', 'extra', '--patch-out', str(alternative)).returncode, 0)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.run_cli('--servers', 'extra', '--patch-out', str(alternative), '--check').returncode, 0)

    def test_smoke_generator_parity_uses_real_check(self):
        smoke = SCRIPT.parents[6] / '.dsh/scripts/smoke.sh'
        text = smoke.read_text(encoding='utf-8')
        section = text.split('echo "== generator parity"', 1)[1].split('echo "== patch contents"', 1)[0]
        scripts = self.root / '.agents/skills/harness-router/children/environment-sync/scripts'
        scripts.parent.mkdir(parents=True)
        scripts.symlink_to(SCRIPT.parent, target_is_directory=True)
        self.assertEqual(self.run_cli().returncode, 0)
        command = 'fail=0; ok() { :; }; bad() { fail=$((fail+1)); };\n' + section + '\nexit "$fail"'
        result = subprocess.run(['bash', '-c', command], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / '.dsh/project.patch.yml').write_text('manual patch\n')
        result = subprocess.run(['bash', '-c', command], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_output_aliases_rejected_before_writes(self):
        target = self.root / 'same'
        for check in ((), ('--check',)):
            result = self.run_cli('--patch-out', str(target), '--rules-out', str(target), *check)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.exists())
        target.write_text('original')
        for kind in ('symlink', 'hardlink'):
            alias = self.root / kind
            if kind == 'symlink':
                alias.symlink_to(target)
            else:
                os.link(target, alias)
            result = self.run_cli('--patch-out', str(target), '--rules-out', str(alias))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), 'original')

    def test_atomic_write_permissions_and_failure_cleanup(self):
        target = self.root / 'output'
        gen.atomic_write_text(target, 'old')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        target.chmod(0o640)
        gen.atomic_write_text(target, 'new')
        self.assertEqual(target.read_text(), 'new')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
        before = set(self.root.iterdir())
        def fail_replace(source, destination):
            self.assertEqual(Path(source).parent, target.parent)
            self.assertEqual(Path(destination), target)
            self.assertEqual(target.read_text(), 'new')
            raise OSError('injected failure')
        with patch.object(gen.os, 'replace', side_effect=fail_replace):
            with self.assertRaises(OSError):
                gen.atomic_write_text(target, 'SECRET_NEW')
        self.assertEqual(target.read_text(), 'new')
        self.assertEqual(set(self.root.iterdir()), before)
        with patch.object(gen.os, 'fsync', side_effect=OSError('flush failure')):
            with self.assertRaises(OSError):
                gen.atomic_write_text(target, 'SECRET_NEW')
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(target.read_text(), 'new')

    def test_no_mcp(self):
        result = self.run_cli('--mcp-profile', 'research', '--no-mcp')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['mcp_servers'], [])

    def test_overlay_switches(self):
        overlay = self.root / 'overlay.json'
        overlay.write_text(json.dumps({'llm_pi_ai': {'providers': {}}, 'subagent': {'modelSelectionSettings': True}}))
        target = self.root / 'selected.patch.yml'
        result = self.run_cli('--overlay', str(overlay), '--no-llm', '--no-model-selection', '--patch-out', str(target))
        self.assertEqual(result.returncode, 0)
        patch = target.read_text()
        self.assertNotIn('- id: llm-pi-ai', patch)
        self.assertIn('modelSelectionSettings: false', patch)


if __name__ == '__main__':
    unittest.main()
