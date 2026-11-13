# Скрипт: `.tools/scripts/mysql-mcp-proxy.mjs`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/mysql.md]
tags: [harness, script, mysql, mcp, proxy, relay, nodejs]
-->

## Суть
TCP-релей + MCP-прокси для MySQL. Upstream MCP-сервер (`@f4ww4z/mcp-mysql-server`) не принимает порт в `connect_db` — только host. Этот скрипт поднимает локальный TCP-релей на стандартном порту 3306 (настраивается `MYSQL_MCP_LISTEN_PORT`), который форвардит соединения в Docker-публикуемый порт MySQL (по умолчанию 8031). Одновременно запускает MCP-сервер через npx и проксирует JSON-RPC: перехватывает `connect_db`, подменяет host на релей-хост, авто-коннектится при первом database-tool вызове, ставит в очередь последующие вызовы до успешного коннекта.

## Когда запускать
- Как HTTP/stdio MCP-сервер для MySQL в `.cursor/mcp.json`
- Автоматически MCP-клиентами; не требует ручного запуска

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| — | — | — | — | Конфигурация через переменные окружения |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Сервер остановлен нормально | — |
| 1 | Релей порт занят / ошибка запуска | Проверить `MYSQL_MCP_LISTEN_PORT` |
| 2 | Отсутствуют `MYSQL_USER` или `MYSQL_DATABASE` | Задать в `.cursor/mcp.env` |

## Что читает и что пишет
- **Читает**: переменные окружения (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_MCP_LISTEN_HOST`, `MYSQL_MCP_LISTEN_PORT`, `MCP_WORKSPACE`)
- **Пишет**: TCP релей на `listenHost:listenPort`, MCP JSON-RPC на stdout/stdin, логи в stderr

## Побочные эффекты
- Запускает TCP сервер (релей) на 127.0.0.1:3306 (или настроенный порт)
- Запускает child process `npx -y @f4ww4z/mcp-mysql-server`
- Держит открытое соединение к MySQL в Docker

## Окружение и зависимости
| Переменная | Описание | По умолчанию |
|---|---|---|
| `MYSQL_HOST` | Хост MySQL (в Docker) | `127.0.0.1` |
| `MYSQL_PORT` | Порт MySQL в Docker | `8031` |
| `MYSQL_USER` | Пользователь БД | **обязателен** |
| `MYSQL_PASSWORD` | Пароль БД | **обязателен** |
| `MYSQL_DATABASE` | Имя БД | **обязателен** |
| `MYSQL_MCP_LISTEN_HOST` | Хост для релея | `127.0.0.1` |
| `MYSQL_MCP_LISTEN_PORT` | Порт для релея | `3306` |
| `MCP_WORKSPACE` | Корень проекта для npx cwd | `../..` от скрипта |

## Примеры
```json
// .cursor/mcp.json
{
  "mcpServers": {
    "mysql": {
      "type": "stdio",
      "command": "node",
      "args": [".tools/scripts/mysql-mcp-proxy.mjs"],
      "env": {
        "MYSQL_USER": "user",
        "MYSQL_PASSWORD": "pass",
        "MYSQL_DATABASE": "copytrust"
      }
    }
  }
}
```

## Ограничения
- Только localhost релей (127.0.0.1) — не для внешних подключений
- Требует Node.js (npx) и доступ к Docker MySQL порту
- Один релей на проект (порт 3306 может быть занят)
- Upstream MCP не поддерживает порт в connect_db — релей обязателен
- Авто-коннект при первом database tool вызове (list_tables, describe_table, query, execute)

## Связи
- Конфиг: `.cursor/mcp.env` (credentials), `.cursor/mcp.json`
- Docker MySQL: `.tools/docker-test` / `.tools/docker-dev`
- Документация: `.doc/harnes/mcp/mysql.md`, `.doc/harnes/state/15-mcp-stack.md`
- MCP сервер: `@f4ww4z/mcp-mysql-server` (npm)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)