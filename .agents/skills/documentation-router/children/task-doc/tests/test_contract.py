"""J01 contract tests: schema strictness, semantics, examples stay valid."""

import copy
import json
import unittest
from pathlib import Path

import support
from jsondoc import contract

SCHEMAS = support.SCRIPTS_DIR / "schemas"


class SchemaKeywordTests(unittest.TestCase):
    def test_unsupported_keyword_rejected_at_load(self):
        bad = {"type": "object", "properties": {"x": {"type": "string",
                                                      "maxLength": 3}}}
        with self.assertRaises(contract.ContractError) as ctx:
            contract._check_keywords(bad, "$")
        self.assertIn("unsupported_keyword", str(ctx.exception))

    def test_bool_never_passes_integer(self):
        errors = contract.validate_schema(True, {"type": "integer"}, )
        self.assertTrue(any(e["code"] == "type_mismatch" for e in errors))

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(contract.ContractError):
            contract.load_json_strict('{"a": 1, "a": 2}')


class DocumentTests(unittest.TestCase):
    def test_minimal_task_valid(self):
        doc = support.minimal_task()
        self.assertEqual(contract.validate_document(doc), [])

    def test_unknown_field_rejected(self):
        doc = support.minimal_task()
        doc["surprise"] = 1
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "unknown_fields" for e in errors))

    def test_missing_required_field_rejected(self):
        doc = support.minimal_task()
        del doc["tracker"]
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "missing_field" and
                            e["at"] == "$.tracker" for e in errors))

    def test_bad_status_enum_rejected(self):
        doc = support.minimal_task()
        doc["metadata"]["status"] = "green-ish"
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "enum_violation" for e in errors))

    def test_task_id_coupling(self):
        doc = support.minimal_task()
        doc["metadata"]["task_id"] = None
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "task_id_required" for e in errors))

    def test_cross_reference_unknown_rejected(self):
        doc = support.minimal_task()
        doc["findings"].append({
            "id": "ПК-1", "kind": "pitfall", "title": "т", "statement": "с",
            "symptom": None, "cause": None, "resolution": None,
            "status": "observed", "severity": None, "file_ids": ["no-such-file"],
            "source_ids": ["no-such-source"], "superseded_by": None,
            "section_id": None})
        errors = contract.validate_document(doc)
        codes = {e["code"] for e in errors}
        self.assertIn("unknown_reference", codes)

    def test_stage_graph_cycle_rejected(self):
        doc = support.minimal_task()
        base = {
            "title": "s", "status": "planned", "placeholder": False,
            "trigger": None, "superseded_by": None, "plan_artifact_id": None,
            "diff_artifact_ids": [], "diff_manifest_id": None,
            "test_artifact_ids": [], "test_run_ids": [], "documentation_refs": [],
            "requirement_ids": [], "source_ids": []}
        doc["stages"] = [
            {"id": "stage:1", "number": 1, "depends_on": ["stage:2"], **base},
            {"id": "stage:2", "number": 2, "depends_on": ["stage:1"], **base}]
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] in ("stage_dependency_cycle",
                                          "duplicate_stage_numbers")
                            for e in errors))

    def test_section_order_must_cover_all(self):
        doc = support.minimal_task()
        doc["sections"].append({
            "id": "s1", "title": "Т", "level": 2, "parent_id": None,
            "anchor": "т", "anchor_aliases": [], "body_markdown": "",
            "source_ids": [], "origin": "authored"})
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "section_order_mismatch"
                            for e in errors))
        doc["section_order"] = ["s1"]
        self.assertEqual(contract.validate_document(doc), [])

    def test_sha256_pattern_enforced(self):
        doc = support.minimal_task()
        doc["sources"].append({
            "id": "S1", "kind": "doc", "path": ".doc/x.md", "pointer": None,
            "sha256": "zz", "revision": None, "observed_at": None,
            "observation": None, "availability": "present"})
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "pattern_mismatch" for e in errors))

    def test_utc_pattern_enforced(self):
        doc = support.minimal_task()
        doc["metadata"]["updated_at"] = "25.09.2026"
        errors = contract.validate_document(doc)
        self.assertTrue(any(e["code"] == "pattern_mismatch" for e in errors))


class UpdateEnvelopeTests(unittest.TestCase):
    def envelope(self):
        return {
            "schema_version": "1.0",
            "operation_id": "op-001",
            "expected_revision": 1,
            "actor": "task-doc",
            "reason": "обновление",
            "operations": [{"op": "set", "collection": "summary",
                            "key": "summary", "value": "текст"}],
            "document": None,
        }

    def test_valid_update(self):
        self.assertEqual(contract.validate_update(self.envelope()), [])

    def test_create_with_operations_rejected(self):
        env = self.envelope()
        env["document"] = support.minimal_task()
        env["expected_revision"] = 0
        errors = contract.validate_update(env)
        self.assertTrue(any(e["code"] == "create_with_operations"
                            for e in errors))

    def test_create_revision_zero(self):
        env = self.envelope()
        env["document"] = support.minimal_task()
        env["operations"] = []
        errors = contract.validate_update(env)
        self.assertTrue(any(e["code"] == "create_requires_revision_zero"
                            for e in errors))
        env["expected_revision"] = 0
        self.assertEqual(contract.validate_update(env), [])

    def test_set_whitelist(self):
        env = self.envelope()
        env["operations"][0]["collection"] = "history"
        errors = contract.validate_update(env)
        self.assertTrue(any(e["code"] == "set_collection_not_whitelisted"
                            for e in errors))


class TagsDictionaryTests(unittest.TestCase):
    def dictionary(self):
        return {
            "schema_version": "1.0", "revision": 1,
            "tags": [
                {"id": "domain:orders", "kind": "domain", "label": "Заказы",
                 "description": "Домен заказов", "aliases": ["orders"],
                 "parents": [], "status": "active", "replaced_by": None},
                {"id": "process:order-cancellation", "kind": "process",
                 "label": "Отмена заказа", "description": "Отмена и возврат",
                 "aliases": ["отмена заказа"],
                 "parents": [], "status": "active", "replaced_by": None},
            ],
        }

    def test_valid_dictionary(self):
        self.assertEqual(contract.validate_tags_dictionary(self.dictionary()), [])

    def test_ambiguous_alias_rejected(self):
        data = self.dictionary()
        data["tags"][1]["kind"] = "domain"
        data["tags"][1]["aliases"].append("orders")
        errors = contract.validate_tags_dictionary(data)
        self.assertTrue(any(e["code"] == "ambiguous_alias" for e in errors))

    def test_parent_cycle_rejected(self):
        data = self.dictionary()
        data["tags"][0]["parents"] = ["process:order-cancellation"]
        data["tags"][1]["parents"] = ["domain:orders"]
        errors = contract.validate_tags_dictionary(data)
        self.assertTrue(any(e["code"] == "parent_cycle" for e in errors))

    def test_deprecated_needs_replacement(self):
        data = self.dictionary()
        data["tags"][0]["status"] = "deprecated"
        errors = contract.validate_tags_dictionary(data)
        self.assertTrue(any(e["code"] == "deprecated_without_replacement"
                            for e in errors))


class PlanExamplesStayValid(unittest.TestCase):
    """Every json example in .doc/jsondoc.md must parse (plan section 13)."""

    def test_plan_json_examples_parse(self):
        plan = (support.SCRIPTS_DIR.parents[5] / ".doc" / "harnes" / "jsondoc.md").resolve()
        text = plan.read_text(encoding="utf-8")
        import re
        blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
        self.assertGreaterEqual(len(blocks), 3)
        for block in blocks:
            json.loads(block)


if __name__ == "__main__":
    unittest.main()
