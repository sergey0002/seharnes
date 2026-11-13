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
ROOT_DIR="$(find_project_root "$SCRIPT_DIR")" || { echo "codegraph: project root not found" >&2; exit 1; }

if ! command -v codegraph >/dev/null 2>&1; then
    for candidate in "$HOME"/.nvm/versions/node/*/bin/codegraph; do
        if [ -x "$candidate" ]; then
            PATH="$(dirname "$candidate"):$PATH"
            break
        fi
    done
fi

if ! command -v codegraph >/dev/null 2>&1; then
    echo "codegraph not found: install with npm i -g @colbymchenry/codegraph" >&2
    exit 127
fi

exec codegraph serve --mcp --path "$ROOT_DIR"
