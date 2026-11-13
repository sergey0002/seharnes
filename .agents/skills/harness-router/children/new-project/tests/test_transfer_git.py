import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_git import discover_git_paths, plan_selected_git_update, snapshot_git_blobs
from transfer_inventory import snapshot_files


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class TransferGitTest(unittest.TestCase):
    def test_cli_receipt_preview_includes_removed_files_without_trusting_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bare, commit = self.fixture(root)
            target = root / 'target'
            (target / 'kit').mkdir(parents=True)
            (target / 'kit/old.txt').write_bytes(b'old')
            state = target / '.doc/web/state/transfer'
            state.mkdir(parents=True)
            receipt = {'schema_version': 1, 'release_url': 'https://user:password@example.invalid/repo',
                       'commit': commit, 'profile': 'core', 'files': {
                           'kit/old.txt': {'installed_hash': hashlib.sha256(b'old').hexdigest(),
                                           'mode': 0o644, 'role': 'owned', 'decision': 'installed'}}}
            (state / 'receipt.json').write_text(json.dumps(receipt))
            cli = Path(__file__).resolve().parents[1] / 'scripts/git-preview.py'
            command = [sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                       '--target', str(target), '--root', 'kit', '--use-receipt']
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('password', result.stdout)
            payload = json.loads(result.stdout)
            self.assertFalse(payload['applyable'])
            self.assertEqual(payload['base'], 'receipt_unverified')
            self.assertEqual(payload['receipt']['commit'], commit)
            row = next(r for r in payload['files'] if r['path'] == 'kit/old.txt')
            self.assertEqual(row['base']['sha256'], hashlib.sha256(b'old').hexdigest())
            local = subprocess.run(command + ['--local', 'kit/old.txt'], capture_output=True, text=True)
            self.assertEqual(local.returncode, 2)
            self.assertIn('LOCAL_POLICY_ESCALATION', local.stdout)
            self.assertEqual((target / 'kit/old.txt').read_bytes(), b'old')

    def test_cli_local_policy_is_scoped_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bare, commit = self.fixture(root)
            target = root / 'target'
            (target / 'kit/custom').mkdir(parents=True)
            (target / 'kit/custom/readme.md').write_text('custom')
            state = target / '.doc/harnes/state'
            state.mkdir(parents=True)
            policy = state / 'canon-paths.local.yaml'
            policy.write_text('schema_version: 1\ncustom_components:\n  - kind: "skill"\n'
                              '    name: "custom"\n    path: "kit/custom"\n'
                              '    owner: "project"\n    docs_layout_key: "layout.docs.script_skill"\n')
            cli = Path(__file__).resolve().parents[1] / 'scripts/git-preview.py'
            command = [sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                       '--base-commit', commit, '--target', str(target), '--root', 'kit', '--use-local-policy']
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload['applyable'])
            self.assertEqual(payload['local_policy'], 'scoped_historical_check_only_not_ownership_proof')
            row = next(r for r in payload['files'] if r['path'] == 'kit/custom/readme.md')
            self.assertEqual(row['proposal']['status'], 'local_custom')
            self.assertEqual((target / 'kit/custom/readme.md').read_text(), 'custom')
            policy.write_text(policy.read_text().replace('kit/custom', 'kit/a.txt'))
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn('LOCAL_POLICY_ESCALATION', result.stdout)

    def fixture(self, base):
        work, bare = base / 'work', base / 'store.git'
        work.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(work), *args], check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).stdout.decode().strip()
        git('init')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (work / 'file.txt').write_bytes(b'git content\n')
        (work / 'tool.sh').write_bytes(b'#!/bin/sh\nexit 0\n')
        (work / 'kit').mkdir()
        (work / 'kit/a.txt').write_bytes(b'a')
        (work / 'kit/b.txt').write_bytes(b'b')
        git('add', 'file.txt', 'tool.sh', 'kit')
        git('update-index', '--chmod=+x', 'tool.sh')
        git('commit', '-m', 'fixture')
        commit = git('rev-parse', 'HEAD')
        subprocess.run(['git', 'clone', '--bare', str(work), str(bare)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return work, bare, commit

    def test_reads_pinned_commit_without_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            work, bare, commit = self.fixture(Path(directory))
            (work / 'file.txt').write_bytes(b'uncommitted')
            result = snapshot_git_blobs(bare, commit, ['file.txt', 'tool.sh', 'absent'], max_file_bytes=100)
            self.assertEqual(set(result), {'file.txt', 'tool.sh'})
            self.assertEqual(result['file.txt'].sha256, hashlib.sha256(b'git content\n').hexdigest())
            self.assertEqual(result['tool.sh'].mode, 0o755)
            self.assertEqual((work / 'file.txt').read_bytes(), b'uncommitted')

    def test_rejects_unpinned_private_oversized_and_nonbare(self):
        with tempfile.TemporaryDirectory() as directory:
            work, bare, commit = self.fixture(Path(directory))
            for repo, revision, paths, maximum in ((bare, 'HEAD', ['file.txt'], 100),
                                                    (bare, commit, ['.cursor/mcp.env'], 100),
                                                    (bare, commit, ['file.txt'], 2),
                                                    (work, commit, ['file.txt'], 100)):
                with self.subTest(repo=repo, revision=revision, paths=paths), self.assertRaises(ValueError):
                    snapshot_git_blobs(repo, revision, paths, max_file_bytes=maximum)

    def test_selected_git_preview_compares_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, commit = self.fixture(root)
            target = root / 'target'
            target.mkdir()
            (target / 'file.txt').write_bytes(b'base')
            receipt = snapshot_files(target, ['file.txt'], max_file_bytes=100)
            (target / 'file.txt').write_bytes(b'local')
            (target / 'custom.txt').write_bytes(b'custom')
            result = plan_selected_git_update(repo=bare, commit=commit, target=target,
                                              paths=['file.txt', 'custom.txt', 'tool.sh'], receipt=receipt,
                                              local_paths=['custom.txt'], max_file_bytes=100)
            rows = {row['path']: row for row in result['files']}
            self.assertEqual(rows['file.txt']['proposal']['status'], 'both_modified')
            self.assertEqual(rows['custom.txt']['proposal']['status'], 'local_custom')
            self.assertEqual(rows['tool.sh']['proposal']['status'], 'new_from_release')
            self.assertFalse(result['applyable'])
            self.assertEqual(result['mode_comparison'], 'raw_os_vs_git_unverified')
            self.assertEqual((target / 'file.txt').read_bytes(), b'local')
            self.assertFalse((target / 'tool.sh').exists())
            with self.assertRaises(ValueError):
                plan_selected_git_update(repo=bare, commit=commit, target=bare / 'nested', paths=[],
                                         receipt=None, local_paths=[], max_file_bytes=100)

    def test_cli_is_explicit_and_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bare, commit = self.fixture(root)
            target = root / 'not-created'
            cli = Path(__file__).resolve().parents[1] / 'scripts/git-preview.py'
            result = subprocess.run([sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                                     '--target', str(target), '--path', 'file.txt'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'preview_only')
            self.assertFalse(payload['applyable'])
            self.assertEqual(payload['release_trust'], 'not_verified')
            self.assertFalse(target.exists())
            (target / 'kit').mkdir(parents=True)
            (target / 'kit/custom.txt').write_bytes(b'local')
            (target / 'kit/.env').write_bytes(b'secret do not read')
            discovered = subprocess.run([sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                                         '--target', str(target), '--root', 'kit'],
                                        capture_output=True, text=True, check=False)
            self.assertEqual(discovered.returncode, 0, discovered.stdout + discovered.stderr)
            payload = json.loads(discovered.stdout)
            self.assertEqual(payload['scope'], 'selected_roots_preview')
            self.assertEqual(payload['directory_summary']['directories']['kit']['files'], 3)
            self.assertEqual(payload['directory_summary']['sizes'], 'not_collected')
            self.assertTrue(payload['target_only_discovery'])
            self.assertEqual([r['path'] for r in payload['files']], ['kit/a.txt', 'kit/b.txt', 'kit/custom.txt'])
            self.assertEqual(payload['files'][-1]['proposal']['status'], 'unexpected_unclassified')
            self.assertTrue(payload['files'][-1]['proposal']['requires_review'])
            self.assertEqual(payload['protected_paths_not_read'], ['kit/.env'])
            with self.assertRaises(ValueError):
                discover_git_paths(bare, commit, ['kit'], max_entries=1)

    def test_git_symlink_and_alternates_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            work, bare, commit = self.fixture(Path(directory))
            link = work / 'link'
            try:
                os.symlink('file.txt', link)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable')
            subprocess.run(['git', '-C', str(work), 'add', 'link'], check=True)
            subprocess.run(['git', '-C', str(work), 'commit', '-m', 'symlink'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            new_commit = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD']).decode().strip()
            subprocess.run(['git', '-C', str(bare), 'fetch', str(work), new_commit], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with self.assertRaises(ValueError):
                snapshot_git_blobs(bare, new_commit, ['link'], max_file_bytes=100)
            with self.assertRaises(ValueError):
                discover_git_paths(bare, new_commit, ['link'])
            alternates = bare / 'objects/info/alternates'
            alternates.parent.mkdir(parents=True, exist_ok=True)
            alternates.write_text('')
            with self.assertRaises(ValueError):
                snapshot_git_blobs(bare, commit, ['file.txt'], max_file_bytes=100)

    def test_cli_base_commit_includes_deleted_upstream_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, base = self.fixture(root)
            (work / 'kit/a.txt').write_bytes(b'upstream')
            subprocess.run(['git', '-C', str(work), 'rm', 'kit/b.txt'], check=True, stdout=subprocess.PIPE)
            subprocess.run(['git', '-C', str(work), 'add', 'kit/a.txt'], check=True)
            subprocess.run(['git', '-C', str(work), 'commit', '-m', 'new release'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            commit = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD']).decode().strip()
            subprocess.run(['git', '-C', str(bare), 'fetch', str(work), commit], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            target = root / 'target'
            (target / 'kit').mkdir(parents=True)
            (target / 'kit/a.txt').write_bytes(b'local')
            cli = Path(__file__).resolve().parents[1] / 'scripts/git-preview.py'
            result = subprocess.run([sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                                     '--base-commit', base, '--target', str(target), '--root', 'kit'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            rows = {row['path']: row['proposal']['status'] for row in payload['files']}
            self.assertEqual(payload['base'], 'historical_commit_unverified')
            self.assertEqual(rows['kit/a.txt'], 'both_modified')
            self.assertEqual(rows['kit/b.txt'], 'both_deleted')
            self.assertFalse(payload['applyable'])
            local = subprocess.run([sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                                    '--base-commit', base, '--target', str(target), '--root', 'kit',
                                    '--local', 'kit/a.txt'], capture_output=True, text=True, check=False)
            self.assertEqual(local.returncode, 0, local.stdout + local.stderr)
            row = next(row for row in json.loads(local.stdout)['files'] if row['path'] == 'kit/a.txt')
            self.assertEqual(row['proposal']['status'], 'local_path_collision')
            self.assertTrue(row['proposal']['requires_review'])
            self.assertIsNone(row['base'])
            self.assertIn('historical_base_not_ownership', row)
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'local')

    def test_git_known_secret_is_not_returned_in_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, _ = self.fixture(root)
            synthetic = 'gh' + 'p_' + 'abcdefgh12345678'
            (work / 'ordinary.txt').write_text(synthetic, encoding='utf-8')
            subprocess.run(['git', '-C', str(work), 'add', 'ordinary.txt'], check=True)
            subprocess.run(['git', '-C', str(work), 'commit', '-m', 'fixture'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            commit = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD']).decode().strip()
            subprocess.run(['git', '-C', str(bare), 'fetch', str(work), commit], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cli = Path(__file__).resolve().parents[1] / 'scripts/git-preview.py'
            result = subprocess.run([sys.executable, str(cli), '--repo', str(bare), '--commit', commit,
                                     '--target', str(root / 'target'), '--path', 'ordinary.txt'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(synthetic, result.stdout + result.stderr)
            self.assertIn('known secret signature', result.stdout)


if __name__ == '__main__':
    unittest.main()
