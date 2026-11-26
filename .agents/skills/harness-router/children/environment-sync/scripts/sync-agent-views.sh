#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../../../../.." && pwd)"
cd "$ROOT_DIR"
LOCAL_ONLY="${HARNESS_SYNC_LOCAL_ONLY:-0}"
ALLOW_DRIFT=0
RENDER_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --local-only) LOCAL_ONLY=1 ;;
        --install-windows-mcp) : ;;
        --replace-managed-mcp) RENDER_ARGS+=("$arg") ;;
        --allow-drift) ALLOW_DRIFT=1 ;;
        --strict) ALLOW_DRIFT=0 ;;
        *) printf 'Unknown sync option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

ACTIVE="$(python3 "$SCRIPT_DIR/environment_policy.py" --root "$ROOT_DIR" --list-enabled-shell)"
enabled() { [[ " $ACTIVE " == *" $1 "* ]]; }
python3 "$SCRIPT_DIR/render_agent_views.py" --root "$ROOT_DIR" "${RENDER_ARGS[@]}"

NATIVE_MCP_ARTIFACT="$ROOT_DIR/.doc/skil_data/harness-router/antigravity_mcp_config.json"
WINDOWS_WSL_ARTIFACT="$ROOT_DIR/.doc/skil_data/harness-core/antigravity_mcp_config.windows-wsl.json"
if enabled agents && [[ "$LOCAL_ONLY" != 1 ]]; then
    GLOBAL_GEMINI_DIR="$HOME/.gemini/config"
    if [[ -d "$GLOBAL_GEMINI_DIR" ]]; then
        ln -sf "$NATIVE_MCP_ARTIFACT" "$GLOBAL_GEMINI_DIR/mcp_config.json"
    fi
    if command -v cmd.exe >/dev/null && command -v wslpath >/dev/null; then
        WIN_PROFILE="$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' || true)"
        WIN_HOME="$(wslpath -u "$WIN_PROFILE" 2>/dev/null || true)"
        if [[ -n "$WIN_HOME" && -d "$WIN_HOME/.gemini/config" ]]; then
            cp -f "$WINDOWS_WSL_ARTIFACT" "$WIN_HOME/.gemini/config/mcp_config.json"
            cmp -s "$WINDOWS_WSL_ARTIFACT" "$WIN_HOME/.gemini/config/mcp_config.json"
        fi
    fi
fi

FAILURES=()
verify_step() {
    local name="$1"; shift
    if "$@"; then printf 'PASS %s\n' "$name"; else FAILURES+=("$name"); printf 'FAIL %s\n' "$name"; fi
}

MANIFEST=".doc/skil_data/harness-core/parity-report.json"
CANON=(--canonical .agents/skills --rules-canonical .cursor/rules --mcp-canonical .cursor/mcp.json)
PARITY=(--view .agents/skills)
MCP=()
if enabled codex; then PARITY+=(--rules-view .codex/rules); MCP+=(--codex-toml .codex/config.toml); fi
if enabled kilo; then PARITY+=(--rules-view .kilo/rules --mcp-view .kilo/kilo.jsonc); MCP+=(--kilo .kilo/kilo.jsonc); fi
if enabled qoder; then PARITY+=(--view .qoder/skills --rules-view .qoder/rules --mcp-view .qoder/settings.json); MCP+=(--expanded .qoder/settings.json); fi
if enabled agents; then PARITY+=(--rules-view .agents/rules --mcp-view .agents/mcp.json --mcp-view "$WINDOWS_WSL_ARTIFACT"); MCP+=(--expanded .agents/mcp.json --expanded "$WINDOWS_WSL_ARTIFACT"); fi
if enabled qwen; then MCP+=(--qwen .qwen/settings.json); fi
if enabled opencode; then MCP+=(--opencode opencode.json); fi
if enabled omp; then MCP+=(--expanded .omp/mcp.json); fi
verify_step parity python3 "$SCRIPT_DIR/verify_parity.py" "${CANON[@]}" "${PARITY[@]}" --manifest "$MANIFEST"
verify_step render-check python3 "$SCRIPT_DIR/render_agent_views.py" --root "$ROOT_DIR" --check
verify_step rule-triggers python3 "$SCRIPT_DIR/verify_rule_triggers.py" --root "$ROOT_DIR"
verify_step rule-visibility python3 "$SCRIPT_DIR/../../mirror/scripts/harness_mirror.py" --root "$ROOT_DIR" visibility --summary
if ((${#MCP[@]})); then
    verify_step mcp-views python3 "$SCRIPT_DIR/../../mcp-audit/scripts/verify_mcp_views.py" --canonical .cursor/mcp.json "${MCP[@]}"
fi
verify_step parity-fresh python3 "$SCRIPT_DIR/verify_parity.py" "${CANON[@]}" --manifest "$MANIFEST" --check
if ((${#FAILURES[@]})); then
    printf 'Sync finished with failures: %s\n' "${FAILURES[*]}"
    if [[ "$ALLOW_DRIFT" == 0 ]]; then exit 1; fi
    exit 0
fi
SCAN_SCRIPT="$SCRIPT_DIR/../../add-skill/scripts/scan_local_skills.py"
if [[ -f "$SCAN_SCRIPT" ]]; then
    python3 "$SCAN_SCRIPT" --root "$ROOT_DIR" || printf 'warning: skill scan failed\n' >&2
    if [[ "${HARNESS_SYNC_NO_PROMPT:-0}" != 1 && -t 0 && -t 1 ]]; then
        LOCAL_COUNT="$(python3 "$SCAN_SCRIPT" --root "$ROOT_DIR" --json 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("installable", [])))' 2>/dev/null || printf 0)"
        if [[ "$LOCAL_COUNT" -gt 0 ]] && read -r -p 'Install local skills into canon? [y/N] ' answer; then
            case "$answer" in
                y|Y|yes|да|д|Д)
                    python3 "$SCRIPT_DIR/../../add-skill/scripts/add_skill.py" --root "$ROOT_DIR" --all --yes --no-sync
                    HARNESS_SYNC_NO_PROMPT=1 bash "$SCRIPT_DIR/sync-agent-views.sh" "$@"
                    exit
                    ;;
            esac
        fi
    fi
fi
printf '=== All Agent Views (including MCP config) Successfully Synced ===\n'
