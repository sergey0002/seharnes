# Скрипт: `.agents/skills/task-router/children/reporting-router/children/task-report/scripts/collect-shots.py`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, task-report, screenshots, jira]
-->

## Суть
Сбор скриншотов прогона тестов для вставки в Jira-комментарий (task-report). Ищет PNG в `.doc/tasks/{N}/screenshots/` (ручные) и в последнем прогоне `.doc/tasks/{N}/test-runs/{stamp}/` (автотесты). Приоритизирует прогоны со статусом `passed` (по `report.md` или `verdict.json`). Ранжирует скриншоты по эвристике имени файла (плюс за `result`, `view`, `card`, `form`, `after`, `done`, `success`, `order`, `ok`; минус за `foreign`, `fake`, `login`, `console`, `before`, `debug`). Выводит список путей и подписей в формате `SHOT\t<rel_path>\t<caption>` для потребления `task-report` скилом.

## Когда запускать
Вызывается из `task-report` SKILL.md перед формированием комментария в Jira. Можно вызвать вручную для проверки какие скриншоты попадут в отчёт. Если не запустить — в Jira-комментарии не будет путей к скриншотам.

## Аргументы
Позиции передаются в порядке следования, без флагов.

| Позиция | Имя | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| 1 | `TASK` | string | **да** | | Номер задачи (только цифры) |
| 2 | `MAX` | int | нет | 6 | Максимум скриншотов в выводе |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: напечатан список SHOT строк | Разобрать stdout, использовать пути |
| 1 | Папка задачи не существует | Проверить номер задачи |
| 2 | Не передан TASK или не цифры | Исправить вызов |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/screenshots/*.png` — ручные скриншоты
- `.doc/tasks/{N}/test-runs/screenshots/*.png` — общие скриншоты тестов
- `.doc/tasks/{N}/test-runs/{stamp}/debug/*.png` и `*.png` — скриншоты конкретного прогона
- `.doc/tasks/{N}/test-runs/{stamp}/report.md` — статус прогона (парсит `status:` или PASS/FAIL)
- `.doc/tasks/{N}/test-runs/{stamp}/verdict.json` — фолбэк статус (`green: true/false`)

**Пишет:** только stdout в формате:
```
task: 2538
hand: screenshots/
SHOT	.doc/tasks/2538/screenshots/login.png	login
SHOT	.doc/tasks/2538/test-runs/task-2538-20261107/debug/step1.png	step 1
run: task-2538-20261107
status: passed
shots: 12
SHOT	.doc/tasks/2538/test-runs/task-2538-20261107/debug/result.png	result
...
more: 5 in .doc/tasks/2538/test-runs/task-2538-20261107/debug
```

## Побочные эффекты
Нет (read-only).

## Окружение и зависимости
- Python 3.8+
- Стандартная библиотека: `re`, `json`, `sys`, `pathlib`
- Нет внешних зависимостей

## Примеры
```bash
# Базовый вызов (лимит 6)
python .agents/skills/task-router/children/reporting-router/children/task-report/scripts/collect-shots.py 2538

# С лимитом 10
python .agents/skills/task-router/children/reporting-router/children/task-report/scripts/collect-shots.py 2538 10

# Из task-report скила (захват stdout)
output=$(python .../collect-shots.py 2538)
echo "$output" | grep ^SHOT
```

## Ограничения
- Не копирует/перемещает файлы — только выдаёт пути
- Эвристика ранжирования по имени файла может не совпадать с семантической важностью
- Ищет только `.png` (не `.jpg`, `.webp`)
- `hand` скриншоты (из `screenshots/`) имеют приоритет над автотестами, если они есть
- Не проверяет актуальность скриншотов относительно текущего кода
- Максимум `MAX` скриншотов в выводе (остальные в `more:` строках)

## Связи
- Вызывается: `task-report` SKILL.md (scripts/collect-shots.py), вручную
- Зависит от: структуры `.doc/tasks/{N}/test-runs/`, `verdict.json`, `report.md`
- Результат потребляет: `task-report` (формирует Jira-комментарий с путями к скринам)
- Связанные: `browser-verify` (создаёт скриншоты), `test-task` (создаёт test-runs)

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода