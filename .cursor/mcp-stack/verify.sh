#!/usr/bin/env bash
# Verify the shared MCP stack and CodeGraph index for one project.
#
# Usage: verify.sh [project_root]
set -uo pipefail

ROOT="${1:-$(pwd)}"
ROOT="$(cd "${ROOT}" && pwd)"
SLUG="$(basename "${ROOT}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g')"
CBM_UNIT="mcp-codebase-memory"
FAIL=0

ok()   { printf 'PASS  %s\n' "${*}"; }
bad()  { printf 'FAIL  %s\n' "${*}"; FAIL=1; }
warn() { printf 'WARN  %s\n' "${*}"; }

post() {
  local port="${1:-}" body="${2:-}"
  curl -sS --max-time 45 -X POST "http://127.0.0.1:${port}/mcp" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d "${body}" 2>/dev/null
}

if [[ "$(systemctl --user is-active "${CBM_UNIT}" 2>/dev/null)" == "active" ]]; then
  ok "${CBM_UNIT} active"
else
  bad "${CBM_UNIT} not active"
fi

PROJECTS=""
for _ in 1 2 3 4; do
  PROJECTS="$(post 9131 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_projects","arguments":{}}}')"
  printf '%s' "${PROJECTS}" | grep -q "${ROOT}" && break
  sleep 3
done
if printf '%s' "${PROJECTS}" | grep -q "${ROOT}"; then
  ok "CBM 9131 видит ${ROOT}"
else
  bad "CBM 9131 не видит ${ROOT} (нужен index_repository)"
fi

if [[ -f "${ROOT}/.codegraph/codegraph.db" ]]; then
  ok "CodeGraph index ${ROOT}/.codegraph/codegraph.db"
  if command -v codegraph >/dev/null 2>&1; then
    CG_STATUS="$(codegraph status --json "${ROOT}" 2>/dev/null || true)"
    if printf '%s' "${CG_STATUS}" | grep -qE '"fileCount":[[:space:]]*[1-9]'; then
      ok "CodeGraph fileCount $(printf '%s' "${CG_STATUS}" | grep -oE '"fileCount":[[:space:]]*[0-9]+' | head -1)"
    else
      bad "CodeGraph status для ${ROOT}"
    fi
  else
    warn "codegraph CLI не найден в PATH; проверьте npm i -g @colbymchenry/codegraph"
  fi
else
  bad "нет ${ROOT}/.codegraph/codegraph.db (нужен codegraph init --yes)"
fi

if [[ ! -x "${ROOT}/.cursor/tools/codeprism-ai/venv/bin/python" ]]; then
  bad "CodePrism не проверен: окружение отсутствует"
elif ! "${ROOT}/.cursor/tools/codeprism-ai/venv/bin/python" - "${ROOT}" <<'PY'
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fastmcp import Client

root = Path(sys.argv[1]).resolve()

try:
    with (root / '.cursor/mcp.json').open(encoding='utf-8') as file:
        servers = json.load(file)['mcpServers']
    server = servers.get('codeprism')
    if server is None:
        print('WARN  CodePrism отсутствует в конфигурации; не проверен')
    else:
        if server.get('disabled') or server.get('enabled') is False:
            raise ValueError('CodePrism отключен; сервер проекта не проверен')
        url = server['url']
        parsed = urlsplit(url)
        if server.get('type') != 'http' or parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.port is None or parsed.username or parsed.password:
            raise ValueError('CodePrism должен использовать локальный HTTP endpoint')

        async def verify():
            async with Client(url) as client:
                result = await client.call_tool('get_graph_stats', {'path': '.'})
                data = result.structured_content or result.data
                if result.is_error or not isinstance(data, dict) or Path(data['project_path']).resolve() != root or data.get('index_status') != 'ready':
                    raise ValueError('сервер вернул другой проект или индекс не готов')

        asyncio.run(asyncio.wait_for(verify(), timeout=15))
        print(f'PASS  CodePrism HTTP обслуживает {root}')
except Exception as error:
    print(f'FAIL  CodePrism не проверен: {error}')
    sys.exit(1)
PY
then
  FAIL=1
fi

if systemctl --user is-active mcp-graphify >/dev/null 2>&1; then
  warn "legacy mcp-graphify все еще active; остановите: systemctl --user disable --now mcp-graphify"
fi

SERENA_UNIT="mcp-serena-${SLUG}"
SERENA_FILE="${HOME}/.config/systemd/user/${SERENA_UNIT}.service"
if [[ -f "${SERENA_FILE}" ]]; then
  SPORT="$(grep -oE '127\.0\.0\.1:[0-9]+' "${SERENA_FILE}" | head -1 | cut -d: -f2 || true)"
  if [[ "$(systemctl --user is-active "${SERENA_UNIT}" 2>/dev/null)" == "active" ]] && (exec 3<>"/dev/tcp/127.0.0.1/${SPORT}") 2>/dev/null; then
    ok "serena ${SPORT} (${SERENA_UNIT})"
  else
    bad "serena ${SERENA_UNIT} не active или порт ${SPORT} закрыт"
  fi
else
  warn "нет юнита ${SERENA_UNIT}; serena не вынесена в общий HTTP"
fi

CMB="$(ps -eo args= | grep -F -- 'codebase-memory-mcp --ui=false' | grep -v "[g]rep" | wc -l)"
if [[ "${CMB}" -gt 1 ]]; then
  warn "codebase-memory-mcp процессов: ${CMB} (ожидается 1 shared; остальные - stdio клиенты до reload)"
fi

echo
if [[ "${FAIL}" -eq 0 ]]; then
  echo "MCP stack: OK (${SLUG})"
else
  echo "MCP stack: FAIL (${SLUG})"
fi
exit "${FAIL}"
