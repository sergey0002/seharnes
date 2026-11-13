#!/usr/bin/env bash
set -euo pipefail

# One store for every project and every launcher. The old default
# ~/.cache/codebase-memory-mcp is a symlink to the same directory.
: "${CBM_CACHE_DIR:=${HOME}/.local/share/mcp-stack/codebase-memory}"
export CBM_CACHE_DIR

find_binary() {
  local home="${HOME}"
  local candidate

  if [[ "${OS:-}" == "Windows_NT" ]] || [[ "$(uname -s 2>/dev/null || true)" == MINGW* ]]; then
    candidate="${home}/AppData/Local/Programs/codebase-memory-mcp/codebase-memory-mcp.exe"
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
    return 1
  fi

  for candidate in \
    "${home}/.local/bin/codebase-memory-mcp" \
    "${home}/AppData/Local/Programs/codebase-memory-mcp/codebase-memory-mcp.exe"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  if [[ -d /mnt/c/Users ]]; then
    local user
    for user in /mnt/c/Users/*; do
      case "$(basename "${user}")" in
        Public|Default|"Default User"|"All Users") continue ;;
      esac
      candidate="${user}/AppData/Local/Programs/codebase-memory-mcp/codebase-memory-mcp.exe"
      if [[ -f "${candidate}" ]]; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    done
  fi

  return 1
}

ui_port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -q ":${port} "
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "${port}" >/dev/null 2>&1
    return $?
  fi
  return 1
}

ensure_ui_daemon() {
  # Disabled auto-launch to prevent duplicate CBM instance eating ~7GB RAM in WSL.
  # Run codebase-memory-mcp-ui.sh manually if 3D web UI is needed.
  if [[ "${CBM_ENABLE_UI:-0}" != "1" ]]; then
    return 0
  fi

  local binary="$1"
  local port="${CBM_UI_PORT:-9749}"
  local session="${CBM_UI_TMUX_SESSION:-cbm-ui}"

  if ui_port_listening "${port}"; then
    return 0
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    echo "codebase-memory-mcp: UI is down; install tmux or run .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh" >&2
    return 0
  fi

  if tmux has-session -t "${session}" 2>/dev/null; then
    return 0
  fi

  tmux new-session -d -s "${session}" "${binary} --ui=true --port=${port}"
}

is_ui_mode=false
for arg in "$@"; do
  if [[ "${arg}" == --ui=true ]]; then
    is_ui_mode=true
    break
  fi
done

BINARY="$(find_binary || true)"
if [[ -z "${BINARY}" ]]; then
  echo "codebase-memory-mcp: binary not found. See .doc/harnes/mcp/codebase-memory-mcp.md" >&2
  exit 127
fi

if [[ "${is_ui_mode}" == false ]]; then
  ensure_ui_daemon "${BINARY}"
fi

exec "${BINARY}" "$@"
