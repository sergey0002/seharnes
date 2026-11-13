#!/usr/bin/env bash
# Shared MCP server: one stdio MCP server exposed over Streamable HTTP for
# every client (Kilo, Cursor, dsh, Codex) instead of one process per client.
#
# Usage: mcp-shared-server.sh <port> <stdio command> [args...]
# Endpoint: http://127.0.0.1:<port>/mcp
set -euo pipefail

PORT="${1:-}"
if [[ -z "${PORT}" ]]; then
  echo "usage: mcp-shared-server.sh <port> <stdio command> [args...]" >&2
  exit 2
fi
shift

CACHE_ROOT="${HOME}/.cache/uv/archive-v0"

# Prefer the cached mcp-proxy binary: no PyPI round-trip on every boot.
find_proxy() {
  local hit
  hit="$(find "${CACHE_ROOT}" -maxdepth 4 -type f -path "*/bin/mcp-proxy" 2>/dev/null | head -n 1 || true)"
  [[ -n "${hit}" ]] && { printf '%s\n' "${hit}"; return 0; }
  return 1
}

PROXY_BIN="$(find_proxy || true)"

if [[ -n "${PROXY_BIN}" ]]; then
  exec "${PROXY_BIN}" --host 127.0.0.1 --port "${PORT}" --stateless -- "$@"
fi

exec uvx mcp-proxy --host 127.0.0.1 --port "${PORT}" --stateless -- "$@"
