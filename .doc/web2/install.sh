#!/usr/bin/env bash
# Install or check copytrust-tools in the current project.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STATE="$ROOT/.doc/web/state"
PORT="${WEB_PANEL_PORT:-8077}"

fail=0
say() { printf '%s\n' "$*"; }
check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    say "ok $1=$("$1" --version 2>&1 | head -1)"
  else
    say "missing $1"
    fail=1
  fi
}

profile() {
  python3 - "$ROOT/.doc/.rebase-kit.json" "$ROOT/.doc/web/config/service.json" <<'PY'
import json
import sys
from pathlib import Path

for name in sys.argv[1:]:
    path = Path(name)
    if not path.exists():
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        value = data.get("profile") if isinstance(data, dict) else None
        if not isinstance(value, str) or value.lower() not in ("core", "full"):
            raise ValueError("profile must be core or full")
    except (OSError, ValueError) as error:
        print("invalid profile in %s: %s" % (path, error), file=sys.stderr)
        sys.exit(2)
    print(value.lower())
    sys.exit(0)
print("profile missing: configure service.json or migration receipt", file=sys.stderr)
sys.exit(2)
PY
}

check() {
  say "root=$ROOT"
  check_cmd python3
  check_cmd bash
  if ! PROFILE="$(profile)"; then say "invalid panel profile"; exit 1; fi
  say "profile=$PROFILE"
  if [ "$PROFILE" = "full" ]; then check_cmd pwsh; else say "ok pwsh skipped (core)"; fi
  check_cmd docker
  if [ -f "$ROOT/.doc/web/config/service.json" ]; then
    python3 -m json.tool "$ROOT/.doc/web/config/service.json" >/dev/null && say "ok service.json"
  else
    say "missing service.json"
    fail=1
  fi
  if [ -f "$ROOT/.doc/web/config/actions.json" ]; then
    python3 "$ROOT/.doc/web/bin/build-actions.py" --check || fail=1
  else
    say "missing actions.json"
    fail=1
  fi
  if [ -f "$ROOT/.doc/web/config/prices.json" ]; then
    python3 -m json.tool "$ROOT/.doc/web/config/prices.json" >/dev/null && say "ok prices.json"
  else
    say "missing prices.json"
    fail=1
  fi
  if [ -f "$ROOT/.doc/web/compose.tools.yml" ]; then
    say "ok compose.tools.yml"
  else
    say "missing compose.tools.yml"
    fail=1
  fi
  KILO="${KILO_DATA_DIR:-$HOME/.local/share/kilo}"
  if [ -f "$KILO/kilo.db" ]; then
    say "ok kilo.db=$KILO/kilo.db"
  else
    say "warning kilo.db not found: $KILO/kilo.db (analytics_scan disabled at runtime)"
  fi
  exit "$fail"
}

project() {
  PROFILE="$(profile)"
  mkdir -p "$STATE/jobs" "$STATE/tmp"
  python3 - "$ROOT/.doc/web/config/service.json" "$PROFILE" <<'PY'
import json
import sys

path, profile = sys.argv[1], sys.argv[2]
data = json.load(open(path))
data["profile"] = profile
open(path, "w").write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
  if [ ! -f "$ROOT/.doc/skil_data/mirror/graph.json" ]; then
    python3 "$ROOT/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py" --root "$ROOT" scan \
      && python3 "$ROOT/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py" --root "$ROOT" build \
      || { say "graph build failed"; exit 1; }
  fi
  cat > "$ROOT/.doc/web/.env" <<EOF
SERVICE_WORKSPACE=$ROOT
HOST_UID=$(id -u)
HOST_GID=$(id -g)
KILO_DATA_DIR=${KILO_DATA_DIR:-$HOME/.local/share/kilo}
WEB_PANEL_PORT=$PORT
EOF
  if [ ! -f "$ROOT/.doc/web/ADAPTERS.local.md" ]; then
    cat > "$ROOT/.doc/web/ADAPTERS.local.md" <<EOF
# Adapters: copytrust-tools (local)

| Adapter | Значение |
|---|---|
| SERVICE_ROOT | \`$HERE\` |
| WORKSPACE_ROOT | \`$ROOT\` |
| STATE_DIR | \`$STATE\` |
| PORT | \`$PORT\` |
| PROFILE | \`$PROFILE\` |
| KILO_DATA_DIR | \`${KILO_DATA_DIR:-$HOME/.local/share/kilo}\` |
EOF
  fi
  say "state=$STATE"
  say "next: cd $ROOT/.doc/web && HOST_UID=$(id -u) HOST_GID=$(id -g) SERVICE_WORKSPACE=$ROOT docker compose -p copytrust-tools -f compose.tools.yml up -d --build"
}

case "${1:-}" in
  --check) check ;;
  --project) project ;;
  --help|-h)
    say "usage: install.sh --check | --project | --help"
    ;;
  *)
    say "usage: install.sh --check | --project | --help"
    exit 2
    ;;
esac
