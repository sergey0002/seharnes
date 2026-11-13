#!/usr/bin/env python3
"""Self-test suite for skill-creator deterministic utilities."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import package_and_verify  # noqa: E402
import scaffold_skill  # noqa: E402


class SkillCreatorSelfTests(unittest.TestCase):
    def test_scaffold_model_invoked_and_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = scaffold_skill.parse_args(
                [
                    "demo-skill",
                    "--output-dir",
                    tmp,
                    "--description",
                    "Generates clean demo artifacts. Use when testing demo workflows. Do NOT use for general coding.",
                    "--archetype",
                    "script",
                    "--resources",
                    "scripts,references,evals",
                ]
            )
            res = scaffold_skill.scaffold_skill(args)
            self.assertEqual(res["status"], "SCAFFOLDED")
            skill_dir = Path(res["skill_dir"])
            self.assertTrue((skill_dir / "SKILL.md").is_file())
            self.assertTrue((skill_dir / "agents" / "openai.yaml").is_file())
            self.assertTrue((skill_dir / "scripts" / "run_check.py").is_file())
            self.assertTrue((skill_dir / "references" / "domain-rules.md").is_file())
            self.assertTrue((skill_dir / "evals" / "evals.json").is_file())
            self.assertTrue((skill_dir / "evals" / "trigger_evals.json").is_file())

            preflight = package_and_verify.run_builtin_preflight(skill_dir)
            self.assertEqual(preflight["status"], "PASS", preflight)

            pkg = package_and_verify.package_skill(skill_dir, Path(tmp))
            archive = Path(pkg["archive_path"])
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("demo-skill/SKILL.md", names)
                self.assertIn("demo-skill/agents/openai.yaml", names)
                self.assertIn("demo-skill/scripts/run_check.py", names)
                info = zf.getinfo("demo-skill/scripts/run_check.py")
                unix_mode = (info.external_attr >> 16) & 0o777
                self.assertTrue(bool(unix_mode & 0o111), f"Expected +x mode, got {oct(unix_mode)}")

    def test_user_invoked_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = scaffold_skill.parse_args(
                [
                    "manual-release",
                    "--output-dir",
                    tmp,
                    "--archetype",
                    "user-invoked",
                    "--resources",
                    "evals",
                ]
            )
            res = scaffold_skill.scaffold_skill(args)
            skill_dir = Path(res["skill_dir"])
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            openai_text = (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", skill_text)
            self.assertIn('opencode/autoinvoke: "false"', skill_text)
            self.assertIn("allow_implicit_invocation: false", openai_text)
            self.assertFalse((skill_dir / "evals" / "trigger_evals.json").exists())
            preflight = package_and_verify.run_builtin_preflight(skill_dir)
            self.assertEqual(preflight["status"], "PASS", preflight)

    def test_cross_agent_mirrors_and_invalid_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            scaffold_skill.validate_skill_name("Bad_Skill--Name")

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "repo"
            agents_skills = project_root / ".agents" / "skills"
            agents_skills.mkdir(parents=True)
            args = scaffold_skill.parse_args(
                [
                    "repo-helper",
                    "--output-dir",
                    str(agents_skills),
                    "--mirror-project",
                    str(project_root),
                ]
            )
            res = scaffold_skill.scaffold_skill(args)
            self.assertEqual(len(res["mirrors_created"]), 3)
            for mirror_parent in (".claude/skills", ".qoder/skills", ".kiro/skills"):
                link = project_root / mirror_parent / "repo-helper"
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), Path(res["skill_dir"]).resolve())

    def test_preflight_catches_portability_defects_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_skill = Path(tmp) / "bad-skill"
            bad_skill.mkdir()
            (bad_skill / "workflows").mkdir()
            outside = Path(tmp) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            (bad_skill / "leak.txt").symlink_to(outside)
            (bad_skill / "SKILL.md").write_text(
                "---\n"
                "name: bad-skill\n"
                "description: Bad sample\n"
                "version: 1.0.0\n"
                "metadata:\n"
                "  count: 3\n"
                "---\n\n"
                "Run !`cat /etc/passwd` and [missing](references/missing.md)\n",
                encoding="utf-8",
            )
            preflight = package_and_verify.run_builtin_preflight(bad_skill)
            codes = {e["code"] for e in preflight["errors"]}
            self.assertEqual(preflight["status"], "FAIL")
            self.assertIn("PORT-FRONTMATTER-DRIFT", codes)
            self.assertIn("PORT-METADATA-NONSTRING", codes)
            self.assertIn("PORT-NONCANONICAL-DIR", codes)
            self.assertIn("PORT-VENDOR-LOCK", codes)
            self.assertIn("BROKEN-LINK", codes)
            self.assertIn("SYMLINK-ESCAPE", codes)

    def test_sibling_skill_auditor_integration_if_present(self) -> None:
        auditor = package_and_verify.find_sibling_auditor(None)
        if auditor is None:
            self.skipTest("Sibling skill-auditor not found; skipping integration check.")
        proc = subprocess.run(
            [sys.executable, str(auditor), str(SKILL_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data.get("coverage", {}).get("complete"), data.get("coverage"))
        link_graph = data.get("link_graph", {})
        self.assertEqual(link_graph.get("broken_links"), [])
        self.assertEqual(link_graph.get("orphan_files"), [])
        self.assertEqual(data.get("security_findings"), [])
        self.assertEqual(data.get("static_smells"), [])
        univ = data.get("platform_compatibility", {}).get("universal_portability", {})
        self.assertEqual(univ.get("format_fail_count"), 0)
        self.assertEqual(univ.get("portability_score_pct"), 100.0)

        with tempfile.TemporaryDirectory() as tmp:
            args = scaffold_skill.parse_args(
                [
                    "box-clean-skill",
                    "--output-dir",
                    tmp,
                    "--archetype",
                    "script",
                    "--resources",
                    "scripts,references,assets,evals",
                ]
            )
            res = scaffold_skill.scaffold_skill(args)
            sc_proc = subprocess.run(
                [sys.executable, str(auditor), res["skill_dir"]],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(sc_proc.returncode, 0, sc_proc.stderr)
            sc_data = json.loads(sc_proc.stdout)
            self.assertEqual(sc_data.get("link_graph", {}).get("broken_links"), [])
            self.assertEqual(sc_data.get("link_graph", {}).get("orphan_files"), [])
            self.assertEqual(sc_data.get("static_smells"), [])
            self.assertEqual(sc_data.get("security_findings"), [])
            sc_port = sc_data.get("platform_compatibility", {}).get("universal_portability", {})
            self.assertEqual(sc_port.get("portability_score_pct"), 100.0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SkillCreatorSelfTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
