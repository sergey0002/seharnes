#!/usr/bin/env bash
# multi-exec.sh - пакетный запуск N команд и чтений с offset/limit одним вызовом bash.
# Наружу JSON-lines: одна строка на команду/чтение + финальная _meta.
# Канон: .cursor/scripts/multi-exec.sh. План: .doc/harnes/plan/massgrep.md раздел 5.
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: multi-exec.sh [--input FILE] [--cmd "id=X :: command"]... [--read "id=X :: path [+offset] [limit]"]...
  [--mode sequential|parallel] [--timeout SEC] [--max-output BYTES] [--truncate BYTES]
Exit: 0 все ok, 1 хотя бы одна команда упала (JSON полный), 2 ошибка батча.
EOF
  exit 2
}

INPUT=""; CMDS=(); READS=(); MODE="sequential"; TIMEOUT=60; MAX_OUTPUT=20000; TRUNCATE=2000

while [ $# -gt 0 ]; do
  case "$1" in
    --input) INPUT="${2:-}"; shift 2 ;;
    --cmd) CMDS+=("${2:-}"); shift 2 ;;
    --read) READS+=("${2:-}"); shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT="${2:-}"; shift 2 ;;
    --max-output) MAX_OUTPUT="${2:-}"; shift 2 ;;
    --truncate) TRUNCATE="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done

if [ -z "$INPUT" ] && [ "${#CMDS[@]}" -eq 0 ] && [ "${#READS[@]}" -eq 0 ]; then
  echo "nothing to run: give --input, --cmd or --read" >&2; usage
fi
if [ "$MODE" != "sequential" ] && [ "$MODE" != "parallel" ]; then
  echo "bad --mode: $MODE" >&2; exit 2
fi
command -v timeout >/dev/null 2>&1 || { echo "timeout not found (coreutils)" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 2; }

# parallel allowlist: только read-only (план 5.2).
PARALLEL_ALLOW='^(rg|grep|git (log|diff|show|blame|status)|php -l|php -m|php --version|ls|cat|head|tail|wc|file|stat|python3 .doc/jsondoc_scripts/jsondoc\.py (get|batch))([ \t]|$)'

export INPUT TIMEOUT MAX_OUTPUT TRUNCATE MODE PARALLEL_ALLOW
export CMDS_FILE READS_FILE
CMDS_FILE="$(mktemp)"; READS_FILE="$(mktemp)"
trap 'rm -f "$CMDS_FILE" "$READS_FILE"' EXIT
printf '%s\n' "${CMDS[@]:-}" > "$CMDS_FILE"
printf '%s\n' "${READS[@]:-}" > "$READS_FILE"

python3 - <<'PYEOF'
import json, os, re, subprocess, sys, time, hashlib

timeout = int(os.environ['TIMEOUT']); max_out = int(os.environ['MAX_OUTPUT'])
trunc = int(os.environ['TRUNCATE']); mode = os.environ['MODE']
allow = re.compile(os.environ['PARALLEL_ALLOW'])

def parse_entry(s):
    m = re.match(r'\s*id\s*=\s*([^:]+?)\s*::\s*(.*)$', s or '', re.S)
    if not m: return None, None
    return m.group(1).strip(), m.group(2).strip()

def parse_read(spec):
    # path [+offset] [limit], offset с плюсом как в плане: "+445 25"
    parts = spec.strip().split()
    if not parts: return None, 1, 100
    path = parts[0]; off = 1; lim = 100
    rest = parts[1:]
    if rest and rest[0].startswith('+'):
        try: off = int(rest[0][1:]); rest = rest[1:]
        except: pass
    if rest:
        try: lim = int(rest[0])
        except: pass
    return path, max(1, off), max(1, lim)

items = []  # (kind, id, spec)
inp = os.environ['INPUT']
if inp:
    try: data = json.load(open(inp, encoding='utf-8'))
    except Exception as e:
        print(json.dumps({'error': 'bad input file: %s' % e})); sys.exit(2)
    if not isinstance(data, list):
        print(json.dumps({'error': 'input must be a JSON array'})); sys.exit(2)
    for el in data:
        if not isinstance(el, dict) or 'id' not in el:
            print(json.dumps({'error': 'input items need id'})); sys.exit(2)
        if 'cmd' in el: items.append(('cmd', str(el['id']), str(el['cmd'])))
        elif 'file' in el:
            items.append(('read', str(el['id']), f"{el['file']} +{el.get('offset',1)} {el.get('limit',100)}"))
        else:
            _id = el['id']
            print(json.dumps({'error': 'item %s needs cmd or file' % _id})); sys.exit(2)

def read_lines(f):
    out = []
    try:
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                line = line.rstrip('\n')
                if line: out.append(line)
    except FileNotFoundError: pass
    return out

for s in read_lines(os.environ['CMDS_FILE']):
    _id, _spec = parse_entry(s)
    if _id: items.append(('cmd', _id, _spec))
for s in read_lines(os.environ['READS_FILE']):
    _id, _spec = parse_entry(s)
    if _id: items.append(('read', _id, _spec))

items = [(k, i, s) for (k, i, s) in items if i]
ids = [i for (_, i, _) in items]
if len(ids) != len(set(ids)):
    print(json.dumps({'error': 'duplicate id in batch'})); sys.exit(2)
if not items:
    print(json.dumps({'error': 'empty batch'})); sys.exit(2)

if mode == 'parallel':
    for (k, _id, spec) in items:
        probe = spec if k == 'cmd' else 'cat'
        if not allow.match(probe.strip()):
            print(json.dumps({'error': 'parallel denied for %s' % _id})); sys.exit(2)

def run_cmd(cmd):
    t0 = time.time()
    try:
        p = subprocess.run(['timeout', str(timeout), 'bash', '-c', cmd],
                           capture_output=True, text=True, errors='replace')
        code, out, err, to = p.returncode, p.stdout, p.stderr, (p.returncode == 124)
    except Exception as e:
        code, out, err, to = 1, '', str(e), False
    ms = int((time.time() - t0) * 1000)
    t = len(out) > trunc
    if t: out = out[:trunc] + '...[cut]'
    e2 = len(err) > trunc
    if e2: err = err[:trunc] + '...[cut]'
    out = out.replace('\x00', '[NUL]')
    return {'exit': code, 'ms': ms, 'stdout': out, 'stderr': err,
            'truncated': t or e2, 'timeout': to}

def run_read(spec):
    t0 = time.time()
    path, off, lim = parse_read(spec)
    try:
        with open(path, 'rb') as f: raw = f.read()
    except FileNotFoundError:
        return {'exit': 1, 'ms': 0, 'file': path, 'error': 'not found'}
    total = raw.count(b'\n') + (0 if raw.endswith(b'\n') or not raw else 1)
    if off > total and total > 0:
        return {'exit': 1, 'ms': 0, 'file': path, 'error': 'offset beyond EOF',
                'total_lines': total}
    text = raw.decode('utf-8', errors='replace').splitlines()
    sl = text[off - 1:off - 1 + lim]
    ms = int((time.time() - t0) * 1000)
    lines = []
    for n, t in enumerate(sl, start=off):
        if len(t) > trunc: t = t[:trunc] + '...[cut]'
        lines.append({'n': n, 't': t})
    row = {'exit': 0, 'ms': ms, 'file': path, 'offset': off, 'limit': lim,
           'total_lines': total, 'lines': lines}
    if off - 1 + lim >= total: row['eof'] = True
    if off == 1 and off - 1 + lim >= total:
        row['content_hash'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
    return row

results = []
for (kind, _id, spec) in items:
    if kind == 'cmd':
        r = {'id': _id}; r.update(run_cmd(spec))
    else:
        r = {'id': _id}; r.update(run_read(spec))
    results.append(r)

total_bytes = sum(len(json.dumps(r, ensure_ascii=False)) for r in results)
truncated_all = total_bytes > max_out
shown = []
acc = 0
for r in results:
    s = json.dumps(r, ensure_ascii=False)
    if acc + len(s) > max_out and shown:
        truncated_all = True
        break
    shown.append(s); acc += len(s)

for s in shown: print(s)
failed = sum(1 for r in results if r.get('exit', 0) not in (0,))
timo = sum(1 for r in results if r.get('timeout'))
print(json.dumps({'_meta': {'total': len(results), 'failed': failed,
      'timeout': timo, 'ms': sum(r.get('ms', 0) for r in results),
      'truncated': truncated_all}}))
sys.exit(1 if failed else 0)
PYEOF
