"""J04/J05 query tests: pointers, limits, coverage, tags, search filters."""

import unittest

import support
from jsondoc import search
from jsondoc import tags_resolver


def seeded_docs():
    root, docs = support.make_docs()
    one = support.minimal_task("2612", "Архивация ОИС")
    one["summary"] = "Услуга архивации заказа"
    one["metadata"]["release"] = "5.6.1"
    one["files"].append({"id": "F1", "path": "lib/Objects/Order/OrderService.php",
                         "role": "lifecycle", "change": None, "state": "current",
                         "source_ids": [], "revision": None, "ranges": [],
                         "previous_path": None})
    one["findings"].append({
        "id": "ПК-1", "kind": "pitfall", "title": "Тариф",
        "statement": "тариф нельзя проверять по REMOVE_DOC",
        "symptom": None, "cause": None, "resolution": None,
        "status": "observed", "severity": None, "file_ids": [],
        "source_ids": [], "superseded_by": None, "section_id": None})
    two = support.minimal_task("2070", "Заказ удаления")
    two["summary"] = "Заказ удаления ОИС 2030"
    support.write_canonical(docs / "tasks" / "2612" / "task.json", one)
    support.write_canonical(docs / "tasks" / "2070" / "task.json", two)
    legacy = docs / "tasks" / "1500"
    legacy.mkdir(parents=True)
    (legacy / "doc.md").write_text("# legacy", encoding="utf-8")
    return root, docs, one, two


class GetTests(unittest.TestCase):
    def test_not_found(self):
        root, docs, _, _ = seeded_docs()
        result = search.get(docs, "task", "9999")
        self.assertEqual(result["exit"], 1)

    def test_keys_returns_card_and_counts(self):
        root, docs, one, _ = seeded_docs()
        result = search.get(docs, "task", "2612", keys_only=True)
        self.assertIn("card", result["data"])
        self.assertEqual(result["data"]["card"]["release"], "5.6.1")
        self.assertEqual(result["data"]["card"]["counts"]["findings"], 1)

    def test_pointer_select_and_record_limit(self):
        root, docs, one, _ = seeded_docs()
        result = search.get(docs, "task", "2612",
                            pointers=["/findings", "/summary"], record_limit=5)
        self.assertEqual(len(result["data"]["/findings"]), 1)
        self.assertEqual(result["page"]["totals"]["/findings"], 1)
        self.assertFalse(result["page"]["truncated"].get("/findings"))

    def test_record_id_selection(self):
        root, docs, one, _ = seeded_docs()
        result = search.get(docs, "task", "2612", pointers=["/findings/ПК-1"])
        self.assertEqual(result["data"]["/findings/ПК-1"]["kind"], "pitfall")

    def test_field_not_found(self):
        root, docs, one, _ = seeded_docs()
        with self.assertRaises(search.QueryError) as ctx:
            search.get(docs, "task", "2612", pointers=["/nope"])
        self.assertEqual(ctx.exception.code, "FIELD_NOT_FOUND")

    def test_limit_truncates_list(self):
        root, docs, one, _ = seeded_docs()
        for i in range(15):
            one["notes"].append({"id": f"N{i}", "kind": "observation",
                                 "text": f"note {i}", "source_ids": [],
                                 "section_id": None})
        support.write_canonical(docs / "tasks" / "2612" / "task.json", one)
        result = search.get(docs, "task", "2612", pointers=["/notes"],
                            record_limit=10)
        self.assertEqual(len(result["data"]["/notes"]), 10)
        self.assertTrue(result["page"]["truncated"]["/notes"])
        self.assertEqual(result["page"]["totals"]["/notes"], 15)


class SearchTests(unittest.TestCase):
    def test_text_search_matches_casefold(self):
        root, docs, one, _ = seeded_docs()
        result = search.search(docs, kind="task", text="ТАРИФ")
        self.assertEqual(result["counts"]["matched"], 1)
        self.assertEqual(result["data"][0]["key"], "2612")

    def test_and_semantics_all_tokens_required(self):
        root, docs, one, _ = seeded_docs()
        result = search.search(docs, kind="task", text="тариф архивация")
        self.assertEqual(result["counts"]["matched"], 1)
        result = search.search(docs, kind="task", text="тариф удаление")
        self.assertEqual(result["counts"]["matched"], 0)

    def test_file_filter(self):
        root, docs, one, _ = seeded_docs()
        result = search.search(docs, kind="task",
                               file="lib/Objects/Order/OrderService.php")
        self.assertEqual(result["counts"]["matched"], 1)

    def test_release_filter(self):
        root, docs, one, _ = seeded_docs()
        self.assertEqual(search.search(docs, release="5.6.1")["counts"]["matched"], 1)
        self.assertEqual(search.search(docs, release="5.6.2")["counts"]["matched"], 0)

    def test_coverage_reports_legacy_and_invalid(self):
        root, docs, one, _ = seeded_docs()
        bad = docs / "tasks" / "1800"
        bad.mkdir(parents=True)
        (bad / "task.json").write_text("{broken", encoding="utf-8")
        result = search.search(docs)
        cov = result["coverage"]
        self.assertEqual(cov["legacy"], 1)
        self.assertEqual(cov["invalid"], 1)
        self.assertEqual(cov["discovered"], 4)
        self.assertFalse(cov["complete"])

    def test_pagination_window_and_total(self):
        root, docs, one, two = seeded_docs()
        result = search.search(docs, kind="task", limit=1)
        self.assertEqual(result["counts"]["returned"], 1)
        self.assertEqual(result["counts"]["matched"], 2)
        self.assertTrue(result["page"]["truncated"])

    def test_read_only_no_writes(self):
        import os
        root, docs, one, _ = seeded_docs()
        before = {p: p.stat().st_mtime_ns
                  for p in docs.rglob("*") if p.is_file()}
        search.search(docs)
        search.get(docs, "task", "2612", keys_only=True)
        after = {p: p.stat().st_mtime_ns
                 for p in docs.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class RelatedDiscoveryTests(unittest.TestCase):
    def seeded(self):
        root, docs, one, two = seeded_docs()
        one["relations"].append({
            "id": "R1", "kind": "baseline",
            "target": {"document_id": "task:2070", "record_id": None,
                       "anchor": None},
            "reason": "baseline flow", "source_ids": [],
            "status": "confirmed", "availability": "present"})
        one["tags"].append({"tag_id": "domain:orders",
                            "reason": "заказы", "source_ids": [],
                            "status": "confirmed"})
        two["tags"].append({"tag_id": "domain:orders",
                            "reason": "заказы", "source_ids": [],
                            "status": "confirmed"})
        two["files"].append({"id": "F1",
                             "path": "lib/Objects/Order/OrderService.php",
                             "role": "core", "change": None, "state": "current",
                             "source_ids": [], "revision": None, "ranges": [],
                             "previous_path": None})
        support.write_canonical(docs / "tasks" / "2612" / "task.json", one)
        support.write_canonical(docs / "tasks" / "2070" / "task.json", two)
        return root, docs, one, two

    def test_explicit_relation_scores_top(self):
        root, docs, one, two = self.seeded()
        result = search.related(docs, "discovery-v1", task="2612")
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["data"][0]["id"], "2070")
        self.assertGreaterEqual(result["data"][0]["score"], 100)
        kinds = {s["kind"] for s in result["data"][0]["signals"]}
        self.assertIn("relation", kinds)
        self.assertIn("file", kinds)  # shared OrderService file

    def test_tag_only_match_is_candidate(self):
        root, docs, one, two = self.seeded()
        one["files"] = []
        one["relations"] = []  # keep tag-only signal
        support.write_canonical(docs / "tasks" / "2612" / "task.json", one)
        result = search.related(docs, "discovery-v1", task="2612")
        hit = next(h for h in result["data"] if h["id"] == "2070")
        self.assertTrue(hit["candidate"])

    def test_current_task_excluded(self):
        root, docs, one, two = self.seeded()
        result = search.related(docs, "discovery-v1", task="2612")
        self.assertNotIn("2612", [h["id"] for h in result["data"]])

    def test_legacy_profile_live(self):
        root, docs, one, two = self.seeded()
        result = search.related(docs, "legacy-v1", arch="orders")
        # no architecture doc in this sandbox -> documented not_found exit 1
        self.assertEqual(result["exit"], 1)
        self.assertEqual(result["profile"], "legacy-v1")


class TagResolverTests(unittest.TestCase):
    def dictionary(self, docs):
        support.write_canonical(docs / "skil_data" / "task-doc" / "state" / "tags.json", {
            "schema_version": "1.0", "revision": 1,
            "tags": [
                {"id": "domain:orders", "kind": "domain", "label": "Заказы",
                 "description": "Домен заказов", "aliases": ["orders"],
                 "parents": [], "status": "active", "replaced_by": None},
                {"id": "domain:payments", "kind": "domain", "label": "Платежи",
                 "description": "Домен платежей", "aliases": [],
                 "parents": ["domain:orders"], "status": "active",
                 "replaced_by": None},
            ]})

    def test_alias_resolves_canonical(self):
        root, docs, _, _ = seeded_docs()
        self.dictionary(docs)
        tags_resolver._CACHE.clear()
        self.assertEqual(tags_resolver.resolve_tag(docs, "orders"),
                         "domain:orders")
        self.assertEqual(tags_resolver.resolve_tag(docs, "domain:orders"),
                         "domain:orders")

    def test_unknown_tag_raises(self):
        root, docs, _, _ = seeded_docs()
        self.dictionary(docs)
        tags_resolver._CACHE.clear()
        with self.assertRaises(tags_resolver.TagError) as ctx:
            tags_resolver.resolve_tag(docs, "nope:missing")
        self.assertEqual(ctx.exception.code, "unknown_tag")

    def test_invalid_dictionary_raises(self):
        root, docs, _, _ = seeded_docs()
        support.write_canonical(docs / "skil_data" / "task-doc" / "state" / "tags.json", {
            "schema_version": "1.0", "revision": 1, "tags": [
                {"id": "domain:orders", "kind": "domain", "label": "x",
                 "description": "y", "aliases": [], "parents": ["nope:gone"],
                 "status": "active", "replaced_by": None}]})
        tags_resolver._CACHE.clear()
        with self.assertRaises(tags_resolver.TagError):
            tags_resolver.resolve_tag(docs, "domain:orders")


if __name__ == "__main__":
    unittest.main()
