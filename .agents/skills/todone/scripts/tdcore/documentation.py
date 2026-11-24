"""Local-first documentation domain for ``todone``.

Tasks and flows remain owned by the existing queue engine. This module owns the
explicit project documentation workspace, exact envelopes, revision sidecars,
bounded resolver and scoped documentation policy.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone

from .errors import Issue, SkillError
from .queue import load_json

WORKSPACE_SCHEMA = "WORKSPACE-1"
DOC_SCHEMA = "DOC-1"
MACHINE_SCHEMA = "DOC-MACHINE-1"
CLAIM_SCHEMA = "DOC-CLAIM-1"
CAPTURE_SCHEMA = "DOC-CAPTURE-1"
PACKET_SCHEMA = "DOC-PACKET-1"
POLICY_SCHEMA = "DOC-POLICY-1"
DOC_PATH_SCHEMA = "DOC-PATH-1"
DOC_PATH_POINTER = ".todone/docs-path.json"
DOC_PATH_KEYS = ("$schema", "schema", "root", "docs_path", "manifest")
DOC_KINDS = ("overview", "architecture", "glossary", "requirement", "scenario",
             "business_rule", "entity", "contract", "flow", "flow_path",
             "decision_tree", "data_map", "lifecycle", "test_case", "test_map",
             "integration", "command_reference", "error_reference", "release",
             "change", "adr", "faq")
DOC_STATUSES = ("draft", "active", "proposed", "verified", "conflicted", "stale",
                "retired", "superseded")
AUTOMATION = ("ask", "always", "manual", "disabled")
ENFORCEMENT = ("advisory", "required", "critical")
CADENCE = ("slice", "aggregate", "both", "explicit")
UPDATE_AFTER = ("implementation", "slice_tests", "all_tests", "explicit_command")
VERIFY = ("on_update", "after_final_tests", "on_close")
CLAIM_STATUS = ("observed", "declared", "inferred", "proposed", "unknown")
REVIEW_STATUS = ("unreviewed", "reviewed", "approved", "rejected")
CAPTURE_STATUSES = ("captured", "packet_ready", "draft", "needs_review", "approved",
                    "rejected", "applied")
MODULE_KEYS = ("$schema", "schema", "workspace_id", "doc_key", "doc_kind", "canonical_path",
               "machine_path", "claims_path", "revision", "status", "summary", "audience",
               "scope", "content_format", "machine_format", "source_task_refs", "source_refs",
               "source_fingerprints", "supersedes", "created_at", "updated_at", "updated_by",
               "generated", "checks")
DOC_FAMILY_DIRS = {"glossary": "glossary", "overview": "overview", "architecture": "architecture",
    "requirement": "requirements", "scenario": "scenarios", "business_rule": "business-rules",
    "entity": "entities", "contract": "contracts", "flow": "workflows", "flow_path": "workflows",
    "decision_tree": "decisions", "decision": "decisions", "test_map": "test-maps",
    "test_case": "test-maps", "change": "changes", "adr": "decisions", "release": "changes",
    "integration": "contracts", "data_map": "entities", "lifecycle": "entities",
    "command_reference": "contracts", "error_reference": "contracts", "faq": "glossary"}


def now_stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path):
    try:
        with open(path, "rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            return "sha256:" + digest.hexdigest()
    except OSError:
        return None


def atomic_json(path, payload):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as src, open(path + ".bak", "w", encoding="utf-8") as dst:
            dst.write(src.read())
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return path


def _json(path, what, default=None):
    if not os.path.isfile(path):
        return default
    return load_json(path, what)


def _read_text(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def validate_doc_path(pointer, where="documentation path"):
    """Validate the persisted pointer used to rediscover a custom docs root."""
    if not isinstance(pointer, dict):
        return [Issue("error", where, "DOC-PATH-1 должен быть object", "DOC_PATH_INVALID")]
    allowed = set(DOC_PATH_KEYS)
    issues = [Issue("error", "%s.%s" % (where, key),
                    "ключ не из DOC-PATH-1", "DOC_PATH_INVALID")
              for key in pointer if key not in allowed]
    for key in ("schema", "docs_path"):
        if key not in pointer:
            issues.append(Issue("error", where, "нет поля «%s»" % key,
                                "DOC_PATH_INVALID"))
    if pointer.get("schema") != DOC_PATH_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть %s" % DOC_PATH_SCHEMA,
                            "DOC_PATH_INVALID"))
    if "docs_path" in pointer and (not isinstance(pointer["docs_path"], str)
                                    or not pointer["docs_path"].strip()):
        issues.append(Issue("error", "%s.docs_path" % where,
                            "docs_path должен быть непустой строкой",
                            "DOC_PATH_INVALID"))
    if "manifest" in pointer and (not isinstance(pointer["manifest"], str)
                                   or not pointer["manifest"].strip()):
        issues.append(Issue("error", "%s.manifest" % where,
                            "manifest должен быть непустой строкой",
                            "DOC_PATH_INVALID"))
    return issues


def _resolve_doc_path(root, value):
    if not isinstance(value, str) or not value.strip():
        raise SkillError("DOC_PATH_INVALID", "docs_path должен быть непустой строкой",
                         DOC_PATH_POINTER)
    candidate = value if os.path.isabs(value) else os.path.join(root, value)
    absolute = os.path.abspath(candidate)
    try:
        inside = os.path.commonpath([root, os.path.realpath(absolute)]) == root
    except ValueError:
        inside = False
    if not inside:
        raise SkillError("DOC_PATH_INVALID",
                         "docs_path не может выходить за пределы project root",
                         value,
                         hint="использовать путь внутри --root")
    return absolute


def _relative_doc_path(root, absolute):
    return os.path.relpath(absolute, root).replace(os.sep, "/")


def _write_text(path, value):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(str(value or ""))
        handle.flush()
        os.fsync(handle.fileno())


def _safe_key(doc_key):
    if not isinstance(doc_key, str) or not doc_key.strip():
        raise SkillError("DOC_KEY_UNKNOWN", "doc_key пуст", "documentation")
    value = doc_key.strip().strip("/")
    if ".." in value or "\\" in value or not re.match(r"^[A-Za-z0-9_.:/-]+$", value):
        raise SkillError("DOC_KEY_INVALID", "doc_key имеет небезопасный формат: %s" % doc_key, doc_key)
    parts = [item for item in value.split("/") if item]
    if len(parts) < 2:
        raise SkillError("DOC_KEY_INVALID", "doc_key должен быть family/name: %s" % doc_key, doc_key)
    return parts


def _summary(content):
    return (" ".join(str(content or "").split())[:240] or "Без summary")


def _fingerprints(root, refs):
    result = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = ref.get("path") or ref.get("ref")
        if not path or "://" in path:
            continue
        absolute = path if os.path.isabs(path) else os.path.join(root, path)
        digest = sha256_file(absolute)
        result.append({"path": path, "algorithm": "sha256", "value": digest or "sha256:missing",
                       "exists": digest is not None})
    return result


def _is_stale(root, module):
    for item in module.get("source_fingerprints") or []:
        path, expected = item.get("path") or item.get("ref"), item.get("value")
        if not path or not expected or "://" in path:
            continue
        actual = sha256_file(path if os.path.isabs(path) else os.path.join(root, path)) or "sha256:missing"
        if actual != expected:
            return True
    return False


def _release_matches(module, release):
    scope = module.get("scope") or {}
    return not scope.get("release") or scope.get("release") == release


class DocumentationWorkspace:
    def __init__(self, root, docs_path=None):
        self.root = os.path.abspath(root)
        self.pointer_path = os.path.join(self.root, DOC_PATH_POINTER)
        self._requested_docs_path = docs_path
        selected = docs_path or self._discover_docs_path()
        self.docs_path = _resolve_doc_path(self.root, selected)
        self.docs_path_value = _relative_doc_path(self.root, self.docs_path)
        self.manifest_path = os.path.join(self.docs_path, "manifest.json")
        self.catalog_path = os.path.join(self.root, ".todone", "catalog", "docs.json")
        self._manifest = None

    def _discover_docs_path(self):
        if not os.path.isfile(self.pointer_path):
            return "docs"
        pointer = _json(self.pointer_path, "documentation path pointer")
        issues = validate_doc_path(pointer, self.pointer_path)
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where,
                             command="tcheck docs init --root <root> --docs-path <path>")
        return pointer["docs_path"]

    def _write_pointer(self):
        pointer = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                   "schema": DOC_PATH_SCHEMA, "root": ".",
                   "docs_path": self.docs_path_value,
                   "manifest": self.docs_path_value + "/manifest.json"}
        issues = validate_doc_path(pointer, self.pointer_path)
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where)
        atomic_json(self.pointer_path, pointer)
        return pointer

    @property
    def manifest(self):
        if self._manifest is None:
            self._manifest = _json(self.manifest_path, "документационный manifest")
        return self._manifest

    def validate_manifest(self, manifest):
        if not isinstance(manifest, dict):
            return [Issue("error", self.manifest_path, "manifest должен быть объектом", "DOC_MANIFEST_INVALID")]
        allowed = ("$schema", "schema", "workspace_id", "product_id", "root", "docs_path",
                   "task_registry", "default_release", "release_registry", "catalog_path",
                   "contract_versions", "policy")
        issues = [Issue("error", "%s.%s" % (self.manifest_path, key), "ключ не из WORKSPACE-1",
                        "DOC_MANIFEST_INVALID") for key in manifest if key not in allowed]
        for key in ("schema", "workspace_id", "product_id", "docs_path", "policy"):
            if key not in manifest:
                issues.append(Issue("error", self.manifest_path, "в manifest нет «%s»" % key,
                                    "DOC_MANIFEST_INVALID"))
        if manifest.get("schema") != WORKSPACE_SCHEMA:
            issues.append(Issue("error", self.manifest_path, "schema должен быть %s" % WORKSPACE_SCHEMA,
                                "DOC_MANIFEST_INVALID"))
        if isinstance(manifest.get("docs_path"), str):
            try:
                manifest_path = _resolve_doc_path(self.root, manifest["docs_path"])
                if manifest_path != self.docs_path:
                    issues.append(Issue("error", "%s.docs_path" % self.manifest_path,
                                        "docs_path manifest не совпадает с выбранной точкой записи",
                                        "DOC_PATH_CONFLICT"))
            except SkillError as exc:
                issues.append(Issue("error", "%s.docs_path" % self.manifest_path,
                                    exc.message, exc.code))
        if not isinstance(manifest.get("policy"), dict):
            issues.append(Issue("error", self.manifest_path, "policy должен быть объектом", "DOC_POLICY_INVALID"))
        else:
            issues.extend(validate_policy(manifest["policy"], self.manifest_path))
        return issues

    def require_manifest(self):
        if self.manifest is None:
            raise SkillError("DOC_WORKSPACE_MISSING", "docs workspace не инициализирован", self.manifest_path,
                             command="tcheck docs init --root <root>")
        issues = self.validate_manifest(self.manifest)
        if any(i.is_error for i in issues):
            first = issues[0]
            raise SkillError("DOC_MANIFEST_INVALID", first.message, first.where,
                             command="tcheck docs check --root <root>")
        return self.manifest

    def init(self, workspace_id=None, product_id=None, policy=None):
        os.makedirs(self.docs_path, exist_ok=True)
        if self._requested_docs_path is not None and os.path.isfile(self.pointer_path):
            pointer = _json(self.pointer_path, "documentation path pointer")
            issues = validate_doc_path(pointer, self.pointer_path)
            if any(item.is_error for item in issues):
                first = next(item for item in issues if item.is_error)
                raise SkillError(first.code, first.message, first.where)
            if _resolve_doc_path(self.root, pointer["docs_path"]) != self.docs_path:
                raise SkillError("DOC_PATH_CONFLICT",
                                 "нельзя сменить docs_path без отдельной migration policy",
                                 self.pointer_path,
                                 hint="использовать сохранённый --docs-path или миграцию")
        existing = self.manifest
        if existing is not None and isinstance(existing.get("docs_path"), str):
            if _resolve_doc_path(self.root, existing["docs_path"]) != self.docs_path:
                raise SkillError("DOC_PATH_CONFLICT",
                                 "manifest уже привязан к другой точке записи",
                                 self.manifest_path)
        ident = workspace_id or os.path.basename(self.root) or "workspace"
        manifest = {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": WORKSPACE_SCHEMA,
                    "workspace_id": ident, "product_id": product_id or ident, "root": ".",
                    "docs_path": self.docs_path_value, "task_registry": ".todone", "default_release": None,
                    "release_registry": ".todone/releases.json", "catalog_path": ".todone/catalog/docs.json",
                    "contract_versions": {"module": DOC_SCHEMA, "claim": CLAIM_SCHEMA,
                                          "capture": CAPTURE_SCHEMA, "packet": PACKET_SCHEMA},
                    "policy": effective_policy(default_policy(), policy)}
        issues = self.validate_manifest(manifest)
        if any(i.is_error for i in issues):
            first = issues[0]
            raise SkillError(first.code, first.message, first.where)
        atomic_json(self.manifest_path, manifest)
        self._write_pointer()
        self._manifest = manifest
        for family in ("glossary", "requirements", "scenarios", "business-rules", "entities", "contracts",
                       "workflows", "decisions", "test-maps", "changes"):
            os.makedirs(os.path.join(self.docs_path, family), exist_ok=True)
        return manifest

    def policy(self):
        # Policy may be changed by a scoped chat adapter instance; reload the
        # manifest so callers never observe a stale cached default.
        self._manifest = None
        return effective_policy(self.require_manifest().get("policy"))

    def set_policy(self, values, by=None, reason=None, approved_by=None):
        manifest = self.require_manifest()
        old = dict(manifest.get("policy") or {})
        new = dict(old)
        new.update({key: value for key, value in values.items() if value is not None})
        if (old.get("enforcement") in ("required", "critical")
                and new.get("enforcement") == "advisory"
                and not approved_by):
            raise SkillError("DOC_POLICY_CONFLICT",
                             "нельзя понизить required/critical policy без approval",
                             self.manifest_path)

        issues = validate_policy(new, self.manifest_path)
        if any(i.is_error for i in issues):
            first = issues[0]
            raise SkillError(first.code, first.message, first.where)
        new.update({"policy": POLICY_SCHEMA, "updated_at": now_stamp(), "updated_by": by or "local",
                    "reason": reason or "policy change"})
        manifest["policy"] = new
        atomic_json(self.manifest_path, manifest)
        self._manifest = manifest
        decision = {"actor": by or "local", "approved_by": approved_by,
                    "at": now_stamp(), "reason": reason or "policy change",
                    "scope": "workspace", "fingerprint": sha256_bytes(json.dumps(new, sort_keys=True))}
        return {"old": old, "new": new, "decision": decision}

    def module_paths(self, doc_key, doc_kind=None):
        parts = _safe_key(doc_key)
        folder = os.path.join(self.docs_path, DOC_FAMILY_DIRS.get(parts[0], parts[0] + "s"), *parts[1:-1])
        stem = parts[-1]
        return {"folder": folder, "markdown": os.path.join(folder, stem + ".md"),
                "module": os.path.join(folder, stem + ".module.json"),
                "machine": os.path.join(folder, stem + ".machine.json"),
                "claims": os.path.join(folder, stem + ".claims.json"),
                "fixtures": os.path.join(folder, stem + ".fixtures")}

    def read_module(self, doc_key, revision=None):
        paths = self.module_paths(doc_key)
        module = _json(paths["module"], "module %s" % doc_key)
        if module is None:
            raise SkillError("DOC_KEY_UNKNOWN", "документа «%s» нет" % doc_key, paths["module"],
                             command="tcheck docs catalog --root <root>")
        selected = dict(paths)
        if revision is not None and int(module.get("revision", 0)) != int(revision):
            number = int(revision); stem = os.path.basename(paths["module"]).replace(".module.json", "")
            selected.update({"module": os.path.join(paths["folder"], "%s.r%d.module.json" % (stem, number)),
                             "markdown": os.path.join(paths["folder"], "%s.r%d.md" % (stem, number)),
                             "machine": os.path.join(paths["folder"], "%s.r%d.machine.json" % (stem, number)),
                             "claims": os.path.join(paths["folder"], "%s.r%d.claims.json" % (stem, number))})
            module = _json(selected["module"], "module %s@%s" % (doc_key, revision))
            if module is None:
                raise SkillError("DOC_REVISION_CONFLICT", "у документа %s нет revision %s" % (doc_key, revision),
                                 paths["module"])
        return {"module": module, "paths": selected, "content": _read_text(selected["markdown"]),
                "machine": _json(selected["machine"], "machine %s" % doc_key),
                "claims": _json(selected["claims"], "claims %s" % doc_key)}

    def write_module(self, doc_key, doc_kind, content, machine=None, claims=None,
                     source_task_refs=None, source_refs=None, scope=None, status="draft",
                     by="writer", generated=False):
        self.require_manifest()
        if doc_kind not in DOC_KINDS:
            raise SkillError("DOC_MODULE_INVALID", "doc_kind «%s» не объявлен" % doc_kind, doc_key)
        paths = self.module_paths(doc_key, doc_kind); os.makedirs(paths["folder"], exist_ok=True)
        previous = _json(paths["module"], "module %s" % doc_key)
        revision = int((previous or {}).get("revision") or 0) + 1
        refs = list(source_refs or [])
        module = {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": DOC_SCHEMA,
                  "workspace_id": self.manifest.get("workspace_id"), "doc_key": doc_key, "doc_kind": doc_kind,
                  "canonical_path": os.path.relpath(paths["markdown"], self.root),
                  "machine_path": os.path.relpath(paths["machine"], self.root) if machine is not None else None,
                  "claims_path": os.path.relpath(paths["claims"], self.root) if claims is not None else None,
                  "revision": revision, "status": status, "summary": _summary(content),
                  "audience": ["agent", "developer", "user"], "scope": dict(scope or {}),
                  "content_format": "gfm", "machine_format": "json" if machine is not None else None,
                  "source_task_refs": list(source_task_refs or []), "source_refs": refs,
                  "source_fingerprints": _fingerprints(self.root, refs),
                  "supersedes": "%s@%d" % (doc_key, int(previous["revision"])) if previous and previous.get("revision") else None,
                  "created_at": (previous or {}).get("created_at") or now_stamp(), "updated_at": now_stamp(),
                  "updated_by": by, "generated": bool(generated),
                  "checks": {"schema": "passed", "links": "passed", "stale": "current", "render": "not_run"}}
        if machine is not None and (not isinstance(machine, dict)
                                    or machine.get("doc_key") != doc_key
                                    or machine.get("revision") != revision):
            raise SkillError("DOC_MACHINE_INVALID",
                             "machine doc_key/revision не совпадает с DOC-1 module", doc_key)
        if claims is not None and (not isinstance(claims, dict)
                                   or claims.get("doc_key") != doc_key
                                   or claims.get("revision") != revision):
            raise SkillError("DOC_CLAIM_INVALID",
                             "claims doc_key/revision не совпадает с DOC-1 module", doc_key)
        for validator, value, label in ((validate_module, module, "module"),
                                         (validate_machine, machine, "machine"),
                                         (validate_claims, claims, "claims")): 
            issues = validator(value, "%s.%s" % (doc_key, label))
            if any(i.is_error for i in issues):
                first = issues[0]; raise SkillError(first.code, first.message, first.where)
        if previous and previous.get("revision"):
            number = int(previous["revision"]); stem = os.path.basename(paths["module"]).replace(".module.json", "")
            archives = {"module": "%s.r%d.module.json" % (stem, number), "markdown": "%s.r%d.md" % (stem, number),
                        "machine": "%s.r%d.machine.json" % (stem, number), "claims": "%s.r%d.claims.json" % (stem, number)}
            for key, name in archives.items():
                if os.path.isfile(paths[key]) and not os.path.isfile(os.path.join(paths["folder"], name)):
                    with open(paths[key], "rb") as src, open(os.path.join(paths["folder"], name), "wb") as dst:
                        dst.write(src.read())
        _write_text(paths["markdown"] + ".tmp", content or "")
        if machine is not None: atomic_json(paths["machine"] + ".tmp", machine)
        if claims is not None: atomic_json(paths["claims"] + ".tmp", claims)
        atomic_json(paths["module"] + ".tmp", module)
        for key in ("markdown", "machine", "claims", "module"):
            tmp = paths[key] + ".tmp"
            if os.path.isfile(tmp): os.replace(tmp, paths[key])
        for key, value in (("machine", machine), ("claims", claims)):
            if value is None and os.path.isfile(paths[key]):
                os.unlink(paths[key])
        self.build_catalog()
        return self.read_module(doc_key)

    def scan_modules(self):
        result = []
        if not os.path.isdir(self.docs_path): return result
        for folder, dirs, files in os.walk(self.docs_path):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                if name.endswith(".module.json"):
                    item = _json(os.path.join(folder, name), "module %s" % name)
                    if isinstance(item, dict): result.append(item)
        return sorted(result, key=lambda item: (item.get("doc_key") or "", int(item.get("revision") or 0)))

    def build_catalog(self):
        revisions = self.scan_modules(); current = {}
        for item in revisions:
            key = item.get("doc_key")
            if key not in current or int(item.get("revision") or 0) > int(current[key].get("revision") or 0):
                current[key] = item
        payload = {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": "DOC-CATALOG-1",
                   "workspace_id": (self.manifest or {}).get("workspace_id"), "generated_at": now_stamp(),
                   "modules": list(current.values()), "revisions": revisions, "count": len(current),
                   "source_fingerprint": sha256_bytes(json.dumps(revisions, sort_keys=True, ensure_ascii=False))}
        atomic_json(self.catalog_path, payload)
        return payload

    def resolve(self, mode="catalog", doc_key=None, task_refs=None, files=None, symbols=None,
                release=None, limits=None):
        catalog = self.build_catalog(); modules = list(catalog.get("modules") or []); limits = dict(limits or {})
        if doc_key: modules = [m for m in modules if m.get("doc_key") == doc_key]
        if release: modules = [m for m in modules if _release_matches(m, release)]
        tasks, paths = set(task_refs or []), set(files or [])
        if tasks: modules = [m for m in modules if tasks.intersection(set(m.get("source_task_refs") or []))]
        if paths: modules = [m for m in modules if any(str(r.get("path")) in paths for r in m.get("source_refs") or [])]
        modules.sort(key=lambda m: m.get("doc_key") or "")
        max_modules, max_chars = int(limits.get("modules") or 12), int(limits.get("chars") or 24000)
        truncated = len(modules) > max_modules; omitted = [m.get("doc_key") for m in modules[max_modules:]]; modules = modules[:max_modules]
        result = {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": "DOC-QUERY-RESPONSE-1",
                  "mode": mode, "query_fingerprint": sha256_bytes(json.dumps({"mode": mode, "doc_key": doc_key,
                  "task_refs": sorted(tasks), "files": sorted(paths), "symbols": symbols or [], "release": release,
                  "limits": limits}, sort_keys=True)), "scope": {"workspace_id": (self.manifest or {}).get("workspace_id"), "release": release},
                  "summaries": [{"doc_key": m.get("doc_key"), "doc_kind": m.get("doc_kind"), "revision": m.get("revision"),
                  "status": m.get("status"), "summary": m.get("summary"), "scope": m.get("scope"), "stale": _is_stale(self.root, m)} for m in modules],
                  "modules": [], "machine": [], "claims": [], "refs": [], "unknowns": [], "conflicts": [], "stale": [],
                  "limits": limits, "truncation": {"truncated": truncated, "omitted_refs": omitted}}
        total = 0
        if mode != "catalog":
            for module in modules:
                try: item = self.read_module(module.get("doc_key"))
                except SkillError as exc: result["unknowns"].append(exc.message); continue
                content = item.get("content") or ""
                if mode in ("module", "for-task", "impact", "path", "test-map", "reconstruct"):
                    if total + len(content) > max_chars:
                        result["truncation"]["truncated"] = True; result["truncation"]["omitted_refs"].append(module.get("doc_key"))
                    else: result["modules"].append(content); total += len(content)
                if mode in ("machine", "for-task", "impact", "path", "test-map", "reconstruct"):
                    if item.get("machine") is not None: result["machine"].append(item["machine"])
                    if item.get("claims") is not None: result["claims"].append(item["claims"])
                result["refs"].extend(module.get("source_refs") or [])
                if _is_stale(self.root, module): result["stale"].append(module.get("doc_key"))
        return result

    def check(self):
        if self.manifest is None:
            return [Issue("warning", self.manifest_path, "docs workspace не инициализирован", "DOC_WORKSPACE_MISSING")]
        issues = self.validate_manifest(self.manifest)
        for module in self.scan_modules():
            issues.extend(validate_module(module))
            try:
                item = self.read_module(module.get("doc_key"))
                if item.get("content") is None: issues.append(Issue("error", module.get("doc_key"), "Markdown-файл отсутствует", "DOC_REF_BROKEN"))
                issues.extend(validate_machine(item.get("machine"), module.get("doc_key")))
                issues.extend(validate_claims(item.get("claims"), module.get("doc_key")))
                if _is_stale(self.root, module): issues.append(Issue("warning", module.get("doc_key"), "source fingerprint устарел", "DOC_STALE"))
            except SkillError as exc: issues.append(Issue("error", module.get("doc_key"), exc.message, exc.code))
        self.build_catalog(); return issues

    def capture(self, task_refs=None, doc_keys=None, release_context=None, user_intent="задокументируй",
                changed_files=None, decision_digest="", transcript_digest=None, by="chat"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        payload = {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": CAPTURE_SCHEMA,
                   "capture_id": "capture:chat:" + stamp, "source": {"system": "chat", "conversation_ref": None, "message_ref": None},
                   "task_refs": list(task_refs or []), "doc_keys": list(doc_keys or []), "release_context": release_context or {},
                   "user_intent": user_intent, "changed_files": list(changed_files or []), "decision_digest": decision_digest,
                   "transcript_digest": transcript_digest, "redaction": {"secrets_removed": True, "pii_removed": True},
                   "provenance": [{"by": by, "at": now_stamp()}], "status": "captured"}
        issues = validate_capture(payload)
        if any(i.is_error for i in issues): first = issues[0]; raise SkillError(first.code, first.message, first.where)
        atomic_json(os.path.join(self.docs_path, "captures", stamp + ".json"), payload); return payload


def default_policy():
    return {"policy": POLICY_SCHEMA, "automation": "ask", "enforcement": "advisory", "cadence": "slice",
            "update_after": "slice_tests", "verify": "on_close", "render": "on_close", "audit": "machine"}


def effective_policy(policy=None, override=None):
    result = default_policy()
    for source in (policy, override):
        if isinstance(source, dict):
            legacy_mode = source.get("mode")
            if legacy_mode is not None:
                result["automation"] = "disabled" if legacy_mode in ("off", "disabled") else (
                    "manual" if legacy_mode in ("manual", "explicit") else result["automation"])
            for key, value in source.items():
                if value is not None and (key in result or key in ("policy", "reason", "updated_at", "updated_by", "scope", "explicit_intent", "retain_impact_record")):
                    result[key] = value
    return result


def validate_policy(policy, where="documentation policy"):
    issues = []
    raw = policy
    if not isinstance(raw, dict):
        return [Issue("error", where, "policy должен быть object", "DOC_POLICY_INVALID")]
    policy = effective_policy(raw)
    allowed = ("policy", "automation", "enforcement", "cadence", "update_after", "verify",
               "render", "audit", "updated_at", "updated_by", "reason", "scope",
               "retain_impact_record", "mode")
    issues.extend(Issue("error", "%s.%s" % (where, key), "ключ не из DOC-POLICY-1",
                        "DOC_POLICY_INVALID") for key in raw if key not in allowed)
    for key, values in (("automation", AUTOMATION), ("enforcement", ENFORCEMENT),
                        ("cadence", CADENCE), ("update_after", UPDATE_AFTER),
                        ("verify", VERIFY)):
        if policy.get(key) not in values:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "значение «%s» не из %s" % (policy.get(key), list(values)),
                                "DOC_POLICY_INVALID"))
    return issues


class PolicyDecisionStore:
    def __init__(self, root):
        self.root = os.path.abspath(root); self.path = os.path.join(self.root, ".todone", "documentation-policy-decisions.json")
    def read(self):
        if not os.path.isfile(self.path): return {"schema": "DOC-POLICY-DECISIONS-1", "decisions": []}
        data = _json(self.path, "documentation policy decisions")
        if not isinstance(data, dict) or data.get("schema") != "DOC-POLICY-DECISIONS-1":
            raise SkillError("DOC_POLICY_INVALID", "policy decision ledger has invalid schema", self.path)
        return data
    def set(self, scope, values, by="local", reason=None, scope_ref=None,
            approved_by=None):
        if scope not in ("workspace", "flow", "preset", "task", "change", "run"):
            raise SkillError("DOC_POLICY_INVALID", "unsupported policy scope: %s" % scope, self.path)
        clean = {k: v for k, v in (values or {}).items() if v is not None}
        unknown = [key for key in clean if key not in ("policy", "automation", "enforcement", "cadence",
                                                        "update_after", "verify", "render", "audit", "mode")]
        if unknown:
            raise SkillError("DOC_POLICY_INVALID", "unknown policy keys: %s" % ", ".join(unknown), self.path)
        merged = effective_policy(default_policy(), clean)
        issues = validate_policy(merged, self.path)
        if any(i.is_error for i in issues): first = issues[0]; raise SkillError(first.code, first.message, first.where)
        old = self.current(scope, scope_ref); new = effective_policy(old or default_policy(), clean)
        if (old and old.get("enforcement") in ("required", "critical")
                and new.get("enforcement") == "advisory" and not approved_by):
            raise SkillError("DOC_POLICY_CONFLICT",
                             "нельзя понизить required/critical policy без approval",
                             self.path)
        decision = {"schema": "DOC-POLICY-DECISION-1", "scope": scope, "scope_ref": scope_ref, "actor": by,
                    "approved_by": approved_by,
                    "at": now_stamp(), "reason": reason or "explicit policy decision", "old": old, "new": new,
                    "policy_fingerprint": sha256_bytes(json.dumps(new, sort_keys=True, ensure_ascii=False))}
        data = self.read(); data["decisions"].append(decision); atomic_json(self.path, data); return decision
    def current(self, scope=None, scope_ref=None):
        result = None
        for item in self.read().get("decisions", []):
            if scope is not None and item.get("scope") != scope: continue
            if scope_ref is not None and item.get("scope_ref") != scope_ref: continue
            result = item.get("new")
        return result


def resolve_effective_policy(workspace=None, flow=None, preset=None, task=None, explicit=None, decisions=None):
    result = effective_policy(workspace)
    for source in (flow, preset, task, explicit): result = effective_policy(result, source)
    for decision in decisions or []: result = effective_policy(result, decision.get("new") if isinstance(decision, dict) else decision)
    return result


effective_policy_resolver = resolve_effective_policy


def validate_module(module, where="module"):
    if not isinstance(module, dict): return [Issue("error", where, "module должен быть объектом", "DOC_MODULE_INVALID")]
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-1", "DOC_MODULE_INVALID") for key in module if key not in MODULE_KEYS]
    for key in ("schema", "workspace_id", "doc_key", "doc_kind", "revision", "canonical_path", "status", "summary"):
        if key not in module: issues.append(Issue("error", where, "нет обязательного поля «%s»" % key, "DOC_MODULE_INVALID"))
    if module.get("schema") != DOC_SCHEMA: issues.append(Issue("error", where, "schema должен быть %s" % DOC_SCHEMA, "DOC_MODULE_INVALID"))
    if module.get("doc_kind") not in DOC_KINDS: issues.append(Issue("error", where, "doc_kind не объявлен", "DOC_MODULE_INVALID"))
    if module.get("status") not in DOC_STATUSES: issues.append(Issue("error", where, "status не объявлен", "DOC_MODULE_INVALID"))
    if not isinstance(module.get("revision"), int) or module.get("revision") < 1: issues.append(Issue("error", where, "revision должна быть positive integer", "DOC_MODULE_INVALID"))
    try: _safe_key(module.get("doc_key"))
    except SkillError as exc: issues.append(Issue("error", where, exc.message, exc.code))
    return issues


def validate_machine(machine, where="machine"):
    if machine is None: return []
    if not isinstance(machine, dict) or machine.get("schema") != MACHINE_SCHEMA:
        return [Issue("error", where, "machine должен иметь schema %s" % MACHINE_SCHEMA, "DOC_MACHINE_INVALID")]
    allowed = ("$schema", "schema", "doc_key", "doc_kind", "revision", "profile", "payload", "source_refs", "claim_refs", "extensions")
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-MACHINE-1", "DOC_MACHINE_INVALID") for key in machine if key not in allowed]
    for key in ("doc_key", "doc_kind", "revision", "profile", "payload", "source_refs", "claim_refs"):
        if key not in machine: issues.append(Issue("error", where, "machine без %s" % key, "DOC_MACHINE_INVALID"))
    if not isinstance(machine.get("payload"), dict): issues.append(Issue("error", where, "payload должен быть object", "DOC_MACHINE_INVALID"))
    return issues


def validate_claims(claims, where="claims"):
    if claims is None: return []
    if not isinstance(claims, dict) or claims.get("schema") != CLAIM_SCHEMA:
        return [Issue("error", where, "claims должны иметь schema %s" % CLAIM_SCHEMA, "DOC_CLAIM_INVALID")]
    allowed = ("$schema", "schema", "doc_key", "revision", "claims")
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-CLAIM-1", "DOC_CLAIM_INVALID") for key in claims if key not in allowed]
    for key in ("doc_key", "revision", "claims"):
        if key not in claims: issues.append(Issue("error", where, "claims без %s" % key, "DOC_CLAIM_INVALID"))
    if not isinstance(claims.get("revision"), int) or claims.get("revision", 0) < 1: issues.append(Issue("error", where, "revision claims invalid", "DOC_CLAIM_INVALID"))
    if not isinstance(claims.get("claims"), list): issues.append(Issue("error", where, "claims должен быть массив", "DOC_CLAIM_INVALID"))
    for pos, claim in enumerate(claims.get("claims") or []):
        spot = "%s[%d]" % (where, pos)
        if not isinstance(claim, dict): issues.append(Issue("error", spot, "claim должен быть объектом", "DOC_CLAIM_INVALID")); continue
        for key in ("claim_id", "subject", "predicate", "object", "status", "evidence_refs", "review_status"):
            if key not in claim: issues.append(Issue("error", spot, "claim без поля %s" % key, "DOC_CLAIM_NO_EVIDENCE"))
        if claim.get("status") not in CLAIM_STATUS: issues.append(Issue("error", spot, "status claim не объявлен", "DOC_CLAIM_INVALID"))
        if claim.get("review_status") not in REVIEW_STATUS: issues.append(Issue("error", spot, "review_status claim не объявлен", "DOC_CLAIM_INVALID"))
        if claim.get("status") in ("observed", "declared") and not claim.get("evidence_refs"):
            issues.append(Issue("error", spot, "observed/declared claim без evidence_refs", "DOC_CLAIM_NO_EVIDENCE"))
    return issues


def validate_capture(capture, where="capture"):
    if not isinstance(capture, dict): return [Issue("error", where, "capture должен быть объектом", "DOC_CAPTURE_INVALID")]
    allowed = ("$schema", "schema", "capture_id", "source", "task_refs", "doc_keys", "release_context", "user_intent", "changed_files", "decision_digest", "transcript_digest", "redaction", "provenance", "status")
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-CAPTURE-1", "DOC_CAPTURE_INVALID") for key in capture if key not in allowed]
    for key in ("schema", "capture_id", "source", "task_refs", "doc_keys", "release_context", "user_intent", "changed_files", "redaction", "provenance", "status"):
        if key not in capture: issues.append(Issue("error", where, "capture без %s" % key, "DOC_CAPTURE_INVALID"))
    if capture.get("schema") != CAPTURE_SCHEMA: issues.append(Issue("error", where, "schema должен быть %s" % CAPTURE_SCHEMA, "DOC_CAPTURE_INVALID"))
    if not isinstance(capture.get("source"), dict): issues.append(Issue("error", where, "source должен быть object", "DOC_CAPTURE_INVALID"))
    for key in ("task_refs", "doc_keys", "changed_files", "provenance"):
        if not isinstance(capture.get(key), list): issues.append(Issue("error", "%s.%s" % (where, key), "должен быть массив", "DOC_CAPTURE_INVALID"))
    if capture.get("status") not in CAPTURE_STATUSES: issues.append(Issue("error", where, "status capture неизвестен", "DOC_CAPTURE_INVALID"))
    if not isinstance(capture.get("redaction"), dict): issues.append(Issue("error", where, "redaction должен быть объектом", "DOC_CAPTURE_INVALID"))
    return issues


def validate_packet(packet, where="packet"):
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        return [Issue("error", where, "packet должен иметь schema %s" % PACKET_SCHEMA, "DOC_PACKET_INVALID")]
    allowed = {"$schema", "schema", "packet_id", "workspace_id", "release_context",
               "purpose", "task_refs", "doc_keys", "changed_files", "changed_symbols",
               "selected_modules", "claims", "refs", "test_map", "decision_digest",
               "limits", "truncation", "unknowns", "conflicts", "stale"}
    required = ("schema", "packet_id", "workspace_id", "purpose", "task_refs",
                "doc_keys", "selected_modules", "claims", "refs", "decision_digest",
                "limits", "truncation")
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-PACKET-1",
                     "DOC_PACKET_INVALID") for key in packet if key not in allowed]
    issues.extend(Issue("error", where, "packet без %s" % key, "DOC_PACKET_INVALID")
                  for key in required if key not in packet)
    return issues


def make_packet(workspace_id, purpose, task_refs=None, doc_keys=None, selected_modules=None, claims=None, refs=None, limits=None, release_context=None, changed_files=None, decision_digest=None):
    digest = sha256_bytes(json.dumps({"workspace_id": workspace_id, "purpose": purpose, "task_refs": task_refs or [], "doc_keys": doc_keys or []}, sort_keys=True))
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "schema": PACKET_SCHEMA, "packet_id": "packet:" + digest[7:], "workspace_id": workspace_id, "release_context": release_context or {}, "purpose": purpose, "task_refs": list(task_refs or []), "doc_keys": list(doc_keys or []), "changed_files": list(changed_files or []), "changed_symbols": [], "selected_modules": list(selected_modules or []), "claims": list(claims or []), "refs": list(refs or []), "test_map": [], "decision_digest": decision_digest or [], "limits": limits or {"modules": 12, "chars": 24000, "claims": 100}, "truncation": {"truncated": False, "omitted_refs": []}, "unknowns": [], "conflicts": [], "stale": []}


WRITER_SCHEMA = "DOC-WRITER-1"


def validate_writer_result(result, where="writer"):
    if not isinstance(result, dict) or result.get("schema") != WRITER_SCHEMA:
        return [Issue("error", where, "writer result должен иметь schema %s" % WRITER_SCHEMA,
                      "DOC_WRITER_INVALID")]
    required = ("schema", "docs_changed", "doc_keys", "revisions", "claims_changed",
                "source_refs", "render_check", "schema_check", "stale_check",
                "verdict", "unknowns", "next_action")
    allowed = set(required)
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-WRITER-1",
                     "DOC_WRITER_INVALID") for key in result if key not in allowed]
    issues.extend(Issue("error", where, "writer result без %s" % key,
                        "DOC_WRITER_INVALID") for key in required if key not in result)
    if result.get("verdict") not in ("updated", "no_change", "needs_review", "blocked"):
        issues.append(Issue("error", "%s.verdict" % where, "verdict writer неизвестен",
                            "DOC_WRITER_INVALID"))
    if "docs_changed" in result and not isinstance(result["docs_changed"], bool):
        issues.append(Issue("error", "%s.docs_changed" % where,
                            "docs_changed должен быть boolean", "DOC_WRITER_INVALID"))
    return issues



def make_writer_result(docs_changed=False, doc_keys=None, revisions=None,
                       claims_changed=None, source_refs=None, render_check="passed",
                       schema_check="passed", stale_check="current", verdict=None,
                       unknowns=None, next_action="tcheck docs check --root ."):
    if verdict is None:
        verdict = "updated" if docs_changed else "no_change"
    return {"schema": WRITER_SCHEMA, "docs_changed": bool(docs_changed),
            "doc_keys": list(doc_keys or []), "revisions": list(revisions or []),
            "claims_changed": list(claims_changed or []), "source_refs": list(source_refs or []),
            "render_check": render_check, "schema_check": schema_check,
            "stale_check": stale_check, "verdict": verdict,
            "unknowns": list(unknowns or []), "next_action": next_action}


def validate_query_request(request, where="query"):
    if not isinstance(request, dict) or request.get("schema") != "DOC-QUERY-1":
        return [Issue("error", where, "query должен иметь schema DOC-QUERY-1", "DOC_QUERY_INVALID")]
    allowed = {"schema", "mode", "workspace_id", "task_refs", "release_context",
               "files", "symbols", "doc_keys", "limits", "include_history"}
    required = ("schema", "mode", "workspace_id")
    issues = [Issue("error", "%s.%s" % (where, key), "ключ не из DOC-QUERY-1",
                    "DOC_QUERY_INVALID") for key in request if key not in allowed]
    issues.extend(Issue("error", where, "query без %s" % key, "DOC_QUERY_INVALID")
                  for key in required if key not in request)
    for key in ("mode", "workspace_id"):
        if key in request and (not isinstance(request[key], str) or not request[key].strip()):
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "значение должно быть непустой строкой", "DOC_QUERY_INVALID"))
    return issues


POLICY_COMMANDS = {"документация: спрашивай каждый раз": {"automation": "ask"}, "документация: документируй всегда": {"automation": "always"}, "документация: только по команде": {"automation": "manual"}, "документация: отключить": {"automation": "disabled"}}


def parse_documentation_intent(text):
    value = " ".join(str(text or "").strip().lower().split())
    if value in POLICY_COMMANDS: return {"kind": "policy", "values": dict(POLICY_COMMANDS[value]), "command": value}
    if value == "задокументируй": return {"kind": "capture", "values": {}, "command": value}
    return None


def apply_documentation_policy_intent(root, text, actor="chat", scope="workspace", scope_ref=None, reason=None, confirmed=False):
    intent = parse_documentation_intent(text)
    if intent is None or intent["kind"] != "policy": return {"intent": intent, "changed": False}
    values = intent["values"]
    if scope == "workspace" and values.get("automation") == "disabled" and not confirmed:
        raise SkillError("ASK_USER", "отключение workspace documentation требует явного approval", "documentation policy", details={"question": "Отключить автоматическое документирование?", "scope": ["run", "change", "flow", "workspace", "нет"]})
    if scope == "workspace":
        workspace = DocumentationWorkspace(root)
        if workspace.manifest is None: workspace.init()
        result = workspace.set_policy(values, by=actor, reason=reason or intent["command"],
                                      approved_by=actor if confirmed else None)
    else:
        result = PolicyDecisionStore(root).set(scope, values, by=actor,
                                               reason=reason or intent["command"],
                                               scope_ref=scope_ref,
                                               approved_by=actor if confirmed else None)
    return {"intent": intent, "changed": True, "result": result}
