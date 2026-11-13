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
TASK="${1:-}"
LEVEL="${2:-0}"

if [[ -z "${TASK}" ]]; then
  BRANCH="$(git -C "${ROOT_DIR}" branch --show-current 2>/dev/null || true)"
  TASK="$(printf '%s' "${BRANCH}" | sed -n 's/.*[#]\([0-9][0-9]*\).*/\1/p')"
fi

if [[ ! "${TASK}" =~ ^[0-9]+$ ]]; then
  echo "usage: phpstan-task.sh <task-number> [level]" >&2
  exit 2
fi

cd "${ROOT_DIR}"

collect_files() {
  local diff_file=".doc/tasks/${TASK}/diff.files.md"
  if [[ -f "${diff_file}" ]]; then
    sed -n 's/^`\{0,1\}\([A-Za-z0-9_][A-Za-z0-9_./-]*\.php\)`\{0,1\}[[:space:]]*$/\1/p' "${diff_file}"
  fi
  git diff --name-only --diff-filter=ACMRT 2>/dev/null || true
  git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || true
  git ls-files --others --exclude-standard 2>/dev/null || true
}

FILES=()
while IFS= read -r file; do
  file="${file#./}"
  case "${file}" in
    vendor/* | node_modules/* | templates_c/* | .tools/* | .kilo/* | .cursor/* | .git/*) continue ;;
  esac
  [[ -f "${file}" ]] && FILES+=("${file}")
done < <(collect_files | tr -d '\r' | grep -E '\.php$' || true)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "phpstan-task.sh: no PHP files for task ${TASK}" >&2
  exit 0
fi

mapfile -t UNIQUE < <(printf '%s\n' "${FILES[@]}" | awk '!seen[$0]++')

echo "phpstan-task.sh: task ${TASK}, level ${LEVEL}, files ${#UNIQUE[@]}" >&2
printf ' - %s\n' "${UNIQUE[@]}" >&2

exec "${SCRIPT_DIR}/phpstan-docker.sh" analyze \
  -c /app/.cursor/tools/phpstan.neon \
  --no-progress \
  --error-format=raw \
  --level="${LEVEL}" \
  "${UNIQUE[@]}"
