#!/usr/bin/env python3
"""Read-only workflow preflight. Paths are POSIX project-relative, never URLs.

The schema defines structure; preflight checks evidence, freshness and consent.
Input hashes exclude steps and Jira output. This validates declared scope, not
whether the author discovered every relevant file or interpreted evidence well.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


STEPS = ("diff", "documentation", "jira", "html")
SCHEMA = Path(__file__).resolve().parents[1] / "assets/workflow-context.schema.json"


def input_hash(context):
    """Hash declared inputs, independent of object order and output state."""
    inputs = {key: value for key, value in context.items() if key not in ("steps", "jira")}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate(value, rule, schema, location="$", errors=None):
    """Implement only the JSON Schema keywords used in the bundled schema."""
    errors = [] if errors is None else errors
    if "$ref" in rule:
        rule = schema["$defs"][rule["$ref"].rsplit("/", 1)[1]]
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if type(value) is not types[rule["type"]]:
        errors.append({"code": "schema_type", "at": location})
        return errors
    if "enum" in rule and value not in rule["enum"]:
        errors.append({"code": "schema_enum", "at": location})
    if isinstance(value, dict):
        props = rule.get("properties", {})
        if set(value) - set(props) and not rule.get("additionalProperties", True):
            errors.append({"code": "unknown_fields", "at": location})
        for key in rule.get("required", []):
            if key not in value:
                errors.append({"code": "missing_field", "at": location + "." + key})
        for key in props:
            if key in value:
                _validate(value[key], props[key], schema, location + "." + key, errors)
    elif isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append({"code": "empty_list", "at": location})
        if rule.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append({"code": "duplicates", "at": location})
        for index, item in enumerate(value):
            _validate(item, rule["items"], schema, f"{location}[{index}]", errors)
    elif isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or ("pattern" in rule and not re.search(rule["pattern"], value)):
            errors.append({"code": "schema_string", "at": location})
    return errors


def _path(root, raw):
    path = PurePosixPath(raw)
    if (path.is_absolute() or ".." in path.parts or "\\" in raw or ":" in raw
            or any(ord(char) < 32 for char in raw) or path.as_posix() != raw or raw == "."):
        raise ValueError("unsafe_path")
    resolved = (root / raw).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("unsafe_path")
    return resolved


def _digest(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint(context, project_root, facts, generated_sources=()):
    """Rebase after upstream writes, returning a new context without saving it.

    Callers must recheck facts explicitly. Only passed diff/documentation outputs
    may replace sources or be added via {path, sha256, role} generated_sources.
    All other sources must remain unchanged; downstream passes forbid rebasing.
    This is a mechanical checkpoint, not an automatic attestation of prose.
    """
    root = Path(project_root).resolve()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if _validate(context, schema, schema):
        raise ValueError("checkpoint_malformed_context")
    old_hash = input_hash(context)
    artifacts = {}
    passed = []
    for name, step in context["steps"].items():
        if step["status"] != "passed":
            continue
        if (name not in ("diff", "documentation") or name not in context["allowed_steps"]
                or step["input_hash"] != old_hash or not step["artifacts"]):
            raise ValueError("checkpoint_ineligible_step")
        for artifact in step["artifacts"]:
            if _digest(_path(root, artifact["path"])) != artifact["sha256"]:
                raise ValueError("checkpoint_stale_artifact")
            artifacts[artifact["path"]] = artifact["sha256"]
        passed.append(name)
    updated = copy.deepcopy(context)
    for source in updated["sources"]:
        actual = _digest(_path(root, source["path"]))
        if actual != source["sha256"]:
            if artifacts.get(source["path"]) != actual:
                raise ValueError("checkpoint_unrecorded_change")
            source["sha256"] = actual
    existing = {source["path"] for source in updated["sources"]}
    for source in generated_sources:
        if (_validate(source, schema["properties"]["sources"]["items"], schema)
                or source["path"] in existing or artifacts.get(source["path"]) != source["sha256"]):
            raise ValueError("checkpoint_invalid_generated_source")
        updated["sources"].append(copy.deepcopy(source))
        existing.add(source["path"])
    updated["facts"] = copy.deepcopy(facts)
    updated.pop("jira", None)
    new_hash = input_hash(updated)
    for name in passed:
        updated["steps"][name]["input_hash"] = new_hash
    result = preflight(updated, root)
    if result["errors"]:
        raise ValueError("checkpoint_invalid_result")
    return updated


def preflight(context, project_root):
    """Return compact status without returning source/fact/Jira text or writing."""
    result = {"status": "malformed", "count": {}, "coverage": {}, "paths": [],
              "errors": [], "next_action": "fix_context", "input_hash": None,
              "needed_steps": [], "reusable_steps": []}
    errors = result["errors"]
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errors.extend(_validate(context, schema, schema))
    except (OSError, ValueError, RecursionError):
        errors.append({"code": "schema_unavailable", "at": "$"})
    if errors:
        return result
    root = Path(project_root).resolve()
    if not root.is_dir():
        errors.append({"code": "invalid_project_root", "at": "$"})
        return result
    fingerprint = input_hash(context)
    result["input_hash"] = fingerprint
    registered = set()
    verified = set()
    paths = set()

    def check_file(raw, at, expected=None):
        try:
            path = _path(root, raw)
            paths.add(raw)
            if not path.is_file():
                errors.append({"code": "missing_file", "at": at})
                return False
            if expected is not None and _digest(path) != expected:
                errors.append({"code": "stale_hash", "at": at})
                return False
            return True
        except (OSError, ValueError, RuntimeError):
            errors.append({"code": "unsafe_or_unreadable_path", "at": at})
            return False

    for index, source in enumerate(context["sources"]):
        at = f"$.sources[{index}]"
        if source["path"] in registered:
            errors.append({"code": "duplicate_source", "at": at})
        registered.add(source["path"])
        if check_file(source["path"], at, source["sha256"]):
            verified.add(source["path"])
    scope = context["scope"]
    if not scope["files"] and not scope["commits"]:
        errors.append({"code": "empty_scope", "at": "$.scope"})
    for index, raw in enumerate(scope["files"]):
        try:
            _path(root, raw)
        except (ValueError, OSError, RuntimeError):
            errors.append({"code": "unsafe_scope_path", "at": f"$.scope.files[{index}]"})
    if scope["kind"] == "task" and scope["id"] != context["task_id"]:
        errors.append({"code": "task_scope_mismatch", "at": "$.scope.id"})

    def evidence(items, at):
        for index, raw in enumerate(items):
            if raw not in verified:
                errors.append({"code": "unverified_evidence", "at": f"{at}[{index}]"})

    fact_ids = set()
    for index, fact in enumerate(context["facts"]):
        if fact["id"] in fact_ids:
            errors.append({"code": "duplicate_fact", "at": f"$.facts[{index}].id"})
        fact_ids.add(fact["id"])
        evidence(fact["evidence"], f"$.facts[{index}].evidence")
    jira = context.get("jira")
    if jira:
        if "jira" not in context["allowed_steps"]:
            errors.append({"code": "jira_not_authorized", "at": "$.jira"})
        evidence(jira["evidence"], "$.jira.evidence")
        evidence([jira["release_source"]], "$.jira.release_source")
        if jira["text"].strip().splitlines()[-1] != "\u0440\u0435\u043b\u0438\u0437 " + jira["release"]:
            errors.append({"code": "jira_release_line", "at": "$.jira.text"})
        if re.search(r"[\u2013\u2014\u00ab\u00bb]|(?m:^\s*(?:[-*#>]\s|\d+[.)]\s))", jira["text"]):
            errors.append({"code": "jira_style", "at": "$.jira.text"})
        for index, shot in enumerate(jira["shots"]):
            evidence([shot["path"]], f"$.jira.shots[{index}].path")
    source_errors = bool(errors)
    for name in STEPS:
        step = context["steps"].get(name)
        if name not in context["allowed_steps"]:
            continue
        if step is None or step["status"] != "passed":
            result["needed_steps"].append(name)
            if step and step["status"] == "blocked":
                errors.append({"code": "step_blocked", "at": "$.steps." + name})
            continue
        before = len(errors)
        if step["input_hash"] != fingerprint:
            errors.append({"code": "stale_step", "at": "$.steps." + name})
        if not step["artifacts"]:
            errors.append({"code": "missing_artifacts", "at": "$.steps." + name})
        for index, artifact in enumerate(step["artifacts"]):
            check_file(artifact["path"], f"$.steps.{name}.artifacts[{index}]", artifact["sha256"])
        if name == "jira" and jira is None:
            errors.append({"code": "missing_jira", "at": "$.jira"})
        if len(errors) == before and not source_errors:
            result["reusable_steps"].append(name)
        else:
            result["needed_steps"].append(name)
    result["paths"] = sorted(paths)
    result["count"] = {"sources": len(registered), "facts": len(fact_ids),
                       "needed_steps": len(result["needed_steps"]), "reusable_steps": len(result["reusable_steps"])}
    result["coverage"] = {"sources_verified": len(verified), "sources_total": len(registered),
                          "scope_kind": scope["kind"], "scope_files": len(scope["files"]),
                          "scope_commits": len(scope["commits"])}
    result["status"] = "blocked" if errors else ("ready" if result["needed_steps"] else "complete")
    result["next_action"] = "resolve_blockers" if errors else (
        "run_" + result["needed_steps"][0] if result["needed_steps"] else "reuse")
    if any(error["code"] in ("stale_hash", "missing_file") for error in errors):
        result["next_action"] = "refresh_sources" if context["refresh_authorized"] else "request_refresh_consent"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="Workflow JSON path (relative to project root or absolute within it)")
    parser.add_argument("--project-root", required=True, help="Project containment root")
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        path = Path(args.context)
        path = (root / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(root):
            raise ValueError("context_outside_root")
        def unique_object(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("duplicate_key")
                obj[key] = value
            return obj
        context = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite")))
        result = preflight(context, root)
    except (OSError, ValueError, RecursionError, RuntimeError):
        result = {"status": "malformed", "count": {}, "coverage": {}, "paths": [],
                  "errors": [{"code": "context_unreadable_or_malformed", "at": "$"}],
                  "next_action": "fix_context", "input_hash": None, "needed_steps": [], "reusable_steps": []}
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
    return 2 if result["status"] == "malformed" else (1 if result["errors"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
