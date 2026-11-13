# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md]
tags: [harness, script, task-identity]
-->

## Суть
Валидатор сверяет номер задачи в `task.md`, `task.json` и снимке трекера, а также заголовок экспорта с `tracker.snapshot.summary`. Отличие `metadata.title` выводится предупреждением: авторское название документа может отличаться от названия Jira. Указанная в метаданных ветка проверяется по границам номера задачи. Отсутствующие обязательные данные дают статус `incomplete`.

## Когда запускать
- Обязательный гейт перед работой над задачей (bitbucket-tasks.mdc): «Гейт личности задачи (обязательно, машинный)».
- Перед планированием и записью документации задачи.
- В CI/пре-коммите для всех задач: `--all --tsv`.
- При подозрении на рассинхронизацию (task.md перезаписан, task.json не обновлён, ветка переименована).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| task |  | string | нет |  | Номер задачи (позиционный) |
| --all |  | flag | нет |  | Проверить все задачи в `.doc/tasks/` |
| --tsv |  | flag | нет |  | Компактный вывод TSV (для --all) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Идентичность подтверждена (или --all без ошибок) | Продолжить работу с учётом warnings |
| 2 | `mismatch` или `incomplete` | Проверить перечисленные источники, затем повторить проверку |
| 4 | Папка задачи не найдена | Проверить номер задачи |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/task.md` — заголовок задачи и её номер
- `.doc/tasks/{N}/task.json` — идентификаторы, `tracker.snapshot.summary`, `metadata.title`, `metadata.branch`
- Номер задачи из имени папки `.doc/tasks/{N}/`

**Пишет:**
- JSON-отчёт в stdout (или TSV при `--all --tsv`):
  - Одной задачи: `{task, ok, status, checks[{check, ok, detail}], warnings[], task_md_heading, task_json_title, tracker_summary}`. `status`: `ok`, `mismatch`, `incomplete`; `checks[].ok=null` означает отсутствие данных.
  - Для --all: `{total, failed, tasks[]}`

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.7+ (стандартная библиотека: argparse, json, pathlib, re, sys).
- Нет внешних зависимостей.

## Примеры
```bash
# Проверка одной задачи
python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py 2622

# Все задачи, JSON
python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py --all

# Все задачи, TSV
python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py --all --tsv
```

## Ограничения
- Проверяет локальный снимок Jira, а не актуальность данных в трекере.
- Не проверяет содержимое `doc.md`/`plan.md`/`diff.files.md` — только идентичность.
- Без обязательных источников статус `incomplete`, а не подтверждённая идентичность.
- `metadata.branch` может быть устаревшим после переключения веток; текущая ветка Git не проверяется.

## Связи
- Вызывается: `task-intake`, агент вручную перед работой с задачей
- Зависит от: структуры `.doc/tasks/{N}/`, `task.json` (JSONdoc)
- Результат используется: блокировка планирования и записи при конфликте или неполных данных

## История изменений
- 2026-11-09: структурная проверка идентификаторов, отдельный статус неполных данных и предупреждение об авторском названии.
- 2026-11-07: полная документация на основе кода (status: actual)
