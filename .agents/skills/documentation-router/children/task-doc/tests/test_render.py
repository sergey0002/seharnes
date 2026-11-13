"""J03 render tests: idempotent MD view, VIEW_CONFLICT, anchors (UT16-UT18)."""

import copy
import hashlib
import json
import unittest
from pathlib import Path

import support
from jsondoc import render


def sha(data):
    return hashlib.sha256(data).hexdigest()


def view_file(docs, task_id):
    return docs / "tasks" / str(task_id) / "doc.md"


def receipt_file(docs, task_id):
    return docs / "tasks" / str(task_id) / "_jsondoc" / "receipt.json"


def add_source(doc):
    doc["sources"].append({
        "id": "src:1", "kind": "code", "path": "src/Service.php",
        "pointer": None, "sha256": None, "revision": None,
        "observed_at": None, "observation": None, "availability": "present"})


def add_file(doc):
    doc["files"].append({
        "id": "file:1", "path": "src/Service.php", "role": "бизнес-логика",
        "change": "edited", "state": "current", "source_ids": ["src:1"],
        "revision": None, "ranges": [], "previous_path": None})


def add_finding(doc):
    doc["findings"].append({
        "id": "find:1", "kind": "pitfall", "title": "Двойная архивация",
        "statement": "Повторный запуск создаёт дубль.",
        "symptom": "два файла в архиве", "cause": "нет блокировки",
        "resolution": "добавлена блокировка", "status": "observed",
        "severity": "high", "file_ids": ["file:1"],
        "source_ids": ["src:1"], "superseded_by": None, "section_id": None})


def add_section(doc):
    doc["sections"].append({
        "id": "s-arch", "title": "Архитектура решения", "level": 3,
        "parent_id": None, "anchor": "архитектура-решения",
        "anchor_aliases": [], "body_markdown": "Текст **про** архитектуру.",
        "source_ids": ["src:1"], "origin": "authored"})
    doc["section_order"] = ["s-arch"]


def rich_task(task_id="2612"):
    doc = support.minimal_task(task_id)
    add_source(doc)
    add_file(doc)
    add_finding(doc)
    doc["decisions"].append({
        "id": "dec:1", "title": "Идемпотентность",
        "context": "нужен стабильный вывод", "choice": "канонический JSON",
        "alternatives": [], "status": "accepted", "source_ids": ["src:1"],
        "superseded_by": None, "section_id": None})
    doc["relations"].append({
        "id": "rel:1",
        "target": {"document_id": "task:1234", "record_id": None,
                   "anchor": None},
        "kind": "related", "reason": "общий сервис", "source_ids": ["src:1"],
        "status": "confirmed", "availability": "present"})
    doc["tags"].append({
        "tag_id": "domain:orders", "reason": "затронут домен заказов",
        "status": "confirmed", "source_ids": ["src:1"]})
    doc["stages"].append({
        "id": "stage:1", "number": 1, "title": "Подготовка",
        "status": "implemented", "placeholder": False, "trigger": None,
        "depends_on": [], "superseded_by": None, "plan_artifact_id": None,
        "diff_artifact_ids": [], "diff_manifest_id": None,
        "test_artifact_ids": [], "test_run_ids": [], "documentation_refs": [],
        "requirement_ids": [], "source_ids": ["src:1"]})
    doc["git_events"].append({
        "id": "git:1", "action": "commit", "commit": "abc1234def",
        "branch": "features/#2612", "remote": None, "source_ids": ["src:1"],
        "observed_at": "2026-09-25T10:00:00Z"})
    doc["history"].append({
        "id": "h:1", "at": "2026-09-25T10:00:00Z", "actor": "task-doc",
        "summary": "документ создан", "source_ids": []})
    add_section(doc)
    return doc


def tracked_task(task_id="2615"):
    doc = support.minimal_task(task_id)
    add_source(doc)
    doc["tracker"] = {
        "issue_key": "CT-{0}".format(task_id),
        "exported_at": "2026-09-25T12:00:00Z", "exporter": "gototask",
        "availability": "present", "snapshot": {"summary": "x"},
        "source_ids": []}
    doc["git_state"] = {
        "checked_at": "2026-09-25T12:00:00Z", "commit": "abc1234def",
        "pushed_to": ["origin/features/#{0}".format(task_id)],
        "contained_in": ["origin/release/5.6.1"],
        "release_branches": ["release/5.6.1"], "not_pushed_refs": [],
        "fetch_status": "fresh", "source_ids": []}
    doc["jira_report"] = {
        "text": "Сделана архивация ОИС.",
        "updated_at": "2026-09-25T12:00:00Z", "release": "5.6.1",
        "source_ids": []}
    return doc


def arch_doc():
    doc = support.minimal_task()
    doc["kind"] = "architecture"
    doc["id"] = "arch:orders"
    doc["metadata"]["task_id"] = None
    doc["metadata"]["title"] = "Заказы"
    doc["metadata"]["branch"] = None
    doc["metadata"]["release"] = None
    return doc


class RenderMarkdownTests(unittest.TestCase):
    def test_header_title_and_metadata_line(self):
        md = render.render_markdown(support.minimal_task())
        self.assertTrue(md.startswith(
            "<!-- generated from task:2612 by doc_render.py; do not edit -->\n"))
        self.assertIn("# Услуга архивации ОИС\n", md)
        self.assertIn("task 2612 - status unknown - branch features/#2612"
                      " - release unknown\n", md)

    def test_empty_task_collections_render_na(self):
        md = render.render_markdown(support.minimal_task())
        for heading in ("## Находки", "## Решения", "## Файлы",
                        "## Связанные задачи", "## Теги", "## Стадии",
                        "## Git", "## История"):
            self.assertIn(heading + "\n\n_N/A_", md)

    def test_task_collections_render(self):
        md = render.render_markdown(rich_task())
        self.assertIn("- **find:1 Двойная архивация** (pitfall, observed):"
                      " Повторный запуск создаёт дубль.", md)
        self.assertIn("  - symptom: два файла в архиве", md)
        self.assertIn("  - cause: нет блокировки", md)
        self.assertIn("  - resolution: добавлена блокировка", md)
        self.assertIn("- **dec:1 Идемпотентность**: канонический JSON", md)
        self.assertIn("  - context: нужен стабильный вывод", md)
        self.assertIn("| file:1 | src/Service.php | бизнес-логика | current |", md)
        self.assertIn("| task:1234 | related | общий сервис | confirmed |", md)
        self.assertIn("- domain:orders: затронут домен заказов", md)
        self.assertIn("| 1 | implemented | Подготовка |", md)
        self.assertIn("- git:1: commit abc1234def on features/#2612"
                      " -> unknown at 2026-09-25T10:00:00Z", md)
        self.assertIn("- 2026-09-25T10:00:00Z task-doc: документ создан", md)
        self.assertNotIn("_N/A_", md)

    def test_optional_blocks_only_when_present(self):
        minimal = render.render_markdown(support.minimal_task())
        self.assertNotIn("## Tracker", minimal)
        self.assertNotIn("## Git state", minimal)
        self.assertNotIn("## Jira report", minimal)
        tracked = render.render_markdown(tracked_task())
        self.assertIn("## Tracker\n\n- issue: CT-2615", tracked)
        self.assertIn("- exporter: gototask", tracked)
        self.assertIn("## Git state\n\n- checked_at: 2026-09-25T12:00:00Z", tracked)
        self.assertIn("- pushed_to: origin/features/#2615", tracked)
        self.assertIn("- not_pushed_refs: unknown", tracked)
        self.assertIn("## Jira report\n\n- updated_at: 2026-09-25T12:00:00Z", tracked)
        self.assertIn("- release: 5.6.1\n\nСделана архивация ОИС.", tracked)

    def test_architecture_skips_task_sections(self):
        md = render.render_markdown(arch_doc())
        self.assertIn("# Заказы\n", md)
        self.assertIn("task unknown - status unknown - branch unknown"
                      " - release unknown", md)
        for heading in ("## Находки", "## Решения", "## Файлы",
                        "## Связанные задачи", "## Теги", "## Стадии",
                        "## Git", "## История", "## Tracker", "## Jira report"):
            self.assertNotIn(heading, md)
        self.assertNotIn("_N/A_", md)

    def test_section_anchor_verbatim_no_translit(self):
        doc = rich_task()
        md = render.render_markdown(doc)
        self.assertIn("### Архитектура решения\n", md)
        self.assertIn('<a id="архитектура-решения"></a>', md)
        self.assertNotIn("arhitektura", md)
        self.assertNotIn("arhiv", md)
        self.assertIn("Текст **про** архитектуру.", md)

    def test_equal_docs_render_equal_output(self):
        doc_a = rich_task()
        doc_b = copy.deepcopy(doc_a)
        self.assertEqual(render.render_markdown(doc_a),
                         render.render_markdown(doc_b))
        self.assertEqual(render.render_markdown(doc_a),
                         render.render_markdown(rich_task()))


class RenderDocumentTests(unittest.TestCase):
    def setUp(self):
        self.root, self.docs = support.make_docs()

    def test_render_twice_byte_identical_and_receipt_set(self):
        doc = rich_task("2612")
        first = render.render_document(self.root, self.docs, "task", "2612", doc)
        self.assertEqual(first["status"], "written")
        target = view_file(self.docs, "2612")
        original = target.read_bytes()
        second = render.render_document(self.root, self.docs, "task", "2612", doc)
        self.assertEqual(second["status"], "noop")
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(second["view_sha256"], sha(original))
        receipt = support.read_json(receipt_file(self.docs, "2612"))
        self.assertEqual(receipt["view_sha256"], sha(original))
        self.assertEqual(receipt["renderer_version"], render.RENDERER_VERSION)

    def test_manual_edit_conflict_preserves_bytes(self):
        doc = rich_task("2613")
        render.render_document(self.root, self.docs, "task", "2613", doc)
        target = view_file(self.docs, "2613")
        original = target.read_bytes()
        target.write_bytes(original + b"manual note\n")
        edited = target.read_bytes()
        with self.assertRaises(render.RenderError) as ctx:
            render.render_document(self.root, self.docs, "task", "2613", doc)
        self.assertEqual(ctx.exception.code, "VIEW_CONFLICT")
        message = str(ctx.exception)
        self.assertIn(str(target), message)
        self.assertIn(sha(edited), message)
        self.assertIn(sha(original), message)
        self.assertEqual(target.read_bytes(), edited)
        receipt = support.read_json(receipt_file(self.docs, "2613"))
        self.assertEqual(receipt["view_sha256"], sha(original))

    def test_manual_edit_without_receipt_conflicts(self):
        doc = support.minimal_task("2614")
        render.render_document(self.root, self.docs, "task", "2614", doc)
        target = view_file(self.docs, "2614")
        receipt_file(self.docs, "2614").unlink()
        target.write_bytes(b"rewritten by hand\n")
        with self.assertRaises(render.RenderError) as ctx:
            render.render_document(self.root, self.docs, "task", "2614", doc)
        self.assertEqual(ctx.exception.code, "VIEW_CONFLICT")
        self.assertEqual(target.read_bytes(), b"rewritten by hand\n")

    def test_doc_change_updates_view_and_receipt(self):
        doc = support.minimal_task("2615")
        render.render_document(self.root, self.docs, "task", "2615", doc)
        target = view_file(self.docs, "2615")
        self.assertIn(b"_N/A_", target.read_bytes())
        changed = support.minimal_task("2615")
        add_source(changed)
        add_file(changed)
        add_finding(changed)
        result = render.render_document(self.root, self.docs, "task", "2615",
                                        changed)
        self.assertEqual(result["status"], "written")
        text = target.read_text(encoding="utf-8")
        self.assertIn("- **find:1 Двойная архивация** (pitfall, observed):"
                      " Повторный запуск создаёт дубль.", text)
        receipt = support.read_json(receipt_file(self.docs, "2615"))
        self.assertEqual(receipt["view_sha256"], sha(target.read_bytes()))

    def test_receipt_preserves_data_fields(self):
        doc = support.minimal_task("2616")
        seed = {"data_revision": 5, "data_sha256": "a" * 64,
                "operation_id": "op-9"}
        support.write_canonical(receipt_file(self.docs, "2616"), seed)
        result = render.render_document(self.root, self.docs, "task", "2616", doc)
        self.assertEqual(result["status"], "written")
        receipt = support.read_json(receipt_file(self.docs, "2616"))
        self.assertEqual(receipt["data_revision"], 5)
        self.assertEqual(receipt["data_sha256"], "a" * 64)
        self.assertEqual(receipt["operation_id"], "op-9")
        self.assertEqual(receipt["view_sha256"],
                         sha(view_file(self.docs, "2616").read_bytes()))
        self.assertEqual(receipt["renderer_version"], render.RENDERER_VERSION)

    def test_architecture_view_path_and_receipt(self):
        result = render.render_document(self.root, self.docs, "architecture",
                                        "orders", arch_doc())
        self.assertEqual(result["status"], "written")
        target = self.docs / "architecture" / "orders.md"
        text = target.read_text(encoding="utf-8")
        self.assertIn("# Заказы\n", text)
        self.assertNotIn("## Находки", text)
        receipt = self.docs / "architecture" / "_jsondoc" / "orders" / "receipt.json"
        self.assertEqual(support.read_json(receipt)["view_sha256"],
                         sha(target.read_bytes()))

    def test_idempotent_across_separate_roots(self):
        doc = rich_task("2617")
        render.render_document(self.root, self.docs, "task", "2617", doc)
        other_root = support.sandbox_root() / "second"
        other_root, other_docs = support.make_docs(other_root)
        render.render_document(other_root, other_docs, "task", "2617", doc)
        self.assertEqual(view_file(self.docs, "2617").read_bytes(),
                         view_file(other_docs, "2617").read_bytes())


if __name__ == "__main__":
    unittest.main()
