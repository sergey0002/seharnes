#!/usr/bin/env bash
# .doc/web/stop.sh - остановка сервиса copytrust-tools.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
docker compose -p copytrust-tools -f compose.tools.yml down 2>/dev/null || true
echo "service stopped"
