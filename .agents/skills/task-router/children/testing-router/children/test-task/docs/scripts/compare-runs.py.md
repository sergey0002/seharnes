# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/compare-runs.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, compare-runs]
-->

## Суть
Сравнивает текущий прогон задачи с предыдущим прогоном той же задачи. Это регрессионный алерт, а не снапшот-оракул: динамический HTML и ID базы данных не сравниваются побайтно. Сравнивается стабильный контракт: идентичность тестов, AC-идентификаторы, статусы результатов, console/error evidence и доступность артефактов. Улучшения относительно сломанного/пустого бейзлайна (пустые AC → все passed) не считаются провалами.

## Когда запускать
- Автоматически в `task-test.sh` после прогона (создаёт `comparison.json` в run-dir)
- В `gates.py` (проверка comparison.json status)
- При ручном анализе регрессий между прогонами

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --run-dir |  | string | да |  | Путь к каталогу текущего прогона |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Всегда (результат в JSON) | читать comparison.json |

## Что читает и что пишет
**Читает:**
- `{run-dir}/verdict.json` — сводка прогона
- `{run-dir}/ac-results.json` — результаты AC
- `{prev-run}/verdict.json` — предыдущий прогон (по mtime)
- `{prev-run}/ac-results.json` — AC предыдущего прогона

**Пишет:**
- `{run-dir}/comparison.json` — результат сравнения:
  - `status`: `passed` / `failed` / `no_baseline`
  - `previous`: путь к предыдущему прогону
  - `changes`: массив изменений (test-regression, ac-regression, current-failures, browser-noise, ac-results-changed)

## Побочные эффекты
- File write: `comparison.json`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/compare-runs.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022
```

## Ограничения
- Не сравнивает скриншоты/HTML побайтно
- Предыдущий прогон ищется по mtime в той же папке задачи
- Пустой baseline (нет предыдущего) → статус `no_baseline` (не блокирует)
- Улучшения (failed → passed) не помечаются как регрессия
- Только блокирующие регрессии: passed→failed, новые failedTests, рост consoleErrors/errorModals

## Связи
- Вызывается: `task-test.sh`, `gates.py` (проверка comparison.json)
- Читает: `make-verdict.py` (verdict.json), `make-report.py` (ac-results.json)

## История изменений
- 2026-11-07: полная документация (status: draft → actual)