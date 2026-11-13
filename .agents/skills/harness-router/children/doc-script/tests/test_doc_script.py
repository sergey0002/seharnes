import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "doc_script", Path(__file__).parents[1] / "scripts" / "doc_script.py"
)
DOC_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOC_SCRIPT)


class DocScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / ".agents" / "skills"
        self.canon = self.root / ".cursor" / "scripts"
        self.core = self.skills / "harness-router" / "children" / "harness-core"
        for path in (self.skills, self.canon, self.core):
            path.mkdir(parents=True, exist_ok=True)
        (self.core / "SKILL.md").write_text("---\nname: harness-core\n---\n# harness-core\n", encoding="utf-8")

        self.patcher = patch.multiple(
            DOC_SCRIPT,
            ROOT=self.root,
            SKILLS_ROOT=self.skills,
            CANON_SCRIPTS=self.canon,
            HARNESS_CORE=self.core,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def create_skill(self, name: str, relative_path: str = "") -> Path:
        skill_dir = self.skills / relative_path / name if relative_path else self.skills / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")
        (skill_dir / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        (skill_dir / "skill.json").write_text("{}", encoding="utf-8")
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        return skill_dir

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["doc_script.py", *args]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = DOC_SCRIPT.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_policy_adds_sections_without_removing_trusted_requirements(self):
        skill = self.create_skill('policy-test')
        script = skill / 'scripts' / 'sample.py'
        script.write_text('print("hello")\n', encoding='utf-8')
        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)
        sections = [section for section in DOC_SCRIPT.SECTIONS if section != '## Суть']
        doc.write_text('<!-- meta\nstatus: actual\n-->\n' + ''.join(section + '\ntext\n' for section in sections), encoding='utf-8')
        errors = DOC_SCRIPT.audit(script, ('## Дополнительный раздел',))
        self.assertTrue(any('MISSING_SECTION' in error and '## Суть' in error for error in errors))
        self.assertTrue(any('MISSING_SECTION' in error and '## Дополнительный раздел' in error for error in errors))
        code, _, err = self.run_cli('--policy-root', str(self.root))
        self.assertEqual(code, 2)
        self.assertIn('--audit', err)
        code, _, err = self.run_cli('--audit', '--policy-root', str(self.root))
        self.assertEqual(code, 1)
        self.assertIn('POLICY_MISSING', err)
        source = Path(__file__).resolve().parents[6]
        relatives = ('.doc/harnes/state/canon-paths.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')
        for relative in relatives:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination)
        policy = self.root / relatives[-1]
        policy.write_text(policy.read_text(encoding='utf-8').replace('  CD03:', '      - "## Дополнительный раздел"\n  CD03:'), encoding='utf-8')
        code, _, err = self.run_cli('--audit', '--script', str(script.relative_to(self.root)), '--policy-root', str(self.root))
        self.assertEqual(code, 1)
        self.assertIn('## Дополнительный раздел', err)
        self.assertIn('## Суть', err)

    def test_ac02_different_extensions_and_nested_paths_do_not_conflict(self):
        skill = self.create_skill("ext-test")
        sh_script = skill / "scripts" / "run.sh"
        ps_script = skill / "scripts" / "run.ps1"
        sub_script = skill / "scripts" / "sub" / "run.sh"
        sub_script.parent.mkdir(parents=True, exist_ok=True)

        for s in (sh_script, ps_script, sub_script):
            s.write_text("#!/bin/bash\n", encoding="utf-8")

        sh_doc = DOC_SCRIPT.doc_path_for(sh_script)
        ps_doc = DOC_SCRIPT.doc_path_for(ps_script)
        sub_doc = DOC_SCRIPT.doc_path_for(sub_script)

        self.assertIsNotNone(sh_doc)
        self.assertIsNotNone(ps_doc)
        self.assertIsNotNone(sub_doc)

        self.assertEqual(sh_doc.name, "run.sh.md")
        self.assertEqual(ps_doc.name, "run.ps1.md")
        self.assertEqual(sub_doc.name, "run.sh.md")
        self.assertEqual(sub_doc.parent.name, "sub")

        # Distinct paths
        self.assertNotEqual(sh_doc, ps_doc)
        self.assertNotEqual(sh_doc, sub_doc)

    def test_ac04_overwrite_protection(self):
        skill = self.create_skill("sample-skill")
        script = skill / "scripts" / "deploy.sh"
        script.write_text("#!/bin/bash\necho 'deploy'\n", encoding="utf-8")

        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)
        custom_content = "# Custom verified document\n<!-- meta\nstatus: actual\n-->\n"
        doc.write_text(custom_content, encoding="utf-8")

        rel_script = script.relative_to(self.root).as_posix()

        # Attempt overwrite without --force
        code, out, err = self.run_cli("--script", rel_script)
        self.assertEqual(code, 1)
        self.assertIn("DOCUMENT_EXISTS", err)
        self.assertEqual(doc.read_text(encoding="utf-8"), custom_content)

        # Overwrite with --force
        code, out, err = self.run_cli("--script", rel_script, "--force")
        self.assertEqual(code, 0)
        self.assertNotEqual(doc.read_text(encoding="utf-8"), custom_content)
        self.assertIn("# Скрипт:", doc.read_text(encoding="utf-8"))

        # Overwrite with --overwrite flag
        doc.write_text(custom_content, encoding="utf-8")
        code, out, err = self.run_cli("--script", rel_script, "--overwrite")
        self.assertEqual(code, 0)
        self.assertNotEqual(doc.read_text(encoding="utf-8"), custom_content)

    def test_ac05_honest_unparsed_handling(self):
        skill = self.create_skill("honest-skill")

        # 1. Bash script with unparsed arguments ($1, shift)
        unparsed_sh = skill / "scripts" / "unparsed.sh"
        unparsed_sh.write_text("#!/bin/bash\necho $1\nshift\n", encoding="utf-8")
        doc_text_sh = DOC_SCRIPT.generate_doc(unparsed_sh)
        self.assertIn("Определить по коду", doc_text_sh)
        self.assertNotIn("Аргументов нет", doc_text_sh)

        # 2. Python script with dynamic exit
        dynamic_py = skill / "scripts" / "dynamic.py"
        dynamic_py.write_text(
            "import sys\n"
            "def main():\n    return 5\n"
            "if __name__ == '__main__':\n    sys.exit(main())\n",
            encoding="utf-8",
        )
        codes = DOC_SCRIPT.extract_exit_codes(dynamic_py)
        self.assertTrue(any(c.get("dynamic") for c in codes))
        self.assertFalse(any(c.get("code") == 0 and not c.get("dynamic") for c in codes))

        doc_text_py = DOC_SCRIPT.generate_doc(dynamic_py)
        self.assertIn("Динамический", doc_text_py)
        self.assertIn("Определить по коду", doc_text_py)

        # 3. Side effects verification when none matched
        pure_py = skill / "scripts" / "pure.py"
        pure_py.write_text("def add(x, y):\n    return x + y\n", encoding="utf-8")
        doc_text_pure = DOC_SCRIPT.generate_doc(pure_py)
        self.assertIn("Определить по коду", doc_text_pure)
        self.assertNotIn("Побочных эффектов не обнаружено", doc_text_pure)

    def test_ac06_powershell_parameter_extraction(self):
        skill = self.create_skill("ps-skill")
        synthetic_ps = skill / "scripts" / "test_ps.ps1"
        synthetic_ps.write_text(
            "[CmdletBinding()]\n"
            "param(\n"
            "    [Parameter(Mandatory = $true, Position = 0)]\n"
            "    [string]$Url,\n"
            "\n"
            "    [string]$OutputDir = '',\n"
            "\n"
            "    [string]$NamePrefix = 'yadisk',\n"
            "\n"
            "    [switch]$Force,\n"
            "\n"
            "    [switch]$Quiet,\n"
            "\n"
            "    [Alias('c', 'count_alias')]\n"
            "    [Parameter(Mandatory)]\n"
            "    [int]$Count = 42\n"
            ")\n"
            "exit 0\n",
            encoding="utf-8",
        )

        args = DOC_SCRIPT.parse_arguments(synthetic_ps)
        by_name = {a["name"]: a for a in args}

        # Verify -Url
        self.assertIn("-Url", by_name)
        self.assertEqual(by_name["-Url"]["type"], "string")
        self.assertEqual(by_name["-Url"]["required"], True)

        # Verify -OutputDir
        self.assertIn("-OutputDir", by_name)
        self.assertEqual(by_name["-OutputDir"]["type"], "string")
        self.assertEqual(by_name["-OutputDir"]["required"], False)
        self.assertEqual(by_name["-OutputDir"]["default"], "''")

        # Verify -NamePrefix
        self.assertIn("-NamePrefix", by_name)
        self.assertEqual(by_name["-NamePrefix"]["type"], "string")
        self.assertEqual(by_name["-NamePrefix"]["required"], False)
        self.assertEqual(by_name["-NamePrefix"]["default"], "'yadisk'")

        # Verify -Force
        self.assertIn("-Force", by_name)
        self.assertEqual(by_name["-Force"]["type"], "switch")
        self.assertEqual(by_name["-Force"]["required"], False)

        # Verify -Quiet
        self.assertIn("-Quiet", by_name)
        self.assertEqual(by_name["-Quiet"]["type"], "switch")
        self.assertEqual(by_name["-Quiet"]["required"], False)

        # Verify -Count with Alias
        self.assertIn("-Count", by_name)
        self.assertEqual(by_name["-Count"]["type"], "int")
        self.assertEqual(by_name["-Count"]["required"], True)
        self.assertEqual(by_name["-Count"]["default"], "42")
        self.assertIn("-c", by_name["-Count"]["alias"])

        # Also verify real repo script if accessible
        real_yadisk = (
            Path(__file__).parents[6]
            / ".agents"
            / "skills"
            / "yadisk-screenshot"
            / "scripts"
            / "yadisk-fetch.ps1"
        )
        if real_yadisk.is_file():
            real_args = DOC_SCRIPT.parse_arguments(real_yadisk)
            real_by_name = {a["name"]: a for a in real_args}
            self.assertEqual(real_by_name["-Url"]["required"], True)
            self.assertEqual(real_by_name["-Url"]["type"], "string")
            self.assertEqual(real_by_name["-OutputDir"]["default"], "''")
            self.assertEqual(real_by_name["-NamePrefix"]["default"], "'yadisk'")
            self.assertEqual(real_by_name["-Force"]["type"], "switch")
            self.assertEqual(real_by_name["-Force"]["required"], False)
            self.assertEqual(real_by_name["-Quiet"]["type"], "switch")
            self.assertEqual(real_by_name["-Quiet"]["required"], False)

    def test_ac07_python_argparse_extraction(self):
        skill = self.create_skill("py-skill")
        script = skill / "scripts" / "test_argparse.py"
        script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser(description='Test')\n"
            "parser.add_argument('path', help='path to file')\n"
            "parser.add_argument('opt_pos', nargs='?', default='default.txt')\n"
            "parser.add_argument('-s', '--script', help='script file')\n"
            "parser.add_argument('-f', '--force', action='store_true', help='force overwrite')\n"
            "parser.add_argument('--count', type=int, default=10, required=True)\n"
            "parser.add_argument('-v', action='store_true')\n"
            "parser.add_argument('--tags', nargs='+', default=[])\n",
            encoding="utf-8",
        )

        args = DOC_SCRIPT.parse_arguments(script)
        by_name = {a["name"]: a for a in args}

        # Positional required
        self.assertIn("path", by_name)
        self.assertEqual(by_name["path"]["required"], True)
        self.assertEqual(by_name["path"]["type"], "string")
        self.assertEqual(by_name["path"]["help"], "path to file")

        # Positional optional with default
        self.assertIn("opt_pos", by_name)
        self.assertEqual(by_name["opt_pos"]["required"], False)
        self.assertEqual(by_name["opt_pos"]["default"], "default.txt")

        # Optional with short alias
        self.assertIn("--script", by_name)
        self.assertEqual(by_name["--script"]["alias"], "-s")
        self.assertEqual(by_name["--script"]["required"], False)

        # Flag with action=store_true
        self.assertIn("--force", by_name)
        self.assertEqual(by_name["--force"]["alias"], "-f")
        self.assertEqual(by_name["--force"]["type"], "flag")
        self.assertEqual(by_name["--force"]["required"], False)

        # Typed option with required=True and default=10
        self.assertIn("--count", by_name)
        self.assertEqual(by_name["--count"]["type"], "int")
        self.assertEqual(by_name["--count"]["required"], True)
        self.assertEqual(by_name["--count"]["default"], "10")

        # Short flag only
        self.assertIn("-v", by_name)
        self.assertEqual(by_name["-v"]["type"], "flag")
        self.assertEqual(by_name["-v"]["required"], False)

    def test_ac08_orphan_doc_detection_without_deletion(self):
        skill = self.create_skill("orphan-skill")
        script = skill / "scripts" / "to_delete.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        # Generate doc
        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(DOC_SCRIPT.generate_doc(script), encoding="utf-8")
        self.assertTrue(doc.is_file())

        # Now delete the script, making the doc an orphan
        script.unlink()
        self.assertFalse(script.exists())

        # Run audit
        code, out, err = self.run_cli("--audit")
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_DOC:", err)
        self.assertIn(doc.name, err)

        # Document must NOT be deleted automatically
        self.assertTrue(doc.is_file(), "Orphan document must not be deleted automatically")

    def test_audit_validation_checks(self):
        skill = self.create_skill("audit-skill")
        script = skill / "scripts" / "audited.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)

        # 1. Draft status error
        doc_content = DOC_SCRIPT.generate_doc(script)
        doc.write_text(doc_content, encoding="utf-8")
        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("DRAFT_STATUS" in e for e in errors))

        # 2. Placeholder error
        valid_doc = doc_content.replace("status: draft", "status: actual")
        doc.write_text(valid_doc, encoding="utf-8")
        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("PLACEHOLDER" in e for e in errors))

        # 3. Draft pattern error
        no_placeholder = valid_doc.replace("Заполнить:", "Готово:")
        doc.write_text(no_placeholder, encoding="utf-8")
        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("DRAFT_PATTERN" in e for e in errors))

    def test_a01_symlink_and_boundary_security(self):
        skill = self.create_skill("security-skill")
        script = skill / "scripts" / "run.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        outside_dir = self.root / "outside_target"
        outside_dir.mkdir(parents=True, exist_ok=True)

        (skill / "docs").mkdir(parents=True, exist_ok=True)
        symlink_target = skill / "docs" / "scripts"
        try:
            symlink_target.symlink_to(outside_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this platform/filesystem")

        rel_script = script.relative_to(self.root).as_posix()
        code, out, err = self.run_cli("--script", rel_script)
        self.assertEqual(code, 1)
        self.assertIn("SECURITY_ERROR", err)
        self.assertEqual(list(outside_dir.iterdir()), [], "Outside directory must not be written to")

    def test_a02_mask_sensitive_parameters(self):
        skill = self.create_skill("secret-skill")
        py_script = skill / "scripts" / "secret_cli.py"
        py_script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--token', default='FAKE_SECRET_123', help='api token')\n"
            "parser.add_argument('--password', default='super_secret_pw', help='user password')\n"
            "parser.add_argument('--normal', default='public_val', help='regular option')\n",
            encoding="utf-8",
        )
        doc_text = DOC_SCRIPT.generate_doc(py_script)
        self.assertNotIn("FAKE_SECRET_123", doc_text)
        self.assertNotIn("super_secret_pw", doc_text)
        self.assertIn("[MASKED]", doc_text)
        self.assertIn("public_val", doc_text)

        ps_script = skill / "scripts" / "secret_ps.ps1"
        ps_script.write_text(
            "param(\n"
            "    [string]$ApiKey = 'FAKE_SECRET_999',\n"
            "    [string]$Normal = 'normal_value'\n"
            ")\n",
            encoding="utf-8",
        )
        ps_doc = DOC_SCRIPT.generate_doc(ps_script)
        self.assertNotIn("FAKE_SECRET_999", ps_doc)
        self.assertIn("[MASKED]", ps_doc)
        self.assertIn("normal_value", ps_doc)

    def test_a03_audit_exact_argument_matching(self):
        skill = self.create_skill("exact-audit-skill")
        script = skill / "scripts" / "token_cli.py"
        script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--token', required=True)\n",
            encoding="utf-8",
        )
        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)

        bad_doc = DOC_SCRIPT.generate_doc(script)
        bad_doc = bad_doc.replace("status: draft", "status: actual")
        bad_doc = bad_doc.replace("Заполнить:", "Готово:")
        bad_doc = bad_doc.replace("--token", "--tokenizer")
        doc.write_text(bad_doc, encoding="utf-8")

        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("ARG_MISSING" in e and "--token" in e for e in errors))

        no_arg_table_doc = bad_doc.replace("--tokenizer", "нет")
        no_arg_table_doc = no_arg_table_doc.replace("## Примеры", "## Примеры\nВызов: `script --token abc`")
        doc.write_text(no_arg_table_doc, encoding="utf-8")
        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("ARG_MISSING" in e and "--token" in e for e in errors))

    def test_a04_collision_resolution_between_canon_and_core(self):
        canon_same = self.canon / "same.sh"
        canon_same.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        core_scripts = self.core / "scripts"
        core_scripts.mkdir(parents=True, exist_ok=True)
        core_same = core_scripts / "same.sh"
        core_same.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        canon_doc = DOC_SCRIPT.doc_path_for(canon_same)
        core_doc = DOC_SCRIPT.doc_path_for(core_same)

        self.assertIsNotNone(canon_doc)
        self.assertIsNotNone(core_doc)
        self.assertNotEqual(canon_doc, core_doc)
        self.assertIn("cursor-canon", canon_doc.parts)
        self.assertIn("core-scripts", core_doc.parts)

        # Ensure reverse mapping returns proper script
        self.assertEqual(DOC_SCRIPT.script_path_for_doc(canon_doc), canon_same)
        self.assertEqual(DOC_SCRIPT.script_path_for_doc(core_doc), core_same)

        # Test A-4 scenario: .cursor/scripts/cursor/same.sh must not collide
        cursor_sub_same = self.canon / "cursor" / "same.sh"
        cursor_sub_same.parent.mkdir(parents=True, exist_ok=True)
        cursor_sub_same.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        cursor_sub_doc = DOC_SCRIPT.doc_path_for(cursor_sub_same)

        self.assertIsNotNone(cursor_sub_doc)
        self.assertNotEqual(canon_doc, cursor_sub_doc)
        self.assertNotEqual(core_doc, cursor_sub_doc)

        # Single --script with collision must be blocked even with --force
        with patch.object(DOC_SCRIPT, "detect_script_doc_collisions", return_value={canon_doc: [canon_same, core_same]}):
            code, out, err = self.run_cli("--script", canon_same.relative_to(self.root).as_posix(), "--force")
            self.assertEqual(code, 1)
            self.assertIn("COLLISION_DETECTED", err)

    def test_a05_unparsed_click_and_dynamic_syntax(self):
        skill = self.create_skill("dynamic-skill")
        click_script = skill / "scripts" / "click_app.py"
        click_script.write_text(
            "import click\n"
            "@click.command()\n"
            "@click.option('--secret', default='sec123', help='secret opt')\n"
            "@click.option('--force', is_flag=True)\n"
            "def main(secret, force):\n    pass\n",
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(click_script)
        by_name = {a["name"]: a for a in args}
        self.assertIn("--secret", by_name)
        self.assertIn("--force", by_name)
        self.assertEqual(by_name["--force"]["type"], "flag")

        dynamic_script = skill / "scripts" / "dynamic_argparse.py"
        dynamic_script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "FLAG = '--dynamic'\n"
            "parser.add_argument(FLAG, required=True)\n",
            encoding="utf-8",
        )
        _, is_reliable = DOC_SCRIPT.parse_script_arguments(dynamic_script)
        self.assertFalse(is_reliable)

    def test_a06_powershell_comment_skipping_and_mandatory_switch(self):
        skill = self.create_skill("ps-comment-skill")
        ps_script = skill / "scripts" / "test_ps_comments.ps1"
        ps_script.write_text(
            "<#\n"
            "param(\n"
            "    [string]$FakeParam\n"
            ")\n"
            "#>\n"
            "param(\n"
            "    [Parameter(Mandatory = $true)]\n"
            "    [switch]$Force,\n"
            "    [string]$RealParam\n"
            ")\n",
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(ps_script)
        by_name = {a["name"]: a for a in args}

        self.assertNotIn("-FakeParam", by_name)
        self.assertIn("-RealParam", by_name)
        self.assertIn("-Force", by_name)
        self.assertEqual(by_name["-Force"]["required"], True)

    def test_a06_shell_getopts_options_with_values(self):
        skill = self.create_skill("sh-getopts-skill")
        sh_script = skill / "scripts" / "opts.sh"
        sh_script.write_text(
            '#!/bin/bash\n'
            'while getopts "f:o:v" opt; do\n'
            '  case "$opt" in\n'
            '    f) FILE="$OPTARG" ;;\n'
            '    o) OUT="$OPTARG" ;;\n'
            '    v) VERBOSE=1 ;;\n'
            '  esac\n'
            'done\n',
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(sh_script)
        by_name = {a["name"]: a for a in args}

        self.assertIn("-f", by_name)
        self.assertEqual(by_name["-f"]["type"], "string")
        self.assertIn("-o", by_name)
        self.assertEqual(by_name["-o"]["type"], "string")
        self.assertIn("-v", by_name)
        self.assertEqual(by_name["-v"]["type"], "flag")

    def test_a06_commander_option_parsing(self):
        skill = self.create_skill("js-commander-skill")
        js_script = skill / "scripts" / "cli.js"
        js_script.write_text(
            "const { program } = require('commander');\n"
            "program\n"
            "  .option('-f, --force', 'force overwrite')\n"
            "  .option('-c, --config <path>', 'path to configuration file')\n"
            "  .parse(process.argv);\n",
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(js_script)
        by_name = {a["name"]: a for a in args}

        self.assertIn("--force", by_name)
        self.assertEqual(by_name["--force"]["alias"], "-f")
        self.assertEqual(by_name["--force"]["type"], "flag")

        self.assertIn("--config", by_name)
        self.assertEqual(by_name["--config"]["alias"], "-c")
        self.assertEqual(by_name["--config"]["type"], "string")
        self.assertEqual(by_name["--config"]["help"], "path to configuration file")

    def test_a08_atomic_write_safety(self):
        skill = self.create_skill("atomic-skill")
        target_file = skill / "docs" / "test_doc.md"
        DOC_SCRIPT.atomic_write_text(target_file, "Initial content")
        self.assertEqual(target_file.read_text(encoding="utf-8"), "Initial content")

        DOC_SCRIPT.atomic_write_text(target_file, "Updated content")
        self.assertEqual(target_file.read_text(encoding="utf-8"), "Updated content")

    def test_a01_predictable_temp_symlink_attack(self):
        skill = self.create_skill("symlink-target-skill")
        outside_victim = self.root / "victim.txt"
        outside_victim.write_text("CRITICAL_EXTERNAL_DATA", encoding="utf-8")

        target_file = skill / "docs" / "test_doc.md"
        target_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            target_file.symlink_to(outside_victim)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported")

        with self.assertRaises(PermissionError):
            DOC_SCRIPT.atomic_write_text(target_file, "MALICIOUS_CONTENT")

        self.assertEqual(outside_victim.read_text(encoding="utf-8"), "CRITICAL_EXTERNAL_DATA")

    def test_a02_credentials_in_url_and_help_text_masking(self):
        skill = self.create_skill("url-secret-skill")
        py_script = skill / "scripts" / "url_cli.py"
        py_script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--url', default='https://admin:FAKE_SECRET_PASS@api.service.com', help='connect url')\n"
            "parser.add_argument('--normal', default='val', help='Use FAKE_SECRET_API_KEY as token')\n",
            encoding="utf-8",
        )
        doc_text = DOC_SCRIPT.generate_doc(py_script)
        self.assertNotIn("FAKE_SECRET_PASS", doc_text)
        self.assertNotIn("FAKE_SECRET_API_KEY", doc_text)
        self.assertIn("https://admin:***@api.service.com", doc_text)
        self.assertIn("[MASKED]", doc_text)

    def test_a03_empty_sections_and_missing_table_row_rejected(self):
        skill = self.create_skill("empty-sec-skill")
        script = skill / "scripts" / "app.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)

        valid_doc = DOC_SCRIPT.generate_doc(script)
        valid_doc = valid_doc.replace("status: draft", "status: actual")
        valid_doc = valid_doc.replace("Заполнить: что делает скрипт и зачем он нужен, 2-4 предложения.", "")
        doc.write_text(valid_doc, encoding="utf-8")

        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("EMPTY_SECTION" in e and "## Суть" in e for e in errors))

    def test_a05_mixed_known_and_dynamic_arguments_rejected(self):
        skill = self.create_skill("mixed-dynamic-skill")
        script = skill / "scripts" / "mixed.py"
        script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--known', help='known arg')\n"
            "FLAG = '--dynamic'\n"
            "parser.add_argument(FLAG, required=True)\n",
            encoding="utf-8",
        )
        args, is_reliable = DOC_SCRIPT.parse_script_arguments(script)
        self.assertFalse(is_reliable)

        doc_text = DOC_SCRIPT.generate_doc(script)
        self.assertIn("Внимание: синтаксис аргументов распознан не полностью", doc_text)

        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(doc_text.replace("status: draft", "status: actual").replace("Заполнить:", "Готово:"), encoding="utf-8")
        errors = DOC_SCRIPT.audit(script)
        self.assertTrue(any("UNRELIABLE_PARSE" in e for e in errors))

    def test_a05_argv_contract_accepts_wrapper(self):
        skill = self.create_skill("argv-wrapper-skill")
        script = skill / "scripts" / "wrap.sh"
        script.write_text("#!/bin/bash\nexec php \"$@\"\n", encoding="utf-8")
        _, is_reliable = DOC_SCRIPT.parse_script_arguments(script)
        self.assertFalse(is_reliable)

        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc_text = DOC_SCRIPT.generate_doc(script)
        doc_text = doc_text.replace("status: draft", "status: actual").replace("Заполнить:", "Готово:")
        doc_text = doc_text.replace("status: actual\nupdated:", "status: actual\nargv: passthrough\nupdated:")
        doc.write_text(doc_text, encoding="utf-8")

        errors = DOC_SCRIPT.audit(script)
        self.assertFalse(any("UNRELIABLE_PARSE" in e for e in errors))

    def test_a06_commander_optional_vs_required(self):
        skill = self.create_skill("js-required-skill")
        js_script = skill / "scripts" / "cli2.js"
        js_script.write_text(
            "const { program } = require('commander');\n"
            "program\n"
            "  .option('-c, --config <path>', 'path to configuration file')\n"
            "  .requiredOption('-m, --must <val>', 'mandatory option')\n"
            "  .argument('<input>', 'input file')\n"
            "  .parse(process.argv);\n",
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(js_script)
        by_name = {a["name"]: a for a in args}

        self.assertIn("--config", by_name)
        self.assertEqual(by_name["--config"]["required"], False)

        self.assertIn("--must", by_name)
        self.assertEqual(by_name["--must"]["required"], True)

        self.assertIn("<input>", by_name)
        self.assertEqual(by_name["<input>"]["required"], True)

    def test_a06_python_subcommands_mode_isolation(self):
        skill = self.create_skill("subcmd-skill")
        py_script = skill / "scripts" / "subcmd.py"
        py_script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "sub = parser.add_subparsers()\n"
            "sp_build = sub.add_parser('build')\n"
            "sp_build.add_argument('--mode', choices=['fast', 'slow'])\n"
            "sp_deploy = sub.add_parser('deploy')\n"
            "sp_deploy.add_argument('--mode', choices=['dev', 'prod'])\n",
            encoding="utf-8",
        )
        args = DOC_SCRIPT.parse_arguments(py_script)
        self.assertEqual(len(args), 2)
        subcmds = {a.get("subcommand") for a in args}
        self.assertEqual(subcmds, {"build", "deploy"})

    def test_a06_python_complex_literal_defaults_reliable(self):
        skill = self.create_skill("literal-default-skill")
        py_script = skill / "scripts" / "cli.py"
        py_script.write_text(
            "import argparse\n"
            "DEFAULT_VAL = 'constant'\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--items', default=[])\n"
            "parser.add_argument('--conf', default=DEFAULT_VAL)\n",
            encoding="utf-8",
        )
        args, reliable = DOC_SCRIPT.parse_script_arguments(py_script)
        self.assertTrue(reliable)
        by_name = {a["name"]: a for a in args}
        self.assertEqual(by_name["--items"]["default"], "[]")
        self.assertEqual(by_name["--conf"]["default"], "DEFAULT_VAL")

    def test_a07_inventory_breakdown_and_classification(self):
        skill = self.create_skill("inventory-skill")
        (skill / "scripts" / "run.sh").write_text("#!/bin/bash\necho run\n", encoding="utf-8")
        (skill / "scripts" / "_lib.ps1").write_text("function Helper { 1 }\n", encoding="utf-8")
        (skill / "scripts" / "lib.sh").write_text("common_func() { true; }\n", encoding="utf-8")
        (skill / "scripts" / "test_runner.py").write_text("import unittest\n", encoding="utf-8")

        outside_dir = self.root / ".dsh" / "scripts"
        outside_dir.mkdir(parents=True, exist_ok=True)
        (outside_dir / "unowned.sh").write_text("#!/bin/bash\necho unowned\n", encoding="utf-8")

        self.assertEqual(DOC_SCRIPT.classify_script(skill / "scripts" / "run.sh")[0], "entrypoint")
        self.assertEqual(DOC_SCRIPT.classify_script(skill / "scripts" / "_lib.ps1")[0], "library")
        self.assertEqual(DOC_SCRIPT.classify_script(skill / "scripts" / "lib.sh")[0], "library")
        self.assertEqual(DOC_SCRIPT.classify_script(skill / "scripts" / "test_runner.py")[0], "test")
        self.assertEqual(DOC_SCRIPT.classify_script(outside_dir / "unowned.sh")[0], "unknown_owner")

    def test_a03_exact_table_row_matching_with_backticks_and_aliases(self):
        table = (
            "| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |\n"
            "|---|---|---|---|---|---|\n"
            "| `--root` | нет | string | да | нет | корень репозитория |\n"
            "| `-h`, `--help` | нет | flag | нет | выключен | показать справку |\n"
            "| `--tokenizer` | нет | string | нет | bpe | токенизатор текста |\n"
        )
        cols_root, desc_root = DOC_SCRIPT.find_arg_table_row("--root", table)
        self.assertIsNotNone(cols_root)
        self.assertIn("корень", desc_root)

        cols_help, desc_help = DOC_SCRIPT.find_arg_table_row("--help", table)
        self.assertIsNotNone(cols_help)
        self.assertIn("справку", desc_help)

        cols_short_h, desc_short_h = DOC_SCRIPT.find_arg_table_row("-h", table)
        self.assertIsNotNone(cols_short_h)

        cols_token, _ = DOC_SCRIPT.find_arg_table_row("--token", table)
        self.assertIsNone(cols_token)

        cols_toker, desc_toker = DOC_SCRIPT.find_arg_table_row("--tokenizer", table)
        self.assertIsNotNone(cols_toker)
        self.assertIn("токенизатор", desc_toker)

    def test_r01_parent_directory_symlink_race_protection(self):
        import shutil
        skill = self.create_skill("race-skill")
        target_doc = skill / "docs" / "scripts" / "target.sh.md"
        target_doc.parent.mkdir(parents=True, exist_ok=True)
        original_content = "# Original content\n"
        target_doc.write_text(original_content, encoding="utf-8")

        external_dir = self.root / "external_leak"
        external_dir.mkdir(parents=True, exist_ok=True)
        external_marker = external_dir / "marker.txt"
        external_marker.write_text("safe\n", encoding="utf-8")

        # Swap docs/scripts with a symlink to external_dir
        shutil.rmtree(target_doc.parent)
        try:
            target_doc.parent.symlink_to(external_dir, target_is_directory=True)
        except OSError as error:
            if getattr(error, 'winerror', None) == 1314:
                self.skipTest('Windows lacks permission to create symbolic links')
            raise

        with self.assertRaises(PermissionError):
            DOC_SCRIPT.atomic_write_text(target_doc, "# Malicious write\n", owner=skill)

        self.assertEqual(external_marker.read_text(encoding="utf-8"), "safe\n")
        self.assertFalse((external_dir / "target.sh.md").exists())

    def test_r02_query_token_and_complex_password_in_help_masked(self):
        skill = self.create_skill("secret-skill")
        py_script = skill / "scripts" / "fetcher.py"
        py_script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--url', default='https://user:synthetic_pass123@host:8080/path?token=synthetic_tok_456&mode=full', help='Connect URL')\n"
            "parser.add_argument('--auth-info', default='normal', help='Provide credentials with password: s#cr3t!p@ss value')\n"
            "parser.add_argument('--timeout', type=int, default=30, help='Normal timeout in seconds')\n",
            encoding="utf-8",
        )
        doc_content = DOC_SCRIPT.generate_doc(py_script)

        self.assertNotIn("synthetic_pass123", doc_content)
        self.assertNotIn("synthetic_tok_456", doc_content)
        self.assertNotIn("s#cr3t!p@ss", doc_content)

        self.assertIn("--url", doc_content)
        self.assertIn("mode=full", doc_content)
        self.assertIn("token=***", doc_content)
        self.assertIn("://user:***@host:8080", doc_content)
        self.assertIn("password: ***", doc_content)
        self.assertIn("--timeout", doc_content)
        self.assertIn("30", doc_content)

    def test_r03_mcp_stack_and_cursor_scripts_collision_prevention(self):
        cursor_script = self.canon / "_same.sh"
        mcp_stack_dir = self.root / ".cursor" / "mcp-stack"
        mcp_stack_dir.mkdir(parents=True, exist_ok=True)
        mcp_script = mcp_stack_dir / "_same.sh"
        core_script = self.core / "scripts" / "_same.sh"
        core_script.parent.mkdir(parents=True, exist_ok=True)

        for s in (cursor_script, mcp_script, core_script):
            s.write_text("#!/bin/bash\necho same\n", encoding="utf-8")

        with patch.object(DOC_SCRIPT, "CANON_MCP_STACK", mcp_stack_dir):
            doc_cursor = DOC_SCRIPT.doc_path_for(cursor_script)
            doc_mcp = DOC_SCRIPT.doc_path_for(mcp_script)
            doc_core = DOC_SCRIPT.doc_path_for(core_script)

            self.assertIsNotNone(doc_cursor)
            self.assertIsNotNone(doc_mcp)
            self.assertIsNotNone(doc_core)
            self.assertNotEqual(doc_cursor, doc_mcp)
            self.assertNotEqual(doc_cursor, doc_core)
            self.assertNotEqual(doc_mcp, doc_core)

            self.assertEqual(DOC_SCRIPT.script_path_for_doc(doc_cursor), cursor_script)
            self.assertEqual(DOC_SCRIPT.script_path_for_doc(doc_mcp), mcp_script)
            self.assertEqual(DOC_SCRIPT.script_path_for_doc(doc_core), core_script)

            doc_cursor.parent.mkdir(parents=True, exist_ok=True)
            doc_cursor.write_text("# Cursor doc\n", encoding="utf-8")

            with patch.object(DOC_SCRIPT, "doc_path_for", return_value=doc_cursor):
                code, out, err = self.run_cli("--script", mcp_script.relative_to(self.root).as_posix(), "--force")
                self.assertEqual(code, 1)
                self.assertTrue("COLLISION" in err, f"expected collision error in {err}")
                self.assertEqual(doc_cursor.read_text(encoding="utf-8"), "# Cursor doc\n")

            # Direct test for COLLISION_OVERWRITE_PREVENTED:
            # If doc_cursor belongs to cursor_script, trying to write it from mcp_script triggers COLLISION_OVERWRITE_PREVENTED
            with patch.object(DOC_SCRIPT, "doc_path_for", return_value=doc_cursor), \
                 patch.object(DOC_SCRIPT, "detect_script_doc_collisions", return_value={}):
                code, out, err = self.run_cli("--script", mcp_script.relative_to(self.root).as_posix(), "--force")
                self.assertEqual(code, 1)
                self.assertIn("COLLISION_OVERWRITE_PREVENTED", err)
                self.assertEqual(doc_cursor.read_text(encoding="utf-8"), "# Cursor doc\n")

    def test_r04_strict_section_headings_and_subcommand_rows_and_exact_hyphens(self):
        skill = self.create_skill("r04-skill")
        script = skill / "scripts" / "tool.py"
        script.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "sub = parser.add_subparsers()\n"
            "b = sub.add_parser('build')\n"
            "b.add_argument('--mode', help='build mode')\n"
            "d = sub.add_parser('deploy')\n"
            "d.add_argument('--mode', help='deploy mode')\n"
            "parser.add_argument('--token', help='auth token')\n",
            encoding="utf-8",
        )
        doc = DOC_SCRIPT.doc_path_for(script)
        doc.parent.mkdir(parents=True, exist_ok=True)

        invalid_heading_doc = (
            "# Скрипт: tool.py\n<!-- meta\nstatus: actual\n-->\n"
            "## Суть суффикс\nТекст сути.\n"
            "## Когда запускать\nТекст.\n"
            "## Аргументы\n"
            "| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |\n"
            "|---|---|---|---|---|---|\n"
            "| build: --mode | нет | string | нет | нет | build mode |\n"
            "| deploy: --mode | нет | string | нет | нет | deploy mode |\n"
            "| `--token` | нет | string | нет | нет | auth token |\n"
            "## Коды выхода\n| Код | Значение | Действие вызывающего |\n|---|---|---|\n| 0 | ok | продолжить |\n"
            "## Что читает и что пишет\nФайлы.\n## Побочные эффекты\nНет.\n"
            "## Окружение и зависимости\nНет.\n## Примеры\nВызов.\n## Ограничения\nНет.\n## Связи\nСкил.\n"
            "## История изменений\n- 2026-11-07: создан\n"
        )
        doc.write_text(invalid_heading_doc, encoding="utf-8")
        errs = DOC_SCRIPT.audit(script)
        self.assertTrue(any("MISSING_SECTION" in e and "## Суть" in e for e in errs), errs)

        valid_heading_wrong_token = invalid_heading_doc.replace("## Суть суффикс", "## Суть").replace("`--token`", "`token`")
        doc.write_text(valid_heading_wrong_token, encoding="utf-8")
        errs = DOC_SCRIPT.audit(script)
        self.assertTrue(any("ARG_MISSING" in e and "--token" in e for e in errs), errs)

        only_build_subcmd = invalid_heading_doc.replace("## Суть суффикс", "## Суть").replace("| deploy: --mode | нет | string | нет | нет | deploy mode |\n", "")
        doc.write_text(only_build_subcmd, encoding="utf-8")
        errs = DOC_SCRIPT.audit(script)
        self.assertTrue(any("ARG_MISSING" in e and "--mode" in e for e in errs), errs)

        correct_doc = invalid_heading_doc.replace("## Суть суффикс", "## Суть")
        doc.write_text(correct_doc, encoding="utf-8")
        errs = DOC_SCRIPT.audit(script)
        self.assertEqual(errs, [])

    def test_r05_dynamic_kwargs_commander_flags_and_multiline_case(self):
        skill = self.create_skill("r05-skill")
        py_kwargs = skill / "scripts" / "kwargs_script.py"
        py_kwargs.write_text(
            "import argparse\n"
            "opts = {'help': 'dynamic'}\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--unsafe', required=True, **opts)\n",
            encoding="utf-8",
        )
        args_py, rel_py = DOC_SCRIPT.parse_script_arguments(py_kwargs)
        self.assertFalse(rel_py, "Python add_argument with **kwargs must be marked unreliable")

        js_script = skill / "scripts" / "dynamic_cmd.js"
        js_script.write_text(
            "const { program } = require('commander');\n"
            "const FLAG = '--custom';\n"
            "program.option('--known', 'known option').option(FLAG, 'dynamic flag');\n",
            encoding="utf-8",
        )
        args_js, rel_js = DOC_SCRIPT.parse_script_arguments(js_script)
        self.assertFalse(rel_js, "Commander with dynamic option name must be marked unreliable")

        sh_script = skill / "scripts" / "multiline_case.sh"
        sh_script.write_text(
            "#!/bin/bash\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    -c|--config)\n"
            "      CONFIG=\"$2\"\n"
            "      shift 2\n"
            "      ;;\n"
            "    -v|--verbose)\n"
            "      VERBOSE=1\n"
            "      shift\n"
            "      ;;\n"
            "    *)\n"
            "      break ;;\n"
            "  esac\n"
            "done\n",
            encoding="utf-8",
        )
        args_sh, rel_sh = DOC_SCRIPT.parse_script_arguments(sh_script)
        self.assertTrue(rel_sh)
        by_name_sh = {a["name"]: a for a in args_sh}
        self.assertEqual(by_name_sh["--config"]["type"], "string")
        self.assertEqual(by_name_sh["-c"]["type"], "string")
        self.assertEqual(by_name_sh["--verbose"]["type"], "flag")
        self.assertEqual(by_name_sh["-v"]["type"], "flag")

    def test_r07_lib_directory_shebang_classified_as_library_and_dsh_owner(self):
        skill = self.create_skill("r07-skill")
        lib_dir = skill / "scripts" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)
        lib_with_shebang = lib_dir / "io_jsonl.py"
        lib_with_shebang.write_text("#!/usr/bin/env python3\nimport json\ndef load(): pass\n", encoding="utf-8")

        cat, reason = DOC_SCRIPT.classify_script(lib_with_shebang)
        self.assertEqual(cat, "library")
        self.assertIn("lib", reason)

        dsh_scripts_dir = self.root / ".dsh" / "scripts"
        dsh_scripts_dir.mkdir(parents=True, exist_ok=True)
        dsh_smoke = dsh_scripts_dir / "smoke.sh"
        dsh_smoke.write_text("#!/bin/bash\necho smoke\n", encoding="utf-8")

        dsh_router_skill = self.root / ".dsh" / "skills" / "dsh-router"
        dsh_router_skill.mkdir(parents=True, exist_ok=True)
        (dsh_router_skill / "SKILL.md").write_text("---\nname: dsh-router\n---\n", encoding="utf-8")

        with patch.object(DOC_SCRIPT, "DSH_SCRIPTS", dsh_scripts_dir):
            owner = DOC_SCRIPT.skill_root_for(dsh_smoke)
            self.assertEqual(owner, dsh_router_skill)
            cat_smoke, _ = DOC_SCRIPT.classify_script(dsh_smoke)
            self.assertEqual(cat_smoke, "entrypoint")

    def test_r09_python38_ast_fallback(self):
        import ast
        node = ast.parse("['a', {'k': (1, 2)}, None]").body[0].value
        with patch.object(ast, "unparse", None, create=True):
            result = DOC_SCRIPT.safe_ast_unparse(node)
            self.assertIsNotNone(result)
            self.assertIn("'a'", result)
            self.assertIn("'k'", result)


if __name__ == "__main__":
    unittest.main()
