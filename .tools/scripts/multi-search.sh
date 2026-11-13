#!/usr/bin/env bash
# multi-search.sh - пакетный поиск N паттернов одним проходом rg, наружу JSON-lines.
# Канон: .cursor/scripts/multi-search.sh. Вызов через bash, новый MCP не нужен.
# План: .doc/harnes/plan/massgrep.md раздел 4.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: multi-search.sh --root DIR --pattern STR [--pattern STR ...]
  [--include GLOB ...] [--max-per-file N] [--max-total N] [--context N] [--truncate N]
Exit: 0 есть совпадения, 1 нет совпадений, 2 ошибка аргументов или нет rg.
EOF
  exit 2
}

ROOT=""
PATTERNS=()
INCLUDES=()
MAX_PER_FILE=5
MAX_TOTAL=100
CONTEXT=0
TRUNCATE=300

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --pattern) PATTERNS+=("${2:-}"); shift 2 ;;
    --include) INCLUDES+=("${2:-}"); shift 2 ;;
    --max-per-file) MAX_PER_FILE="${2:-}"; shift 2 ;;
    --max-total) MAX_TOTAL="${2:-}"; shift 2 ;;
    --context) CONTEXT="${2:-}"; shift 2 ;;
    --truncate) TRUNCATE="${2:-}"; shift 2 ;;
    --json) shift ;;
    -h|--help) usage ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done

[ -n "$ROOT" ] || { echo "missing --root" >&2; usage; }
[ "${#PATTERNS[@]}" -gt 0 ] || { echo "missing --pattern" >&2; usage; }
[ -d "$ROOT" ] || { echo "root not found: $ROOT" >&2; exit 2; }

# Движок: rg если есть, иначе grep -rn (медленнее, без --json, парсим текст).
ENGINE="rg"
command -v rg >/dev/null 2>&1 || ENGINE="grep"
if [ "$ENGINE" = "grep" ]; then
  echo "note: rg not found, using grep fallback (slower)" >&2
fi

# Защита: корень репо без --include запрещен (прогон по vendor/ и стенду).
if [ "$ROOT" = "." ] && [ "${#INCLUDES[@]}" -eq 0 ]; then
  echo "refusing repo root without --include (use --include to narrow)" >&2
  exit 2
fi

RG_ARGS=(-n --json --no-heading -S --max-count "$(( MAX_PER_FILE * 3 ))")
for g in "${INCLUDES[@]}"; do RG_ARGS+=(-g "$g"); done
for p in "${PATTERNS[@]}"; do RG_ARGS+=(-e "$p"); done
if [ "$CONTEXT" -gt 0 ]; then RG_ARGS+=(-C "$CONTEXT"); fi

# Исключения по умолчанию: gitignore уважать, бинарники пропустить,
# рабочую копию стенда пропустить при широком корне.
RG_ARGS+=(--no-ignore-vcs -g '!.tools/codeception/**')

export MAX_PER_FILE MAX_TOTAL TRUNCATE NPAT="${#PATTERNS[@]}"

if [ "$ENGINE" = "rg" ]; then
  RG_OUT="$(rg "${RG_ARGS[@]}" "$ROOT" 2>/dev/null || true)"
else
  # grep fallback: строим alternation, вывод file:line:text
  ALT="$(printf '%s|' "${PATTERNS[@]}")"; ALT="${ALT%|}"
  GLOBS=()
  for g in "${INCLUDES[@]}"; do GLOBS+=(--include="$g"); done
  RG_OUT="$(grep -rn -I ${GLOBS[@]:-} -E "$ALT" "$ROOT" 2>/dev/null || true)"
  export GREP_FALLBACK=1
fi

if [ -z "$RG_OUT" ]; then
  printf '{"_meta":{"patterns":%d,"files":0,"shown":0,"skipped":0,"truncated":false}}\n' "$NPAT"
  exit 1
fi

printf '%s\n' "$RG_OUT" | python3 -c "
import json,sys,os
max_pf=int(os.environ['MAX_PER_FILE']); max_tot=int(os.environ['MAX_TOTAL'])
trunc=int(os.environ['TRUNCATE']); npat=int(os.environ['NPAT'])
fallback=os.environ.get('GREP_FALLBACK')=='1'
per_file={}; total=[0]; skipped=[0]
def emit(path,ln,txt):
    bucket=per_file.setdefault(path,[])
    if len(bucket)>=max_pf: skipped[0]+=1; return
    if total[0]>=max_tot: skipped[0]+=1; return
    if len(txt)>trunc: txt=txt[:trunc]+'...[cut]'
    bucket.append((ln,txt)); total[0]+=1
if fallback:
    for line in sys.stdin:
        line=line.rstrip('\n')
        if not line: continue
        # формат grep -rn: path:line:text (путь без двоеточий в наших корнях)
        parts=line.split(':',2)
        if len(parts)<3: continue
        try: ln=int(parts[1])
        except: continue
        emit(parts[0],ln,parts[2])
else:
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        try: ev=json.loads(line)
        except: continue
        if ev.get('type')!='match': continue
        path=ev['data']['path']['text']; ln=ev['data']['line_number']
        txt=ev['data']['lines']['text'].rstrip('\n')
        emit(path,ln,txt)
shown=0
for path in sorted(per_file):
    for ln,txt in sorted(per_file[path]):
        print(json.dumps({'file':path,'line':ln,'match':txt},ensure_ascii=False))
        shown+=1
meta={'patterns':npat,'files':len(per_file),'shown':shown,'skipped':skipped[0],'truncated':skipped[0]>0}
print(json.dumps({'_meta':meta},ensure_ascii=False))
"
