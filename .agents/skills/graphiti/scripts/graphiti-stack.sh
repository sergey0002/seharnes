#!/usr/bin/env bash
# Graphiti MCP stack: FalkorDB + Graphiti MCP server.
# Embeddings are served by the local Ollama service on port 11434.
#
# Usage: graphiti-stack.sh [up|down|restart|status|logs|verify]
#
# Secrets are read from .cursor/mcp.env. The stack listens on 127.0.0.1 only:
# 8000 MCP (HTTP), 3000 FalkorDB browser. Ollama on 11434 is a separate service.
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
ROOT_DIR="$(find_project_root "$SCRIPT_DIR")" || { echo "graphiti: project root not found" >&2; exit 1; }
STACK_DIR="${ROOT_DIR}/.cursor/mcp-stack/graphiti"
ENV_FILE="${ROOT_DIR}/.cursor/mcp.env"
COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${STACK_DIR}/docker-compose.yml")

usage() {
    cat <<'EOF'
Usage: graphiti-stack.sh [command]

  up       Start FalkorDB and Graphiti MCP, wait for health
  down     Stop and remove the stack containers
  restart  Recreate the stack containers
  status   Show container status and MCP health
  logs     Follow stack logs
  verify   Check health endpoint and MCP tools/list
EOF
}

wait_health() {
    local attempt
    for attempt in $(seq 1 60); do
        if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
            echo "graphiti: healthy on http://127.0.0.1:8000/mcp/"
            return 0
        fi
        sleep 3
    done
    echo "graphiti: health timeout, see graphiti-stack.sh logs" >&2
    return 1
}

verify() {
    local health tools
    health="$(curl -fsS --max-time 10 http://127.0.0.1:8000/health 2>/dev/null || true)"
    if [[ -z "${health}" ]]; then
        echo "FAIL  health endpoint http://127.0.0.1:8000/health" >&2
        return 1
    fi
    echo "PASS  health ${health}"

    tools="$(curl -sS --max-time 30 -X POST http://127.0.0.1:8000/mcp/ \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json, text/event-stream' \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"graphiti-verify","version":"1.0"}}}' 2>/dev/null || true)"

    if printf '%s' "${tools}" | grep -q '"serverInfo"'; then
        echo "PASS  MCP initialize"
    else
        echo "FAIL  MCP initialize" >&2
        return 1
    fi
}

case "${1:-status}" in
    up)
        "${COMPOSE[@]}" up -d
        wait_health
        ;;
    down)
        "${COMPOSE[@]}" down
        ;;
    restart)
        "${COMPOSE[@]}" up -d --force-recreate
        wait_health
        ;;
    status)
        "${COMPOSE[@]}" ps
        curl -fsS --max-time 5 http://127.0.0.1:8000/health 2>/dev/null || echo "health: unavailable"
        ;;
    logs)
        "${COMPOSE[@]}" logs -f --tail=200
        ;;
    verify)
        verify
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
