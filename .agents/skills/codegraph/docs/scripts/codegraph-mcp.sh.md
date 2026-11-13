# Скрипт: `.agents/skills/codegraph/scripts/codegraph-mcp.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codegraph.md]
tags: [harness, script, codegraph, mcp, stdio]
-->

## Суть
Запускает CodeGraph MCP-сервер в stdio-режиме для текущего проекта. Находит бинарник `codegraph` в PATH или в `~/.nvm/versions/node/*/bin/`, и запускает `codegraph serve --mcp --path <project_root>`. Используется MCP-клиентами (Cursor, Kilo, Codex) для подключения к CodeGraph.

## Когда запускать
- Автоматически MCP-клиентами при подключении к CodeGraph (stdio transport)
- Не требует ручного вызова; настраивается в `.cursor/mcp.json` как stdio-сервер

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| — | — | — | — | Аргументов нет; проект определяется по местоположению скрипта |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | MCP сервер запущен | Клиент подключается по stdio |
| 127 | codegraph CLI не найден | Установить: `npm i -g @colbymchenry/codegraph` |

## Что читает и что пишет
- **Читает**: CodeGraph index (`.codegraph/codegraph.db` в корне проекта)
- **Пишет**: MCP протокол на stdout (stdio transport)

## Побочные эффекты
- Запускает Node.js процесс codegraph
- Читает индекс кода проекта

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `PATH` | Должен содержать путь к `codegraph` бинарнику |

## Примеры
```bash
# В .cursor/mcp.json (stdio конфиг):
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "bash",
      "args": [".agents/skills/codegraph/scripts/codegraph-mcp.sh"]
    }
  }
}
```

## Ограничения
- Требует установленного CodeGraph CLI: `npm i -g @colbymchenry/codegraph`
- Требует предварительно созданного индекса: `codegraph init --yes <project_root>`
- Работает только в stdio режиме (не HTTP)
- Проект определяется автоматически как родительская директория скрипта (`../..`)

## Связи
- UI launcher: `codegraph-ui.sh` (HTTP + веб-интерфейс)
- Windows launcher: нет (CodeGraph CLI кроссплатформенный через Node.js)
- Документация: `.doc/harnes/mcp/codegraph.md`, `.doc/harnes/state/15-mcp-stack.md`
- Проверка: `verify.sh` (проверяет наличие `.codegraph/codegraph.db` и `codegraph status`)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)