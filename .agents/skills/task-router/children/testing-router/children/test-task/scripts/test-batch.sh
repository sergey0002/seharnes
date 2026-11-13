#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TASKS=()
FILE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --file) FILE="$2"; shift 2 ;;
        -h|--help) echo "Использование: test-batch.sh N [N ...] | --file tasks.txt"; exit 0 ;;
        *) TASKS+=("$1"); shift ;;
    esac
done

if [ -n "$FILE" ]; then
    [ -f "$FILE" ] || die "нет файла списка: $FILE"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="${line//[[:space:]]/}"
        [ -n "$line" ] && TASKS+=("$line")
    done < "$FILE"
fi
[ "${#TASKS[@]}" -gt 0 ] || die "не указаны задачи"

STAMP="$(date +%Y-%m-%d_%H%M%S)"
BATCH_DIR="$TASKS_DIR/_batch-runs/$STAMP"
mkdir -p "$BATCH_DIR"
SUMMARY="$BATCH_DIR/summary.tsv"
printf "task\tcheck_tests\trun\tgates\tstatus\n" > "$SUMMARY"
overall=0

for task in "${TASKS[@]}"; do
    [[ "$task" =~ ^[0-9]+$ ]] || die "номер задачи должен быть числом: $task"
    info "Групповой прогон CT-$task"
    check=0; run=0; gates=0
    if bash "$SCRIPTS_DIR/check-tests.sh" >"$BATCH_DIR/${task}.check.log" 2>&1; then check=1; fi
    if [ "$check" -eq 1 ] && bash "$SCRIPTS_DIR/task-test.sh" "$task" >"$BATCH_DIR/${task}.run.log" 2>&1; then run=1; fi
    if [ "$run" -eq 1 ] && python3 "$SCRIPTS_DIR/gates.py" "$task" >"$BATCH_DIR/${task}.gates.log" 2>&1; then gates=1; fi
    status="FAIL"
    if [ "$check" -eq 1 ] && [ "$run" -eq 1 ] && [ "$gates" -eq 1 ]; then status="PASS"; else overall=1; fi
    printf "%s\t%s\t%s\t%s\t%s\n" "$task" "$check" "$run" "$gates" "$status" | tee -a "$SUMMARY"
done

python3 - "$SUMMARY" "$BATCH_DIR/summary.json" <<'PY'
import json, sys
from pathlib import Path
rows=[]
for line in Path(sys.argv[1]).read_text().splitlines()[1:]:
    task, check, run, gates, status = line.split('\t')
    rows.append({'task': task, 'checkTests': check == '1', 'run': run == '1', 'gates': gates == '1', 'status': status})
Path(sys.argv[2]).write_text(json.dumps({'tasks': rows, 'passed': all(r['status']=='PASS' for r in rows)}, ensure_ascii=False, indent=2)+'\n')
PY

echo "Batch: $BATCH_DIR"
exit "$overall"
