"""Resumable agent review queue over one JSON state file (J10, plan 17).

The queue lives at docs/skil_data/task-doc/state/review-queue.json. Every
mutation acquires the exclusive .review-queue.lock (O_CREAT|O_EXCL owner
token, 5s deadline), re-reads and validates the file, applies the change,
bumps the revision and atomically replaces it; unknown fields are rejected
on load. Review results are stored next to their document (task-local
reviews dir or architecture _jsondoc zone) and the queue keeps only a
pointer. Acceptance re-checks the live source hash, so a changed source
marks the review stale instead of accepting outdated work. Stdlib only.
"""

import copy
import hashlib
import json
import os
import re
import socket
import time
import uuid
from pathlib import Path

QUEUE_SCHEMA_VERSION = "1.0"
QUEUE_REL = ("skil_data", "task-doc", "state", "review-queue.json")
LOCK_REL = ("skil_data", "task-doc", "state", ".review-queue.lock")

REASON_CODES = frozenset({
    "ambiguous_section",
    "opaque_critical_flow",
    "conflicting_ids",
    "missing_reverse_link",
    "tag_mapping_ambiguous",
    "metadata_conflict",
    "encoding_warning",
    "sensitive_source",
})

ITEM_STATUSES = ("pending", "leased", "submitted", "accepted",
                 "blocked", "stale", "deferred")
OPEN_STATUSES = ("pending", "leased")
TAG_STATUSES = ("candidate", "confirmed")
KIND_PREFIXES = {"architecture": "arch:", "task": "task:"}

ITEM_FIELDS = ("id", "document_id", "source_path", "source_sha256",
               "candidate_sha256", "reason_codes", "required_sections",
               "evidence_paths", "status", "lease", "attempts",
               "result_path", "coverage", "blockers")
LEASE_FIELDS = ("owner", "token", "expires_at")
COVERAGE_FIELDS = ("text_preserved", "structure_extracted",
                   "semantic_reviewed", "code_verified")
RESULT_FIELDS = ("source_sha256", "enrichment", "reviewer",
                 "evidence_paths", "coverage", "blockers")
ENRICHMENT_FIELDS = ("tags", "relations", "findings_updates",
                     "sections_typed", "notes")

LOCK_DEADLINE = 5.0
LOCK_POLL = 0.05

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DOCUMENT_ID_RE = re.compile(r"^(arch|task):([a-z0-9_-]+)$")
_ITEM_ID_RE = re.compile(r"^(arch|task)-[a-z0-9][a-z0-9_-]*$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

_CACHE = {}


class ReviewError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _utc_in(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(time.time() + int(seconds)))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def queue_path(docs):
    return Path(docs).joinpath(*QUEUE_REL)


def _lock_path(docs):
    return Path(docs).joinpath(*LOCK_REL)


def _fresh_queue():
    return {"schema_version": QUEUE_SCHEMA_VERSION, "revision": 0,
            "items": []}


def _is_hex64(value):
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _split_document_id(document_id):
    if not isinstance(document_id, str):
        return None
    match = _DOCUMENT_ID_RE.fullmatch(document_id)
    if match is None:
        return None
    kind, key = match.group(1), match.group(2)
    if kind == "task" and not key.isdigit():
        return None
    return kind, key


def _resolve_source(docs, source_path):
    docs_root = Path(docs).resolve()
    candidate = Path(source_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (docs_root / candidate).resolve()
    if not resolved.is_relative_to(docs_root):
        raise ReviewError("path_outside_docs", str(source_path))
    return resolved


def _validate_coverage(coverage):
    if not isinstance(coverage, dict):
        raise ReviewError("item_invalid", "coverage not an object")
    unknown = set(coverage) - set(COVERAGE_FIELDS)
    if unknown:
        raise ReviewError("item_invalid",
                          f"coverage unknown fields {sorted(unknown)}")
    missing = set(COVERAGE_FIELDS) - set(coverage)
    if missing:
        raise ReviewError("item_invalid",
                          f"coverage missing {sorted(missing)}")
    for field in COVERAGE_FIELDS:
        if not isinstance(coverage[field], bool):
            raise ReviewError("item_invalid", f"coverage.{field} not boolean")


def _validate_lease(lease):
    if lease is None:
        return
    if not isinstance(lease, dict):
        raise ReviewError("item_invalid", "lease not an object")
    unknown = set(lease) - set(LEASE_FIELDS)
    if unknown:
        raise ReviewError("item_invalid",
                          f"lease unknown fields {sorted(unknown)}")
    missing = set(LEASE_FIELDS) - set(lease)
    if missing:
        raise ReviewError("item_invalid", f"lease missing {sorted(missing)}")
    for field in ("owner", "token"):
        if not isinstance(lease[field], str) or not lease[field]:
            raise ReviewError("item_invalid", f"lease.{field} invalid")
    if _UTC_RE.fullmatch(lease["expires_at"]) is None:
        raise ReviewError("item_invalid", "lease.expires_at invalid")


def _validate_item_stored(item):
    if not isinstance(item, dict):
        raise ReviewError("item_invalid", "item not an object")
    unknown = set(item) - set(ITEM_FIELDS)
    if unknown:
        raise ReviewError("item_unknown_field", sorted(unknown)[0])
    missing = set(ITEM_FIELDS) - set(item)
    if missing:
        raise ReviewError("item_missing_field", sorted(missing)[0])
    split = _split_document_id(item["document_id"])
    if split is None:
        raise ReviewError("item_invalid", "document_id")
    kind = split[0]
    if (not isinstance(item["id"], str)
            or _ITEM_ID_RE.fullmatch(item["id"]) is None
            or not item["id"].startswith(kind + "-")):
        raise ReviewError("item_invalid", "id")
    if not isinstance(item["source_path"], str) or not item["source_path"]:
        raise ReviewError("item_invalid", "source_path")
    if not _is_hex64(item["source_sha256"]):
        raise ReviewError("item_invalid", "source_sha256")
    if item["candidate_sha256"] is not None \
            and not _is_hex64(item["candidate_sha256"]):
        raise ReviewError("item_invalid", "candidate_sha256")
    for field in ("reason_codes", "required_sections", "evidence_paths",
                  "blockers"):
        if not _is_str_list(item[field]):
            raise ReviewError("item_invalid", field)
    if set(item["reason_codes"]) - REASON_CODES:
        raise ReviewError("item_invalid", "reason_codes")
    if item["status"] not in ITEM_STATUSES:
        raise ReviewError("item_invalid", "status")
    _validate_lease(item["lease"])
    if item["status"] == "leased" and item["lease"] is None:
        raise ReviewError("item_invalid", "leased item without lease")
    if item["status"] != "leased" and item["lease"] is not None:
        raise ReviewError("item_invalid", "lease on non-leased item")
    attempts = item["attempts"]
    if (not isinstance(attempts, int) or isinstance(attempts, bool)
            or attempts < 0):
        raise ReviewError("item_invalid", "attempts")
    if item["result_path"] is not None \
            and not isinstance(item["result_path"], str):
        raise ReviewError("item_invalid", "result_path")
    _validate_coverage(item["coverage"])


def _validate_queue(data):
    if not isinstance(data, dict):
        raise ReviewError("queue_invalid", "queue not an object")
    allowed = {"schema_version", "revision", "items"}
    unknown = set(data) - allowed
    if unknown:
        raise ReviewError("queue_unknown_field", sorted(unknown)[0])
    missing = allowed - set(data)
    if missing:
        raise ReviewError("queue_missing_field", sorted(missing)[0])
    if data["schema_version"] != QUEUE_SCHEMA_VERSION:
        raise ReviewError("unsupported_schema_version",
                          str(data["schema_version"]))
    revision = data["revision"]
    if (not isinstance(revision, int) or isinstance(revision, bool)
            or revision < 0):
        raise ReviewError("queue_invalid", "revision")
    if not isinstance(data["items"], list):
        raise ReviewError("queue_invalid", "items")
    seen = set()
    for item in data["items"]:
        _validate_item_stored(item)
        if item["id"] in seen:
            raise ReviewError("duplicate_item_id", item["id"])
        seen.add(item["id"])
    return data


def _read_queue_disk(docs):
    path = queue_path(docs)
    if not path.exists():
        return _fresh_queue()
    if not path.is_file():
        raise ReviewError("queue_invalid", "queue path not a file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError("queue_invalid", str(exc)) from None
    return _validate_queue(data)


def load_queue(docs, refresh=False):
    """Validated queue snapshot; refresh forces a re-read from disk."""
    key = str(queue_path(docs))
    if refresh or key not in _CACHE:
        _CACHE[key] = _read_queue_disk(docs)
    return _CACHE[key]


def _write_bytes(path, data):
    path = Path(path)
    tmp = path.parent / f".{path.name}.tmp-{os.getpid()}"
    fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


def _write_queue(docs, queue):
    path = queue_path(docs)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(path, canonical_bytes(queue))
    _CACHE[str(path)] = queue


def _acquire_lock(path):
    now = time.time()
    token = {"pid": os.getpid(), "host": socket.gethostname(),
             "time": _utc_now() + f".{int(now % 1 * 1000):03d}Z"}
    raw = canonical_bytes(token)
    started = time.monotonic()
    while True:
        try:
            fd = os.open(str(path),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            if time.monotonic() - started >= LOCK_DEADLINE:
                raise ReviewError("lock_busy", str(path)) from None
            time.sleep(LOCK_POLL)
            continue
        try:
            view = memoryview(raw)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
        return token


def _release_lock(path, token):
    try:
        raw = path.read_bytes()
    except OSError:
        return
    try:
        holder = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return
    if holder == token:
        try:
            path.unlink()
        except OSError:
            pass


def _mutate(docs, fn):
    """Run fn(queue) -> changed under the exclusive queue lock (CAS)."""
    path = queue_path(docs)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(docs)
    token = _acquire_lock(lock)
    try:
        queue = _read_queue_disk(docs)
        changed = fn(queue)
        if changed:
            queue["revision"] += 1
            _write_queue(docs, queue)
        else:
            _CACHE[str(path)] = queue
    finally:
        _release_lock(lock, token)


def _find(queue, item_id):
    for item in queue["items"]:
        if item["id"] == item_id:
            return item
    raise ReviewError("unknown_item", str(item_id))


def _select(queue, kind, limit):
    prefix = KIND_PREFIXES[kind] if kind is not None else None
    selected = [item for item in queue["items"]
                if item["status"] == "pending"]
    if prefix is not None:
        selected = [item for item in selected
                    if item["document_id"].startswith(prefix)]
    selected.sort(key=lambda item: (item["document_id"], item["id"]))
    return selected[:limit]


def _prepare_item(docs, raw, check_sources):
    if not isinstance(raw, dict):
        raise ReviewError("item_invalid", "item not an object")
    allowed = {"id", "document_id", "source_path", "source_sha256",
               "candidate_sha256", "reason_codes", "required_sections",
               "evidence_paths", "coverage"}
    unknown = set(raw) - allowed
    if unknown:
        raise ReviewError("item_unknown_field", sorted(unknown)[0])
    for field in ("id", "document_id", "source_path", "source_sha256"):
        if field not in raw:
            raise ReviewError("item_missing_field", field)
    split = _split_document_id(raw["document_id"])
    if split is None:
        raise ReviewError("item_invalid", "document_id")
    kind = split[0]
    if (not isinstance(raw["id"], str)
            or _ITEM_ID_RE.fullmatch(raw["id"]) is None
            or not raw["id"].startswith(kind + "-")):
        raise ReviewError("item_invalid", "id")
    if not isinstance(raw["source_path"], str) or not raw["source_path"]:
        raise ReviewError("item_invalid", "source_path")
    if not _is_hex64(raw["source_sha256"]):
        raise ReviewError("item_invalid", "source_sha256 not hex64")
    candidate = raw.get("candidate_sha256")
    if candidate is not None and not _is_hex64(candidate):
        raise ReviewError("item_invalid", "candidate_sha256 not hex64")
    reason = raw.get("reason_codes", [])
    if not _is_str_list(reason) or set(reason) - REASON_CODES:
        raise ReviewError("item_invalid", "reason_codes")
    for field in ("required_sections", "evidence_paths"):
        if not _is_str_list(raw.get(field, [])):
            raise ReviewError("item_invalid", field)
    if check_sources:
        resolved = _resolve_source(docs, raw["source_path"])
        if not resolved.is_file():
            raise ReviewError("source_missing", raw["source_path"])
    return {
        "id": raw["id"],
        "document_id": raw["document_id"],
        "source_path": raw["source_path"],
        "source_sha256": raw["source_sha256"],
        "candidate_sha256": candidate,
        "reason_codes": list(reason),
        "required_sections": list(raw.get("required_sections", [])),
        "evidence_paths": list(raw.get("evidence_paths", [])),
        "status": "pending",
        "lease": None,
        "attempts": 0,
        "result_path": None,
        "coverage": raw.get("coverage",
                            {field: False for field in COVERAGE_FIELDS}),
        "blockers": [],
    }


def add_items(docs, items, check_sources=False):
    """Add review items; same id+sha is a noop, changed sha resets to
    pending with a note. Returns counts plus the queue revision."""
    if not isinstance(items, list):
        raise ReviewError("items_not_list")
    if not items:
        return {"added": 0, "refreshed": 0, "skipped": 0, "notes": [],
                "queue_revision": load_queue(docs)["revision"]}
    prepared = []
    seen = set()
    for raw in items:
        entry = _prepare_item(docs, raw, check_sources)
        if entry["id"] in seen:
            raise ReviewError("duplicate_id", entry["id"])
        seen.add(entry["id"])
        prepared.append(entry)
    counts = {"added": 0, "refreshed": 0, "skipped": 0}
    notes = []

    def fn(queue):
        existing = {item["id"]: item for item in queue["items"]}
        for entry in prepared:
            current = existing.get(entry["id"])
            if current is None:
                queue["items"].append(entry)
                counts["added"] += 1
                continue
            if current["source_sha256"] == entry["source_sha256"]:
                counts["skipped"] += 1
                continue
            current["source_path"] = entry["source_path"]
            current["source_sha256"] = entry["source_sha256"]
            current["candidate_sha256"] = entry["candidate_sha256"]
            current["reason_codes"] = entry["reason_codes"]
            current["required_sections"] = entry["required_sections"]
            current["evidence_paths"] = entry["evidence_paths"]
            current["status"] = "pending"
            current["lease"] = None
            current["result_path"] = None
            current["coverage"] = {field: False
                                   for field in COVERAGE_FIELDS}
            current["blockers"] = []
            counts["refreshed"] += 1
            notes.append(f"{entry['id']}: source_sha256 changed, "
                         f"item reset to pending")
        return bool(counts["added"] or counts["refreshed"])

    _mutate(docs, fn)
    return {"added": counts["added"], "refreshed": counts["refreshed"],
            "skipped": counts["skipped"], "notes": notes,
            "queue_revision": load_queue(docs)["revision"]}


def next_item(docs, kind=None, claim=False, owner=None, ttl_seconds=900,
              limit=1):
    """Pending items sorted by document_id then id; claim leases them."""
    if kind is not None and kind not in KIND_PREFIXES:
        raise ReviewError("invalid_kind", str(kind))
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ReviewError("invalid_limit", str(limit))
    if not claim:
        queue = load_queue(docs)
        selected = _select(queue, kind, limit)
        return {"items": [copy.deepcopy(item) for item in selected],
                "queue_revision": queue["revision"]}
    if not isinstance(owner, str) or not owner:
        raise ReviewError("owner_required")
    if (not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool)
            or ttl_seconds <= 0):
        raise ReviewError("invalid_ttl", str(ttl_seconds))
    holder = {}

    def fn(queue):
        selected = _select(queue, kind, limit)
        for item in selected:
            item["status"] = "leased"
            item["lease"] = {"owner": owner, "token": uuid.uuid4().hex,
                             "expires_at": _utc_in(ttl_seconds)}
        holder["items"] = [copy.deepcopy(item) for item in selected]
        return bool(selected)

    _mutate(docs, fn)
    return {"items": holder["items"],
            "queue_revision": load_queue(docs)["revision"]}


def _result_path(docs, item):
    kind, key = _split_document_id(item["document_id"])
    if kind == "task":
        rel = Path("tasks") / key / "_jsondoc" / "reviews" / f"{item['id']}.json"
    else:
        rel = (Path("architecture") / "_jsondoc" / key / "reviews"
               / f"{item['id']}.json")
    return Path(docs) / rel


def _validate_result(item, result):
    if not isinstance(result, dict):
        raise ReviewError("result_invalid", "result not an object")
    unknown = set(result) - set(RESULT_FIELDS)
    if unknown:
        raise ReviewError("result_unknown_field", sorted(unknown)[0])
    for field in ("source_sha256", "enrichment", "reviewer",
                  "evidence_paths", "coverage"):
        if field not in result:
            raise ReviewError("result_missing_field", field)
    if not _is_hex64(result["source_sha256"]):
        raise ReviewError("result_invalid", "source_sha256 not hex64")
    if result["source_sha256"] != item["source_sha256"]:
        raise ReviewError("stale_source", item["id"])
    enrichment = result["enrichment"]
    if not isinstance(enrichment, dict):
        raise ReviewError("result_invalid", "enrichment not an object")
    unknown = set(enrichment) - set(ENRICHMENT_FIELDS)
    if unknown:
        raise ReviewError("result_unknown_field",
                          f"enrichment.{sorted(unknown)[0]}")
    if "tags" not in enrichment:
        raise ReviewError("result_missing_field", "enrichment.tags")
    tags = enrichment["tags"]
    if not isinstance(tags, list):
        raise ReviewError("result_invalid", "enrichment.tags")
    for tag in tags:
        if not isinstance(tag, dict) or set(tag) != {"tag_id", "reason",
                                                     "status"}:
            raise ReviewError("result_invalid", "enrichment.tags entry")
        if not isinstance(tag["tag_id"], str) or not tag["tag_id"]:
            raise ReviewError("result_invalid", "enrichment.tags.tag_id")
        if not isinstance(tag["reason"], str):
            raise ReviewError("result_invalid", "enrichment.tags.reason")
        if tag["status"] not in TAG_STATUSES:
            raise ReviewError("result_invalid", "enrichment.tags.status")
    for field in ENRICHMENT_FIELDS[1:]:
        if field in enrichment and not isinstance(enrichment[field], list):
            raise ReviewError("result_invalid", f"enrichment.{field}")
    if not isinstance(result["reviewer"], str) or not result["reviewer"]:
        raise ReviewError("result_invalid", "reviewer")
    if not _is_str_list(result["evidence_paths"]):
        raise ReviewError("result_invalid", "evidence_paths")
    coverage = result["coverage"]
    if not isinstance(coverage, dict):
        raise ReviewError("result_invalid", "coverage not an object")
    unknown = set(coverage) - set(COVERAGE_FIELDS)
    missing = set(COVERAGE_FIELDS) - set(coverage)
    if unknown or missing:
        raise ReviewError("result_invalid", "coverage fields")
    for field in COVERAGE_FIELDS:
        if not isinstance(coverage[field], bool):
            raise ReviewError("result_invalid", f"coverage.{field}")
    if coverage["text_preserved"] is not True:
        raise ReviewError("text_not_preserved", item["id"])
    if not _is_str_list(result.get("blockers", [])):
        raise ReviewError("result_invalid", "blockers")
    return copy.deepcopy(result)


def submit(docs, item_id, result):
    """Validate a review result, write it into the document zone and flip
    the queue item to submitted. Stale source hashes are rejected."""
    item = _find(load_queue(docs), item_id)
    if item["status"] not in OPEN_STATUSES:
        raise ReviewError("invalid_status", item["status"])
    clean = _validate_result(item, result)
    target = _result_path(docs, item)
    rel = target.relative_to(Path(docs)).as_posix()
    envelope = {"schema_version": QUEUE_SCHEMA_VERSION,
                "item_id": item_id,
                "document_id": item["document_id"],
                "submitted_at": _utc_now(),
                "result": clean}
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(target, canonical_bytes(envelope))

    def fn(queue):
        stored = _find(queue, item_id)
        if stored["status"] not in OPEN_STATUSES:
            raise ReviewError("invalid_status", stored["status"])
        if stored["source_sha256"] != clean["source_sha256"]:
            raise ReviewError("stale_source", item_id)
        stored["status"] = "submitted"
        stored["lease"] = None
        stored["result_path"] = rel
        stored["coverage"] = {field: bool(clean["coverage"][field])
                              for field in COVERAGE_FIELDS}
        stored["blockers"] = list(clean.get("blockers", []))
        return True

    _mutate(docs, fn)
    return {"status": "submitted", "item_id": item_id, "result_path": rel,
            "queue_revision": load_queue(docs)["revision"]}


def _load_result(docs, item):
    rel = item["result_path"]
    if not rel:
        raise ReviewError("result_missing", item["id"])
    path = Path(docs) / rel
    if not path.is_file():
        raise ReviewError("result_missing", rel)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError("result_invalid", str(exc)) from None
    result = envelope.get("result") if isinstance(envelope, dict) else None
    if not isinstance(result, dict):
        raise ReviewError("result_invalid", rel)
    return result


def _mark_stale(docs, item_id):
    def fn(queue):
        item = _find(queue, item_id)
        if item["status"] == "stale":
            return False
        item["status"] = "stale"
        item["lease"] = None
        return True

    _mutate(docs, fn)


def _check_fresh_source(docs, item):
    resolved = _resolve_source(docs, item["source_path"])
    if not resolved.is_file():
        _mark_stale(docs, item["id"])
        raise ReviewError("source_missing", item["source_path"])
    live = sha256_file(resolved)
    if live != item["source_sha256"]:
        _mark_stale(docs, item["id"])
        raise ReviewError("stale_source", item["id"])
    return live


def validate_item(docs, item_id):
    """Re-check the live source hash; mismatch marks the item stale."""
    item = _find(load_queue(docs), item_id)
    live = _check_fresh_source(docs, item)
    return {"status": "ok", "item_id": item_id, "source_sha256": live,
            "queue_revision": load_queue(docs)["revision"]}


def approve(docs, item_id):
    """Accept a submitted review after re-checking source freshness."""
    item = _find(load_queue(docs), item_id)
    if item["status"] != "submitted":
        raise ReviewError("not_submitted", item["status"])
    _check_fresh_source(docs, item)
    kind = _split_document_id(item["document_id"])[0]
    result = _load_result(docs, item)
    if kind == "arch":
        coverage = result.get("coverage", {})
        if coverage.get("semantic_reviewed") is not True:
            raise ReviewError("arch_semantic_review_required", item_id)
        enrichment = result.get("enrichment", {})
        if not any(enrichment.get(field)
                   for field in ENRICHMENT_FIELDS):
            raise ReviewError("enrichment_empty", item_id)

    def fn(queue):
        stored = _find(queue, item_id)
        if stored["status"] != "submitted":
            raise ReviewError("not_submitted", stored["status"])
        stored["status"] = "accepted"
        return True

    _mutate(docs, fn)
    return {"status": "accepted", "item_id": item_id,
            "queue_revision": load_queue(docs)["revision"]}


def release_expired(docs):
    """Revert expired leases to pending with attempts incremented."""
    now = _utc_now()
    released = []

    def fn(queue):
        for item in queue["items"]:
            lease = item["lease"]
            if (item["status"] == "leased" and lease is not None
                    and lease["expires_at"] < now):
                item["status"] = "pending"
                item["lease"] = None
                item["attempts"] += 1
                released.append(item["id"])
        return bool(released)

    _mutate(docs, fn)
    return {"released": released,
            "queue_revision": load_queue(docs)["revision"]}


def stats(docs):
    queue = load_queue(docs)
    counts = {status: 0 for status in ITEM_STATUSES}
    for item in queue["items"]:
        counts[item["status"]] += 1
    return counts
