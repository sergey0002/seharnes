#!/usr/bin/env bash
# Быстрая проверка тестов без браузера и стенда:
# загрузка всех Cest, битые симлинки задач, коллизии классов, селекторы.
#
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh
#
# Гонять после prepare-task-test и перед task-test.sh: ловит львиную долю
# проблем за пару секунд вместо полного прогона.

set -euo pipefail
# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

STATUS=0

info "Реестр data-test"
python3 "$SCRIPTS_DIR/collect-data-test.py"

info "Селекторы"
python3 "$SCRIPTS_DIR/check-selectors.py" || STATUS=1

info "Загрузка Cest"
if host_php_ok; then
    ( cd "$CODECEPT_DIR" && php "$SCRIPTS_DIR/check-tests-load.php" "$CODECEPT_DIR" ) || STATUS=1
else
    ensure_runner_image
    docker run --rm -v "$REPO_ROOT:/app" -v "$SCRIPTS_DIR:/qa-scripts:ro" -w /app/.tools/codeception \
        "$RUNNER_IMAGE" php /qa-scripts/check-tests-load.php /app/.tools/codeception || STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then
    info "Всё чисто"
else
    info "Есть проблемы, смотри выше"
fi

exit "$STATUS"
