#!/usr/bin/env bash
set -euo pipefail
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check "$@"
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
