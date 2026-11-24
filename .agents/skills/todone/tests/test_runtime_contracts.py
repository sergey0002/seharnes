"""P0 acceptance tests for FLOW-2 controls, choices, transitions and docs policy."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore.choice import (DecisionTree, make_choice_request, make_recommendation,
                           validate_choice_response)
from tdcore.contracts import validate_contract_file
from tdcore.documentation import (DocumentationWorkspace, apply_documentation_policy_intent,
                                  parse_documentation_intent)
from tdcore.errors import SkillError
from tdcore.flow import FlowIndex, FlowState
from tdcore.queue import Queue, Registry
from tdcore.typedefs import TypeIndex

ROOT = Path(__file__).resolve().parents[1]


class RuntimeContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        Registry(str(self.root)).register("site", str(self.root / "tasks" / "site"))
        self.queue = Queue(str(self.root), "site")
        self.types = TypeIndex(str(ROOT / "assets" / "types"))

    def tearDown(self):
        self.tmp.cleanup()

    def _controlled_flow(self, flow_id="controlled"):
        folder = self.root / ".todone" / "flows" / flow_id
        folder.mkdir(parents=True)
        payload = {
            "schema": "FLOW-2", "id": flow_id, "name": "Controlled", "entry": "source",
            "steps": [{"id": "review", "type": "code-review", "input_from": [], "output": [],
                        "step_control": {"schema": "FLOW-STEP-CONTROL-1",
                            "enabled_by_default": True, "confirmation": "always",
                            "question": {"id": "review-confirm", "text": "Run review?",
                                          "choices": ["run_now", "skip_once", "cancel"],
                                          "default": "run_now"},
                            "on_decline": "skip_with_reason", "on_disabled": "skip_with_reason"}}]}
        (folder / "flow.json").write_text(json.dumps(payload), encoding="utf-8")
        (folder / "instruction.md").write_text("# controlled", encoding="utf-8")
        return FlowIndex(str(ROOT / "assets" / "flows"), str(self.root / ".todone" / "flows"))

    def test_choice_recommendation_is_not_final_user_choice(self):
        request = make_choice_request("choice:test", "decision", "Pick", options=[
            {"id": "a", "label": "A"}, {"id": "b", "label": "B"}], default="a")
        recommendation = make_recommendation(request, value="a", rationale="evidence", actor="agent")
        with self.assertRaises(SkillError) as caught:
            validate_choice_response(request, recommendation)
        self.assertEqual(caught.exception.code, "FLOW_CHOICE_USER_REQUIRED")
        answer = validate_choice_response(request, {"request_id": request["request_id"],
            "value": "b", "source": "user", "actor": "human"})
        self.assertEqual(answer["value"], "b")

    def test_control_question_is_required_and_skip_is_persisted(self):
        flows = self._controlled_flow()
        source = self.queue.create("source", "default")
        state = FlowState(self.queue, flows, self.types)
        with self.assertRaises(SkillError) as caught:
            state.start("controlled", source.id)
        self.assertEqual(caught.exception.code, "FLOW_CHOICE_REQUIRED")
        request = caught.exception.request
        created, remaining = state.start("controlled", source.id, by="human", choice={
            "request_id": request["request_id"], "value": "skip_once", "source": "user"})
        self.assertEqual(created, [])
        self.assertEqual(remaining, [])
        ledger = json.loads((self.root / ".todone" / "flow-decisions.json").read_text())
        self.assertEqual(ledger["decisions"][0]["outcome"]["action"], "skip")

    def test_entry_selector_is_allowlisted_and_records_provenance(self):
        flows = self._controlled_flow("one")
        request = flows.entry_choice(allowlist=["one", "jira-fix"])
        result = FlowState(self.queue, flows, self.types).select_entry(request, {
            "request_id": request["request_id"], "value": "one", "source": "user"})
        self.assertEqual(result["flow"], "one")
        self.assertTrue((self.root / ".todone" / "flow-decisions.json").is_file())
        with self.assertRaises(SkillError):
            flows.entry_choice(allowlist=["not-allowlisted"])

    def test_transition_preserves_old_run_and_creates_linked_run(self):
        flows = FlowIndex(str(ROOT / "assets" / "flows"), str(self.root / ".todone" / "flows"))
        source = self.queue.create("source", "default")
        state = FlowState(self.queue, flows, self.types)
        first, _ = state.start("jira-fix", source.id, by="human")
        result = state.transition(first[0].id, "issue-delivery", target_step="intake", by="human")
        self.assertEqual(result["transition"]["status"], "applied")
        self.assertEqual(self.queue.index.find(first[0].id)["flow_run_status"], "switched")
        self.assertNotEqual(result["old_run"]["run"], result["new_run"]["run"])
        self.assertTrue((self.root / ".todone" / "flow-transitions.json").is_file())

    def test_docs_revision_and_scoped_policy(self):
        workspace = DocumentationWorkspace(str(self.root))
        workspace.init()
        workspace.write_module("entity/order", "entity", "one", status="active")
        workspace.write_module("entity/order", "entity", "two", status="active")
        self.assertEqual(workspace.read_module("entity/order", revision=1)["content"], "one")
        self.assertEqual(workspace.read_module("entity/order")["content"], "two")
        self.assertEqual(parse_documentation_intent("обычное обсуждение"), None)
        self.assertEqual(parse_documentation_intent("задокументируй")["kind"], "capture")
        apply_documentation_policy_intent(str(self.root), "документация: только по команде", actor="owner")
        self.assertEqual(workspace.policy()["automation"], "manual")
        with self.assertRaises(SkillError):
            apply_documentation_policy_intent(str(self.root), "документация: отключить", actor="chat")
        workspace.set_policy({"enforcement": "required"}, by="owner")
        with self.assertRaises(SkillError) as caught:
            workspace.set_policy({"enforcement": "advisory"}, by="chat")
        self.assertEqual(caught.exception.code, "DOC_POLICY_CONFLICT")
        workspace.set_policy({"enforcement": "advisory"}, by="owner", approved_by="owner")

    def test_docs_path_is_configurable_and_survives_restart(self):
        workspace = DocumentationWorkspace(str(self.root), docs_path="documentation")
        manifest = workspace.init(workspace_id="custom", product_id="product")
        self.assertEqual(manifest["docs_path"], "documentation")
        self.assertTrue((self.root / "documentation" / "manifest.json").is_file())
        self.assertTrue((self.root / ".todone" / "docs-path.json").is_file())

        restarted = DocumentationWorkspace(str(self.root))
        self.assertEqual(restarted.docs_path, str(self.root / "documentation"))
        restarted.write_module("entity/order", "entity", "custom path", status="active")
        self.assertTrue((self.root / "documentation" / "entities" / "order.md").is_file())
        with self.assertRaises(SkillError) as caught:
            DocumentationWorkspace(str(self.root), docs_path="../outside")
        self.assertEqual(caught.exception.code, "DOC_PATH_INVALID")

    def test_choice_variants_use_one_envelope(self):
        definitions = [
            ("boolean", {}, {"value": True}, "value"),
            ("multiple", {"options": [{"id": "a", "label": "A"},
                                        {"id": "b", "label": "B"}]},
             {"values": ["a", "b"]}, "values"),
            ("text", {"allow_custom_response": True}, {"text": "bounded answer"}, "text"),
        ]
        for selection, options, answer, field in definitions:
            request = make_choice_request("choice:" + selection, "decision", "Question",
                                           selection=selection, **options)
            response = dict(answer, request_id=request["request_id"], source="user")
            result = validate_choice_response(request, response)
            self.assertEqual(result["schema"], "FLOW-CHOICE-RESPONSE-1")
            self.assertEqual(result[field], answer[field])

    def test_decision_tree_is_deterministic_and_declared(self):
        tree = DecisionTree({
            "schema": "DECISION-TREE-1", "id": "change-route", "version": 1,
            "root": "impact", "nodes": [{
                "id": "impact", "routes": {"low": "quick_fix", "high": "review"}
            }]
        })
        first = tree.branch({"impact": "high"})
        second = tree.branch({"impact": "high"})
        self.assertEqual(first, second)
        self.assertEqual(first["target"], "review")
        with self.assertRaises(SkillError):
            tree.branch({"impact": "unknown"})

    def test_contract_dispatch_accepts_valid_and_rejects_negative_fixtures(self):
        fixture_root = ROOT / "assets" / "fixtures" / "runtime"
        for name in ("flow-choice.valid.json", "flow-doc.valid.json",
                     "doc-query.valid.json", "doc-writer.valid.json",
                     "doc-path.valid.json"):
            _, issues = validate_contract_file(str(fixture_root / name))
            self.assertFalse([item for item in issues if item.is_error], name)
        for name in ("flow-choice.invalid-recommendation.json",
                     "doc-claim.invalid-no-evidence.json",
                     "doc-query.invalid-unknown.json", "doc-path.invalid.json"):
            _, issues = validate_contract_file(str(fixture_root / name))
            self.assertTrue(any(item.is_error for item in issues), name)

    def test_disabled_optional_documentation_is_persisted_and_required_conflicts(self):
        folder = self.root / ".todone" / "flows" / "docs-control"
        folder.mkdir(parents=True)
        definition = {
            "schema": "FLOW-2", "id": "docs-control", "name": "Docs control",
            "entry": "source", "steps": [{
                "id": "doc", "type": "doc", "input_from": [], "optional": True,
                "documentation": {
                    "schema": "FLOW-DOC-1", "policy_key": "documentation", "required": False,
                    "confirmation": "effective_policy", "question": {
                        "id": "DOC", "text": "Document?",
                        "choices": ["document_now", "skip_once", "cancel"],
                        "default": "document_now"
                    }, "on_decline": "block|skip_with_reason|manual_only",
                    "automation": "disabled", "cadence": "aggregate",
                    "update_after": "all_tests", "verify": "on_close",
                    "enforcement": "advisory", "retain_impact_record": True
                }
            }]
        }
        (folder / "flow.json").write_text(json.dumps(definition), encoding="utf-8")
        (folder / "instruction.md").write_text("# docs", encoding="utf-8")
        workspace = DocumentationWorkspace(str(self.root))
        workspace.init()
        workspace.set_policy({"automation": "disabled"}, by="owner")
        flows = FlowIndex(str(ROOT / "assets" / "flows"), str(self.root / ".todone" / "flows"))
        state = FlowState(self.queue, flows, self.types)
        source = self.queue.create("docs source", "default")
        created, remaining = state.start("docs-control", source.id, by="human")
        self.assertEqual(created, [])
        self.assertEqual(remaining, [])
        decision = json.loads((self.root / ".todone" / "flow-decisions.json").read_text())
        self.assertEqual(decision["decisions"][0]["outcome"]["action"], "skip")
        definition["steps"][0]["optional"] = False
        definition["steps"][0]["documentation"]["required"] = True
        (folder / "flow.json").write_text(json.dumps(definition), encoding="utf-8")
        required_flows = FlowIndex(str(ROOT / "assets" / "flows"), str(self.root / ".todone" / "flows"))
        required_state = FlowState(self.queue, required_flows, self.types)
        required_source = self.queue.create("required docs source", "default")
        with self.assertRaises(SkillError) as caught:
            required_state.start("docs-control", required_source.id, by="human")
        self.assertEqual(caught.exception.code, "DOC_POLICY_CONFLICT")
        definition["steps"][0]["optional"] = True
        definition["steps"][0]["documentation"]["required"] = False
        definition["steps"][0]["documentation"].pop("automation", None)
        (folder / "flow.json").write_text(json.dumps(definition), encoding="utf-8")
        workspace.set_policy({"automation": "manual"}, by="owner")
        manual_flows = FlowIndex(str(ROOT / "assets" / "flows"), str(self.root / ".todone" / "flows"))
        manual_state = FlowState(self.queue, manual_flows, self.types)
        manual_source = self.queue.create("manual docs source", "default")
        created, remaining = manual_state.start("docs-control", manual_source.id, by="human")
        self.assertEqual(created, [])
        self.assertEqual(remaining, ["doc"])
        created, _ = manual_state.start("docs-control", manual_source.id, by="human",
                                       explicit_document=True)
        self.assertEqual(len(created), 1)


if __name__ == "__main__":
    unittest.main()
