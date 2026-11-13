# Скрипт: `.cursor/mcp-stack/add-project.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codegraph.md, .doc/harnes/mcp/codebase-memory-mcp.md]
tags: [harness, script, add-project, codegraph, cbm, setup]
-->

## Суть
Подготавливает проект для работы с CodeGraph и shared Codebase-Memory (CBM). Проверяет наличие CodeGraph индекса (`.codegraph/codegraph.db`) и выводит инструкции для подключения к CBM (`index_repository`) и CodeGraph (`projectPath`).

## Когда запускать
- При добавлении нового проекта в MCP-стек
- После `codegraph init --yes <project>` для проверки готовности
- При настройке нового окружения разработчика

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<project_root>` | string | да | — | Путь к корню проекта |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Проект готов, индекс найден | Использовать вывод для настройки MCP |
| 1 | CodeGraph индекс не найден | Запустить `codegraph init --yes <project_root>` |
| 2 | project_root не передан | Проверить синтаксис: `add-project.sh <project_root>` |

## Что читает и что пишет
- **Читает**: наличие `.codegraph/codegraph.db` в проекте
- **Пишет**: stdout с инструкциями (пути к индексу, CBM вызов, projectPath для CodeGraph)

## Побочные эффекты
- Нет (только чтение и вывод информации)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `codegraph` | CLI для проверки статуса (опционально) |

## Примеры
```bash
# Проверить готовность проекта
bash .cursor/mcp-stack/add-project.sh /home/user/projects/myproject

# Вывод:
# Проект готов для CodeGraph и CBM
#   index:  /home/user/projects/myproject/.codegraph/codegraph.db
#   CBM:    index_repository(repo_path="/home/user/projects/myproject")
#   projectPath для CodeGraph: /home/user/projects/myproject
# Проверка:
#   bash .cursor/mcp-stack/verify.sh /home/user/projects/myproject
```

## Ограничения
- Не создаёт индекс — только проверяет наличие
- Не настраивает MCP конфиги — только выводит команды для ручного выполнения
- CodeGraph индекс должен быть создан заранее (`codegraph init --yes`)

## Связи
- Создаёт индекс: `codegraph init --yes <project>`
- CBM индексация: `index_repository(repo_path=...)`
- Проверка: `verify.sh`
- Документация: `.doc/harnes/mcp/codegraph.md`, `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/state/15-mcp-stack.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)