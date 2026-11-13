# Скрипт: `.agents/skills/task-router/children/jira/scripts/server.php`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md, ../../docs/mcp/jira-task.md]
tags: [harness, script, server, jira, mcp]
-->

## Суть
MCP-сервер (stdio) для экспорта задач Jira и релизов в Markdown. Работает в двух режимах:
1. **CLI** — прямой запуск `php server.php 2538` или `php server.php release 5.7.2`
2. **MCP** — регистрирует инструменты `export_task_md` и `list_release_tasks` для вызова из агентов (Cursor, Codex, Kilo, Qoder)

Использует полноценные PHP-классы (`JiraClient`, `TaskExporter`, `ReleaseExporter`, `TaskMarkdownBuilder`, `AdfTextConverter`) с кэшированием, повторными попытками и валидацией. Основной способ экспорта задач в проекте.

## Когда запускать
- **CLI**: для разового экспорта задачи или релиза без MCP-клиента
- **MCP**: автоматически поднимается клиентом (Cursor/Kilo/Codex/Qoder) при вызове инструментов `jira-task`
- Не запускать вручную в фоновом режиме — MCP-клиент управляет жизненным циклом

## Аргументы
### CLI-режим
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| $argv[1] | issue_id / release | string | да | — | Номер задачи (`2538`), ключ (`CT-2538`), URL, или слово `release` / `--release` |
| $argv[2] | version | string | при release | — | Версия релиза (например, `5.7.2`) |

### MCP-инструменты
| Инструмент | Параметры | Описание |
|---|---|---|
| `export_task_md` | `issue_id` (string, required) | Экспорт одной задачи в `.doc/tasks/{N}/task.md` |
| `list_release_tasks` | `release_version` (string, required) | Экспорт всех задач релиза в `.doc/{version}.md` (метаданные без описания/комментариев) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: stdout — сохранённый путь, ключ, заголовок, счётчики (CLI) / JSON-результат (MCP) | Использовать результат |
| 1 | Ошибка: неверные аргументы, отсутствует config.env, ошибка Jira API, невалидный JSON (MCP) | Проверить stderr / MCP error response |

## Что читает и что пишет
**Читает:**
- `config.env` (рядом или по `JIRA_CONFIG_FILE`) — `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, опционально `WORKSPACE_ROOT`
- Jira REST API v3: issue, changelog, comments (пагинация), search (для релизов)
- Классы из `src/`: `EnvConfig`, `IssueIdParser`, `JiraClient`, `TaskExporter`, `ReleaseExporter`, `TaskMarkdownBuilder`, `AdfTextConverter`, `ReleaseMarkdownBuilder`, `McpStdioServer`

**Пишет (CLI и MCP):**
- Задача: `.doc/tasks/{N}/task.md` (полный Markdown с метаданными, описанием, комментариями, changelog)
- Релиз: `.doc/{version}.md` (таблица задач: ID, State, Kind, Assignee, Title — без описания и комментариев)
- Создаёт директории по необходимости

**Сеть:**
- HTTPS к Jira Cloud API (Basic Auth)

## Побочные эффекты
- network requests (Jira API)
- file writes (создаёт/перезаписывает .md файлы)
- Не меняет данные в Jira

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| JIRA_CONFIG_FILE | Путь к config.env (по умолчанию `./config.env`) |
| JIRA_BASE_URL | Базовый URL Jira Cloud |
| JIRA_PROJECT_KEY | Ключ проекта (например, `CT`) |
| JIRA_EMAIL | Email учётной записи |
| JIRA_API_TOKEN | API токен |
| WORKSPACE_ROOT | Корень репозитория для выходных файлов (по умолчанию вычисляется как родитель `.doc/skil_data/jira`) |

**Зависимости:** PHP 7.1+, расширения `curl`, `json`, `mbstring`. Composer-зависимости не требуются — все классы в `src/`.

## Примеры
```bash
# CLI: экспорт задачи 2538
php server.php 2538

# CLI: экспорт задачи по ключу
php server.php CT-2538

# CLI: экспорт релиза 5.7.2
php server.php release 5.7.2
php server.php --release 5.7.2

# MCP: инструмент export_task_md
# {"issue_id": "2538"} -> сохраняет .doc/tasks/2538/task.md

# MCP: инструмент list_release_tasks
# {"release_version": "5.7.2"} -> сохраняет .doc/5.7.2.md
```

**CLI вывод при успехе (задача):**
```
Saved: /home/user/project/.doc/tasks/2538/task.md
Key: CT-2538
Title: Исправить расчёт скидки при оплате бонусами
Comments: 12
Changes: 8
```

**CLI вывод при успехе (релиз):**
```
Saved: /home/user/project/.doc/5.7.2.md
Release: 5.7.2
Active: 15 (total API: 18, excluded: 3)
#2538 | Done | Bug | ivan.ivanov | Исправить расчёт скидки
#2540 | In Progress | Task | petr.petrov | Добавить валидацию
...
```

## Ограничения
- Только Jira Cloud REST API v3
- MCP-режим требует клиента с поддержкой stdio (Cursor, Codex, Kilo, Qoder, VS Code с MCP)
- При ошибке MCP возвращает `isError: true` с текстом ошибки
- Релизный экспорт не включает описание и комментарии задач (только метаданные)
- `WORKSPACE_ROOT` в config.env позволяет переопределить корень вывода (полезно в контейнерах)
- Не кэширует между запусками CLI (MCP-сервер держит соединение открытым)

## Связи
- Основной экспортер, используемый `gototask` и `task-intake`
- `diag-auth.php` — диагностика тех же кредов
- `export_task.py` — Python-фолбэк без PHP
- Документирован в `../../SKILL.md` и `../../docs/mcp/jira-task.md`
- MCP-конфиг в `.cursor/mcp.json` (ключ `jira-task`)

## История изменений
- 2026-11-07: заполнена полная документация по коду (был draft)