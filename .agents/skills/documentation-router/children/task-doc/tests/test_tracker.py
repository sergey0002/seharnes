"""JR01-JR05 tracker ingest tests (offline fixtures)."""

import unittest

import support
from jsondoc import ingest
from jsondoc.store import Store


def payload(total=205, per_page=100, missing_total=False, early_empty=False,
            duplicates=False, assignee=None, availability=None,
            status="In Progress", exporter="gototask", summary=None,
            issuetype=None):
    pages = []
    remaining = total
    index = 0
    while remaining > 0 or not pages:
        count = min(per_page, remaining)
        comments = [{"id": f"c-{index * per_page + i}", "author":
                     {"id": "u1", "name": "QA", "active": True},
                     "created_at": "2026-09-01T00:00:00Z",
                     "updated_at": None, "body": f"comment {i}",
                     "visibility": None}
                    for i in range(count)]
        if duplicates and index == 1 and comments:
            comments[0]["id"] = "c-0"
        pages.append({"start_at": index * per_page,
                      "max_results": per_page,
                      "total": None if missing_total else total,
                      "is_last": remaining <= per_page,
                      "comments": comments})
        if early_empty and index == 0:
            # pagination stopped early on an empty page before total reached
            pages.append({"start_at": per_page, "max_results": per_page,
                          "total": total, "is_last": True, "comments": []})
            remaining = 0
            break
        remaining -= count
        index += 1
        if remaining <= 0:
            break
    issue = {
        "issue_key": "CT-2612",
        "summary": summary,
        "issuetype": issuetype,
        "status": {"id": "3", "name": status,
                   "category": {"id": "2", "key": "indeterminate",
                                "name": "In Progress"}},
        "resolution": None,
        "priority": {"id": "3", "name": "Major"},
        "creator": {"id": "u0", "name": "Author", "active": True},
        "reporter": {"id": "u0", "name": "Author", "active": True},
        "assignee": assignee,
        "fix_versions": [{"name": "5.6.1", "released": False}],
        "labels": ["orders"],
        "components": [{"name": "backend"}],
    }
    data = {
        "schema_version": "1.0",
        "issue": issue,
        "comments_pages": pages,
        "changelog_pages": [],
        "exporter": exporter,
        "exported_at": "2026-09-25T19:00:00Z",
        "task_md_sha256": "a" * 64,
    }
    if availability is not None:
        data["field_availability"] = availability
    return data


class CoverageTests(unittest.TestCase):
    def test_jr01_full_pagination_complete(self):
        cov = ingest.comment_coverage(
            ingest.payload if False else payload()["comments_pages"])
        self.assertTrue(cov["complete"])
        self.assertEqual(cov["retrieved"], 205)
        self.assertEqual(cov["unique_ids"], 205)
        self.assertEqual(cov["total_reported"], 205)

    def test_jr02_missing_total_incomplete(self):
        cov = ingest.comment_coverage(payload(missing_total=True)["comments_pages"])
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["termination"], "missing_total")

    def test_jr02_early_empty_page_incomplete(self):
        cov = ingest.comment_coverage(payload(early_empty=True)["comments_pages"])
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["termination"], "early_empty_page")

    def test_jr02_duplicate_ids_incomplete(self):
        cov = ingest.comment_coverage(payload(duplicates=True)["comments_pages"])
        self.assertFalse(cov["complete"])
        self.assertLess(cov["unique_ids"], cov["retrieved"])

    def test_availability_null_value_kept_not_returned_dropped(self):
        cleaned, errors = ingest.validate_tracker_input(
            payload(assignee=None,
                    availability=[{"field_id": "issue.assignee",
                                   "state": "null_value"},
                                  {"field_id": "issue.priority",
                                   "state": "not_returned"}]))
        self.assertEqual(errors, [])
        self.assertIsNone(cleaned["issue"].get("assignee"))
        self.assertNotIn("priority", cleaned["issue"])
        self.assertEqual(cleaned["availability_map"]["issue.priority"],
                         "not_returned")

    def test_unknown_fields_rejected(self):
        bad = payload()
        bad["surprise"] = 1
        cleaned, errors = ingest.validate_tracker_input(bad)
        self.assertIsNone(cleaned)
        self.assertEqual(errors[0]["code"], "unknown_fields")


class IngestTests(unittest.TestCase):
    def store(self):
        root, docs = support.make_docs()
        return root, docs, Store(root, docs)

    def test_create_fills_release_branch_snapshot(self):
        root, docs, store = self.store()
        result = ingest.ingest_tracker(store, "2612", payload())
        self.assertEqual(result["status"], "applied")
        doc = store.load("task", "2612")
        self.assertEqual(doc["metadata"]["release"], "5.6.1")
        self.assertEqual(doc["metadata"]["branch"], "features/#2612")
        self.assertEqual(doc["tracker"]["snapshot"]["coverage"]["comments"]
                         ["retrieved"], 205)
        manifest = ingest.snapshot_dir(docs, "2612", result["snapshot_id"]) \
            / "manifest.json"
        self.assertTrue(manifest.is_file())
        data = json.loads(manifest.read_text())
        self.assertEqual(data["task_md_sha256"], "a" * 64)

    def test_create_uses_jira_summary_and_issuetype(self):
        root, docs, store = self.store()
        ingest.ingest_tracker(store, "1422", payload(
            summary="Ошибка при редактировании роли",
            issuetype={"id": "1", "name": "Баг"}))
        doc = store.load("task", "1422")
        self.assertEqual(doc["metadata"]["title"],
                         "Ошибка при редактировании роли")
        self.assertEqual(doc["metadata"]["task_type"], "bug")
        self.assertEqual(doc["metadata"]["branch"], "bugfixes/#1422")

    def test_bug_type_derivess_bugfixes_branch(self):
        root, docs, store = self.store()
        ingest.ingest_tracker(store, "3001", payload())
        # create uses default feature type; simulate bug via direct create
        doc = support.minimal_task("3002")
        doc["metadata"]["task_type"] = "bug"
        envelope = {"schema_version": "1.0", "operation_id": "c-3002",
                    "expected_revision": 0, "actor": "user", "reason": "seed",
                    "operations": [], "document": doc}
        store.apply("task", "3002", envelope)
        ingest.ingest_tracker(store, "3002", payload())
        self.assertEqual(store.load("task", "3002")["metadata"]["branch"],
                         "bugfixes/#3002")

    def test_noop_on_same_semantic_payload_new_timestamp(self):
        root, docs, store = self.store()
        ingest.ingest_tracker(store, "2612", payload())
        first = store.load("task", "2612")
        again = dict(payload())
        again["exported_at"] = "2026-09-25T22:00:00Z"
        result = ingest.ingest_tracker(store, "2612", again)
        self.assertEqual(result["status"], "noop")
        self.assertEqual(store.load("task", "2612")["revision"],
                         first["revision"])


    def test_ingest_stores_comments_dates_and_changelog(self):
        root, docs, store = self.store()
        data = payload(total=1)
        data["issue"]["created"] = "2026-09-01T10:00:00.000+0300"
        data["issue"]["updated"] = "2026-09-20T12:00:00.000+0300"
        data["comments_pages"][0]["comments"][0]["clean_text"] = "hello"
        data["changelog_pages"] = [{
            "start_at": 0, "max_results": 1, "total": 1, "is_last": True,
            "histories": [{
                "id": "h1", "created": "2026-09-02T10:00:00.000+0300",
                "author": {"displayName": "QA"},
                "items": [{"field": "status", "fromString": "Open",
                           "toString": "Done"}],
            }],
        }]
        result = ingest.ingest_tracker(store, "2612", data)
        self.assertEqual(result["status"], "applied")
        snapshot = store.load("task", "2612")["tracker"]["snapshot"]
        self.assertEqual(snapshot["updated_at"], "2026-09-20T12:00:00.000+0300")
        self.assertEqual(snapshot["created_at"], "2026-09-01T10:00:00.000+0300")
        self.assertEqual(snapshot["comments"][0]["created_at"],
                         "2026-09-01T00:00:00Z")
        self.assertEqual(snapshot["comments"][0]["text"], "hello")
        self.assertEqual(snapshot["changelog"][0]["items"][0]["field"], "status")
        self.assertTrue(snapshot["coverage"]["changelog"]["complete"])

    def test_ingest_preserves_unrelated_document_fields(self):
        root, docs, store = self.store()
        doc = support.minimal_task("2612")
        doc["summary"] = "keep me"
        doc["business_logic"] = {"facts": [], "linked_rule_ids": []}
        envelope = {"schema_version": "1.0", "operation_id": "seed-2612",
                    "expected_revision": 0, "actor": "user", "reason": "seed",
                    "operations": [], "document": doc}
        store.apply("task", "2612", envelope)
        before = store.load("task", "2612")
        ingest.ingest_tracker(store, "2612", payload(total=1))
        after = store.load("task", "2612")
        self.assertEqual(after["summary"], "keep me")
        self.assertEqual(after["business_logic"], {"facts": [], "unconfirmed": [], "linked_rule_ids": []})
        self.assertEqual(after["revision"], before["revision"] + 1)

    def test_status_change_applies_and_appends_history(self):
        root, docs, store = self.store()
        ingest.ingest_tracker(store, "2612", payload())
        before = store.load("task", "2612")
        result = ingest.ingest_tracker(store, "2612", payload(status="Done"))
        self.assertEqual(result["status"], "applied")
        after = store.load("task", "2612")
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(len(after["history"]), len(before["history"]) + 1)
        self.assertEqual(after["history"][-1]["actor"], "gototask")


import json  # noqa: E402  (used above)

if __name__ == "__main__":
    unittest.main()
