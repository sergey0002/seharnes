#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

# Base directory: project root (.doc/skil_data/harness-core/ -> .. -> .. -> project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../../../../.." && pwd)"

cd "$ROOT_DIR"

LOCAL_ONLY="${HARNESS_SYNC_LOCAL_ONLY:-0}"
QODER_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--local-only" ]; then LOCAL_ONLY=1; fi
    if [ "$arg" = "--replace-managed-mcp" ]; then QODER_ARGS+=("--replace-managed-mcp"); fi
done

# Check Qoder before any generator can change a view or its discovery files.
python3 "${SCRIPT_DIR}/generate-qoder-config.py" --root "$ROOT_DIR" --preflight "${QODER_ARGS[@]}"

echo "=== Syncing Agent Views with Canonical Source (.cursor/) ==="

# Windows-side Antigravity is a Windows process even for WSL remote workspaces.
# Its stdio MCP servers need wsl.exe wrappers.
WINDOWS_WSL_ARTIFACT="${ROOT_DIR}/.doc/skil_data/harness-core/antigravity_mcp_config.windows-wsl.json"
NATIVE_MCP_ARTIFACT="${ROOT_DIR}/.doc/skil_data/harness-router/antigravity_mcp_config.json"

# Build native Codex and Kilo configuration instead of exposing Cursor's
# files through symlinks. Each client has a different instruction/MCP schema.
echo "--- Generating Codex and Kilo native configuration ---"
python3 "${SCRIPT_DIR}/generate-agent-configs.py" "$ROOT_DIR"
python3 "${SCRIPT_DIR}/generate-codex-mcp.py" --root "$ROOT_DIR" --config "${ROOT_DIR}/.codex/config.toml"
python3 "${SCRIPT_DIR}/generate-codex-mcp.py" --root "$ROOT_DIR" --config "${ROOT_DIR}/.codex/config.toml" --check

# Bytecode caches and pre-native leftovers must not survive in generated views.
echo "--- Cleaning generated views ---"
find .codex .kilo .qoder .qwen .cursor .agents -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
# Kilo reads kilo.jsonc; the old symlink exposed raw canon tokens Kilo cannot expand.
if [ -e ".kilo/mcp.json" ] || [ -L ".kilo/mcp.json" ]; then
    rm -f ".kilo/mcp.json"
    echo "Removed legacy .kilo/mcp.json"
fi

# 0. Generate Antigravity / Gemini compatible MCP config from canonical .cursor/mcp.json
# (Expands ${workspaceFolder}, resolves ${env:VAR}, inlines envFile for clients without VS Code var support)
echo "--- Generating Antigravity/Gemini adapted MCP config ---"
python3 "${SCRIPT_DIR}/generate-mcp-config.py" "$ROOT_DIR" --out "$NATIVE_MCP_ARTIFACT"
echo "--- Generating Windows Antigravity MCP config (stdio via wsl.exe) ---"
python3 "${SCRIPT_DIR}/generate-mcp-config.py" "$ROOT_DIR" \
    --host windows-wsl \
    --distro "${WSL_DISTRO_NAME:-}" \
    --out "$WINDOWS_WSL_ARTIFACT"

# 0a. Qoder reads project-level .qoder/rules, .qoder/skills and .qoder/settings.json.
echo "--- Generating Qoder project view ---"
python3 "${SCRIPT_DIR}/generate-qoder-config.py" --root "$ROOT_DIR" "${QODER_ARGS[@]}"

# 0b. Qwen Code reads .qwen/rules and .qwen/settings.json; .agents/skills is native.
echo "--- Generating Qwen Code project view ---"
python3 "${SCRIPT_DIR}/generate-qwen-config.py" --root "$ROOT_DIR"

create_symlink_view() {
    local target_dir="$1"
    local symlink_name="$2"
    local rel_source="$3"

    mkdir -p "$target_dir"
    
    if [ -d "$target_dir/$symlink_name" ] && [ ! -L "$target_dir/$symlink_name" ]; then
        echo "Removing non-symlink folder $target_dir/$symlink_name..."
        rm -rf "$target_dir/$symlink_name"
    fi

    if [ -L "$target_dir/$symlink_name" ] || [ -f "$target_dir/$symlink_name" ]; then
        rm -f "$target_dir/$symlink_name"
    fi

    ln -s "$rel_source" "$target_dir/$symlink_name"
    echo "Linked $target_dir/$symlink_name -> $rel_source"
}

create_copy_view() {
    local target_dir="$1"
    local name="$2"
    local source="$3"
    mkdir -p "$target_dir"
    if [ -d "$source" ]; then
        rm -rf "$target_dir/$name"
        mkdir -p "$target_dir/$name"
        cp -a "$source"/. "$target_dir/$name"/
        # Generated skill data must not travel into mirror views.
        find "$target_dir/$name" -type d -name '.data' -prune -exec rm -rf {} + 2>/dev/null || true
        # Normalize CRLF to LF in text files so parity never flags
        # line-ending-only drift between canon and views.
        find "$target_dir/$name" -type f \( -name '*.md' -o -name '*.mdc' -o -name '*.json' -o -name '*.jsonc' -o -name '*.toml' -o -name '*.yaml' -o -name '*.yml' -o -name '*.py' -o -name '*.ps1' -o -name '*.sh' -o -name '*.js' -o -name '*.mjs' -o -name '*.txt' -o -name '*.env' -o -name '*.example' -o -name '*.dist' \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true
        echo "Copied $target_dir/$name from $source"
    else
        echo "ERROR: canonical directory missing: $source" >&2
        return 1
    fi
}

copy_file_view() {
    local source="$1"
    local target="$2"
    rm -f "$target"
    mkdir -p "$(dirname "$target")"
    cp -f "$source" "$target"
    case "$target" in
        *.md|*.mdc|*.json|*.jsonc|*.toml|*.yaml|*.yml|*.py|*.ps1|*.sh|*.js|*.mjs|*.txt|*.env|*.example|*.dist)
            sed -i 's/\r$//' "$target" 2>/dev/null || true
            ;;
    esac
}

sync_full_agent_env() {
    local env_dir="$1"
    local skip_rules="${2:-0}"
    local skip_skills="${3:-0}"
    echo "--- Syncing $env_dir ---"
    if [ "$skip_rules" != "1" ]; then
        create_copy_view "$env_dir" "rules" ".cursor/rules"
    fi
    if [ "$skip_skills" != "1" ]; then
        create_copy_view "$env_dir" "skills" ".agents/skills"
    fi
    if [ -d ".cursor/scripts" ]; then
        create_copy_view "$env_dir" "scripts" ".cursor/scripts"
    else
        rm -rf "$env_dir/scripts"
        echo "No canonical scripts pool; removed $env_dir/scripts"
    fi
    # Bytecode caches must not propagate into mirror views.
    find "$env_dir" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    copy_file_view "$NATIVE_MCP_ARTIFACT" "$env_dir/mcp.json"
    copy_file_view "$NATIVE_MCP_ARTIFACT" "$env_dir/mcp_config.json"
    if [ -f ".cursor/mcp.env" ]; then
        copy_file_view ".cursor/mcp.env" "$env_dir/mcp.env"
    fi
}

# 1. Agents common view: Cursor, Kilo and Antigravity read .agents.
# Rules are not copied as .mdc: Antigravity needs flat .md with trigger.
sync_full_agent_env ".agents" 1 1
# MCP server sources live in .tools/mcp-servers and are not part of any agent
# view. Remove copies left by older syncs so they cannot drift from the canon.
for legacy in ".agents/mcp-servers" ".codex/mcp-servers"; do
    if [ -d "$legacy" ]; then
        rm -rf "$legacy"
        echo "Removed legacy $legacy"
    fi
done
find .agents/rules -type f -name '*.mdc' -delete 2>/dev/null || true
python3 "${SCRIPT_DIR}/generate-antigravity-rules.py" --root "${ROOT_DIR}" >/dev/null

# Cursor reads the canonical .agents/skills. Retire only the known alias.
if [ -L ".cursor/skills" ] && [ "$(readlink -f .cursor/skills)" = "$(realpath .agents/skills)" ]; then
    rm .cursor/skills
fi

# 2. Global Antigravity / Gemini config (~/.gemini/config/mcp_config.json)
GLOBAL_GEMINI_DIR="${HOME}/.gemini/config"
if [ "$LOCAL_ONLY" != "1" ] && [ -d "$GLOBAL_GEMINI_DIR" ]; then
    echo "--- Syncing global Antigravity / Gemini config ($GLOBAL_GEMINI_DIR) ---"
    if [ -f "$GLOBAL_GEMINI_DIR/mcp_config.json" ] || [ -L "$GLOBAL_GEMINI_DIR/mcp_config.json" ]; then
        rm -f "$GLOBAL_GEMINI_DIR/mcp_config.json"
    fi
    ln -sf "$NATIVE_MCP_ARTIFACT" "$GLOBAL_GEMINI_DIR/mcp_config.json"
    echo "Linked $GLOBAL_GEMINI_DIR/mcp_config.json -> $NATIVE_MCP_ARTIFACT"
fi

# 5. Global Antigravity config on the Windows side (%USERPROFILE%\.gemini\config).
# The language server is language_server_windows_x64.exe even when the
# workspace lives in WSL, so it never reads the WSL ~/.gemini/config symlink.
WIN_HOME=""
if [ "$LOCAL_ONLY" != "1" ] && command -v cmd.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
    WIN_PROFILE="$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r' || true)"
    if [ -n "$WIN_PROFILE" ]; then
        WIN_HOME="$(wslpath -u "$WIN_PROFILE" 2>/dev/null || true)"
    fi
fi
if [ -n "$WIN_HOME" ] && [ -d "$WIN_HOME/.gemini/config" ]; then
    WIN_MCP="$WIN_HOME/.gemini/config/mcp_config.json"
    cp -f "$WINDOWS_WSL_ARTIFACT" "$WIN_MCP"
    cmp -s "$WINDOWS_WSL_ARTIFACT" "$WIN_MCP"
    echo "Installed and verified Windows Antigravity config: $WIN_MCP"
else
    echo "Windows Antigravity global config not found; skipping install"
fi

echo "--- Generating DeepSeek Harness project patch ---"
# DSH must be generated BEFORE the manifest is written: the manifest records
# that every consumer view (including .dsh/project.patch.yml) was regenerated.
python3 "${SCRIPT_DIR}/generate-dsh-config.py" --root "${ROOT_DIR}"

# Drift policy. Repair mode always regenerates and records the result; strict
# mode (default) exits nonzero when any check fails. --allow-drift lets a
# developer re-run the sync to heal stale mirrors without editing the script.
ALLOW_DRIFT=0
for arg in "$@"; do
    case "$arg" in
        --allow-drift) ALLOW_DRIFT=1 ;;
        --strict) ALLOW_DRIFT=0 ;;
    esac
done

FAILURES=()
verify_step() {
    local name="$1"; shift
    if ! "$@"; then
        FAILURES+=("$name")
        echo "FAIL ${name}"
    else
        echo "PASS ${name}"
    fi
}

echo "--- Verifying DSH outputs ---"
verify_step "dsh" \
python3 "${SCRIPT_DIR}/generate-dsh-config.py" --root "${ROOT_DIR}" --check

echo "--- Verifying canonical parity (skills + rules + mcp) ---"
VERIFY_SCRIPT="${ROOT_DIR}/.agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py"
# The manifest is written by the parity check below, before later gates. The
# parity-fresh gate re-reads it at the end, so a stored "passed" cannot be
# stale against the current canon.
verify_step "parity" \
python3 "$VERIFY_SCRIPT" \
    --canonical "${ROOT_DIR}/.agents/skills" \
    --view "${ROOT_DIR}/.agents/skills" \
    --view "${ROOT_DIR}/.qoder/skills" \
    --rules-canonical "${ROOT_DIR}/.cursor/rules" \
    --rules-view "${ROOT_DIR}/.codex/rules" \
    --rules-view "${ROOT_DIR}/.kilo/rules" \
    --rules-view "${ROOT_DIR}/.agents/rules" \
    --rules-view "${ROOT_DIR}/.qoder/rules" \
    --mcp-canonical "${ROOT_DIR}/.cursor/mcp.json" \
    --mcp-view "${ROOT_DIR}/.kilo/kilo.jsonc" \
    --mcp-view "${ROOT_DIR}/.agents/mcp.json" \
    --mcp-view "${ROOT_DIR}/.qoder/settings.json" \
    --mcp-view "${WINDOWS_WSL_ARTIFACT}" \
    --manifest "${ROOT_DIR}/.doc/skil_data/harness-core/parity-report.json"

echo "--- Verifying Qoder view matches the canon ---"
verify_step "qoder" \
python3 "${SCRIPT_DIR}/generate-qoder-config.py" --root "${ROOT_DIR}" --check

echo "--- Verifying Qwen Code view matches the canon ---"
verify_step "qwen" \
python3 "${SCRIPT_DIR}/generate-qwen-config.py" --root "${ROOT_DIR}" --check

echo "--- Verifying rule trigger parity across environments ---"
verify_step "rule-triggers" \
python3 "${SCRIPT_DIR}/verify_rule_triggers.py" --root "${ROOT_DIR}"
verify_step "native-discovery" \
python3 "${SCRIPT_DIR}/generate-agent-configs.py" "$ROOT_DIR" --check-discovery

echo "--- Verifying rule visibility contracts across environments ---"
verify_step "rule-visibility" \
python3 "${ROOT_DIR}/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py" \
    --root "${ROOT_DIR}" visibility --summary

echo "--- Verifying MCP server sets across views ---"
verify_step "mcp-views" \
python3 "${ROOT_DIR}/.agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py" \
    --canonical "${ROOT_DIR}/.cursor/mcp.json" \
    --kilo "${ROOT_DIR}/.kilo/kilo.jsonc" \
    --expanded "${ROOT_DIR}/.agents/mcp.json" \
    --expanded "${ROOT_DIR}/.qoder/settings.json" \
    --qwen "${ROOT_DIR}/.qwen/settings.json" \
    --expanded "${WINDOWS_WSL_ARTIFACT}" \
    --codex-toml "${ROOT_DIR}/.codex/config.toml"

echo "--- Confirming the written report matches the current canon ---"
verify_step "parity-fresh" \
python3 "$VERIFY_SCRIPT" \
    --canonical "${ROOT_DIR}/.agents/skills" \
    --manifest "${ROOT_DIR}/.doc/skil_data/harness-core/parity-report.json" \
    --check

if [ "${#FAILURES[@]}" -gt 0 ]; then
    echo "=== Sync finished WITH FAILURES: ${FAILURES[*]} ==="
    echo "Run again to retry, or pass --allow-drift to record drift and continue."
    if [ "$ALLOW_DRIFT" -eq 0 ]; then
        exit 1
    fi
    echo "(--allow-drift) continuing despite failures"
fi

echo "--- Scanning skills outside the package ---"
SCAN_SCRIPT="${ROOT_DIR}/.agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py"
ADD_SCRIPT="${ROOT_DIR}/.agents/skills/harness-router/children/add-skill/scripts/add_skill.py"
if [ -f "$SCAN_SCRIPT" ]; then
    python3 "$SCAN_SCRIPT" --root "$ROOT_DIR" || echo "warning: skill scan failed"
    if [ "${HARNESS_SYNC_NO_PROMPT:-0}" != "1" ] && [ -t 0 ] && [ -t 1 ]; then
        LOCAL_COUNT="$(python3 "$SCAN_SCRIPT" --root "$ROOT_DIR" --json 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("installable", [])))' 2>/dev/null || echo 0)"
        if [ "${LOCAL_COUNT:-0}" -gt 0 ]; then
            read -r -p "Установить локальные скилы в канон? [y/N] " answer
            case "$answer" in
                y|Y|д|Д|yes|да)
                    python3 "$ADD_SCRIPT" --root "$ROOT_DIR" --all --yes --no-sync || echo "warning: local skill install failed"
                    HARNESS_SYNC_NO_PROMPT=1 bash "${ROOT_DIR}/.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh"
                    ;;
            esac
        fi
    fi
else
    echo "skill scanner not found: $SCAN_SCRIPT"
fi

echo "=== All Agent Views (including MCP config) Successfully Synced ==="
