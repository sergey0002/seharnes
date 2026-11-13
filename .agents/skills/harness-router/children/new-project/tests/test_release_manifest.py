import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/release_manifest.py'
ROOT = Path(__file__).resolve().parents[6]
CANON = '.doc/harnes/state/canon-paths.yaml'
POLICIES = (
    '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
    '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml',
)


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class ReleaseManifestTest(unittest.TestCase):
    def fixture(self, base: Path) -> tuple[Path, str]:
        root = base / 'repo'
        root.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(['git', '-C', str(root), *args], check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).stdout.decode().strip()

        git('init')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        for relative in (CANON, *POLICIES):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        for relative, content in (('.agents/skills/demo/SKILL.md', b'demo\n'),
                                  ('.cursor/mcp.env', b'TOKEN=secret\n'),
                                  ('.doc/skil_data/private.json', b'{"private": true}\n')):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        git('add', '-A')
        git('commit', '-m', 'fixture')
        return root, git('rev-parse', 'HEAD')

    def test_manifest_is_derived_from_commit_and_excludes_private_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root, commit = self.fixture(Path(directory))
            command = [sys.executable, str(SCRIPT), '--root', str(root), '--commit', 'HEAD']
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads(result.stdout)
            self.assertEqual(manifest['source']['commit'], commit)
            self.assertEqual(manifest['policy']['distribution_entries'], 19)
            files = {item['path']: item for item in manifest['files']}
            for relative in (CANON, *POLICIES):
                self.assertIn(relative, files)
            self.assertEqual(files['.agents/skills/demo/SKILL.md']['sha256'],
                             hashlib.sha256(b'demo\n').hexdigest())
            excluded = {item['path']: item['reason'] for item in manifest['excluded']}
            self.assertEqual(excluded['.cursor/mcp.env'], 'private_path')
            self.assertEqual(excluded['.doc/skil_data/private.json'], 'private_path')
            (root / '.agents/skills/demo/SKILL.md').write_bytes(b'dirty worktree\n')
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            second_files = {item['path']: item for item in json.loads(second.stdout)['files']}
            self.assertEqual(second_files['.agents/skills/demo/SKILL.md']['sha256'],
                             hashlib.sha256(b'demo\n').hexdigest())

    def test_tampered_policy_and_unsupported_tree_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root, commit = self.fixture(Path(directory))
            policy = root / POLICIES[0]
            policy.write_text(policy.read_text().replace('enabled: true', 'enabled: false', 1), encoding='utf-8')
            subprocess.run(['git', '-C', str(root), 'commit', '-am', 'weak policy'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--commit', 'HEAD'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['code'], 'TRUSTED_GATE_WEAKENING')
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self.fixture(Path(directory))
            (root / 'link').symlink_to('demo')
            subprocess.run(['git', '-C', str(root), 'add', 'link'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['git', '-C', str(root), 'commit', '-m', 'link'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--commit', 'HEAD'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['code'], 'unsupported_entry')

    def test_out_file_and_invalid_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root, commit = self.fixture(Path(directory))
            output = root / '.doc/skil_data/manifest.json'
            result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--commit', commit,
                                     '--out', str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(output.read_text())['source']['commit'], commit)
            invalid = subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--commit', 'missing'],
                                     capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
