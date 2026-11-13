# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/make-verdict.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, make-verdict]
-->

## Суть
Строит сводку прогона в `verdict.json`: счётчики тестов + шум из `checkpoint()`. Читает артефакты Codeception из каталога прогона:
- `report.xml` — JUnit, счётчики и имена упавших тестов
- `checkpoints.jsonl` — что записал `AcceptanceTester::checkpoint()`
- `run.log` — сырой вывод, если XML не создался

`verdict.json` потом читает `gates.py` (гейты G3/G4) и отчёт `test-runs`. Отдельный файл, а не парсинг глазами: агент не должен «на глаз» определять, зелёный прогон или нет.

## Когда запускать
- Автоматически в `task-test.sh` сразу после завершения Codeception
- Для ручной пересборки verdict из артефактов

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --group |  | string | да |  | Группа Codeception (task-{N}, flow-{name}) |
| --run-dir |  | string | да |  | Путь к каталогу прогона |
| --exit-code |  | int | да |  | Exit код Codeception процесса |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Всегда (результат в файле) | читать verdict.json |

## Что читает и что пишет
**Читает:**
- `{run-dir}/report.xml` — JUnit XML
- `{run-dir}/checkpoints.jsonl` — checkpoint записи
- `{run-dir}/run.log` — fallback
- Артефакты статусов: `static.json`, `lint.json`, `phpunit.json`, `ac-check.json`, `db-isolation.json`, `comparison.json`, `llm-review.json`, `neighbor-results.json`, `manifest.json`

**Пишет:**
- `{run-dir}/verdict.json` — полная сводка:
  - `task`, `group`, `runDir`, `exitCode`, `green` (bool)
  - `tests`: total/passed/failed/errors/skipped, failedTests[], testcases[]
  - `checkpoints`: count, consoleErrors[], errorModals[], toasted[]
  - `screenshots`: список .png
  - `artifacts`: статусы слоёв
  - `hashesMatch`: fingerprint совпал (через qa-manifest.py)
  - `comparison`, `llmReview`, `neighborResults` — статусы артефактов

**Вывод (stdout):**
- Человекочитаемая сводка: счётчики, упавшие тесты, checkpoint-шум, скриншоты, green yes/no

## Побочные эффекты
- File write: `verdict.json`
- Запуск `qa-manifest.py --check` для fingerprint

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/make-verdict.py \
  --task 2605 --group task-2605 \
  --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022 \
  --exit-code 0
```

## Ограничения
- `green=true` требует: exit_code=0, total>0, lint=passed, static=passed, phpunit∈{passed,skipped,baseline_failed}, ac=passed, db=passed, neighbor∈{passed,skipped}, comparison∈{passed,no_baseline}, llm∈{passed,skipped}, hashesMatch=true
- Если JUnit XML нет — берёт только summary из run.log (нет деталей тестов)
- fingerprint проверяется через qa-manifest.py (code/tests/requirements/skills/environment SHA256)

## Связи
- Вызывается: `task-test.sh`
- Читается: `gates.py` (G3, G4), `make-report.py`, `compare-runs.py`, `llm-review.py`
- Канон: `.doc/harnes/tests.md` § verdict

## История изменений
- 2026-11-07: полная документация (status: draft → actual)