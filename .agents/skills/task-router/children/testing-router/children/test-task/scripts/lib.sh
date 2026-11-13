#!/usr/bin/env bash
# Общие функции раннера тестов задач.
#
# Инкапсулирует то, что раньше приходилось помнить из .doc/qa/browser-setup.md:
# хост без PHP 8.2+, два порта WebDriver (9515 / 4444), сеть Selenium,
# host-resolver-rules. Подключается через `source`.
#
# Ничего не запускает сам: стенд и chromedriver поднимает человек
# (правило .doc/harnes/tests.md — агент стенды не поднимает без спроса).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../../../../" && pwd)"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODECEPT_DIR="$REPO_ROOT/.tools/codeception"
QA_DIR="$REPO_ROOT/.doc/qa"
TASKS_DIR="$REPO_ROOT/.doc/tasks"
RUNNER_IMAGE="copytrust-codecept:8.3"
SELENIUM_CONTAINER="${SELENIUM_CONTAINER:-selenium-chrome-test}"

log()  { printf '  %s\n' "$*" >&2; }
info() { printf '\n== %s\n' "$*" >&2; }
die()  { printf '\nОШИБКА: %s\n' "$*" >&2; exit 1; }

# --- .env -------------------------------------------------------------

load_env() {
    [ -f "$CODECEPT_DIR/.env" ] || die "нет $CODECEPT_DIR/.env (скопируй .env.dist)"
    set -a
    # shellcheck disable=SC1091
    . "$CODECEPT_DIR/.env"
    set +a
}

# --- Предполётные проверки -------------------------------------------

# Стенд приложения отвечает?
check_app() {
    local url="${CHROMEDRIVER_APP_URL:-http://127.0.0.1:8030/}"
    local probe="http://127.0.0.1:${APP_PORT:-8030}/"
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$probe" 2>/dev/null || echo 000)"
    case "$code" in
        200|301|302) log "стенд $probe: HTTP $code" ;;
        *) die "стенд $probe не отвечает (HTTP $code). Подними tools/docker-dev или tools/docker-test" ;;
    esac
}

# Возвращает режим WebDriver: "local" (9515, окно на экране) либо "selenium" (4444).
# Локальный chromedriver предпочтительнее: Chrome открывается в WSLg и все
# действия видны. Selenium в Docker показывает браузер только через noVNC :7900.
detect_webdriver() {
    if curl -sS --max-time 3 "http://127.0.0.1:9515/wd/hub/status" 2>/dev/null | grep -q '"ready": *true'; then
        echo local
        return 0
    fi
    if curl -sS --max-time 3 "http://127.0.0.1:4444/status" 2>/dev/null | grep -q '"ready": *true'; then
        echo selenium
        return 0
    fi
    die "WebDriver не запущен. Для ВИДИМОГО окна на экране:
    bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh   (порт 9515, WSLg)
  Альтернатива (браузер в Docker, смотреть на http://127.0.0.1:7900):
    docker start $SELENIUM_CONTAINER                          (порт 4444)
  Подробности: .doc/qa/browser-setup.md"
}

# .env часто хранит порт от прошлого режима (4444 vs 9515).
# Codeception читает порт из .env через params, поэтому без override
# раннер подключается не туда, куда смотрит detect_webdriver.
apply_webdriver_env() {
    local wd_mode="$1"
    if [ "$wd_mode" = "selenium" ]; then
        export CHROMEDRIVER_PORT=4444
        export CHROMEDRIVER_HOST=127.0.0.1
    else
        export CHROMEDRIVER_PORT=9515
        export CHROMEDRIVER_HOST=127.0.0.1
    fi
    log "WebDriver порт для прогона: ${CHROMEDRIVER_HOST}:${CHROMEDRIVER_PORT}"
}

# --- Раннер PHP -------------------------------------------------------

# Есть ли на хосте php >= 8.2?
host_php_ok() {
    command -v php >/dev/null 2>&1 || return 1
    php -r 'exit(PHP_VERSION_ID >= 80200 ? 0 : 1);' >/dev/null 2>&1
}

ensure_runner_image() {
    if ! docker image inspect "$RUNNER_IMAGE" >/dev/null 2>&1; then
        info "Собираю образ раннера $RUNNER_IMAGE (один раз)"
        docker build -q -t "$RUNNER_IMAGE" "$QA_DIR/docker" >/dev/null \
            || die "не собрался образ раннера"
    fi
}

# Выполняет codecept с аргументами. Сам выбирает хостовый PHP или docker.
# $1 — режим webdriver (selenium|local), далее аргументы codecept.
# Обёртка с таймаутом: вешает зависший прогон, чтобы не блокировать сессию.
# Код 124/137 означает "прервано по времени" и трактуется как красный вердикт.
with_timeout() {
    local limit="${QA_RUN_TIMEOUT:-}"
    if [ -n "$limit" ] && command -v timeout >/dev/null 2>&1; then
        timeout --signal=TERM --kill-after=30 "$limit" "$@"
        return $?
    fi
    "$@"
}

run_codecept() {
    local wd_mode="$1"; shift
    # Порт из .env перекрываем: иначе params в codeception.yml берут 4444
    # при живом chromedriver на 9515 (и наоборот).
    local port_override=(-o "modules: config: WebDriver: host: ${CHROMEDRIVER_HOST}" -o "modules: config: WebDriver: port: ${CHROMEDRIVER_PORT}")

    if host_php_ok; then
        log "раннер: хостовый PHP $(php -r 'echo PHP_VERSION;')"
        ( cd "$CODECEPT_DIR" && QA_AC_RESULTS_FILE="${QA_AC_RESULTS_FILE:-}" with_timeout php -d register_argc_argv=1 vendor/bin/codecept "$@" "${port_override[@]}" )
        return $?
    fi

    ensure_runner_image
    log "раннер: docker $RUNNER_IMAGE (на хосте нет PHP 8.2+)"

    # Монтируем корень проекта: Codeception лежит в .tools/codeception,
    # а тесты задач в .doc/tasks/{N}/tests подключены симлинками
    # tests/Acceptance/Task/{N} -> ../../../../../.doc/tasks/{N}/tests.
    # При маунте одного .tools симлинк уходит за пределы маунта и
    # Codeception молча не находит ни одного Task-теста.
    local mount=("-v" "$REPO_ROOT:/app" "-w" "/app/.tools/codeception")
    local ac_file="${QA_AC_RESULTS_FILE:-}"
    if [ -n "$ac_file" ]; then
        ac_file="/app/${ac_file#"$REPO_ROOT/"}"
    fi

    if [ "$wd_mode" = "selenium" ]; then
        # Сеть контейнера Selenium: chrome внутри резолвит localhost на хост
        # через host-resolver-rules (browser-setup.md §П-5).
        docker run --rm \
            --network "container:$SELENIUM_CONTAINER" \
            -e "CHROMEDRIVER_PORT=${CHROMEDRIVER_PORT}" \
            -e "CHROMEDRIVER_HOST=${CHROMEDRIVER_HOST}" \
            -e "QA_VISIBLE_DELAY=${QA_VISIBLE_DELAY:-0}" \
            -e "QA_AC_RESULTS_FILE=${ac_file}" \
            -e "DISPLAY=${DISPLAY:-:0}" \
            "${mount[@]}" \
            "$RUNNER_IMAGE" \
            vendor/bin/codecept "$@" "${port_override[@]}" \
            -o "modules: config: WebDriver: capabilities: goog:chromeOptions: args: [\"--no-sandbox\", \"--disable-gpu\", \"--remote-allow-origins=*\", \"--host-resolver-rules=MAP localhost 172.17.0.1\"]"
    else
        # Linux/WSL2: контейнер раннера видит host-loopback через --network host.
        # host.docker.internal указывает на 172.17.0.1 и не достает до relay,
        # который слушает 127.0.0.1:9515.
        local wd_host="127.0.0.1"
        log "WebDriver ${wd_host}:${CHROMEDRIVER_PORT} (Chrome на хосте, видимое окно)"
        docker run --rm \
            --network host \
            -e "CHROMEDRIVER_PORT=${CHROMEDRIVER_PORT}" \
            -e "CHROMEDRIVER_HOST=${wd_host}" \
            -e "QA_VISIBLE_DELAY=${QA_VISIBLE_DELAY:-0}" \
            -e "QA_AC_RESULTS_FILE=${ac_file}" \
            "${mount[@]}" \
            "$RUNNER_IMAGE" \
            vendor/bin/codecept "$@" \
            -o "modules: config: WebDriver: host: ${wd_host}" \
            -o "modules: config: WebDriver: port: ${CHROMEDRIVER_PORT}"
    fi
}

# --- Раскладка тестов задачи -----------------------------------------

# Тесты задачи физически лежат в .doc/tasks/{N}/tests/ (вне git).
# Codeception ищет их в tests/Acceptance/Task/ — связываем симлинком.
# Симлинк тоже внутри .doc/, то есть тоже вне git.
link_task_tests() {
    local task="$1"
    local src="$TASKS_DIR/$task/tests"
    local link="$CODECEPT_DIR/tests/Acceptance/Task/$task"

    [ -d "$src" ] || die "нет каталога тестов $src (создай через prepare-task-test)"

    if [ -L "$link" ]; then
        rm -f "$link"
    elif [ -e "$link" ]; then
        die "$link существует и это не симлинк — разберись вручную"
    fi

    ln -s "../../../../tasks/$task/tests" "$link"
    log "связал tests/Acceptance/Task/$task -> .doc/tasks/$task/tests"
}

# Пересобирает все симлинки задач (например после clone/переезда).
relink_all_tasks() {
    local d task
    for d in "$TASKS_DIR"/*/tests; do
        [ -d "$d" ] || continue
        task="$(basename "$(dirname "$d")")"
        link_task_tests "$task"
    done
}

# Очистка Smarty cache / templates_c на хосте и в dev-контейнере
clear_smarty_cache() {
    info "Очистка Smarty cache / templates_c"
    local removed=0
    for d in \
        "$REPO_ROOT/templates_c" \
        "$REPO_ROOT/admin/templates_c" \
        "$REPO_ROOT/cache"
    do
        [ -d "$d" ] || continue
        local n
        n="$(find "$d" -maxdepth 1 -type f \( -name '*.php' -o -name '*.txt' \) 2>/dev/null | wc -l | tr -d ' ')"
        find "$d" -maxdepth 1 -type f \( -name '*.php' -o -name '*.txt' \) -delete 2>/dev/null || true
        removed=$((removed + n))
        log "$d: снято $n файлов"
    done
    if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^copytrust-dev-php-apache-1$"; then
        docker exec copytrust-dev-php-apache-1 sh -c 'rm -f /var/www/html/templates_c/*.php /var/www/html/admin/templates_c/*.php /var/www/html/cache/*.txt' 2>/dev/null || true
        log "Очищен кэш Smarty внутри контейнера copytrust-dev-php-apache-1"
    fi
    log "Итого снято кэш-файлов: $removed"
}

