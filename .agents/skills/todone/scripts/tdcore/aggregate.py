"""Read-only recursive aggregate for declared todone workspaces.

The aggregate is a generated projection. Child task.json, queue indexes and
local documentation remain canonical and are never edited by this module.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from .errors import Issue, SkillError

AGGREGATE_SCHEMA = "AGGREGATE-1"
AGGREGATE_VERSION = "aggregate-local-1"
AGGREGATE_KEYS = (
    "$schema", "schema", "aggregate_run_id", "root_workspace_id", "root_path",
    "started_at", "finished_at", "aggregator_version", "contract_version",
    "discovery", "completeness", "counts", "sources", "outputs", "warnings",
    "unknowns", "invalid_sources", "snapshot_path",
)
WORKSPACE_MARKER = "workspace.json"
QUEUE_REGISTRY = "queues.json"
DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn", "node_modules", "vendor", ".cache", "build",
    "dist", "out", "coverage", ".tmp", "__pycache__",
}


def now_stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sha256_bytes(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path):
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except OSError:
        return None


def _json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, payload):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _rel(root, path):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")


def _within(root, path):
    root = os.path.abspath(root)
    path = os.path.abspath(path)
    return path == root or path.startswith(root + os.sep)


def _safe_id(value, fallback):
    value = str(value or "").strip()
    return value if value else fallback


def _media_type(name):
    suffix = os.path.splitext(name.lower())[1]
    return {".md": "text/markdown", ".json": "application/json",
            ".yaml": "application/yaml", ".yml": "application/yaml",
            ".txt": "text/plain"}.get(suffix, "application/octet-stream")


def _warning(code, path, message, severity="warning"):
    return {"code": code, "severity": severity, "path": path, "message": message}


def validate_aggregate_manifest(payload, where="aggregate"):
    """Small semantic validator for the AGGREGATE-1 run envelope."""
    issues = []
    if not isinstance(payload, dict):
        return [Issue("error", where, "aggregate manifest должен быть объектом", "AGGREGATE_INVALID")]
    for key in payload:
        if key not in AGGREGATE_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из AGGREGATE-1", "AGGREGATE_INVALID"))
    for key in ("schema", "aggregate_run_id", "root_workspace_id", "root_path",
                "started_at", "finished_at", "aggregator_version", "contract_version",
                "discovery", "completeness", "counts", "sources", "outputs", "warnings",
                "unknowns", "invalid_sources"):
        if key not in payload:
            issues.append(Issue("error", where, "нет обязательного поля «%s»" % key,
                                "AGGREGATE_INVALID"))
    if payload.get("schema") != AGGREGATE_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть %s" % AGGREGATE_SCHEMA,
                            "AGGREGATE_INVALID"))
    for key in ("discovery", "completeness", "counts"):
        if key in payload and not isinstance(payload[key], dict):
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "поле должно быть object", "AGGREGATE_INVALID"))
    for key in ("sources", "outputs", "warnings", "unknowns", "invalid_sources"):
        if key in payload and not isinstance(payload[key], list):
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "поле должно быть array", "AGGREGATE_INVALID"))
    return issues


class Aggregate:
    """Build and query the generated aggregate under ``<root>/.todone/aggregate``."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.project_todone = os.path.join(self.root, ".todone")
        self.output = os.path.join(self.project_todone, "aggregate")

    # ---- discovery -----------------------------------------------------
    def _read_marker(self, workspace_root, required=False):
        path = os.path.join(workspace_root, ".todone", WORKSPACE_MARKER)
        if not os.path.isfile(path):
            if required:
                return None, _warning("WORKSPACE_MARKER_MISSING", _rel(self.root, workspace_root),
                                      "дочерний workspace не имеет .todone/workspace.json")
            ident = os.path.basename(self.root.rstrip(os.sep)) or "root"
            return {"schema": "WORKSPACE-1", "workspace_id": ident,
                    "kind": "root", "docs_path": "docs", "aggregate": True,
                    "implicit": True}, None
        try:
            marker = _json(path)
        except (OSError, ValueError) as exc:
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "workspace marker не читается: %s" % exc, "error")
        if not isinstance(marker, dict) or marker.get("schema") != "WORKSPACE-1":
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "schema workspace marker должен быть WORKSPACE-1", "error")
        if marker.get("kind") is not None and not isinstance(marker.get("kind"), str):
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "kind workspace marker должен быть строкой", "error")
        if marker.get("aggregate") is not None and not isinstance(marker.get("aggregate"), bool):
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "aggregate workspace marker должен быть boolean", "error")
        if marker.get("docs_path") is not None and not isinstance(marker.get("docs_path"), str):
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "docs_path workspace marker должен быть строкой", "error")
        if marker.get("queues") is not None and not isinstance(marker.get("queues"), list):
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "queues workspace marker должен быть array", "error")
        if not str(marker.get("workspace_id") or "").strip():
            return None, _warning("WORKSPACE_MANIFEST_INVALID", _rel(self.root, path),
                                  "workspace_id обязателен", "error")
        return marker, None

    def _discover(self):
        workspaces = []
        warnings = []
        root_marker, warning = self._read_marker(self.root, required=False)
        if warning:
            warnings.append(warning)
        if root_marker:
            workspaces.append((self.root, root_marker, "root"))

        # Explicit markers are the only accepted child-workspace discovery
        # rule. Queue .todone directories are never treated as workspaces.
        for folder, dirs, files in os.walk(self.root, topdown=True, followlinks=False):
            dirs[:] = sorted(dirs)
            for name in list(dirs):
                candidate = os.path.join(folder, name)
                if name in DEFAULT_EXCLUDES or name.startswith("."):
                    dirs.remove(name)
                    continue
                if os.path.islink(candidate):
                    warnings.append(_warning("SYMLINK_SKIPPED", _rel(self.root, candidate),
                                             "symlink не обходится без explicit policy"))
                    dirs.remove(name)
            if os.path.abspath(folder) == self.root:
                # The root .todone is project metadata, not a child.
                if ".todone" in dirs:
                    dirs.remove(".todone")
            marker_path = os.path.join(folder, ".todone", WORKSPACE_MARKER)
            if os.path.isfile(marker_path) and os.path.abspath(folder) != self.root:
                marker, item_warning = self._read_marker(folder, required=True)
                if item_warning:
                    warnings.append(item_warning)
                if marker:
                    workspaces.append((folder, marker, "declared"))
                # Do not descend into a child workspace twice. Nested declared
                # workspaces are still found when explicitly nested by walking
                # from their parent, so keep traversal deterministic.

            queues_path = os.path.join(folder, ".todone", QUEUE_REGISTRY)
            if os.path.isfile(queues_path) and os.path.abspath(folder) != self.root \
                    and not os.path.isfile(marker_path):
                warnings.append(_warning("WORKSPACE_MARKER_MISSING", _rel(self.root, folder),
                                         "queues.json найден без explicit workspace marker"))
        seen = {}
        unique = []
        for path, marker, source in sorted(workspaces, key=lambda item: _rel(self.root, item[0])):
            workspace_id = marker.get("workspace_id")
            if workspace_id in seen:
                warnings.append(_warning("WORKSPACE_ID_DUPLICATE", _rel(self.root, path),
                                         "workspace_id «%s» уже объявлен в %s" %
                                         (workspace_id, _rel(self.root, seen[workspace_id])), "error"))
                continue
            seen[workspace_id] = path
            unique.append((path, marker, source))
        return unique, warnings

    # ---- projections ---------------------------------------------------
    def _queue_entries(self, workspace_root, marker, warnings):
        registry_path = os.path.join(workspace_root, ".todone", QUEUE_REGISTRY)
        entries = []
        if os.path.isfile(registry_path):
            try:
                data = _json(registry_path)
                entries = [item for item in data.get("queues", []) if isinstance(item, dict)] \
                    if isinstance(data, dict) else []
            except (OSError, ValueError) as exc:
                warnings.append(_warning("QUEUE_REGISTRY_INVALID", _rel(self.root, registry_path),
                                         "реестр очередей не читается: %s" % exc, "error"))
        if not entries:
            tasks_root = os.path.join(workspace_root, "tasks")
            if os.path.isdir(tasks_root):
                for alias in sorted(os.listdir(tasks_root)):
                    candidate = os.path.join(tasks_root, alias)
                    if os.path.isfile(os.path.join(candidate, ".todone", "index.json")):
                        entries.append({"alias": alias, "path": candidate})
        result = []
        seen = set()
        for entry in entries:
            alias = _safe_id(entry.get("alias"), "queue")
            raw_path = entry.get("path") or os.path.join("tasks", alias)
            queue_path = raw_path if os.path.isabs(raw_path) else os.path.join(workspace_root, raw_path)
            token = (alias, os.path.abspath(queue_path))
            if token not in seen:
                result.append(token)
                seen.add(token)
        return sorted(result, key=lambda item: (item[0], item[1]))

    def _read_tasks(self, workspace_root, marker, warnings, aggregate_run_id=None,
                    captured_at=None):
        tasks = []
        queues = []
        invalid_sources = []
        workspace_id = marker.get("workspace_id")
        captured_at = captured_at or now_stamp()
        for alias, queue_path in self._queue_entries(workspace_root, marker, warnings):
            queue_rel = _rel(self.root, queue_path)
            within_workspace = _within(workspace_root, queue_path)
            if not within_workspace:
                warnings.append(_warning("QUEUE_PATH_OUTSIDE_WORKSPACE", queue_rel,
                                         "реестр очередей указывает за пределы workspace", "error"))
            queues.append({"global_ref": "%s:%s" % (workspace_id, alias),
                           "workspace_id": workspace_id, "alias": alias,
                           "source_root": _rel(self.root, workspace_root),
                           "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                           "source_path": queue_rel,
                           "source_fingerprint": sha256_file(os.path.join(queue_path, ".todone", "index.json")),
                           "source_status": "read" if os.path.isdir(queue_path) and within_workspace else "missing"})
            if not within_workspace:
                continue
            data_root = os.path.join(queue_path, ".todone", "data")
            if not os.path.isdir(data_root):
                code = "QUEUE_DATA_MISSING" if os.path.isdir(queue_path) else "QUEUE_MISSING"
                message = "у очереди нет data/" if os.path.isdir(queue_path) else "путь очереди не существует"
                warnings.append(_warning(code, _rel(self.root, data_root if os.path.isdir(queue_path) else queue_path),
                                         message))
                continue
            for folder in sorted(os.listdir(data_root)):
                record_dir = os.path.join(data_root, folder)
                if not os.path.isdir(record_dir) or folder.startswith("."):
                    continue
                path = os.path.join(record_dir, "task.json")
                rel_path = _rel(self.root, path)
                if not os.path.isfile(path):
                    warning = _warning("TASK_FILE_MISSING", _rel(self.root, record_dir),
                                       "папка записи без task.json")
                    warnings.append(warning)
                    invalid_sources.append({
                        "global_ref": "%s:%s:%s" % (workspace_id, alias, folder),
                        "workspace_id": workspace_id, "queue": alias,
                        "source_root": _rel(self.root, workspace_root),
                        "source_path": _rel(self.root, record_dir),
                        "source_fingerprint": None, "source_status": "missing",
                        "reason": warning["message"], "aggregate_run_id": aggregate_run_id,
                    })
                    continue
                fingerprint = sha256_file(path)
                try:
                    task = _json(path)
                    if not isinstance(task, dict):
                        raise ValueError("task.json должен быть object")
                except (OSError, ValueError) as exc:
                    warning = _warning("TASK_INVALID", rel_path,
                                       "task.json не читается: %s" % exc, "error")
                    warnings.append(warning)
                    invalid_sources.append({
                        "global_ref": "%s:%s:%s" % (workspace_id, alias, folder),
                        "workspace_id": workspace_id, "queue": alias,
                        "source_root": _rel(self.root, workspace_root),
                        "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                        "source_path": rel_path, "source_fingerprint": fingerprint,
                        "source_status": "invalid", "reason": str(exc),
                        "aggregate_run_id": aggregate_run_id,
                    })
                    continue
                local_id = _safe_id(task.get("id"), folder)
                global_ref = "%s:%s:%s" % (workspace_id, alias, local_id)
                tasks.append({
                    "global_ref": global_ref,
                    "workspace_id": workspace_id,
                    "queue": alias,
                    "local_id": local_id,
                    "source_root": _rel(self.root, workspace_root),
                    "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                    "source_queue": alias,
                    "source_local_id": local_id,
                    "source_file": rel_path,
                    "source_path": rel_path,
                    "source_fingerprint": fingerprint,
                    "captured_at": captured_at,
                    "aggregator_version": AGGREGATE_VERSION,
                    "aggregate_run_id": aggregate_run_id,
                    "source_revision": (task.get("source") or {}).get("revision")
                    if isinstance(task.get("source"), dict) else None,
                    "source_status": "read",
                    "task": task,
                })
        return queues, tasks, invalid_sources

    def _read_documents(self, workspace_root, marker, warnings, aggregate_run_id=None,
                         captured_at=None):
        workspace_id = marker.get("workspace_id")
        raw_docs_path = marker.get("docs_path") or "docs"
        docs_root = raw_docs_path if os.path.isabs(raw_docs_path) else os.path.join(workspace_root, raw_docs_path)
        documents, unknown = [], []
        captured_at = captured_at or now_stamp()
        if not _within(workspace_root, docs_root):
            warnings.append(_warning("DOCS_PATH_OUTSIDE_WORKSPACE", _rel(self.root, docs_root),
                                     "docs_path указывает за пределы workspace", "error"))
            return documents, unknown
        if not os.path.isdir(docs_root):
            return documents, unknown
        module_markdown = set()
        for folder, dirs, files in os.walk(docs_root, topdown=True, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in DEFAULT_EXCLUDES and not d.startswith("."))
            for name in sorted(files):
                if name.endswith(".module.json"):
                    module_markdown.add(os.path.abspath(os.path.join(folder, name[:-12] + ".md")))
        known_sidecars = {"manifest.json", "catalog.json"}
        for folder, dirs, files in os.walk(docs_root, topdown=True, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in DEFAULT_EXCLUDES and not d.startswith("."))
            for name in sorted(files):
                path = os.path.join(folder, name)
                if os.path.islink(path):
                    warnings.append(_warning("SYMLINK_SKIPPED", _rel(self.root, path),
                                             "symlink document не читается"))
                    continue
                rel_path = _rel(self.root, path)
                if name.endswith(".module.json"):
                    try:
                        module = _json(path)
                        if not isinstance(module, dict):
                            raise ValueError("module должен быть object")
                    except (OSError, ValueError) as exc:
                        warnings.append(_warning("DOCUMENT_INVALID", rel_path,
                                                 "module не читается: %s" % exc, "error"))
                        unknown.append({"workspace_id": workspace_id, "source_path": rel_path,
                                        "source_fingerprint": sha256_file(path),
                                        "media_type": "application/json", "size": os.path.getsize(path),
                                        "status": "invalid_document", "reason": str(exc),
                                        "aggregate_run_id": aggregate_run_id})
                        continue
                    doc_key = _safe_id(module.get("doc_key"), name[:-12])
                    documents.append({
                        "global_ref": "%s:%s" % (workspace_id, doc_key),
                        "workspace_id": workspace_id,
                        "source_root": _rel(self.root, workspace_root),
                        "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                        "doc_key": doc_key,
                        "doc_kind": module.get("doc_kind"),
                        "revision": module.get("revision"),
                        "status": module.get("status"),
                        "summary": module.get("summary"),
                        "source_file": rel_path,
                        "source_path": rel_path,
                        "markdown_path": _rel(self.root, os.path.join(folder, name[:-12] + ".md")),
                        "source_fingerprint": sha256_file(path),
                        "captured_at": captured_at,
                        "aggregator_version": AGGREGATE_VERSION,
                        "aggregate_run_id": aggregate_run_id,
                        "source_revision": module.get("revision"),
                        "source_task_refs": list(module.get("source_task_refs") or []),
                        "scope": module.get("scope") or {},
                        "module": module,
                    })
                elif name.endswith(".md") and os.path.abspath(path) in module_markdown:
                    # The module sidecar is canonical for metadata; markdown is
                    # linked from the document row instead of being double-listed.
                    continue
                elif name in known_sidecars or name.endswith((".machine.json", ".claims.json")):
                    continue
                else:
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        size = None
                    unknown.append({
                        "workspace_id": workspace_id,
                        "source_root": _rel(self.root, workspace_root),
                        "source_path": rel_path,
                        "source_fingerprint": sha256_file(path),
                        "media_type": _media_type(name),
                        "size": size,
                        "raw_reference": rel_path,
                        "status": "unknown_document",
                        "aggregate_run_id": aggregate_run_id,
                    })
        return documents, unknown

    def _relations(self, tasks, documents):
        task_map = {item["global_ref"]: item for item in tasks}
        local_map = {}
        for item in tasks:
            key = (item["workspace_id"], item["queue"], item["local_id"])
            local_map[key] = item["global_ref"]
        relations = []
        for item in tasks:
            task = item["task"]
            parent = task.get("parent")
            if parent:
                target = local_map.get((item["workspace_id"], item["queue"], str(parent)))
                relations.append({"kind": "parent", "from": item["global_ref"],
                                  "to": target or "%s:%s:%s" %
                                  (item["workspace_id"], item["queue"], parent),
                                  "resolved": target is not None})
            for dependency in task.get("depends_on") or []:
                target = local_map.get((item["workspace_id"], item["queue"], str(dependency)))
                relations.append({"kind": "depends_on", "from": item["global_ref"],
                                  "to": target or "%s:%s:%s" %
                                  (item["workspace_id"], item["queue"], dependency),
                                  "resolved": target is not None})
            for ref in task.get("refs") or []:
                if not isinstance(ref, dict):
                    continue
                if ref.get("kind") == "queue" and ref.get("path"):
                    target = local_map.get((item["workspace_id"], item["queue"], str(ref["path"])))
                    relations.append({"kind": "ref", "from": item["global_ref"],
                                      "to": target or str(ref["path"]), "resolved": target is not None,
                                      "source": ref})
        doc_map = {item["global_ref"]: item for item in documents}
        for doc in documents:
            for task_ref in doc.get("source_task_refs") or []:
                token = str(task_ref)
                target = None
                parts = token.split(":")
                if len(parts) == 3:
                    target = "%s:%s:%s" % (parts[0], parts[1], parts[2])
                elif len(parts) == 2:
                    target = "%s:%s:%s" % (doc["workspace_id"], parts[0], parts[1])
                relations.append({"kind": "documents", "from": doc["global_ref"],
                                  "to": target or token, "resolved": target in task_map if target else False})
        return relations

    def _entities(self, documents):
        entities = []
        for document in documents:
            if document.get("doc_kind") != "entity":
                continue
            key = document.get("doc_key") or "entity/unknown"
            name = key.split("/", 1)[-1]
            entities.append({"global_ref": "%s:entity/%s" % (document["workspace_id"], name),
                             "workspace_id": document["workspace_id"],
                             "entity_key": name, "status": document.get("status"),
                             "source_document": document["global_ref"],
                             "source_path": document["source_path"]})
        return entities

    # ---- public operations --------------------------------------------
    def read_only_scan(self):
        """Return the aggregate projection without writing any catalog files.

        Autodoc and other inspection tools need the same discovery/queue/doc
        semantics as the recursive aggregate but must not create a snapshot as
        a side effect of a read-only command.  The returned shape intentionally
        mirrors the persisted aggregate artifacts, minus volatile run metadata.
        """
        started = "read-only"
        workspaces, warnings = self._discover()
        rows = {"workspaces": [], "queues": [], "tasks": [], "documents": [],
                "entities": [], "relations": [], "warnings": list(warnings),
                "unknowns": [], "invalid_sources": []}
        for workspace_root, marker, discovery in workspaces:
            local_warnings = []
            local_queues, local_tasks, local_invalid = self._read_tasks(
                workspace_root, marker, local_warnings, "read-only", started)
            local_documents, local_unknowns = self._read_documents(
                workspace_root, marker, local_warnings, "read-only", started)
            rows["workspaces"].append({
                "workspace_id": marker.get("workspace_id"),
                "source_root": _rel(self.root, workspace_root),
                "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                "source_path": _rel(self.root, workspace_root),
                "marker_path": _rel(self.root, os.path.join(workspace_root, ".todone", WORKSPACE_MARKER)),
                "kind": marker.get("kind"), "parent": marker.get("parent"),
                "docs_path": marker.get("docs_path") or "docs",
                "discovery": discovery,
                "status": "partial" if local_warnings else "complete",
                "queue_count": len(local_queues), "task_count": len(local_tasks),
                "document_count": len(local_documents),
            })
            rows["queues"].extend(local_queues)
            rows["tasks"].extend(local_tasks)
            rows["documents"].extend(local_documents)
            rows["unknowns"].extend(local_unknowns)
            rows["invalid_sources"].extend(local_invalid)
            rows["warnings"].extend(local_warnings)
        for values, key in ((rows["workspaces"], "workspace_id"),
                            (rows["queues"], "global_ref"), (rows["tasks"], "global_ref"),
                            (rows["documents"], "global_ref"), (rows["unknowns"], "source_path"),
                            (rows["invalid_sources"], "source_path"), (rows["warnings"], "path")):
            values.sort(key=lambda item: str(item.get(key) or item.get("global_ref") or ""))
        rows["relations"] = self._relations(rows["tasks"], rows["documents"])
        rows["entities"] = self._entities(rows["documents"])
        rows["relations"].sort(key=lambda item: (item.get("from", ""), item.get("kind", ""), item.get("to", "")))
        rows["entities"].sort(key=lambda item: item.get("global_ref", ""))
        return rows

    def scan(self, archive=False):
        started = now_stamp()
        aggregate_run_id = run_id()
        workspaces, warnings = self._discover()
        workspace_rows, sources = [], []
        queues, tasks, documents, unknowns, invalid_sources = [], [], [], [], []
        for workspace_root, marker, discovery in workspaces:
            marker_path = os.path.join(workspace_root, ".todone", WORKSPACE_MARKER)
            source_row = {
                "workspace_id": marker.get("workspace_id"),
                "source_root": _rel(self.root, workspace_root),
                "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                "marker_path": _rel(self.root, marker_path),
                "marker_fingerprint": sha256_file(marker_path),
                "discovery": discovery,
            }
            if marker.get("aggregate") is False:
                source_row["status"] = "excluded"
                sources.append(source_row)
                workspace_rows.append({"workspace_id": marker.get("workspace_id"),
                                       "source_path": _rel(self.root, workspace_root),
                                       "marker_path": _rel(self.root, marker_path),
                                       "status": "excluded", "discovery": discovery})
                continue
            local_warnings = []
            local_queues, local_tasks, local_invalid = self._read_tasks(
                workspace_root, marker, local_warnings, aggregate_run_id, started)
            local_documents, local_unknowns = self._read_documents(
                workspace_root, marker, local_warnings, aggregate_run_id, started)
            warnings.extend(local_warnings)
            queues.extend(local_queues)
            tasks.extend(local_tasks)
            documents.extend(local_documents)
            unknowns.extend(local_unknowns)
            invalid_sources.extend(local_invalid)
            status = "partial" if local_warnings else "complete"
            source_row.update({"status": status, "warning_count": len(local_warnings),
                               "task_count": len(local_tasks), "document_count": len(local_documents)})
            sources.append(source_row)
            workspace_rows.append({
                "workspace_id": marker.get("workspace_id"),
                "source_root": _rel(self.root, workspace_root),
                "source_todone_path": _rel(self.root, os.path.join(workspace_root, ".todone")),
                "source_path": _rel(self.root, workspace_root),
                "marker_path": _rel(self.root, marker_path),
                "marker_fingerprint": sha256_file(marker_path),
                "kind": marker.get("kind"), "parent": marker.get("parent"),
                "docs_path": marker.get("docs_path") or "docs",
                "discovery": discovery, "status": status,
                "queue_count": len(local_queues), "task_count": len(local_tasks),
                "document_count": len(local_documents),
                "aggregate_run_id": aggregate_run_id,
                "aggregator_version": AGGREGATE_VERSION,
            })
        # Stable order is part of the generated catalog contract.  Timestamps
        # and run ids identify the snapshot; item ordering never depends on FS order.
        for values, key in ((workspace_rows, "workspace_id"), (sources, "workspace_id"),
                            (queues, "global_ref"), (tasks, "global_ref"),
                            (documents, "global_ref"), (unknowns, "source_path"),
                            (invalid_sources, "source_path"), (warnings, "path")):
            values.sort(key=lambda item: str(item.get(key) or item.get("global_ref") or ""))
        relations = self._relations(tasks, documents)
        entities = self._entities(documents)
        relations.sort(key=lambda item: (item.get("from", ""), item.get("kind", ""), item.get("to", "")))
        entities.sort(key=lambda item: item.get("global_ref", ""))
        complete = len([item for item in workspace_rows if item.get("status") == "complete"])
        partial = len([item for item in workspace_rows if item.get("status") == "partial"])
        failed = len([item for item in warnings if item.get("severity") == "error"])
        manifest = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "schema": AGGREGATE_SCHEMA,
            "aggregate_run_id": aggregate_run_id,
            "root_workspace_id": workspaces[0][1].get("workspace_id") if workspaces else os.path.basename(self.root),
            "root_path": self.root,
            "started_at": started, "finished_at": now_stamp(),
            "aggregator_version": AGGREGATE_VERSION,
            "contract_version": AGGREGATE_SCHEMA,
            "discovery": {"mode": "explicit-child-markers", "root": _rel(self.root, self.root),
                          "excluded_names": sorted(DEFAULT_EXCLUDES)},
            "completeness": {"status": "complete" if not warnings else "partial",
                             "workspace_count": len(workspace_rows), "complete_count": complete,
                             "partial_count": partial, "failed_count": failed,
                             "unknown_count": len(unknowns), "invalid_source_count": len(invalid_sources)},
            "counts": {"workspaces": len(workspace_rows), "queues": len(queues),
                       "tasks": len(tasks), "documents": len(documents),
                       "entities": len(entities), "relations": len(relations),
                       "warnings": len(warnings), "unknown_documents": len(unknowns),
                       "invalid_sources": len(invalid_sources)},
            "sources": sources, "outputs": [], "warnings": warnings, "unknowns": unknowns,
            "invalid_sources": invalid_sources,
        }
        artifacts = {"workspaces": workspace_rows, "queues": queues, "tasks": tasks,
                     "documents": documents, "entities": entities, "relations": relations,
                     "warnings": warnings, "unknowns": unknowns,
                     "invalid_sources": invalid_sources}
        snapshot_path = os.path.join(self.output, "snapshots", aggregate_run_id)
        manifest["snapshot_path"] = _rel(self.root, snapshot_path)
        os.makedirs(snapshot_path, exist_ok=True)
        if archive:
            self._archive_sources(os.path.join(snapshot_path, "archive"),
                                  tasks, documents, unknowns)
        filenames = {"manifest": "manifest.json", **{key: "%s.json" % key for key in artifacts}}
        # Write catalog files first.  The manifest lists their fingerprints; it
        # intentionally does not list its own hash because that would be cyclic.
        for key, filename in filenames.items():
            if key == "manifest":
                continue
            path = os.path.join(snapshot_path, filename)
            _write_json(path, artifacts[key])
            manifest["outputs"].append({"path": _rel(self.root, path),
                                        "sha256": sha256_file(path)})
        _write_json(os.path.join(snapshot_path, "manifest.json"), manifest)
        os.makedirs(self.output, exist_ok=True)
        for key, filename in filenames.items():
            source = os.path.join(snapshot_path, filename)
            target = os.path.join(self.output, filename)
            _write_json(target, _json(source))
        _write_json(os.path.join(self.output, "latest.json"), manifest)
        return {"manifest": manifest, **artifacts}

    def _archive_sources(self, archive_root, tasks, documents, unknowns=None):
        for item in list(tasks) + list(documents) + list(unknowns or []):
            source = os.path.join(self.root, item.get("source_path") or "")
            if not os.path.isfile(source):
                continue
            ref = item.get("global_ref") or item.get("source_path") or "unknown"
            destination = os.path.join(archive_root, ref.replace(":", "__"),
                                       os.path.basename(source))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)

    def _require_manifest(self):
        path = os.path.join(self.output, "manifest.json")
        if not os.path.isfile(path):
            raise SkillError("AGGREGATE_MISSING", "aggregate catalog ещё не построен", path,
                             command="tcheck aggregate scan --root <root>")
        try:
            payload = _json(path)
        except (OSError, ValueError) as exc:
            raise SkillError("AGGREGATE_INVALID", "aggregate manifest не читается: %s" % exc, path)
        issues = validate_aggregate_manifest(payload, path)
        if any(item.is_error for item in issues):
            first = issues[0]
            raise SkillError(first.code, first.message, first.where)
        return payload

    def status(self):
        return self._require_manifest()

    def _catalog(self, kind):
        allowed = {"tasks", "documents", "workspaces", "queues", "entities",
                   "relations", "warnings", "unknowns", "invalid_sources"}
        if kind not in allowed:
            raise SkillError("AGGREGATE_KIND_UNKNOWN", "вид aggregate catalog неизвестен: %s" % kind,
                             kind, command="tcheck aggregate list --kind tasks --root <root>")
        self._require_manifest()
        filename = os.path.join(self.output, "%s.json" % kind)
        if not os.path.isfile(filename):
            return []
        try:
            value = _json(filename)
        except (OSError, ValueError) as exc:
            raise SkillError("AGGREGATE_INVALID", "catalog %s не читается: %s" % (kind, exc), filename)
        return value if isinstance(value, list) else []

    def listing(self, kind="tasks", workspace=None, limit=None):
        values = self._catalog(kind)
        if workspace:
            values = [item for item in values if item.get("workspace_id") == workspace]
        if limit is not None:
            values = values[:max(0, int(limit))]
        return values

    def show(self, reference):
        labels = {"workspaces": "workspace", "queues": "queue", "tasks": "task",
                  "documents": "document", "entities": "entity"}
        for kind in labels:
            for item in self._catalog(kind):
                if item.get("global_ref") == reference or item.get("workspace_id") == reference:
                    return {"kind": labels[kind], "item": item}
        raise SkillError("AGGREGATE_REF_UNKNOWN", "aggregate ref не найден: %s" % reference,
                         reference, command="tcheck aggregate list --root <root>")

    def verify(self):
        manifest = self._require_manifest()
        stale = []
        for kind in ("tasks", "documents"):
            for item in self._catalog(kind):
                path = os.path.join(self.root, item.get("source_path") or "")
                actual = sha256_file(path)
                if actual != item.get("source_fingerprint"):
                    stale.append({"global_ref": item.get("global_ref"),
                                  "source_path": item.get("source_path"),
                                  "expected": item.get("source_fingerprint"),
                                  "actual": actual})
        return {"aggregate_run_id": manifest["aggregate_run_id"], "stale": stale,
                "valid": not stale, "checked": sum(len(self._catalog(kind)) for kind in ("tasks", "documents"))}

    def _snapshot(self, aggregate_run_id):
        path = os.path.join(self.output, "snapshots", aggregate_run_id)
        if not os.path.isdir(path):
            raise SkillError("AGGREGATE_RUN_UNKNOWN", "aggregate run не найден: %s" % aggregate_run_id, path)
        return path

    def diff(self, from_run=None, to_run=None):
        current = self._require_manifest()
        to_run = to_run or current.get("aggregate_run_id")
        snapshots = sorted(os.listdir(os.path.join(self.output, "snapshots"))) \
            if os.path.isdir(os.path.join(self.output, "snapshots")) else []
        if from_run is None:
            previous = [item for item in snapshots if item < to_run]
            from_run = previous[-1] if previous else None
        if not from_run:
            return {"from_run": None, "to_run": to_run, "added": [], "removed": [], "changed": []}
        from_path = self._snapshot(from_run)
        to_path = self._snapshot(to_run)
        old = {item.get("global_ref"): item for item in _json(os.path.join(from_path, "tasks.json"))}
        old.update({item.get("global_ref"): item for item in _json(os.path.join(from_path, "documents.json"))})
        new = {item.get("global_ref"): item for item in _json(os.path.join(to_path, "tasks.json"))}
        new.update({item.get("global_ref"): item for item in _json(os.path.join(to_path, "documents.json"))})
        added = sorted(set(new) - set(old)); removed = sorted(set(old) - set(new))
        changed = sorted(ref for ref in set(old).intersection(new)
                         if old[ref].get("source_fingerprint") != new[ref].get("source_fingerprint"))
        return {"from_run": from_run, "to_run": to_run, "added": added,
                "removed": removed, "changed": changed}

    def rebuild(self, aggregate_run_id=None):
        manifest = self._require_manifest()
        aggregate_run_id = aggregate_run_id or manifest.get("aggregate_run_id")
        source = self._snapshot(aggregate_run_id)
        for filename in ("manifest.json", "workspaces.json", "queues.json", "tasks.json",
                         "documents.json", "entities.json", "relations.json", "warnings.json",
                         "unknowns.json", "invalid_sources.json"):
            path = os.path.join(source, filename)
            if os.path.isfile(path):
                _write_json(os.path.join(self.output, filename), _json(path))
        _write_json(os.path.join(self.output, "latest.json"), _json(os.path.join(source, "manifest.json")))
        return _json(os.path.join(source, "manifest.json"))

    def export(self, output_path=None):
        manifest = self._require_manifest()
        bundle = {"manifest": manifest, "sources": manifest.get("sources", [])}
        for kind in ("workspaces", "queues", "tasks", "documents", "entities", "relations",
                     "warnings", "unknowns", "invalid_sources"):
            bundle[kind] = self._catalog(kind)
        output_path = output_path or os.path.join(self.output, "export.json")
        _write_json(output_path, bundle)
        return {"path": output_path, "sha256": sha256_file(output_path),
                "aggregate_run_id": manifest["aggregate_run_id"]}
