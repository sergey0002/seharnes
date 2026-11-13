"""Integration: clean Core export uses the installed policy declarations."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/rebase_project.ps1'
SOURCE = SCRIPT.parents[6]


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell is unavailable')
class CorePolicyExportTest(unittest.TestCase):
    def test_core_exports_policy_files_and_strict_policy_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'target'
            result = subprocess.run([
                'pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(SOURCE),
                '-Target', str(target), '-Profile', 'Core', '-Mode', 'migrate',
                '-ProjectName', 'policyfixture', '-SkipReview', '-SkipTools',
                '-SkipRuntimeDeps', '-SkipSiblingConfig', '-Yes',
            ], capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('EXPORT_REBASE_DONE', result.stdout)
            self.assertFalse((target / '.git').exists())
            for name in ('skill-format.yaml', 'component-docs.yaml'):
                self.assertTrue((target / '.agents/skills/harness-router/children/harness-core/assets/policies' / name).is_file())
            self.assertTrue((target / '.doc/harnes/state/canon-paths.yaml').is_file())
            self.assertTrue((target / '.doc/web/README.md').is_file())
            checks = [
                ('.agents/skills/harness-router/children/improvement/scripts/validate_structure.py', '--require-policy', '--json'),
                ('.agents/skills/harness-router/children/improvement/scripts/validate_skills.py', '--policy-root', '.', '--json'),
                ('.agents/skills/harness-router/children/doc-script/scripts/doc_script.py', '--audit', '--policy-root', '.'),
                ('.agents/skills/harness-router/children/doc-skill/scripts/doc_skill.py', '--audit', '--policy-root', '.'),
                ('.agents/skills/harness-router/children/doc-mcp/scripts/doc_mcp.py', '--audit', '--policy-root', '.'),
            ]
            for args in checks:
                with self.subTest(check=args[0]):
                    check = subprocess.run([sys.executable, *args], cwd=target, capture_output=True, text=True, timeout=120)
                    self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            policy = target / '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml'
            policy.unlink()
            check = subprocess.run([sys.executable, *checks[0]], cwd=target, capture_output=True, text=True, timeout=120)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn('POLICY_MISSING', check.stdout + check.stderr)

    @unittest.skipUnless(shutil.which('git'), 'Git is unavailable')
    def test_core_default_preserves_existing_git_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'target'
            target.mkdir()
            subprocess.run(['git', 'init', '-q', str(target)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(target), 'remote', 'add', 'origin', 'https://example.invalid/app.git'],
                           check=True, capture_output=True)
            exclude = target / '.git/info/exclude'
            exclude.write_bytes(b'# local settings\n/project-private\n')
            def git_tree():
                return {path.relative_to(target / '.git').as_posix(): path.read_bytes()
                        for path in (target / '.git').rglob('*') if path.is_file()}
            before = git_tree()
            result = subprocess.run([
                'pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(SOURCE),
                '-Target', str(target), '-Profile', 'Core', '-Mode', 'migrate',
                '-ProjectName', 'gitfixture', '-SkipReview', '-SkipTools', '-SkipRuntimeDeps',
                '-SkipSiblingConfig', '-Yes',
            ], capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(git_tree(), before)

    @unittest.skipUnless(shutil.which('git'), 'Git is unavailable')
    def test_core_git_initialization_and_excludes_require_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'target'
            result = subprocess.run([
                'pwsh', '-NoProfile', '-File', str(SCRIPT), '-Source', str(SOURCE),
                '-Target', str(target), '-Profile', 'Core', '-Mode', 'migrate',
                '-ProjectName', 'gitoptin', '-SkipReview', '-SkipTools', '-SkipRuntimeDeps',
                '-SkipSiblingConfig', '-InitGit', '-ManageGitExclude', '-Yes',
            ], capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / '.git/info/exclude').is_file())
            self.assertIn('export-rebase-project', (target / '.git/info/exclude').read_text(encoding='utf-8'))
            remotes = subprocess.run(['git', '-C', str(target), 'remote'], check=True, capture_output=True, text=True)
            self.assertEqual(remotes.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
