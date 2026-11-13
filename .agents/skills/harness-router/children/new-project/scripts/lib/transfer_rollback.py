"""Experimental journaled single-file rollback for isolated tests only.

This is not a complete recovery supervisor: it does not recover a lost lease,
verify the full pre-apply tree or mark the whole run rolled_back.
"""
from __future__ import annotations

from pathlib import Path

from transfer_inventory import capture_file
from transfer_plan import _root_path
from transfer_process_lock import ProcessLock
from transfer_recovery import inspect_journal_recovery
from transfer_replace import _replace_one, _state
from transfer_tree import capture_tree, compare_trees


def rollback_next(journal, lease, lock: ProcessLock, target: Path, backup_root: Path,
                  *, max_file_bytes: int) -> dict:
    """Restore the latest unresolved journal entry, never finalize the run.

    Requires a private state directory and a shared lock held by all writers.
    Full-tree and trust gates, process takeover and TOCTOU protections remain the
    responsibility of the future supervisor. Unexpected changes fail closed.
    """
    if not isinstance(lock, ProcessLock) or type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ValueError('invalid lock or file size limit')
    lock.assert_held()
    if journal.active_state() != (lease.run_id, lease.generation, 'rolling_back'):
        raise ValueError('journal is not rolling back')
    records = journal.file_records(lease)
    report = inspect_journal_recovery(journal, lease, target, backup_root, max_file_bytes=max_file_bytes)
    if report['status'] == 'manual_required':
        raise ValueError('manual recovery required')
    step = next((row for row in report['steps'] if row['phase'] != 'restored'), None)
    if step is None:
        return {'status': 'no_pending_files', 'full_tree_verified': False, 'run_finalized': False}
    path = step['path']
    record = next(row for row in records if row[0] == path)
    _, _, old_hash, old_mode, new_hash, new_mode, key, _ = record
    old, new = _state(old_hash, old_mode), _state(new_hash, new_mode)
    root = _root_path(Path(target), must_exist=True)
    if step['action'] == 'restore_backup':
        backup = _root_path(Path(backup_root), must_exist=True)
        captured = capture_file(backup, key, max_file_bytes=max_file_bytes)
        if captured is None or captured[0] != old:
            raise ValueError('backup changed during rollback')
        _replace_one(journal, lease, lock, root, path, new, old, captured[1], max_file_bytes)
    elif step['action'] == 'remove_new_file':
        _replace_one(journal, lease, lock, root, path, new, None, None, max_file_bytes)
    elif step['action'] != 'mark_restored':
        raise ValueError('unsupported recovery action')
    lock.assert_held()
    journal.mark_file(lease, path, 'restored')
    return {'status': 'file_restored', 'path': path, 'full_tree_verified': False, 'run_finalized': False}


def audit_recovery_tree(journal, lease, lock: ProcessLock, target: Path, *, max_file_bytes: int,
                        excludes: list[str] | None = None) -> dict:
    """Compare the recorded partial baseline after all file records restore.

    Drift, a missing baseline or an unreadable tree moves the journal to
    ``needs_manual_recovery``. Even a match is incomplete: secret contents,
    directory metadata, policy coverage and full target identity are unchecked.
    It deliberately cannot finalize rollback.
    """
    if not isinstance(lock, ProcessLock) or type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ValueError('invalid lock or file size limit')
    lock.assert_held()
    if journal.active_state() != (lease.run_id, lease.generation, 'rolling_back'):
        raise ValueError('journal is not rolling back')
    records = journal.file_records(lease)
    if any(row[-1] != 'restored' for row in records):
        raise ValueError('journal has unresolved files')
    try:
        baseline = journal.tree_baseline(lease)
        if baseline is None:
            reason, report = 'baseline_missing', None
        else:
            current = capture_tree(target, list(baseline.roots), max_file_bytes=max_file_bytes,
                                   excludes=excludes)
            report = compare_trees(baseline, current)
            reason = ('tree_mismatch' if not report['matches_scanned_files'] or report['protected_names_changed']
                      else None)
    except (OSError, ValueError):
        reason, report = 'baseline_or_tree_unreadable', None
    lock.assert_held()
    if reason is not None:
        journal.transition(lease, 'needs_manual_recovery')
        return {'status': 'needs_manual_recovery', 'reason': reason, 'comparison': report,
                'full_tree_verified': False, 'run_finalized': False}
    return {'status': 'partial_match', 'reason': 'full_tree_gate_missing', 'comparison': report,
            'full_tree_verified': False, 'run_finalized': False}
