"""Run with python3 -B -m unittest discover -s <this directory>."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflow_contract.py"
SPEC = importlib.util.spec_from_file_location("workflow_contract", SCRIPT)
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


class WorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "task.md"
        self.source.write_text("Task evidence, release 1.2.3", encoding="utf-8")
        self.context = {
            "version": 1, "task_id": "sample",
            "scope": {"kind": "task", "id": "sample", "files": ["src/deleted.php"], "commits": []},
            "allowed_steps": ["documentation", "html", "jira"], "refresh_authorized": False,
            "sources": [{"path": "task.md", "sha256": self.digest(self.source), "role": "task"}],
            "facts": [{"id": "F1", "text": "A verified observation", "evidence": ["task.md"]}],
            "steps": {},
        }

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_check(self):
        return contract.preflight(self.context, self.root)

    def cli(self, raw=None):
        path = self.root / "context.json"
        path.write_text(json.dumps(self.context) if raw is None else raw, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "--context", str(path),
                               "--project-root", str(self.root)], capture_output=True, text=True)
        return proc, json.loads(proc.stdout)

    def pass_step(self, name):
        path = self.root / (name + ".out")
        path.write_text("output " + name, encoding="utf-8")
        self.context["steps"][name] = {
            "status": "passed", "input_hash": contract.input_hash(self.context),
            "artifacts": [{"path": path.name, "sha256": self.digest(path)}],
        }

    def test_valid_ready_and_cli(self):
        result = self.run_check()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["needed_steps"], ["documentation", "jira", "html"])
        self.assertEqual(result["next_action"], "run_documentation")
        proc, result = self.cli()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")

    def test_malformed_json_and_unknown_fields_do_not_dump_secrets(self):
        secret = "private-secret-value-do-not-emit"
        for raw in ('{"password":"' + secret, '{"x":1,"x":2}', 'NaN'):
            proc, result = self.cli(raw)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(result["status"], "malformed")
            self.assertNotIn(secret, proc.stdout + proc.stderr)
        self.context[secret] = secret
        proc, result = self.cli()
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(secret, proc.stdout + proc.stderr)

    def test_schema_types_and_nested_unknowns(self):
        for change in ({"version": True}, {"allowed_steps": ["upload"]}, {"facts": []}):
            with self.subTest(change=change):
                context = dict(self.context, **change)
                self.assertEqual(contract.preflight(context, self.root)["status"], "malformed")
        self.context["scope"]["surprise"] = "secret"
        self.assertEqual(self.run_check()["status"], "malformed")

    def test_changed_and_missing_source(self):
        self.source.write_text("secret changed content", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["next_action"], "request_refresh_consent")
        self.assertNotIn("secret changed content", json.dumps(result))
        proc, _ = self.cli()
        self.assertEqual(proc.returncode, 1)
        self.context["refresh_authorized"] = True
        self.source.unlink()
        self.assertEqual(self.run_check()["next_action"], "refresh_sources")

    def test_partial_consent_never_expands_steps(self):
        self.context["allowed_steps"] = ["documentation"]
        self.assertEqual(self.run_check()["needed_steps"], ["documentation"])
        self.pass_step("documentation")
        self.assertEqual(self.run_check()["status"], "complete")
        self.context["allowed_steps"] = []
        self.assertEqual(self.run_check()["needed_steps"], [])

    def test_reuse_exact_hash_and_available_artifact(self):
        self.pass_step("documentation")
        self.assertEqual(self.run_check()["reusable_steps"], ["documentation"])
        (self.root / "documentation.out").write_text("changed", encoding="utf-8")
        self.assertEqual(self.run_check()["reusable_steps"], [])
        self.assertEqual(self.run_check()["status"], "blocked")
        (self.root / "documentation.out").unlink()
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_new_inputs_invalidate_reuse(self):
        self.pass_step("documentation")
        self.context["facts"][0]["text"] = "Different interpretation"
        self.assertEqual(self.run_check()["status"], "blocked")
        self.assertEqual(self.run_check()["reusable_steps"], [])

    def test_output_steps_do_not_change_hash(self):
        before = contract.input_hash(self.context)
        self.pass_step("documentation")
        self.pass_step("html")
        self.assertEqual(contract.input_hash(self.context), before)
        self.assertEqual(self.run_check()["reusable_steps"], ["documentation", "html"])
        self.assertEqual(contract.input_hash(dict(reversed(list(self.context.items())))), before)

    def test_scope_task_stage_and_empty(self):
        self.context["scope"]["id"] = "wrong"
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["scope"]["kind"] = "stage"
        self.assertEqual(self.run_check()["status"], "ready")
        before = contract.input_hash(self.context)
        self.context["scope"]["id"] = "next-stage"
        self.assertNotEqual(contract.input_hash(self.context), before)
        self.context["scope"]["files"] = []
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_containment_and_symlink_escape(self):
        for raw in ("../outside", "/etc/passwd", "C:\\private", "./task.md", "a/../task.md"):
            with self.subTest(raw=raw):
                context = copy.deepcopy(self.context)
                context["sources"][0]["path"] = raw
                self.assertEqual(contract.preflight(context, self.root)["status"], "blocked")
        link = self.root / "escape"
        link.symlink_to(self.root.parent, target_is_directory=True)
        self.context["sources"][0]["path"] = "escape/secret"
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_evidence_and_duplicate_ids(self):
        self.context["facts"][0]["evidence"] = ["unregistered.md"]
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["facts"][0]["evidence"] = ["task.md"]
        self.context["facts"].append(copy.deepcopy(self.context["facts"][0]))
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_jira_evidence_release_and_shots(self):
        self.context["jira"] = {"text": "Implemented\nрелиз 1.2.3", "release": "1.2.3",
                                "release_source": "task.md", "evidence": ["task.md"],
                                "shots": [], "limitations": []}
        self.assertEqual(self.run_check()["status"], "ready")
        self.context["jira"]["shots"] = [{"path": "absent.png", "title": "View", "caption": "Result"}]
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["jira"]["shots"] = []
        self.context["jira"]["release_source"] = "unregistered.md"
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_jira_requires_authorization_and_release_last_line(self):
        self.context["allowed_steps"].remove("jira")
        self.context["jira"] = {"text": "Implemented\nrelease 1.2.3", "release": "1.2.3",
                                "release_source": "task.md", "evidence": ["task.md"],
                                "shots": [], "limitations": []}
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["allowed_steps"].append("jira")
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["jira"]["text"] = "Implemented\nрелиз 1.2.3"
        self.assertEqual(self.run_check()["status"], "ready")
        self.context["jira"]["text"] = "Implemented\n- item\nрелиз 1.2.3"
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_checkpoint_rebases_updated_documentation_for_html(self):
        self.context["allowed_steps"] = ["documentation", "html"]
        old_hash = contract.input_hash(self.context)
        self.source.write_text("documented task, release 1.2.3", encoding="utf-8")
        self.context["steps"]["documentation"] = {
            "status": "passed", "input_hash": old_hash,
            "artifacts": [{"path": "task.md", "sha256": self.digest(self.source)}],
        }
        refreshed_facts = [{"id": "F1", "text": "Documented observation", "evidence": ["task.md"]}]
        rebased = contract.checkpoint(self.context, self.root, refreshed_facts)
        self.assertNotEqual(contract.input_hash(rebased), old_hash)
        self.assertEqual(rebased["steps"]["documentation"]["status"], "passed")
        self.assertEqual(rebased["steps"]["documentation"]["input_hash"], contract.input_hash(rebased))
        self.context = rebased
        self.pass_step("html")
        result = self.run_check()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["reusable_steps"], ["documentation", "html"])

    def test_checkpoint_rejects_unrecorded_document_change(self):
        self.context["allowed_steps"] = ["documentation", "html"]
        self.pass_step("documentation")
        self.source.write_text("unrecorded edit", encoding="utf-8")
        with self.assertRaises(ValueError):
            contract.checkpoint(self.context, self.root, self.context["facts"])

    def test_checkpoint_can_register_generated_doc_source(self):
        self.context["allowed_steps"] = ["documentation", "html"]
        self.pass_step("documentation")
        generated = self.root / "doc.generated.md"
        generated.write_text("generated documentation", encoding="utf-8")
        self.context["steps"]["documentation"]["artifacts"].append(
            {"path": generated.name, "sha256": self.digest(generated)}
        )
        rebased = contract.checkpoint(
            self.context, self.root, self.context["facts"],
            [{"path": generated.name, "sha256": self.digest(generated), "role": "doc"}],
        )
        self.assertIn(generated.name, [source["path"] for source in rebased["sources"]])
        self.assertEqual(contract.preflight(rebased, self.root)["status"], "ready")

    def test_missing_jira_and_blocked_step(self):
        self.pass_step("jira")
        self.assertEqual(self.run_check()["status"], "blocked")
        self.context["steps"]["jira"]["status"] = "blocked"
        self.assertEqual(self.run_check()["status"], "blocked")

    def test_deterministic_read_only_and_help(self):
        self.context["facts"][0]["text"] = "password=not-for-output"
        before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.root.rglob("*") if path.is_file()}
        first = self.run_check()
        self.assertEqual(first, self.run_check())
        after = {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn("not-for-output", json.dumps(first))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "--help"], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--project-root", proc.stdout)


if __name__ == "__main__":
    unittest.main()
