"""J10 review queue tests (MG01-MG08 sandbox subset): claim CAS, stale
review rejection, task-local evidence, candidate tags, strict queue
schema, duplicate add semantics, lease expiry and approve gating."""

import copy
import unittest

import support
from jsondoc import review


def seed_sources(docs):
    (docs / "architecture").mkdir(parents=True, exist_ok=True)
    (docs / "architecture" / "orders.md").write_text(
        "# Заказы\n\nКритичный поток оплаты.\n", encoding="utf-8")
    (docs / "architecture" / "payments.md").write_text(
        "# Оплаты\n\nПроведение платежа.\n", encoding="utf-8")
    task_dir = docs / "tasks" / "2612"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(
        "# Задача 2612\n\nУслуга архивации ОИС.\n", encoding="utf-8")


def make_item(docs, item_id, document_id, source_path, reason_codes):
    return {
        "id": item_id,
        "document_id": document_id,
        "source_path": source_path,
        "source_sha256": review.sha256_file(docs / source_path),
        "candidate_sha256": "f" * 64,
        "reason_codes": list(reason_codes),
        "required_sections": ["Критичный поток"],
        "evidence_paths": [],
    }


def seeded_docs():
    root, docs = support.make_docs()
    seed_sources(docs)
    review.add_items(docs, [
        make_item(docs, "arch-payments-01", "arch:payments",
                  "architecture/payments.md", ["opaque_critical_flow"]),
        make_item(docs, "arch-orders-01", "arch:orders",
                  "architecture/orders.md", ["ambiguous_section"]),
        make_item(docs, "task-2612-01", "task:2612",
                  "tasks/2612/task.md", ["tag_mapping_ambiguous"]),
    ])
    return docs


def result_for(item, **coverage):
    cov = {"text_preserved": True, "structure_extracted": True,
           "semantic_reviewed": True, "code_verified": False}
    cov.update(coverage)
    return {
        "source_sha256": item["source_sha256"],
        "enrichment": {
            "tags": [{"tag_id": "domain-orders", "reason": "поток заказов",
                      "status": "candidate"}],
            "notes": ["секции сверены с источником"],
        },
        "reviewer": "agent-session",
        "evidence_paths": [item["source_path"]],
        "coverage": cov,
        "blockers": [],
    }


def get_item(docs, item_id):
    for item in review.load_queue(docs, refresh=True)["items"]:
        if item["id"] == item_id:
            return item
    raise AssertionError(f"item {item_id} missing")


class SeedingTests(unittest.TestCase):
    def test_mg02_opaque_critical_flow_gets_queue_item(self):
        docs = seeded_docs()
        self.assertEqual(review.stats(docs)["pending"], 3)
        item = get_item(docs, "arch-payments-01")
        self.assertEqual(item["reason_codes"], ["opaque_critical_flow"])
        self.assertEqual(item["status"], "pending")
        self.assertEqual(item["attempts"], 0)
        self.assertIsNone(item["lease"])
        self.assertTrue(item["coverage"]["text_preserved"] is False)

    def test_missing_queue_loads_fresh_empty(self):
        root, docs = support.make_docs()
        queue = review.load_queue(docs)
        self.assertEqual(queue["schema_version"], "1.0")
        self.assertEqual(queue["revision"], 0)
        self.assertEqual(queue["items"], [])
        self.assertEqual(sum(review.stats(docs).values()), 0)


class NextItemTests(unittest.TestCase):
    def test_order_and_kind_filter_without_claim(self):
        docs = seeded_docs()
        out = review.next_item(docs, limit=3)
        self.assertEqual([i["id"] for i in out["items"]],
                         ["arch-orders-01", "arch-payments-01",
                          "task-2612-01"])
        only_tasks = review.next_item(docs, kind="task", limit=5)
        self.assertEqual([i["id"] for i in only_tasks["items"]],
                         ["task-2612-01"])
        arch = review.next_item(docs, kind="architecture", limit=5)
        self.assertNotIn("task-2612-01", [i["id"] for i in arch["items"]])
        for item in out["items"]:
            self.assertEqual(get_item(docs, item["id"])["status"], "pending")

    def test_mg03_second_claim_never_releases_same_item(self):
        docs = seeded_docs()
        first = review.next_item(docs, claim=True, owner="agent-a")
        self.assertEqual(len(first["items"]), 1)
        leased = first["items"][0]
        self.assertEqual(leased["id"], "arch-orders-01")
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["lease"]["owner"], "agent-a")
        self.assertEqual(len(leased["lease"]["token"]), 32)
        self.assertRegex(leased["lease"]["expires_at"],
                         r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
                         r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
        second = review.next_item(docs, claim=True, owner="agent-b")
        self.assertNotIn("arch-orders-01", [i["id"] for i in second["items"]])
        stored = get_item(docs, "arch-orders-01")
        self.assertEqual(stored["lease"]["owner"], "agent-a")

    def test_mg03_single_pending_item_second_claim_empty(self):
        root, docs = support.make_docs()
        seed_sources(docs)
        review.add_items(docs, [
            make_item(docs, "arch-orders-01", "arch:orders",
                      "architecture/orders.md", ["ambiguous_section"])])
        review.next_item(docs, claim=True, owner="agent-a")
        second = review.next_item(docs, claim=True, owner="agent-b")
        self.assertEqual(second["items"], [])
        self.assertEqual(review.stats(docs)["leased"], 1)


class SubmitTests(unittest.TestCase):
    def test_mg04_stale_submit_rejected_item_stays_leased(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        item = get_item(docs, "arch-orders-01")
        stale = result_for(item)
        stale["source_sha256"] = "0" * 64
        with self.assertRaises(review.ReviewError) as ctx:
            review.submit(docs, "arch-orders-01", stale)
        self.assertEqual(ctx.exception.code, "stale_source")
        stored = get_item(docs, "arch-orders-01")
        self.assertEqual(stored["status"], "leased")
        self.assertIsNone(stored["result_path"])

    def test_mg04_source_change_marks_item_stale(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        source = docs / "architecture" / "orders.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nновый раздел\n",
            encoding="utf-8")
        with self.assertRaises(review.ReviewError) as ctx:
            review.validate_item(docs, "arch-orders-01")
        self.assertEqual(ctx.exception.code, "stale_source")
        self.assertEqual(get_item(docs, "arch-orders-01")["status"], "stale")

    def test_mg05_task_result_written_task_local(self):
        docs = seeded_docs()
        review.next_item(docs, kind="task", claim=True, owner="agent-a")
        item = get_item(docs, "task-2612-01")
        out = review.submit(docs, "task-2612-01", result_for(item))
        expected = "tasks/2612/_jsondoc/reviews/task-2612-01.json"
        self.assertEqual(out["result_path"], expected)
        self.assertTrue((docs / expected).is_file())
        stored = get_item(docs, "task-2612-01")
        self.assertEqual(stored["status"], "submitted")
        self.assertEqual(stored["result_path"], expected)
        self.assertIsNone(stored["lease"])
        self.assertTrue(stored["coverage"]["text_preserved"])

    def test_mg07_candidate_tags_survive_submit_and_approve(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        item = get_item(docs, "arch-orders-01")
        review.submit(docs, "arch-orders-01", result_for(item))
        out = review.approve(docs, "arch-orders-01")
        self.assertEqual(out["status"], "accepted")
        payload = support.read_json(
            docs / "architecture" / "_jsondoc" / "orders" / "reviews"
            / "arch-orders-01.json")
        tag = payload["result"]["enrichment"]["tags"][0]
        self.assertEqual(tag["status"], "candidate")
        self.assertEqual(review.stats(docs)["accepted"], 1)

    def test_approve_without_submit_rejected(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        with self.assertRaises(review.ReviewError) as ctx:
            review.approve(docs, "arch-orders-01")
        self.assertEqual(ctx.exception.code, "not_submitted")

    def test_arch_semantic_review_required_at_approve(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        item = get_item(docs, "arch-orders-01")
        review.submit(docs, "arch-orders-01",
                      result_for(item, semantic_reviewed=False))
        self.assertEqual(get_item(docs, "arch-orders-01")["status"],
                         "submitted")
        with self.assertRaises(review.ReviewError) as ctx:
            review.approve(docs, "arch-orders-01")
        self.assertEqual(ctx.exception.code,
                         "arch_semantic_review_required")
        self.assertEqual(get_item(docs, "arch-orders-01")["status"],
                         "submitted")

    def test_submit_without_text_preserved_rejected(self):
        docs = seeded_docs()
        review.next_item(docs, kind="task", claim=True, owner="agent-a")
        item = get_item(docs, "task-2612-01")
        with self.assertRaises(review.ReviewError) as ctx:
            review.submit(docs, "task-2612-01",
                          result_for(item, text_preserved=False))
        self.assertEqual(ctx.exception.code, "text_not_preserved")
        self.assertEqual(get_item(docs, "task-2612-01")["status"], "leased")


class QueueSchemaTests(unittest.TestCase):
    def test_unknown_queue_field_rejected_on_load(self):
        docs = seeded_docs()
        data = copy.deepcopy(review.load_queue(docs))
        data["owner"] = "agent-a"
        support.write_canonical(review.queue_path(docs), data)
        with self.assertRaises(review.ReviewError) as ctx:
            review.load_queue(docs, refresh=True)
        self.assertEqual(ctx.exception.code, "queue_unknown_field")

    def test_unknown_item_field_rejected_on_load(self):
        docs = seeded_docs()
        data = copy.deepcopy(review.load_queue(docs))
        data["items"][0]["priority"] = 5
        support.write_canonical(review.queue_path(docs), data)
        with self.assertRaises(review.ReviewError) as ctx:
            review.load_queue(docs, refresh=True)
        self.assertEqual(ctx.exception.code, "item_unknown_field")


class AddItemsTests(unittest.TestCase):
    def test_duplicate_same_sha_noop(self):
        docs = seeded_docs()
        before = review.load_queue(docs)["revision"]
        out = review.add_items(docs, [
            make_item(docs, "arch-orders-01", "arch:orders",
                      "architecture/orders.md", ["ambiguous_section"])])
        self.assertEqual(out["added"], 0)
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["refreshed"], 0)
        self.assertEqual(review.load_queue(docs)["revision"], before)

    def test_changed_sha_refreshes_to_pending_with_note(self):
        docs = seeded_docs()
        source = docs / "architecture" / "orders.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\nправка\n",
            encoding="utf-8")
        out = review.add_items(docs, [
            make_item(docs, "arch-orders-01", "arch:orders",
                      "architecture/orders.md", ["ambiguous_section"])])
        self.assertEqual(out["added"], 0)
        self.assertEqual(out["refreshed"], 1)
        self.assertTrue(any("arch-orders-01" in note for note in out["notes"]))
        stored = get_item(docs, "arch-orders-01")
        self.assertEqual(stored["status"], "pending")
        self.assertIsNone(stored["lease"])
        self.assertEqual(stored["source_sha256"],
                         review.sha256_file(source))

    def test_invalid_reason_and_sha_rejected(self):
        root, docs = support.make_docs()
        seed_sources(docs)
        item = make_item(docs, "arch-orders-01", "arch:orders",
                         "architecture/orders.md", ["ambiguous_section"])
        item["reason_codes"] = ["not_a_reason"]
        with self.assertRaises(review.ReviewError):
            review.add_items(docs, [item])
        item["reason_codes"] = ["ambiguous_section"]
        item["source_sha256"] = "xyz"
        with self.assertRaises(review.ReviewError) as ctx:
            review.add_items(docs, [item])
        self.assertEqual(ctx.exception.code, "item_invalid")
        self.assertEqual(review.load_queue(docs)["items"], [])

    def test_check_sources_flag_rejects_missing_file(self):
        root, docs = support.make_docs()
        item = {"id": "arch-ghost-01", "document_id": "arch:ghost",
                "source_path": "architecture/ghost.md",
                "source_sha256": "a" * 64}
        with self.assertRaises(review.ReviewError) as ctx:
            review.add_items(docs, [item], check_sources=True)
        self.assertEqual(ctx.exception.code, "source_missing")


class ReleaseExpiredTests(unittest.TestCase):
    def test_expired_lease_reverts_to_pending_attempts_increment(self):
        docs = seeded_docs()
        review.next_item(docs, claim=True, owner="agent-a")
        data = copy.deepcopy(review.load_queue(docs))
        for item in data["items"]:
            if item["id"] == "arch-orders-01":
                item["lease"]["expires_at"] = "2020-01-01T00:00:00Z"
        support.write_canonical(review.queue_path(docs), data)
        out = review.release_expired(docs)
        self.assertEqual(out["released"], ["arch-orders-01"])
        stored = get_item(docs, "arch-orders-01")
        self.assertEqual(stored["status"], "pending")
        self.assertIsNone(stored["lease"])
        self.assertEqual(stored["attempts"], 1)
        reclaimed = review.next_item(docs, claim=True, owner="agent-b")
        self.assertEqual(reclaimed["items"][0]["id"], "arch-orders-01")
        self.assertEqual(get_item(docs, "arch-orders-01")["attempts"], 1)
        fresh = review.release_expired(docs)
        self.assertEqual(fresh["released"], [])


if __name__ == "__main__":
    unittest.main()
