#!/usr/bin/env bash
# Export every MCP config, unit and state file into one portable archive.
#
# Usage: export.sh [output.tar.gz]
# Default output: ~/mcp-stack-export-YYYYmmdd-HHMM.tar.gz
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$HOME/mcp-stack-export-$(date +%Y%m%d-%H%M).tar.gz}"
SLUG="$(basename "${ROOT}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g')"
CBM_SLUG="$(printf '%s' "${ROOT}" | sed 's#^/##; s#/#-#g')"
STACK="${HOME}/.local/share/mcp-stack"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE"/{config/scripts,units,state/codebase-memory,state/serena,state/project-serena}

cp "$ROOT/.cursor/mcp.json" "$STAGE/config/mcp.json"
[[ -f "$ROOT/.cursor/mcp.env" ]] && cp "$ROOT/.cursor/mcp.env" "$STAGE/config/mcp.env"

mkdir -p "$STAGE/config/mcp-stack"
cp "$ROOT"/.cursor/mcp-stack/*.sh "$STAGE/config/mcp-stack/" 2>/dev/null || true
[[ -f "$ROOT/.cursor/mcp-stack/add-codeprism.py" ]] && cp "$ROOT/.cursor/mcp-stack/add-codeprism.py" "$STAGE/config/mcp-stack/"
# Stack directories hold config that the .sh wrappers cannot recreate:
# graphiti/config.yaml and docker-compose.yml. Graph data itself is not exported.
for d in graphiti; do
  [[ -d "$ROOT/.cursor/mcp-stack/$d" ]] && cp -a "$ROOT/.cursor/mcp-stack/$d" "$STAGE/config/mcp-stack/"
done

copy_scripts_dir() {
  local name="${1:-}" source="${2:-}"
  [[ -d "$source" ]] || return 0
  mkdir -p "$STAGE/config/scripts/$name"
  cp -a "$source"/. "$STAGE/config/scripts/$name/"
}
copy_scripts_dir tools "$ROOT/.tools/scripts"
copy_scripts_dir codebase-memory-mcp "$ROOT/.agents/skills/codebase-memory-mcp/scripts"
copy_scripts_dir codegraph "$ROOT/.agents/skills/codegraph/scripts"
copy_scripts_dir codeprism "$ROOT/.agents/skills/codeprism/scripts"
copy_scripts_dir graphiti "$ROOT/.agents/skills/graphiti/scripts"
copy_scripts_dir jdocmunch "$ROOT/.agents/skills/jdocmunch/scripts"
copy_scripts_dir serena "$ROOT/.agents/skills/serena/scripts"
copy_scripts_dir phpstan-mcp "$ROOT/.agents/skills/phpstan-mcp/scripts"

for u in "$HOME/.config/systemd/user/mcp-codebase-memory.service" \
         "$HOME/.config/systemd/user/mcp-serena-${SLUG}.service"; do
  [[ -f "$u" ]] && cp "$u" "$STAGE/units/"
done

# codebase-memory indexes (project DBs + config), no logs
for f in "$STACK/codebase-memory/${CBM_SLUG}.db" "$STACK/codebase-memory/_config.db" "$STACK/codebase-memory/config.json"; do
  [[ -f "$f" ]] && cp "$f" "$STAGE/state/codebase-memory/"
done

# CodeGraph index is local and rebuilt with codegraph init, not exported.

# serena: config and memories only; language_servers are re-downloaded
[[ -f "$HOME/.serena/serena_config.yml" ]] && cp "$HOME/.serena/serena_config.yml" "$STAGE/state/serena/"
[[ -d "$HOME/.serena/memories" ]] && cp -a "$HOME/.serena/memories" "$STAGE/state/serena/"

# per-project serena state, cache excluded
for f in project.yml project.local.yml; do
  [[ -f "$ROOT/.serena/$f" ]] && cp "$ROOT/.serena/$f" "$STAGE/state/project-serena/"
done
[[ -d "$ROOT/.serena/memories" ]] && cp -a "$ROOT/.serena/memories" "$STAGE/state/project-serena/"

{
  echo "exported_at=$(date -Iseconds)"
  echo "project_root=$ROOT"
  echo "project_branch=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo "project_head=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "project_slug=${SLUG}"
  echo "codegraph_db=${ROOT}/.codegraph/codegraph.db"
  echo "serena_unit=mcp-serena-${SLUG}.service"
  echo "serena_port=$(grep -oE '127\.0\.0\.1:[0-9]+' "$HOME/.config/systemd/user/mcp-serena-${SLUG}.service" 2>/dev/null | head -1 | cut -d: -f2)"
  echo "cbm_slug=${CBM_SLUG}"
  echo "cbm_store=$STACK/codebase-memory"
  echo "mcp_endpoints=codebase-memory:9131,serena:auto,codegraph:stdio"
} > "$STAGE/MANIFEST.txt"

tar -czf "$OUT" -C "$STAGE" .
echo "$OUT"
