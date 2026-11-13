"""Batch tests: BT01-BT04 (plan 18.4)."""

import unittest

import support
from jsondoc import batch
from jsondoc.store import Store, StoreError


def seeded():
    root, docs = support.make_docs()
    one = support.minimal_task("2612", "Архивация")
    one["summary"] = "Услуга архивации заказа"
    support.write_canonical(docs / "tasks" / "2612" / "task.json", one)
    two = support.minimal_task("2070", "Удаление")
    support.write_canonical(docs / "tasks" / "2070" / "task.json", two)
    support.write_canonical(docs / "skil_data" / "task-doc" / "state" / "tags.json", {
        "schema_version": "1.0", "revision": 1, "tags": [
            {"id": "domain:orders", "kind": "domain", "label": "Заказы",
             "description": "Домен заказов", "aliases": ["orders"],
             "parents": [], "status": "active", "replaced_by": None}]})
    return root, docs


class BatchTests(unittest.TestCase):
    def test_bt01_four_commands_one_envelope(self):
        root, docs = seeded()
        result = batch.run_batch(docs, {
            "batch_id": "b1",
            "calls": [
                {"id": "keys", "command": "get",
                 "args": {"task": "2612", "keys": True}},
                {"id": "find", "command": "search",
                 "args": {"kind": "task", "text": "архивация"}},
                {"id": "tags", "command": "tags_search",
                 "args": {"text": "заказы"}},
                {"id": "miss", "command": "get", "args": {"task": "9999"}},
            ]})
        self.assertEqual(result["exit"], 0)
        self.assertEqual(len(result["results"]), 4)
        self.assertEqual(result["results"][0]["status"], "ok")
        self.assertEqual(result["results"][1]["counts"]["matched"], 1)
        self.assertEqual(result["results"][2]["counts"]["matched"], 1)
        self.assertEqual(result["results"][3]["status"], "not_found")

    def test_bt02_batch_with_apply_single_revision(self):
        root, docs = seeded()
        store = Store(root, docs)
        result = batch.run_batch(docs, {
            "batch_id": "b2",
            "calls": [{"id": "k", "command": "get",
                       "args": {"task": "2612", "keys": True}}],
            "apply": {
                "schema_version": "1.0", "operation_id": "batch-op-1",
                "expected_revision": 1, "actor": "task-doc",
                "reason": "batch update",
                "operations": [{"op": "set", "collection": "summary",
                                "key": "summary", "value": "новый summary"}],
                "document": None,
                "task": "2612"}}, store=store)
        self.assertEqual(result["apply_summary"]["status"], "applied")
        doc = store.load("task", "2612")
        self.assertEqual(doc["summary"], "новый summary")
        self.assertEqual(doc["revision"], 2)
        self.assertEqual(len(doc["history"]), 1)

    def test_bt03_per_item_not_found_does_not_kill_batch(self):
        root, docs = seeded()
        result = batch.run_batch(docs, {
            "batch_id": "b3",
            "calls": [
                {"id": "miss", "command": "get", "args": {"task": "404"}},
                {"id": "hit", "command": "get", "args": {"task": "2612"}},
            ]})
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["results"][1]["status"], "ok")

    def test_bt04_twenty_first_call_rejected(self):
        root, docs = seeded()
        calls = [{"id": f"c{i}", "command": "get",
                  "args": {"task": "2612", "keys": True}} for i in range(21)]
        with self.assertRaises(batch.BatchError) as ctx:
            batch.run_batch(docs, {"calls": calls})
        self.assertEqual(ctx.exception.code, "too_many_calls")

    def test_apply_error_isolated_from_reads(self):
        root, docs = seeded()
        store = Store(root, docs)
        result = batch.run_batch(docs, {
            "calls": [{"id": "k", "command": "get",
                       "args": {"task": "2612", "keys": True}}],
            "apply": {
                "schema_version": "1.0", "operation_id": "batch-op-bad",
                "expected_revision": 99, "actor": "task-doc",
                "reason": "stale revision", "operations": [],
                "document": None, "task": "2612"}}, store=store)
        self.assertEqual(result["results"][0]["status"], "ok")
        self.assertEqual(result["apply_summary"]["status"],
                         "conflict")

    def test_reads_see_pre_apply_state(self):
        root, docs = seeded()
        store = Store(root, docs)
        result = batch.run_batch(docs, {
            "calls": [{"id": "sum", "command": "get",
                       "args": {"task": "2612", "select": ["/summary"]}}],
            "apply": {
                "schema_version": "1.0", "operation_id": "batch-op-2",
                "expected_revision": 1, "actor": "task-doc",
                "reason": "change summary",
                "operations": [{"op": "set", "collection": "summary",
                                "key": "summary", "value": "после"}],
                "document": None, "task": "2612"}}, store=store)
        self.assertEqual(result["results"][0]["data"]["/summary"],
                         "Услуга архивации заказа")
        self.assertEqual(store.load("task", "2612")["summary"], "после")


if __name__ == "__main__":
    unittest.main()
