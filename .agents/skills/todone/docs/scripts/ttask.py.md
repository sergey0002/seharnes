# Скрипт: `ttask`

<!-- meta
type: script
status: actual
updated: 2026-11-18
related: [../../SKILL.md]
tags: [harness, script, ttask, record]
-->

## Суть
Точка входа для работы с записями: создание, чтение, правка полей/статуса/владельца, комментарии, рефсы/артефакты, запуск потоков, упаковка для субагентов. Делегирует в `tdcore.task_cli.TaskCli`.

## Когда запускать
При работе с записями очереди: новая запись (`ttask new`), чтение/показ (`ttask show`), правка (`ttask set`), комментарии (`ttask comment`), потоки (`ttask flow`), рефсы (`ttask ref`), упаковка (`ttask pack`), документирование (`ttask document`).

## Аргументы
Общие флаги: `--root`, `--queue`, `--json`, `--fields`, `--quiet`, `--limit`, `--by` (обязателен для мутирующих команд).
Подкоманды: `new`, `show`, `set`, `comment`, `flow`, `ref`, `pack`, `document`, `list`, `claim`, `close`, `evidence`, `handoff`.
Каждая подкоманда имеет свои флаги.

## Коды выхода
- 0: успех
- 1: ошибка контроля/валидации
- 3: требуется человеческое вмешательство (ASK_USER)

## Что читает и что пишет
Читает: `<queue>/.todone/index.json`, `data/T-NNN-тип/task.json`, `.todone/flows/`.
Пишет: создает/обновляет `task.json`, индекс, комментарии, рефсы, артефакты.

## Побочные эффекты
Создает файлы записи, обновляет индекс очереди, может запускать потоки.

## Окружение и зависимости
`TODONE_ROOT`. Требует Python 3.8+.

## Примеры
```bash
ttask new "Заголовок" --type task
ttask show T-001 --json
ttask set T-001 --status done --by me
ttask flow start --flow issue-delivery --from T-001
```

## Ограничения
Не управляет очередями (для этого `tqueue`). Не читает проектные настройки напрямую.

## Связи
Вызывается из SKILL.md (намерения "создать/читать запись", "постановка задачи", "вести ленту решений", "разложить работу потоком", "refs/artifacts"). Процедуры: `references/child-skills/03-formulate-task.md`, `04-decompose-and-order.md`, `05-agree-and-clarify.md`, `06-read-and-report.md`, `07-execute-and-close.md`, `08-file-operations.md`, `11-subagent-dispatch.md`, `14-task-intake.md`.

## История изменений
- 2026-11-18: документация заполнена агентом
