# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/doctor.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, doctor]
-->

## Суть
Fail-fast диагностика окружения для запуска браузерных тестов задачи. Проверяет Docker, контейнеры приложения и БД, HTTP-эндпойнты приложения и WebDriver, наличие `.env` для Codeception и бинарников внутри контейнера. Возвращает машинный JSON или человекочитаемый отчёт. Используется как pre-check перед прогоном `test-task.sh` и в CI.

## Когда запускать
- Перед первым запуском `task-test.sh` в новой сессии.
- В CI перед прогоном задач — чтобы не тратить время на Codeception при нерабочем стенде.
- Локально при ошибках «connection refused» или «chromedriver not ready».
- Можно вызвать вручную: `python3 .../doctor.py 2605 --json`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task | | string | нет | | Номер задачи CT-N; включает проверку `db-isolation` hooks из `ac-matrix.json` |
| --json | | flag | нет | | Машинный вывод (JSON) вместо текстового |
| --require-browser | | flag | нет | | Требует готовность WebDriver (local или Selenium); без флага WebDriver помечается «not required» |
| --require-db | | flag | нет | | В связке с `--task` проверяет реальные DB reset/cleanup hooks |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверки пройдены | Продолжать прогон |
| 1 | Есть проваленные проверки | Не запускать тесты; исправить окружение |
| 2 | Критическая ошибка (нет test.md при --task) | Прервать; проверить аргументы |

## Что читает и что пишет
- Читает: `.tools/codeception/.env` (ключи MYSQL_*, CHROMEDRIVER_*), `.doc/tasks/{N}/ac-matrix.json` (поле `db_isolation`).
- Пишет: только stdout (JSON или текст). Никаких файлов не создаёт.
- Сеть: HTTP к `CHROMEDRIVER_APP_URL` (по умолчанию `http://127.0.0.1:8030/`), `http://127.0.0.1:9515/wd/hub/status`, `http://127.0.0.1:4444/status`.
- Docker: `docker context show`, `docker inspect` контейнеров `copytrust-dev-php-apache-1` и `copytrust-dev-mysql-1`, `docker exec` для проверки бинарников и монтирования конфига.

## Побочные эффекты
- Нет изменений в файловой системе или БД.
- Только read-only проверки контейнеров и HTTP.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| CHROMEDRIVER_APP_URL | URL приложения для health-check (default `http://127.0.0.1:8030/`) |
| QA_DB_CLEANUP_CMD | Hook очистки БД после теста (проверяется на no-op) |
| QA_DB_RESET_CMD | Hook сброса БД перед тестом (проверяется на no-op) |
| QA_MYSQL_CONTAINER | Имя MySQL контейнера (default `copytrust-dev-mysql-1`) |
| QA_PHPUNIT_CONTAINER | Имя PHP-Apache контейнера (default `copytrust-dev-php-apache-1`) |

## Примеры
```bash
# Базовая проверка окружения (текстовый вывод)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/doctor.py

# С задачей и JSON для CI
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/doctor.py --task 2605 --json

# С требованием WebDriver и БД-хуков
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/doctor.py --task 2605 --require-browser --require-db
```

## Ограничения
- Не поднимает контейнеры — только проверяет, что они уже запущены.
- Не проверяет содержимое БД, только доступность контейнера и наличие хуков.
- Проверка PHP бинарников ограничена наличием `phpunit`, `doctrine-migrations`, `bootstrap.php`.
- Не валидирует `.env` значения — только наличие ключей.

## Связи
- Вызывается: `preflight.sh`, `test-batch.sh`, `task-test.sh` (внутри), CI pipeline.
- Зависит: Docker daemon, запущенные контейнеры, `.tools/codeception/.env`.
- Документирует результат: `verdict.json` → `artifacts.doctor` (через gates.py G12).

## История изменений
- 2026-11-07: полная документация на основе реализации (был draft скелет)