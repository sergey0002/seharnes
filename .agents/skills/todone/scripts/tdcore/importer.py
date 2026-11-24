"""Local external import profiles.

The importer is local-first: the exact UTF-8 input is retained in the generic
mirror ``source.raw`` and in immutable per-revision artifacts.  Jira uses a
provider profile to build a structured projection, but the projection never
replaces the raw snapshot and never changes the local task lifecycle/status.
There is deliberately no network client in this module.
"""

import copy
import hashlib
import json
import os
import shutil

from .errors import Issue, SkillError
from .queue import Queue
from .record import now_stamp

JIRA_MIRROR_SCHEMA = "JIRA-MIRROR-1"
JIRA_PROFILE = "jira-cloud-rest-v3-local"
JIRA_MIRROR_KEYS = (
    "$schema", "schema", "profile", "revision", "provenance", "raw",
    "external", "normalized", "fields", "comments", "custom_fields",
    "dates", "attachments", "links", "relations", "worklogs", "changelog",
    "properties", "unknown_fields", "completeness",
)

# Jira system fields with a stable structured projection.  The complete field
# object is still retained under ``fields`` and the complete parsed document
# under ``raw``; this list only controls the unknown-field report.
KNOWN_JIRA_FIELDS = {
    "summary", "description", "environment", "project", "issuetype", "issueType",
    "status", "priority", "assignee", "reporter", "creator", "labels", "components",
    "fixVersions", "versions", "parent", "subtasks", "attachment", "attachments",
    "issuelinks", "issueLinks", "comment", "worklog", "worklogs", "timetracking",
    "votes", "watches", "watcher", "security", "progress", "resolution",
    "resolutiondate", "created", "updated", "duedate", "statuscategorychangedate",
    "lastViewed", "aggregateprogress", "aggregatetimeestimate",
    "aggregatetimeoriginalestimate", "aggregatetimespent", "timeestimate",
    "timeoriginalestimate", "timespent", "components", "fixVersions",
}

RESOURCE_NAMES = (
    "comments", "changelog", "worklogs", "attachments", "links", "remote_links",
    "properties", "project_versions", "custom_fields",
)


class ExternalComment:
    """Комментарий внешней системы с raw body для projection и идемпотенции."""

    def __init__(self, external_id, at, by, text, raw=None, body_raw=None,
                 updated_at=None, update_author=None, visibility=None,
                 properties=None, body_format="plain"):
        self.external_id = str(external_id) if external_id is not None else None
        self.at = at or (("external:%s" % self.external_id)
                         if self.external_id is not None else now_stamp())
        self.by = by or "external"
        self.text = str(text or "")
        self.raw = raw
        self.body_raw = body_raw
        self.updated_at = updated_at
        self.update_author = update_author
        self.visibility = visibility
        self.properties = properties
        self.body_format = body_format

    def fingerprint(self):
        """Stable comparison key; provider id wins over rendered text."""
        return (self.external_id, self.updated_at or self.at, self.text)

    def as_record_comment(self):
        item = {"at": self.at, "by": self.by, "kind": "import",
                "text": self.text}
        if self.external_id is not None:
            item["external_id"] = self.external_id
        return item

    def as_projection(self):
        return {
            "external_id": self.external_id,
            "created": self.at,
            "updated": self.updated_at,
            "author": self.by,
            "update_author": self.update_author,
            "visibility": self.visibility,
            "body_format": self.body_format,
            "body_raw": self.body_raw,
            "body_text": self.text,
            "properties": self.properties,
            "raw": self.raw,
        }


class ExternalPayload:
    """Нормализованная мета внешнего файла плюс дословный вход."""

    def __init__(self, system, raw, external_id, title, url=None, comments=None,
                 projection=None, completeness=None):
        self.system = system
        self.raw = raw
        self.external_id = str(external_id) if external_id is not None else None
        self.title = title or "%s %s" % (system, self.external_id or "без id")
        self.url = url
        self.comments = comments or []
        self.projection = projection
        self.completeness = completeness


def read_payload(system, path, external_id=None, title=None):
    """Прочитать файл: ``raw`` остаётся исходным UTF-8 текстом целиком."""
    if not os.path.isfile(path):
        raise SkillError("RECORD_NOT_FOUND", "файла внешней системы «%s» нет" % path,
                         path, command="tcheck import %s --file <путь> --by <имя>"
                         % system)
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except (OSError, UnicodeError) as exc:
        raise SkillError("SOURCE_RAW_MISSING",
                         "сырой вход не прочитать: %s" % exc, path,
                         command="tcheck import %s --file <путь> --by <имя>" % system)
    payload_data = _json_meta(raw, path)
    external_id = external_id or _first(payload_data, "id", "key", "issue_id")
    title = title or _title(payload_data)
    url = _first(payload_data, "url", "self", "html_url")
    comments = _comments(payload_data)
    projection = None
    completeness = None
    if system == "jira":
        projection, completeness = jira_projection(payload_data, path, raw=raw)
        issues = validate_jira_projection(projection, path)
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where,
                             command="tcheck import jira --file <путь> --by <имя>")
    if external_id is None:
        # A file-only import still needs stable source identity.
        external_id = os.path.basename(path)
    return ExternalPayload(system, raw, external_id, title, url, comments,
                           projection=projection, completeness=completeness)


def import_payload(queue, payload, by):
    """Create/update a mirror and persist the profile projection losslessly.

    Profile artifacts and the generic mirror are one local transaction from the
    caller's perspective.  A failed artifact write or queue/index write restores
    the pre-import record, index and artifact tree; a failed first import does
    not leave an empty mirror behind.
    """
    if not by:
        raise SkillError("ASK_USER", "импорт без имени того, кто его выполнил",
                         "tcheck import", command="tcheck import jira --file <путь> "
                                                 "--by <имя>")
    if payload.system == "jira" and payload.projection is not None:
        issues = validate_jira_projection(payload.projection)
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where,
                             command="tcheck import jira --file <путь> --by <имя>")

    existing = _find_mirror(queue, payload.system, payload.external_id)
    before_folders = set(queue.store.names())
    before_index_bytes = _read_bytes(queue.index_path)
    before_index_items = copy.deepcopy(queue.index.items)
    before_folder = _snapshot_tree(existing.folder) if existing is not None else None
    record = None
    new_comments, updated_comments = [], []
    try:
        if existing is None:
            revision = 1
            source = {
                "system": payload.system, "id": payload.external_id,
                "url": payload.url, "imported_at": now_stamp(), "by": by,
                "raw": payload.raw, "revision": revision,
            }
            record = queue.create(payload.title, "mirror", status="mirror",
                                  source=source)
            for comment in payload.comments:
                item = _append_import(record, comment)
                new_comments.append(item)
            reason = "первичная загрузка"
        else:
            record = existing
            old_comments = {
                str(item.get("external_id")): item
                for item in record.comments
                if item.get("kind") == "import" and item.get("external_id") is not None
            }
            old_fingerprints = {
                (item.get("external_id"), item.get("at"), item.get("by"), item.get("text"))
                for item in record.comments if item.get("kind") == "import"
            }
            for comment in payload.comments:
                old = old_comments.get(str(comment.external_id)) if comment.external_id is not None else None
                if old is not None:
                    current = comment.as_record_comment()
                    same = (old.get("external_id"), old.get("at"), old.get("by"), old.get("text")) == (
                        current.get("external_id"), current.get("at"), current.get("by"), current.get("text"))
                    if same:
                        continue
                    # A provider update changes the imported representation in
                    # place; it must not create a duplicate local comment.
                    old.update({"at": comment.at, "by": comment.by, "text": comment.text})
                    updated_comments.append(old)
                    continue
                if comment.fingerprint() not in old_fingerprints:
                    new_comments.append(_append_import(record, comment))
            source = record.data.setdefault("source", {})
            revision = int(source.get("revision") or 0) + 1
            source.update({"system": payload.system, "id": payload.external_id,
                           "url": payload.url, "imported_at": now_stamp(), "by": by,
                           "raw": payload.raw, "revision": revision})
            reason = "повторный импорт"

        profile_files = _persist_profile(record, payload, revision)
        queue.save(record)
    except Exception:
        _rollback_import(queue, existing, record, before_folders,
                         before_index_bytes, before_index_items, before_folder)
        raise

    commands = [
        "ttask new «Формализация стадии: %s» --type intake --parent %s --by <имя>"
        % (record.title, record.id)
    ] if existing is None else []
    commands.extend(
        "ttask new «Комментарий %s: %s» --type intake --parent %s --by <имя>"
        % (item.get("external_id") or item.get("id"),
           _one_line(item.get("text")), record.id)
        for item in new_comments
    )
    return {
        "record": record, "created": existing is None, "reason": reason,
        "revision": revision, "new_comments": new_comments,
        "updated_comments": updated_comments, "draft_commands": commands,
        "profile_files": profile_files, "completeness": payload.completeness,
    }


def _persist_profile(record, payload, revision):
    """Write profile artifacts without changing TASK/SOURCE schema."""
    if payload.system != "jira" or payload.projection is None:
        return []
    projection = copy.deepcopy(payload.projection)
    completeness = copy.deepcopy(payload.completeness or projection.get("completeness") or {})
    imported_at = now_stamp()
    projection["revision"] = revision
    projection.setdefault("provenance", {})["mirror_record_id"] = record.id
    projection["provenance"]["import_revision"] = revision
    projection["provenance"]["imported_at"] = imported_at
    projection["completeness"]["import_revision"] = revision
    projection["completeness"]["mirror_record_id"] = record.id
    projection["completeness"]["imported_at"] = imported_at
    completeness["import_revision"] = revision
    completeness["mirror_record_id"] = record.id
    completeness["imported_at"] = imported_at
    payload.completeness = completeness
    issues = validate_jira_projection(projection)
    if any(item.is_error for item in issues):
        first = next(item for item in issues if item.is_error)
        raise SkillError(first.code, first.message, first.where)

    folder = os.path.join(record.folder, "artifacts")
    snapshot_folder = os.path.join(folder, "jira-snapshots")
    os.makedirs(snapshot_folder, exist_ok=True)
    files = []
    # Exact raw snapshot per revision prevents a later refresh from erasing the
    # previous provider payload.  The source.raw field remains the current raw.
    raw_relative = "artifacts/jira-snapshots/revision-%03d.json" % revision
    raw_path = os.path.join(record.folder, raw_relative)
    _atomic_text(raw_path, payload.raw)
    _ensure_artifact(record, "spec", raw_relative,
                     "exact Jira UTF-8 snapshot for source revision %d" % revision)
    files.append(raw_relative)

    for name, value, kind, note in (
        ("jira-projection.json", projection, "spec",
         "JIRA-MIRROR-1 structured projection; source.raw remains canonical current input"),
        ("jira-completeness.json", completeness, "report",
         "Jira snapshot completeness, provenance and unknown/custom-field report"),
    ):
        path = os.path.join(folder, name)
        _atomic_json(path, value)
        relative = "artifacts/" + name
        _ensure_artifact(record, kind, relative, note)
        files.append(relative)

    # Generic mirror task keeps only a bounded normalized projection. Provider
    # raw/ADF/history remain in artifacts/source.raw and are never treated as a
    # local lifecycle status or local ownership value.
    record.extra["external"] = {
        "profile": JIRA_PROFILE,
        "system": "jira",
        "schema": JIRA_MIRROR_SCHEMA,
        "revision": revision,
        "identity": copy.deepcopy(projection["external"]),
        "normalized": copy.deepcopy(projection["normalized"]),
        "dates": copy.deepcopy(projection["dates"]),
        "relations": copy.deepcopy(projection["relations"]),
        "completeness": copy.deepcopy(projection["completeness"]),
    }
    return files


def _ensure_artifact(record, kind, path, note):
    found = next((item for item in record.artifacts
                  if isinstance(item, dict) and item.get("path") == path), None)
    if found is None:
        record.artifacts.append({"kind": kind, "derived": False,
                                 "path": path, "note": note})
    else:
        found.update({"kind": kind, "derived": False, "note": note})


def _atomic_json(path, value):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _atomic_text(path, value):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _snapshot_tree(folder):
    """Capture a record folder for rollback without interpreting its JSON."""
    if not folder or not os.path.isdir(folder):
        return {}
    snapshot = {}
    for base, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(base, name)
            data = _read_bytes(path)
            if data is not None:
                snapshot[os.path.relpath(path, folder)] = data
    return snapshot


def _restore_file(path, data):
    if data is None:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".rollback.tmp"
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _restore_tree(folder, snapshot):
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    for base, dirs, files in os.walk(folder, topdown=False):
        for name in files:
            path = os.path.join(base, name)
            relative = os.path.relpath(path, folder)
            if relative not in snapshot:
                try:
                    os.remove(path)
                except OSError:
                    pass
        for name in dirs:
            path = os.path.join(base, name)
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except OSError:
                pass
    for relative, data in snapshot.items():
        _restore_file(os.path.join(folder, relative), data)


def _rollback_import(queue, existing, record, before_folders,
                     before_index_bytes, before_index_items, before_folder):
    """Best-effort restoration after a failed mirror/profile transaction."""
    current_folders = set(queue.store.names())
    for name in sorted(current_folders - before_folders):
        shutil.rmtree(os.path.join(queue.store.data_dir, name), ignore_errors=True)
    if existing is not None:
        _restore_tree(existing.folder, before_folder or {})
    queue.index.items = copy.deepcopy(before_index_items)
    _restore_file(queue.index_path, before_index_bytes)
    # Do not leave temporary files from a failed atomic write in either domain.
    for base in (queue.store.data_dir, existing.folder if existing is not None else None):
        if not base or not os.path.isdir(base):
            continue
        for folder, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith((".tmp", ".rollback.tmp")):
                    try:
                        os.remove(os.path.join(folder, name))
                    except OSError:
                        pass


def _find_mirror(queue, system, external_id):
    for record in queue.records:
        source = record.source or {}
        if record.kind == "mirror" and source.get("system") == system \
                and str(source.get("id")) == str(external_id):
            return record
    return None


def _append_import(record, comment):
    item = comment.as_record_comment()
    item["id"] = "C-%d" % (len(record.comments) + 1)
    record.comments.append(item)
    return item


def _json_meta(raw, path):
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _first(data, *keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _title(data):
    fields = data.get("fields") if isinstance(data, dict) else None
    return _first(data, "title", "summary", "name") or _first(fields or {}, "summary", "title")


def _sha256_text(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def adf_to_text(value):
    """Deterministic plain-text projection for Jira ADF/string bodies."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "".join(adf_to_text(item) for item in value)
    if not isinstance(value, dict):
        return str(value)
    if value.get("type") == "hardBreak":
        return "\n"
    if value.get("type") == "emoji":
        attrs = value.get("attrs") or {}
        return ":%s:" % (attrs.get("shortName") or attrs.get("text") or "emoji")
    if value.get("type") == "mention":
        attrs = value.get("attrs") or {}
        mention = str(attrs.get("text") or attrs.get("displayName") or attrs.get("id") or "mention")
        return mention if mention.startswith("@") else "@%s" % mention
    if value.get("type") in ("media", "mediaSingle"):
        return "[media]"
    if value.get("type") == "inlineCard":
        attrs = value.get("attrs") or {}
        return str(attrs.get("url") or "[card]")
    if "text" in value:
        return str(value.get("text") or "")
    return adf_to_text(value.get("content") or value.get("value") or "")


def _author(value):
    if isinstance(value, dict):
        return (value.get("displayName") or value.get("name") or
                value.get("accountId") or value.get("key") or "external")
    return value or "external"


def _identity(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        return {"display_name": str(value), "raw": value}
    return {
        "id": value.get("accountId") or value.get("id") or value.get("key"),
        "key": value.get("key"),
        "display_name": value.get("displayName") or value.get("name"),
        "active": value.get("active"),
        "raw": value,
    }


def _date_value(value):
    """Keep raw Jira timestamp and expose a stable ISO-ish normalized value."""
    if value is None:
        return None
    text = str(value)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return {"raw": text, "value": text, "precision": "date"}
    # Jira commonly emits +0000 or +01:00.  Avoid timezone libraries while
    # producing a deterministic representation for the common UTC form.
    normalized = text
    if normalized.endswith("+0000"):
        normalized = normalized[:-5] + "Z"
    elif normalized.endswith("+00:00"):
        normalized = normalized[:-6] + "Z"
    return {"raw": text, "value": normalized, "precision": "datetime"}


def _date_map(fields):
    keys = ("created", "updated", "resolutiondate", "duedate", "statuscategorychangedate",
            "lastViewed")
    return {key: _date_value(fields.get(key)) for key in keys if fields.get(key) is not None}


def _version(value, project_id=None):
    if not isinstance(value, dict):
        return {"id": None, "name": str(value), "project_id": project_id,
                "release_ref": None, "raw": value}
    version_id = value.get("id")
    project = value.get("projectId") or value.get("project_id") or project_id
    return {"id": version_id, "name": value.get("name"), "project_id": project,
            "release_ref": ("jira:%s:%s" % (project, version_id)
                            if project and version_id else None),
            "raw": value}


def _versions(values, project_id=None):
    if not isinstance(values, list):
        return []
    return [_version(value, project_id) for value in values]


def _comment_block(data):
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("comments"), list):
        return data
    fields = data.get("fields") or {}
    block = fields.get("comment") if isinstance(fields, dict) else None
    return block if isinstance(block, dict) else None


def _comments(data):
    block = _comment_block(data)
    candidates = block.get("comments") if block else None
    if not isinstance(candidates, list):
        candidates = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        return []
    result = []
    for pos, item in enumerate(candidates, start=1):
        if isinstance(item, str):
            result.append(ExternalComment(pos, None, "external", item, raw=item,
                                          body_raw=item, body_format="plain"))
            continue
        if not isinstance(item, dict):
            continue
        author_value = item.get("author") or item.get("author_display_name") or item.get("by")
        update_author = _author(item.get("updateAuthor")) if item.get("updateAuthor") else None
        body = item.get("body") if "body" in item else item.get("text")
        fmt = "adf" if isinstance(body, (dict, list)) else "plain"
        result.append(ExternalComment(
            item.get("id") or pos,
            item.get("created") or item.get("at"),
            _author(author_value),
            adf_to_text(body),
            raw=item,
            body_raw=body,
            updated_at=item.get("updated"),
            update_author=update_author,
            visibility=item.get("visibility"),
            properties=item.get("properties"),
            body_format=fmt,
        ))
    return result


def _attachments(fields, data):
    values = fields.get("attachment")
    if values is None:
        values = fields.get("attachments")
    if values is None:
        values = data.get("attachments") if isinstance(data, dict) else None
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, dict):
            result.append({"id": None, "filename": str(value), "raw": value})
            continue
        result.append({
            "id": value.get("id"), "filename": value.get("filename"),
            "mime_type": value.get("mimeType") or value.get("mime_type"),
            "size": value.get("size"), "created": _date_value(value.get("created")),
            "author": _identity(value.get("author")),
            "url": value.get("content") or value.get("url"),
            "thumbnail": value.get("thumbnail"),
            "content_saved": bool(value.get("content_bytes") or value.get("local_path")),
            "raw": value,
        })
    return result


def _issue_links(fields, data):
    values = fields.get("issuelinks")
    if values is None:
        values = fields.get("issueLinks")
    if values is None:
        values = data.get("issuelinks") if isinstance(data, dict) else None
    if not isinstance(values, list):
        values = []
    result = []
    for value in values:
        if not isinstance(value, dict):
            result.append({"id": None, "raw": value})
            continue
        link_type = value.get("type") or {}
        direction = "outward" if value.get("outwardIssue") is not None else "inward"
        issue = value.get("outwardIssue") or value.get("inwardIssue") or {}
        result.append({"id": value.get("id"), "direction": direction,
                       "type": link_type, "issue": {
                           "id": issue.get("id") if isinstance(issue, dict) else None,
                           "key": issue.get("key") if isinstance(issue, dict) else None,
                           "self": issue.get("self") if isinstance(issue, dict) else None,
                       }, "raw": value})
    remote = data.get("remoteLinks") if isinstance(data, dict) else None
    if remote is None and isinstance(data, dict):
        remote = data.get("remotelinks")
    remote_result = []
    if isinstance(remote, list):
        for value in remote:
            remote_result.append({
                "id": value.get("id") if isinstance(value, dict) else None,
                "global_id": value.get("globalId") if isinstance(value, dict) else None,
                "relationship": value.get("relationship") if isinstance(value, dict) else None,
                "object": value.get("object") if isinstance(value, dict) else None,
                "raw": value,
            })
    return result, remote_result


def _resource_source(data, key):
    """Return an explicitly supplied completeness state, if any."""
    sources = []
    if isinstance(data, dict):
        sources.extend([data.get("completeness"), data.get("_completeness")])
        snapshot = data.get("snapshot")
        if isinstance(snapshot, dict):
            sources.append(snapshot.get("completeness"))
    for source in sources:
        if not isinstance(source, dict):
            continue
        item = source.get(key)
        if isinstance(item, str):
            return {"state": item}
        if isinstance(item, dict):
            return copy.deepcopy(item)
    return None


def _resource_state(data, key, present, count=None, metadata_only=False):
    explicit = _resource_source(data, key)
    if explicit:
        result = explicit
        result.setdefault("state", "partial" if present else "not_requested")
    elif not present:
        # A file importer cannot infer permission from omission.  `not_requested`
        # is explicit and honest; API adapters may override it in a manifest.
        result = {"state": "not_requested"}
    elif metadata_only:
        result = {"state": "metadata_only"}
    else:
        result = {"state": "complete"}
    result["present"] = bool(present)
    if count is not None:
        result["items"] = count
    return result


def jira_projection(data, path="jira.json", raw=None, revision=1):
    """Build a lossless, structured Jira local-snapshot projection."""
    if not isinstance(data, dict):
        data = {"raw_value": data}
    fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    comments = _comments(data)
    custom_fields = {key: value for key, value in fields.items()
                     if str(key).startswith("customfield_")}
    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    project_id = project.get("id") or project.get("projectId")
    issue_links, remote_links = _issue_links(fields, data)
    attachments = _attachments(fields, data)
    worklog_value = fields.get("worklog")
    if worklog_value is None:
        worklog_value = data.get("worklogs")
    changelog = data.get("changelog")
    properties = data.get("properties")
    known_top = {"id", "key", "self", "url", "html_url", "fields", "comments",
                 "changelog", "properties", "attachments", "remoteLinks", "remotelinks",
                 "worklogs", "snapshot", "completeness", "_completeness"}
    unknown_fields = {
        "top_level": {key: value for key, value in data.items() if key not in known_top},
        "fields": {key: value for key, value in fields.items()
                   if key not in KNOWN_JIRA_FIELDS and not str(key).startswith("customfield_")},
    }
    dates = _date_map(fields)
    description = fields.get("description")
    environment = fields.get("environment")
    normalized = {
        "id": data.get("id"), "key": data.get("key") or data.get("issue_id"),
        "url": data.get("self") or data.get("url") or data.get("html_url"),
        "project": _identity(project), "issue_type": _identity(fields.get("issuetype") or fields.get("issueType")),
        "status": copy.deepcopy(fields.get("status")),
        "status_category": ((fields.get("status") or {}).get("statusCategory")
                             if isinstance(fields.get("status"), dict) else None),
        "priority": copy.deepcopy(fields.get("priority")),
        "assignee": _identity(fields.get("assignee")),
        "reporter": _identity(fields.get("reporter")),
        "creator": _identity(fields.get("creator")),
        "summary": fields.get("summary"),
        "description": {"format": "adf" if isinstance(description, (dict, list)) else "plain",
                        "raw": description, "text": adf_to_text(description)},
        "environment": {"format": "adf" if isinstance(environment, (dict, list)) else "plain",
                        "raw": environment, "text": adf_to_text(environment)},
        "labels": list(fields.get("labels") or []),
        "components": [copy.deepcopy(item) for item in (fields.get("components") or [])]
            if isinstance(fields.get("components"), list) else fields.get("components"),
        "fix_versions": _versions(fields.get("fixVersions"), project_id),
        "affected_versions": _versions(fields.get("versions"), project_id),
        "parent": copy.deepcopy(fields.get("parent")),
        "resolution": copy.deepcopy(fields.get("resolution")),
        "dates": dates,
    }
    present = {
        "comments": bool(_comment_block(data) is not None or data.get("comments") is not None),
        "changelog": changelog is not None,
        "worklogs": worklog_value is not None,
        "attachments": ("attachment" in fields or "attachments" in fields or "attachments" in data),
        "links": bool(fields.get("issuelinks") is not None or fields.get("issueLinks") is not None
                   or data.get("issuelinks") is not None),
        "remote_links": data.get("remoteLinks") is not None or data.get("remotelinks") is not None,
        "properties": properties is not None,
        "project_versions": (data.get("project_versions") is not None
                              or data.get("versions_registry") is not None),
        "custom_fields": bool(custom_fields),
    }
    resource_values = {
        "comments": comments, "changelog": changelog, "worklogs": worklog_value,
        "attachments": attachments, "links": issue_links, "remote_links": remote_links,
        "properties": properties, "project_versions": data.get("project_versions")
            or data.get("versions_registry"), "custom_fields": custom_fields,
    }
    resources = {}
    for name in RESOURCE_NAMES:
        value = resource_values[name]
        metadata_only = name == "attachments" and bool(value) and not any(
            item.get("content_saved") for item in value if isinstance(item, dict))
        count = len(value) if isinstance(value, (list, dict)) else None
        resources[name] = _resource_state(data, name, present[name], count, metadata_only)
    overall_states = {item.get("state") for item in resources.values()}
    overall = "complete" if overall_states.issubset({"complete", "metadata_only"}) \
        else "partial"
    raw_value = copy.deepcopy(data)
    raw_text = raw if isinstance(raw, str) else json.dumps(data, ensure_ascii=False, sort_keys=True)
    completeness = {
        "status": overall,
        "source_path": path,
        "source_kind": "local_jira_snapshot",
        "resources": resources,
        "present": present,
        "missing_or_not_requested": sorted(name for name, item in resources.items()
                                            if item.get("state") == "not_requested"),
        "custom_field_count": len(custom_fields),
        "custom_fields": sorted(custom_fields),
        "unknown_field_count": len(unknown_fields["fields"]),
        "raw_preserved": True,
        "raw_sha256": _sha256_text(raw_text),
        "notes": ["absence in a local file is not treated as permission denial"],
    }
    external = {
        "id": normalized["id"], "key": normalized["key"], "url": normalized["url"],
        "project": normalized["project"], "issue_type": normalized["issue_type"],
        "status": normalized["status"], "status_category": normalized["status_category"],
        "summary": normalized["summary"],
    }
    projection = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema": JIRA_MIRROR_SCHEMA, "profile": JIRA_PROFILE,
        "revision": revision,
        "provenance": {"source_path": path, "source_kind": "local_file",
                        "raw_sha256": completeness["raw_sha256"],
                        "provider": "jira", "profile": JIRA_PROFILE},
        "raw": raw_value, "external": external, "normalized": normalized,
        "fields": fields, "comments": [item.as_projection() for item in comments],
        "custom_fields": custom_fields, "dates": dates, "attachments": attachments,
        "links": {"issue": issue_links, "remote": remote_links},
        "relations": {"parent": copy.deepcopy(fields.get("parent")),
                      "subtasks": copy.deepcopy(fields.get("subtasks")),
                      "issue_links": issue_links, "remote_links": remote_links},
        "worklogs": worklog_value, "changelog": changelog, "properties": properties,
        "unknown_fields": unknown_fields, "completeness": completeness,
    }
    return projection, completeness


def validate_jira_projection(payload, where="jira projection"):
    """Dependency-free semantic validator for the exact JIRA-MIRROR-1 envelope."""
    if not isinstance(payload, dict):
        return [Issue("error", where, "Jira projection должен быть object", "JIRA_MIRROR_INVALID")]
    issues = []
    for key in payload:
        if key not in JIRA_MIRROR_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из JIRA-MIRROR-1", "JIRA_MIRROR_INVALID"))
    required = ("schema", "profile", "revision", "provenance", "raw", "external",
                "normalized", "fields", "comments", "custom_fields", "dates",
                "attachments", "links", "relations", "worklogs", "changelog",
                "properties", "unknown_fields", "completeness")
    for key in required:
        if key not in payload:
            issues.append(Issue("error", where, "нет поля «%s»" % key, "JIRA_MIRROR_INVALID"))
    if payload.get("schema") != JIRA_MIRROR_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть JIRA-MIRROR-1", "JIRA_MIRROR_INVALID"))
    if payload.get("profile") != JIRA_PROFILE:
        issues.append(Issue("error", where, "profile должен быть %s" % JIRA_PROFILE,
                            "JIRA_MIRROR_INVALID"))
    if "revision" in payload and (not isinstance(payload["revision"], int) or payload["revision"] < 1):
        issues.append(Issue("error", "%s.revision" % where, "revision должен быть положительным integer",
                            "JIRA_MIRROR_INVALID"))
    for key in ("provenance", "external", "normalized", "fields", "custom_fields",
                "dates", "relations", "unknown_fields", "completeness"):
        if key in payload and not isinstance(payload[key], dict):
            issues.append(Issue("error", "%s.%s" % (where, key), "поле должно быть object",
                                "JIRA_MIRROR_INVALID"))
    if "raw" in payload and not isinstance(payload["raw"], (dict, list, str, int, float, bool, type(None))):
        issues.append(Issue("error", "%s.raw" % where, "raw должен быть JSON value", "JIRA_MIRROR_INVALID"))
    for key in ("comments", "attachments", "links"):
        if key in payload and not isinstance(payload[key], (list, dict)):
            issues.append(Issue("error", "%s.%s" % (where, key), "поле должно быть array/object",
                                "JIRA_MIRROR_INVALID"))
    if "completeness" in payload:
        resources = payload["completeness"].get("resources")
        if resources is not None and not isinstance(resources, dict):
            issues.append(Issue("error", "%s.completeness.resources" % where,
                                "resources должен быть object", "JIRA_MIRROR_INVALID"))
        allowed_states = {"complete", "partial", "permission_denied", "not_requested", "metadata_only"}
        for name, item in (resources or {}).items():
            if not isinstance(item, dict) or item.get("state") not in allowed_states:
                issues.append(Issue("error", "%s.completeness.resources.%s" % (where, name),
                                    "state должен быть %s" % sorted(allowed_states),
                                    "JIRA_MIRROR_INVALID"))
    return issues


def _one_line(text):
    return " ".join(str(text or "").split())[:120]
