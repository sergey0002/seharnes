"""IT09-IT13 freshness projection tests (J12)."""

import copy
import unittest

import support
from jsondoc import freshness


def seeded():
    doc = support.minimal_task("2612")
    doc["summary"] = "Услуга архивации"
    doc["requirements"].append({
        "id": "AC1", "text": "услуга 2031", "source_ids": [], "stage_ids": [],
        "scenario_refs": [], "state": "open", "reason": None})
    doc["decisions"].append({
        "id": "Р-1", "title": "код 2031", "context": "2030 занят",
        "choice": "2031", "alternatives": [], "status": "accepted",
        "source_ids": [], "superseded_by": None, "section_id": None})
    doc["artifacts"].append({
        "id": "A-spec", "role": "test_spec", "path": ".doc/tasks/2612/test.md",
        "sha256": "b" * 64, "scope": "task", "revision": None,
        "availability": "present", "projection_path": None, "source_ids": []})
    doc["artifacts"].append({
        "id": "A-run", "role": "test_run",
        "path": ".doc/tasks/2612/test-runs/r1", "sha256": None,
        "scope": "task", "revision": None, "availability": "present",
        "projection_path": None, "source_ids": []})
    doc["checks"].append({
        "id": "C1", "artifact_id": "A-run", "scope": "task",
        "revision": None, "source_ids": [], "result": "passed",
        "source_verdict": None,
        "run_identity": {"task": "2612", "stage": None, "group": None,
                         "run": "r1"}})
    doc["git_state"] = {
        "checked_at": "2026-09-25T00:00:00Z", "commit": "a" * 7,
        "pushed_to": [], "contained_in": [], "release_branches": [],
        "not_pushed_refs": [], "fetch_status": "unknown", "source_ids": []}
    return doc


class ReportProjectionTests(unittest.TestCase):
    def test_it10_recording_result_keeps_report_input_hash(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-input-v1")
        changed = copy.deepcopy(doc)
        changed["checks"].append(dict(doc["checks"][0], id="C2",
                                      result="failed"))
        changed["revision"] = doc["revision"] + 1
        changed["git_state"]["pushed_to"] = ["origin/master"]
        changed["metadata"]["updated_at"] = "2026-09-26T00:00:00Z"
        changed["history"].append({"id": "H1", "at": "2026-09-26T00:00:00Z",
                                   "actor": "ingest", "summary": "run",
                                   "source_ids": []})
        after = freshness.semantic_hash(changed, "jsondoc-input-v1")
        self.assertEqual(before, after)

    def test_it11_requirement_change_changes_hash(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-input-v1")
        changed = copy.deepcopy(doc)
        changed["requirements"][0]["text"] = "услуга 2032"
        after = freshness.semantic_hash(changed, "jsondoc-input-v1")
        self.assertNotEqual(before, after)

    def test_output_only_artifact_excluded(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-input-v1")
        changed = copy.deepcopy(doc)
        changed["artifacts"].append(dict(
            doc["artifacts"][1], id="A-report", role="change_report",
            path=".doc/tasks/2612/reports/r.html"))
        after = freshness.semantic_hash(changed, "jsondoc-input-v1")
        self.assertEqual(before, after)

    def test_semantic_summary_change_matters(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-input-v1")
        changed = copy.deepcopy(doc)
        changed["summary"] = "другая суть"
        after = freshness.semantic_hash(changed, "jsondoc-input-v1")
        self.assertNotEqual(before, after)

    def test_it13_self_reference_via_jira_report_text_safe(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-input-v1")
        changed = copy.deepcopy(doc)
        changed["jira_report"] = {"text": "отчёт", "updated_at":
                                  "2026-09-26T00:00:00Z", "release": None,
                                  "source_ids": []}
        after = freshness.semantic_hash(changed, "jsondoc-input-v1")
        self.assertEqual(before, after)


class QaProjectionTests(unittest.TestCase):
    def test_run_result_does_not_change_qa_input(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-qa-input-v1")
        changed = copy.deepcopy(doc)
        changed["checks"][0]["result"] = "failed"
        after = freshness.semantic_hash(changed, "jsondoc-qa-input-v1")
        self.assertEqual(before, after)

    def test_test_spec_hash_change_invalidates(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-qa-input-v1")
        changed = copy.deepcopy(doc)
        changed["artifacts"][0]["sha256"] = "c" * 64
        after = freshness.semantic_hash(changed, "jsondoc-qa-input-v1")
        self.assertNotEqual(before, after)

    def test_accepted_decision_change_invalidates(self):
        doc = seeded()
        before = freshness.semantic_hash(doc, "jsondoc-qa-input-v1")
        changed = copy.deepcopy(doc)
        changed["decisions"][0]["choice"] = "2032"
        after = freshness.semantic_hash(changed, "jsondoc-qa-input-v1")
        self.assertNotEqual(before, after)

    def test_unknown_projection_rejected(self):
        doc = seeded()
        with self.assertRaises(freshness.FreshnessError):
            freshness.semantic_hash(doc, "jsondoc-input-v9")

    def test_descriptor_shape(self):
        doc = seeded()
        d = freshness.descriptor(doc, "jsondoc-input-v1")
        self.assertEqual(d["projection_version"], "jsondoc-input-v1")
        self.assertEqual(d["document_id"], "task:2612")
        self.assertEqual(len(d["semantic_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
