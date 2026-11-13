#!/usr/bin/env bash
# Restore an MCP stack exported by export.sh on another machine or project root.
#
# Usage: restore.sh <archive.tar.gz> [project-root] [--no-start]
#   project-root  where the project lives on this machine (default: current dir)
#   --no-start    copy files only, do not enable or start systemd units
#
# CBM is one machine-level unit. Serena is one unit per project.
# CodeGraph is stdio; its local .codegraph index is rebuilt after restore.
set -euo pipefail

ARCHIVE="${1:-}"
if [[ -z "${ARCHIVE}" || ! -f "${ARCHIVE}" ]]; then
  echo "usage: restore.sh <archive.tar.gz> [project-root] [--no-start]" >&2
  exit 2
fi
shift

ROOT="$(pwd)"
START=1
for arg in "$@"; do
  case "${arg}" in
    --no-start) START=0 ;;
    *) ROOT="${arg}" ;;
  esac
done
ROOT="$(cd "${ROOT}" && pwd)"
SLUG="$(basename "${ROOT}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g')"
NEW_SERENA_UNIT="mcp-serena-${SLUG}.service"
CBM_UNIT="mcp-codebase-memory.service"

STACK="${HOME}/.local/share/mcp-stack"
UNIT_DIR="${HOME}/.config/systemd/user"
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT

tar -xzf "${ARCHIVE}" -C "${STAGE}"
manifest() { sed -n "s/^$1=//p" "${STAGE}/MANIFEST.txt" 2>/dev/null | head -1; }
OLD_ROOT="$(manifest project_root)"
OLD_SERENA_UNIT="$(manifest serena_unit)"
OLD_SERENA_PORT="$(manifest serena_port)"
ARCH_SERENA="${OLD_SERENA_UNIT:-$(basename "$(ls "${STAGE}"/units/mcp-serena-*.service 2>/dev/null | head -1)" 2>/dev/null || true)}"

# Never publish the source project's endpoint, even temporarily.
python3 - "${STAGE}/config/mcp.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as file:
    config = json.load(file)
server = config.get('mcpServers', {}).get('codeprism')
if server is not None:
    if not isinstance(server, dict):
        raise ValueError('invalid CodePrism configuration')
    server['disabled'] = True
    server.pop('url', None)
    print('note: CodePrism disabled; configure and confirm a project-specific server before enabling', file=sys.stderr)
with open(path, 'w', encoding='utf-8') as file:
    json.dump(config, file, indent=2, ensure_ascii=False)
    file.write('\n')
PY

if [[ -e "${ROOT}/.cursor/mcp.json" || -L "${ROOT}/.cursor/mcp.json" ]]; then
  echo "error: refusing to overwrite ${ROOT}/.cursor/mcp.json" >&2
  exit 1
fi

mkdir -p "${STACK}"/{codebase-memory,serena,logs} \
         "${UNIT_DIR}" "$HOME/.serena" \
         "${ROOT}/.serena" \
         "${ROOT}/.cursor/mcp-stack"

cp -an "${STAGE}/state/codebase-memory/." "${STACK}/codebase-memory/" 2>/dev/null || true
cp -an "${STAGE}/state/serena/." "$HOME/.serena/" 2>/dev/null || true
cp -an "${STAGE}/state/project-serena/." "${ROOT}/.serena/" 2>/dev/null || true

cp "${STAGE}/config/mcp.json" "${ROOT}/.cursor/mcp.json"
[[ -f "${STAGE}/config/mcp.env" ]] && cp -n "${STAGE}/config/mcp.env" "${ROOT}/.cursor/mcp.env"
if [[ -n "${OLD_ROOT}" && "${OLD_ROOT}" != "${ROOT}" ]]; then
  while IFS= read -r s; do
    [[ -f "${s}" ]] && sed -i "s#${OLD_ROOT}#${ROOT}#g" "${s}"
  done < <(find "${STAGE}/config/scripts" "${STAGE}/config/mcp-stack" -type f -name '*.sh' 2>/dev/null)
fi
restore_scripts_dir() {
  local name="$1" dest="$2"
  [[ -d "${STAGE}/config/scripts/${name}" ]] || return 0
  mkdir -p "${ROOT}/${dest}"
  cp -an "${STAGE}/config/scripts/${name}/." "${ROOT}/${dest}/" 2>/dev/null || true
}
restore_scripts_dir tools ".tools/scripts"
restore_scripts_dir codebase-memory-mcp ".agents/skills/codebase-memory-mcp/scripts"
restore_scripts_dir codegraph ".agents/skills/codegraph/scripts"
restore_scripts_dir codeprism ".agents/skills/codeprism/scripts"
restore_scripts_dir graphiti ".agents/skills/graphiti/scripts"
restore_scripts_dir jdocmunch ".agents/skills/jdocmunch/scripts"
restore_scripts_dir serena ".agents/skills/serena/scripts"
restore_scripts_dir phpstan-mcp ".agents/skills/phpstan-mcp/scripts"
cp -an "${STAGE}/config/mcp-stack/." "${ROOT}/.cursor/mcp-stack/" 2>/dev/null || true

# Machine-level units are installed only when missing.
CBM_INSTALLED=0
if [[ ! -f "${UNIT_DIR}/${CBM_UNIT}" && -f "${STAGE}/units/${CBM_UNIT}" ]]; then
  cp "${STAGE}/units/${CBM_UNIT}" "${UNIT_DIR}/${CBM_UNIT}"
  CBM_INSTALLED=1
fi

# Serena is per project: install under the new slug.
if [[ -n "${ARCH_SERENA}" && -f "${STAGE}/units/${ARCH_SERENA}" && ! -e "${UNIT_DIR}/${NEW_SERENA_UNIT}" && ! -L "${UNIT_DIR}/${NEW_SERENA_UNIT}" ]]; then
  cp "${STAGE}/units/${ARCH_SERENA}" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  SERENA_INSTALLED=1
  OLD_SS="${ARCH_SERENA#mcp-serena-}"; OLD_SS="${OLD_SS%.service}"
  sed -i "s#mcp-serena-${OLD_SS}#mcp-serena-${SLUG}#g" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  sed -i "s#Serena MCP (${OLD_SS})#Serena MCP (${SLUG})#g" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  echo "note: serena unit installed as ${NEW_SERENA_UNIT}" >&2
fi

# Absolute paths follow the project. Only newly installed units and project files.
if [[ -n "${OLD_ROOT}" && "${OLD_ROOT}" != "${ROOT}" ]]; then
  if [[ -n "${ARCH_SERENA}" && -f "${STAGE}/units/${ARCH_SERENA}" && "${SERENA_INSTALLED:-0}" -eq 1 ]]; then
    sed -i "s#${OLD_ROOT}#${ROOT}#g" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  fi
  if [[ "${CBM_INSTALLED}" -eq 1 ]]; then
    sed -i "s#${OLD_ROOT}#${ROOT}#g" "${UNIT_DIR}/${CBM_UNIT}"
  fi
  sed -i "s#${OLD_ROOT}#${ROOT}#g" "${ROOT}/.cursor/mcp.json" 2>/dev/null || true
  echo "note: project moved ${OLD_ROOT} -> ${ROOT}" >&2
  echo "note: codebase-memory DB keeps the old slug; reindex with index_repository" >&2
fi

# Serena port on this machine.
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
SPORT="${OLD_SERENA_PORT:-9121}"
if port_open "${SPORT}"; then
  for p in $(seq 9121 9199); do
    if ! port_open "${p}"; then SPORT="${p}"; break; fi
  done
fi
if [[ -n "${OLD_SERENA_PORT}" && "${SPORT}" != "${OLD_SERENA_PORT}" && "${SERENA_INSTALLED:-0}" -eq 1 ]]; then
  sed -i "s#--port ${OLD_SERENA_PORT}#--port ${SPORT}#g" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  sed -i "s#serena-${OLD_SERENA_PORT}.log#serena-${SPORT}.log#g" "${UNIT_DIR}/${NEW_SERENA_UNIT}"
  sed -i "s#127.0.0.1:${OLD_SERENA_PORT}/mcp#127.0.0.1:${SPORT}/mcp#g" "${ROOT}/.cursor/mcp.json" 2>/dev/null || true
  echo "note: serena port ${OLD_SERENA_PORT} busy, moved to ${SPORT}" >&2
fi

if [[ "${START}" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now "${CBM_UNIT}"
  if [[ -f "${UNIT_DIR}/${NEW_SERENA_UNIT}" ]]; then
    systemctl --user enable --now "${NEW_SERENA_UNIT}"
  fi
  echo "services enabled and started" >&2
fi

echo "restored to: ${ROOT}" >&2
echo "verify: bash ${ROOT}/.cursor/mcp-stack/verify.sh ${ROOT}" >&2
