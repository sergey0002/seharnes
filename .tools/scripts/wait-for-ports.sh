#!/usr/bin/env bash
# Wait until the given TCP ports on 127.0.0.1 accept connections.
# Used as ExecStartPre so clients do not race a still-loading MCP server.
set -u

TIMEOUT="${MCP_WAIT_TIMEOUT:-120}"
port_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- && return 0
  return 1
}

for port in "$@"; do
  for _ in $(seq 1 "${TIMEOUT}"); do
    port_open "${port}" && break
    sleep 1
  done
  if port_open "${port}"; then
    echo "port ${port}: ready"
  else
    echo "port ${port}: not ready after ${TIMEOUT}s, continuing" >&2
  fi
done

exit 0
