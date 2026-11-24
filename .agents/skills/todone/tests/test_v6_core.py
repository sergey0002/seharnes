"""Приёмочные тесты новой архитектуры v0.6.

Тесты работают на чистой временной папке: старую markdown-раскладку они не
читают. Проверяется предметное поведение, а не размер текста и не внутренний
порядок частных методов.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore import schema
from tdcore.brief import Brief
from tdcore.digest import Digest, stale_issues
from tdcore.errors import SkillError
from tdcore.flow import FlowIndex, FlowState
from tdcore.gates import close_issues
from tdcore.importer import import_payload, read_payload
from tdcore.link import Linker, broken_links
from tdcore.queue import Queue, Registry
from tdcore.record import Record, new_task
from tdcore.report import render_show
from tdcore.store import RecordStore
from tdcore.typedefs import TypeIndex
from tdcore.validate import Validator

ROOT = Path(__file__).resolve().parents[1]
TYPE_ROOT = ROOT / "assets" / "types"
FLOW_ROOT = ROOT / "assets" / "flows"


class V6TestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = Registry(str(self.root))
        self.registry.register("site", str(self.root / "tasks" / "site"))
        self.queue = Queue(str(self.root), "site")
        self.types = TypeIndex(str(TYPE_ROOT))

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_creation_writes_record_and_index_without_body_copy(self):
        record = self.queue.create("Проверить очередь", "default", priority=1)
        self.assertTrue(Path(record.path).is_file())
        self.assertEqual(record.id, "T-001")
        row = self.queue.index.find(record.id)
        self.assertEqual(row["path"], "data/T-001-default/task.json")
        self.assertNotIn("problem", row)
        self.assertEqual(self.queue.sync_issues(), [])
        os.unlink(self.queue.index_path)
        self.queue._index = None
        self.queue.rebuild_index()
        self.assertEqual(self.queue.index.find(record.id)["status"], "draft")

    def test_status_parked_is_a_record_status_not_a_notes_entity(self):
        record = self.queue.create("Отложить", "default", status="parked")
        self.assertIn(record.status, schema.STATUSES)
        self.assertEqual(self.queue.rows()[0]["status"], "parked")
        self.assertEqual(self.queue.children_of(record.id), [])

    def test_type_fields_are_data_and_no_text_length_is_checked(self):
        record = self.queue.create("Дефект", "fix")
        record.data["extra"] = {"reproduce": "x" * 5000}
        issues = Validator(self.types).record(record, strict=False)
        codes = {item.code for item in issues}
        self.assertNotIn("TYPE_FIELD_INVALID", codes)
        self.assertNotIn("TYPE_FIELD_MISSING", codes)
        typedef = self.types.get("fix")
        self.assertTrue(typedef.field("reproduce"))

    def test_comment_text_has_no_hard_ceiling_and_handoff_is_always_selected(self):
        record = Record(new_task("T-001", "Лента", "default"))
        record.add_comment("x" * 5000, "a", kind="human")
        record.add_comment("важная передача", "a", kind="handoff")
        record.add_comment("обычная", "b", kind="agent")
        picked, rest = record.tail(1)
        self.assertEqual([item["kind"] for item in picked], ["handoff", "agent"])
        self.assertEqual(rest, 1)
        self.assertGreaterEqual(record.sizes()["comments_chars"], 5000 + len("важная передача") + len("обычная"))
        text = "\n".join(render_show(record, "handoff", settings={"handoff_last": 1}))
        self.assertIn("важная передача", text)
        self.assertIn("обычная", text)
        self.assertNotIn("x" * 5001, text)

    def test_read_modes_keep_body_and_offer_full_lenta(self):
        record = Record(new_task("T-001", "Чтение", "default"))
        record.add_comment("реплика", "a", kind="human")
        body = "\n".join(render_show(record, "body"))
        full = "\n".join(render_show(record, "full"))
        self.assertIn('"title": "Чтение"', body)
        self.assertNotIn("реплика", body)
        self.assertIn("реплика", full)
        self.assertIn("размеры:", full)

    def test_mirror_import_is_idempotent_and_new_comment_only_prints_child(self):
        source = self.root / "jira.json"
        source.write_text(json.dumps({
            "id": "P-1", "fields": {"summary": "Задача",
            "comment": {"comments": [{"id": "c1", "body": "первый",
                                           "created": "2026-01-01", "author": "Анна"}]}}
        }, ensure_ascii=False), encoding="utf-8")
        payload = read_payload("jira", str(source))
        first = import_payload(self.queue, payload, "lead")
        self.assertTrue(first["created"])
        self.assertEqual(first["revision"], 1)
        second = import_payload(self.queue, payload, "lead")
        self.assertFalse(second["created"])
        self.assertEqual(second["new_comments"], [])
        data = json.loads(Path(first["record"].path).read_text(encoding="utf-8"))
        self.assertEqual(data["source"]["raw"], source.read_text(encoding="utf-8"))
        modified = json.loads(source.read_text(encoding="utf-8"))
        modified["fields"]["comment"]["comments"].append({
            "id": "c2", "body": "второй", "created": "2026-01-02", "author": "Пётр"})
        source.write_text(json.dumps(modified, ensure_ascii=False), encoding="utf-8")
        third = import_payload(self.queue, read_payload("jira", str(source)), "lead")
        self.assertEqual(third["revision"], 3)
        self.assertEqual(len(third["new_comments"]), 1)
        self.assertEqual(len(third["draft_commands"]), 1)
        mirror = self.queue.resolve(first["record"].id)
        self.assertTrue(mirror.is_mirror)
        # Record is a data object; readonly is enforced at the CLI boundary.
        mirror.add_ref("file", "x.py", "низкоуровневый объект допускает данные")
        self.assertEqual(mirror.refs[0]["path"], "x.py")

    def test_linker_keeps_child_content_out_of_parent(self):
        parent = self.queue.create("Родитель", "default")
        child = self.queue.create("Ребёнок", "research", parent=parent.id)
        linker = Linker(self.queue)
        ref = linker.link(parent.id, child.id, "исследование стадии", by="lead")
        self.assertEqual(ref["kind"], "queue")
        fresh = self.queue.resolve(parent.id)
        self.assertNotIn(child.title, json.dumps(fresh.data, ensure_ascii=False))
        root, by_parent = linker.tree(parent.id)
        self.assertEqual(root.id, parent.id)
        self.assertEqual([item.id for item in by_parent[parent.id]], [child.id])
        self.assertEqual(broken_links(self.queue), [])

    def test_digest_contains_task_toc_and_verbatim_comments(self):
        record = self.queue.create("Большая запись", "default")
        record.add_comment("строка\nс продолжением", "lead", kind="human")
        path, text = Digest(record, self.queue.settings).write()
        self.assertTrue(Path(path).is_file())
        self.assertIn("## Тело записи", text)
        self.assertIn("## Оглавление ленты", text)
        self.assertIn("## Лента дословно", text)
        self.assertIn("с продолжением", text)
        self.assertEqual(stale_issues(record), [])

    def test_flow_definitions_validate_and_state_lives_in_index(self):
        flows = FlowIndex(str(FLOW_ROOT))
        self.assertEqual(set(flows.names()), {"jira-feature", "jira-fix", "release-testing",
                                              "issue-delivery"})
        self.assertEqual(flows.validate_all([item.id for item in self.types.all()]), [])
        mirror = self.queue.create("Jira", "mirror", status="mirror")
        mirror.data["source"] = {"system": "jira", "id": "P-2", "url": None,
                                  "imported_at": "2026-01-01", "by": "lead",
                                  "raw": "сырой вход", "revision": 1}
        self.queue.save(mirror)
        state = FlowState(self.queue, flows, self.types)
        created, remaining = state.start("jira-fix", mirror.id, by="lead")
        self.assertEqual(len(created), 1)
        self.assertIn("research", remaining)
        row = self.queue.index.find(created[0].id)
        self.assertEqual((row["flow"], row["flow_step"]), ("jira-fix", "intake"))
        mirror_after = self.queue.resolve(mirror.id)
        self.assertEqual(mirror_after.refs, [])
        self.assertEqual(mirror_after.comments, [])

    def test_source_and_type_are_not_mutable_by_record_validator_contract(self):
        record = self.queue.create("Тип", "default")
        record.data["kind"] = "bad type!"
        record.data["id"] = "X-999"
        issues = Validator(self.types).record(record, strict=False)
        codes = {item.code for item in issues}
        self.assertIn("TYPE_UNKNOWN", codes)
        self.assertIn("ID_IMMUTABLE", codes)

    def test_flow_waits_for_closed_research_before_test_prep_and_planning(self):
        flows = FlowIndex(str(FLOW_ROOT))
        mirror = self.queue.create("Источник", "mirror", status="mirror")
        state = FlowState(self.queue, flows, self.types)
        created, _ = state.start("issue-delivery", mirror.id, by="lead")
        self.assertEqual([self.queue.index.find(item.id)["flow_step"]
                          for item in created], ["intake"])
        # The first result is marked in the index after creation; it must not
        # unlock research while it is still a draft.
        next_created, _ = state.start("issue-delivery", mirror.id, by="lead")
        self.assertEqual(next_created, [])
        intake = self.queue.resolve(created[0].id)
        intake.data["extra"] = {
            "raw_gaps": "нет пробелов",
            "assumptions": "нет допущений",
            "draft_child": "research",
        }
        intake.add_ref("file", "README.md", "исходный контекст", by="lead")
        intake.add_comment("готово исследователю", "lead", kind="handoff")
        intake.data["status"] = "closed"
        self.queue.save(intake)
        next_created, _ = state.start("issue-delivery", mirror.id, by="lead")
        self.assertEqual([self.queue.index.find(item.id)["flow_step"]
                          for item in next_created], ["research"])
        research = next_created[0]
        research.add_ref("file", "module.py", "исследованное место", by="lead")
        research.add_comment("готово test-prep", "lead", kind="handoff")
        research.data["status"] = "closed"
        self.queue.save(research)
        test_prep, _ = state.start("issue-delivery", mirror.id, by="lead")
        self.assertEqual([self.queue.index.find(item.id)["flow_step"]
                          for item in test_prep], ["test-prep"])

    def test_flow_condition_blocks_unapproved_plan_audit(self):
        flows = FlowIndex(str(FLOW_ROOT))
        flow = flows.get("issue-delivery")
        audit = self.queue.create("Аудит", "plan-audit")
        audit.data["extra"] = {"verdict": "changes_required", "findings": "AC-2"}
        audit.data["status"] = "closed"
        self.queue.save(audit)
        state = FlowState(self.queue, flows, self.types)
        step = flow.step("implementation")
        with self.assertRaises(SkillError) as caught:
            state._check_requires(flow, [{"step": "plan-audit", "record": audit}], step)
        self.assertEqual(caught.exception.code, "FLOW_CONDITION_UNMET")

    def test_flow_fanout_creates_tasks_and_waits_for_all_closed(self):
        overlay = self.root / ".todone" / "flows" / "dynamic-test"
        overlay.mkdir(parents=True)
        (overlay / "flow.json").write_text(json.dumps({
            "schema": "FLOW-2", "id": "dynamic-test", "name": "Dynamic test",
            "entry": "source", "max_batch": 2,
            "steps": [
                {"id": "seed", "type": "default", "input_from": [],
                 "output": ["items"]},
                {"id": "slice", "type": "feature", "input_from": ["seed"],
                 "output": [], "fan_out": {
                     "items_from": ["seed", "items"], "item_id": "slice_id",
                     "task_type_from": "type", "title_from": "title",
                     "join": "all_closed"}},
                {"id": "done", "type": "testing", "input_from": ["slice"],
                 "output": []},
            ]
        }, ensure_ascii=False), encoding="utf-8")
        (overlay / "instruction.md").write_text("# dynamic", encoding="utf-8")
        flows = FlowIndex(str(FLOW_ROOT), str(self.root / ".todone" / "flows"))
        state = FlowState(self.queue, flows, self.types)
        source = self.queue.create("Источник", "default")
        created, _ = state.start("dynamic-test", source.id, by="lead")
        seed = created[0]
        seed.data["extra"] = {"items": [
            {"slice_id": "S-1", "type": "feature", "title": "Первый slice"},
            {"slice_id": "S-2", "type": "fix", "title": "Второй slice"},
            {"slice_id": "S-3", "type": "feature", "title": "Третий slice"},
        ]}
        seed.data["status"] = "closed"
        self.queue.save(seed)
        first, _ = state.start("dynamic-test", source.id, by="lead")
        self.assertEqual([item.title for item in first], ["Первый slice", "Второй slice"])
        self.assertEqual({self.queue.index.find(item.id)["flow_item"] for item in first},
                         {"S-1", "S-2"})
        for item in first:
            item.data["status"] = "closed"
            self.queue.save(item)
        second, _ = state.start("dynamic-test", source.id, by="lead")
        self.assertEqual([item.title for item in second], ["Третий slice"])
        self.assertEqual(self.queue.index.find(second[0].id)["flow_item"], "S-3")
        self.assertEqual(state.start("dynamic-test", source.id)[0], [])
        second[0].data["status"] = "closed"
        self.queue.save(second[0])
        final, _ = state.start("dynamic-test", source.id, by="lead")
        self.assertEqual([item.kind for item in final], ["testing"])
        self.assertEqual(self.queue.index.find(final[0].id)["flow_revision"], 1)

    def test_flow_revision_route_reopens_logical_plan_without_work(self):
        overlay = self.root / ".todone" / "flows" / "revision-test"
        overlay.mkdir(parents=True)
        (overlay / "flow.json").write_text(json.dumps({
            "schema": "FLOW-2", "id": "revision-test", "name": "Revision test",
            "entry": "source", "steps": [
                {"id": "plan", "type": "planning", "input_from": [], "output": []},
                {"id": "audit", "type": "plan-audit", "input_from": ["plan"],
                 "output": [], "routes": {"changes_required": "work"},
                 "decision_tree": {
                     "schema": "DECISION-TREE-1", "id": "revision-route",
                     "version": 1, "root": "verdict", "nodes": [{
                         "id": "verdict", "field": "verdict", "routes": {
                             "approved": "work", "changes_required": "plan.revision",
                             "blocked": "human-decision"}}]}},
                {"id": "work", "type": "feature", "input_from": ["audit"],
                 "output": [], "requires": [
                     {"from": "audit", "field": "verdict", "equals": "approved"}
                 ]},
            ]
        }, ensure_ascii=False), encoding="utf-8")
        (overlay / "instruction.md").write_text("# revision", encoding="utf-8")
        flows = FlowIndex(str(FLOW_ROOT), str(self.root / ".todone" / "flows"))
        state = FlowState(self.queue, flows, self.types)
        source = self.queue.create("Источник", "default")

        plan, _ = state.start("revision-test", source.id)
        plan[0].data["status"] = "closed"
        self.queue.save(plan[0])
        audit, _ = state.start("revision-test", source.id)
        audit[0].data["status"] = "closed"
        audit[0].data["extra"] = {"verdict": "changes_required"}
        self.queue.save(audit[0])

        revision, _ = state.start("revision-test", source.id)
        self.assertEqual([item.kind for item in revision], ["planning"])
        self.assertEqual(self.queue.index.find(revision[0].id)["flow_revision"], 2)
        self.assertEqual(self.queue.index.find(revision[0].id)["flow_step"], "plan")
        self.assertEqual(state.start("revision-test", source.id)[0], [])

        revision[0].data["status"] = "closed"
        self.queue.save(revision[0])
        audit2, _ = state.start("revision-test", source.id)
        self.assertEqual([item.kind for item in audit2], ["plan-audit"])
        self.assertEqual(self.queue.index.find(audit2[0].id)["flow_revision"], 2)
        audit2[0].data["status"] = "closed"
        audit2[0].data["extra"] = {"verdict": "approved"}
        self.queue.save(audit2[0])
        work, _ = state.start("revision-test", source.id)
        self.assertEqual([item.kind for item in work], ["feature"])
        self.assertEqual(self.queue.index.find(work[0].id)["flow_revision"], 2)

    def test_project_flow_overlay_replaces_builtin_and_instruction_follows_it(self):
        overlay = self.root / ".todone" / "flows" / "jira-fix"
        overlay.mkdir(parents=True)
        payload = json.loads((FLOW_ROOT / "jira-fix" / "flow.json").read_text(encoding="utf-8"))
        payload["name"] = "Проектный override"
        (overlay / "flow.json").write_text(json.dumps(payload), encoding="utf-8")
        (overlay / "instruction.md").write_text("# override", encoding="utf-8")
        flows = FlowIndex(str(FLOW_ROOT), str(self.root / ".todone" / "flows"))
        flow = flows.get("jira-fix")
        self.assertEqual(flow.name, "Проектный override")
        self.assertEqual(flow.instruction_path(), str(overlay / "instruction.md"))


if __name__ == "__main__":
    unittest.main()
