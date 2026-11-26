#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
EXCLUDED = {'.tools/hermes', '.tools/openhands', '.tools/disk-scan',
            '.codegraph', '.doc/web/state', '.workspace-setup.started',
            '.workspace-ready.json'}
PATTERNS = ('*.pid', '*.pid.lock', '*.runtime.lock', '*.sock', '*-wal', '*-shm')


def excluded(relative):
    parts = relative.parts
    return ('.git' in parts or any(
        Path(*parts[:i]).as_posix() in EXCLUDED
        for i in range(1, len(parts) + 1)) or any(
        fnmatch.fnmatch(part, pattern) for part in parts for pattern in PATTERNS))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve(strict=True)
    given_target = Path(args.target).absolute()
    target = given_target.resolve(strict=True)
    if given_target != target:
        raise ValueError('target must be a physical path')
    if (not source.is_dir() or not target.is_dir() or source == target
            or source in target.parents or target in source.parents):
        raise ValueError('source and target must be separate directories')
    if any(p.name != '.git' for p in target.iterdir()):
        raise ValueError('target must be empty except its own .git')
    for tool in ('rsync', 'bash', 'python3', 'node'):
        if not shutil.which(tool):
            raise ValueError('missing dependency: ' + tool)

    def walk_error(error):
        raise error

    for base, dirs, files in os.walk(source, followlinks=False, onerror=walk_error):
        parent = Path(base)
        dirs[:] = [n for n in dirs if not excluded((parent / n).relative_to(source))]
        for name in dirs + files:
            path = parent / name
            relative = path.relative_to(source)
            if excluded(relative):
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                if os.path.isabs(os.readlink(path)):
                    raise ValueError('absolute source symlink: ' + str(relative))
                resolved = path.resolve(strict=True)
                if source not in resolved.parents or excluded(resolved.relative_to(source)):
                    raise ValueError('unsafe source symlink: ' + str(relative))
                if resolved.is_dir() and resolved in path.parents:
                    raise ValueError('ancestor source symlink: ' + str(relative))
            elif stat.S_ISREG(mode):
                with path.open('rb'):
                    pass
    started = target / '.workspace-setup.started'
    with started.open('x') as stream:
        stream.write('workspace-copy-v1\n')
    command = ['rsync', '--recursive', '--times', '--perms', '--links',
               '--no-devices', '--no-specials', '--exclude=.git']
    command += ['--exclude=/' + p for p in sorted(EXCLUDED)]
    command += ['--exclude=' + p for p in PATTERNS]
    subprocess.run(command + [str(source) + '/', str(target) + '/'], check=True)
    scripts = target / '.agents/skills/harness-router/children/environment-sync/scripts'
    env = dict(os.environ, HARNESS_SYNC_NO_PROMPT='1', PYTHONDONTWRITEBYTECODE='1')
    subprocess.run(['bash', str(scripts / 'sync-agent-views.sh'),
                    '--local-only', '--strict', '--replace-managed-mcp'],
                   cwd=target, env=env, check=True)
    subprocess.run([sys.executable, str(scripts / 'workspace-gate.py'),
                    '--prepare', '--source', str(source)], cwd=target, env=env, check=True)
    marker = {'schema': 1, 'root': str(target), 'source': str(source)}
    with (target / '.workspace-ready.json').open('x') as stream:
        json.dump(marker, stream)
        stream.write('\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print('workspace setup failed; no automatic retry or cleanup', file=sys.stderr)
        sys.exit(78)
