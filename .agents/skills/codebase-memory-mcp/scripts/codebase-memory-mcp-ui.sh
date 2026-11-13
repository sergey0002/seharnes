#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${CBM_UI_PORT:-9749}"
SESSION="${CBM_UI_TMUX_SESSION:-cbm-ui}"

if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  echo "codebase-memory-mcp UI already listening on http://127.0.0.1:${PORT}/"
  exit 0
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required to keep UI running in background on WSL/Linux" >&2
  exit 1
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  tmux kill-session -t "${SESSION}"
fi

# Reuse launcher resolution, but keep UI in tmux instead of blocking this shell.
bash "${SCRIPT_DIR}/codebase-memory-mcp-launch.sh" --ui=true "--port=${PORT}" &
child_pid=$!
sleep 2

if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  echo "codebase-memory-mcp UI: http://127.0.0.1:${PORT}/"
  wait "${child_pid}"
  exit 0
fi

kill "${child_pid}" 2>/dev/null || true

binary="${HOME}/.local/bin/codebase-memory-mcp"
if [[ ! -f "${binary}" ]]; then
  echo "codebase-memory-mcp binary not found at ${binary}" >&2
  exit 127
fi

tmux new-session -d -s "${SESSION}" "${binary} --ui=true --port=${PORT}"
sleep 2

if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  echo "codebase-memory-mcp UI: http://127.0.0.1:${PORT}/ (tmux session: ${SESSION})"
  exit 0
fi

echo "Failed to start codebase-memory-mcp UI on port ${PORT}" >&2
exit 1
