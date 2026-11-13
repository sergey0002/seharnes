import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('doc_skill_test', Path(__file__).parents[1] / 'scripts/doc_skill.py')
DOC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOC)


class DocSkillPolicyTest(unittest.TestCase):
    def test_policy_additions_do_not_relax_builtin_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory)
            (skill / 'README.md').write_text('Заполнить: X\ncustom forbidden\n', encoding='utf-8')
            errors = DOC.audit_readme(skill, ('custom forbidden',))
            self.assertTrue(any('Заполнить:' in error for error in errors))
            self.assertTrue(any('custom forbidden' in error for error in errors))

    def test_cli_loads_policy_and_fails_closed_when_missing(self):
        source = Path(__file__).resolve().parents[6]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / '.agents/skills/example'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('---\nname: example\n---\n', encoding='utf-8')
            (skill / 'README.md').write_text('local marker\n', encoding='utf-8')
            def run():
                out = io.StringIO()
                with patch.multiple(DOC, ROOT=root, SKILLS_ROOT=root / '.agents/skills'), \
                     patch('sys.argv', ['doc_skill.py', '--skill', '.agents/skills/example', '--policy-root', str(root)]), \
                     contextlib.redirect_stderr(out):
                    code = DOC.main()
                return code, out.getvalue()
            self.assertEqual(run()[0], 1)
            relatives = ('.doc/harnes/state/canon-paths.yaml',
                         '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                         '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')
            for relative in relatives:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, destination)
            policy = root / relatives[-1]
            policy.write_text(policy.read_text(encoding='utf-8').replace('  CD02:', '      - "local marker"\n  CD02:'), encoding='utf-8')
            code, errors = run()
            self.assertEqual(code, 1)
            self.assertIn('local marker', errors)


if __name__ == '__main__':
    unittest.main()
