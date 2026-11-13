#!/usr/bin/env bash
set -euo pipefail

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
ROOT_DIR="$(find_project_root "$SCRIPT_DIR")" || { echo "phpstan: project root not found" >&2; exit 1; }
IMAGE="${PHPSTAN_DOCKER_IMAGE:-copytrust-dev-php-apache:latest}"
MEMORY="${PHPSTAN_MEMORY_LIMIT:-1G}"
PHAR="/app/.cursor/tools/vendor/phpstan/phpstan/phpstan.phar"

if [[ ! -f "${ROOT_DIR}/.cursor/tools/vendor/phpstan/phpstan/phpstan.phar" ]]; then
  echo "phpstan-docker.sh: PHPStan phar not found. Run .cursor/setup.ps1 or composer install in .cursor/tools." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "phpstan-docker.sh: docker is required to run PHPStan in the application image." >&2
  exit 2
fi

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  context="${ROOT_DIR}/.tools/docker-dev/php-apache"
  if [[ "${PHPSTAN_AUTO_BUILD:-1}" == "1" && "${IMAGE}" == "copytrust-dev-php-apache:latest" && -f "${context}/Dockerfile" ]]; then
    echo "phpstan-docker.sh: image ${IMAGE} missing, building from ${context}" >&2
    if ! docker build -t "${IMAGE}" "${context}" >&2; then
      echo "phpstan-docker.sh: application image build failed" >&2
      exit 2
    fi
  fi
  if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
    echo "phpstan-docker.sh: image ${IMAGE} not found." >&2
    if [[ "${IMAGE}" == "copytrust-dev-php-apache:latest" ]]; then
      echo "phpstan-docker.sh: build it with: docker build -t ${IMAGE} ${context}" >&2
    else
      echo "phpstan-docker.sh: provision the configured image; custom tags are not rebuilt automatically" >&2
    fi
    echo "phpstan-docker.sh: or set another tag in PHPSTAN_DOCKER_IMAGE in .cursor/mcp.env" >&2
    echo "phpstan-docker.sh: auto-build can be disabled with PHPSTAN_AUTO_BUILD=0" >&2
    exit 2
  fi
fi

exec docker run --rm \
  -v "${ROOT_DIR}:/app" \
  -w /app \
  -e HOME=/tmp \
  "${IMAGE}" \
  php -d "memory_limit=${MEMORY}" "${PHAR}" "$@"
