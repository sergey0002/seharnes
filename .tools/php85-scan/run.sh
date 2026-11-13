#!/usr/bin/env bash
# Запуск сканера PHP 8.5 в контейнере с PHP 7.1 (на хосте PHP нет).
#
#   bash .tools/php85-scan/run.sh
#
# Результат: .doc/migrations/php85/scan-report.json + вывод в консоль.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT/.doc/migrations/php85"
IMAGE="${PHP85_SCAN_IMAGE:-copytrust-dev-php7.1-cli}"

mkdir -p "$OUT_DIR"

docker run --rm \
  -v "$ROOT":/app \
  -w /app \
  "$IMAGE" \
  php -d memory_limit=2G .tools/php85-scan/scan.php /app /app/.doc/migrations/php85/scan-report.json
