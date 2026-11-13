# Скрипт: `.agents/skills/codeprism/scripts/codeprism-mcp.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codeprism.md]
tags: [harness, script, codeprism, mcp, proxy]
-->

## Суть
Мост для CodePrism MCP: читает HTTP URL из `.cursor/mcp.json`, валидирует его (только http://127.0.0.1:<port>, без auth, без фрагментов), и запускает `mcp-proxy` в streamable-HTTP режиме, форвардя запросы к локальному CodePrism серверу. Используется MCP-клиентами, которые ожидают stdio, а CodePrism отдаёт HTTP.

## Когда запускать
- Автоматически MCP-клиентами через `.cursor/mcp.json` (stdio transport → proxy → HTTP)
- Не требует ручного вызова

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| — | — | — | — | Аргументов нет; конфигурация читается из `.cursor/mcp.json` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Proxy запущен | MCP-клиент общается через proxy |
| 1 | Ошибка валидации конфига | Проверить `.cursor/mcp.json` секцию `codeprism` |
| 127 | uvx/mcp-proxy не найден | Установить uv и mcp-proxy |

## Что читает и что пишет
- **Читает**: `.cursor/mcp.json` → `mcpServers.codeprism.url`, `type`, `disabled/enabled`
- **Пишет**: MCP протокол на stdout (stdio transport), форвардит к HTTP endpoint CodePrism

## Побочные эффекты
- Запускает `uvx mcp-proxy --transport streamablehttp <URL>`
- Валидирует URL на соответствие локальному loopback

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `CODEPRISM_TARGET` | Переопределяет целевую директорию для валидации (default: project root) |
| `uvx` | Должен быть доступен для запуска mcp-proxy |

## Примеры
```json
// .cursor/mcp.json
{
  "mcpServers": {
    "codeprism": {
      "type": "stdio",
      "command": "bash",
      "args": [".agents/skills/codeprism/scripts/codeprism-mcp.sh"],
      "disabled": false
    }
  }
}
```

## Ограничения
- Работает только с HTTP типом сервера в конфиге (type: http)
- URL должен быть строго `http://127.0.0.1:<port>` — без auth, без фрагментов, без query
- CodePrism сервер должен быть уже запущен на этом порту (`codeprism_serve.py`)
- Отключает `index_project` tool на стороне клиента (только чтение)

## Связи
- CodePrism HTTP сервер: `codeprism_serve.py`
- Конфиг: `.cursor/mcp.json`
- Документация: `.doc/harnes/mcp/codeprism.md`, `.doc/harnes/state/15-mcp-stack.md`
- Проверка: `verify.sh` (тестирует HTTP endpoint через fastmcp Client)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)