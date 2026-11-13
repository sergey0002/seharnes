# Скрипт: `.agents/skills/serena/scripts/serena-shared.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/serena.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, serena, shared, http, port-management, lock]
-->

## Суть
Запускает один Serena MCP-сервер на проекте и экспонирует его по Streamable HTTP для всех клиентов. Реализует изоляцию проектов: порт детерминированно вычисляется из хэша пути проекта (9200–9299), owner-файл фиксирует, какому проекту принадлежит порт, flock-лок предотвращает гонки запуска. Если порт занят чужим сервером — пропускает и ищет следующий. Запускает Serena через `uvx` и проксирует через `mcp-proxy`.

## Когда запускать
- Как shared HTTP endpoint для Serena (вместо systemd unit из `add-serena.sh`)
- Автоматически MCP-клиентами через `.cursor/mcp.json` (stdio → proxy → HTTP)
- При необходимости shared Serena без systemd

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| — | — | — | — | Проект определяется по местоположению скрипта (`../..`) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Proxy запущен, Serena готова | Клиенты подключаются к `http://127.0.0.1:<port>/mcp` |
| 1 | Нет свободного порта для проекта | Проверить `~/.local/state/serena-shared/` |

## Что читает и что пишет
- **Читает**: корень проекта, `SERENA_PORT` (override), `SERENA_HOST` (default 127.0.0.1), owner/pid/log файлы в `~/.local/state/serena-shared/`
- **Пишет**: owner-файл (`serena-<hash>.project`), pid-файл, лог-файл, HTTP MCP на выбранном порту

## Побочные эффекты
- Создаёт/перезаписывает файлы в `~/.local/state/serena-shared/`
- Запускает Serena через `uvx --from git+https://github.com/oraios/serena`
- Запускает `uvx mcp-proxy --transport streamablehttp <URL>`
- Открывает TCP порт в диапазоне 9200–9299
- Flock на `.lock` файл предотвращает параллельные запуски

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `SERENA_PORT` | Жёстко задать порт (переопределяет хэш-выбор) |
| `SERENA_HOST` | Хост для биндинга (default: 127.0.0.1) |
| `uvx` | Для запуска Serena и mcp-proxy |

## Примеры
```bash
# В .cursor/mcp.json (stdio → proxy → HTTP)
{
  "mcpServers": {
    "serena": {
      "type": "stdio",
      "command": "bash",
      "args": [".agents/skills/serena/scripts/serena-shared.sh"]
    }
  }
}

# Явный порт
SERENA_PORT=9250 bash .agents/skills/serena/scripts/serena-shared.sh
```

## Ограничения
- Один проект = один порт (детерминированно по хэшу пути)
- Порт диапазон 9200–9299 (90 портов, wraparound)
- Если порт занят чужим проектом — сканирует следующие 30 портов
- Не использует systemd — управляет процессами напрямую (nohup/setsid)
- Убивает proxy-env переменные (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY и lowercase) для чистого соединения
- Требует `uvx` и доступ к GitHub (для Serena) / PyPI (mcp-proxy)

## Связи
- Systemd-альтернатива: `add-serena.sh` (создаёт unit, более production-ready)
- Shared proxy: `mcp-shared-server.sh` (generic для любого stdio MCP)
- Документация: `.doc/harnes/mcp/serena.md`, `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/state/01-canon-envs.md`
- Проверка: `verify.sh` (проверяет systemd unit, не этот скрипт напрямую)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)