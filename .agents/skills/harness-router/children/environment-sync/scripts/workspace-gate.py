#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
REL = Path('.agents/skills/harness-router/children/environment-sync/scripts')


def mentions_source(value, source):
    """Match the source path as a whole path segment, not as a name prefix."""
    pattern = re.escape(source.rstrip('/')) + r'(?=[/\\\s"\']|$)'
    return re.search(pattern, value) is not None


def check(root, source):
    if Path(__file__).resolve() != root / REL / 'workspace-gate.py':
        raise ValueError('gate does not belong to cwd')
    for name in ('.agents', '.cursor', '.tools'):
        if (root / name).is_symlink():
            raise ValueError('linked harness root')
    for relative in ('.tools/scripts/run-with-mcp-env.sh',
                     '.tools/scripts/node-mcp.sh',
                     '.tools/mcp-servers/php-toolchain/server.js',
                     '.agents/skills/phpstan-mcp/scripts/phpstan-task.sh',
                     '.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh'):
        path = root / relative
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
            raise ValueError('missing local entrypoint')
    subprocess.run([sys.executable, str(root / REL / 'render_agent_views.py'),
                    '--root', str(root), '--check'], cwd=root, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Check the effective managed argv/env/cwd, not secret files or prose.
    from importlib.machinery import SourceFileLoader
    module = SourceFileLoader('workspace_omp', str(root / REL / 'generate-omp-config.py')).load_module()
    generated = module.render_mcp(root)
    errors = module.check_mcp(root / '.omp/mcp.json', generated)
    if errors:
        raise ValueError('stale local MCP config')
    for server in generated['mcpServers'].values():
        if server.get('enabled') is False:
            continue
        values = [server.get('command', ''), server.get('cwd', ''),
                  *server.get('args', []), *server.get('env', {}).values()]
        if any(isinstance(value, str) and mentions_source(value, source) for value in values):
            raise ValueError('source path in managed MCP runtime')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--source')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.prepare:
        if not args.source or args.command:
            raise ValueError('prepare requires source and no command')
        source = args.source
    else:
        marker = root / '.workspace-ready.json'
        if marker.is_symlink():
            raise ValueError('linked marker')
        data = json.loads(marker.read_text())
        if data.get('schema') != 1 or data.get('root') != str(root):
            raise ValueError('workspace not ready for this cwd')
        source = data['source']
    check(root, source)
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if command:
        os.execvp(command[0], command)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError):
        print('workspace prelaunch refused', file=sys.stderr)
        sys.exit(78)
