#!/usr/bin/env bash
# Prepare a project for CodeGraph and shared CBM.
#
# Usage: add-project.sh <project_root>
set -euo pipefail

ROOT="${1:-}"
if [[ -z "${ROOT}" ]]; then
    echo "usage: add-project.sh <project_root>" >&2
    exit 2
fi
ROOT="$(cd "${ROOT}" && pwd)"
DB="${ROOT}/.codegraph/codegraph.db"

if [[ ! -f "${DB}" ]]; then
    echo "нет индекса CodeGraph: ${DB}" >&2
    echo "создайте: codegraph init --yes ${ROOT}" >&2
    exit 1
fi

cat <<EOF

Проект готов для CodeGraph и CBM
  index:  ${DB}
  CBM:    index_repository(repo_path="${ROOT}")
  projectPath для CodeGraph: ${ROOT}

Проверка:
  bash .cursor/mcp-stack/verify.sh ${ROOT}
EOF
