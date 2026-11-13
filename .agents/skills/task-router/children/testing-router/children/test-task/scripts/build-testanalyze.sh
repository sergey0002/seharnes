#!/usr/bin/env bash
# Обёртка: сборка .doc/testanalyze из корня репозитория.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../../../../" && pwd)"
cd "$ROOT"

exec python3 "$ROOT/.agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py" "$@"
