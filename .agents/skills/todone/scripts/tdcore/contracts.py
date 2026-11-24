"""One dispatch point for the versioned runtime/documentation envelopes.

The JSON files under ``schemas/`` are the wire contracts.  This module keeps
CLI and runtime fixture validation on the same semantic dispatch path instead
of making every caller import a private validator directly.  It deliberately
uses the dependency-free validators owned by each domain; external JSON Schema
validators may still be used as an additional conformance check.
"""

import json

from .errors import Issue, SkillError
from .choice import (CHOICE_SCHEMA, RECOMMENDATION_SCHEMA, RESPONSE_SCHEMA,
                     RECOMMENDATION_KEYS, RESPONSE_KEYS,
                     validate_choice_definition)
from .flow_control import validate_doc_extension, validate_step_control
from .transition import validate_transition
from .aggregate import (AGGREGATE_SCHEMA, validate_aggregate_manifest)
from .importer import (JIRA_MIRROR_SCHEMA, validate_jira_projection)
from .intake import (INTAKE_SCHEMA, AUDIT_SCHEMA, validate_intake_draft, validate_audit)
from .documentation import (WORKSPACE_SCHEMA, DOC_SCHEMA, MACHINE_SCHEMA,
                            DOC_PATH_SCHEMA, CLAIM_SCHEMA, CAPTURE_SCHEMA, PACKET_SCHEMA,
                            POLICY_SCHEMA, validate_doc_path, validate_policy, validate_module,
                            validate_machine, validate_claims, validate_capture,
                            validate_packet, validate_query_request,
                            validate_writer_result)
from .autodoc import (AUTODOC_AUDIT_SCHEMA, AUTODOC_BUNDLE_SCHEMA,
                      AUTODOC_DIAGRAM_SCHEMA, AUTODOC_ENTITY_SCHEMA,
                      AUTODOC_HTML_SCHEMA, AUTODOC_MARKDOWN_SCHEMA,
                      AUTODOC_PACKET_SCHEMA, AUTODOC_PREZA_SCHEMA, PREZA_PARITY_SCHEMA,
                      AUTODOC_RECONSTRUCTION_SCHEMA, AUTODOC_RELATION_SCHEMA,
                      AUTODOC_SOURCE_SCHEMA, validate_autodoc_contract)

QUERY_RESPONSE_SCHEMA = "DOC-QUERY-RESPONSE-1"

CONTRACT_IDS = (
    AGGREGATE_SCHEMA, JIRA_MIRROR_SCHEMA, INTAKE_SCHEMA, AUDIT_SCHEMA, WORKSPACE_SCHEMA, POLICY_SCHEMA, DOC_SCHEMA, MACHINE_SCHEMA,
    CLAIM_SCHEMA, DOC_PATH_SCHEMA, CAPTURE_SCHEMA, PACKET_SCHEMA, QUERY_RESPONSE_SCHEMA, "DOC-QUERY-1",
    "DOC-WRITER-1", "FLOW-DOC-1", "FLOW-STEP-CONTROL-1", CHOICE_SCHEMA,
    RESPONSE_SCHEMA, RECOMMENDATION_SCHEMA, "FLOW-TRANSITION-1",
    AUTODOC_BUNDLE_SCHEMA, AUTODOC_ENTITY_SCHEMA, AUTODOC_RELATION_SCHEMA,
    AUTODOC_SOURCE_SCHEMA, AUTODOC_DIAGRAM_SCHEMA, AUTODOC_AUDIT_SCHEMA,
    AUTODOC_HTML_SCHEMA, AUTODOC_RECONSTRUCTION_SCHEMA, AUTODOC_PACKET_SCHEMA,
    AUTODOC_MARKDOWN_SCHEMA, AUTODOC_PREZA_SCHEMA, PREZA_PARITY_SCHEMA,
)


def _issue(code, where, message):
    return Issue("error", where, message, code)


def _unknown(payload, allowed, where, code="CONTRACT_INVALID"):
    return [_issue(code, "%s.%s" % (where, key),
                   "ключ «%s» не объявлен контрактом" % key)
            for key in payload if key not in allowed]


def _simple_envelope(payload, schema_id, required, allowed, where):
    issues = []
    if payload.get("schema") != schema_id:
        issues.append(_issue("CONTRACT_INVALID", where,
                             "schema должен быть %s" % schema_id))
    issues.extend(_unknown(payload, allowed, where))
    for key in required:
        if key not in payload:
            issues.append(_issue("CONTRACT_INVALID", where,
                                 "нет обязательного поля «%s»" % key))
    return issues


def _validate_workspace(payload, where):
    allowed = {"$schema", "schema", "workspace_id", "product_id", "root",
               "docs_path", "task_registry", "default_release",
               "release_registry", "catalog_path", "contract_versions", "policy"}
    issues = _simple_envelope(payload, WORKSPACE_SCHEMA,
                              ("schema", "workspace_id", "product_id",
                               "docs_path", "policy"), allowed, where)
    for key in ("workspace_id", "product_id", "docs_path"):
        if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
            issues.append(_issue("DOC_MANIFEST_INVALID", "%s.%s" % (where, key),
                                 "значение должно быть непустой строкой"))
    if "policy" in payload:
        issues.extend(validate_policy(payload["policy"], "%s.policy" % where))
    return issues


def _validate_query_response(payload, where):
    required = ("schema", "mode", "query_fingerprint", "scope", "summaries",
                "modules", "machine", "claims", "refs", "unknowns",
                "conflicts", "stale", "limits", "truncation")
    allowed = set(required)
    return _simple_envelope(payload, QUERY_RESPONSE_SCHEMA, required, allowed, where)


def _validate_response(payload, where):
    issues = _simple_envelope(payload, RESPONSE_SCHEMA,
                              ("schema", "request_id", "decision_id", "selection",
                               "source"), set(RESPONSE_KEYS), where)
    if payload.get("source") == "agent":
        issues.append(_issue("FLOW_CHOICE_USER_REQUIRED", where,
                             "recommendation агента не является выбором пользователя"))
    return issues


def _validate_recommendation(payload, where):
    issues = _simple_envelope(payload, RECOMMENDATION_SCHEMA,
                              ("schema", "request_id", "decision_id", "selection",
                               "rationale", "evidence_refs", "actor"),
                              set(RECOMMENDATION_KEYS), where)
    if "evidence_refs" in payload and not isinstance(payload["evidence_refs"], list):
        issues.append(_issue("FLOW_CHOICE_INVALID", "%s.evidence_refs" % where,
                             "evidence_refs должен быть массивом"))
    return issues


_VALIDATORS = {
    AGGREGATE_SCHEMA: lambda payload, where: validate_aggregate_manifest(payload, where),
    JIRA_MIRROR_SCHEMA: lambda payload, where: validate_jira_projection(payload, where),
    INTAKE_SCHEMA: lambda payload, where: validate_intake_draft(payload, where),
    AUDIT_SCHEMA: lambda payload, where: validate_audit(payload, where),
    WORKSPACE_SCHEMA: _validate_workspace,
    POLICY_SCHEMA: lambda payload, where: validate_policy(payload, where),
    DOC_SCHEMA: lambda payload, where: validate_module(payload, where),
    MACHINE_SCHEMA: lambda payload, where: validate_machine(payload, where),
    CLAIM_SCHEMA: lambda payload, where: validate_claims(payload, where),
    DOC_PATH_SCHEMA: lambda payload, where: validate_doc_path(payload, where),
    CAPTURE_SCHEMA: lambda payload, where: validate_capture(payload, where),
    PACKET_SCHEMA: lambda payload, where: validate_packet(payload, where),
    "DOC-QUERY-1": lambda payload, where: validate_query_request(payload, where),
    QUERY_RESPONSE_SCHEMA: _validate_query_response,
    "DOC-WRITER-1": lambda payload, where: validate_writer_result(payload, where),
    "FLOW-DOC-1": lambda payload, where: validate_doc_extension(payload, where),
    "FLOW-STEP-CONTROL-1": lambda payload, where: validate_step_control(payload, where),
    CHOICE_SCHEMA: lambda payload, where: validate_choice_definition(payload, where),
    RESPONSE_SCHEMA: _validate_response,
    RECOMMENDATION_SCHEMA: _validate_recommendation,
    "FLOW-TRANSITION-1": lambda payload, where: validate_transition(payload, where),
    AUTODOC_BUNDLE_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_ENTITY_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_RELATION_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_SOURCE_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_DIAGRAM_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_AUDIT_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_HTML_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_RECONSTRUCTION_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_PACKET_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_MARKDOWN_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    AUTODOC_PREZA_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
    PREZA_PARITY_SCHEMA: lambda payload, where: validate_autodoc_contract(payload, where),
}


def contract_id(payload):
    """Return the version id from a canonical envelope or ``None``."""
    if not isinstance(payload, dict):
        return None
    # DOC-POLICY-1 historically uses ``policy`` as its envelope discriminator.
    return payload.get("schema") or payload.get("policy")


def validate_contract(payload, where="contract"):
    """Validate one payload through the shared schema/semantic dispatcher."""
    if not isinstance(payload, dict):
        return [_issue("CONTRACT_INVALID", where,
                       "contract payload должен быть объектом")]
    identifier = contract_id(payload)
    validator = _VALIDATORS.get(identifier)
    if validator is None:
        return [_issue("CONTRACT_UNKNOWN", where,
                       "контракт «%s» не зарегистрирован; ожидается один из %s"
                       % (identifier, ", ".join(CONTRACT_IDS)))]
    return list(validator(payload, where) or [])


def validate_contract_file(path):
    """Read and validate a JSON fixture, raising only for unreadable JSON."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise SkillError("JSON_MALFORMED", "contract JSON не читается: %s" % exc, path)
    return payload, validate_contract(payload, path)
