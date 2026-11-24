"""FLOW-CHOICE-1: one machine envelope for all runtime decisions.

The adapter is intentionally transport neutral.  CLI, chat and future IDE/MCP
surfaces hand it the same request/response dictionaries.  A recommendation is
kept as evidence and is never accepted as the user's final selection.
"""

import copy
import hashlib
import json
import re

from .errors import Issue, SkillError

CHOICE_SCHEMA = "FLOW-CHOICE-1"
RESPONSE_SCHEMA = "FLOW-CHOICE-RESPONSE-1"
RECOMMENDATION_SCHEMA = "FLOW-CHOICE-RECOMMENDATION-1"
SELECTIONS = ("boolean", "single", "multiple", "text")
POLICY_SCOPES = ("step", "flow_run", "change", "workspace", "task")
OPTION_KEYS = ("id", "label", "description", "value", "route", "flow",
               "preset", "effects", "policy")
REQUEST_KEYS = ("$schema", "schema", "request_id", "flow_run", "task_ref",
                "decision_id", "question", "selection", "options", "default",
                "allow_custom_response", "policy_scope", "expires_at", "flow_id",
                "flow_revision", "step_id", "version", "source", "metadata")
RESPONSE_KEYS = ("$schema", "schema", "request_id", "flow_run", "task_ref",
                 "decision_id", "selection", "value", "values", "text", "actor", "reason", "source",
                 "recommendation_ref", "policy_scope", "metadata")
RECOMMENDATION_KEYS = ("$schema", "schema", "request_id", "decision_id",
                       "selection", "value", "values", "text", "recommended_option",
                       "rationale", "evidence_refs", "confidence", "actor")


def _failure(code, where, message):
    return Issue("error", where, message, code)


def _unknown(data, allowed, where, code="FLOW_CHOICE_INVALID"):
    return [_failure(code, "%s.%s" % (where, key),
                     "ключ «%s» не объявлен контрактом" % key)
            for key in data if key not in allowed]


def _ids(options):
    return [item.get("id") for item in options if isinstance(item, dict)]


def validate_choice_definition(definition, where="choice", raise_error=False):
    """Return exact-schema issues for a FLOW-CHOICE-1 request."""
    issues = []
    if not isinstance(definition, dict):
        issues.append(_failure("FLOW_CHOICE_INVALID", where,
                              "choice envelope должен быть объектом"))
    else:
        issues.extend(_unknown(definition, REQUEST_KEYS, where))
        for key in ("schema", "request_id", "decision_id", "question", "selection",
                    "options", "default", "allow_custom_response", "policy_scope"):
            if key not in definition:
                issues.append(_failure("FLOW_CHOICE_INVALID", where,
                                      "нет обязательного поля «%s»" % key))
        if definition.get("schema") != CHOICE_SCHEMA:
            issues.append(_failure("FLOW_CHOICE_INVALID", where,
                                  "schema должен быть %s" % CHOICE_SCHEMA))
        for key in ("request_id", "decision_id", "question"):
            if key in definition and (not isinstance(definition[key], str)
                                       or not definition[key].strip()):
                issues.append(_failure("FLOW_CHOICE_INVALID", "%s.%s" % (where, key),
                                      "значение должно быть непустой строкой"))
        selection = definition.get("selection")
        if selection not in SELECTIONS:
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.selection" % where,
                                  "selection должен быть одним из %s" % list(SELECTIONS)))
        options = definition.get("options")
        if not isinstance(options, list):
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.options" % where,
                                  "options должен быть массивом"))
            options = []
        seen = set()
        for pos, option in enumerate(options):
            spot = "%s.options[%d]" % (where, pos)
            if not isinstance(option, dict):
                issues.append(_failure("FLOW_CHOICE_INVALID", spot,
                                      "option должен быть объектом"))
                continue
            issues.extend(_unknown(option, OPTION_KEYS, spot))
            for key in ("id", "label"):
                if not isinstance(option.get(key), str) or not option[key].strip():
                    issues.append(_failure("FLOW_CHOICE_INVALID", spot,
                                          "option требует непустые %s" % key))
            if option.get("id") in seen:
                issues.append(_failure("FLOW_CHOICE_INVALID", spot,
                                      "id option повторяется: %s" % option.get("id")))
            seen.add(option.get("id"))
        if selection in ("boolean", "single", "multiple") and not options:
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.options" % where,
                                  "для %s нужны options" % selection))
        if selection == "single" and options and not (2 <= len(options) <= 6):
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.options" % where,
                                  "single choice требует от 2 до 6 options"))
        if selection == "boolean": 
            values = set(_ids(options))
            if values and values != {"true", "false"} and values != {True, False}:
                # bool choices may use explicit IDs; permit only exactly two.
                if len(values) != 2:
                    issues.append(_failure("FLOW_CHOICE_INVALID", "%s.options" % where,
                                          "boolean choice требует ровно два варианта"))
        if selection == "multiple" and definition.get("default") is not None:
            if not isinstance(definition.get("default"), list):
                issues.append(_failure("FLOW_CHOICE_INVALID", "%s.default" % where,
                                      "default multiple должен быть массивом"))
        if definition.get("policy_scope") not in POLICY_SCOPES:
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.policy_scope" % where,
                                  "policy_scope должен быть одним из %s" % list(POLICY_SCOPES)))
        if not isinstance(definition.get("allow_custom_response"), bool):
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.allow_custom_response" % where,
                                  "allow_custom_response должен быть boolean"))
        if selection == "text" and definition.get("allow_custom_response") is not True:
            issues.append(_failure("FLOW_CHOICE_INVALID", "%s.allow_custom_response" % where,
                                  "text selection требует allow_custom_response=true"))
        default = definition.get("default")
        if default is not None:
            values = set(_ids(options))
            check = default if isinstance(default, list) else [default]
            boolean_default_ok = (selection == "boolean"
                                  and isinstance(default, bool)
                                  and {"true", "false"}.issubset(values))
            if selection != "text" and not boolean_default_ok \
                    and any(value not in values for value in check):
                issues.append(_failure("FLOW_CHOICE_INVALID", "%s.default" % where,
                                      "default содержит вариант не из options"))
            if selection == "multiple" and len(set(check)) != len(check):
                issues.append(_failure("FLOW_CHOICE_INVALID", "%s.default" % where,
                                      "default multiple содержит повторы"))
    if raise_error and any(issue.is_error for issue in issues):
        first = issues[0]
        raise SkillError(first.code, first.message, first.where)
    return issues


def make_choice_request(request_id, decision_id, question, selection="single",
                        options=None, default=None, allow_custom_response=False,
                        policy_scope="flow_run", flow_id=None, flow_revision=None,
                        step_id=None, version=1, source=None, metadata=None,
                        flow_run=None, task_ref=None, expires_at=None):
    """Build and validate a canonical request; no caller text is synthesized."""
    if selection == "boolean" and not options:
        options = [{"id": "true", "label": "Да", "description": "true"},
                   {"id": "false", "label": "Нет", "description": "false"}]
        if isinstance(default, bool):
            default = "true" if default else "false"
    request = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema": CHOICE_SCHEMA, "request_id": request_id, "flow_run": flow_run,
        "task_ref": task_ref, "decision_id": decision_id, "question": question,
        "selection": selection, "options": copy.deepcopy(options or []),
        "default": default, "allow_custom_response": bool(allow_custom_response),
        "policy_scope": policy_scope, "expires_at": expires_at, "flow_id": flow_id,
        "flow_revision": flow_revision, "step_id": step_id,
        "version": version, "source": source, "metadata": metadata or {},
    }
    validate_choice_definition(request, raise_error=True)
    return request


def _normalise_value(request, value=None, values=None, text=None):
    selection = request.get("selection")
    options = _ids(request.get("options") or [])
    if selection == "multiple":
        chosen = values if values is not None else value
        if not isinstance(chosen, list):
            raise SkillError("FLOW_CHOICE_INVALID", "multiple choice требует values[]",
                             request.get("request_id", "choice"))
        result = list(chosen)
        if len(result) != len(set(result)):
            raise SkillError("FLOW_CHOICE_INVALID", "multiple choice содержит повтор",
                             request.get("request_id", "choice"))
        if any(item not in options for item in result):
            raise SkillError("FLOW_CHOICE_INVALID", "выбран вариант не из allowlist",
                             request.get("request_id", "choice"))
        return None, result, None
    if selection == "text":
        result = text if text is not None else value
        if not request.get("allow_custom_response"):
            raise SkillError("FLOW_CHOICE_INVALID", "text choice не разрешает custom response",
                             request.get("request_id", "choice"))
        if not isinstance(result, str) or not result.strip():
            raise SkillError("FLOW_CHOICE_INVALID", "text choice требует непустой текст",
                             request.get("request_id", "choice"))
        return None, None, result
    result = value
    if selection == "boolean":
        # The wire option ids remain strings for exact JSON compatibility, while
        # the canonical response preserves a real boolean for true/false.
        if isinstance(result, bool) and {"true", "false"}.issubset(set(options)):
            return result, None, None
        if result in ("true", "false") and {"true", "false"}.issubset(set(options)):
            return result == "true", None, None
    if result not in options:
        # boolean definitions may use actual booleans as option ids.
        if not (selection == "boolean" and isinstance(result, bool)
                and {True, False}.issubset(set(options))):
            raise SkillError("FLOW_CHOICE_INVALID", "выбран вариант не из allowlist",
                             request.get("request_id", "choice"))
    return result, None, None


def validate_choice_response(request, response, actor=None, require_user=True):
    """Validate final choice.  Recommendation-only responses are rejected."""
    validate_choice_definition(request, raise_error=True)
    if not isinstance(response, dict):
        raise SkillError("FLOW_CHOICE_INVALID", "choice response должен быть объектом",
                         request.get("request_id", "choice"))
    if response.get("schema") == RECOMMENDATION_SCHEMA or response.get("source") == "agent":
        raise SkillError("FLOW_CHOICE_USER_REQUIRED",
                         "recommendation агента не является выбором пользователя",
                         request.get("request_id", "choice"))
    issues = _unknown(response, RESPONSE_KEYS, "choice.response")
    if issues:
        raise SkillError(issues[0].code, issues[0].message, issues[0].where)
    if response.get("schema") not in (None, RESPONSE_SCHEMA):
        raise SkillError("FLOW_CHOICE_INVALID", "schema response неизвестен",
                         request.get("request_id", "choice"))
    if response.get("request_id") != request.get("request_id"):
        raise SkillError("FLOW_CHOICE_INVALID", "response относится к другому request_id",
                         request.get("request_id", "choice"))
    if require_user and response.get("source") not in ("user", "policy"):
        raise SkillError("FLOW_CHOICE_USER_REQUIRED",
                         "recommendation агента не является выбором пользователя",
                         request.get("request_id", "choice"))
    if response.get("selection") and response.get("selection") != request.get("selection"):
        raise SkillError("FLOW_CHOICE_INVALID", "тип выбора response не совпадает",
                         request.get("request_id", "choice"))
    value, values, text = _normalise_value(request, response.get("value"),
                                           response.get("values"), response.get("text"))
    result = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema": RESPONSE_SCHEMA, "request_id": request["request_id"],
        "decision_id": request["decision_id"], "selection": request["selection"],
        "value": value, "values": values, "text": text,
        "actor": actor or response.get("actor"),
        "reason": response.get("reason"), "source": response.get("source") or "user",
        "recommendation_ref": response.get("recommendation_ref"),
        "policy_scope": request.get("policy_scope"),
        "metadata": response.get("metadata") or {},
    }
    return result


def make_recommendation(request, value=None, values=None, text=None,
                         rationale="", evidence_refs=None, actor="agent",
                         confidence=None):
    validate_choice_definition(request, raise_error=True)
    # Validate the recommendation value against exactly the same allowlist but
    # do not turn it into a final response.
    final = _normalise_value(request, value, values, text)
    result = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema": RECOMMENDATION_SCHEMA, "request_id": request["request_id"],
        "decision_id": request["decision_id"], "selection": request["selection"],
        "value": final[0], "values": final[1], "text": final[2],
        "recommended_option": final[0] if final[0] is not None else final[1] or final[2],
        "rationale": str(rationale or ""), "evidence_refs": list(evidence_refs or []),
        "confidence": confidence, "actor": actor,
    }
    return result


def answer_from_policy(request, policy_value, actor="policy", reason="deterministic policy"):
    """Create a final response only for a deterministic policy decision."""
    return validate_choice_response(request, {
        "schema": RESPONSE_SCHEMA, "request_id": request["request_id"],
        "decision_id": request["decision_id"], "selection": request["selection"],
        "value": policy_value, "source": "policy", "actor": actor,
        "reason": reason,
    }, actor=actor, require_user=True)


def choice_fingerprint(request):
    body = json.dumps(request, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


DECISION_TREE_SCHEMA = "DECISION-TREE-1"
DECISION_TREE_NODE_KEYS = ("id", "field", "routes", "default")


def validate_decision_tree(tree, where="decision_tree"):
    """Validate a deterministic routing tree without inventing branches.

    A node may name the record field from which its choice is read.  When the
    field is omitted, the runtime uses the node id.  Targets that are not
    another node are terminal flow/step targets and are checked by the owning
    flow adapter when it knows the step allowlist.
    """
    issues = []
    if not isinstance(tree, dict):
        return [_failure("FLOW_DECISION_TREE_INVALID", where,
                         "decision tree должен быть объектом")]
    allowed = ("$schema", "schema", "id", "version", "root", "nodes", "default")
    issues.extend(_failure("FLOW_DECISION_TREE_INVALID", "%s.%s" % (where, key),
                           "ключ не из DECISION-TREE-1") for key in tree if key not in allowed)
    for key in ("schema", "id", "version", "root", "nodes"):
        if key not in tree:
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", where,
                                  "decision tree без %s" % key))
    if tree.get("schema") != DECISION_TREE_SCHEMA:
        issues.append(_failure("FLOW_DECISION_TREE_INVALID", where,
                              "schema должен быть %s" % DECISION_TREE_SCHEMA))
    nodes = tree.get("nodes")
    if isinstance(nodes, list):
        normal = {item.get("id"): item for item in nodes if isinstance(item, dict)}
        if len(normal) != len(nodes):
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.nodes" % where,
                                  "node id должен быть уникальным"))
    elif isinstance(nodes, dict):
        normal = nodes
    else:
        normal = {}
        issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.nodes" % where,
                              "nodes должен быть list или object"))
    if tree.get("root") not in normal:
        issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.root" % where,
                              "root node отсутствует"))
    for node_id, node in normal.items():
        spot = "%s.nodes.%s" % (where, node_id)
        if not isinstance(node, dict):
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", spot,
                                  "node должен быть объектом"))
            continue
        issues.extend(_failure("FLOW_DECISION_TREE_INVALID", "%s.%s" % (spot, key),
                               "ключ не из DECISION-TREE-1 node")
                      for key in node if key not in DECISION_TREE_NODE_KEYS)
        if not isinstance(node_id, str) or not node_id.strip():
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", spot,
                                  "node id должен быть непустой строкой"))
        if node.get("field") is not None and (not isinstance(node.get("field"), str)
                                                or not node.get("field").strip()):
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.field" % spot,
                                  "field должен быть непустой строкой"))
        routes = node.get("routes")
        if not isinstance(routes, dict) or not routes:
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", spot,
                                  "node routes должен быть непустым объектом"))
            routes = {}
        if node.get("default") is not None and node.get("default") not in routes:
            issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.default" % spot,
                                  "default должен быть ключом routes"))
        for target in routes.values():
            target_id = target.get("target") if isinstance(target, dict) else target
            if not isinstance(target_id, str) or not target_id.strip():
                issues.append(_failure("FLOW_DECISION_TREE_INVALID", "%s.routes" % spot,
                                      "route target должен быть непустой строкой"))
                continue
            if target_id not in normal and target_id not in ("human-decision", "block"):
                # Leaf routes are arbitrary allowlisted flow/step IDs.  They
                # are terminal when they are not another tree node.
                continue
    return issues


def branch_decision_tree(tree, choices, where="decision_tree"):
    """Follow only declared routes after validated choices; no free-form branch."""
    issues = validate_decision_tree(tree, where)
    if any(item.is_error for item in issues):
        first = issues[0]
        raise SkillError(first.code, first.message, first.where)
    nodes = {item.get("id"): item for item in tree["nodes"]} if isinstance(tree["nodes"], list) else tree["nodes"]
    current = tree["root"]
    visited = set()
    provenance = []
    while current in nodes:
        if current in visited:
            raise SkillError("FLOW_DECISION_TREE_INVALID", "decision tree содержит cycle", where)
        visited.add(current)
        node = nodes[current]
        value = choices.get(current) if isinstance(choices, dict) else None
        if value is None:
            default = node.get("default")
            value = default
        if value is None:
            raise SkillError("FLOW_CHOICE_REQUIRED", "нет validated choice для node %s" % current,
                             "%s.nodes.%s" % (where, current))
        target = (node.get("routes") or {}).get(str(value))
        if target is None:
            target = (node.get("routes") or {}).get(value)
        if isinstance(target, dict):
            target_id = target.get("target")
        else:
            target_id = target
        if target_id is None:
            raise SkillError("FLOW_CHOICE_INVALID", "route для %s=%s не объявлен" % (current, value),
                             "%s.nodes.%s" % (where, current))
        provenance.append({"node": current, "value": value, "target": target_id})
        current = target_id
    return {"target": current, "provenance": provenance,
            "tree_id": tree.get("id"), "tree_version": tree.get("version")}


class DecisionTree:
    """Small object facade for deterministic decision-tree evaluation."""

    def __init__(self, definition):
        issues = validate_decision_tree(definition)
        if any(item.is_error for item in issues):
            first = issues[0]
            raise SkillError(first.code, first.message, first.where)
        self.definition = copy.deepcopy(definition)

    def branch(self, choices):
        return branch_decision_tree(self.definition, choices)


class ChoiceAdapter:
    """Transport adapter facade used by flow and CLI code."""

    @staticmethod
    def request(**kwargs):
        return make_choice_request(**kwargs)

    @staticmethod
    def recommendation(request, **kwargs):
        return make_recommendation(request, **kwargs)

    @staticmethod
    def answer(request, response, actor=None):
        return validate_choice_response(request, response, actor=actor)
