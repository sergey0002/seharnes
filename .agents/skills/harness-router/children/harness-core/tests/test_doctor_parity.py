import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import harness_cli


class DoctorParityTest(unittest.TestCase):
    def test_strict_selected_structure_runs_fail_on_junk_and_reports_scope(self):
        commands = []
        root = Path(__file__).resolve().parents[6]
        output = io.StringIO()
        def run(command, cwd, timeout):
            commands.append(command)
            return 1, json.dumps({'status': 'failed', 'errors': [], 'warnings': [],
                                  'junk': [{'path': 'example.tmp', 'reason': 'temporary'}]})
        args = argparse.Namespace(root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure')
        with patch.object(harness_cli, '_run', side_effect=run), contextlib.redirect_stdout(output):
            self.assertEqual(harness_cli.cmd_doctor(args), 1)
        self.assertEqual(len(commands), 1)
        self.assertIn('--junk', commands[0])
        self.assertIn('--fail-on-junk', commands[0])
        self.assertIn('--require-policy', commands[0])
        self.assertIn('--json', commands[0])
        self.assertIn('JUNK example.tmp: temporary', output.getvalue())
        report = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(report['scope'], 'selected_gates')
        self.assertEqual(report['failed_gates'], ['structure'])
        self.assertEqual(report['gate_details']['structure']['findings']['junk'][0]['path'], 'example.tmp')

    def test_invalid_structure_json_cannot_report_success(self):
        root = Path(__file__).resolve().parents[6]
        args = argparse.Namespace(root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure')
        with patch.object(harness_cli, '_run', return_value=(0, 'not json')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(args), 1)
        contradictory = json.dumps({'status': 'passed', 'errors': [], 'warnings': [],
                                    'junk': [{'path': 'x.tmp', 'reason': 'temporary'}]})
        with patch.object(harness_cli, '_run', return_value=(0, contradictory)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(args), 1)

    def test_unknown_and_incompatible_gate_selection_fail(self):
        root = Path(__file__).resolve().parents[6]
        for checks, mode, skip in [('missing', 'standard', False), ('rules', 'strict', False),
                                   ('structure', 'standard', True), ('', 'standard', False)]:
            with self.subTest(checks=checks, mode=mode, skip=skip), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(
                    root=str(root), junk=False, skip_gates=skip, mode=mode, checks=checks)), 2)

    def test_strict_skill_check_passes_policy_root(self):
        root = Path(__file__).resolve().parents[6]
        commands = []
        def run(command, cwd, timeout):
            commands.append(command)
            return 0, json.dumps({'status': 'passed', 'errors': [], 'warnings': [], 'junk': []})
        with patch.object(harness_cli, '_run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(
                root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure,skills-format')), 0)
        command = next(item for item in commands if item[1].endswith('validate_skills.py'))
        self.assertIn('--policy-root', command)
        self.assertEqual(command[-1], str(root))

    def test_strict_script_docs_check_passes_policy_root(self):
        root = Path(__file__).resolve().parents[6]
        commands = []
        def run(command, cwd, timeout):
            commands.append(command)
            return 0, json.dumps({'status': 'passed', 'errors': [], 'warnings': [], 'junk': []})
        with patch.object(harness_cli, '_run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(
                root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure,docs-scripts')), 0)
        command = next(item for item in commands if item[1].endswith('doc_script.py'))
        self.assertIn('--policy-root', command)
        self.assertEqual(command[-1], str(root))

    def test_strict_readme_docs_check_passes_policy_root(self):
        root = Path(__file__).resolve().parents[6]
        commands = []
        def run(command, cwd, timeout):
            commands.append(command)
            return 0, json.dumps({'status': 'passed', 'errors': [], 'warnings': [], 'junk': []})
        with patch.object(harness_cli, '_run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(
                root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure,docs-skills')), 0)
        command = next(item for item in commands if item[1].endswith('doc_skill.py'))
        self.assertIn('--policy-root', command)
        self.assertEqual(command[-1], str(root))

    def test_strict_mcp_docs_check_passes_policy_root(self):
        root = Path(__file__).resolve().parents[6]
        commands = []
        def run(command, cwd, timeout):
            commands.append(command)
            return 0, json.dumps({'status': 'passed', 'errors': [], 'warnings': [], 'junk': []})
        with patch.object(harness_cli, '_run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(
                root=str(root), junk=False, skip_gates=False, mode='strict', checks='structure,docs-mcp')), 0)
        command = next(item for item in commands if item[1].endswith('doc_mcp.py'))
        self.assertIn('--policy-root', command)
        self.assertEqual(command[-1], str(root))

    def test_doctor_checks_real_views_and_mcp(self):
        commands = []

        def run(command, cwd, timeout):
            commands.append(command)
            return 0, "{}"

        root = Path(__file__).resolve().parents[6]
        with patch.object(harness_cli, "_run", side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(harness_cli.cmd_doctor(argparse.Namespace(root=str(root), junk=False, skip_gates=False)), 0)

        parity = next(c for c in commands if c[1].endswith("verify_parity.py"))
        self.assertIn(".qoder/skills", parity)
        self.assertNotIn(".codex/skills", parity)
        self.assertEqual(parity.count(".agents/skills"), 1)
        for view in (".codex/rules", ".kilo/rules", ".agents/rules", ".qoder/rules"):
            self.assertIn(view, parity)
        qwen = next(c for c in commands if c[1].endswith("generate-qwen-config.py"))
        self.assertIn("--check", qwen)
        mcp = next(c for c in commands if c[1].endswith("verify_mcp_views.py"))
        self.assertIn(".qwen/settings.json", mcp)
        self.assertIn(".codex/config.toml", mcp)


if __name__ == "__main__":
    unittest.main()
