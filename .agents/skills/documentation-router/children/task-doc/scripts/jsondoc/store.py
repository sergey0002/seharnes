"""Canonical single-document store: CAS apply, lock, journal, receipt (J02).

Publishes task/architecture JSON atomically under an exclusive per-target
lock (target.parent/_jsondoc/.lock with owner token {pid, host, time}),
enforces revision CAS and operation_id idempotency, journals every change
with a byte backup of the previous version, and writes the control receipt
(schemas/control.schema.json) last. recover() restores only hash-consistent
receipts and never mutates data, deletes files or touches views. Renderer
and MD views belong to J03. Stdlib only, Python 3.9+.
"""

import copy
import contextlib
import builtins
import errno
import hashlib
import itertools
import json
import os
import re
import socket
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None

from . import contract

LOCK_DEADLINE = 5.0
LOCK_POLL = 0.05

ERROR_CODES = ("CONFLICT", "VIEW_CONFLICT", "RECOVERY_REQUIRED",
               "VALIDATION", "PATH_OUTSIDE_ROOT")

_TX_SEQ = itertools.count(1)
_KEY_SEPARATORS = ("/", "\\", "\x00")


def canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@contextlib.contextmanager
def _publication_guard(docs, target, shared, already_held=False):
    """No-op publication guard.

    The business-analyst transaction barrier was removed from the harness.
    Task JSON reads and writes no longer share a lock with any analyzer.
    """
    yield


def _next_tx():
    now = time.time()
    return (f"tx-{int(now) * 1000 + int(now % 1 * 1000):016d}"
            f"-{os.getpid():06d}-{next(_TX_SEQ):04d}")


def _render_kind(kind):
    """Store kind names and renderer kind names differ for architecture."""
    return "architecture" if kind == "arch" else kind


class StoreError(Exception):
    def __init__(self, code, payload=None):
        super().__init__(code)
        self.code = code
        self.payload = dict(payload or {})


def _check_key(key):
    if not isinstance(key, str):
        raise StoreError("PATH_OUTSIDE_ROOT", {"key": repr(key)})
    if (not key or key in (".", "..")
            or any(sep in key for sep in _KEY_SEPARATORS)
            or re.match(r"^[A-Za-z]:", key)):
        raise StoreError("PATH_OUTSIDE_ROOT", {"key": key})


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def _fsync_dir(path):
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _write_bytes(path, data):
    path = Path(path)
    tmp = path.parent / f".{path.name}.tmp-{os.getpid()}"
    fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    _fsync_dir(path.parent)


class Store:
    def __init__(self, root, docs_dir):
        self.root = Path(root).resolve()
        self.docs_dir = Path(docs_dir)
        self.docs = self.root / self.docs_dir

    def resolve_target(self, kind, key):
        if kind == "task":
            _check_key(key)
            if re.fullmatch(r"[0-9]+", key) is None:
                raise StoreError("VALIDATION", {"errors": [
                    {"code": "task_key_digits", "at": "$.key"}]})
            rel = Path("tasks") / key / "task.json"
        elif kind == "arch":
            _check_key(key)
            rel = Path("architecture") / (key + ".json")
        else:
            raise StoreError("VALIDATION", {"errors": [
                {"code": "unknown_kind", "kind": kind}]})
        root_resolved = self.root.resolve()
        docs_resolved = self.docs.resolve()
        if not docs_resolved.is_relative_to(root_resolved):
            raise StoreError("PATH_OUTSIDE_ROOT", {"path": str(self.docs)})
        target = self.docs / rel
        if not target.resolve().is_relative_to(root_resolved):
            raise StoreError("PATH_OUTSIDE_ROOT", {"path": str(target)})
        return target

    def load(self, kind, key, publication_lock_held=False):
        target = self.resolve_target(kind, key)
        with _publication_guard(self.docs, target, shared=True,
                                already_held=publication_lock_held):
            doc, _raw = self._read_target(target)
            return doc

    def _load_uncoordinated(self, kind, key):
        target = self.resolve_target(kind, key)
        doc, _raw = self._read_target(target)
        return doc

    def apply(self, kind, key, envelope, dry_run=False,
              publication_lock_held=False):
        target = self.resolve_target(kind, key)
        shared = bool(dry_run)
        with _publication_guard(self.docs, target, shared=shared,
                                already_held=publication_lock_held):
            return self._apply_uncoordinated(kind, key, envelope, dry_run)

    def _apply_uncoordinated(self, kind, key, envelope, dry_run=False):
        target = self.resolve_target(kind, key)
        if not isinstance(envelope, dict):
            raise StoreError("VALIDATION", {"errors": [
                {"code": "envelope_not_object"}]})
        if envelope.get("document") is not None:
            envelope = copy.deepcopy(envelope)
            envelope["document"] = contract.fill_document_defaults(
                envelope["document"])
        errors = contract.validate_update(envelope)
        if errors:
            raise StoreError("VALIDATION",
                             {"errors": errors, "target": str(target)})
        payload_sha = sha256_bytes(canonical_bytes(envelope))
        zone = self._zone(target)
        if dry_run:
            current, raw = self._read_target(target)
            entry = self._idempotency(zone, envelope, payload_sha)
            if entry is not None:
                return self._duplicate_result(kind, key, target, envelope,
                                              entry, dry_run=True)
            self._check_cas(target, current, envelope)
            new_doc, status = self._build(current, envelope)
            errors = contract.validate_document(new_doc)
            if errors:
                raise StoreError("VALIDATION", {"errors": errors})
            return {
                "kind": kind, "key": key,
                "operation_id": envelope["operation_id"],
                "status": "planned" if status == "applied" else "noop",
                "duplicate": False, "dry_run": True,
                "previous_revision": (current.get("revision")
                                      if current else None),
                "revision": new_doc.get("revision"),
                "old_sha256": sha256_bytes(raw) if raw is not None else None,
                "new_sha256": sha256_bytes(canonical_bytes(new_doc)),
                "target": str(target), "transaction": None,
                "receipt_path": None,
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        zone.mkdir(parents=True, exist_ok=True)
        (zone / "transactions").mkdir(parents=True, exist_ok=True)
        (zone / "work").mkdir(parents=True, exist_ok=True)
        token = self._acquire_lock(zone / ".lock")
        try:
            current, raw = self._read_target(target)
            entry = self._idempotency(zone, envelope, payload_sha)
            if entry is not None:
                return self._duplicate_result(kind, key, target, envelope,
                                              entry, dry_run=False)
            self._check_cas(target, current, envelope)
            new_doc, status = self._build(current, envelope)
            errors = contract.validate_document(new_doc)
            if errors:
                raise StoreError("VALIDATION",
                                 {"errors": errors, "target": str(target)})
            old_sha = sha256_bytes(raw) if raw is not None else None
            new_bytes = canonical_bytes(new_doc)
            new_sha = sha256_bytes(new_bytes)
            if status == "noop":
                self._record_operation(zone, envelope, payload_sha, new_sha,
                                       new_doc.get("revision"))
                return {
                    "kind": kind, "key": key,
                    "operation_id": envelope["operation_id"],
                    "status": "noop", "duplicate": False, "dry_run": False,
                    "previous_revision": new_doc.get("revision"),
                    "revision": new_doc.get("revision"),
                    "old_sha256": old_sha, "new_sha256": new_sha,
                    "target": str(target), "transaction": None,
                    "receipt_path": None,
                }
            tx = _next_tx()
            tx_dir = zone / "transactions" / tx
            tx_dir.mkdir(parents=True, exist_ok=True)
            backup_rel = None
            if raw is not None:
                backup_rel = f"transactions/{tx}/backup.json"
                _write_bytes(tx_dir / "backup.json", raw)
            journal = {"operation_id": envelope["operation_id"],
                       "old_sha256": old_sha, "new_sha256": new_sha,
                       "backup_path": backup_rel}
            _write_bytes(tx_dir / "journal.json", canonical_bytes(journal))
            _write_bytes(target, new_bytes)
            # The view file is not touched by apply, so its receipt hash stays
            # valid. Carrying it forward lets render overwrite an older view
            # without a false VIEW_CONFLICT, while a hand-edited view (hash no
            # longer matching the previous receipt) is still rejected.
            carried_view_sha = None
            carried_renderer = None
            previous_receipt = self.receipt(kind, key)
            if previous_receipt and previous_receipt.get("view_sha256"):
                from .render import view_path
                view_file = view_path(self.docs, _render_kind(kind), key)
                if view_file.is_file():
                    actual_view_sha = sha256_bytes(view_file.read_bytes())
                    if actual_view_sha == previous_receipt["view_sha256"]:
                        carried_view_sha = actual_view_sha
                        carried_renderer = previous_receipt.get("renderer_version")
            receipt = {"control": "receipt", "schema_version": "1.0",
                       "data_revision": new_doc["revision"],
                       "data_sha256": new_sha, "view_sha256": carried_view_sha,
                       "operation_id": envelope["operation_id"],
                       "renderer_version": carried_renderer}
            errors = contract.validate_schema(
                receipt, contract.load_schema("control"))
            if errors:
                raise StoreError("VALIDATION", {"errors": errors})
            _write_bytes(zone / "receipt.json", canonical_bytes(receipt))
            self._record_operation(zone, envelope, payload_sha, new_sha,
                                   new_doc["revision"])
            return {
                "kind": kind, "key": key,
                "operation_id": envelope["operation_id"],
                "status": "applied", "duplicate": False, "dry_run": False,
                "previous_revision": (current.get("revision")
                                      if current else None),
                "revision": new_doc["revision"],
                "old_sha256": old_sha, "new_sha256": new_sha,
                "target": str(target), "transaction": tx,
                "receipt_path": str(zone / "receipt.json"),
            }
        finally:
            self._release_lock(zone / ".lock", token)

    def recover(self, kind, key, publication_lock_held=False):
        target = self.resolve_target(kind, key)
        with _publication_guard(self.docs, target, shared=True,
                                already_held=publication_lock_held):
            zone = self._zone(target)
            zone.mkdir(parents=True, exist_ok=True)
            token = self._acquire_lock(zone / ".lock")
            try:
                return self._recover_uncoordinated(kind, key)
            finally:
                self._release_lock(zone / ".lock", token)

    def _recover_uncoordinated(self, kind, key):
        target = self.resolve_target(kind, key)
        zone = self._zone(target)
        journals = self._journals(zone)
        if not target.is_file():
            if journals:
                raise StoreError("RECOVERY_REQUIRED", {
                    "reason": "published_file_missing",
                    "target": str(target),
                    "transactions": [j["tx"] for j in journals]})
            return {"status": "clean", "kind": kind, "key": key,
                    "recovered": False, "target": str(target)}
        raw = target.read_bytes()
        file_sha = sha256_bytes(raw)
        matching = [j for j in journals if j.get("new_sha256") == file_sha]
        if not matching:
            raise StoreError("RECOVERY_REQUIRED", {
                "reason": ("untracked_data_state" if journals
                           else "no_journal_for_existing_file"),
                "target": str(target), "data_sha256": file_sha,
                "known_new_sha256": [j.get("new_sha256") for j in journals]})
        journal = matching[-1]
        try:
            doc = contract.load_json_strict(raw.decode("utf-8"))
        except (UnicodeDecodeError, contract.ContractError) as exc:
            raise StoreError("RECOVERY_REQUIRED", {
                "reason": "invalid_published_json", "target": str(target),
                "message": str(exc)}) from None
        revision = doc.get("revision") if isinstance(doc, dict) else None
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise StoreError("RECOVERY_REQUIRED", {
                "reason": "revision_unreadable", "target": str(target)})
        try:
            current = self.receipt(kind, key)
        except StoreError:
            current = None
        if (current is not None
                and current.get("data_sha256") == file_sha
                and current.get("data_revision") == revision):
            return {"status": "ok", "kind": kind, "key": key,
                    "recovered": False, "data_revision": revision,
                    "data_sha256": file_sha,
                    "operation_id": journal.get("operation_id"),
                    "receipt_path": str(zone / "receipt.json")}
        # The view is never touched by apply, so a valid view hash from the
        # previous receipt is still current. Dropping it made the next render
        # reject an untouched view with VIEW_CONFLICT.
        view_sha = None
        renderer = None
        if current and current.get("view_sha256"):
            try:
                from .render import view_path
                view_file = view_path(self.docs, _render_kind(kind), key)
                if view_file.is_file():
                    actual = sha256_bytes(view_file.read_bytes())
                    if actual == current["view_sha256"]:
                        view_sha = actual
                        renderer = current.get("renderer_version")
            except Exception:
                view_sha = None
                renderer = None
        receipt = {"control": "receipt", "schema_version": "1.0",
                   "data_revision": revision, "data_sha256": file_sha,
                   "view_sha256": view_sha,
                   "operation_id": journal.get("operation_id"),
                   "renderer_version": renderer}
        errors = contract.validate_schema(
            receipt, contract.load_schema("control"))
        if errors:
            raise StoreError("VALIDATION", {"errors": errors})
        zone.mkdir(parents=True, exist_ok=True)
        _write_bytes(zone / "receipt.json", canonical_bytes(receipt))
        return {"status": "recovered", "kind": kind, "key": key,
                "recovered": True, "data_revision": revision,
                "data_sha256": file_sha,
                "operation_id": journal.get("operation_id"),
                "receipt_path": str(zone / "receipt.json")}

    def receipt(self, kind, key):
        target = self.resolve_target(kind, key)
        path = self._zone(target) / "receipt.json"
        if not path.is_file():
            return None
        try:
            data = contract.load_json_strict(path.read_text(encoding="utf-8"))
        except (OSError, contract.ContractError) as exc:
            raise StoreError("VALIDATION", {"errors": [
                {"code": "invalid_receipt", "path": str(path),
                 "message": str(exc)}]}) from None
        return data

    def _zone(self, target):
        # architecture docs share the parent dir: isolate zone per document
        if target.parent.name == "architecture":
            return target.parent / "_jsondoc" / target.stem
        return target.parent / "_jsondoc"

    def _read_target(self, target):
        if not target.exists():
            return None, None
        if not target.is_file():
            raise StoreError("VALIDATION", {"errors": [
                {"code": "target_not_file", "path": str(target)}]})
        try:
            raw = target.read_bytes()
            doc = contract.load_json_strict(raw.decode("utf-8"))
        except (UnicodeDecodeError, contract.ContractError) as exc:
            raise StoreError("VALIDATION", {"errors": [
                {"code": "invalid_document", "path": str(target),
                 "message": str(exc)}]}) from None
        if not isinstance(doc, dict):
            raise StoreError("VALIDATION", {"errors": [
                {"code": "document_not_object", "path": str(target)}]})
        return doc, raw

    def _check_cas(self, target, current, envelope):
        expected = envelope["expected_revision"]
        if envelope["document"] is not None:
            if current is not None:
                raise StoreError("CONFLICT", {
                    "reason": "create_target_exists",
                    "current_revision": current.get("revision"),
                    "expected_revision": expected,
                    "target": str(target)})
            return
        if current is None:
            raise StoreError("CONFLICT", {
                "reason": "missing_document", "current_revision": None,
                "expected_revision": expected, "target": str(target)})
        if current.get("revision") != expected:
            raise StoreError("CONFLICT", {
                "reason": "revision_mismatch",
                "current_revision": current.get("revision"),
                "expected_revision": expected, "target": str(target)})

    def _load_operations(self, zone):
        path = zone / "operations.json"
        if not path.is_file():
            return {}
        try:
            data = contract.load_json_strict(path.read_text(encoding="utf-8"))
        except (OSError, contract.ContractError) as exc:
            raise StoreError("VALIDATION", {"errors": [
                {"code": "invalid_operations", "path": str(path),
                 "message": str(exc)}]}) from None
        return data if isinstance(data, dict) else {}

    def _record_operation(self, zone, envelope, payload_sha, result_sha,
                          revision):
        operations = self._load_operations(zone)
        operations[envelope["operation_id"]] = {
            "payload_sha256": payload_sha,
            "result_sha256": result_sha,
            "revision": revision,
        }
        _write_bytes(zone / "operations.json", canonical_bytes(operations))

    def _idempotency(self, zone, envelope, payload_sha):
        entry = self._load_operations(zone).get(envelope["operation_id"])
        if entry is None:
            return None
        if entry.get("payload_sha256") != payload_sha:
            raise StoreError("CONFLICT", {
                "reason": "operation_id_payload_mismatch",
                "operation_id": envelope["operation_id"],
                "stored_payload_sha256": entry.get("payload_sha256")})
        return entry

    def _duplicate_result(self, kind, key, target, envelope, entry, dry_run):
        return {
            "kind": kind, "key": key,
            "operation_id": envelope["operation_id"],
            "status": "duplicate", "duplicate": True, "dry_run": dry_run,
            "previous_revision": entry.get("revision"),
            "revision": entry.get("revision"),
            "old_sha256": entry.get("result_sha256"),
            "new_sha256": entry.get("result_sha256"),
            "target": str(target), "transaction": None,
            "receipt_path": None,
        }

    def _history_entry(self, envelope):
        return {"id": envelope["operation_id"], "at": _utc_now(),
                "actor": envelope["actor"], "summary": envelope["reason"],
                "source_ids": []}

    def _apply_operations(self, current, envelope):
        doc = copy.deepcopy(current)
        for index, op in enumerate(envelope["operations"]):
            at = f"$.operations[{index}]"
            name = op["op"]
            collection = op["collection"]
            if name == "set":
                parts = collection.split(".")
                node = doc
                for part in parts[:-1]:
                    if not isinstance(node, dict) or part not in node:
                        raise StoreError("VALIDATION", {"errors": [
                            {"code": "set_path_missing",
                             "at": at + ".collection"}]})
                    node = node[part]
                if not isinstance(node, dict):
                    raise StoreError("VALIDATION", {"errors": [
                        {"code": "set_path_missing",
                         "at": at + ".collection"}]})
                node[parts[-1]] = op["value"]
                continue
            items = doc.get(collection)
            if not isinstance(items, list):
                raise StoreError("VALIDATION", {"errors": [
                    {"code": "unknown_collection", "at": at + ".collection",
                     "collection": collection}]})
            id_field = "tag_id" if collection == "tags" else "id"
            if name == "upsert":
                value = op["value"]
                if not isinstance(value, dict):
                    raise StoreError("VALIDATION", {"errors": [
                        {"code": "upsert_value_not_record", "at": at}]})
                for pos, item in enumerate(items):
                    if (isinstance(item, dict)
                            and item.get(id_field) == op["key"]):
                        items[pos] = value
                        break
                else:
                    items.append(value)
            else:
                for item in items:
                    if (isinstance(item, dict)
                            and item.get(id_field) == op["key"]):
                        item["superseded_by"] = op["superseded_by"]
                        break
                else:
                    raise StoreError("VALIDATION", {"errors": [
                        {"code": "unknown_record", "at": at,
                         "collection": collection, "key": op["key"]}]})
        return doc

    @staticmethod
    def _normalize_legacy_document(document):
        """Migrate known legacy fields to the current document contract."""
        document.pop("data_revision", None)

        metadata = document.get("metadata")
        if isinstance(metadata, dict):
            updated = metadata.pop("updated", None)
            current = metadata.get("updated_at")
            if isinstance(updated, str) and updated and (
                    not current or current == "1970-01-01T00:00:00Z"):
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
                    metadata["updated_at"] = updated + "T00:00:00Z"
                else:
                    metadata["updated_at"] = updated

        decisions = document.get("decisions")
        if isinstance(decisions, list):
            for decision in decisions:
                if not isinstance(decision, dict):
                    continue
                alternatives = decision.get("alternatives")
                if not isinstance(alternatives, list):
                    continue
                normalized = []
                for alternative in alternatives:
                    if isinstance(alternative, str):
                        text, sep, reason = alternative.partition(" \u2014 ")
                        normalized.append({
                            "text": text.strip() or alternative.strip(),
                            "reason": reason.strip() if sep and reason.strip()
                            else "legacy alternative",
                        })
                    else:
                        normalized.append(alternative)
                decision["alternatives"] = normalized

        return document

    def _build(self, current, envelope):
        if envelope["document"] is not None:
            new_doc = copy.deepcopy(envelope["document"])
            new_doc = self._normalize_legacy_document(new_doc)
            new_doc = contract.fill_document_defaults(new_doc)
            new_doc["revision"] = 1
            history = list(new_doc.get("history", []))
            history.append(self._history_entry(envelope))
            new_doc["history"] = history
            return new_doc, "applied"
        candidate = self._apply_operations(current, envelope)
        candidate = self._normalize_legacy_document(candidate)
        candidate = contract.fill_document_defaults(candidate)
        probe = copy.deepcopy(candidate)
        probe["revision"] = current.get("revision")
        if canonical_bytes(probe) == canonical_bytes(current):
            return copy.deepcopy(current), "noop"
        candidate["revision"] = current.get("revision", 0) + 1
        history = list(candidate.get("history", []))
        history.append(self._history_entry(envelope))
        candidate["history"] = history
        return candidate, "applied"

    def _journals(self, zone):
        entries = []
        tx_root = zone / "transactions"
        if not tx_root.is_dir():
            return entries
        for tx_dir in sorted(tx_root.iterdir()):
            journal = tx_dir / "journal.json"
            if not journal.is_file():
                continue
            try:
                data = contract.load_json_strict(
                    journal.read_text(encoding="utf-8"))
            except (OSError, contract.ContractError):
                continue
            if isinstance(data, dict) and "new_sha256" in data:
                data["tx"] = tx_dir.name
                entries.append(data)
        return entries

    def _acquire_lock(self, path):
        now = time.time()
        token = {"pid": os.getpid(), "host": socket.gethostname(),
                 "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))
                 + f".{int(now % 1 * 1000):03d}Z"}
        raw = canonical_bytes(token)
        started = time.monotonic()
        while True:
            with self._lock_creation_guard(path):
                if self._create_lock(path, raw):
                    return token
                if self._reap_dead_local_lock(path):
                    if self._create_lock(path, raw):
                        return token
            if time.monotonic() - started >= LOCK_DEADLINE:
                raise StoreError("CONFLICT", {
                    "reason": "lock_busy",
                    "lock": self._lock_info(path)}) from None
            time.sleep(LOCK_POLL)

    @contextlib.contextmanager
    def _lock_creation_guard(self, path):
        if fcntl is None:
            yield
            return
        guard = path.with_name(path.name + ".guard")
        handle = guard.open("a+b")
        started = time.monotonic()
        try:
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() - started >= LOCK_DEADLINE:
                        raise StoreError("CONFLICT", {
                            "reason": "lock_guard_busy", "lock": str(guard)}) from None
                    time.sleep(LOCK_POLL)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    @staticmethod
    def _create_lock(path, raw):
        temp = path.with_name(
            f".{path.name}.{os.getpid()}.{threading.get_ident()}.{next(_TX_SEQ)}.tmp")
        fd = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            _write_all(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(str(temp), str(path))
        except FileExistsError:
            return False
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
        return True

    def _reap_dead_local_lock(self, path):
        if fcntl is None:
            return False
        try:
            before = path.stat()
            raw = path.read_bytes()
            owner = json.loads(raw.decode("utf-8"))
        except FileNotFoundError:
            return True
        except (OSError, UnicodeDecodeError, ValueError):
            return False
        if (not isinstance(owner, dict) or owner.get("host") != socket.gethostname()
                or type(owner.get("pid")) is not int or owner["pid"] < 1):
            return False
        try:
            os.kill(owner["pid"], 0)
            return False
        except PermissionError:
            return False
        except ProcessLookupError:
            pass
        except OSError as exc:
            if exc.errno != errno.ESRCH:
                return False
        try:
            after = path.stat()
            if ((before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                    or path.read_bytes() != raw):
                return False
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _release_lock(self, path, token):
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

    def _lock_info(self, path):
        info = {"path": str(path)}
        try:
            stat = path.stat()
        except OSError:
            info["mtime"] = None
            return info
        info["mtime"] = int(stat.st_mtime)
        info["age_seconds"] = round(time.time() - stat.st_mtime, 3)
        try:
            info["owner"] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info["owner"] = None
        return info
