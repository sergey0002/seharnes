#!/usr/bin/env bash
# Предполёт перед браузерным прогоном задачи.
#
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605 --skip-prod
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605 --level 8
#
# Порядок:
#   1) очистка Smarty templates_c + cache (как после деплоя)
#   2) статика только по строкам патча: PHPStan L5 + ESLint strict
#      (в CI мягче: PHPStan L0 + lint:basic на frontend/entry)
#   3) yarn prod, если в diff есть frontend/entry или --force-prod
#   4) check-tests.sh (Cest/селекторы без браузера)
#
# Важно: «Vue-тесты» в GitVerse deploy = ESLint + yarn prod, не jest/vitest.

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TASK=""
LEVEL=8
SKIP_PROD=0
FORCE_PROD=0
SKIP_STATIC=0
SKIP_CHECK=0

while [ $# -gt 0 ]; do
    case "$1" in
        --level) LEVEL="$2"; shift 2 ;;
        --skip-prod) SKIP_PROD=1; shift ;;
        --force-prod) FORCE_PROD=1; shift ;;
        --skip-static) SKIP_STATIC=1; shift ;;
        --skip-check) SKIP_CHECK=1; shift ;;
        -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
        *)
            [ -z "$TASK" ] || die "лишний аргумент: $1"
            TASK="$1"; shift ;;
    esac
done

[ -n "$TASK" ] || die "нужен номер задачи. Пример: preflight.sh 2605"
[[ "$TASK" =~ ^[0-9]+$ ]] || die "номер задачи — только цифры"

DIFF_FILES="$TASKS_DIR/$TASK/diff.files.md"
[ -f "$DIFF_FILES" ] || die "нет $DIFF_FILES — сначала «обнови диф задачи $TASK»"

need_yarn_prod() {
    [ "$FORCE_PROD" = 1 ] && return 0
    grep -E '^(frontend/entry/|webpack\.config\.js|package\.json)' "$DIFF_FILES" >/dev/null 2>&1
}

run_yarn_prod() {
    info "Сборка фронта (yarn prod), как в deploy-test"
    if ! command -v yarn >/dev/null 2>&1; then
        die "нет yarn на хосте. Поставь yarn или собери фронт в CI-образе Node"
    fi
    if [ ! -d "$REPO_ROOT/node_modules" ]; then
        die "нет node_modules. Один раз: yarn install (как в CI перед lint/prod)"
    fi
    ( cd "$REPO_ROOT" && yarn prod )
    [ -d "$REPO_ROOT/frontend/dist" ] || die "после yarn prod нет frontend/dist"
    log "frontend/dist готов"
}

info "Preflight CT-$TASK (локаль: PHPStan L$LEVEL + ESLint patch-max, не в git)"

clear_smarty_cache

if [ "$SKIP_STATIC" = 0 ]; then
    info "Статика по строкам патча (макс, только .doc/)"
    python3 "$SCRIPTS_DIR/static-on-diff.py" "$TASK" --level "$LEVEL"
else
    log "статика пропущена (--skip-static)"
fi

if [ "$SKIP_PROD" = 1 ]; then
    log "yarn prod пропущен (--skip-prod)"
elif need_yarn_prod; then
    run_yarn_prod
else
    log "yarn prod не нужен: в diff нет frontend/entry (legacy scripts/*.js отдаются как есть)"
    log "для принудительной пересборки: preflight.sh $TASK --force-prod"
fi

if [ "$SKIP_CHECK" = 0 ]; then
    info "Быстрая проверка Cest/селекторов"
    bash "$SCRIPTS_DIR/check-tests.sh"
else
    log "check-tests пропущен (--skip-check)"
fi

info "Preflight CT-$TASK готов → дальше: bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh $TASK"
