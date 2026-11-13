# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/branch-audit.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, branch-audit]
-->

## Суть
Сверяет причины (R) и сценарии (S) из плана задачи (`## Decomposition`) с таблицей веток логики в `test.md` (`## Ветки логики`). Находит: причины без строк в таблице, сценарии без покрытия, строки со статусом не `covered`/`n-a`. Источники плана (по приоритету): `task.json` artifacts с `role=plan`, `stage*/plan.md`, корневой `plan.md`. Вывод: отчёт по каждой причине и список проблем.

## Когда запускать
- После написания/обновления `plan.md` и `test.md` — убедиться, что каждый R закрыт веткой.
- В `test-task.sh` перед прогоном (гейт G13).
- При аудите задачи: `python3 .../branch-audit.py 2605`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| task | | string | да | | Номер задачи CT-N (каталог `.doc/tasks/{N}/`) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все причины покрыты, все сценарии закрыты | План и тесты согласованы |
| 1 | Есть непокрытые причины/сценарии или частичные строки | Исправить `test.md` или `plan.md` |
| 2 | Нет `test.md` или нет планов с `## Decomposition` | Создать `test.md` через `prepare-task-test` или план через `prepare-plan` |

## Что читает и что пишет
- Читает: `.doc/tasks/{N}/test.md` (секция `## Ветки логики`), `.doc/tasks/{N}/plan.md`, `.doc/tasks/{N}/stage*/plan.md`, `.doc/tasks/{N}/task.json` (artifacts с `role=plan`).
- Пишет: только stdout (человекочитаемый отчёт). Файлы не создаёт.

## Побочные эффекты
- Только чтение файлов. Без изменений.

## Окружение и зависимости
Переменных окружения не используется.

## Примеры
```bash
# Базовая проверка задачи 2605
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/branch-audit.py 2605

# Типичный вывод:
# R1 [task]: 3 planned S, 2 branch rows, closed
# R2 [stage:stage2]: 2 planned S, 1 branch rows, partial
# Missing: R2 missing scenarios: S2.2
# Partial: B3=open
```

## Ограничения
- Ищет причины по заголовкам `### R<N>` внутри `## Decomposition`.
- Сценарии извлекаются по паттерну `S<N>.<M>` в теле причины.
- Ветки логики парсятся только из markdown-таблицы с ID `B<N>`.
- Не проверяет, что тесты реально проходят — только наличие строки в таблице.
- Статусы `covered`, `n-a`, `na` считаются закрытыми; остальные — частичные.

## Связи
- Вызывается: `gates.py` (гейт G13), `test-task.sh`, `prepare-plan` (аудит P7).
- Зависит: `test.md`, `plan.md`/`stage*/plan.md`, `task.json`.
- Результат используется: `gates.py` для готовности к QA.

## История изменений
- 2026-11-07: полная документация на основе реализации (был draft скелет)