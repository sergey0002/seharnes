# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/record-history.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, record-history]
-->

## Суть
Добавляет компактную неизменяемую запись в историю прогона задачи. Пишет три файла:
1. `{run-dir}/history-entry.json` — запись текущего прогона
2. `{task-dir}/test-runs/history.jsonl` — агрегированная история всех прогонов задачи (JSONL)
3. `{task-dir}/test-runs/test-history.jsonl` — история по отдельным тестам (JSONL, развёрнуто)

Каждая запись содержит: timestamp, task, run, verdict_sha256, manifest_sha256, comparison. Для test-history добавляются поля теста: test, status, time.

## Когда запускать
- Автоматически в `task-test.sh` в конце прогона (после make-verdict.py)
- Для ручной фиксации истории

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --run-dir |  | string | да |  | Путь к каталогу прогона |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | продолжать |
| 1 | Ошибка (файлы не найдены) | проверить stderr |

## Что читает и что пишет
**Читает:**
- `{run-dir}/verdict.json` — для SHA256 и testcases
- `{run-dir}/manifest.json` — для SHA256
- `{run-dir}/comparison.json` — для comparison объекта
- `{run-dir}/report.xml` — JUnit для test-history

**Пишет:**
- `{run-dir}/history-entry.json` — одна запись
- `{task-dir}/test-runs/history.jsonl` — append JSONL
- `{task-dir}/test-runs/test-history.jsonl` — append JSONL (по тестам)

## Побочные эффекты
- File writes (append к JSONL)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/record-history.py \
  --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022
```

## Ограничения
- Требует verdict.json, manifest.json, comparison.json в run-dir
- Не ротирует историю — накапливается бесконечно
- SHA256 считается от текущего содержимого файлов (если файлы изменились после прогона — hash не совпадёт)

## Связи
- Вызывается: `task-test.sh` (последний шаг)
- Читает: `make-verdict.py`, `qa-manifest.py`, `compare-runs.py`
- Используется: для аудита истории прогонов, трендов

## История изменений
- 2026-11-07: полная документация (status: draft → actual)