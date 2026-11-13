#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
find_project_root() {
    local dir="${1:-}"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.cursor" ] || [ -d "$dir/.git" ]; then
            printf '%s\n' "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}
ROOT_DIR="$(find_project_root "$SCRIPT_DIR")" || { echo "codeprism: project root not found" >&2; exit 1; }
ROOT_DIR="$(cd -P "$ROOT_DIR" && pwd -P)"

URL="$(python3 - "$ROOT_DIR" "${CODEPRISM_TARGET:-$ROOT_DIR}" <<'PY'
import json
import os
import sys
from urllib.parse import urlsplit

root, target = sys.argv[1:]
try:
    if not os.path.isdir(target) or os.path.realpath(target) != os.path.realpath(root):
        raise ValueError('CODEPRISM_TARGET does not match configuration root')
    with open(os.path.join(root, '.cursor', 'mcp.json'), encoding='utf-8') as config:
        server = json.load(config)['mcpServers']['codeprism']
    if server.get('disabled') or server.get('enabled') is False:
        raise ValueError('codeprism is disabled in the project configuration')
    if server.get('type') != 'http':
        raise ValueError('codeprism type must be http')
    url = server['url']
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ValueError('invalid codeprism URL')
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username is not None or parsed.password is not None
            or parsed.fragment or parsed.port is None or not 1 <= parsed.port <= 65535
            or parsed.netloc != '127.0.0.1:' + str(parsed.port)):
        raise ValueError('codeprism URL must be http://127.0.0.1:<port>')
    print(url)
except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
    print('codeprism bridge: ' + str(error), file=sys.stderr)
    sys.exit(1)
PY
)"

exec uvx --offline mcp-proxy --transport streamablehttp "$URL"
