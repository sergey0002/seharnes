#!/usr/bin/env bash
set -euo pipefail

resolve_node() {
  if [[ -n "${NODE_BIN:-}" && -x "${NODE_BIN}" ]]; then
    printf '%s\n' "${NODE_BIN}"
    return 0
  fi

  if command -v node >/dev/null 2>&1; then
    command -v node
    return 0
  fi

  if [[ -x "${HOME}/.local/bin/node" ]]; then
    printf '%s\n' "${HOME}/.local/bin/node"
    return 0
  fi

  local candidate
  for candidate in "${HOME}"/.cursor-server/bin/*/node; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  if [[ -x "/mnt/c/Program Files/nodejs/node.exe" ]]; then
    printf '%s\n' "/mnt/c/Program Files/nodejs/node.exe"
    return 0
  fi

  echo "node-mcp.sh: Node.js not found (install node or set NODE_BIN in .cursor/mcp.env)" >&2
  return 127
}

NODE="$(resolve_node)"
exec "${NODE}" "$@"
