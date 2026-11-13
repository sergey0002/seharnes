#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_node() {
  if command -v node >/dev/null 2>&1; then
    command -v node
    return
  fi
  if [ -x "/mnt/c/Program Files/nodejs/node.exe" ]; then
    echo "/mnt/c/Program Files/nodejs/node.exe"
    return
  fi
  return 1
}

NODE="$(resolve_node || true)"
if [ -n "$NODE" ]; then
  exec "$NODE" "$SCRIPT_DIR/php-docker.js" "$@"
fi

CONTAINER="${DOCKER_PHP_CONTAINER:-copytrust-dev-php-apache-1}"
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
REPO_ROOT="$(find_project_root "$SCRIPT_DIR")" || { echo "php-docker: project root not found" >&2; exit 1; }
LINUX_ROOT="/var/www/html"

args=()
for arg in "$@"; do
  case "$arg" in
    "$REPO_ROOT"/*)
      args+=("${LINUX_ROOT}/${arg#"$REPO_ROOT"/}")
      ;;
    *)
      args+=("$arg")
      ;;
  esac
done

exec docker exec -i "$CONTAINER" php "${args[@]}"
