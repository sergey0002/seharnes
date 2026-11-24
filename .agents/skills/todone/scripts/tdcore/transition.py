"""Immutable FLOW-TRANSITION-1 orchestration primitives."""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone

from .errors import Issue, SkillError

TRANSITION_SCHEMA = "FLOW-TRANSITION-1"
TRANSITION_STATUSES = ("requested", "approved", "applied", "blocked", "rejected")
REQUESTED_BY = ("user", "agent", "policy")
TRANSITION_KEYS = ("schema", "transition_id", "from_flow", "from_run", "from_step",
                   "transition", "target_flow", "target_step", "choice_ref",
                   "carry_refs", "requested_by", "status", "scope", "release_context",
                   "policy", "created_at", "approved_at", "applied_at", "new_run",
                   "new_record", "reason", "validation", "parent_transition")


def now_stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error(where, message, code="FLOW_TRANSITION_INVALID"):
    return Issue("error", where, message, code)


def validate_transition(payload, where="transition"):
    issues = []
    if not isinstance(payload, dict):
        return [_error(where, "transition должен быть объектом")]
    for key in payload:
        if key not in TRANSITION_KEYS:
            issues.append(_error("%s.%s" % (where, key),
                                 "ключ не из FLOW-TRANSITION-1", "KEY_UNKNOWN"))
    for key in ("schema", "from_flow", "from_run", "from_step", "transition",
                "target_flow", "target_step", "carry_refs", "requested_by", "status"):
        if key not in payload:
            issues.append(_error(where, "нет обязательного поля «%s»" % key))
    if payload.get("schema") != TRANSITION_SCHEMA:
        issues.append(_error(where, "schema должен быть %s" % TRANSITION_SCHEMA))
    if payload.get("transition") != "switch_flow":
        issues.append(_error("%s.transition" % where,
                             "transition должен быть switch_flow"))
    for key in ("from_flow", "from_run", "from_step", "target_flow", "target_step"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            issues.append(_error("%s.%s" % (where, key),
                                 "поле должно быть непустой строкой"))
    if payload.get("requested_by") not in REQUESTED_BY:
        issues.append(_error("%s.requested_by" % where,
                             "requested_by должен быть одним из %s" % list(REQUESTED_BY)))
    if payload.get("status") not in TRANSITION_STATUSES:
        issues.append(_error("%s.status" % where,
                             "status должен быть одним из %s" % list(TRANSITION_STATUSES)))
    if not isinstance(payload.get("carry_refs"), list):
        issues.append(_error("%s.carry_refs" % where, "carry_refs должен быть массивом"))
    else:
        if len(payload["carry_refs"]) > 32:
            issues.append(_error("%s.carry_refs" % where, "carry_refs превышает bounded limit"))
        for pos, ref in enumerate(payload["carry_refs"]):
            if not isinstance(ref, (str, dict)):
                issues.append(_error("%s.carry_refs[%d]" % (where, pos),
                                     "carry ref должен быть string или object"))
            if isinstance(ref, str) and len(ref) > 512:
                issues.append(_error("%s.carry_refs[%d]" % (where, pos),
                                     "carry ref слишком длинный"))
    for key in ("scope", "release_context", "policy", "validation"):
        if payload.get(key) is not None and not isinstance(payload.get(key), dict):
            issues.append(_error("%s.%s" % (where, key), "%s должен быть объектом" % key))
    if payload.get("choice_ref") is not None and (
            not isinstance(payload.get("choice_ref"), str)
            or not payload["choice_ref"].strip()
            or len(payload["choice_ref"]) > 512):
        issues.append(_error("%s.choice_ref" % where,
                             "choice_ref должен быть bounded string"))
    for pos, ref in enumerate(payload.get("carry_refs") or []):
        if isinstance(ref, dict):
            allowed_ref_keys = {"kind", "path", "ref", "id", "note"}
            if any(key not in allowed_ref_keys for key in ref):
                issues.append(_error("%s.carry_refs[%d]" % (where, pos),
                                     "carry object содержит лишний key"))
            if not any(ref.get(key) for key in ("path", "ref", "id")):
                issues.append(_error("%s.carry_refs[%d]" % (where, pos),
                                     "carry object не содержит bounded ref"))
            if len(json.dumps(ref, ensure_ascii=False)) > 1024:
                issues.append(_error("%s.carry_refs[%d]" % (where, pos),
                                     "carry object слишком большой"))
    return issues


def make_transition(from_flow, from_run, from_step, target_flow, target_step,
                    choice_ref=None, carry_refs=None, requested_by="user",
                    status="requested", scope=None, release_context=None,
                    policy=None, reason=None, parent_transition=None):
    body = {
        "schema": TRANSITION_SCHEMA, "from_flow": from_flow, "from_run": from_run,
        "from_step": from_step, "transition": "switch_flow", "target_flow": target_flow,
        "target_step": target_step, "choice_ref": choice_ref,
        "carry_refs": list(carry_refs or []), "requested_by": requested_by,
        "status": status, "scope": scope, "release_context": release_context,
        "policy": policy, "created_at": now_stamp(), "approved_at": None,
        "applied_at": None, "new_run": None, "new_record": None,
        "reason": reason, "validation": {}, "parent_transition": parent_transition,
    }
    raw = json.dumps({key: body.get(key) for key in (
        "from_flow", "from_run", "from_step", "target_flow", "target_step",
        "choice_ref", "carry_refs", "scope")}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"))
    body["transition_id"] = "transition:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    issues = validate_transition(body)
    if any(item.is_error for item in issues):
        first = issues[0]
        raise SkillError(first.code, first.message, first.where)
    return body


class TransitionStore:
    """Append-only transition ledger; old runs are never rewritten here."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.path = os.path.join(self.root, ".todone", "flow-transitions.json")

    def read(self):
        if not os.path.isfile(self.path):
            return {"schema": "FLOW-TRANSITIONS-1", "transitions": []}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SkillError("JSON_MALFORMED", "реестр переходов не читается: %s" % exc,
                             self.path)
        if not isinstance(data, dict) or data.get("schema") != "FLOW-TRANSITIONS-1":
            raise SkillError("FLOW_TRANSITION_INVALID", "реестр переходов имеет неверную schema",
                             self.path)
        return data

    def get(self, transition_id):
        for item in self.read().get("transitions", []):
            if item.get("transition_id") == transition_id:
                return item
        return None

    def find_duplicate(self, payload):
        for old in self.read().get("transitions", []):
            if all(old.get(key) == payload.get(key) for key in (
                    "from_flow", "from_run", "from_step", "target_flow",
                    "target_step", "choice_ref")):
                return old
        return None

    def append(self, payload):
        issues = validate_transition(payload)
        if any(item.is_error for item in issues):
            first = issues[0]
            raise SkillError(first.code, first.message, first.where)
        old = self.get(payload.get("transition_id"))
        if old is not None:
            if old == payload:
                return old
            raise SkillError("FLOW_TRANSITION_DUPLICATE",
                             "transition_id уже существует с другим содержимым", self.path)
        duplicate = None if payload.get("parent_transition") else self.find_duplicate(payload)
        if duplicate is not None:
            raise SkillError("FLOW_TRANSITION_DUPLICATE",
                             "эквивалентный переход уже зарегистрирован: %s"
                             % duplicate.get("transition_id"), self.path,
                             command="ttask flow transition state %s"
                                     % duplicate.get("transition_id"))
        data = self.read()
        data["transitions"].append(copy.deepcopy(payload))
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        return payload

    def update_once(self, transition_id, **fields):
        """Only append a replacement event; the original transition remains immutable."""
        old = self.get(transition_id)
        if old is None:
            raise SkillError("FLOW_TRANSITION_UNKNOWN", "переход не найден", transition_id)
        replacement = copy.deepcopy(old)
        replacement.update(fields)
        replacement["parent_transition"] = old.get("transition_id")
        # A transition ledger can contain a successor event, but callers must
        # use the successor id and cannot mutate the old row in place.
        replacement["transition_id"] = "%s:%s" % (
            old.get("transition_id"), fields.get("status", "event"))
        return self.append(replacement)
