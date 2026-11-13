#!/usr/bin/env bash
# .doc/web/start.sh - запуск сервиса copytrust-tools. Работает из WSL и Linux.
# Порт по умолчанию 8077, переопределение: WEB_PANEL_PORT=8090 ./start.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found; run install.sh --check and install Docker" >&2
  exit 1
fi

if [ ! -f .env ]; then
  ./install.sh --project >/dev/null
fi

HOST_UID="$(id -u)" HOST_GID="$(id -g)" docker compose -p copytrust-tools -f compose.tools.yml up -d
echo "service up: http://127.0.0.1:${WEB_PANEL_PORT:-8077}/"
