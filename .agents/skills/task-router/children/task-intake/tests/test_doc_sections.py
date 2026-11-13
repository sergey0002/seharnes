import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "doc_sections.py"
REPO = HERE.parents[5]
JSONDOC = REPO / ".agents" / "skills" / "documentation-router" / "children" / "task-doc" / "scripts"


class DocSectionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".doc").mkdir()
        scripts_dir = self.root / ".agents/skills/documentation-router/children/task-doc/scripts"
        scripts_dir.parent.mkdir(parents=True, exist_ok=True)
        scripts_dir.symlink_to(JSONDOC, target_is_directory=True)
        (self.root / ".doc/tasks/1491").mkdir(parents=True)

    def create_task(self):
        sys.path.insert(0, str(JSONDOC))
        from jsondoc import store
        doc = {
            "schema_version": "1.0", "kind": "task", "id": "task:1491",
            "revision": 1,
            "metadata": {"task_id": "1491", "title": "Card",
                         "task_type": "bug", "doc_type": None,
                         "branch": "bugfixes/#1491", "release": None,
                         "updated_at": "2026-10-30T00:00:00Z",
                         "status": "unknown", "source_status": None},
            "summary": None, "tags": [],
            "sections": [{"id": "s1", "title": "Краткое описание",
                          "level": 2, "parent_id": None,
                          "anchor": "краткое-описание", "anchor_aliases": [],
                          "origin": "authored", "source_ids": [],
                          "body_markdown": "old"}],
            "section_order": ["s1"], "files": [], "findings": [],
            "decisions": [], "requirements": [], "progress": [],
            "stages": [], "notes": [], "relations": [], "artifacts": [],
            "checks": [], "git_events": [], "tracker": None,
            "git_state": None, "jira_report": None, "sources": [],
            "history": [],
        }
        envelope = {"schema_version": "1.0",
                    "operation_id": "create-1491",
                    "expected_revision": 0, "actor": "task-doc",
                    "reason": "тестовая задача", "operations": [],
                    "document": doc}
        store.Store(self.root, Path(".doc")).apply("task", "1491", envelope)

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root),
             "--task", "1491", *args],
            capture_output=True, text=True, timeout=120)

    def test_plan_reuses_existing_section_ids(self):
        self.create_task()
        source = self.root / "sections.md"
        source.write_text(
            "## Краткое описание\n\nnew text\n\n"
            "## Подводные камни\n\nСимптом: x\nРешение: y\n", encoding="utf-8")
        result = self.run_script("--input", str(source))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertEqual(payload["order"], ["s1", "s2"])
        envelope = json.loads(Path(payload["envelope"]).read_text(encoding="utf-8"))
        keys = [op["key"] for op in envelope["operations"]
                if op["collection"] == "sections"]
        self.assertEqual(keys, ["s1", "s2"])
        updated = envelope["operations"][0]["value"]
        self.assertEqual(updated["title"], "Краткое описание")
        self.assertEqual(updated["body_markdown"], "new text")

    def test_apply_renders_doc(self):
        self.create_task()
        source = self.root / "sections.md"
        source.write_text("## Краткое описание\n\nnew text\n", encoding="utf-8")
        result = self.run_script("--input", str(source), "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "applied")
        doc_md = (self.root / ".doc/tasks/1491/doc.md").read_text(encoding="utf-8")
        self.assertIn("new text", doc_md)
        self.assertNotIn("old", doc_md)

    def test_finalize_blocks_before_any_mutation_when_identity_unavailable(self):
        self.create_task()
        source = self.root / "sections.md"
        source.write_text("## Краткое описание\n\nnew text\n", encoding="utf-8")
        task_dir = self.root / ".doc/tasks/1491"
        before = {str(p.relative_to(task_dir)): p.read_bytes() for p in task_dir.rglob("*") if p.is_file()}
        result = self.run_script("--input", str(source), "--finalize")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["identity"]["status"], "unavailable")
        after = {str(p.relative_to(task_dir)): p.read_bytes() for p in task_dir.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_finalize_blocks_mismatch_before_any_mutation(self):
        self.create_task()
        source = self.root / "sections.md"
        source.write_text("## Краткое описание\n\nnew text\n", encoding="utf-8")
        task_dir = self.root / ".doc/tasks/1491"
        (task_dir / "task.md").write_text("task", encoding="utf-8")
        identity = self.root / ".agents/skills/documentation-router/children/project-doc/scripts/task-identity.py"
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text('import sys\nprint(\'{"status":"mismatch","ok":false,"checks":[],"warnings":[]}\')\nsys.exit(2)\n', encoding="utf-8")
        before = {str(p.relative_to(task_dir)): p.read_bytes() for p in task_dir.rglob("*") if p.is_file()}
        result = self.run_script("--input", str(source), "--finalize")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["identity"]["status"], "mismatch")
        after = {str(p.relative_to(task_dir)): p.read_bytes() for p in task_dir.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_json_map_is_primary_input(self):
        self.create_task()
        source = self.root / "sections.json"
        source.write_text(json.dumps({
            "sections": {
                "Краткое описание": "new text",
                "Подводные камни": "Симптом: x\nРешение: y",
            }
        }, ensure_ascii=False), encoding="utf-8")
        result = self.run_script("--input", str(source), "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "applied")
        self.assertEqual(payload["sections"],
                         ["Краткое описание", "Подводные камни"])
        doc_md = (self.root / ".doc/tasks/1491/doc.md").read_text(encoding="utf-8")
        self.assertIn("Симптом: x", doc_md)

    def test_json_list_with_source_ids(self):
        self.create_task()
        source = self.root / "sections.json"
        source.write_text(json.dumps({"sections": [{
            "title": "Краткое описание",
            "body": "text",
            "source_ids": ["SRC-1"],
        }]}, ensure_ascii=False), encoding="utf-8")
        result = self.run_script("--input", str(source))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        envelope = json.loads(Path(payload["envelope"]).read_text(encoding="utf-8"))
        value = envelope["operations"][0]["value"]
        self.assertEqual(value["source_ids"], ["SRC-1"])

    def test_json_empty_body_is_error(self):
        self.create_task()
        source = self.root / "sections.json"
        source.write_text(json.dumps({"sections": {"Пусто": ""}}),
                          encoding="utf-8")
        result = self.run_script("--input", str(source))
        self.assertEqual(result.returncode, 2)
        self.assertIn("body must not be empty", json.loads(result.stdout)["error"])

    def test_fence_is_not_a_section(self):
        source = self.root / "sections.md"
        source.write_text(
            "## Один\n\n```\n## not a heading\n```\n\n## Два\n\nbody\n",
            encoding="utf-8")
        self.create_task()
        result = self.run_script("--input", str(source))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["sections"], ["Один", "Два"])
        envelope = json.loads(Path(payload["envelope"]).read_text(encoding="utf-8"))
        body = [op for op in envelope["operations"]
                if op["collection"] == "sections"][0]["value"]["body_markdown"]
        self.assertIn("## not a heading", body)


if __name__ == "__main__":
    unittest.main()
