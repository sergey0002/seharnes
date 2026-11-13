# Скрипт: `.agents/skills/codegraph/scripts/codegraph-ui.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codegraph.md]
tags: [harness, script, codegraph, ui, mcp]
-->

## Суть
Запускает веб-интерфейс CodeGraph (codegraph ui) для текущего проекта. Скрипт находит бинарник codegraph в PATH или в ~/.nvm, проверяет его наличие и запускает UI в режиме read-only. Позволяет указать порт и автоматически открывать браузер.

## Когда запускать
- При необходимости визуально исследовать граф кода проекта
- Для отладки связей между символами, blast radius, call paths
- После `codegraph init` или обновления индекса

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --open | | flag | нет | false | Автоматически открыть браузер после запуска UI |
| --port | | string | нет | auto (codegraph default) | Порт для веб-сервера UI |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | UI запущен успешно | — |
| 2 | Неизвестный аргумент | Проверить синтаксис вызова |
| 127 | codegraph не найден в PATH | Установить: `npm i -g @colbymchenry/codegraph` |

## Что читает и что пишет
- **Читает**: CodeGraph index (`.codegraph/codegraph.db` в корне проекта), переменную окружения `CODEGRAPH_UI_PORT`
- **Пишет**: Запускает HTTP-сервер на указанном порту, пишет логи в stdout/stderr

## Побочные эффекты
- Запускает долгоживущий процесс codegraph ui (HTTP-сервер)
- Открывает порт на 127.0.0.1
- Может открыть браузер (при --open)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `CODEGRAPH_UI_PORT` | Порт для UI (переопределяет --port) |
| `PATH` | Должен содержать путь к бинарнику `codegraph` |

## Примеры
```bash
# Запустить UI на порту по умолчанию, не открывать браузер
bash .agents/skills/codegraph/scripts/codegraph-ui.sh

# Запустить на конкретном порту и открыть браузер
bash .agents/skills/codegraph/scripts/codegraph-ui.sh --port 8080 --open
```

## Ограничения
- Требует установленного codegraph CLI (`npm i -g @colbymchenry/codegraph`)
- Работает только если CodeGraph index уже создан (`codegraph init --yes <project>`)
- UI работает в режиме read-only — не изменяет индекс
- В WSL доступен только на 127.0.0.1 (нужен порт-проброс для браузера на Windows)

## Связи
- Использует: CodeGraph index в `.codegraph/codegraph.db`
- Документация: `.doc/harnes/mcp/codegraph.md`, `.doc/harnes/state/15-mcp-stack.md`
- Парный скрипт: `codegraph-mcp.sh` (MCP-сервер для агентов)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)