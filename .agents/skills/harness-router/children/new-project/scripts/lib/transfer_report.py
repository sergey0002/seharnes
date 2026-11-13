"""Directory summaries derived exclusively from a read-only preview."""
from __future__ import annotations

from collections import Counter

from transfer_inventory import validate_paths


def summarize_preview(rows: list[dict]) -> dict:
    """Count proposals recursively without equating a proposal with an action.

    Files protected before snapshotting are not represented. No claim about
    complete release coverage or bytes is made by this scoped report.
    """
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError("invalid preview rows")
    try:
        paths = [row['path'] for row in rows]
    except (KeyError, TypeError) as error:
        raise ValueError("invalid preview row") from error
    validate_paths(paths)
    directories: dict[str, dict] = {}
    for row in rows:
        try:
            proposal = row['proposal']
            status, action, review = proposal['status'], proposal['action'], proposal['requires_review']
            if not isinstance(status, str) or not status or not isinstance(action, str) or not action or type(review) is not bool:
                raise ValueError("invalid proposal")
            source, target = row['incoming'] is not None, row['target'] is not None
        except (KeyError, TypeError) as error:
            raise ValueError("invalid preview row") from error
        parts = row['path'].split('/')
        for directory in ['.'] + ['/'.join(parts[:i]) for i in range(1, len(parts))]:
            aggregate = directories.setdefault(directory, {'files': 0, 'incoming_files': 0, 'target_files': 0,
                                                           'review_files': 0, 'statuses': Counter(), 'actions': Counter()})
            aggregate['files'] += 1
            aggregate['incoming_files'] += source
            aggregate['target_files'] += target
            aggregate['review_files'] += review
            aggregate['statuses'][status] += 1
            aggregate['actions'][action] += 1
    return {'scope': 'selected_files_only', 'sizes': 'not_collected',
            'directories': {key: {**value, 'statuses': dict(sorted(value['statuses'].items())),
                                  'actions': dict(sorted(value['actions'].items()))}
                            for key, value in sorted(directories.items())}}
