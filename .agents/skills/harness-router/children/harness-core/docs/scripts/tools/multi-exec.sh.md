# Скрипт: `.tools/scripts/multi-exec.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/plan/massgrep.md, .cursor/rules/batch-calls.mdc]
tags: [harness, script, multi-exec, batch, parallel, json-lines]
-->

## Суть
Пакетный исполнитель N команд и/или чтений файлов с offset/limit за один вызов bash. Возвращает JSON Lines: одна строка на команду/чтение + финальная `_meta`. Используется для экономии контекста и round-trips: 3+ независимых вызова объединяются в один. Поддерживает sequential и parallel режимы (parallel только для read-only allowlist: rg, grep, git log/diff/show/blame/status, php -l, ls, cat, head, tail, wc, file, stat, jsondoc.py get/batch).

## Когда запускать
- При необходимости выполнить 3+ независимых поиска/чтений/команд
- Из агентов (Kilo, Cursor, Codex) через `multi-exec.ps1` на Windows
- В скилах: `prepare-plan` (blast radius), `task-doc` (Reuse/Impact Gate), `test-task` (php -l пачкой)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `--input FILE` | string | нет | — | JSON файл с батчем (альтернатива --cmd/--read) |
| `--cmd "id=X :: command"` | string | нет | — | Команда для выполнения (повторить для нескольких) |
| `--read "id=X :: path [+offset] [limit]"` | string | нет | — | Чтение файла со сдвигом (offset с плюсом: `+445 25`) |
| `--mode` | `sequential` \| `parallel` | нет | `sequential` | Режим исполнения |
| `--timeout SEC` | integer | нет | 60 | Таймаут на одну команду |
| `--max-output BYTES` | integer | нет | 20000 | Лимит суммарного размера JSON вывода |
| `--truncate BYTES` | integer | нет | 2000 | Обрезать stdout/stderr каждой команды |
| `-h, --help` | flag | нет | — | Показать справку |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все команды/чтения завершились с exit 0 | Результаты в JSON Lines |
| 1 | Хотя бы одна команда вернула non-zero | JSON содержит exit codes, `_meta.failed > 0` |
| 2 | Ошибка батча (синтаксис, дубликаты id, пустой батч) | Исправить аргументы вызова |

## Что читает и что пишет
- **Читает**: `--input` JSON файл, файлы из `--read`, stdin не используется
- **Пишет**: JSON Lines на stdout (по одной строке на item + `_meta`), stderr для ошибок парсинга

## Побочные эффекты
- Выполняет переданные команды (side effects зависят от команд)
- Читает файлы (read-only)
- Создаёт временные файлы для CMDS/READS массивов (удаляются по EXIT trap)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `timeout` (coreutils) | Обязателен для таймаутов команд |
| `python3` | Обязателен для JSON-обработки внутри скрипта |
| `PARALLEL_ALLOW` (internal) | Regex allowlist для parallel режима |

## Примеры
```bash
# Пакетное чтение 4 файлов задачи (паттерн из batch-calls.mdc)
bash .tools/scripts/multi-exec.sh \
  --read "id=a :: .doc/tasks/123/task.md +1 100" \
  --read "id=b :: .doc/tasks/123/doc.md +1 100" \
  --read "id=c :: .doc/tasks/123/diff.files.md +1 50" \
  --read "id=d :: .doc/tasks/123/plan.md +1 200"

# Пакетный php -l для 5 файлов
bash .tools/scripts/multi-exec.sh \
  --cmd "id=f1 :: php -l file1.php" \
  --cmd "id=f2 :: php -l file2.php" \
  --mode parallel
```

## Ограничения
- Parallel режим строго ограничен `PARALLEL_ALLOW` regex — только read-only операции
- Дубликаты `id` в батче — ошибка (exit 2)
- Общий лимит вывода `max-output` (default 20KB) — обрезает хвост результатов
- Не подходит для долгих команд (стенд, тесты, миграции) — только быстрые read-only
- Не поддерживает цепочки зависимостей (grep→read) — только независимые вызовы

## Связи
- PowerShell wrapper: `multi-exec.ps1`
- Документация: `.doc/harnes/plan/massgrep.md` §5, `.cursor/rules/batch-calls.mdc`
- Используется в: `prepare-plan` (P1.1 blast radius), `task-doc` (B2.5/B2.6), `test-task` (php -l)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)

## Аргументы (аудит: 2 колонки)
| Аргумент | Описание |
|---|---|
| `--input` | JSON файл с батчем (альтернатива --cmd/--read) |
| `--cmd` | Команда для выполнения (повторить для нескольких): `id=X :: command` |
| `--read` | Чтение файла со сдвигом: `id=X :: path [+offset] [limit]` |
| `--mode` | `sequential` или `parallel` (default sequential) |
| `--timeout` | Таймаут на одну команду в секундах (default 60) |
| `--max-output` | Лимит суммарного размера JSON вывода (default 20000) |
| `--truncate` | Обрезать stdout/stderr каждой команды (default 2000) |
| `-h`, `--help` | Показать справку |