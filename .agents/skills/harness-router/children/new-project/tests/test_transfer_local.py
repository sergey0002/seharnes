import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_local import selected_local_paths, validate_local_extension


class LocalPolicyTest(unittest.TestCase):
    def component(self, path='kit/custom'):
        return {'kind': 'skill', 'name': 'custom', 'path': path, 'owner': 'project',
                'docs_layout_key': 'layout.docs.script_skill'}

    def test_valid_scoped_components_select_descendants(self):
        policy = {'schema_version': 1, 'custom_components': [self.component()]}
        components = validate_local_extension(policy, ['kit/a.txt'], ['kit'])
        self.assertEqual(selected_local_paths(['kit/custom/README.md', 'kit/a.txt'], components),
                         ['kit/custom/README.md'])

    def test_escalations_and_collisions_rejected(self):
        entry = self.component()
        for policy, history, roots in [
            ({'schema_version': 1, 'custom_components': [entry], 'distribution': {}}, [], ['kit']),
            ({'schema_version': True, 'custom_components': [entry]}, [], ['kit']),
            ({'schema_version': 1, 'custom_components': [entry]}, ['kit/CUSTOM/file'], ['kit']),
            ({'schema_version': 1, 'custom_components': [self.component('../escape')]}, [], ['kit']),
            ({'schema_version': 1, 'custom_components': [entry, entry]}, [], ['kit']),
            ({'schema_version': 1, 'custom_components': [entry]}, [], ['other']),
        ]:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                validate_local_extension(policy, history, roots)


if __name__ == '__main__':
    unittest.main()
