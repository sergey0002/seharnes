"""Conservative, read-only analysis of journaled rollback states.

The optional inspector reads journaled paths but never mutates them. Snapshots
are not locks and must be revalidated by the future recovery supervisor. In
particular, this does not check unjournaled files or the pre-apply hash tree.
"""
from __future__ import annotations

from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import snapshot_files, validate_paths
from transfer_plan import _root_path


def _state(digest, mode):
    if digest is None and mode is None:
        return None
    if digest is None or mode is None:
        raise ValueError('incomplete journal file state')
    return FileState(digest, mode)


def analyze_recovery(records: list[tuple], current: dict, backups: dict) -> dict:
    """Describe rollback actions in reverse sequence; never authorize writes.

    ``current`` explicitly maps every journal path to FileState or None. A
    missing mapping is unknown, not an absent file. ``backups`` maps journal
    backup keys to their observed FileState. Unknown/diverged states require
    manual recovery and block automatic recovery of the entire run.
    """
    if not isinstance(records, list) or len(records) > 2000 or not isinstance(current, dict) or not isinstance(backups, dict):
        raise ValueError('invalid recovery inputs')
    parsed, paths, sequences, backup_keys = [], [], set(), []
    for record in records:
        if not isinstance(record, (tuple, list)) or len(record) != 8:
            raise ValueError('invalid journal record')
        path, sequence, before_hash, before_mode, after_hash, after_mode, key, phase = record
        if type(sequence) is not int or sequence <= 0 or sequence in sequences:
            raise ValueError('invalid journal sequence')
        if phase not in ('prepared', 'replaced', 'restored'):
            raise ValueError('invalid journal phase')
        before, after = _state(before_hash, before_mode), _state(after_hash, after_mode)
        if before is None and after is None:
            raise ValueError('journal record has no before or after')
        if (before is None and key is not None) or (before is not None and not isinstance(key, str)):
            raise ValueError('invalid journal backup key')
        if key is not None:
            validate_paths([key])
            backup_keys.append(key)
        sequences.add(sequence)
        paths.append(path)
        parsed.append((path, sequence, before, after, key, phase))
    validate_paths(paths)
    validate_paths(backup_keys)
    if set(current) != set(paths):
        raise ValueError('current snapshot must explicitly cover every journal path')
    if any(value is not None and not isinstance(value, FileState) for value in current.values()):
        raise ValueError('invalid current snapshot')
    if any(not isinstance(value, FileState) for value in backups.values()):
        raise ValueError('invalid backup snapshot')
    steps = []
    for path, sequence, before, after, key, phase in sorted(parsed, key=lambda item: item[1], reverse=True):
        observed = current[path]
        if observed == before:
            action, reason = ('already_restored' if phase == 'restored' else 'mark_restored'), 'matches_before'
        elif phase == 'restored':
            action, reason = 'manual', 'restored_file_changed'
        elif observed != after:
            action, reason = 'manual', 'current_differs_from_before_and_after'
        elif before is None:
            action, reason = 'remove_new_file', 'matches_after'
        elif backups.get(key) != before:
            action, reason = 'manual', 'backup_missing_or_mismatch'
        else:
            action, reason = 'restore_backup', 'matches_after_and_backup'
        steps.append({'path': path, 'sequence': sequence, 'phase': phase,
                      'action': action, 'reason': reason, 'backup_key': key})
    return {'status': 'manual_required' if any(step['action'] == 'manual' for step in steps) else 'review_required',
            'write_authorized': False, 'full_tree_verified': False, 'steps': steps}


def inspect_journal_recovery(journal, lease, target: Path, backup_root: Path, *, max_file_bytes: int) -> dict:
    """Snapshot journaled files and backups to produce read-only recovery advice.

    The active lease must already be held. Parent roots, paths, hardlinks and
    known secret signatures are checked by the existing inventory code. This
    snapshot is racy relative to later writes and is not full-tree verification;
    no actual recovery, locking, lease takeover or authorization happens here.
    """
    records = journal.file_records(lease)
    paths = [record[0] for record in records]
    keys = [record[6] for record in records if record[6] is not None]
    target_root = _root_path(Path(target), must_exist=True)
    backups_root = _root_path(Path(backup_root), must_exist=True)
    target_states = snapshot_files(target_root, paths, max_file_bytes=max_file_bytes)
    backup_states = snapshot_files(backups_root, keys, max_file_bytes=max_file_bytes)
    report = analyze_recovery(records, {path: target_states.get(path) for path in paths}, backup_states)
    report['snapshot_scope'] = 'journaled_paths_only'
    report['snapshot_is_lock'] = False
    return report
