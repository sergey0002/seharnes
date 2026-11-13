import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "doc_mcp", Path(__file__).parents[1] / "scripts" / "doc_mcp.py"
)
MCP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MCP)


class DocMcpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / ".agents/skills"
        self.legacy = self.root / ".doc/harnes/mcp"
        self.config = self.root / ".cursor/mcp.json"
        for path in (self.skills, self.legacy, self.config.parent):
            path.mkdir(parents=True)
        self.patcher = patch.multiple(
            MCP, ROOT=self.root, SKILLS=self.skills, LEGACY=self.legacy, CONFIG=self.config
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.config.write_text(json.dumps({"mcpServers": {"example": {}}}))

    def skill(self, name="example"):
        path = self.skills / name
        path.mkdir()
        for filename in ("SKILL.md", "README.md", "skill.json"):
            (path / filename).write_text("{}" if filename.endswith("json") else name)
        doc = path / "docs/mcp" / "example.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# MCP: example\n")
        return path, doc

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["doc_mcp.py", *args]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = MCP.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_complete_skill_passes_and_audit_is_read_only(self):
        _, doc = self.skill()
        before = doc.read_bytes()
        self.assertEqual(self.run_cli("--audit")[0], 0)
        self.assertEqual(self.run_cli("--audit")[0], 0)
        self.assertEqual(doc.read_bytes(), before)

    def test_policy_layout_adds_requirement_without_relaxing_trusted_location(self):
        source = Path(__file__).resolve().parents[6]
        skill, original = self.skill()
        relatives = ('.doc/harnes/state/canon-paths.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                     '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')
        for relative in relatives:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination)
        canon = self.root / relatives[0]
        canon.write_text(canon.read_text(encoding='utf-8').replace(
            '.agents/skills/{skill}/docs/mcp', '.agents/skills/{skill}/docs/extra'), encoding='utf-8')
        code, _, error = self.run_cli('--audit', '--policy-root', str(self.root))
        self.assertEqual(code, 1)
        self.assertIn('POLICY_DOC_MISSING', error)
        extra = skill / 'docs/extra/example.md'
        extra.parent.mkdir(parents=True)
        extra.write_text('# additional\n', encoding='utf-8')
        self.assertEqual(self.run_cli('--audit', '--policy-root', str(self.root))[0], 0)
        original.unlink()
        code, _, error = self.run_cli('--audit', '--policy-root', str(self.root))
        self.assertEqual(code, 1)
        self.assertIn('DOC_MISSING', error)
        canon.write_text(canon.read_text(encoding='utf-8').replace(
            '.agents/skills/{skill}/docs/extra', '.agents/skills/{skill}/../outside'), encoding='utf-8')
        code, _, error = self.run_cli('--audit', '--policy-root', str(self.root))
        self.assertEqual(code, 1)
        self.assertIn('unsafe MCP doc layout', error)
        self.assertEqual(self.run_cli('--audit', '--move', '--policy-root', str(self.root))[0], 2)
        for server in ('../escape', 'CON', 'name.'):
            with self.subTest(server=server), self.assertRaises(ValueError):
                MCP.extra_policy_doc(skill, server, ('docs', 'extra'))

    def test_missing_skill_is_not_hidden_by_list_option(self):
        code, _, error = self.run_cli("--list", "--audit")
        self.assertEqual(code, 1)
        self.assertIn("SKILL_MISSING: example", error)

    def test_incomplete_skill_fails(self):
        skill, _ = self.skill()
        (skill / "README.md").unlink()
        code, _, error = self.run_cli("--audit")
        self.assertEqual(code, 1)
        self.assertIn("SKILL_INCOMPLETE", error)

    def test_duplicate_document_fails_without_changing_either_copy(self):
        _, doc = self.skill()
        old = self.legacy / "example.md"
        old.write_text("original audit history")
        code, _, error = self.run_cli("--audit")
        self.assertEqual(code, 1)
        self.assertIn("DOC_DUPLICATE", error)
        self.assertEqual(old.read_text(), "original audit history")
        self.assertEqual(doc.read_text(), "# MCP: example\n")

    def test_relative_links_and_related_paths_are_checked(self):
        skill, doc = self.skill()
        doc.write_text(
            "related: [../../README.md, ./missing-meta.md]\n"
            "[skill](../../SKILL.md)\n[broken](./missing-link.md)\n"
            "[web](https://example.invalid/)\n[section](#section)\n"
            "```markdown\n[template](./ignored.md)\n```\n"
        )
        errors = MCP.audit_document(doc)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("missing-meta.md" in error for error in errors))
        self.assertTrue(any("missing-link.md" in error for error in errors))
        self.assertTrue((skill / "README.md").exists())

    def test_disabled_server_keeps_existing_legacy_document(self):
        self.config.write_text(json.dumps({"mcpServers": {"example": {"disabled": True}}}))
        doc = self.legacy / "example.md"
        doc.write_text("# Disabled: replaced by another tool\n")
        code, output, _ = self.run_cli("--list", "--audit")
        self.assertEqual(code, 0)
        self.assertIn(".doc/harnes/mcp/example.md", output)
        self.assertTrue(doc.exists())

    def test_document_needed_to_move_is_reported(self):
        _, doc = self.skill()
        doc.unlink()
        (self.legacy / "example.md").write_text("existing document")
        code, _, error = self.run_cli("--audit")
        self.assertEqual(code, 1)
        self.assertIn("DOC_NOT_MOVED", error)

    def test_r08_command_paths_checked_statically_without_execution(self):
        skill, doc = self.skill()
        valid_script = self.root / ".cursor" / "scripts" / "valid.sh"
        valid_script.parent.mkdir(parents=True, exist_ok=True)
        valid_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

        doc.write_text(
            f"# MCP: example\n\n```bash\nbash .cursor/scripts/valid.sh\nbash .cursor/scripts/missing_tool.sh\n```\n",
            encoding="utf-8",
        )
        errors = MCP.audit_document(doc)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("COMMAND_PATH_NOT_FOUND", errors[0])
        self.assertIn("missing_tool.sh", errors[0])
        self.assertNotIn("valid.sh", errors[0])


if __name__ == "__main__":
    unittest.main()
