#!/usr/bin/env python3
"""Prepare a per-project CodePrism systemd user unit without installing it."""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shlex
import socket
import sys
import tempfile


def unit_quote(value, exec_argument=False):
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("control characters in paths are not supported")
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    return '"' + (value.replace('$', '$$') if exec_argument else value) + '"'


def main():
    parser = argparse.ArgumentParser(description="Prepare a CodePrism user unit; never install or start it.")
    parser.add_argument("project", help="existing project root (symlinks resolved)")
    parser.add_argument("port", type=int, help="HTTP port, 1-65535")
    parser.add_argument("--output-dir", required=True, help="existing directory for the user unit")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        root = Path(args.project).resolve(strict=True)
        output = Path(args.output_dir).resolve(strict=True)
        if not root.is_dir() or not output.is_dir():
            raise ValueError("project and output directory must be directories")
        python = root / '.cursor/tools/codeprism-ai/venv/bin/python'
        server = root / '.agents/skills/codeprism/scripts/codeprism_serve.py'
        if not python.is_file() or not os.access(python, os.X_OK) or not server.is_file():
            raise ValueError("project Python or codeprism_serve.py is missing")
        root_text = str(root)
        identity = hashlib.sha256(os.fsencode(root_text)).hexdigest()
        name = 'mcp-codeprism-' + identity + '.service'
        target = output / name
        content = (f'# CodePrism project-sha256={identity} port={args.port}\n'
                   '[Unit]\nDescription=CodePrism MCP per project\nAfter=network.target\n\n'
                   f'[Service]\nType=simple\nWorkingDirectory={root_text.replace("%", "%%")}\n'
                   f'ExecStart={unit_quote(str(python), True)} {unit_quote(str(server), True)} '
                   f'{unit_quote(root_text, True)} --transport http --port {args.port}\n'
                   'Restart=on-failure\nRestartSec=3\n\n[Install]\nWantedBy=default.target\n')
        directory_fd = os.open(str(output), os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            for existing in output.glob('mcp-codeprism-*.service'):
                if existing == target:
                    continue
                if existing.is_symlink() or not existing.is_file():
                    raise ValueError(f"cannot inspect existing unit safely: {existing}")
                first = existing.read_text(encoding='utf-8').splitlines()[:1]
                if not first or not re.fullmatch(r'# CodePrism project-sha256=[0-9a-f]{64} port=[0-9]+', first[0]):
                    raise ValueError(f"unrecognized CodePrism unit: {existing}")
                if first[0].endswith(f' port={args.port}'):
                    raise ValueError(f"port {args.port} already registered: {existing}")
            if target.is_symlink():
                raise ValueError(f"refusing symlink: {target}")
            if target.exists():
                if not target.is_file() or target.read_text(encoding='utf-8') != content:
                    raise ValueError(f"existing unit differs, refusing overwrite: {target}")
                status = 'unchanged'
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    try:
                        probe.bind(('127.0.0.1', args.port))
                    except OSError as exc:
                        raise ValueError(f"port {args.port} unavailable: {exc}") from exc
                fd, temporary = tempfile.mkstemp(prefix='.codeprism-', dir=str(output))
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as file:
                        file.write(content)
                    os.chmod(temporary, 0o644)
                    os.link(temporary, str(target), follow_symlinks=False)
                finally:
                    os.unlink(temporary)
                status = 'created'
        finally:
            os.close(directory_fd)
        print(f'{status}: {target}\nproject: {root}\nport: {args.port}')
        if output != Path.home() / '.config/systemd/user':
            print('Install manually after review:')
            print('  mkdir -p -- "$HOME/.config/systemd/user"')
            print(f'  cp -n -- {shlex.quote(str(target))} "$HOME/.config/systemd/user/{name}"')
            print('  Compare the installed unit with the staged unit before starting it.')
        print(f'  systemctl --user daemon-reload\n  systemctl --user enable --now {name}')
        print('Check that codeprism_serve.py supports --transport http --port before starting.')
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
