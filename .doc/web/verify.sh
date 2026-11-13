#!/usr/bin/env bash
# Verify the running panel and the harness graph.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PORT="${WEB_PANEL_PORT:-8077}"
BASE="http://127.0.0.1:$PORT"
fail=0

say() { printf '%s\n' "$*"; }

say "health"
if health=$(curl -fsS -m 10 "$BASE/harness/api/health"); then
  printf '%s\n' "$health" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get("status")=="ok"; print("ok nodes=%s" % (d.get("stats") or {}).get("nodes"))'
else
  say "health failed"
  fail=1
fi

say "actions"
python3 "$ROOT/.doc/web/bin/build-actions.py" --check || fail=1

say "graph"
python3 "$ROOT/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py" check || fail=1

say "jobs"
curl -fsS -m 10 "$BASE/jobs" >/dev/null && say "ok jobs" || { say "jobs failed"; fail=1; }

exit "$fail"
