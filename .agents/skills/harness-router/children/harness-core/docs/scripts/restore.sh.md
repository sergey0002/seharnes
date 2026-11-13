# Скрипт: `.cursor/mcp-stack/restore.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, restore, mcp, migration, backup, import]
-->

## Суть
Развёртывает MCP-стек из архива, созданного `export.sh`, на другой машине или в другом корне проекта. Восстанавливает: CBM индексы (machine-level), Serena конфиги и памяти (global + per-project), `.cursor/mcp.json`, `.cursor/mcp.env`, скрипты MCP-стека, systemd units (CBM machine-level — только если отсутствует; Serena — под новым slug проекта). Перезаписывает старые абсолютные пути на новый `ROOT`. Опционально запускает сервисы (`--no-start` только копирует файлы). CodeGraph индекс не восстанавливается — пересобирается `codegraph init` после restore.

## Когда запускать
- При миграции проекта на новую машину
- При восстановлении из бэкапа после сбоя
- При клонировании настроенного окружения для нового разработчика

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<archive.tar.gz>` | string | да | — | Путь к архиву из `export.sh` |
| `[project-root]` | string | нет | `$(pwd)` | Куда развернуть проект на этой машине |
| `--no-start` | flag | нет | false | Только копировать файлы, не запускать systemd units |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Восстановление успешно | Запустить `verify.sh` для проверки |
| 1 | Отказ перезаписать существующий `.cursor/mcp.json` | Удалить/переместить старый конфиг |
| 2 | Архив не найден / неверные аргументы | Проверить путь и синтаксис |

## Что читает и что пишет
- **Читает**: архив `.tar.gz` (MANIFEST.txt, config/, units/, state/), старый `project_root` из манифеста
- **Пишет**: `.cursor/mcp.json`, `.cursor/mcp.env`, `.tools/scripts/`, `.agents/skills/{codebase-memory-mcp,codegraph,codeprism,graphiti,jdocmunch,serena,phpstan-mcp}/scripts/`, `.cursor/mcp-stack/`, `~/.local/share/mcp-stack/codebase-memory/`, `~/.serena/`, `<ROOT>/.serena/`, systemd units в `~/.config/systemd/user/`, логи в stderr

## Побочные эффекты
- **Отключает CodePrism в восстановленном mcp.json** (требует проектно-специфичной настройки)
- Создаёт/обновляет systemd units (CBM machine-level, Serena per-project)
- Перезаписывает пути в скриптах и конфигах если проект сменил корень
- При `--no-start` не делает `systemctl daemon-reload` и не стартует units
- Может сменить Serena порт если старый занят (подбирает свободный 9121–9199)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `tar`, `gzip` | Распаковка архива |
| `systemctl --user` | Для установки/запуска units (если не `--no-start`) |
| `python3` | Для манипуляции JSON (CodePrism disable) |
| `sed` | Для замены путей в файлах |

## Примеры
```bash
# Полный restore с запуском сервисов
bash .cursor/mcp-stack/restore.sh ~/backups/mcp-stack-export-20261107-1200.tar.gz /home/user/projects/myproject

# Только файлы, без systemd
bash .cursor/mcp-stack/restore.sh ~/backups/mcp-stack-export-20261107-1200.tar.gz /home/user/projects/myproject --no-start

# После restore:
bash .cursor/mcp-stack/verify.sh /home/user/projects/myproject
```

## Ограничения
- **Никогда не перезаписывает существующий `.cursor/mcp.json`** — exit 1 если файл есть
- CodePrism принудительно отключается в восстановленном конфиге (нужно настроить заново)
- CodeGraph индекс не восстанавливается — нужен `codegraph init --yes <ROOT>`
- CBM индекс сохраняет старый slug — нужна реиндексация `index_repository(repo_path=ROOT)`
- Serena unit устанавливается только если отсутствует (не перезаписывает чужой)
- Требует совпадающей архитектуры (Linux/WSL) для systemd units

## Связи
- Парный скрипт: `export.sh` (создаёт архив)
- Проверка после: `verify.sh`
- CodeGraph пересборка: `codegraph init --yes <ROOT>`
- CBM реиндексация: `index_repository(repo_path=ROOT)`
- Документация: `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/mcp/serena.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)