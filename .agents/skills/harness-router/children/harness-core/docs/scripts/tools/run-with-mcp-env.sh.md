# Скрипт: `.tools/scripts/run-with-mcp-env.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/state/01-canon-envs.md]
tags: [harness, script, mcp, env, wrapper, codex]
-->

## Суть
Загружает проектное окружение из `.cursor/mcp.env` (или `MCP_ENV_FILE`) перед запуском stdio MCP-сервера. Codex TOML не поддерживает `envFile` как Cursor — этот скрипт решает проблему: `source <(tr -d '\r' < mcp.env)` и `exec "$@"`. Убирает CRLF для совместимости WSL.

## Когда запускать
- В `.codex/mcp.json` как wrapper для stdio MCP-серверов, которым нужны переменные из `mcp.env`
- Для любых MCP-серверов, запускаемых из Codex/сред без envFile поддержки

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<command> [args...]` | string[] | да | — | Команда MCP-сервера с аргументами |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Сервер завершился нормально | — |
| 1 | Ошибка запуска команды | Проверить команду и окружение |
| 2 | Команда не передана | `usage: run-with-mcp-env.sh <command> [args...]` |

## Что читает и что пишет
- **Читает**: `MCP_ENV_FILE` (default: `.cursor/mcp.env` рядом со скриптом), `.cursor/mcp.env`
- **Пишет**: передаёт stdout/stderr запускаемой команде

## Побочные эффекты
- Экспортирует все переменные из `mcp.env` в окружение процесса
- Запускает переданную команду с этим окружением

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `MCP_ENV_FILE` | Путь к .env файлу (default: `.cursor/mcp.env` относительно скрипта) |

## Примеры
```json
// .codex/mcp.json
{
  "mcpServers": {
    "mysql": {
      "type": "stdio",
      "command": "bash",
      "args": [".tools/scripts/run-with-mcp-env.sh", "node", ".tools/scripts/mysql-mcp-proxy.mjs"]
    }
  }
}
```

## Ограничения
- Только для stdio MCP-серверов (не HTTP)
- Не парсит сложные .env (нет поддержки кавычек, комментариев, многострочных) — простой `source`
- Удаляет `\r` для WSL/Windows совместимости
- `set -a` / `set +a` экспортирует все переменные файла

## Связи
- Конфиг: `.cursor/mcp.env`, `.cursor/mcp.env.example`
- Codex конфиг: `.codex/mcp.json`
- Документация: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/mcp/mysql.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)