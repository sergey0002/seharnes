"""J02 store tests: create/update CAS, idempotency, no-op, receipt, recover,
concurrency and stale lock behaviour. Task ids are unique per test so the
suite stays independent inside the shared selftest sandbox."""

import json
import os
import subprocess
import sys
import tempfile
import time
import socket
import unittest
from pathlib import Path
from unittest import mock

import support
from jsondoc import contract, render, store


def envelope(operation_id, expected_revision, operations=None, document=None,
             actor="task-doc", reason="рабочее обновление"):
    return {
        "schema_version": "1.0",
        "operation_id": operation_id,
        "expected_revision": expected_revision,
        "actor": actor,
        "reason": reason,
        "operations": operations or [],
        "document": document,
    }


def create_envelope(task_id, operation_id):
    return envelope(operation_id, 0, document=support.minimal_task(task_id))


def set_summary(operation_id, expected_revision, value):
    return envelope(operation_id, expected_revision, operations=[
        {"op": "set", "collection": "summary", "key": "summary",
         "value": value}])


def doc_path(docs, task_id):
    return docs / "tasks" / str(task_id) / "task.json"


def zone_path(docs, task_id):
    return docs / "tasks" / str(task_id) / "_jsondoc"


CHILD_APPLY = r'''
import json, os, sys
from pathlib import Path

scripts_dir, task, oid, value = sys.argv[1:5]
sys.path.insert(0, scripts_dir)
from jsondoc import store

root = Path(os.environ["JSONDOC_RUN_DIR"]) / "sandbox"
st = store.Store(root, Path(".doc"))
envelope = {
    "schema_version": "1.0",
    "operation_id": oid,
    "expected_revision": 1,
    "actor": "task-doc",
    "reason": "конкурентное обновление",
    "operations": [{"op": "set", "collection": "summary", "key": "summary",
                    "value": value}],
    "document": None,
}
try:
    result = st.apply("task", task, envelope)
except store.StoreError as exc:
    print(json.dumps({"outcome": "store_error", "code": exc.code}))
except Exception as exc:
    print(json.dumps({"outcome": "crash",
                      "message": type(exc).__name__ + ": " + str(exc)}))
else:
    print(json.dumps({"outcome": "applied", "revision": result["revision"]}))
'''


class CreateTests(unittest.TestCase):
    def test_create_ok_writes_canonical_doc_and_receipt(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2612"
        res = st.apply("task", task, create_envelope(task, "op-create-2612"))
        self.assertEqual(res["status"], "applied")
        self.assertFalse(res["duplicate"])
        self.assertEqual(res["revision"], 1)
        path = doc_path(docs, task)
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        self.assertEqual(doc["revision"], 1)
        self.assertEqual(raw, store.canonical_bytes(doc))
        self.assertEqual(doc["history"][0]["id"], "op-create-2612")
        self.assertEqual(doc["history"][0]["actor"], "task-doc")
        self.assertEqual(st.load("task", task), doc)
        zone = zone_path(docs, task)
        receipt = st.receipt("task", task)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["control"], "receipt")
        self.assertEqual(receipt["schema_version"], "1.0")
        self.assertEqual(receipt["data_revision"], 1)
        self.assertEqual(receipt["data_sha256"], store.sha256_bytes(raw))
        self.assertIsNone(receipt["view_sha256"])
        self.assertEqual(receipt["operation_id"], "op-create-2612")
        self.assertIsNone(receipt["renderer_version"])
        self.assertEqual(contract.validate_schema(
            receipt, contract.load_schema("control")), [])
        journal = json.loads((zone / "transactions" / res["transaction"]
                              / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["operation_id"], "op-create-2612")
        self.assertIsNone(journal["old_sha256"])
        self.assertEqual(journal["new_sha256"], receipt["data_sha256"])
        self.assertIsNone(journal["backup_path"])
        operations = json.loads((zone / "operations.json").read_text(
            encoding="utf-8"))
        self.assertEqual(operations["op-create-2612"]["revision"], 1)
        self.assertEqual(operations["op-create-2612"]["result_sha256"],
                         receipt["data_sha256"])

    def test_apply_preserves_matching_view_hash(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2622"
        st.apply("task", task, create_envelope(task, "op-create-2622"))
        render.render_document(root, docs, "task", task,
                               st.load("task", task))
        before = st.receipt("task", task)["view_sha256"]
        self.assertIsNotNone(before)
        st.apply("task", task, set_summary("op-view-2622", 1, "new summary"))
        self.assertEqual(st.receipt("task", task)["view_sha256"], before)
        result = render.render_document(root, docs, "task", task,
                                        st.load("task", task))
        self.assertEqual(result["status"], "written")

    def test_duplicate_create_conflict(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2614"
        st.apply("task", task, create_envelope(task, "op-first-2614"))
        before = doc_path(docs, task).read_bytes()
        with self.assertRaises(store.StoreError) as ctx:
            st.apply("task", task, create_envelope(task, "op-again-2614"))
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(ctx.exception.payload["reason"],
                         "create_target_exists")
        self.assertEqual(doc_path(docs, task).read_bytes(), before)

    def test_dry_run_plans_without_writes(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2613"
        res = st.apply("task", task, create_envelope(task, "op-dry-2613"),
                       dry_run=True)
        self.assertEqual(res["status"], "planned")
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["revision"], 1)
        self.assertFalse((docs / "tasks" / task).exists())
        applied = st.apply("task", task,
                           create_envelope(task, "op-dry-2613"))
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["revision"], 1)


class UpdateCasTests(unittest.TestCase):
    def test_wrong_expected_revision_conflict_keeps_file(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2615"
        st.apply("task", task, create_envelope(task, "op-c-2615"))
        path = doc_path(docs, task)
        before = path.read_bytes()
        receipt_before = zone_path(docs, task).joinpath(
            "receipt.json").read_bytes()
        with self.assertRaises(store.StoreError) as ctx:
            st.apply("task", task, set_summary("op-wrong-2615", 7, "миимо"))
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(ctx.exception.payload["reason"], "revision_mismatch")
        self.assertEqual(ctx.exception.payload["current_revision"], 1)
        self.assertEqual(ctx.exception.payload["expected_revision"], 7)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(zone_path(docs, task).joinpath(
            "receipt.json").read_bytes(), receipt_before)


class IdempotencyTests(unittest.TestCase):
    def test_same_operation_same_payload_is_duplicate(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2616"
        st.apply("task", task, create_envelope(task, "op-c-2616"))
        env = set_summary("op-u-2616", 1, "текст правки")
        first = st.apply("task", task, env)
        self.assertEqual(first["status"], "applied")
        self.assertEqual(first["revision"], 2)
        path = doc_path(docs, task)
        after = path.read_bytes()
        doc = json.loads(after.decode("utf-8"))
        self.assertEqual(len(doc["history"]), 2)
        second = st.apply("task", task, env)
        self.assertEqual(second["status"], "duplicate")
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["revision"], 2)
        self.assertEqual(path.read_bytes(), after)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(doc["history"]), 2)

    def test_same_operation_different_payload_conflict(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2617"
        st.apply("task", task, create_envelope(task, "op-c-2617"))
        st.apply("task", task, set_summary("op-dup-2617", 1, "первый вариант"))
        path = doc_path(docs, task)
        before = path.read_bytes()
        with self.assertRaises(store.StoreError) as ctx:
            st.apply("task", task, set_summary("op-dup-2617", 1,
                                               "второй вариант"))
        self.assertEqual(ctx.exception.code, "CONFLICT")
        self.assertEqual(ctx.exception.payload["reason"],
                         "operation_id_payload_mismatch")
        self.assertEqual(path.read_bytes(), before)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["summary"], "первый вариант")


class NoopTests(unittest.TestCase):
    def test_noop_update_same_revision_no_history(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2618"
        st.apply("task", task, create_envelope(task, "op-c-2618"))
        path = doc_path(docs, task)
        after_create = path.read_bytes()
        res = st.apply("task", task, set_summary("op-noop-2618", 1, None))
        self.assertEqual(res["status"], "noop")
        self.assertFalse(res["duplicate"])
        self.assertEqual(res["revision"], 1)
        self.assertEqual(res["previous_revision"], 1)
        self.assertEqual(path.read_bytes(), after_create)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["revision"], 1)
        self.assertEqual(len(doc["history"]), 1)
        self.assertEqual(st.receipt("task", task)["data_revision"], 1)


class SequenceTests(unittest.TestCase):
    def test_two_sequential_updates_revisions_and_history(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2619"
        support.write_canonical(doc_path(docs, task),
                                support.minimal_task(task))
        note = {"id": "note-1", "kind": "observation",
                "text": "первая запись", "source_ids": [], "section_id": None}
        env_a = envelope("op-seq-a-2619", 1, operations=[
            {"op": "set", "collection": "summary", "key": "summary",
             "value": "первый шаг"},
            {"op": "upsert", "collection": "notes", "key": "note-1",
             "value": note}])
        res_a = st.apply("task", task, env_a)
        self.assertEqual(res_a["revision"], 2)
        env_b = envelope("op-seq-b-2619", 2, operations=[
            {"op": "upsert", "collection": "notes", "key": "note-1",
             "value": dict(note, text="обновлённая запись")}])
        res_b = st.apply("task", task, env_b)
        self.assertEqual(res_b["revision"], 3)
        doc = json.loads(doc_path(docs, task).read_text(encoding="utf-8"))
        self.assertEqual(doc["revision"], 3)
        self.assertEqual(doc["summary"], "первый шаг")
        self.assertEqual(len(doc["notes"]), 1)
        self.assertEqual(doc["notes"][0]["text"], "обновлённая запись")
        self.assertEqual([h["id"] for h in doc["history"]],
                         ["op-seq-a-2619", "op-seq-b-2619"])
        self.assertEqual(st.receipt("task", task)["data_revision"], 3)


class PathSafetyTests(unittest.TestCase):
    def test_traversal_and_absolute_keys_rejected(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        for bad in ("../x", "/etc/passwd", "..", ".", "a/b", "a\\b", "C:x"):
            with self.assertRaises(store.StoreError) as ctx:
                st.resolve_target("task", bad)
            self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ROOT")
        for bad in ("..", "../x", "/abs"):
            with self.assertRaises(store.StoreError) as ctx:
                st.resolve_target("arch", bad)
            self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ROOT")
        with self.assertRaises(store.StoreError) as ctx:
            st.resolve_target("task", "abc")
        self.assertEqual(ctx.exception.code, "VALIDATION")
        with self.assertRaises(store.StoreError) as ctx:
            st.resolve_target("widget", "x")
        self.assertEqual(ctx.exception.code, "VALIDATION")

    def test_symlink_escape_rejected(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        tasks = docs / "tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        (tasks / "2620").symlink_to(root.parent)
        with self.assertRaises(store.StoreError) as ctx:
            st.resolve_target("task", "2620")
        self.assertEqual(ctx.exception.code, "PATH_OUTSIDE_ROOT")


class RecoverTests(unittest.TestCase):
    def test_recover_restores_missing_receipt(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2621"
        st.apply("task", task, create_envelope(task, "op-c-2621"))
        zone = zone_path(docs, task)
        (zone / "receipt.json").unlink()
        self.assertIsNone(st.receipt("task", task))
        res = st.recover("task", task)
        self.assertEqual(res["status"], "recovered")
        self.assertTrue(res["recovered"])
        raw = doc_path(docs, task).read_bytes()
        receipt = st.receipt("task", task)
        self.assertEqual(receipt["control"], "receipt")
        self.assertEqual(receipt["data_sha256"], store.sha256_bytes(raw))
        self.assertEqual(receipt["data_revision"], 1)
        self.assertEqual(receipt["operation_id"], "op-c-2621")
        self.assertEqual(contract.validate_schema(
            receipt, contract.load_schema("control")), [])
        again = st.recover("task", task)
        self.assertEqual(again["status"], "ok")
        self.assertFalse(again["recovered"])
        self.assertGreaterEqual(len(list((zone / "transactions").iterdir())), 1)

    def test_recover_tampered_file_requires_recovery(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2622"
        st.apply("task", task, create_envelope(task, "op-c-2622"))
        path = doc_path(docs, task)
        zone = zone_path(docs, task)
        receipt_before = (zone / "receipt.json").read_bytes()
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["summary"] = "изменено руками после публикации"
        support.write_canonical(path, doc)
        with self.assertRaises(store.StoreError) as ctx:
            st.recover("task", task)
        self.assertEqual(ctx.exception.code, "RECOVERY_REQUIRED")
        self.assertEqual(ctx.exception.payload["reason"],
                         "untracked_data_state")
        self.assertEqual((zone / "receipt.json").read_bytes(), receipt_before)
        self.assertTrue((zone / "transactions").is_dir())
        backups = list((zone / "transactions").rglob("backup.json"))
        self.assertEqual(len(backups), 0)
        journals = list((zone / "transactions").rglob("journal.json"))
        self.assertEqual(len(journals), 1)


class ConcurrencyTests(unittest.TestCase):
    def test_two_subprocesses_exactly_one_commit(self):
        run_dir = Path(os.environ.get("JSONDOC_RUN_DIR")
                       or tempfile.mkdtemp(prefix="jsondoc-store-conc-"))
        root = run_dir / "sandbox"
        task = "2623"
        st = store.Store(root, Path(".doc"))
        st.apply("task", task, create_envelope(task, "op-conc-c-2623"))
        env = dict(os.environ)
        env["JSONDOC_RUN_DIR"] = str(run_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        argv = [sys.executable, "-c", CHILD_APPLY, str(support.SCRIPTS_DIR),
                task]
        procs = [subprocess.Popen(argv + ["op-conc-a-2623", "значение A"],
                                  cwd=str(support.SCRIPTS_DIR), env=env,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True,
                                  encoding="utf-8"),
                 subprocess.Popen(argv + ["op-conc-b-2623", "значение B"],
                                  cwd=str(support.SCRIPTS_DIR), env=env,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True,
                                  encoding="utf-8")]
        try:
            outputs = [p.communicate(timeout=120)[0] for p in procs]
        finally:
            for p in procs:
                if p.poll() is None:
                    p.kill()
        results = [json.loads(out.strip().splitlines()[-1])
                   for out in outputs]
        outcomes = sorted(r["outcome"] for r in results)
        self.assertEqual(outcomes, ["applied", "store_error"])
        error = next(r for r in results if r["outcome"] == "store_error")
        self.assertEqual(error["code"], "CONFLICT")
        path = doc_path(root / ".doc", task)
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        self.assertEqual(doc["revision"], 2)
        self.assertIn(doc["summary"], ("значение A", "значение B"))
        self.assertEqual(len(doc["history"]), 2)
        receipt = st.receipt("task", task)
        self.assertEqual(receipt["data_revision"], 2)
        self.assertEqual(receipt["data_sha256"], store.sha256_bytes(raw))


class LockTests(unittest.TestCase):
    def test_stale_lock_conflict_with_info_no_autodelete(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2624"
        st.apply("task", task, create_envelope(task, "op-c-2624"))
        path = doc_path(docs, task)
        zone = zone_path(docs, task)
        lock = zone / ".lock"
        lock.write_bytes(store.canonical_bytes(
            {"pid": 999999, "host": "not-here",
             "time": "2020-01-01T00:00:00Z"}))
        stale = time.time() - 7200
        os.utime(lock, (stale, stale))
        before = path.read_bytes()
        journals_before = sorted(p.name for p in
                                 (zone / "transactions").glob("*/journal.json"))
        with mock.patch.object(store, "LOCK_DEADLINE", 0.3):
            started = time.monotonic()
            with self.assertRaises(store.StoreError) as ctx:
                st.apply("task", task, set_summary("op-stale-2624", 1,
                                                   "не пройдёт"))
            elapsed = time.monotonic() - started
        exc = ctx.exception
        self.assertEqual(exc.code, "CONFLICT")
        self.assertEqual(exc.payload["reason"], "lock_busy")
        info = exc.payload["lock"]
        self.assertEqual(info["path"], str(lock))
        self.assertEqual(info["owner"]["pid"], 999999)
        self.assertGreaterEqual(info["age_seconds"], 7000)
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertTrue(lock.exists())
        self.assertEqual(path.read_bytes(), before)
        operations = json.loads((zone / "operations.json").read_text(
            encoding="utf-8"))
        self.assertNotIn("op-stale-2624", operations)
        journals_after = sorted(p.name for p in
                                (zone / "transactions").glob("*/journal.json"))
        self.assertEqual(journals_after, journals_before)

    def test_dead_local_lock_is_reaped_before_next_write(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        task = "2625"
        st.apply("task", task, create_envelope(task, "op-c-2625"))
        zone = zone_path(docs, task)
        lock = zone / ".lock"
        lock.write_bytes(store.canonical_bytes(
            {"pid": 99999999, "host": socket.gethostname(),
             "time": "2020-01-01T00:00:00Z"}))
        result = st.apply("task", task, set_summary("op-dead-2625", 1, "recovered"))
        self.assertEqual(result["status"], "applied")
        self.assertFalse(lock.exists())


class DefaultFillTests(unittest.TestCase):
    def test_create_fills_structural_nulls_without_text(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        doc = support.minimal_task("2626")
        for key in ("progress", "stages", "notes", "relations", "artifacts",
                    "checks", "git_events", "sources", "business_logic"):
            doc.pop(key, None)
        doc["files"] = [{"id": "F-1", "path": "lib/a.php", "role": "role",
                         "change": "change", "state": "current"}]
        doc["findings"] = [{
            "id": "PK-1", "kind": "pitfall", "title": "t",
            "statement": "s", "status": "observed"}]
        doc["decisions"] = [{
            "id": "R-1", "title": "t", "context": "c", "choice": "x",
            "status": "implemented"}]
        doc["requirements"] = [{
            "id": "REQ-1", "text": "t", "state": "closed"}]
        doc["sources"] = [{
            "id": "SRC-1", "kind": "brief", "path": ".doc/tasks/2626/task.md",
            "availability": "present"}]

        res = st.apply("task", "2626", envelope(
            "op-defaults-2626", 0, document=doc))
        self.assertEqual(res["status"], "applied")
        saved = st.load("task", "2626")
        self.assertEqual(saved["progress"], [])
        self.assertEqual(saved["business_logic"],
                         {"facts": [], "unconfirmed": [],
                          "linked_rule_ids": []})
        self.assertEqual(saved["files"][0]["ranges"], [])
        self.assertIsNone(saved["files"][0]["previous_path"])
        self.assertEqual(saved["findings"][0]["file_ids"], [])
        self.assertIsNone(saved["findings"][0]["cause"])
        self.assertEqual(saved["decisions"][0]["alternatives"], [])
        self.assertEqual(saved["requirements"][0]["stage_ids"], [])
        self.assertIsNone(saved["requirements"][0]["reason"])
        self.assertIsNone(saved["sources"][0]["pointer"])

    def test_repeated_apply_is_noop_after_defaults(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        doc = support.minimal_task("2627")
        doc["files"] = [{"id": "F-1", "path": "lib/a.php", "role": None,
                         "change": None, "state": "current"}]
        st.apply("task", "2627", envelope(
            "op-defaults-create-2627", 0, document=doc))
        repeated = st.apply("task", "2627", envelope(
            "op-defaults-repeat-2627", 1, operations=[
                {"op": "set", "collection": "summary", "key": "summary",
                 "value": None}]))
        self.assertEqual(repeated["status"], "noop")


class ArchitectureApplyTests(unittest.TestCase):
    key = "example-1489"

    def arch_document(self, title="Пример архитектуры"):
        doc = support.minimal_task("1489", title)
        doc["kind"] = "architecture"
        doc["id"] = f"architecture:{self.key}"
        doc["metadata"]["task_id"] = None
        doc["metadata"]["branch"] = None
        doc["metadata"]["task_type"] = None
        return doc

    def test_arch_apply_and_render_keep_receipt_consistent(self):
        root, docs = support.make_docs()
        st = store.Store(root, Path(".doc"))
        created = st.apply("arch", self.key, envelope(
            "op-arch-create-1489", 0, document=self.arch_document()))
        self.assertEqual(created["status"], "applied")
        self.assertEqual(created["revision"], 1)

        doc = st.load("arch", self.key)
        render.render_document(root, docs, "architecture", self.key, doc)
        rendered = st.receipt("arch", self.key)
        self.assertIsNotNone(rendered["view_sha256"])

        updated = st.apply("arch", self.key, set_summary(
            "op-arch-update-1489", 1, "обновлено"))
        self.assertEqual(updated["status"], "applied")
        receipt = st.receipt("arch", self.key)
        self.assertEqual(receipt["data_revision"], 2)
        self.assertEqual(receipt["view_sha256"], rendered["view_sha256"])

        stale = dict(receipt, data_revision=1, data_sha256=created["new_sha256"])
        (docs / "architecture/_jsondoc" / self.key / "receipt.json").write_text(
            json.dumps(stale), encoding="utf-8")
        recovered = st.recover("arch", self.key)
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["data_revision"], 2)
        self.assertEqual(st.receipt("arch", self.key)["view_sha256"],
                         rendered["view_sha256"])


class NoShadowingTests(unittest.TestCase):
    def test_ut29_import_resolves_package_not_script(self):
        import jsondoc
        self.assertTrue(str(jsondoc.__file__).endswith("jsondoc/__init__.py"))


if __name__ == "__main__":
    unittest.main()
