import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/harness_transfer.py'
ROOT = Path(__file__).resolve().parents[6]
STATE = Path('.doc/web/state')
RECEIPT = STATE / 'transfer' / 'receipt.json'
CANON = '.doc/harnes/state/canon-paths.yaml'
POLICIES = ('.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
            '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes = b'fixture') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def receipt(root: Path, commit: str, files: dict[str, bytes], profile: str = 'core') -> None:
    payload = {'schema_version': 1, 'release_url': 'https://example.invalid/repo.git', 'commit': commit,
               'profile': profile, 'files': {
                   path: {'installed_hash': digest(data), 'mode': 0o644, 'role': 'owned',
                          'decision': 'installed'} for path, data in files.items()}}
    write(root / RECEIPT, json.dumps(payload).encode())


class HarnessTransferLocalTest(unittest.TestCase):
    def test_install_plan_is_read_only_and_needs_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'a')
            write(source / 'kit/b.txt', b'b')
            inventory = run('inventory', '--source', str(source), '--target', str(target), '--root', 'kit')
            self.assertEqual(inventory.returncode, 0, inventory.stdout + inventory.stderr)
            payload = json.loads(inventory.stdout)
            self.assertEqual(payload['source_file_count'], 2)
            self.assertFalse(payload['target']['exists'])
            self.assertFalse(target.exists())
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                       '--profile', 'core', '--operation', 'install')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            payload = json.loads(plan.stdout)
            self.assertEqual(payload['status'], 'needs_decision')
            self.assertFalse(payload['applyable'])
            self.assertEqual(payload['source_file_count'], 2)
            self.assertEqual(payload['base'], 'unknown')
            statuses = {row['path']: row['proposal']['status'] for row in payload['files']}
            self.assertEqual(statuses, {'kit/a.txt': 'new_from_release', 'kit/b.txt': 'new_from_release'})
            self.assertEqual(payload['state_dir_kind'], 'temporary')
            self.assertFalse(target.exists())
            again = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                        '--profile', 'core', '--operation', 'install')
            self.assertEqual(again.returncode, 2)
            self.assertNotEqual(payload['plan_id'], json.loads(again.stdout)['plan_id'])

    def test_receipt_update_keeps_target_bytes_and_writes_target_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'new upstream')
            write(source / 'kit/b.txt', b'b')
            write(target / 'kit/a.txt', b'old installed')
            write(target / 'kit/b.txt', b'b')
            receipt(target, 'a' * 40, {'kit/a.txt': b'old installed', 'kit/b.txt': b'b'})
            before = (target / 'kit/a.txt').read_bytes()
            result = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                         '--profile', 'core', '--operation', 'update', '--use-receipt')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['base'], 'receipt_unverified')
            self.assertEqual(payload['state_dir_kind'], 'target')
            self.assertTrue(Path(payload['plan_path']).is_relative_to(target / STATE / 'plans'))
            rows = {row['path']: row['proposal'] for row in payload['files']}
            self.assertEqual(rows['kit/a.txt']['status'], 'modified_upstream')
            self.assertEqual(rows['kit/b.txt']['status'], 'unchanged')
            decisions = {item['path']: item for item in payload['decisions_required']}
            self.assertEqual(set(decisions), {'kit/a.txt'})
            self.assertEqual((target / 'kit/a.txt').read_bytes(), before)

    def test_both_modified_requires_review_and_keeps_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'upstream different')
            write(target / 'kit/a.txt', b'local different')
            receipt(target, 'b' * 40, {'kit/a.txt': b'base'})
            result = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                         '--profile', 'core', '--operation', 'update', '--use-receipt')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            row = next(item for item in payload['files'] if item['path'] == 'kit/a.txt')
            self.assertEqual(row['proposal']['status'], 'both_modified')
            self.assertIn('edited', row['proposal']['choices'])
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'local different')

    def test_missing_receipt_treats_existing_target_as_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'source')
            write(target / 'kit/a.txt', b'target')
            result = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                         '--profile', 'core', '--operation', 'update')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            row = next(item for item in payload['files'] if item['path'] == 'kit/a.txt')
            self.assertEqual(row['proposal']['status'], 'same_path_collision')
            self.assertEqual(payload['state_dir_kind'], 'temporary')
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'target')

    def test_secret_and_traversal_fail_before_any_target_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/notes.txt', b'value: ' + b'ghp_' + b'abcdefghijklmnop' + b'\n')
            secret = run('plan', '--source', str(source), '--target', str(target), '--path', 'kit/notes.txt',
                         '--profile', 'core', '--operation', 'install')
            self.assertEqual(secret.returncode, 3, secret.stdout + secret.stderr)
            self.assertIn('sensitive_content', secret.stdout)
            self.assertFalse(target.exists())
            traversal = run('plan', '--source', str(source), '--target', str(target),
                            '--path', '../outside', '--profile', 'core', '--operation', 'install')
            self.assertEqual(traversal.returncode, 3, traversal.stdout + traversal.stderr)
            self.assertIn('invalid_path', traversal.stdout)
            self.assertFalse(target.exists())

    def test_local_policy_gate_rejects_invalid_source_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'a')
            for relative in (CANON, *POLICIES):
                write(source / relative, (ROOT / relative).read_bytes())
            policy = source / POLICIES[-1]
            policy.write_text(policy.read_text().replace(
                'self_path: ".agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml"',
                'self_path: ".agents/skills/harness-router/children/harness-core/assets/policies/wrong.yaml"'),
                encoding='utf-8')
            result = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                         '--profile', 'core', '--operation', 'install')
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['code'], 'SELF_PATH_MISMATCH')
            self.assertEqual(payload['policy_id'], 'component_docs')
            self.assertFalse(target.exists())

    def test_jsonl_events_have_monotonic_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'a')
            result = run('inventory', '--source', str(source), '--target', str(target),
                         '--root', 'kit', '--jsonl')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(events[0]['event'], 'run_started')
            self.assertEqual(events[-1]['event'], 'run_finished')
            self.assertEqual([event['sequence'] for event in events], list(range(1, len(events) + 1)))
            self.assertEqual(len({event['run_id'] for event in events}), 1)


@unittest.skipUnless(shutil.which('git'), 'git unavailable')
class HarnessTransferGitTest(unittest.TestCase):
    def fixture(self, base: Path) -> tuple[Path, Path, str]:
        work, bare = base / 'work', base / 'store.git'
        work.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(['git', '-C', str(work), *args], check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).stdout.decode().strip()

        git('init')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        write(work / 'kit/a.txt', b'git content\n')
        git('add', 'kit/a.txt')
        git('commit', '-m', 'fixture')
        commit = git('rev-parse', 'HEAD')
        subprocess.run(['git', 'clone', '--bare', str(work), str(bare)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return work, bare, commit

    def test_git_plan_reads_pinned_commit_without_checkout_or_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, commit = self.fixture(root)
            write(work / 'kit/a.txt', b'uncommitted change')
            target = root / 'target'
            result = run('plan', '--source-kind', 'git', '--repo', str(bare), '--commit', commit,
                         '--target', str(target), '--root', 'kit', '--profile', 'developer',
                         '--operation', 'install')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['source_commit_sha'], commit)
            self.assertEqual(payload['source_kind'], 'local_bare_git')
            self.assertFalse(payload['applyable'])
            self.assertFalse(target.exists())
            self.assertEqual((work / 'kit/a.txt').read_bytes(), b'uncommitted change')

    def test_fetch_into_cache_then_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, commit = self.fixture(root)
            branch = subprocess.run(['git', '-C', str(work), 'rev-parse', '--abbrev-ref', 'HEAD'],
                                    check=True, stdout=subprocess.PIPE).stdout.decode().strip()
            cache = root / 'cache.git'
            fetched = run('fetch', '--url', str(bare), '--cache', str(cache), '--ref', branch,
                          '--allow-local')
            self.assertEqual(fetched.returncode, 0, fetched.stdout + fetched.stderr)
            payload = json.loads(fetched.stdout)
            self.assertEqual(payload['status'], 'fetched')
            self.assertEqual(payload['commit'], commit)
            self.assertEqual(payload['release_trust'], 'not_verified')
            ref = subprocess.run(['git', '--git-dir', str(cache), 'rev-parse', 'refs/harness/source'],
                                 check=True, stdout=subprocess.PIPE).stdout.decode().strip()
            self.assertEqual(ref, commit)
            target = root / 'target'
            plan = run('plan', '--source-kind', 'git', '--repo', str(cache), '--commit', commit,
                       '--target', str(target), '--root', 'kit', '--profile', 'core',
                       '--operation', 'install')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            self.assertFalse(target.exists())

    def test_fetch_rejects_embedded_credentials_and_local_path_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, _ = self.fixture(root)
            branch = subprocess.run(['git', '-C', str(work), 'rev-parse', '--abbrev-ref', 'HEAD'],
                                    check=True, stdout=subprocess.PIPE).stdout.decode().strip()
            credentials = run('fetch', '--url', 'https://user:password@example.invalid/repo.git',
                              '--cache', str(root / 'cache.git'), '--ref', 'main')
            self.assertEqual(credentials.returncode, 3, credentials.stdout + credentials.stderr)
            self.assertIn('credentials', credentials.stdout)
            self.assertFalse((root / 'cache.git').exists())
            local = run('fetch', '--url', str(bare), '--cache', str(root / 'cache.git'), '--ref', branch)
            self.assertEqual(local.returncode, 3, local.stdout + local.stderr)
            self.assertFalse((root / 'cache.git').exists())

    def test_candidate_executables_are_never_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, _ = self.fixture(root)
            marker = root / 'executed'
            script = work / 'kit/run.sh'
            script.write_text(f'#!/bin/sh\ntouch {marker}\n', encoding='utf-8')
            subprocess.run(['git', '-C', str(work), 'add', 'kit/run.sh'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['git', '-C', str(work), 'update-index', '--chmod=+x', 'kit/run.sh'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['git', '-C', str(work), 'commit', '-m', 'candidate'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            commit = subprocess.run(['git', '-C', str(work), 'rev-parse', 'HEAD'], check=True,
                                    stdout=subprocess.PIPE).stdout.decode().strip()
            subprocess.run(['git', '--git-dir', str(bare), 'fetch', str(work), '+refs/heads/*:refs/heads/*'],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            target = root / 'target'
            result = run('plan', '--source-kind', 'git', '--repo', str(bare), '--commit', commit,
                         '--target', str(target), '--root', 'kit', '--profile', 'core',
                         '--operation', 'install')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse(target.exists())

    def test_release_manifest_is_checked_against_selected_blobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, bare, commit = self.fixture(root)
            content = b'git content\n'
            manifest = {'schema_version': 1, 'kind': 'harness-release-manifest',
                        'source': {'commit': commit},
                        'files': [{'path': 'kit/a.txt', 'mode': '100644', 'size': len(content),
                                   'sha256': digest(content)}],
                        'excluded': []}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            target = root / 'target'
            command = ['plan', '--source-kind', 'git', '--repo', str(bare), '--commit', commit,
                       '--target', str(target), '--root', 'kit', '--profile', 'core',
                       '--operation', 'install', '--release-manifest', str(path)]
            result = run(*command)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            check = next(item for item in json.loads(result.stdout)['checks'] if item['id'] == 'release_manifest')
            self.assertEqual(check['status'], 'passed')
            manifest['files'][0]['sha256'] = '0' * 64
            path.write_text(json.dumps(manifest), encoding='utf-8')
            tampered = run(*command)
            self.assertEqual(tampered.returncode, 3, tampered.stdout + tampered.stderr)
            self.assertIn('release manifest content differs', tampered.stdout)
            self.assertFalse(target.exists())

    def test_git_base_commit_is_not_treated_as_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work, bare, commit = self.fixture(root)
            (work / 'kit/a.txt').write_bytes(b'second\n')
            subprocess.run(['git', '-C', str(work), 'commit', '-am', 'second'], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            second = subprocess.run(['git', '-C', str(work), 'rev-parse', 'HEAD'], check=True,
                                    stdout=subprocess.PIPE).stdout.decode().strip()
            subprocess.run(['git', '--git-dir', str(bare), 'fetch', str(work), '+refs/heads/*:refs/heads/*'],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            target = root / 'target'
            write(target / 'kit/a.txt', b'git content\n')
            result = run('plan', '--source-kind', 'git', '--repo', str(bare), '--commit', second,
                         '--base-commit', commit, '--target', str(target), '--root', 'kit',
                         '--profile', 'developer', '--operation', 'update')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['base'], 'historical_commit_unverified')
            row = next(item for item in payload['files'] if item['path'] == 'kit/a.txt')
            self.assertEqual(row['proposal']['status'], 'modified_upstream')
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'git content\n')


WIZARD = Path(__file__).resolve().parents[1] / 'scripts/harness_wizard.py'
REPO_ROOT = Path(__file__).resolve().parents[6]


class HarnessWizardTest(unittest.TestCase):
    def test_non_interactive_wizard_builds_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'a')
            result = subprocess.run([sys.executable, str(WIZARD), '--non-interactive', '--source-kind', 'local',
                                     '--source', str(source), '--target', str(target), '--root', 'kit',
                                     '--profile', 'core', '--operation', 'install'],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'needs_decision')
            self.assertFalse(payload['applyable'])
            self.assertFalse(target.exists())

    def test_non_interactive_wizard_requires_choices(self):
        result = subprocess.run([sys.executable, str(WIZARD), '--non-interactive', '--source-kind', 'local'],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn('missing required choices', result.stdout)


class HarnessTransferProfileTest(unittest.TestCase):
    def test_plan_can_select_profile_paths_without_explicit_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts = {}
            for profile in ('core', 'developer', 'project'):
                target = root / profile
                result = run('plan', '--source', str(REPO_ROOT), '--target', str(target),
                             '--profile', profile, '--operation', 'install',
                             '--state-dir', str(root / ('state-' + profile)))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload['profile_selection'], 'profile_manifest')
                self.assertIn('.agents', payload['profile_roots'])
                self.assertGreater(len(payload['files']), 100)
                checks = {item['id']: item for item in payload['checks']}
                self.assertEqual(checks['profile_manifest']['status'], 'passed')
                counts[profile] = len(payload['files'])
            self.assertLess(counts['core'], counts['developer'])
            self.assertGreaterEqual(counts['project'], counts['developer'])


class HarnessTransferApproveTest(unittest.TestCase):
    def plan(self, root: Path) -> tuple[Path, Path, Path, dict]:
        source, target = root / 'source', root / 'target'
        write(source / 'kit/a.txt', b'a')
        result = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                     '--profile', 'core', '--operation', 'install')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        return source, target, Path(payload['plan_path']), payload

    def decisions(self, root: Path, choices: dict) -> Path:
        path = root / 'decisions.json'
        path.write_text(json.dumps({'schema_version': 1, 'decisions': choices}), encoding='utf-8')
        return path

    def test_approve_freezes_plan_and_does_not_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, target, plan_path, payload = self.plan(root)
            decisions = self.decisions(root, {'kit/a.txt': 'add'})
            result = run('approve', '--plan', str(plan_path), '--decisions', str(decisions))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            approved = json.loads(result.stdout)
            self.assertEqual(approved['status'], 'approved')
            self.assertFalse(approved['applyable'])
            self.assertTrue(Path(approved['approved_path']).is_file())
            self.assertFalse(target.exists())
            payload = json.loads(result.stdout)
            self.assertEqual(payload['decisions'], {'kit/a.txt': 'add'})

    def test_approve_requires_exact_decisions_and_valid_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, plan_path, _ = self.plan(root)
            missing = self.decisions(root, {})
            result = run('approve', '--plan', str(plan_path), '--decisions', str(missing))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            invalid = self.decisions(root, {'kit/a.txt': 'delete'})
            result = run('approve', '--plan', str(plan_path), '--decisions', str(invalid))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            extra = self.decisions(root, {'kit/a.txt': 'add', 'kit/other.txt': 'add'})
            result = run('approve', '--plan', str(plan_path), '--decisions', str(extra))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_approve_rejects_stale_target_source_and_expired_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target, plan_path, _ = self.plan(root)
            decisions = self.decisions(root, {'kit/a.txt': 'add'})
            write(target / 'kit/a.txt', b'created after plan')
            stale = run('approve', '--plan', str(plan_path), '--decisions', str(decisions))
            self.assertEqual(stale.returncode, 4, stale.stdout + stale.stderr)
            self.assertEqual(json.loads(stale.stdout)['status'], 'stale_plan')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _, plan_path, _ = self.plan(root)
            decisions = self.decisions(root, {'kit/a.txt': 'add'})
            write(source / 'kit/a.txt', b'changed after plan')
            stale = run('approve', '--plan', str(plan_path), '--decisions', str(decisions))
            self.assertEqual(stale.returncode, 4, stale.stdout + stale.stderr)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, plan_path, _ = self.plan(root)
            decisions = self.decisions(root, {'kit/a.txt': 'add'})
            plan = json.loads(plan_path.read_text(encoding='utf-8'))
            plan['expires_at'] = '2000-01-01T00:00:00Z'
            plan_path.write_text(json.dumps(plan), encoding='utf-8')
            expired = run('approve', '--plan', str(plan_path), '--decisions', str(decisions))
            self.assertEqual(expired.returncode, 4, expired.stdout + expired.stderr)


class HarnessTransferApplyTest(unittest.TestCase):
    def test_apply_replaces_one_file_and_updates_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'new')
            write(source / 'kit/b.txt', b'b')
            write(target / 'kit/a.txt', b'old')
            write(target / 'kit/b.txt', b'b')
            receipt(target, 'd' * 40, {'kit/a.txt': b'old', 'kit/b.txt': b'b'})
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                       '--profile', 'core', '--operation', 'update', '--use-receipt')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            plan_payload = json.loads(plan.stdout)
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1, 'decisions': {'kit/a.txt': 'replace'}}),
                                 encoding='utf-8')
            approved = run('approve', '--plan', plan_payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            approved_path = json.loads(approved.stdout)['approved_path']
            state = target / '.doc/web/state/transfer'
            result = run('apply', '--plan', plan_payload['plan_path'], '--approved', approved_path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'committed')
            self.assertIn('kit/a.txt', payload['applied'])
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'new')
            self.assertEqual((target / 'kit/b.txt').read_bytes(), b'b')
            receipt_data = json.loads((state / 'receipt.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt_data['files']['kit/a.txt']['installed_hash'], digest(b'new'))
            self.assertEqual(receipt_data['files']['kit/b.txt']['installed_hash'], digest(b'b'))

    def test_apply_refuses_unimplemented_merge_paths_before_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / '.codex/config.toml', b'# source\n')
            (target / '.codex').mkdir(parents=True)
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', '.codex',
                       '--profile', 'core', '--operation', 'update')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            plan_payload = json.loads(plan.stdout)
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1,
                                             'decisions': {'.codex/config.toml': 'add'}}), encoding='utf-8')
            approved = run('approve', '--plan', plan_payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            result = run('apply', '--plan', plan_payload['plan_path'],
                         '--approved', json.loads(approved.stdout)['approved_path'],
                         '--state-dir', str(root / 'state'))
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn('merge_not_implemented', result.stdout)
            self.assertFalse((target / '.codex/config.toml').exists())

    def test_apply_merges_mcp_and_agents_structurally(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
        from transfer_merge import merge_agents
        block = ('<!-- BEGIN HARNESS BOOTSTRAP: generated; edit .cursor/rules -->\n'
                 'new block\n<!-- END HARNESS BOOTSTRAP -->\n')
        target_agents = ('# Target local\n\n'
                         '<!-- BEGIN HARNESS BOOTSTRAP: generated; edit .cursor/rules -->\n'
                         'old block\n<!-- END HARNESS BOOTSTRAP -->\n'
                         'local tail\n')
        merged_agents, report = merge_agents(target_agents.encode(), ('# Source\n\n' + block).encode())
        agents = merged_agents.decode()
        self.assertEqual(report['mode'], 'replace_block')
        self.assertIn('# Target local', agents)
        self.assertIn('local tail', agents)
        self.assertIn('new block', agents)
        self.assertNotIn('old block', agents)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source_mcp = {'mcpServers': {
                'shared': {'command': 'source', 'args': ['source'], 'disabled': False},
                'fresh': {'command': 'fresh', 'args': []},
            }}
            target_mcp = {'mcpServers': {
                'shared': {'command': 'target', 'args': ['target']},
                'local': {'command': 'local', 'args': []},
            }}
            write(source / '.cursor/mcp.json', json.dumps(source_mcp).encode())
            write(target / '.cursor/mcp.json', json.dumps(target_mcp).encode())
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', '.cursor',
                       '--profile', 'core', '--operation', 'update')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            plan_payload = json.loads(plan.stdout)
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1, 'decisions': {
                '.cursor/mcp.json': 'adopt'}}), encoding='utf-8')
            approved = run('approve', '--plan', plan_payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            result = run('apply', '--plan', plan_payload['plan_path'],
                         '--approved', json.loads(approved.stdout)['approved_path'])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            merged_mcp = json.loads((target / '.cursor/mcp.json').read_text(encoding='utf-8'))
            self.assertEqual(merged_mcp['mcpServers']['shared'], target_mcp['mcpServers']['shared'])
            self.assertTrue(merged_mcp['mcpServers']['fresh']['disabled'])
            self.assertIn('shared__upstream', merged_mcp['mcpServers'])
            self.assertTrue(merged_mcp['mcpServers']['shared__upstream']['disabled'])


    def test_repeated_update_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'new')
            write(target / 'kit/a.txt', b'old')
            receipt(target, 'f' * 40, {'kit/a.txt': b'old'})
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                       '--profile', 'core', '--operation', 'update', '--use-receipt')
            payload = json.loads(plan.stdout)
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1, 'decisions': {'kit/a.txt': 'replace'}}),
                                 encoding='utf-8')
            approved = run('approve', '--plan', payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            applied = run('apply', '--plan', payload['plan_path'],
                          '--approved', json.loads(approved.stdout)['approved_path'])
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            again = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                        '--profile', 'core', '--operation', 'update', '--use-receipt')
            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            second = json.loads(again.stdout)
            self.assertEqual(second['status'], 'preview_ready')
            self.assertEqual(second['decisions_required'], [])
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'new')

    def test_apply_render_reports_committed_view_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            write(source / 'kit/a.txt', b'new')
            write(target / 'kit/a.txt', b'old')
            receipt(target, 'e' * 40, {'kit/a.txt': b'old'})
            plan = run('plan', '--source', str(source), '--target', str(target), '--root', 'kit',
                       '--profile', 'core', '--operation', 'update', '--use-receipt')
            self.assertEqual(plan.returncode, 2, plan.stdout + plan.stderr)
            plan_payload = json.loads(plan.stdout)
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1, 'decisions': {'kit/a.txt': 'replace'}}),
                                 encoding='utf-8')
            approved = run('approve', '--plan', plan_payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
            result = run('apply', '--plan', plan_payload['plan_path'],
                         '--approved', json.loads(approved.stdout)['approved_path'], '--render')
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'committed_render_failed')
            self.assertTrue(payload['committed'])
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'new')

    def test_rollback_restores_replaced_file_and_finalizes(self):
        import sqlite3
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
        from transfer_diff import FileState
        from transfer_journal import TransferJournal
        from transfer_prepare import prepare_replacement
        from transfer_process_lock import ProcessLock
        from transfer_replace import replace_prepared
        from transfer_tree import capture_tree

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            write(target / 'kit/a.txt', b'old')
            state = target / '.doc/web/state/transfer'
            state.mkdir(parents=True)
            lock = ProcessLock(state / 'transfer.lock')
            lock.acquire()
            try:
                journal = TransferJournal(sqlite3.connect(state / 'transfer.sqlite3'))
                lease = journal.acquire()
                backup = state / 'backups' / lease.run_id
                backup.mkdir(parents=True)
                baseline = capture_tree(target, ['kit'], max_file_bytes=8 * 1024 * 1024)
                journal.save_tree_baseline(lease, baseline)
                journal.transition(lease, 'backed_up')
                journal.transition(lease, 'replacing')
                before = FileState(digest(b'old'), 0o644)
                after = FileState(digest(b'new'), 0o644)
                prepare_replacement(journal, lease, lock, target, backup, 'kit/a.txt', before, after,
                                    max_file_bytes=8 * 1024 * 1024)
                replace_prepared(journal, lease, lock, target, backup, 'kit/a.txt', b'new',
                                 max_file_bytes=8 * 1024 * 1024)
                journal.transition(lease, 'validating')
            finally:
                lock.release()
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'new')
            result = run('rollback', '--target', str(target))
            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'old')
            self.assertEqual(json.loads(result.stdout)['status'], 'rolled_back')


class HarnessTransferAdoptTest(unittest.TestCase):
    def test_adopt_preview_is_read_only_and_keeps_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            write(target / 'kit/a.txt', b'local')
            write(target / '.doc/.rebase-kit.json', b'{"status": "pending", "profile": "Core", "mode": "migrate"}')
            result = run('adopt', '--target', str(target), '--root', 'kit', '--profile', 'core')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'needs_decision')
            self.assertEqual(payload['kit_marker']['status'], 'pending')
            self.assertEqual(payload['files'][0]['proposal']['status'], 'local_adopt_candidate')
            self.assertTrue(Path(payload['plan_path']).is_file())
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'local')
            decisions = root / 'decisions.json'
            decisions.write_text(json.dumps({'schema_version': 1, 'decisions': {'kit/a.txt': 'adopt'}}),
                                 encoding='utf-8')
            committed = run('adopt', '--plan', payload['plan_path'], '--decisions', str(decisions))
            self.assertEqual(committed.returncode, 0, committed.stdout + committed.stderr)
            self.assertEqual(json.loads(committed.stdout)['status'], 'adopted')
            receipt_data = json.loads((target / '.doc/web/state/transfer/receipt.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt_data['files']['kit/a.txt']['decision'], 'adopted')
            self.assertEqual((target / 'kit/a.txt').read_bytes(), b'local')


class HarnessTransferVerifyTest(unittest.TestCase):
    def test_verify_reports_hash_changes_and_requires_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'target'
            write(target / 'kit/a.txt', b'a')
            receipt(target, 'c' * 40, {'kit/a.txt': b'a'})
            passed = run('verify', '--target', str(target), '--root', 'kit')
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            payload = json.loads(passed.stdout)
            self.assertEqual(payload['status'], 'passed')
            self.assertEqual(payload['checked_files'], 1)
            write(target / 'kit/b.txt', b'extra')
            scoped = run('verify', '--target', str(target), '--root', 'kit')
            self.assertEqual(scoped.returncode, 0, scoped.stdout + scoped.stderr)
            full = run('verify', '--target', str(target), '--root', 'kit', '--full')
            self.assertEqual(full.returncode, 1, full.stdout + full.stderr)
            self.assertEqual(json.loads(full.stdout)['unexpected'], ['kit/b.txt'])
            (target / 'kit/a.txt').write_bytes(b'changed')
            failed = run('verify', '--target', str(target), '--root', 'kit')
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
            self.assertEqual(json.loads(failed.stdout)['hash_changed'], ['kit/a.txt'])
            empty = root / 'empty'
            empty.mkdir()
            missing = run('verify', '--target', str(empty), '--root', 'kit')
            self.assertEqual(missing.returncode, 3, missing.stdout + missing.stderr)
            self.assertIn('receipt', missing.stdout)


if __name__ == '__main__':
    unittest.main()
