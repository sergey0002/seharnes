#!/usr/bin/env python3
"""Check whether essential harness files can be seen by a release repository.

This read-only diagnostic does not create a release manifest, scan secrets,
stage files, change excludes, authenticate remotes or prove kit completeness.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from transfer_plan import _root_path

WITNESSES = ('.agents/skills/harness-router/SKILL.md', '.cursor/rules/harness-improvement.mdc',
             '.cursor/mcp.json', '.doc/harnes/state/canon-paths.yaml', '.doc/web/README.md', 'AGENTS.md')


def check_release_repo(root: Path) -> dict:
    root = _root_path(root, must_exist=True)
    git = shutil.which('git')
    if not git:
        raise ValueError('git unavailable')
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    def run(*args, data=None):
        try:
            return subprocess.run([git, '-C', str(root), *args], input=data, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env=env, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError('Git inspection failed') from error
    top = run('rev-parse', '--show-toplevel')
    if top.returncode != 0:
        raise ValueError('not a Git working tree')
    try:
        toplevel = Path(os.fsdecode(top.stdout.rstrip(b'\r\n'))).resolve(strict=True)
    except (OSError, ValueError) as error:
        raise ValueError('invalid Git working tree root') from error
    if toplevel != root:
        raise ValueError('target must be the Git working tree root')
    output = run('check-ignore', '--no-index', '--verbose', '--non-matching', '-z', '--stdin',
                 data=b''.join(path.encode('utf-8') + b'\0' for path in WITNESSES))
    if output.returncode not in (0, 1):
        raise ValueError('Git ignore inspection failed')
    fields = output.stdout.split(b'\0')
    if fields[-1:] != [b''] or len(fields) != len(WITNESSES) * 4 + 1:
        raise ValueError('unexpected Git ignore output')
    rows = []
    for index, expected in enumerate(WITNESSES):
        source, number, pattern, path = (os.fsdecode(x) for x in fields[index * 4:index * 4 + 4])
        if path != expected:
            raise ValueError('unexpected Git ignore path')
        # A negated matching rule is an explicit unignore, not an exclusion.
        ignored = bool(pattern) and not pattern.startswith('!')
        candidate = root / expected
        missing = not candidate.is_file() or candidate.is_symlink()
        rows.append({'path': path, 'status': 'missing' if missing else 'ignored' if ignored else 'visible',
                     'rule': {'source': source, 'line': number, 'pattern': pattern} if pattern else None})
    return {'status': 'failed' if any(row['status'] != 'visible' for row in rows) else 'witnesses_visible',
            'scope': 'fixed_witnesses_only', 'release_safe': False, 'files': rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='root of the intended release working tree')
    args = parser.parse_args()
    try:
        result = check_release_repo(args.root)
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['status'] == 'witnesses_visible' else 1


if __name__ == '__main__':
    raise SystemExit(main())
