import sys
import os
import tempfile
import unittest
import runpy
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from canon_paths import parse_policy, read_policy, load_preliminary_policies, load_preliminary_policy_bundle, PolicyError


class CanonPolicyTest(unittest.TestCase):
    def test_preliminary_loader_rejects_missing_tampered_and_weakened_policy(self):
        root = Path(__file__).resolve().parents[6]
        rels = ['.doc/harnes/state/canon-paths.yaml',
                '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml']
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in rels:
                destination = fixture / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, destination)
            bundle = load_preliminary_policies(fixture)
            self.assertTrue(bundle['skill_format']['rules']['SF01']['enabled'])
            with self.assertRaises(TypeError):
                bundle['skill_format']['rules']['SF01']['enabled'] = False
            target = fixture / rels[1]
            original = target.read_text(encoding='utf-8')
            for changed, code in [(original.replace('enabled: true', 'enabled: false', 1), 'TRUSTED_GATE_WEAKENING'),
                                  (original.replace('owner: "harness-core"', 'owner: "other"'), 'POLICY_SCHEMA_ERROR'),
                                  (original.replace('self_path: "', 'self_path: "wrong/', 1), 'SELF_PATH_MISMATCH'),
                                  (original.replace('schema_version: 1', 'schema_version: 1\nschema_version: 1'), 'POLICY_SCHEMA_ERROR')]:
                target.write_text(changed, encoding='utf-8')
                with self.subTest(code=code), self.assertRaises(PolicyError) as raised:
                    load_preliminary_policies(fixture)
                self.assertEqual(raised.exception.code, code)
            target.unlink()
            with self.assertRaises(PolicyError) as raised:
                load_preliminary_policies(fixture)
            self.assertEqual(raised.exception.code, 'POLICY_MISSING')
            self.assertEqual(raised.exception.relative_path, rels[1])

    def test_preliminary_policy_files_match_existing_validator_constants(self):
        root = Path(__file__).resolve().parents[6]
        canon = read_policy(root / '.doc/harnes/state/canon-paths.yaml')
        policies = canon['policies']
        self.assertEqual(set(policies), {'skill_format', 'component_docs'})
        loaded = {}
        for name, declaration in policies.items():
            self.assertEqual(declaration['required_profiles'], ['core', 'developer', 'project'])
            data = read_policy(root / declaration['path'])
            self.assertEqual(data['schema_version'], 1)
            self.assertEqual(data['policy_id'], name)
            self.assertEqual(data['self_path'], declaration['path'])
            self.assertEqual(data['owner'], 'harness-core')
            self.assertTrue(all(rule['enabled'] and rule['severity'] == 'error' for rule in data['rules'].values()))
            loaded[name] = data['rules']
        skills = runpy.run_path(str(root / '.agents/skills/harness-router/children/improvement/scripts/validate_skills.py'))
        script_docs = runpy.run_path(str(root / '.agents/skills/harness-router/children/doc-script/scripts/doc_script.py'))
        readme_docs = runpy.run_path(str(root / '.agents/skills/harness-router/children/doc-skill/scripts/doc_skill.py'))
        skill_policy = loaded['skill_format']
        self.assertEqual(set(skill_policy['SF01']['required_files']), {'SKILL.md', 'README.md', 'skill.json'})
        self.assertEqual(set(skill_policy['SF02']['allowed_directories']), skills['ALLOWED_DIRS'])
        self.assertEqual(set(skill_policy['SF02']['forbidden_directories']), skills['FORBIDDEN_DIRS'])
        self.assertEqual(set(skill_policy['SF02']['allowed_frontmatter']), skills['ALLOWED_FRONTMATTER'])
        self.assertEqual(skill_policy['SF02']['name_pattern'], skills['NAME_RE'].pattern)
        self.assertEqual(set(skill_policy['SF03']['resource_keys']), skills['RESOURCE_KEYS'])
        self.assertEqual(loaded['component_docs']['CD02']['required_sections'], script_docs['SECTIONS'])
        self.assertEqual(loaded['component_docs']['CD01']['forbidden_literals'], readme_docs['DRAFT_PATTERNS'])
        self.assertEqual(canon['local_extension']['path'], '.doc/harnes/state/canon-paths.local.yaml')
        self.assertEqual(canon['local_extension']['allowed_sections'], ['custom_components'])

    def test_nested_types_and_comments(self):
        policy = parse_policy('schema_version: 1 # comment\nmanifest:\n  path: "a/#b" # suffix\n'
                              '  profiles:\n    - "core"\n    - "developer"\nflags:\n  enabled: true\n')
        self.assertEqual(policy['schema_version'], 1)
        self.assertEqual(policy['manifest']['path'], 'a/#b')
        self.assertEqual(policy['manifest']['profiles'], ['core', 'developer'])
        self.assertIs(policy['flags']['enabled'], True)
        nested = parse_policy('rules:\n  - name: "first"\n    enabled: true\n  - name: "second"\n    count: 2\n')
        self.assertEqual(nested['rules'], [{'name': 'first', 'enabled': True}, {'name': 'second', 'count': 2}])

    def test_invalid_and_ambiguous_yaml_is_rejected(self):
        for text in ('a: "1"\na: "2"\n', 'a: &x "value"\n', 'a: null\n',
                     'a: ["x"]\n', 'a:\n   x: "bad"\n', 'a:\n  - "x"\n  key: "y"\n',
                     'a: "unterminated\n', 'a: "\\n"\n', 'a:\n  b: "x"\n    c: "y"\n',
                     'a:\n  - name: "x"\n    name: "y"\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_policy(text)

    def test_distribution_references_existing_keys_and_enums(self):
        root = Path(__file__).resolve().parents[6]
        rels = ['.doc/harnes/state/canon-paths.yaml',
                '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml']
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            for relative in rels:
                destination = fixture / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, destination)
            canon = fixture / rels[0]
            bundle = load_preliminary_policy_bundle(fixture)
            self.assertEqual(len(bundle['distribution']), 19)
            original = canon.read_text(encoding='utf-8')
            cases = [
                (original.replace('ref: "layout.temp_dir"', 'ref: "layout.unknown"'), 'distribution.ref'),
                (original.replace('role: "policy"', 'role: "bogus"'), 'distribution.role'),
                (original.replace('ref: "layout.temp_dir"', 'ref: "layout.tools_inventory"'), 'distribution.ref'),
                (original.replace('copy_policy: "copy"', 'copy_policy: "overwrite"', 1), 'distribution.copy_policy'),
            ]
            for changed, field in cases:
                canon.write_text(changed, encoding='utf-8')
                with self.subTest(field=field), self.assertRaises(PolicyError) as raised:
                    load_preliminary_policy_bundle(fixture)
                self.assertEqual(raised.exception.code, 'POLICY_SCHEMA_ERROR')
                self.assertEqual(raised.exception.field, field)

    def test_current_canonical_policy_is_readable(self):
        root = Path(__file__).resolve().parents[6]
        policy = read_policy(root / '.doc/harnes/state/canon-paths.yaml')
        self.assertEqual(policy['canonical_roots']['path_manifest'], '.doc/harnes/state/canon-paths.yaml')
        self.assertIn('mcp_disabled', policy['layout']['docs'])

    def test_policy_changed_during_read_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.yaml'
            path.write_text('name: "first"\n', encoding='utf-8')
            original = os.read
            changed = False
            def racing_read(fd, size):
                nonlocal changed
                data = original(fd, size)
                if data and not changed:
                    changed = True
                    path.write_text('name: "changed-value"\n', encoding='utf-8')
                return data
            with patch('canon_paths.os.read', side_effect=racing_read):
                with self.assertRaises(ValueError):
                    read_policy(path)

    def test_hardlink_alias_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / 'policy.yaml'
            policy.write_text('name: "valid"\n', encoding='utf-8')
            try:
                os.link(policy, root / 'alias.yaml')
            except (OSError, NotImplementedError):
                self.skipTest('hardlinks unavailable')
            with self.assertRaises(ValueError):
                read_policy(policy)

    def test_policy_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'policy.yaml'
            path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
            with self.assertRaises(ValueError):
                read_policy(path)


if __name__ == '__main__':
    unittest.main()
