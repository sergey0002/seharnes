"""Apply and roll back one approved harness plan on the local filesystem.

This is the CLI-only engine. It refuses merge files, generated views and
unsupported review decisions. Every write is journaled, backed up and verified;
the receipt is written after the full managed-tree check. Panel, supervisor,
Docker and Windows-native entry points are out of scope.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from pathlib import Path

from transfer_diff import FileState
from transfer_git import capture_git_blob
from transfer_inventory import capture_file
from transfer_journal import TransferJournal
from transfer_merge import MergeError, merge_agents, merge_mcp
from transfer_plan import _root_path
from transfer_prepare import prepare_replacement
from transfer_process_lock import ProcessLock
from transfer_receipt import read_receipt_document, write_receipt
from transfer_replace import replace_prepared
from transfer_rollback import audit_recovery_tree, rollback_next
from transfer_tree import TreeSnapshot, capture_tree, compare_trees

MERGE_HANDLERS = {
    "AGENTS.md": merge_agents,
    ".cursor/mcp.json": merge_mcp,
}
MERGE_REFUSED = {
    ".codex/config.toml",
    ".qwen/settings.json",
    ".kilo/kilo.jsonc",
    ".qoder/settings.json",
}
GENERATED_PREFIXES = (".qoder/", ".codex/rules/", ".kilo/rules/", ".agents/rules/")
UNSUPPORTED_CHOICES = {"edited", "rename_incoming", "mark_local"}


class ApplyError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _state(value) -> FileState | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"sha256", "mode"}:
        raise ApplyError("invalid_plan", "invalid file state")
    return FileState(value["sha256"], value["mode"])


def _digest(states: dict) -> str:
    digest = hashlib.sha256()
    for path in sorted(states):
        state = states[path]
        digest.update(f"{path}\0{state.mode:o}\0{state.sha256}\n".encode("utf-8"))
    return digest.hexdigest()


def _unsupported(path: str) -> str | None:
    if path in MERGE_REFUSED:
        return "merge_not_implemented"
    if path.startswith(GENERATED_PREFIXES):
        return "generated_view_not_implemented"
    if path.startswith((".doc/web/state/", ".doc/skil_data/", ".doc/temp/")):
        return "state_not_managed"
    return None


def _content_loader(plan: dict):
    source = plan.get("source")
    if not isinstance(source, dict):
        raise ApplyError("invalid_plan", "plan has no source identity")
    kind = source.get("kind")
    limit = plan.get("max_file_bytes", 8 * 1024 * 1024)
    if kind == "local_source":
        root = _root_path(Path(source.get("path", "")), must_exist=True)

        def load(path: str):
            captured = capture_file(root, path, max_file_bytes=limit)
            return None if captured is None else captured

        return load
    if kind == "local_bare_git":
        repo = Path(source.get("repo", ""))
        commit = source.get("commit")
        if not isinstance(commit, str):
            raise ApplyError("invalid_plan", "invalid plan commit")
        return lambda path: capture_git_blob(repo, commit, path, max_file_bytes=limit)
    raise ApplyError("invalid_plan", "unsupported source kind")


def _actions(plan: dict, decisions: dict, load, target: Path) -> list[dict]:
    rows = plan.get("files")
    required = {item.get("path") for item in plan.get("decisions_required", []) if isinstance(item, dict)}
    limit = plan.get("max_file_bytes", 8 * 1024 * 1024)
    if not isinstance(rows, list):
        raise ApplyError("invalid_plan", "plan has no files")
    actions = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ApplyError("invalid_plan", "invalid plan row")
        path = row["path"]
        unsupported = _unsupported(path)
        if unsupported:
            raise ApplyError(unsupported, f"{unsupported}: {path}")
        proposal = row.get("proposal") or {}
        action = proposal.get("action")
        choice = decisions.get(path) if path in required else None
        if path in required and choice is None:
            raise ApplyError("needs_decision", f"missing decision for {path}")
        if choice in ("keep", "skip", "keep_deleted"):
            continue
        before, incoming = _state(row.get("target")), _state(row.get("incoming"))
        after = None
        if action == "add":
            if choice not in ("add", None):
                raise ApplyError("invalid_decision", f"invalid choice for {path}")
            after = incoming
        elif action == "replace":
            if choice not in ("replace", None):
                raise ApplyError("invalid_decision", f"invalid choice for {path}")
            after = incoming
        elif action == "propose_delete":
            if choice != "delete":
                raise ApplyError("invalid_decision", f"delete choice required for {path}")
        elif action == "review":
            if choice in ("adopt", "replace", "restore_incoming"):
                after = incoming
            elif choice == "delete":
                after = None
            elif choice in UNSUPPORTED_CHOICES:
                raise ApplyError("unsupported_decision", f"review choice {choice} is not implemented")
            else:
                raise ApplyError("invalid_decision", f"invalid choice for {path}")
        elif action in ("none", "keep", "keep_deleted"):
            continue
        else:
            raise ApplyError("unsupported_action", f"unsupported action {action}")
        content = None
        report = None
        if after is not None:
            captured = load(path)
            if captured is None or captured[0] != after:
                raise ApplyError("stale_plan", f"source content changed for {path}")
            content = captured[1]
            handler = MERGE_HANDLERS.get(path)
            if handler is not None:
                try:
                    current = capture_file(target, path, max_file_bytes=limit)
                except ValueError as error:
                    raise ApplyError("merge_target_unreadable", f"cannot read target {path}") from error
                if current is not None and current[0] != before:
                    raise ApplyError("stale_plan", f"target changed for {path}")
                merged, report = handler(current[1] if current is not None else None, content)
                if current is not None and merged == current[1]:
                    continue
                mode = before.mode if before is not None else incoming.mode
                after = FileState(hashlib.sha256(merged).hexdigest(), mode)
                content = merged
        actions.append({"path": path, "before": before, "after": after, "content": content,
                        "decision": choice or action, "merge_report": report})
    return actions


def _ensure_parents(target: Path, actions: list[dict]) -> list[Path]:
    created = []
    for action in actions:
        if action["after"] is None:
            continue
        parent = target / Path(action["path"]).parent
        missing = []
        current = parent
        while current != target and not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            _root_path(directory.parent, must_exist=True)
            directory.mkdir(mode=0o755)
            created.append(directory)
    return created


def _remove_created(created: list[Path]) -> None:
    for directory in reversed(created):
        try:
            directory.rmdir()
        except OSError:
            pass


def _restore_receipt(receipt_path: Path, backup: Path) -> None:
    if backup.exists():
        os.replace(backup, receipt_path)
    elif receipt_path.exists():
        receipt_path.unlink()


def _rollback(journal, lease, lock, target, backup_root, max_file_bytes, created, baseline,
              receipt_path: Path, excludes: list[str]) -> dict:
    try:
        active = journal.active_state()
        if active is not None and active[2] != "rolling_back":
            lease = journal.takeover_for_recovery(lock)
        for _ in range(64):
            result = rollback_next(journal, lease, lock, target, backup_root, max_file_bytes=max_file_bytes)
            if result["status"] == "no_pending_files":
                break
        report = audit_recovery_tree(journal, lease, lock, target, max_file_bytes=max_file_bytes, excludes=excludes)
        if report["status"] == "partial_match":
            current = capture_tree(target, list(baseline.roots), max_file_bytes=max_file_bytes, excludes=excludes)
            digest = _digest(dict(current.files))
            already = journal.tree_baseline(lease)
            expected = _digest(dict(already.files)) if already is not None else digest
            _restore_receipt(receipt_path, backup_root / "receipt.json")
            journal.finalize(lease, "rolled_back", {"tree_digest": digest, "expected_digest": expected})
            _remove_created(created)
            return {"status": "rolled_back", "run_id": lease.run_id}
        _remove_created(created)
        return {"status": "needs_manual_recovery", "run_id": lease.run_id, "reason": report.get("reason")}
    except (OSError, ValueError) as error:
        return {"status": "needs_manual_recovery", "run_id": lease.run_id, "reason": str(error)}


def _receipt_document(plan: dict, actions: list[dict], existing: dict | None) -> dict:
    files = dict(existing["files"]) if existing else {}
    for action in actions:
        path, after = action["path"], action["after"]
        if after is None:
            files.pop(path, None)
        else:
            files[path] = {"installed_hash": after.sha256, "mode": after.mode, "role": "owned",
                           "decision": "replaced" if action["before"] is not None else "installed"}
    source = plan.get("source") or {}
    commit = source.get("commit")
    if not isinstance(commit, str):
        commit = hashlib.sha256(str(plan.get("source_tree_digest")).encode("utf-8")).hexdigest()
    release_url = existing["release_url"] if existing else (
        source.get("repo") or source.get("path") or "local-source")
    return {"release_url": release_url, "commit": commit, "profile": plan.get("profile"), "files": files}


def apply_plan(plan: dict, approved: dict, target: Path, state_dir: Path, *, max_file_bytes: int) -> dict:
    decisions = approved.get("decisions")
    if not isinstance(decisions, dict):
        raise ApplyError("invalid_approval", "approval has no decisions")
    roots = plan.get("roots")
    if not isinstance(roots, list) or not roots:
        raise ApplyError("scope_not_applyable", "apply requires selected roots")
    excludes = plan.get("excludes", [])
    if not isinstance(excludes, list) or any(not isinstance(item, str) for item in excludes):
        raise ApplyError("invalid_plan", "invalid plan excludes")
    target = _root_path(Path(target), must_exist=True)
    actions = _actions(plan, decisions, _content_loader(plan), target)
    if not actions:
        return {"status": "no_changes", "run_id": None}
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = ProcessLock(state_dir / "transfer.lock")
    lock.acquire()
    journal = None
    lease = None
    created = []
    try:
        journal = TransferJournal(sqlite3.connect(state_dir / "transfer.sqlite3"))
        lease = journal.acquire()
        backup_root = Path(state_dir) / "backups" / lease.run_id
        backup_root.mkdir(parents=True, exist_ok=True)
        receipt_path = Path(state_dir) / "receipt.json"
        existing = read_receipt_document(receipt_path) if receipt_path.exists() else None
        if existing is not None:
            shutil.copyfile(receipt_path, backup_root / "receipt.json")
        baseline = capture_tree(target, roots, max_file_bytes=max_file_bytes, excludes=excludes)
        journal.save_tree_baseline(lease, baseline)
        journal.transition(lease, "backed_up")
        created = _ensure_parents(target, actions)
        journal.transition(lease, "replacing")
        for action in actions:
            prepare_replacement(journal, lease, lock, target, backup_root, action["path"],
                                action["before"], action["after"], max_file_bytes=max_file_bytes)
            replace_prepared(journal, lease, lock, target, backup_root, action["path"],
                             action["content"], max_file_bytes=max_file_bytes)
        journal.transition(lease, "validating")
        expected = dict(baseline.files)
        for action in actions:
            if action["after"] is None:
                expected.pop(action["path"], None)
            else:
                expected[action["path"]] = action["after"]
        expected_digest = _digest(expected)
        current = capture_tree(target, roots, max_file_bytes=max_file_bytes, excludes=excludes)
        comparison = compare_trees(TreeSnapshot(baseline.roots, tuple(sorted(expected.items())), baseline.protected),
                                   current)
        if not comparison["matches_scanned_files"] or comparison["protected_names_changed"]:
            raise ApplyError("tree_mismatch", "managed tree does not match the applied result")
        current_digest = _digest(dict(current.files))
        receipt = _receipt_document(plan, actions, existing)
        receipt_sha = write_receipt(receipt_path, **receipt)
        journal.finalize(lease, "committed", {"tree_digest": current_digest,
                                              "expected_digest": expected_digest,
                                              "receipt_sha256": receipt_sha})
        return {"status": "committed", "run_id": lease.run_id,
                "applied": [action["path"] for action in actions],
                "receipt_sha256": receipt_sha, "tree_digest": current_digest}
    except BaseException as error:
        if journal is not None and lease is not None:
            result = _rollback(journal, lease, lock, target, Path(state_dir) / "backups" / lease.run_id,
                               max_file_bytes, created, capture_tree(target, roots, max_file_bytes=max_file_bytes, excludes=excludes),
                               Path(state_dir) / "receipt.json", excludes)
            result["reason"] = str(error)
            return result
        raise
    finally:
        try:
            lock.release()
        except ValueError:
            pass


def rollback_plan(target: Path, state_dir: Path, *, max_file_bytes: int) -> dict:
    excludes = []
    target = _root_path(Path(target), must_exist=True)
    lock = ProcessLock(Path(state_dir) / "transfer.lock")
    lock.acquire()
    try:
        journal = TransferJournal(sqlite3.connect(Path(state_dir) / "transfer.sqlite3"))
        lease = journal.takeover_for_recovery(lock)
        baseline = journal.tree_baseline(lease)
        if baseline is None:
            raise ApplyError("baseline_missing", "tree baseline is missing")
        for _ in range(64):
            result = rollback_next(journal, lease, lock, target, Path(state_dir) / "backups" / lease.run_id,
                                   max_file_bytes=max_file_bytes)
            if result["status"] == "no_pending_files":
                break
        report = audit_recovery_tree(journal, lease, lock, target, max_file_bytes=max_file_bytes, excludes=excludes)
        if report["status"] == "partial_match":
            current = capture_tree(target, list(baseline.roots), max_file_bytes=max_file_bytes, excludes=excludes)
            digest = _digest(dict(current.files))
            expected = _digest(dict(baseline.files))
            _restore_receipt(Path(state_dir) / "receipt.json",
                             Path(state_dir) / "backups" / lease.run_id / "receipt.json")
            journal.finalize(lease, "rolled_back", {"tree_digest": digest, "expected_digest": expected})
            return {"status": "rolled_back", "run_id": lease.run_id}
        return {"status": "needs_manual_recovery", "run_id": lease.run_id, "reason": report.get("reason")}
    finally:
        try:
            lock.release()
        except ValueError:
            pass
