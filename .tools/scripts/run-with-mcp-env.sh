#!/usr/bin/env bash
set -euo pipefail

# Codex TOML has no Cursor-style envFile option. Load the project-local
# environment before starting a stdio MCP server instead.
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
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR" || true)"
ENV_FILE="${MCP_ENV_FILE:-${PROJECT_ROOT}/.cursor/mcp.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(tr -d '\r' < "${ENV_FILE}")
  set +a
fi

if [[ "$#" -eq 0 ]]; then
  echo "run-with-mcp-env.sh: command is required" >&2
  exit 2
fi

exec "$@"
