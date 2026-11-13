"""UT19-UT23 migration staging tests (offline fixtures)."""

import unittest

import support
from jsondoc import migrate
from jsondoc.render import render_document
from jsondoc.store import Store

LEGACY = """# Issue #2612: Услуга архивации

<!-- meta
type: task-doc
status: actual
updated: 2026-09-25
-->

## Суть

Общий контекст задачи.

## Затронутые файлы

| Файл | Роль |
|---|---|
| `lib/Objects/Order/OrderService.php` | lifecycle заказа |
| `sql/migrations/Version20260925120000.php` | миграция услуги |

## Подводные камни

- **ПК-1: Тариф по REMOVE_DOC**
  Симптом: заказ 2031 блокирован.
  Причина: findServiceByCode без кода заказа.
- **ПК-3: Частичный прогон**
  Симптом: ветка table red.

## Принятые решения

- **Р-1: Код услуги 2031**
  Контекст: 2030 занят.

## Связанные задачи

- #2070 - baseline 2030 flow
- #2354 - тарифы

## Что-то непонятное

Произвольный текст секции, который не распознаётся.

```json
{"внутри": "блока", "## фейковый заголовок": true}
```

## История изменений

- 2026-09-25: создано
"""


class SpanTests(unittest.TestCase):
    def test_ut19_roundtrip_variants(self):
        variants = [
            LEGACY.encode("utf-8"),
            LEGACY.replace("\n", "\r\n").encode("utf-8"),
            b"\xef\xbb\xbf" + LEGACY.encode("utf-8"),
            LEGACY.encode("utf-8").rstrip(b"\n"),
        ]
        for data in variants:
            root, docs = support.make_docs()
            staging = migrate.write_staging(docs, "task", "2612", "run-1", data)
            result = migrate.check(docs, "task", "2612", "run-1")
            self.assertTrue(result["byte_roundtrip"], data[:20])


class CoverageTests(unittest.TestCase):
    def test_ut20_opaque_section_preserved(self):
        data = LEGACY.encode("utf-8")
        root, docs = support.make_docs()
        staging = migrate.write_staging(docs, "task", "2612", "run-2", data)
        candidate = support.read_json(
            __import__("pathlib").Path(staging["dir"]) / "candidate.json")
        titles = [s["title"] for s in candidate["sections"]]
        self.assertIn("Что-то непонятное", titles)
        opaque = next(s for s in candidate["sections"]
                      if s["title"] == "Что-то непонятное")
        self.assertEqual(opaque["origin"], "opaque")
        self.assertIn("Произвольный текст", opaque["body_markdown"])
        fenced = next(s for s in candidate["sections"]
                      if "фейковый заголовок" in s["body_markdown"])
        self.assertIn("внутри", fenced["body_markdown"])

    def test_structure_extracted_with_id_gaps(self):
        data = LEGACY.encode("utf-8")
        root, docs = support.make_docs()
        staging = migrate.write_staging(docs, "task", "2612", "run-3", data)
        candidate = support.read_json(
            __import__("pathlib").Path(staging["dir"]) / "candidate.json")
        ids = [f["id"] for f in candidate["findings"]]
        self.assertEqual(ids, ["ПК-1", "ПК-3"])
        self.assertEqual(candidate["decisions"][0]["id"], "Р-1")
        related = {r["target"]["document_id"] for r in candidate["relations"]}
        self.assertEqual(related, {"task:2070", "task:2354"})
        paths = [f["path"] for f in candidate["files"]]
        self.assertIn("lib/Objects/Order/OrderService.php", paths)


class CutoverTests(unittest.TestCase):
    def staging(self, run="run-a"):
        root, docs = support.make_docs()
        live = docs / "tasks" / "2612" / "doc.md"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(LEGACY.encode("utf-8"))
        staging = migrate.write_staging(docs, "task", "2612", run,
                                        LEGACY.encode("utf-8"))
        store = Store(root, docs)
        return root, docs, live, staging, store

    def test_ut21_live_source_changed_blocks(self):
        root, docs, live, staging, store = self.staging()
        live.write_text("# изменён вручную", encoding="utf-8")
        with self.assertRaises(migrate.MigrateError) as ctx:
            migrate.apply_cutover(store, None, docs, "task", "2612", "run-a")
        self.assertEqual(ctx.exception.code, "MIGRATION_SOURCE_CHANGED")
        self.assertIsNone(store.load("task", "2612"))

    def test_ut22_resume_duplicate_noop(self):
        root, docs, live, staging, store = self.staging()
        first = migrate.apply_cutover(store, None, docs, "task", "2612",
                                      "run-a")
        self.assertEqual(first["status"], "applied")
        second = migrate.apply_cutover(store, None, docs, "task", "2612",
                                       "run-a")
        self.assertEqual(second["status"], "duplicate")

    def test_cutover_publishes_json_and_view(self):
        root, docs, live, staging, store = self.staging()
        from jsondoc import render as render_mod
        result = migrate.apply_cutover(store, render_mod, docs, "task", "2612",
                                       "run-a")
        self.assertEqual(result["status"], "applied")
        doc = store.load("task", "2612")
        self.assertEqual(doc["kind"], "task")
        self.assertTrue((docs / "tasks" / "2612" / "task.json").is_file())
        view_text = (docs / "tasks" / "2612" / "doc.md").read_text(
            encoding="utf-8")
        self.assertIn("generated", view_text.splitlines()[0])
        self.assertIn("Услуга архивации", view_text)
        # original preserved in staging
        original = (__import__("pathlib").Path(staging["dir"]) /
                    "original.md").read_text(encoding="utf-8")
        self.assertIn("Услуга архивации", original)


class InventoryTests(unittest.TestCase):
    def test_roles_and_stage_variants(self):
        root, docs = support.make_docs()
        base = docs / "tasks" / "2612"
        for rel in ["task.md", "doc.md", "plan.md", "stage2/plan.md",
                    "stage1v2/plan.md", "test-runs/out.json",
                    "reports/r.html", "unknown.png", "gototask-state.json"]:
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
        (base / "stage6").mkdir(parents=True, exist_ok=True)
        (docs / "tasks" / "_map").mkdir(parents=True, exist_ok=True)
        (docs / "tasks" / "_map" / "file-to-tasks.tsv").write_text("p\t1",
                                                                   encoding="utf-8")
        (docs / "architecture").mkdir(parents=True, exist_ok=True)
        (docs / "architecture" / "orders.md").write_text("# o", encoding="utf-8")
        (docs / "architecture" / "_map").mkdir(parents=True, exist_ok=True)
        (docs / "architecture" / "_map" / "doc-index.tsv").write_text("x",
                                                                      encoding="utf-8")
        (docs / "_context-base.md").write_text("# ctx", encoding="utf-8")
        result = migrate.inventory(docs)
        entries = {item["path"]: item for item in result["tasks"]["2612"]["files"]}
        self.assertEqual(entries["doc.md"]["role"], "migrate")
        self.assertEqual(entries["plan.md"]["role"], "migrate_root")
        self.assertEqual(entries["stage2/plan.md"]["role"], "migrate_stage")
        self.assertEqual(entries["stage1v2/plan.md"]["role"],
                         "migrate_stage_rev")
        self.assertEqual(entries["stage1v2/plan.md"]["number"], 1)
        self.assertEqual(entries["stage1v2/plan.md"]["variant"], 2)
        self.assertEqual(entries["test-runs/out.json"]["role"], "state")
        self.assertEqual(entries["unknown.png"]["role"], "attachment")
        placeholders = [e for e in result["tasks"]["2612"]["files"]
                        if e.get("placeholder")]
        self.assertEqual(placeholders, [{"path": "stage6", "role": "state",
                                         "number": 6, "placeholder": True}])
        self.assertEqual(result["arch"][0]["stem"], "orders")
        self.assertEqual(result["counts"]["arch"], 1)


if __name__ == "__main__":
    unittest.main()
