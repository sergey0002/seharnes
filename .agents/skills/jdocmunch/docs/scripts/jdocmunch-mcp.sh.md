# Скрипт: `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/jdocmunch.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, jdocmunch, mcp, documentation, index, search]
-->

## Суть
Канонический лаунчер jDocMunch MCP для всех агентных сред (Cursor, Kilo, Codex, dsh). Индекс общий на машину, ключируется по owner/name под `$DOC_INDEX_PATH`. Эмбеддинги отключены с 2026-11-03 — лексический поиск точнее на этом корпусе (Hit@3 0.59 vs 0.45 hybrid vs 0.27 semantic-only). Скрипт: резолвит repo handle из метаданных индекса (source_root), строит явный список путей для индексации (корпус: architecture harnes tasks web, с прунингом generated артефактов), запускает `jdocmunch-mcp` бинарник. Зеркала в других средах создаются синком — править только канон здесь.

## Когда запускать
- Как MCP-сервер в `.cursor/mcp.json` (stdio transport)
- Ручно: `--index` (переиндексация), `--corpus` (сколько файлов), `--repo` (handle для клиентов), `--status` (что проиндексировано)
- Автоматически агентами при поиске документации

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `serve` | command | нет | (default) | Запустить MCP-сервер (stdio) |
| `--index` | flag | нет | — | Переиндексировать корпус (читает .doc/) |
| `--corpus` | flag | нет | — | Показать количество файлов для индексации |
| `--repo` | flag | нет | — | Вывести repo handle для `search_sections` |
| `--status` | flag | нет | — | Показать все проиндексированные репозитории и модели |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (сервер запущен / команда выполнена) | — |
| 1 | Ошибка индексации / бинарник не найден | Проверить `~/.local/bin/jdocmunch-mcp` |
| 2 | Неверные аргументы | Использовать `--help` у бинарника |

## Что читает и что пишет
- **Читает**: `.doc/architecture/`, `.doc/harnes/`, `.doc/tasks/`, `.doc/web/` (по корпусу), `$DOC_INDEX_PATH` (default `~/.doc-index`), uv-кэш не используется
- **Пишет**: индексы в `$DOC_INDEX_PATH/local/<repo>/`, логи MCP в stderr

## Побочные эффекты
- `--index`: создаёт/обновляет `.json`, `.related.json`, `.postings.jsonl`, `.summary.json` в индексе
- `serve`: запускает долгоживущий MCP-процесс (stdio)
- Прунит при индексации: `backups/`, `jsondoc_scripts/`, `codeception/vendor/`, `codeception/tests/`, `*.sql`, `*.pdf`, `__pycache__/`, `.content-extractor/`, `.jira/`, `.bitbucket/`, `.mcpyandexscreen/`, `test-runs/`, `tests/`, `reports/`, `backup-*`, `_jsondoc/`, `_dialogs/`, `dialogs/`, `business-rules/`, `technical-facts/`, `ui-rules/`

## Окружение и зависимости
| Переменная | Описание | По умолчание |
|---|---|---|
| `DOC_INDEX_PATH` | Хранилище индексов | `~/.doc-index` |
| `JDOCMUNCH_DOCROOT` | Корень документации | `<project>/.doc` |
| `JDOCMUNCH_CORPUS` | Поддиректории для индексации | `architecture harnes tasks web` |
| `JDOCMUNCH_INDEX_NAME` | Имя индекса под local/ | `<repo#*/>` |
| `JDOCMUNCH_REPO` | Repo handle (override резолва) | auto-resolve |
| `jdocmunch-mcp` бинарник | В `~/.local/bin/` | обязателен |

## Примеры
```bash
# MCP сервер (в .cursor/mcp.json)
{
  "mcpServers": {
    "jdocmunch": {
      "type": "stdio",
      "command": "bash",
      "args": [".agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh", "serve"]
    }
  }
}

# Переиндексация
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index

# Сколько файлов будет проиндексировано
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --corpus

# Repo handle для клиентов
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --repo
# → local/testdeploy-arch

# Статус индексов
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --status
```

## Ограничения
- **Эмбеддинги отключены жёстко** (`--embeddings off`) — только лексический BM25
- Корпус жёстко задан (architecture harnes tasks web) — переопределяется `JDOCMUNCH_CORPUS`
- Игнор-паттерны.persist в индексе — повторный `--index` без `--no-extra-ignore-patterns` не расширит корпус
- Repo handle резолвится по `source_root` в метаданных — работает после переезда проекта
- Канон только здесь, копия в зеркалах скилов создается синком; отдельного пула скриптов нет

## Связи
- Бинарник: `~/.local/bin/jdocmunch-mcp` (устанавливается отдельно)
- MCP конфиг: `.cursor/mcp.json`
- Документация: `.doc/harnes/mcp/jdocmunch.md` (бенчмарк, corpus, модели), `.doc/harnes/state/15-mcp-stack.md`
- Синк зеркал: `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)