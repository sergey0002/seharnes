"""Freshness input projections: report and QA semantic hashes (J12).

jsondoc-input-v1: knowledge fields minus revision/metadata.updated_at/history/
checks/git_state/output-only artifacts and output-reachable refs.
jsondoc-qa-input-v1: requirements, accepted decisions, applicable invariants,
confirmed relation scopes, test spec hashes, stage identity/diff manifest.
Recording a result must not invalidate itself (plan 18.3, IT10/IT13).
"""

import hashlib
import json

REPORT_EXCLUDED_TOP = {"revision", "history", "checks", "git_state",
                       "jira_report"}
OUTPUT_ONLY_ROLES = {"test_run", "change_report", "jira_report", "audit"}
PROJECTION_VERSIONS = {
    "jsondoc-input-v1": "report",
    "jsondoc-qa-input-v1": "qa",
}


class FreshnessError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def _reachable_source_ids(doc):
    """source_ids reachable from kept knowledge (excluding output-only)."""
    kept = []

    def keep(item):
        kept.append(item)

    for tag in doc.get("tags", []):
        keep(tag)
    for section in doc.get("sections", []):
        keep(section)
    for item in (doc.get("findings", []) + doc.get("decisions", []) +
                 doc.get("requirements", []) + doc.get("progress", []) +
                 doc.get("notes", []) + doc.get("relations", []) +
                 doc.get("files", [])):
        keep(item)
    ids = set()
    for item in kept:
        ids.update(item.get("source_ids", []))
    return ids


def report_projection(doc):
    """Copy of doc minus output state and output-reachable refs (18.3)."""
    out = {}
    for key, value in doc.items():
        if key in REPORT_EXCLUDED_TOP:
            continue
        out[key] = json.loads(json.dumps(value, ensure_ascii=False))
    metadata = dict(out.get("metadata", {}))
    metadata.pop("updated_at", None)
    out["metadata"] = metadata
    kept_sources = _reachable_source_ids(out)
    out["sources"] = [s for s in doc.get("sources", [])
                      if s.get("id") in kept_sources]
    # stages: drop test output refs but keep plan/diff/identity
    stages = []
    for stage in out.get("stages", []):
        trimmed = dict(stage)
        trimmed["test_run_ids"] = []
        trimmed["test_artifact_ids"] = [
            aid for aid in stage.get("test_artifact_ids", []) if aid]
        stages.append(trimmed)
    out["stages"] = stages
    # artifacts: exclude output-only roles
    out["artifacts"] = [a for a in out.get("artifacts", [])
                        if a.get("role") not in OUTPUT_ONLY_ROLES]
    return out


def qa_projection(doc):
    """Semantic QA inputs: requirements + accepted decisions + invariants +
    confirmed relations + test spec hashes + stage identity."""
    return {
        "requirements": [r for r in doc.get("requirements", [])],
        "decisions": [d for d in doc.get("decisions", [])
                      if d.get("status") in ("accepted", "implemented")],
        "invariants": [f for f in doc.get("findings", [])
                       if f.get("kind") == "invariant"],
        "relations": [r for r in doc.get("relations", [])
                      if r.get("status") == "confirmed"],
        "test_specs": [a for a in doc.get("artifacts", [])
                       if a.get("role") in ("test_spec", "test_matrix")],
        "stages_identity": [{"id": s.get("id"), "status": s.get("status"),
                             "diff_manifest_id": s.get("diff_manifest_id")}
                            for s in doc.get("stages", [])],
        "summary": doc.get("summary"),
    }


def projection_for(name):
    kind = PROJECTION_VERSIONS.get(name)
    if kind is None:
        raise FreshnessError("unknown_projection", name)
    return report_projection if kind == "report" else qa_projection


def semantic_hash(doc, projection_name):
    projection = projection_for(projection_name)(doc)
    payload = json.dumps(projection, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def descriptor(doc, projection_name):
    return {
        "projection_version": projection_name,
        "semantic_sha256": semantic_hash(doc, projection_name),
        "document_id": doc.get("id"),
    }
