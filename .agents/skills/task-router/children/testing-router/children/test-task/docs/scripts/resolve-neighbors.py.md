# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/resolve-neighbors.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, resolve-neighbors]
-->

## Суть
Резолвит и валидирует обязательные соседние флоу (neighbor flows), объявленные задачей в `ac-matrix.json` → `required_neighbors`. Проверяет: сосед — это другой номер задачи с непустой группой, у которого есть папка тестов (`.doc/tasks/{N}/tests/`). Нормализует список, убирает дубликаты, самоссылки. Результат пишется в JSON для `gates.py` / `task-test.sh` (проверка соседних флоу).

## Когда запускать
- Автоматически в `task-test.sh` перед прогоном соседних флоу
- В `gates.py` (проверка neighbor-results.json)

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --output |  | string | да |  | Путь для записи результата |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (даже если ошибки валидации — в JSON status=failed) | читать JSON |
| 1 | Ошибка выполнения (нет ac-matrix.json) | проверить stderr |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/ac-matrix.json` — поле `required_neighbors[]` (объекты с task, group, reason)

**Пишет:**
- `{output}` — JSON:
  - `status`: `passed` / `failed`
  - `neighbors`: `[{task, group, reason}]` (только валидные)
  - `errors`: `[]` или список ошибок валидации

## Побочные эффекты
- File write

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/resolve-neighbors.py \
  --task 2605 --output .doc/tasks/2605/test-runs/2026-11-07_143022/neighbor-results.json
```

## Ограничения
- Не запускает соседние тесты — только резолвит и валидирует список
- Требует ac-matrix.json с required_neighbors
- Проверяет существование папки тестов соседа (не запускает их)

## Связи
- Вызывается: `task-test.sh`, `gates.py` (проверка neighbor-results.json)
- Читает: `ac-matrix.json` (генерируется prepare-task-test / руками)
- Канон: `.doc/harnes/tests.md` § neighbor flows

## История изменений
- 2026-11-07: полная документация (status: draft → actual)