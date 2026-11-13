# Скрипт: `.tools/scripts/node-mcp.cmd`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, node, windows, cmd, mcp]
-->

## Суть
Windows CMD-лаунчер для Node.js MCP-серверов (phpstan-mcp, php-deps-mcp). Избегает bash+WSL, которые ломают Windows-пути. Ищет `node.exe` в `%ProgramFiles%\nodejs\` → `%LocalAppData%\Programs\node\` → `node` в PATH → `NODE_BIN` env. Форвардит все аргументы.

## Когда запускать
- В Cursor/Codex native на Windows для JS/TS MCP-серверов
- Когда нужен Node.js без WSL path translation проблем

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `%*` (все аргументы) | string[] | да | — | Пробрасываются в `node.exe` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Node.js скрипт завершён | — |
| 1 | Node.js не найден | Установить Node.js |

## Что читает и что пишет
- **Читает**: пути установки Node.js, `NODE_BIN` env
- **Пишет**: stdout/stderr Node.js процесса

## Побочные эффекты
- Запускает `node.exe` с переданными аргументами

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `NODE_BIN` | Явный путь к node.exe (приоритет выше автопоиска) |

## Примеры
```cmd
REM В .cursor/mcp.json для Windows
{
  "mcpServers": {
    "phpstan": {
      "type": "stdio",
      "command": "cmd",
      "args": ["/c", ".tools/scripts/node-mcp.cmd", ".tools/scripts/phpstan-mcp.js"]
    }
  }
}
```

## Ограничения
- Только Windows cmd.exe
- Не использует WSL — нативные Windows пути
- Приоритет: ProgramFiles → LocalAppData → PATH → NODE_BIN

## Связи
- Linux/WSL версия: `node-mcp.sh` (универсальная)
- Используется для: phpstan-mcp, php-deps-mcp, других Node.js MCP
- Документация: `.doc/harnes/mcp/phpstan-mcp.md`, `.doc/harnes/mcp/php-deps-mcp.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)