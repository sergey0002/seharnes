# Скрипт: `.cursor/mcp-stack/export.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/state/15-mcp-stack.md, .doc/harnes/mcp/codebase-memory-mcp.md]
tags: [harness, script, export, mcp, backup, migration]
-->

## Суть
Экспортирует всю конфигурацию MCP-стека, systemd-юниты и состояние в один переносимый `.tar.gz` архив. Включает: `.cursor/mcp.json`, `.cursor/mcp.env`, скрипты MCP-стека, конфиги graphiti, systemd-юниты (CBM machine-level и Serena project-level), индексы CBM, конфиги и памяти Serena. CodeGraph индекс не экспортируется (пересобирается `codegraph init` на месте).

## Когда запускать
- При миграции проекта на другую машину
- Для бэкапа MCP-конфигурации перед крупными изменениями
- При настройке нового окружения из готового стека

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[output.tar.gz]` | string | нет | `~/mcp-stack-export-YYYYmmdd-HHMM.tar.gz` | Путь для выходного архива |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Архив создан | Использовать `restore.sh` для развёртывания |
| 1 | Ошибка создания архива | Проверить права доступа и дисковое пространство |

## Что читает и что пишет
- **Читает**: `.cursor/mcp.json`, `.cursor/mcp.env`, `.cursor/mcp-stack/*`, `.tools/scripts/*`, `.agents/skills/{codebase-memory-mcp,codegraph,codeprism,graphiti,jdocmunch,serena,phpstan-mcp}/scripts/*`, `~/.config/systemd/user/mcp-*.service`, `~/.local/share/mcp-stack/codebase-memory/`, `~/.serena/`, `<project>/.serena/`, git info
- **Пишет**: `.tar.gz` архив с полной структурой стека, `MANIFEST.txt` внутри архива с метаданными

## Побочные эффекты
- Создаёт временную директорию для сборки (`mktemp -d`)
- Читает systemd unit файлы (требует доступа к `~/.config/systemd/user/`)
- Не останавливает сервисы — только копирует конфигурацию

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `HOME` | База для путей кэша, юнитов, конфигов Serena |
| `tar`, `gzip` | Для создания архива |
| `git` | Для получения branch/commit в MANIFEST |

## Примеры
```bash
# Экспорт с автоименем
bash .cursor/mcp-stack/export.sh

# Экспорт в конкретный файл
bash .cursor/mcp-stack/export.sh ~/backups/mcp-stack-project-2026-11-07.tar.gz
```

## Ограничения
- Не экспортирует CodeGraph индекс (`.codegraph/codegraph.db`) — он пересобирается локально
- Не экспортирует логи серверов
- Не экспортирует graphiti данные (только конфиг)
- Serena language_servers не экспортируются (перекачиваются при первом запуске)
- Архив привязан к slug проекта (базируется на basename пути)

## Связи
- Парный скрипт: `restore.sh` (импорт на другой машине)
- Проверка после restore: `verify.sh`
- Документация: `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/state/01-canon-envs.md`
- Используемые скрипты: складывает в `config/scripts/<owner>/` файлы из `.tools/scripts` и из `scripts/` скилов `codebase-memory-mcp`, `codegraph`, `codeprism`, `graphiti`, `jdocmunch`, `serena`, `phpstan-mcp`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)