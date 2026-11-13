# Скрипт: `.tools/scripts/node-mcp.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, node, resolver, mcp, wrapper]
-->

## Суть
Резолвер Node.js бинарника для MCP-серверов, написанных на JS/TS. Ищет Node.js в порядке приоритета: `NODE_BIN` env → `node` в PATH → `~/.local/bin/node` → Cursor server bundled (`~/.cursor-server/bin/*/node`) → Windows system (`/mnt/c/Program Files/nodejs/node.exe`). Форвардит все аргументы в найденный Node.js.

## Когда запускать
- Как shebang/entrypoint для JS/TS MCP-серверов в `.cursor/mcp.json`
- Когда нужен гарантированный Node.js в среде с множественными установками (WSL, Cursor, системный)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[node args...]` | string[] | да | — | Аргументы для Node.js (обычно путь к .mjs/.js скрипту) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Node.js скрипт завершён | — |
| 127 | Node.js не найден | Установить Node.js или задать `NODE_BIN` в `.cursor/mcp.env` |
| * | Exit code Node.js скрипта | Проверить ошибки самого скрипта |

## Что читает и что пишет
- **Читает**: `NODE_BIN` env, файловую систему для поиска node
- **Пишет**: stdout/stderr Node.js процесса

## Побочные эффекты
- Запускает Node.js с переданными аргументами

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `NODE_BIN` | Явный путь к node.exe (приоритет выше всего) |

## Примеры
```json
// .cursor/mcp.json
{
  "mcpServers": {
    "mysql": {
      "type": "stdio",
      "command": "bash",
      "args": [".tools/scripts/node-mcp.sh", ".tools/scripts/mysql-mcp-proxy.mjs"]
    }
  }
}
```

## Ограничения
- Не управляет версиями Node.js — берёт первый найденный
- В WSL предпочитает Linux node, но фоллбечит на Windows node.exe через /mnt/c
- Cursor bundled node может быть старой версии

## Связи
- Windows версия: `node-mcp.cmd` (для нативного Windows)
- Используется в: `mysql-mcp-proxy.mjs`, `php-docker.js`, других JS MCP
- Документация: `.doc/harnes/mcp/mysql.md`, `.doc/harnes/state/15-mcp-stack.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)