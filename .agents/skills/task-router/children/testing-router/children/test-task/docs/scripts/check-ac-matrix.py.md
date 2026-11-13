# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-ac-matrix.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-ac-matrix]
-->

## Суть
Валидирует машиночитаемую матрицу приёмочных критериев (`ac-matrix.json` или `requirements.json`) и её evidence после прогона. Проверяет: структуру JSON, уникальность `id` (формат `AC-XX`), наличие `text`, `test` (формат `Class::method`), `expected`. Проверяет, что метод существует в Cest (`.doc/tasks/{N}/tests`, `.tools/codeception/tests`) или PHPUnit (`tests/lib`). На этапе `result` сверяет `ac-results.json` с матрицей: статус `passed`, наличие evidence, нет дубликатов. Также проверяет `required_neighbors` и `db_isolation`.

## Когда запускать
- После создания/обновления `ac-matrix.json` — фаза `source`.
- После прогона тестов — фаза `result` с `--run-dir` (в `test-task.sh`).
- В `gates.py` G12 (машинный AC gate).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task | | string | да | | Номер задачи CT-N |
| --run-dir | | string | нет | | Каталог прогона для фазы `result` |
| --phase | | string | нет | source | `source` — валидация матрицы; `result` — сверка с `ac-results.json` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Матрица валидна (и evidence прошло при `result`) | OK |
| 1 | Ошибки валидации или evidence не прошло | Исправить матрицу или тесты |
| 2 | Нет файла матрицы | Создать `ac-matrix.json` через `prepare-task-test` |

## Что читает и что пишет
- Читает: `.doc/tasks/{N}/ac-matrix.json` (или `requirements.json`), `.doc/tasks/{N}/tests/**/*.php`, `.tools/codeception/tests/**/*.php`, `tests/lib/**/*.php`, при `--phase result` — `{run-dir}/ac-results.json`, `{run-dir}/phpunit.json`.
- Пишет: при `--run-dir` — `{run-dir}/ac-source.json` (фаза source) или `{run-dir}/ac-check.json` (фаза result). В stdout — JSON с `status`, `errors`.

## Побочные эффекты
- Создаёт файлы отчёта в `--run-dir` (только при явном аргументе).

## Окружение и зависимости
Переменных окружения не используется.

## Примеры
```bash
# Валидация самой матрицы
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-ac-matrix.py --task 2605 --phase source

# Сверка evidence после прогона
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-ac-matrix.py --task 2605 --phase result --run-dir .doc/tasks/2605/test-runs/2026-11-07_143000
```

## Ограничения
- Не создаёт матрицу — только валидирует. Создание через `prepare-task-test`.
- Метод в `test` должен быть точно `Class::method`; fuzzy-поиск не делается.
- Дубликаты `recordAcceptanceCriterion` в Cest-коде детектятся и считаются ошибкой.
- `db_isolation` только `required`/`not_required`; другие значения — ошибка.
- PHPUnit evidence считается пройденным, если `phpunit.json.status == "passed"`.

## Связи
- Вызывается: `test-task.sh`, `gates.py` (G12), `prepare-task-test` (после генерации).
- Зависит: `ac-matrix.json`, Cest/PHPUnit исходники.
- Результат: `ac-check.json` → `verdict.json.artifacts.ac` → G12.

## История изменений
- 2026-11-07: полная документация на основе реализации (был draft скелет)