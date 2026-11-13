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
PORT="${CODEGRAPH_UI_PORT:-}"
OPEN=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --open)
            OPEN=1
            shift
            ;;
        --port)
            PORT="${2:?--port requires a value}"
            shift 2
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

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

export CODEGRAPH_UI=1

ARGS=(ui --read-only)
if [ -n "$PORT" ]; then
    ARGS+=(--port "$PORT")
fi
if [ "$OPEN" -eq 0 ]; then
    ARGS+=(--no-open)
fi
ARGS+=("$ROOT_DIR")

exec codegraph "${ARGS[@]}"
