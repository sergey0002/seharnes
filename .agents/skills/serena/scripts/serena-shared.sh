#!/usr/bin/env bash
# One Serena per project. Editors attach over streamable HTTP instead of
# each spawning their own language server.
#
# Project isolation:
#   - port is derived from the project root, so two projects never share it;
#   - an owner file records which root owns a port; a foreign server on the
#     same port is skipped instead of silently served;
#   - SERENA_PORT overrides the automatic choice for manual setups.
set -euo pipefail

HOST="${SERENA_HOST:-127.0.0.1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
ROOT="$(find_project_root "$SCRIPT_DIR")" || { echo "serena: project root not found" >&2; exit 1; }
RUN_DIR="${HOME}/.local/state/serena-shared"
mkdir -p "${RUN_DIR}"

ROOT_HASH="$(printf '%s' "${ROOT}" | cksum | cut -d' ' -f1)"
BASE_PORT="${SERENA_PORT:-$((9200 + ROOT_HASH % 90))}"
LOCK="${RUN_DIR}/serena-${ROOT_HASH}.lock"

owner_file() { echo "${RUN_DIR}/serena-${1:-}.project"; }
pid_file()   { echo "${RUN_DIR}/serena-${1:-}.pid"; }
log_file()   { echo "${RUN_DIR}/serena-${1:-}.log"; }

listening() {
  local port="${1:-}"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -q ":${port} "
    return $?
  fi
  (echo >/dev/tcp/127.0.0.1/"${port}") >/dev/null 2>&1
}

start_server() {
  local port="${1:-}"
  setsid nohup uvx --from git+https://github.com/oraios/serena \
    serena start-mcp-server \
    --transport streamable-http \
    --host "${HOST}" \
    --port "${port}" \
    --project "${ROOT}" \
    --context desktop-app \
    --open-web-dashboard false \
    >>"$(log_file "$port")" 2>&1 < /dev/null &
  echo $! >"$(pid_file "$port")"
}

pick_port() {
  local offset port
  for offset in $(seq 0 30); do
    port=$((BASE_PORT + offset))
    if (( port > 9299 )); then
      port=$((9200 + port - 9300))
    fi
    if listening "$port"; then
      if [[ "$(cat "$(owner_file "$port")" 2>/dev/null || true)" == "${ROOT}" ]]; then
        echo "$port"
        return 0
      fi
      continue
    fi
    start_server "$port"
    local i
    for i in $(seq 1 60); do
      listening "$port" && break
      sleep 0.5
    done
    if listening "$port"; then
      echo "${ROOT}" >"$(owner_file "$port")"
      echo "$port"
      return 0
    fi
  done
  return 1
}

exec 9>"${LOCK}"
flock 9
PORT="$(pick_port || true)"
[[ -n "${PORT}" ]] || {
  echo "serena-shared: no free port for ${ROOT}, see ${RUN_DIR}" >&2
  exit 1
}
flock -u 9

URL="http://${HOST}:${PORT}/mcp"

exec env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
  -u http_proxy -u https_proxy -u all_proxy \
  -u NO_PROXY -u no_proxy \
  uvx mcp-proxy --transport streamablehttp "${URL}"
