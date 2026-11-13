# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/db-isolation.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, db-isolation]
-->

## Суть
Запускает явные, проект-предоставленные хуки сброса/очистки БД для задач, требующих изоляции данных (`ac-matrix.json: db_isolation: required`). Не угадывает SQL — требует `QA_DB_RESET_CMD` (фаза `before`) и `QA_DB_CLEANUP_CMD` (фаза `after`). No-op команды (`true`, `:`, `echo`, `/bin/true`) отклоняются. Агрегирует результаты обеих фаз в `db-isolation.json` с честным статусом: `not_required` (изоляция не требовалась), `passed` (обе фазы прошли), `failed` (хотя бы одна упала или no-op).

## Когда запускать
- В `test-task.sh`: фаза `before` перед Codeception, фаза `after` после.
- Только для задач с `db_isolation: required` в `ac-matrix.json`.
- Не вызывать вручную без задачи — просто вернёт `skipped`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task | | string | да | | Номер задачи CT-N |
| --run-dir | | string | да | | Каталог прогона для `db-isolation.json` |
| --phase | | string | да | | `before` (сброс перед тестами) или `after` (очистка после) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Фаза пройдена / пропущена (not_required) | Продолжить |
| 1 | Хук упал / не задан / no-op | Не запускать тесты / пометить провал изоляции |

## Что читает и что пишет
- Читает: `.doc/tasks/{N}/ac-matrix.json` (поле `db_isolation`), env vars `QA_DB_RESET_CMD`, `QA_DB_CLEANUP_CMD`.
- Пишет: `{run-dir}/db-isolation.json` с полями `phases[]` (каждая: status, phase, command, exit_code, output) и агрегированный `status`.
- Запускает: shell-команду из env var в корне репо (`cwd=REPO`, `shell=True`, timeout 300s).

## Побочные эффекты
- **Выполняет SQL/скрипты БД** через переданные хуки. Может менять данные в БД стенда.
- Не откатывает изменения при ошибке — это ответственность хука cleanup.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| QA_DB_RESET_CMD | Команда сброса БД перед тестами (обязательна для `required`) |
| QA_DB_CLEANUP_CMD | Команда очистки после тестов (обязательна для `required`) |

## Примеры
```bash
# До тестов (в test-task.sh)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/db-isolation.py --task 2605 --run-dir .doc/tasks/2605/test-runs/... --phase before

# После тестов
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/db-isolation.py --task 2605 --run-dir .doc/tasks/2605/test-runs/... --phase after
```

## Ограничения
- Не работает без `ac-matrix.json` с `db_isolation: required`.
- No-op хуки считаются ошибкой — предотвращает false-green.
- Агрегация: если обе фазы `skipped` → общий `not_required`; если есть `passed` и нет `failed` → `passed`; иначе `failed`.
- Таймаут 300 секунд на хук.
- Не валидирует SQL — только exit code хука.

## Связи
- Вызывается: `test-task.sh` (before/after Codeception), `gates.py` (G12, G6).
- Зависит: `ac-matrix.json`, env vars с хуками.
- Результат: `db-isolation.json` → `verdict.json.artifacts.db` → G12.

## История изменений
- 2026-11-07: полная документация на основе реализации (был draft скелет)