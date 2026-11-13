"""Strict contract loading and validation (J01).

Implements exactly the JSON Schema keywords used by bundled schemas
(section 19.7): $ref, type (incl. nullable lists), enum, const, properties,
required, additionalProperties:false, items, minItems, uniqueItems,
minLength, pattern, minimum, maximum, oneOf. Any other keyword in a schema
raises at load time (no silent ignoring). Semantic checks: UTC dates,
sha256 format beyond pattern, cross-collection references, kind coupling,
stage graph acyclicity, actor enums shared by update/history.
"""

import copy
import json
import re
from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"

SUPPORTED_KEYWORDS = {
    "$ref", "type", "enum", "const", "properties", "required",
    "additionalProperties", "items", "minItems", "uniqueItems",
    "minLength", "pattern", "minimum", "maximum", "oneOf",
    "title", "$schema", "$defs", "description",
}

TYPES = {"object": dict, "array": list, "string": str, "integer": int,
         "boolean": bool, "null": type(None)}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class ContractError(ValueError):
    def __init__(self, code, at="$", message=None):
        super().__init__(f"{code} at {at}" + (f": {message}" if message else ""))
        self.code = code
        self.at = at


def _reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ContractError("duplicate_key", "$." + key)
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ContractError("nonfinite_number")


def load_json_strict(text):
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys,
                          parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid_json", "$", str(exc)) from None


def load_schema(name):
    path = SCHEMAS_DIR / f"{name}.schema.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError("schema_unavailable", "$", name) from None
    schema = load_json_strict(raw)
    _check_keywords(schema, "$")
    return schema


_STRUCTURAL_KEYS = {
    "$schema", "title", "description", "$defs", "type", "enum", "const",
    "properties", "required", "additionalProperties", "items", "minItems",
    "uniqueItems", "minLength", "pattern", "minimum", "maximum", "oneOf",
    "$ref",
}
_CHILD_KEYS = ("properties", "$defs")


def _check_keywords(node, at):
    """Walk schema positions only; document field names are not keywords."""
    if not isinstance(node, dict):
        return
    unknown = set(node) - _STRUCTURAL_KEYS
    if unknown:
        raise ContractError("unsupported_keyword", at, sorted(unknown)[0])
    for key in _CHILD_KEYS:
        for name, child in node.get(key, {}).items():
            _check_keywords(child, f"{at}.{key}.{name}")
    if "items" in node:
        _check_keywords(node["items"], f"{at}.items")
    for index, variant in enumerate(node.get("oneOf", [])):
        _check_keywords(variant, f"{at}.oneOf[{index}]")


def _resolve_ref(rule, schema):
    if "$ref" in rule:
        ref = rule["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ContractError("unsupported_ref", "$", ref)
        target = schema["$defs"][ref.rsplit("/", 1)[1]]
        merged = dict(target)
        for key, value in rule.items():
            if key != "$ref":
                merged[key] = value
        return merged
    return rule


def _matches_type(value, rule):
    declared = rule["type"]
    if isinstance(declared, list):
        if isinstance(value, bool) and "boolean" not in declared:
            # bool must never pass integer/other types implicitly
            return "boolean" in declared
        return any(_matches_type(value, {"type": single}) for single in declared)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "null":
        return value is None
    return isinstance(value, TYPES[declared]) and not (
        declared != "boolean" and isinstance(value, bool))


def _validate(value, rule, schema, at, errors):
    rule = _resolve_ref(rule, schema)
    if "const" in rule and value != rule["const"]:
        errors.append({"code": "const_mismatch", "at": at})
        return
    if "enum" in rule and value not in rule["enum"]:
        errors.append({"code": "enum_violation", "at": at})
        return
    if "type" in rule and not _matches_type(value, rule):
        errors.append({"code": "type_mismatch", "at": at,
                       "expected": rule["type"]})
        return
    if "oneOf" in rule:
        matched = 0
        for variant in rule["oneOf"]:
            probe = []
            _validate(value, variant, schema, at, probe)
            if not probe:
                matched += 1
        if matched != 1:
            errors.append({"code": "oneof_violation", "at": at,
                           "matched": matched})
        return
    if isinstance(value, dict):
        props = rule.get("properties", {})
        if rule.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            if unknown:
                errors.append({"code": "unknown_fields", "at": at,
                               "fields": sorted(unknown)})
                return
        for key in rule.get("required", []):
            if key not in value:
                errors.append({"code": "missing_field", "at": f"{at}.{key}"})
        for key, sub in props.items():
            if key in value:
                _validate(value[key], sub, schema, f"{at}.{key}", errors)
    elif isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append({"code": "min_items", "at": at})
        if rule.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True, ensure_ascii=False) for v in value]
            if len(set(seen)) != len(seen):
                errors.append({"code": "duplicates", "at": at})
        if "items" in rule:
            for index, item in enumerate(value):
                _validate(item, rule["items"], schema, f"{at}[{index}]", errors)
    elif isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            errors.append({"code": "min_length", "at": at})
        if "pattern" in rule and not re.search(rule["pattern"], value):
            errors.append({"code": "pattern_mismatch", "at": at})
    elif isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            errors.append({"code": "minimum", "at": at})
        if "maximum" in rule and value > rule["maximum"]:
            errors.append({"code": "maximum", "at": at})


def validate_schema(data, schema):
    errors = []
    _validate(data, schema, schema, "$", errors)
    return errors


# ---------------------------------------------------------------- semantic

def _ids(items):
    return [item.get("id") for item in items if isinstance(item, dict)]


def semantic_errors(doc):
    errors = []
    kind = doc.get("kind")
    meta = doc.get("metadata", {})

    if kind == "task":
        if not re.fullmatch(r"[0-9]+", str(meta.get("task_id") or "")):
            errors.append({"code": "task_id_required", "at": "$.metadata.task_id"})
        if doc.get("id") != f"task:{meta.get('task_id')}":
            errors.append({"code": "id_kind_mismatch", "at": "$.id"})
    if kind == "architecture" and meta.get("task_id") is not None:
        errors.append({"code": "arch_has_task_id", "at": "$.metadata.task_id"})

    # cross-collection references
    known = {
        "sources": set(_ids(doc.get("sources", []))),
        "files": set(_ids(doc.get("files", []))),
        "artifacts": set(_ids(doc.get("artifacts", []))),
        "sections": set(_ids(doc.get("sections", []))),
    }
    checks = [
        ("tags", "source_ids", "sources"),
        ("sections", "source_ids", "sources"),
        ("files", "source_ids", "sources"),
        ("findings", "source_ids", "sources"),
        ("findings", "file_ids", "files"),
        ("decisions", "source_ids", "sources"),
        ("requirements", "source_ids", "sources"),
        ("progress", "source_ids", "sources"),
        ("notes", "source_ids", "sources"),
        ("relations", "source_ids", "sources"),
        ("artifacts", "source_ids", "sources"),
        ("checks", "source_ids", "sources"),
        ("git_events", "source_ids", "sources"),
        ("sources_none", None, None),
    ]
    for collection, field, target in checks[:-1]:
        for index, item in enumerate(doc.get(collection, [])):
            for ref in item.get(field, []):
                if ref not in known[target]:
                    errors.append({"code": "unknown_reference",
                                   "at": f"$.{collection}[{index}].{field}",
                                   "ref": ref})
    for index, item in enumerate(doc.get("findings", [])):
        if item.get("section_id") and item["section_id"] not in known["sections"]:
            errors.append({"code": "unknown_reference",
                           "at": f"$.findings[{index}].section_id"})
    for index, item in enumerate(doc.get("decisions", [])):
        if item.get("section_id") and item["section_id"] not in known["sections"]:
            errors.append({"code": "unknown_reference",
                           "at": f"$.decisions[{index}].section_id"})
    for index, item in enumerate(doc.get("checks", [])):
        if item.get("artifact_id") not in known["artifacts"]:
            errors.append({"code": "unknown_reference",
                           "at": f"$.checks[{index}].artifact_id"})

    # duplicate ids per collection
    for collection in ("sources", "sections", "files", "findings",
                       "decisions", "requirements", "progress", "stages",
                       "notes", "relations", "artifacts", "checks",
                       "git_events", "history"):
        ids = _ids(doc.get(collection, []))
        if len(ids) != len(set(ids)):
            errors.append({"code": "duplicate_ids", "at": f"$.{collection}"})

    # section_order covers all sections exactly
    order = doc.get("section_order", [])
    section_ids = set(_ids(doc.get("sections", [])))
    if len(order) != len(set(order)) or set(order) != section_ids:
        errors.append({"code": "section_order_mismatch", "at": "$.section_order"})

    # sha256 values beyond pattern already enforced; dates beyond pattern too

    # stages: numbers unique, graph acyclic, supersede targets exist
    stages = doc.get("stages", [])
    numbers = [s.get("number") for s in stages]
    if len(numbers) != len(set(numbers)):
        errors.append({"code": "duplicate_stage_numbers", "at": "$.stages"})
    by_id = {s["id"]: s for s in stages}
    for index, stage in enumerate(stages):
        if stage["id"] != f"stage:{stage['number']}":
            errors.append({"code": "stage_id_number_mismatch",
                           "at": f"$.stages[{index}].id"})
        for dep in stage.get("depends_on", []):
            if dep == stage["id"]:
                errors.append({"code": "stage_self_dependency",
                               "at": f"$.stages[{index}].depends_on"})
            if dep not in by_id:
                errors.append({"code": "unknown_reference",
                               "at": f"$.stages[{index}].depends_on"})
        sup = stage.get("superseded_by")
        if sup is not None and sup not in by_id:
            errors.append({"code": "unknown_supersede",
                           "at": f"$.stages[{index}].superseded_by"})
        plan_art = stage.get("plan_artifact_id")
        if plan_art and plan_art not in known["artifacts"]:
            errors.append({"code": "unknown_reference",
                           "at": f"$.stages[{index}].plan_artifact_id"})
        for art in stage.get("diff_artifact_ids", []):
            if art not in known["artifacts"]:
                errors.append({"code": "unknown_reference",
                               "at": f"$.stages[{index}].diff_artifact_ids"})
    # dependency cycles
    colour = {}

    def visit(node):
        if colour.get(node) == 1:
            return True
        if colour.get(node) == 2:
            return False
        colour[node] = 1
        for dep in by_id.get(node, {}).get("depends_on", []):
            if visit(dep):
                return True
        colour[node] = 2
        return False

    for stage in stages:
        if visit(stage["id"]):
            errors.append({"code": "stage_dependency_cycle", "at": "$.stages"})
            break

    return errors


NULLABLE_DEFAULTS = {
    "files": {"role": None, "change": None, "revision": None,
              "ranges": [], "previous_path": None, "source_ids": []},
    "findings": {"symptom": None, "cause": None, "resolution": None,
                 "severity": None, "file_ids": [], "source_ids": [],
                 "superseded_by": None, "section_id": None},
    "decisions": {"alternatives": [], "source_ids": [],
                  "superseded_by": None, "section_id": None},
    "requirements": {"source_ids": [], "stage_ids": [], "scenario_refs": [],
                     "reason": None},
    "sources": {"pointer": None, "sha256": None, "revision": None,
                "observed_at": None, "observation": None},
    "sections": {"parent_id": None, "anchor_aliases": [], "source_ids": []},
    "notes": {"source_ids": [], "section_id": None},
    "progress": {"reason": None, "requirement_ids": [], "source_ids": []},
    "relations": {"source_ids": []},
    "artifacts": {"sha256": None, "revision": None,
                  "projection_path": None},
    "checks": {"revision": None, "source_verdict": None, "source_ids": []},
    "git_events": {"branch": None, "remote": None, "observed_at": None,
                   "source_ids": []},
}

TOP_LEVEL_DEFAULTS = {
    "summary": None, "tags": [], "sections": [], "section_order": [],
    "files": [], "findings": [], "decisions": [], "requirements": [],
    "progress": [], "stages": [], "notes": [], "relations": [],
    "artifacts": [], "checks": [], "git_events": [], "tracker": None,
    "git_state": None, "jira_report": None, "sources": [], "history": [],
    "business_logic": {"facts": [], "unconfirmed": [], "linked_rule_ids": []},
}


def fill_document_defaults(doc):
    """Fill only structural nullable fields. Never invent text or status."""
    if not isinstance(doc, dict):
        return doc
    for key, value in TOP_LEVEL_DEFAULTS.items():
        if key not in doc:
            doc[key] = copy.deepcopy(value)
    metadata = doc.get("metadata")
    if isinstance(metadata, dict):
        for key in ("task_id", "task_type", "doc_type", "branch", "release",
                    "source_status"):
            if key not in metadata:
                metadata[key] = None
        if not metadata.get("status"):
            metadata["status"] = "unknown"
    business_logic = doc.get("business_logic")
    if isinstance(business_logic, dict):
        business_logic.setdefault("facts", [])
        business_logic.setdefault("unconfirmed", [])
        business_logic.setdefault("linked_rule_ids", [])
    for collection, defaults in NULLABLE_DEFAULTS.items():
        items = doc.get(collection)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for key, value in defaults.items():
                if key not in item:
                    item[key] = copy.deepcopy(value)
    return doc


def validate_document(doc):
    schema = load_schema("document")
    errors = validate_schema(doc, schema)
    if not errors:
        errors.extend(semantic_errors(doc))
    return errors


def validate_update(envelope):
    schema = load_schema("update")
    errors = validate_schema(envelope, schema)
    if errors:
        return errors
    create = envelope.get("document") is not None
    ops = envelope.get("operations", [])
    if create and ops:
        errors.append({"code": "create_with_operations", "at": "$.operations"})
    if create and envelope.get("expected_revision") != 0:
        errors.append({"code": "create_requires_revision_zero",
                       "at": "$.expected_revision"})
    if not create and envelope.get("expected_revision") < 1:
        errors.append({"code": "update_requires_positive_revision",
                       "at": "$.expected_revision"})
    set_whitelist = {"summary", "metadata.title", "metadata.task_type",
                     "metadata.source_status", "metadata.status",
                     "metadata.branch", "metadata.release", "section_order",
                     "tracker", "git_state", "jira_report", "business_logic"}
    for index, op in enumerate(ops):
        at = f"$.operations[{index}]"
        if op["op"] == "set":
            if op["collection"] not in set_whitelist:
                errors.append({"code": "set_collection_not_whitelisted",
                               "at": at + ".collection",
                               "collection": op["collection"]})
        elif op["op"] in ("upsert", "supersede"):
            if op["collection"] not in {"tags", "sections", "files", "findings",
                                        "decisions", "requirements", "progress",
                                        "stages", "notes", "relations",
                                        "artifacts", "checks", "git_events",
                                        "sources"}:
                errors.append({"code": "unknown_collection",
                               "at": at + ".collection",
                               "collection": op["collection"]})
    if create:
        errors.extend(validate_document(envelope["document"]))
    return errors


def validate_tags_dictionary(data):
    schema = load_schema("tags")
    errors = validate_schema(data, schema)
    if errors:
        return errors
    ids = [tag["id"] for tag in data["tags"]]
    if len(ids) != len(set(ids)):
        errors.append({"code": "duplicate_tag_ids", "at": "$.tags"})
    by_id = {tag["id"]: tag for tag in data["tags"]}
    alias_map = {}
    for tag in data["tags"]:
        key = (tag["kind"],)
        for alias in tag["aliases"] + [tag["id"]]:
            norm = alias.casefold()
            alias_map.setdefault(key + (norm,), []).append(tag["id"])
        for parent in tag["parents"]:
            parent_tag = by_id.get(parent)
            if parent_tag is None:
                errors.append({"code": "unknown_parent", "at": "$.tags",
                               "parent": parent})
            elif parent_tag["kind"] != tag["kind"]:
                errors.append({"code": "parent_kind_mismatch",
                               "at": "$.tags", "parent": parent})
        replaced = tag.get("replaced_by")
        if tag["status"] == "deprecated" and replaced is None:
            errors.append({"code": "deprecated_without_replacement",
                           "at": "$.tags", "tag": tag["id"]})
        if replaced and replaced not in by_id:
            errors.append({"code": "unknown_replacement", "at": "$.tags",
                           "tag": tag["id"]})
    for key, owners in alias_map.items():
        if len(set(owners)) > 1:
            errors.append({"code": "ambiguous_alias", "at": "$.tags",
                           "alias": key[-1], "owners": sorted(set(owners))})
    # parent/replacement cycles
    def parent_cycle(start):
        seen = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                return True
            seen.add(node)
            stack.extend(by_id.get(node, {}).get("parents", []))
        return False

    def replacement_cycle(start):
        seen = set()
        node = start
        while node is not None:
            if node in seen:
                return True
            seen.add(node)
            node = by_id.get(node, {}).get("replaced_by")
        return False

    for tag in data["tags"]:
        if parent_cycle(tag["id"]):
            errors.append({"code": "parent_cycle", "at": "$.tags",
                           "tag": tag["id"]})
        if replacement_cycle(tag["id"]):
            errors.append({"code": "replacement_cycle", "at": "$.tags",
                           "tag": tag["id"]})
    return errors
