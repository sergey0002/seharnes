"""Deterministic acceptance tests for aggregate, Jira profile and intake."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore.aggregate import Aggregate
from tdcore.contracts import validate_contract_file
from tdcore.documentation import DocumentationWorkspace
from tdcore.errors import SkillError
import tdcore.importer as importer_module
from tdcore.importer import import_payload, read_payload
from tdcore.intake import (AUDIT_SCHEMA, DraftStore, validate_audit,
                           validate_intake_draft)
from tdcore.queue import Queue, Registry
from tdcore.typedefs import TypeIndex
from tdcore.validate import Validator


class VerticalSliceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _queue(self, root, alias="main"):
        Registry(str(root)).register(alias, str(root / "tasks" / alias))
        queue = Queue(str(root), alias)
        queue.init()
        return queue

    def test_aggregate_recursive_namespaces_provenance_and_stale_verify(self):
        child = self.root / "services" / "billing"
        (child / ".todone").mkdir(parents=True)
        (child / ".todone" / "workspace.json").write_text(json.dumps({
            "schema": "WORKSPACE-1", "workspace_id": "billing", "kind": "service",
            "docs_path": "docs", "aggregate": True, "queues": ["main"]
        }), encoding="utf-8")
        queue = self._queue(child)
        first = queue.create("Billing task", "default")
        second = queue.create("Child", "default", parent=first.id, depends_on=[first.id])
        docs = DocumentationWorkspace(str(child))
        docs.init(workspace_id="billing", product_id="product")
        docs.write_module("entity/order", "entity", "# Order", source_task_refs=[first.id],
                          status="active", by="fixture")
        (child / "docs" / "unknown.bin").write_bytes(b"opaque")
        before = {str(path): path.read_bytes() for path in (Path(first.path), Path(second.path))}

        result = Aggregate(str(self.root)).scan(archive=True)
        manifest = result["manifest"]
        self.assertEqual(manifest["schema"], "AGGREGATE-1")
        self.assertEqual(manifest["completeness"]["status"], "complete")
        refs = {item["global_ref"] for item in result["tasks"]}
        self.assertEqual(refs, {"billing:main:T-001", "billing:main:T-002"})
        self.assertTrue(all(item["source_todone_path"] == "services/billing/.todone"
                            for item in result["tasks"]))
        self.assertIn("billing:entity/order", {item["global_ref"] for item in result["documents"]})
        self.assertTrue(any(item["status"] == "unknown_document" for item in result["unknowns"]))
        self.assertTrue(any(item["kind"] == "parent" and item["resolved"]
                            for item in result["relations"]))
        self.assertTrue(any(item["kind"] == "documents" for item in result["relations"]))
        self.assertEqual(before, {str(path): path.read_bytes() for path in (Path(first.path), Path(second.path))})
        self.assertTrue(Aggregate(str(self.root)).verify()["valid"])

        Path(first.path).write_text(Path(first.path).read_text(encoding="utf-8") + "\n", encoding="utf-8")
        stale = Aggregate(str(self.root)).verify()
        self.assertFalse(stale["valid"])
        self.assertEqual(stale["stale"][0]["global_ref"], "billing:main:T-001")
        second_run = Aggregate(str(self.root)).scan()["manifest"]["aggregate_run_id"]
        diff = Aggregate(str(self.root)).diff(manifest["aggregate_run_id"], second_run)
        self.assertIn("billing:main:T-001", diff["changed"])
        self.assertEqual(validate_contract_file(
            str(self.root / ".todone" / "aggregate" / "manifest.json"))[1], [])

    def test_jira_profile_is_lossless_normalized_and_idempotent(self):
        source_path = ROOT / "assets" / "fixtures" / "runtime" / "jira-issue-rich.json"
        queue = self._queue(self.root, "site")
        payload = read_payload("jira", str(source_path))
        first = import_payload(queue, payload, "fixture")
        record = first["record"]
        self.assertEqual(record.source["raw"], source_path.read_text(encoding="utf-8"))
        self.assertEqual(record.source["revision"], 1)
        projection_path = Path(record.folder) / "artifacts" / "jira-projection.json"
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        self.assertEqual(projection["schema"], "JIRA-MIRROR-1")
        self.assertEqual(projection["normalized"]["key"], "PROJ-7")
        self.assertEqual(projection["normalized"]["description"]["text"], "Export @alice\nas CSV")
        self.assertEqual(projection["dates"]["created"]["value"], "2026-01-02T03:04:05.000Z")
        self.assertEqual([item["id"] for item in projection["normalized"]["fix_versions"]], ["10021", "10022"])
        self.assertEqual(projection["attachments"][0]["filename"], "example.csv")
        self.assertEqual(projection["links"]["issue"][0]["issue"]["key"], "PROJ-8")
        self.assertEqual(projection["links"]["remote"][0]["id"], "r-1")
        self.assertEqual(projection["comments"][0]["body_text"], "Please verify")
        self.assertEqual(projection["custom_fields"]["customfield_10001"]["raw"], "keep me")
        self.assertIn("provider_unknown_field", projection["unknown_fields"]["fields"])
        self.assertIn("unmodeled_top_level", projection["unknown_fields"]["top_level"])
        self.assertTrue(projection["completeness"]["raw_preserved"])
        self.assertEqual(record.extra["external"]["identity"]["key"], "PROJ-7")
        self.assertEqual(Validator(TypeIndex(str(ROOT / "assets" / "types"))).record(record, strict=True), [])
        self.assertEqual(json.loads((Path(record.folder) / "artifacts" / "jira-snapshots" / "revision-001.json").read_text()),
                         json.loads(source_path.read_text(encoding="utf-8")))
        issues = validate_contract_file(str(projection_path))[1]
        self.assertFalse([item for item in issues if item.is_error])

        repeat = import_payload(queue, read_payload("jira", str(source_path)), "fixture")
        self.assertEqual(repeat["new_comments"], [])
        self.assertEqual(repeat["revision"], 2)
        self.assertEqual(len(queue.resolve(record.id).comments), 1)
        self.assertTrue((Path(record.folder) / "artifacts" / "jira-snapshots" / "revision-002.json").is_file())

        changed = json.loads(source_path.read_text(encoding="utf-8"))
        changed["fields"]["comment"]["comments"][0]["body"]["content"][0]["content"][0]["text"] = "Updated"
        changed_path = self.root / "changed.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2), encoding="utf-8")
        updated = import_payload(queue, read_payload("jira", str(changed_path), external_id="10001"), "fixture")
        self.assertEqual(updated["revision"], 3)
        self.assertEqual(updated["new_comments"], [])
        self.assertEqual(updated["updated_comments"][0]["text"], "Updated")
        self.assertEqual(len(queue.resolve(record.id).comments), 1)

    def test_jira_import_rolls_back_new_and_existing_mirrors_on_write_failure(self):
        source_path = ROOT / "assets" / "fixtures" / "runtime" / "jira-issue-rich.json"
        queue = self._queue(self.root, "site")
        payload = read_payload("jira", str(source_path))
        first = import_payload(queue, payload, "fixture")
        record = first["record"]
        folder = Path(record.folder)
        before_tree = {str(path.relative_to(folder)): path.read_bytes()
                       for path in folder.rglob("*") if path.is_file()}
        before_index = Path(queue.index_path).read_bytes()

        changed = json.loads(source_path.read_text(encoding="utf-8"))
        changed["fields"]["summary"] = "write failure"
        changed_path = self.root / "changed-for-rollback.json"
        changed_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(importer_module, "_atomic_json",
                               side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                import_payload(queue, read_payload("jira", str(changed_path)), "fixture")
        restored = queue.resolve(record.id)
        self.assertEqual(restored.source["revision"], 1)
        self.assertEqual(restored.source["raw"], source_path.read_text(encoding="utf-8"))
        after_tree = {str(path.relative_to(folder)): path.read_bytes()
                      for path in folder.rglob("*") if path.is_file()}
        self.assertEqual(after_tree, before_tree)
        self.assertEqual(Path(queue.index_path).read_bytes(), before_index)
        self.assertFalse(any(path.name.endswith((".tmp", ".rollback.tmp"))
                           for path in folder.rglob("*")))

        fresh_root = self.root / "fresh"
        fresh_queue = self._queue(fresh_root, "site")
        with mock.patch.object(importer_module, "_atomic_text",
                               side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                import_payload(fresh_queue, payload, "fixture")
        self.assertEqual(fresh_queue.records, [])
        self.assertEqual(fresh_queue.index.items, [])
        self.assertFalse((fresh_root / "tasks" / "site" / ".todone" / "data").exists()
                         and list((fresh_root / "tasks" / "site" / ".todone" / "data").iterdir()))

    def test_jira_legacy_snapshot_shape_remains_compatible(self):
        queue = self._queue(self.root, "site")
        legacy = {"id": "9001", "key": "LEG-1", "self": "https://jira/LEG-1",
                  "fields": {"summary": "Legacy issue", "status": {"name": "Open"},
                              "labels": ["old"]}}
        path = self.root / "legacy-jira.json"
        raw = json.dumps(legacy, ensure_ascii=False, separators=(",", ":"))
        path.write_text(raw, encoding="utf-8")
        result = import_payload(queue, read_payload("jira", str(path)), "compat")
        record = result["record"]
        projection = json.loads((Path(record.folder) / "artifacts" /
                                 "jira-projection.json").read_text(encoding="utf-8"))
        self.assertEqual(projection["normalized"]["key"], "LEG-1")
        self.assertEqual(projection["normalized"]["summary"], "Legacy issue")
        self.assertEqual(projection["completeness"]["resources"]["comments"]["state"],
                         "not_requested")
        self.assertEqual(record.status, "mirror")
        self.assertEqual(record.source["raw"], raw)
        self.assertFalse([item for item in validate_contract_file(
            str(Path(record.folder) / "artifacts" / "jira-projection.json"))[1]
                          if item.is_error])

    def test_intake_persists_provenance_one_question_finalize_and_audit(self):
        queue = self._queue(self.root, "site")
        store = DraftStore(str(self.root), clock=lambda: "2026-01-01T00:00:00Z")
        draft = store.start("Export task", "alice", queue="site", session_id="session-1")
        text_input = self.root / "requirements.txt"
        text_input.write_text("CSV requirement", encoding="utf-8")
        screenshot = self.root / "requirements.png"
        screenshot.write_bytes(b"PNG fixture")
        first_capture = store.capture_file(draft, str(text_input), actor="alice")
        second_capture = store.capture_file(draft, str(screenshot), actor="alice")
        self.assertEqual(first_capture["provenance"]["source_kind"], "file")
        self.assertEqual(second_capture["provenance"]["source_kind"], "screenshot")
        self.assertTrue((self.root / first_capture["provenance"]["stored_ref"]).is_file())
        self.assertTrue((self.root / second_capture["provenance"]["stored_ref"]).is_file())
        draft.add_entry("proposed", "CSV или JSON", "message", "conversation:2", actor="alice")
        draft.add_option("CSV", ["простая интеграция"], ["меньше типов"], actor="alice")
        with self.assertRaises(SkillError) as caught:
            draft.ask("What first?", choices=["csv", "json"], actor="alice")
            draft.ask("What second?", choices=["yes", "no"], actor="alice")
        self.assertEqual(caught.exception.code, "INTAKE_QUESTION_SEQUENCE")
        draft.answer("Q-001", "csv", actor="alice")
        draft.fix("Пользователь должен скачать CSV", actor="alice")
        loaded = DraftStore(str(self.root), clock=lambda: "2026-01-01T00:00:00Z").load("session-1")
        self.assertEqual(loaded.data["entries"][-1]["status"], "accepted")
        self.assertTrue(loaded.data["provenance"])
        with self.assertRaises(SkillError) as caught:
            loaded.finalize(queue, "feature", "Export", {"problem": "x"}, actor="alice")
        self.assertEqual(caught.exception.code, "INTAKE_FINALIZE_INCOMPLETE")
        task = loaded.finalize(queue, "feature", "Export", {
            "problem": "Пользователь не может скачать CSV",
            "goals": ["дать download"], "acceptance": ["CSV скачивается"],
            "verify": ["python3 -m unittest"], "files_hint": ["scripts/tdcore/intake.py"]
        }, actor="alice")
        target = queue.resolve(task.id)
        (self.root / "intake.py").write_text("# fixture", encoding="utf-8")
        target.add_ref("file", "intake.py", "runtime intake implementation")
        queue.save(target)
        audit = loaded.audit(queue, task.id, actor="alice")
        self.assertEqual(audit["schema"], AUDIT_SCHEMA)
        self.assertEqual(audit["verdict"], "approved")
        self.assertEqual(audit["remaining_questions"], [])
        self.assertTrue(audit["audit_task_ref"])
        self.assertFalse([item for item in validate_audit(audit) if item.is_error])
        self.assertEqual(validate_intake_draft(store.load("session-1").data), [])

    def test_contract_fixtures_cover_new_envelopes(self):
        valid = ("intake.valid.json", "task-audit.valid.json")
        for name in valid:
            _, issues = validate_contract_file(str(ROOT / "assets" / "fixtures" / "runtime" / name))
            self.assertFalse([item for item in issues if item.is_error], name)
        _, issues = validate_contract_file(str(ROOT / "assets" / "fixtures" / "runtime" / "intake.invalid-two-open.json"))
        self.assertTrue(any(item.code == "INTAKE_QUESTION_SEQUENCE" for item in issues))
        _, issues = validate_contract_file(str(ROOT / "assets" / "fixtures" / "runtime" / "jira-projection.invalid.json"))
        self.assertTrue(any(item.code == "JIRA_MIRROR_INVALID" for item in issues))


if __name__ == "__main__":
    unittest.main()
