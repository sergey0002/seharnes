"""Declarative FLOW-STEP-CONTROL-1 and FLOW-DOC-1 runtime policy.

Nothing in this module invents a question or route.  A step is controlled only
when ``flow.json`` contains the explicit extension; all question text, choices,
default and outcomes are read from that definition and machine-validated.
"""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone

from .choice import (CHOICE_SCHEMA, make_choice_request, validate_choice_definition,
                     validate_choice_response)
from .errors import Issue, SkillError

CONTROL_SCHEMA = "FLOW-STEP-CONTROL-1"
DOC_SCHEMA = "FLOW-DOC-1"
CONTROL_KEYS = ("schema", "enabled_by_default", "confirmation", "question",
                "on_decline", "on_disabled", "policy_key", "scope")
CONTROL_ROUTES = ("block", "skip_with_reason", "route", "cancel", "manual_only")
CONFIRMATIONS = ("effective_policy", "always", "never")
DOC_KEYS = ("schema", "policy_key", "required", "confirmation", "question",
            "on_decline", "on_disabled", "automation", "cadence", "update_after", "verify",
            "enforcement", "retain_impact_record")


def now_stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_step_control(control, where="step_control"):
    issues = []
    if not isinstance(control, dict):
        return [Issue("error", where, "step_control должен быть объектом",
                      "FLOW_CONTROL_INVALID")]
    for key in control:
        if key not in CONTROL_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из FLOW-STEP-CONTROL-1", "KEY_UNKNOWN"))
    if control.get("schema") != CONTROL_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть %s" % CONTROL_SCHEMA,
                            "FLOW_CONTROL_INVALID"))
    if not isinstance(control.get("enabled_by_default"), bool):
        issues.append(Issue("error", "%s.enabled_by_default" % where,
                            "enabled_by_default должен быть boolean",
                            "FLOW_CONTROL_INVALID"))
    if control.get("confirmation") not in CONFIRMATIONS:
        issues.append(Issue("error", "%s.confirmation" % where,
                            "confirmation должен быть одним из %s" % list(CONFIRMATIONS),
                            "FLOW_CONTROL_INVALID"))
    question = control.get("question")
    if not isinstance(question, dict):
        issues.append(Issue("error", "%s.question" % where,
                            "question обязателен и должен быть объектом",
                            "FLOW_CONTROL_INVALID"))
    else:
        # The question is itself the canonical FLOW-CHOICE envelope fragment.
        for key in ("id", "text", "choices", "default"):
            if key not in question:
                issues.append(Issue("error", "%s.question" % where,
                                    "question без поля %s" % key,
                                    "FLOW_CONTROL_INVALID"))
        if not isinstance(question.get("id"), str) or not question.get("id"):
            issues.append(Issue("error", "%s.question.id" % where,
                                "id вопроса обязателен", "FLOW_CONTROL_INVALID"))
        if not isinstance(question.get("text"), str) or not question.get("text").strip():
            issues.append(Issue("error", "%s.question.text" % where,
                                "text вопроса обязателен", "FLOW_CONTROL_INVALID"))
        choices = question.get("choices")
        selection = question.get("selection", "single")
        if not isinstance(choices, list) or (not choices and selection != "text"):
            issues.append(Issue("error", "%s.question.choices" % where,
                                "choices вопроса — массив; для non-text он непустой",
                                "FLOW_CONTROL_INVALID"))
        else:
            seen = set()
            for choice in choices:
                # Legacy/control shorthand is a string; object choices are also
                # accepted and retain labels/metadata for the adapter.
                cid = choice.get("id") if isinstance(choice, dict) else choice
                if not isinstance(cid, str) or not cid.strip():
                    issues.append(Issue("error", "%s.question.choices" % where,
                                        "choice должен иметь непустой id",
                                        "FLOW_CONTROL_INVALID"))
                if cid in seen:
                    issues.append(Issue("error", "%s.question.choices" % where,
                                        "choice повторяется: %s" % cid,
                                        "FLOW_CONTROL_INVALID"))
                seen.add(cid)
            if selection != "text" and question.get("default") not in seen:
                issues.append(Issue("error", "%s.question.default" % where,
                                    "default не входит в choices", "FLOW_CONTROL_INVALID"))
            if selection == "text" and question.get("allow_custom_response") is not True:
                issues.append(Issue("error", "%s.question.allow_custom_response" % where,
                                    "text choice требует явного allow_custom_response=true",
                                    "FLOW_CONTROL_INVALID"))
    for key in ("on_decline", "on_disabled"):
        if key not in control:
            issues.append(Issue("error", where, "step_control без поля %s" % key,
                                "FLOW_CONTROL_INVALID"))
        value = control.get(key)
        if value is not None:
            if isinstance(value, str):
                values = [item for item in value.split("|") if item]
            elif isinstance(value, list):
                values = []
                for item in value:
                    values.extend(str(item).split("|") if isinstance(item, str) else [item])
            else:
                values = []
            for item in values:
                if item not in CONTROL_ROUTES:
                    issues.append(Issue("error", "%s.%s" % (where, key),
                                        "route «%s» не разрешён" % item,
                                        "FLOW_CONTROL_INVALID"))
            if not values:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "route должен быть разрешённым значением",
                                    "FLOW_CONTROL_INVALID"))
    return issues


def validate_doc_extension(documentation, where="documentation"):
    issues = []
    if not isinstance(documentation, dict):
        return [Issue("error", where, "documentation должен быть объектом",
                      "FLOW_DOC_INVALID")]
    for key in documentation:
        if key not in DOC_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из FLOW-DOC-1", "KEY_UNKNOWN"))
    if documentation.get("schema") != DOC_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть %s" % DOC_SCHEMA,
                            "FLOW_DOC_INVALID"))
    if documentation.get("policy_key") not in (None, "documentation"):
        issues.append(Issue("error", "%s.policy_key" % where,
                            "policy_key должен быть documentation", "FLOW_DOC_INVALID"))
    if not isinstance(documentation.get("required"), bool):
        issues.append(Issue("error", "%s.required" % where,
                            "required должен быть boolean", "FLOW_DOC_INVALID"))
    if documentation.get("confirmation") not in CONFIRMATIONS:
        issues.append(Issue("error", "%s.confirmation" % where,
                            "confirmation должен быть одним из %s" % list(CONFIRMATIONS),
                            "FLOW_DOC_INVALID"))
    for key in ("question", "on_decline"):
        if key not in documentation:
            issues.append(Issue("error", where, "documentation без поля %s" % key,
                                "FLOW_DOC_INVALID"))
    question = documentation.get("question")
    if question is not None:
        # FLOW-DOC question is translated to generic choice below; validate its
        # declared keys without treating it as user-authored prompt text.
        if not isinstance(question, dict):
            issues.append(Issue("error", "%s.question" % where,
                                "question должен быть объектом", "FLOW_DOC_INVALID"))
        else:
            for key in ("id", "text", "choices", "default"):
                if key not in question:
                    issues.append(Issue("error", "%s.question" % where,
                                        "question без поля %s" % key,
                                        "FLOW_DOC_INVALID"))
            if isinstance(question.get("choices"), list):
                seen = set()
                for choice in question.get("choices"):
                    cid = choice.get("id") if isinstance(choice, dict) else choice
                    if not isinstance(cid, str) or not cid.strip() or cid in seen:
                        issues.append(Issue("error", "%s.question.choices" % where,
                                            "choices должны иметь уникальные непустые id",
                                            "FLOW_DOC_INVALID"))
                    seen.add(cid)
                if question.get("selection", "single") != "text" \
                        and question.get("default") not in seen:
                    issues.append(Issue("error", "%s.question.default" % where,
                                        "default не входит в choices", "FLOW_DOC_INVALID"))
            elif question.get("choices") is not None:
                issues.append(Issue("error", "%s.question.choices" % where,
                                    "choices должен быть массивом", "FLOW_DOC_INVALID"))
    for key, values in (("automation", ("ask", "always", "manual", "disabled")),
                        ("cadence", ("slice", "aggregate", "both", "explicit")),
                        ("update_after", ("implementation", "slice_tests", "all_tests",
                                           "explicit_command")),
                        ("verify", ("on_update", "after_final_tests", "on_close")),
                        ("enforcement", ("advisory", "required", "critical"))):
        if documentation.get(key) is not None and documentation[key] not in values:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "значение «%s» не из %s" % (documentation[key], list(values)),
                                "FLOW_DOC_INVALID"))
    if documentation.get("retain_impact_record") is not None \
            and not isinstance(documentation["retain_impact_record"], bool):
        issues.append(Issue("error", "%s.retain_impact_record" % where,
                            "retain_impact_record должен быть boolean", "FLOW_DOC_INVALID"))
    for key in ("on_decline", "on_disabled"):
        if key in documentation:
            raw = documentation.get(key)
            values = raw if isinstance(raw, list) else str(raw).split("|")
            if not values or any(item not in CONTROL_ROUTES for item in values):
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "route должен быть из %s" % list(CONTROL_ROUTES),
                                    "FLOW_DOC_INVALID"))
    return issues


def _choice_fragment(question, flow_id, step_id, revision=1, policy_scope="step"):
    choices = question.get("choices") or []
    options = []
    for item in choices:
        if isinstance(item, dict):
            option = dict(item)
            option.setdefault("id", option.get("value"))
            option.setdefault("label", option.get("id"))
            option.setdefault("description", option.get("label"))
        else:
            option = {"id": str(item), "label": str(item),
                      "description": str(item)}
        options.append(option)
    return make_choice_request(
        request_id="choice:%s:%s:%s:%s" % (flow_id, step_id, revision,
                                            question.get("id")),
        decision_id=question.get("id"), question=question.get("text"),
        selection=question.get("selection", "single"), options=options,
        default=question.get("default"),
        allow_custom_response=bool(question.get("allow_custom_response", False)),
        policy_scope=policy_scope, flow_id=flow_id, flow_revision=revision,
        step_id=step_id, source="flow.json", metadata={"declared_question": True})


def control_request(flow, step, revision=1, policy_scope="step"):
    """Return a canonical choice request for an explicitly controlled step."""
    control = getattr(step, "step_control", None)
    if not control:
        return None
    issues = validate_step_control(control,
                                   "flows/%s/%s.step_control" % (flow.id, step.id))
    if any(item.is_error for item in issues):
        first = issues[0]
        raise SkillError(first.code, first.message, first.where)
    return _choice_fragment(control["question"], flow.id, step.id, revision,
                            policy_scope=policy_scope)


def doc_request(flow, step, revision=1):
    extension = getattr(step, "documentation", None)
    if not extension:
        return None
    issues = validate_doc_extension(extension,
                                    "flows/%s/%s.documentation" % (flow.id, step.id))
    if any(item.is_error for item in issues):
        first = issues[0]
        raise SkillError(first.code, first.message, first.where)
    question = extension.get("question")
    return _choice_fragment(question, flow.id, step.id, revision,
                            policy_scope="flow_run") if question else None


def _route_value(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def route_for_decision(control, decision, disabled=False):
    """Resolve an explicit response through declarative route policy."""
    value = decision.get("value") or _route_value(decision.get("values"))
    if disabled:
        outcome = control.get("on_disabled")
    else:
        outcome = control.get("on_decline")
    routes = outcome if isinstance(outcome, list) else [outcome]
    expanded = []
    for item in routes:
        expanded.extend(item.split("|") if isinstance(item, str) else [item])
    routes = [item for item in expanded if item]
    # Common values are conventional only as a selector; actual target route
    # still comes from flow.json.  A run/skip/cancel answer is mapped to the
    # declared route, never invented by the model.
    if value in ("run_now", "enable", "yes", "true", True, "document_now"):
        return {"action": "run", "route": None, "reason": "declared affirmative choice"}
    if value in ("skip_once", "disable", "manual", "no", "false", False) \
            and "skip_with_reason" in routes:
        return {"action": "skip", "route": None, "reason": "explicit user choice"}
    if value == "switch_to_manual" and "manual_only" in routes:
        return {"action": "manual", "route": None, "reason": "explicit manual-only choice"}
    if "route" not in routes and value not in ("cancel", "skip_once", "disable",
                                                "manual", "switch_to_manual", "no", "false", False):
        return {"action": "run", "route": None, "reason": "declared affirmative choice"}
    selected = next((item for item in routes if item), None)
    if selected == "route":
        return {"action": "route", "route": control.get("route"),
                "reason": "declared route outcome"}
    if selected == "skip_with_reason":
        return {"action": "skip", "route": None, "reason": "explicit user choice"}
    if selected == "manual_only":
        return {"action": "manual", "route": None, "reason": "manual-only policy"}
    if selected == "cancel" or value in ("cancel", "no", "false", False):
        return {"action": "block", "route": None, "reason": "explicit decline"}
    return {"action": "block", "route": None, "reason": "no declared skip route"}


class DecisionStore:
    """Append-only, scope-aware decisions.  It never rewrites workspace policy."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.path = os.path.join(self.root, ".todone", "flow-decisions.json")

    def read(self):
        if not os.path.isfile(self.path):
            return {"schema": "FLOW-DECISIONS-1", "decisions": []}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SkillError("JSON_MALFORMED", "решения flow не читаются: %s" % exc,
                             self.path)
        if not isinstance(data, dict) or data.get("schema") != "FLOW-DECISIONS-1":
            raise SkillError("FLOW_DECISION_INVALID", "реестр решений имеет неверную schema",
                             self.path)
        return data

    def append(self, decision):
        data = self.read()
        # Idempotency is by immutable decision_id + scope + request.
        for old in data.get("decisions", []):
            if old.get("decision_id") == decision.get("decision_id"):
                if (old.get("choice") == decision.get("choice")
                        and old.get("outcome") == decision.get("outcome")):
                    return old
                raise SkillError("FLOW_DECISION_DUPLICATE",
                                 "decision_id уже сохранён с другим содержимым",
                                 self.path)
        data.setdefault("decisions", []).append(copy.deepcopy(decision))
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        return decision

    def find(self, request_id, scope=None, run_id=None, step_id=None):
        result = []
        for item in self.read().get("decisions", []):
            if item.get("request_id") != request_id:
                continue
            if scope is not None and item.get("scope") != scope:
                continue
            if run_id is not None and item.get("run_id") != run_id:
                continue
            if step_id is not None and item.get("step_id") != step_id:
                continue
            result.append(item)
        return result[-1] if result else None


def persist_control_decision(store, request, response, outcome, run_id,
                             flow_id, step_id, revision=1, reason=None):
    actor = response.get("actor") or response.get("source")
    decision_id = "decision:%s:%s:%s:%s" % (request["request_id"], run_id,
                                             response.get("value") or
                                             response.get("values") or
                                             response.get("text"), actor)
    payload = {
        "schema": "FLOW-DECISION-1", "decision_id": decision_id,
        "request_id": request["request_id"], "flow_id": flow_id,
        "step_id": step_id, "run_id": run_id, "revision": revision,
        "scope": request.get("policy_scope"), "question_id": request["decision_id"],
        "choice": response, "outcome": outcome, "actor": actor,
        "reason": reason or response.get("reason"), "at": now_stamp(),
        "policy_fingerprint": response.get("metadata", {}).get("policy_fingerprint"),
    }
    return store.append(payload)
