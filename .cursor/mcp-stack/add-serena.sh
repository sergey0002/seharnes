#!/usr/bin/env bash
# Register a project as a shared Serena MCP endpoint (one systemd user unit).
#
# Usage: add-serena.sh <project_root> [port]
#   port  optional, default: first free in 9121..9199
#
# Serena keeps one active project per process, so the unit is per project.
# Clients connect over HTTP; the number of clients does not add processes.
set -euo pipefail

ROOT="${1:-}"
PORT="${2:-}"
if [[ -z "${ROOT}" ]]; then
  echo "usage: add-serena.sh <project_root> [port]" >&2
  exit 2
fi
ROOT="$(cd "${ROOT}" && pwd)"
SLUG="$(basename "${ROOT}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g')"
UNIT="mcp-serena-${SLUG}"
UNIT_DIR="${HOME}/.config/systemd/user"
LOG_DIR="${HOME}/.local/state/mcp-shared"
SERENA="${HOME}/.local/bin/serena"

[[ -x "${SERENA}" ]] || { echo "нет ${SERENA}; установите: uv tool install git+https://github.com/oraios/serena" >&2; exit 1; }
[[ -d "${ROOT}/.serena" || -f "${ROOT}/.serena/project.yml" ]] || echo "warn: ${ROOT}/.serena нет, Serena создаст проект при первом activate_project" >&2

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/${1:-}") 2>/dev/null; }

if [[ -z "${PORT}" ]]; then
  for p in $(seq 9121 9199); do
    if ! port_open "${p}"; then PORT="${p}"; break; fi
  done
fi
[[ -n "${PORT}" ]] || { echo "нет свободного порта 9121-9199" >&2; exit 1; }
if port_open "${PORT}"; then
  echo "порт ${PORT} уже занят" >&2
  exit 1
fi

mkdir -p "${UNIT_DIR}" "${LOG_DIR}"

cat >"${UNIT_DIR}/${UNIT}.service" <<EOF
[Unit]
Description=Serena MCP (${SLUG}) on 127.0.0.1:${PORT}
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
Environment="PATH=${PATH}"
ExecStart=${SERENA} start-mcp-server --transport streamable-http --host 127.0.0.1 --port ${PORT} --project ${ROOT} --context desktop-app --open-web-dashboard false
MemoryHigh=2G
MemoryMax=4G
CPUQuota=200%
TasksMax=512
Restart=always
RestartSec=3
StandardOutput=append:${LOG_DIR}/serena-${PORT}.log
StandardError=append:${LOG_DIR}/serena-${PORT}.log

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable "${UNIT}.service" >/dev/null
systemctl --user restart "${UNIT}.service"

for _ in $(seq 1 90); do
  port_open "${PORT}" && break
  sleep 2
done
if ! port_open "${PORT}"; then
  echo "сервис не поднял порт ${PORT}: systemctl --user status ${UNIT}" >&2
  exit 1
fi

cat <<EOF

Serena MCP для ${SLUG} поднят
  unit:     ${UNIT}.service
  endpoint: http://127.0.0.1:${PORT}/mcp

В ${ROOT}/.cursor/mcp.json:
  "serena": {
    "type": "http",
    "url": "http://127.0.0.1:${PORT}/mcp",
    "disabled": false
  }

Дальше перезагрузить клиента и проверить:
  bash .cursor/mcp-stack/verify.sh ${ROOT}
EOF
