# Скрипт: `.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.cmd`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codebase-memory-mcp.md]
tags: [harness, script, codebase-memory-mcp, windows, cmd]
-->

## Суть
Windows-лаунчер для codebase-memory-mcp (CBM). Избегает bash+WSL, которые ломают Windows-пути. Ищет бинарник в `%LocalAppData%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe` и форвардит все аргументы ему.

## Когда запускать
- В Cursor/Codex на Windows (native) для запуска CBM MCP-сервера
- Когда нужно избежать WSL path translation проблем

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `%*` (все переданные) | string[] | да | — | Пробрасываются напрямую в CBM бинарник |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | CBM запущен успешно | — |
| 127 | Бинарник не найден | Установить CBM или использовать WSL Cursor remote. См. `.cursor/codebase-memory-mcp.md` |

## Что читает и что пишет
- **Читает**: бинарник в фиксированном пути Windows
- **Пишет**: MCP протокол на stdout/stderr

## Побочные эффекты
- Запускает CBM процесс

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| — | Бинарник ищется в жёстко заданном пути |

## Примеры
```cmd
REM Запуск CBM с аргументами
.cursor\scripts\codebase-memory-mcp-launch.cmd --ui=false
```

## Ограничения
- Только для Windows (cmd.exe)
- Жёстко завязан на путь установки `%LocalAppData%\Programs\codebase-memory-mcp\`
- Не ищет в PATH — только фиксированный путь

## Связи
- Linux/WSL аналог: `codebase-memory-mcp-launch.sh`
- UI-лаунчер: `codebase-memory-mcp-ui.sh`
- Документация: `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/state/15-mcp-stack.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)