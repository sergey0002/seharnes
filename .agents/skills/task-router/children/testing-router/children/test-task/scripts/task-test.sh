#!/usr/bin/env bash
# Прогон браузерных тестов задачи + сбор артефактов + verdict.json.
#
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --group item-draft
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --filter QualityWarningCest
#
# Тесты берутся из .doc/tasks/{N}/tests/ (вне git), результаты кладутся
# в .doc/tasks/{N}/test-runs/{дата}_{группа}/.
#
# Скрипт НЕ поднимает стенд и chromedriver — только проверяет, что они живы,
# и печатает команду запуска, если нет.

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TASK=""
GROUP=""
FILTER=""
SKIP_NEIGHBORS=0
PHASE="all"
STAGE_NUM=""
EXISTING_RUN_DIR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --group)  GROUP="$2"; shift 2 ;;
        --filter) FILTER="$2"; shift 2 ;;
        --phase) PHASE="$2"; shift 2 ;;
        --stage-num) STAGE_NUM="$2"; shift 2 ;;
        --run-dir) EXISTING_RUN_DIR="$2"; shift 2 ;;
        --skip-neighbors) SKIP_NEIGHBORS=1; shift ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *)
            [ -z "$TASK" ] || die "лишний аргумент: $1"
            TASK="$1"; shift ;;
    esac
done

[ -n "$TASK" ] || die "не указан номер задачи. Пример: task-test.sh 2236"
[[ "$TASK" =~ ^[0-9]+$ ]] || die "номер задачи — только цифры, получено: $TASK"
case "$PHASE" in
    preflight|unit|browser|all|finalize) ;;
    stage)
        # Stage mode verifies one plan stage in isolation. It was documented in
        # test-priority.mdc but rejected here, so the rule was unusable.
        [ -n "$STAGE_NUM" ] || die "--phase stage требует --stage-num K"
        [[ "$STAGE_NUM" =~ ^[0-9]+$ ]] || die "--stage-num: только цифры, получено: $STAGE_NUM"
        ;;
    *) die "неизвестная фаза: $PHASE" ;;
esac

if [ "$PHASE" = "finalize" ]; then
    [ -n "$EXISTING_RUN_DIR" ] || die "--run-dir обязателен для --phase finalize"
    RUN_DIR="$EXISTING_RUN_DIR"
    [ -d "$RUN_DIR" ] || die "каталог прогона не найден: $RUN_DIR"
    python3 "$SCRIPTS_DIR/make-verdict.py" --task "$TASK" --group "task-$TASK" --run-dir "$RUN_DIR" --exit-code 0
    python3 "$SCRIPTS_DIR/gates.py" "$TASK" --json > "$RUN_DIR/gates.json"
    exit $?
fi

GROUP="${GROUP:-task-$TASK}"
RUN_DIR="${EXISTING_RUN_DIR:-$TASKS_DIR/$TASK/test-runs/$(date +%Y-%m-%d_%H%M%S)_$GROUP}"
OUT_DIR="$CODECEPT_DIR/tests/_output"

mkdir -p "$RUN_DIR"
printf '{"results": []}\n' > "$RUN_DIR/ac-results.json"
python3 "$SCRIPTS_DIR/qa-manifest.py" --task "$TASK" --group "$GROUP" --output "$RUN_DIR/run-meta.json" >/dev/null

# Run and persist every precheck. A failure must still produce a complete
# machine-readable report instead of aborting the shell script halfway through.
PRECHECK_CODE=0
run_precheck() {
    local name="$1"; shift
    set +e
    "$@" >"$RUN_DIR/${name}.log" 2>&1
    local code=$?
    set -e
    if [ "$name" = "static" ] || [ "$name" = "phpunit" ] || [ "$name" = "branch-audit" ]; then
        [ "$code" -eq 0 ] || log "$name precheck exit $code, Codeception всё равно запускаем"
    else
        [ "$code" -eq 0 ] || PRECHECK_CODE=1
    fi
    printf '{"name":"%s","exit_code":%s}\n' "$name" "$code" >> "$RUN_DIR/prechecks.jsonl"
    if [ "$name" = "static" ]; then
        if [ "$code" -eq 0 ]; then
            printf '{"status":"passed","exit_code":0}\n' > "$RUN_DIR/static.json"
        else
            printf '{"status":"failed","exit_code":%s}\n' "$code" > "$RUN_DIR/static.json"
        fi
    fi
}

clear_smarty_cache
: > "$RUN_DIR/prechecks.jsonl"
DOCTOR_ARGS=(--task "$TASK")
if [ "$PHASE" = "all" ] || [ "$PHASE" = "browser" ]; then
    DOCTOR_ARGS+=(--require-browser)
    DOCTOR_ARGS+=(--require-db)
fi
run_precheck doctor python3 "$SCRIPTS_DIR/doctor.py" "${DOCTOR_ARGS[@]}"
run_precheck branch-audit python3 "$SCRIPTS_DIR/branch-audit.py" "$TASK"
run_precheck ac-source python3 "$SCRIPTS_DIR/check-ac-matrix.py" --task "$TASK" --phase source --run-dir "$RUN_DIR"
if [ "$PHASE" = "preflight" ] || [ "$PHASE" = "all" ] || [ "$PHASE" = "browser" ]; then
    run_precheck static python3 "$SCRIPTS_DIR/static-on-diff.py" "$TASK" --level "${QA_PHPSTAN_LEVEL:-8}"
    run_precheck lint python3 "$SCRIPTS_DIR/qa-lint.py" --task "$TASK" --run-dir "$RUN_DIR"
fi
if [ "$PHASE" = "unit" ] || [ "$PHASE" = "all" ] || [ "$PHASE" = "browser" ]; then
    run_precheck phpunit python3 "$SCRIPTS_DIR/run-phpunit.py" --task "$TASK" --run-dir "$RUN_DIR" --profile "${QA_PHPUNIT_PROFILE:-task}"
fi
if [ "$PHASE" = "all" ] || [ "$PHASE" = "browser" ]; then
    run_precheck db-before python3 "$SCRIPTS_DIR/db-isolation.py" --task "$TASK" --run-dir "$RUN_DIR" --phase before
    # manifest.json is written AFTER load_env/apply_webdriver_env below: hashing
    # the environment before it is applied made verdict.green unreachable.
fi

info "Задача CT-$TASK, группа $GROUP"

if [ "$PHASE" = "preflight" ]; then
    python3 "$SCRIPTS_DIR/qa-manifest.py" --task "$TASK" --group "$GROUP" --output "$RUN_DIR/manifest.json"
    exit "$PRECHECK_CODE"
fi
if [ "$PHASE" = "unit" ]; then
    python3 "$SCRIPTS_DIR/qa-manifest.py" --task "$TASK" --group "$GROUP" --output "$RUN_DIR/manifest.json"
    exit "$PRECHECK_CODE"
fi
if [ "$PHASE" = "browser" ]; then
    :
fi

WD_MODE="unavailable"
if [ "$PRECHECK_CODE" -eq 0 ]; then
    load_env
    check_app
    WD_MODE="$(detect_webdriver)"
    apply_webdriver_env "$WD_MODE"
else
    log "Browser layer skipped: mandatory prechecks failed"
fi

# Environment hash must be taken once the runner environment is final. Doing it
# earlier produced a spurious mismatch between manifest.json and the verdict.
if [ "$PHASE" = "all" ] || [ "$PHASE" = "browser" ]; then
    python3 "$SCRIPTS_DIR/qa-manifest.py" --task "$TASK" --group "$GROUP" --output "$RUN_DIR/manifest.json"
fi
# Пауза между шагами выключена по умолчанию: 0.3-0.4с на шаг давали
# около 20с на один тест. Для показа действий поставить QA_VISIBLE_DELAY=0.3.
export QA_VISIBLE_DELAY="${QA_VISIBLE_DELAY:-0}"
export QA_AC_RESULTS_FILE="$RUN_DIR/ac-results.json"
log "WebDriver: $WD_MODE"
if [ "$WD_MODE" = "local" ]; then
    log "Браузер: видимое окно Chrome на экране (DISPLAY=${DISPLAY:-?}), пауза шага ${QA_VISIBLE_DELAY}с"
else
    log "Браузер внутри Selenium — смотри http://127.0.0.1:7900 (noVNC). Для окна на экране подними start-chromedriver-wsl.sh"
fi

# Предупреждение о длительности прогона только при включённой паузе.
PAUSE_ACTIVE=$(awk -v d="$QA_VISIBLE_DELAY" 'BEGIN { print (d > 0) ? 1 : 0 }')
if [ "$PAUSE_ACTIVE" = "1" ]; then
    TASK_CEST_DIR="$TASKS_DIR/$TASK/tests"
    METHOD_COUNT=$(grep -rnE 'public function [a-zA-Z0-9_]+\(AcceptanceTester' "$TASK_CEST_DIR" 2>/dev/null | wc -l || echo 0)
    [ "$METHOD_COUNT" -eq 0 ] && METHOD_COUNT=1
    ESTIMATED_MIN=$(( (METHOD_COUNT * 40 + 59) / 60 ))
    log "ВНИМАНИЕ: прогон займет примерно: число шагов * ${QA_VISIBLE_DELAY}с (около ${ESTIMATED_MIN}-2 мин на ${METHOD_COUNT} метод(ов) Cest). Ожидайте."
fi
link_task_tests "$TASK"

# Чистый _output: иначе в отчёт попадут скрины прошлого прогона.
# Файлы часто принадлежат root (прошлый docker run) — чистим через alpine.
if ! rm -rf "$OUT_DIR" 2>/dev/null; then
    docker run --rm -v "$OUT_DIR:/out" alpine sh -c 'rm -rf /out/* /out/.[!.]*' 2>/dev/null || true
    rm -rf "$OUT_DIR" 2>/dev/null || true
fi
mkdir -p "$OUT_DIR"

CODECEPT_ARGS=(run Acceptance --steps --html --xml)
[ -n "$FILTER" ] && CODECEPT_ARGS+=("$FILTER")
CODECEPT_ARGS+=(-g "$GROUP")
[ "$WD_MODE" = "selenium" ] && CODECEPT_ARGS+=(--env chromedriver)
if [ "$PHASE" = "stage" ]; then
    # Stage mode narrows the run to one plan stage. Stages are tagged in Cest
    # with `@stage-K` annotations; the filter keeps unrelated stages out.
    CODECEPT_ARGS+=("--grep" "@stage-${STAGE_NUM}")
    log "Режим этапа: только методы с @stage-${STAGE_NUM}"
fi

RUN_CODE=0
if [ "$PRECHECK_CODE" -ne 0 ]; then
    RUN_CODE=1
    printf 'Browser run skipped because mandatory prechecks failed. See prechecks.jsonl and *.log.\n' > "$OUT_DIR/run.log"
else
    info "Запуск"
    set +e
    # QA_RUN_TIMEOUT guards against a hung browser run. lib.sh applies it around
    # the actual codecept/php/docker call, so the timeout is not lost through a
    # subshell and a verdict is always written.
    export QA_RUN_TIMEOUT="${QA_RUN_TIMEOUT:-3600}"
    run_codecept "$WD_MODE" "${CODECEPT_ARGS[@]}" 2>&1 | tee "$OUT_DIR/run.log"
    RUN_CODE="${PIPESTATUS[0]}"
    if [ "$RUN_CODE" -eq 124 ] || [ "$RUN_CODE" -eq 137 ]; then
        log "Прогон прерван по таймауту ${QA_RUN_TIMEOUT}с, вердикт будет red"
    fi
    set -e
fi

info "Сбор артефактов"
mkdir -p "$RUN_DIR"
cp -r "$OUT_DIR/." "$RUN_DIR/" 2>/dev/null || true
log "$RUN_DIR"

python3 "$SCRIPTS_DIR/make-verdict.py" \
    --task "$TASK" \
    --group "$GROUP" \
    --run-dir "$RUN_DIR" \
    --exit-code "$RUN_CODE"

DB_CODE=0
python3 "$SCRIPTS_DIR/db-isolation.py" --task "$TASK" --run-dir "$RUN_DIR" --phase after || DB_CODE=1
AC_CODE=0
python3 "$SCRIPTS_DIR/check-ac-matrix.py" --task "$TASK" --phase result --run-dir "$RUN_DIR" || AC_CODE=1
python3 "$SCRIPTS_DIR/qa-manifest.py" --task "$TASK" --group "$GROUP" --output "$RUN_DIR/current-manifest.json"

if [ "$SKIP_NEIGHBORS" -eq 1 ]; then
    printf '{"status":"skipped","neighbors":[],"errors":[]}\n' > "$RUN_DIR/neighbors.json"
    printf '{"status":"skipped","results":[]}\n' > "$RUN_DIR/neighbor-results.json"
else
    python3 "$SCRIPTS_DIR/resolve-neighbors.py" --task "$TASK" --output "$RUN_DIR/neighbors.json"
    printf '{"status":"passed","results":[]}\n' > "$RUN_DIR/neighbor-results.json"
    while IFS=$'\t' read -r neighbor_task neighbor_group; do
        [ -n "$neighbor_task" ] || continue
        set +e
        bash "$SCRIPTS_DIR/task-test.sh" "$neighbor_task" --group "$neighbor_group" --skip-neighbors
        neighbor_code=$?
        set -e
        python3 - "$RUN_DIR/neighbor-results.json" "$neighbor_task" "$neighbor_group" "$neighbor_code" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
code = int(sys.argv[4])
entry = {'task': sys.argv[2], 'group': sys.argv[3], 'exit_code': code}
# The child run writes its own verdict.json. An exit code of 0 only means the
# runner finished; it does not mean the neighbour flow stayed green. Read the
# verdict so a red neighbour is not recorded as passed.
runs = pathlib.Path('.doc/tasks') / sys.argv[2] / 'test-runs'
verdict_green = None
if runs.is_dir():
    dirs = sorted([p for p in runs.iterdir() if p.is_dir()], key=lambda p: p.name)
    for candidate in reversed(dirs):
        vp = candidate / 'verdict.json'
        if vp.exists():
            try:
                vdata = json.loads(vp.read_text())
            except json.JSONDecodeError:
                break
            if sys.argv[3] and vdata.get('group') not in (None, sys.argv[3]):
                continue
            verdict_green = bool(vdata.get('green'))
            entry['verdict_green'] = verdict_green
            entry['run_dir'] = str(candidate)
            break
data.setdefault('results', []).append(entry)
if code != 0 or verdict_green is False:
    data['status'] = 'failed'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
PY
        [ "$neighbor_code" -eq 0 ] || RUN_CODE=1
    done < <(python3 - "$RUN_DIR/neighbors.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding='utf-8'))
for item in data.get('neighbors', []):
    print(f"{item['task']}\t{item['group']}")
PY
)
fi

# Produce the final machine report only after required neighboring flows have
# completed. Historical comparison and LLM review are evidence layers, not a
# replacement for deterministic assertions.
python3 "$SCRIPTS_DIR/compare-runs.py" --task "$TASK" --run-dir "$RUN_DIR"
python3 "$SCRIPTS_DIR/llm-review.py" --task "$TASK" --run-dir "$RUN_DIR"

# Neighbor flows can change the overall result; persist the final exit code,
# rather than leaving verdict.json from the pre-neighbor phase.
python3 "$SCRIPTS_DIR/make-verdict.py" \
    --task "$TASK" --group "$GROUP" --run-dir "$RUN_DIR" --exit-code "$RUN_CODE"
python3 "$SCRIPTS_DIR/make-report.py" --task "$TASK" --run-dir "$RUN_DIR"
python3 "$SCRIPTS_DIR/record-history.py" --task "$TASK" --run-dir "$RUN_DIR"

if [ "$RUN_CODE" -ne 0 ] || [ "$DB_CODE" -ne 0 ] || [ "$AC_CODE" -ne 0 ]; then
    exit 1
fi
exit 0
