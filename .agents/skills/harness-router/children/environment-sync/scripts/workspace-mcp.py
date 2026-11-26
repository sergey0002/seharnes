#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
REL = Path('.agents/skills/harness-router/children/environment-sync/scripts')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', required=True,
                        choices=('git', 'phpstan-mcp', 'php-deps-mcp'))
    parser.add_argument('--loaded-env', action='store_true')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    script = root / REL / 'workspace-mcp.py'
    if Path(__file__).resolve() != script:
        raise ValueError('MCP wrapper does not belong to cwd')
    subprocess.run([sys.executable, str(root / REL / 'workspace-gate.py')],
                   cwd=root, check=True, stdout=subprocess.DEVNULL)
    config = json.loads((root / '.omp/mcp.json').read_text())
    server = config['mcpServers'][args.server]
    if server.get('enabled') is not True or server.get('type') != 'stdio':
        raise ValueError('MCP server is not enabled stdio')
    argv = [server['command'], *server.get('args', [])]
    environment = dict(os.environ)
    environment.update(server.get('env', {}))
    wrapper = str(root / '.tools/scripts/run-with-mcp-env.sh')
    has_wrapper = argv[:2] == ['bash', wrapper]
    if has_wrapper and not args.loaded_env:
        environment['MCP_ENV_FILE'] = str(root / '.cursor/mcp.env')
        os.execvpe('bash', ['bash', wrapper, sys.executable, str(script),
                          '--server', args.server, '--loaded-env'], environment)
    if has_wrapper:
        argv = argv[2:]
    environment.pop('MCP_ENV_FILE', None)
    environment['MCP_WORKSPACE'] = str(root)
    os.execvpe(argv[0], argv, environment)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print('workspace MCP refused', file=sys.stderr)
        sys.exit(78)
