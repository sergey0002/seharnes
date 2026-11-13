# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, task-test, testing, codeception, playwright]
-->

## Суть
Оркестратор полного прогона браузерных тестов задачи: prechecks (doctor, static analysis, PHPUnit, branch-audit), запуск Codeception Acceptance (видимый браузер), сбор артефактов, верификация соседних флоу (neighbor regression), генерация verdict.json и HTML-отчёта. Не поднимает стенд и chromedriver — только проверяет их доступность.

## Когда запускать
Запускать после реализации задачи для проверки соответствия acceptance criteria. Обязателен перед сдачей задачи (`тестируй задачу`).
Фаза `--phase preflight` — только статические проверки без браузера.
Фаза `--phase browser` — только браузерный слой (prechecks + Codeception).
Фаза `--phase stage` — изолированный прогон одной стадии плана (`--stage-num K`).
Фаза `--phase finalize` — завершение прогона по существующему каталогу `--run-dir`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `TASK` | — | число | да | — | номер задачи Jira (CT-N) |
| `--group` | — | строка | нет | `task-{TASK}` | группа Codeception для фильтра тестов |
| `--filter` | — | строка | нет | — | фильтр методов Codeception (имя метода/класса) |
| `--phase` | — | выбор | нет | `all` | `preflight\|unit\|browser\|all\|stage\|finalize` |
| `--stage-num` | — | число | при phase=stage | — | номер стадии плана для изолированного прогона |
| `--run-dir` | — | путь | при phase=finalize | — | существующий каталог прогона для финализации |
| `--skip-neighbors` | — | флаг | нет | выкл. | пропустить регрессию соседних флоу |
| `-h`, `--help` | — | флаг | нет | выкл. | показать краткую справку и выйти |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | все проверки зелёные, соседние флоу пройдены | задача готова к сдаче |
| 1 | любой гейт упал (precheck, Codeception, neighbor, AC matrix, DB isolation) | изучить артефакты в `$RUN_DIR`, исправить и перезапустить |
| 124 | таймаут `QA_RUN_TIMEOUT` (по умолчанию 3600с) | увеличить таймаут или оптимизировать тесты |
| 137 | процесс убит сигналом (SIGTERM/SIGKILL) | проверить ресурсы системы, перезапустить |

## Что читает и что пишет
Читает: `.doc/tasks/{TASK}/tests/` (Cest-файлы вне git), `.doc/tasks/{TASK}/diff.files.md`, `.doc/qa/index.md`, `.env`, переменные `CODECEPT_DIR`, `TASKS_DIR`, `DISPLAY`, `QA_VISIBLE_DELAY`, `QA_RUN_TIMEOUT`, `QA_PHPSTAN_LEVEL`, `QA_PHPUNIT_PROFILE`.
Пишет: `.doc/tasks/{TASK}/test-runs/{timestamp}_{group}/` — `verdict.json`, `manifest.json`, `ac-results.json`, `prechecks.jsonl`, `static.json`, `neighbors.json`, `neighbor-results.json`, `gates.json`, `current-manifest.json`, HTML/скриншоты Codeception, `run.log`, `*.log` пречекей.

## Побочные эффекты
Создаёт каталог прогона с артефактами.
Запускает видимый браузер (Chrome через chromedriver или Selenium/NoVNC).
Очищает `$CODECEPT_DIR/tests/_output` (может требовать root/docker для удаления старых файлов).
Вызывает `db-isolation.py` (фикстуры БД до/после), `make-verdict.py`, `make-report.py`, `record-history.py`, `compare-runs.py`, `llm-review.py`.
Меняет состояние БД стенда через фикстуры тестов.

## Окружение и зависимости
Требует: `bash`, `python3`, `docker` (для очистки _output от root), `codecept` (Codeception), `chromedriver` (локально или через Selenium), работающий стенд на `:8030`.
Переменные: `CODECEPT_DIR`, `TASKS_DIR`, `DISPLAY`, `QA_VISIBLE_DELAY` (пауза между шагами, умолч. `0` - выключена; `0.3` включает показ действий), `QA_RUN_TIMEOUT` (умолч. 3600с), `QA_PHPSTAN_LEVEL` (умолч. 8), `QA_PHPUNIT_PROFILE` (умолч. `task`).

## Примеры
```bash
# Полный прогон задачи 2236
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236

# Только статические проверки (preflight)
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --phase preflight

# Только браузерный слой с фильтром по группе
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --phase browser --group item-draft

# Изолированный прогон стадии 2 плана
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --phase stage --stage-num 2

# Финализация существующего прогона
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2236 --phase finalize --run-dir .doc/tasks/2236/test-runs/2026-11-07_143000_task-2236
```

## Ограничения
Не поднимает стенд (`:8030`) и не запускает `chromedriver` — если они недоступны, скрипт печатает команду запуска и завершается с ошибкой пречека.
`--phase stage` требует наличия тестов с аннотацией `@stage-K` в Cest.
Результаты соседних флоу влияют на итоговый код выхода (если сосед упал — общий код 1).
Артефакты прогона не коммитятся в git (`.doc/` в .gitignore).

## Связи
Скил: `test-task` (оркестратор). Использует библиотеку `lib.sh` из того же каталога.
Вызывает: `doctor.py`, `branch-audit.py`, `check-ac-matrix.py`, `static-on-diff.py`, `qa-lint.py`, `run-phpunit.py`, `db-isolation.py`, `qa-manifest.py`, `make-verdict.py`, `make-report.py`, `record-history.py`, `compare-runs.py`, `llm-review.py`, `resolve-neighbors.py`, `gates.py`.
Гейт: `harness doctor` → `test-task` → `test-priority.mdc` порядок прогона.

## История изменений
- 2026-11-07: документ составлен из исходника, статус actual, все аргументы и коды выхода сверены