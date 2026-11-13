# Скрипт: `.tools/scripts/mcp-shared-server.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, mcp, shared, proxy, stdio-to-http]
-->

## Суть
Запускает один stdio MCP-сервер и экспонирует его по Streamable HTTP на указанном порту для всех клиентов (Kilo, Cursor, dsh, Codex). Избегает запуска отдельного процесса на клиента. Использует `mcp-proxy` — сначала ищет закешированный бинарник в `~/.cache/uv/archive-v0`, иначе качает через `uvx`.

## Когда запускать
- Для любого stdio-only MCP-сервера, который нужен нескольким клиентам одновременно
- Через systemd или вручную для shared HTTP endpoints
- При настройке нового MCP-сервера в стеке

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<port>` | integer | да | — | Порт для HTTP endpoint (127.0.0.1:<port>/mcp) |
| `<stdio command> [args...]` | string[] | да | — | Команда запуска stdio MCP-сервера |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Proxy запущен | Клиенты подключаются к `http://127.0.0.1:<port>/mcp` |
| 1 | Ошибка запуска proxy | Проверить логи |
| 2 | Порт не передан | `usage: mcp-shared-server.sh <port> <stdio command> [args...]` |

## Что читает и что пишет
- **Читает**: кэш uv (`~/.cache/uv/archive-v0`) для mcp-proxy бинарника
- **Пишет**: HTTP MCP на `127.0.0.1:<port>/mcp`, логи в stdout/stderr

## Побочные эффекты
- Запускает `mcp-proxy --host 127.0.0.1 --port <port> --stateless -- <stdio command>`
- Открывает TCP порт на localhost
- Запускает дочерний stdio MCP процесс

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `uvx` / кэш uv | Для mcp-proxy (предпочитает закешированный бинарник) |

## Примеры
```bash
# Запуск Serena через shared proxy на порту 9121
bash .tools/scripts/mcp-shared-server.sh 9121 \
  uvx --from git+https://github.com/oraios/serena \
  serena start-mcp-server --transport stdio --project /path/to/project

# В systemd unit:
# ExecStart=.tools/scripts/mcp-shared-server.sh 9131 codebase-memory-mcp
```

## Ограничения
- Только localhost (127.0.0.1) — не для внешней сети
- Stateless proxy — не сохраняет состояние между запросами
- Зависит от доступности uvx/uv кэша
- Не управляет жизненным циклом stdio-сервера отдельно (proxy делает это)

## Связи
- Используется в: `add-serena.sh` (для systemd unit), `export.sh`/`restore.sh`
- Документация: `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/mcp/codebase-memory-mcp.md`
- Альтернатива: `serena-shared.sh` (встроенный порт-менеджмент для Serena)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)