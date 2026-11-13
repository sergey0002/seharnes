# Скрипт: `.agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../scripts/chromedriver-host-relay.py, .doc/qa/browser-setup.md]
tags: [harness, script, browser-verify, chromedriver, wsl, docker, headed]
-->

## Суть
Запуск Chrome for Testing chromedriver в WSL с видимым окном браузера (headed через WSLg/DISPLAY=:0) и HTTP релеем для доступа из Docker Desktop. Скрипт: проверяет наличие chromedriver в `~/.local/chrome-for-testing/chromedriver-linux64/chromedriver`, настраивает `LD_LIBRARY_PATH` для зависимостей Chrome, убивает старые процессы, стартует chromedriver на порту 9516 (loopback, `--allowed-origins=*`, `--url-base=/wd/hub`), ждёт readiness (`/wd/hub/status`), запускает `chromedriver-host-relay.py` на порту 9515 (переписывает Host для Docker), проверяет релей. Выводит PIDs и порты.

## Когда запускать
Перед запуском Codeception Acceptance тестов в Docker (`browser-verify`, `test-task`). Вызывается вручную или из `browser-verify` SKILL.md. Если не запустить — Codeception не сможет подключиться к chromedriver (connection refused или "Rejecting request with non-local host").

## Аргументы
Нет (все параметры жёстко в скрипте).

## Переменные окружения (вход)
| Переменная | Описание |
|---|---|
| `DISPLAY` | X11 display (по умолчанию `:0` если есть `/tmp/.X11-unix/X0`) |
| `WAYLAND_DISPLAY` | Wayland display (пробрасывается в chromedriver) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: chromedriver + релей запущены, готовы к подключению | Запускать тесты |
| 1 | Ошибка: chromedriver не найден, не executable, нет DISPLAY, chromedriver не запустился, релей не запустился | Прочитать stderr, исправить причину (см. `.doc/qa/browser-setup.md`) |

## Что читает и что пишет
**Читает:**
- `~/.local/chrome-for-testing/chromedriver-linux64/chromedriver` — бинарник
- `~/.local/chrome-deps/root/usr/lib/x86_64-linux-gnu` и `.../lib/x86_64-linux-gnu` — зависимости
- `chromedriver-host-relay.py` (рядом со скриптом) — релей
- Переменные `DISPLAY`, `WAYLAND_DISPLAY`

**Пишет (логи):**
- `~/.local/chrome-for-testing/chromedriver-9516.log` — stdout/stderr chromedriver
- `~/.local/chrome-for-testing/chromedriver-relay-9515.log` — stdout/stderr релея
- Stdout: итоговые строки с PIDs и портами

## Побочные эффекты
- Запускает два фоновых процесса: chromedriver (PID) и python релей (PID)
- Открывает TCP порты 9516 (chromedriver) и 9515 (релей) на 127.0.0.1
- Убивает старые процессы chromedriver и релея (`pkill -f`)
- Не пишет в проект, не меняет git

## Окружение и зависимости
- WSL2 с WSLg (или X-сервер с `DISPLAY=:0`)
- `~/.local/chrome-for-testing/chromedriver-linux64/chromedriver` (Chrome for Testing, версия под Chrome в системе)
- `~/.local/chrome-deps/root/...` — библиотеки Chrome (libnss3, libatk, etc.)
- `python3` в PATH (для релея)
- `curl` в PATH (для health-check)
- `chromedriver-host-relay.py` в той же директории

## Примеры
```bash
# Стандартный запуск
bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh

# Проверка что запущено
curl http://127.0.0.1:9515/wd/hub/status
curl http://127.0.0.1:9516/wd/hub/status

# Остановка
pkill -f "chromedriver-linux64/chromedriver"
pkill -f "chromedriver-host-relay.py"
```

## Ограничения
- **Только headed** — не добавлять `--headless` (Chrome открывается видимым окном на экране)
- Только WSL/Linux — не работает на macOS/Windows напрямую
- Жёстко заданные порты 9515/9516 и пути `~/.local/chrome-for-testing/`
- Не управляет жизненным циклом Chrome браузера — только chromedriver
- Если `DISPLAY` не задан и нет `/tmp/.X11-unix/X0` — ошибка
- `allowed-ips` не задаётся намеренно (пустое значение запрещало все адреса)
- Health-check только `/wd/hub/status` — не проверяет создание сессий

## Связи
- Вызывается: `browser-verify` SKILL.md, вручную перед тестами
- Зависит от: `chromedriver-host-relay.py`, Chrome for Testing установки
- Результат потребляет: Codeception в Docker (php-webdriver → `host.docker.internal:9515` → релей → chromedriver:9516)
- Связанные: `chromedriver-host-relay.py`, `.doc/qa/browser-setup.md`, `test-task` SKILL.md

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода