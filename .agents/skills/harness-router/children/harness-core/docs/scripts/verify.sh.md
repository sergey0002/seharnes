# Скрипт: `.cursor/mcp-stack/verify.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, verify, mcp, health-check, stack]
-->

## Суть
Полная верификация MCP-стека для одного проекта. Проверяет: systemd unit CBM (mcp-codebase-memory), CBM API (list_projects видит проект), CodeGraph индекс (файл + codegraph status), CodePrism HTTP сервер (fastmcp Client → get_graph_stats), legacy graphify unit (warn если активен), Serena unit + порт, количество CBM процессов (warn если >1 shared). Возвращает суммарный PASS/FAIL.

## Когда запускать
- После настройки/миграции проекта (`add-project.sh`, `restore.sh`)
- При диагностике проблем с MCP
- В CI/пре-деплой для проверки стека
- Ручно: `bash .cursor/mcp-stack/verify.sh <project_root>`

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[project_root]` | string | нет | `$(pwd)` | Корень проекта для проверки |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверки PASS | Стек здоров |
| 1 | Есть FAIL проверки | Прочитать вывод, исправить помеченные компоненты |

## Что читает и что пишет
- **Читает**: systemd units (`mcp-codebase-memory`, `mcp-serena-<slug>`), CBM API (localhost:9131), CodeGraph index (`.codegraph/codegraph.db`), CodePrism HTTP (из `.cursor/mcp.json`), Serena port (из unit файла), процессы `codebase-memory-mcp`
- **Пишет**: Структурированный лог PASS/FAIL/WARN в stdout, итоговый статус в stderr

## Побочные эффекты
- Делает HTTP запросы к локальным MCP-серверам (curl, fastmcp Client)
- Читает systemd status (не меняет)
- Может ждать до 3 минут (CBM list_projects retry loop)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `curl` | Для CBM API проверки |
| `codegraph` CLI | Для `codegraph status --json` (опционально) |
| `fastmcp` / Python | Для CodePrism проверки (в `.cursor/tools/codeprism-ai/venv/`) |
| `systemctl --user` | Для проверки units |
| `ss` / `nc` / `/dev/tcp` | Для проверки портов |

## Примеры
```bash
# Проверить текущий проект
bash .cursor/mcp-stack/verify.sh

# Проверить конкретный проект
bash .cursor/mcp-stack/verify.sh /home/user/projects/myproject

# Типичный вывод:
# PASS  mcp-codebase-memory active
# PASS  CBM 9131 видит /home/user/projects/myproject
# PASS  CodeGraph index /home/user/projects/myproject/.codegraph/codegraph.db
# PASS  CodeGraph fileCount 1234
# PASS  CodePrism HTTP обслуживает /home/user/projects/myproject
# WARN  legacy mcp-graphify все еще active; остановите: systemctl --user disable --now mcp-graphify
# PASS  serena 9121 (mcp-serena-myslug)
# MCP stack: OK (myslug)
```

## Ограничения
- CodePrism проверка требует настроенного venv в `.cursor/tools/codeprism-ai/venv/`
- CBM проверка делает до 4 попыток с 3с паузой (итого ~12с ожидания)
- Serena проверяет только systemd unit, не `serena-shared.sh` процесс
- Не проверяет graphify MCP (legacy) — только предупреждает если unit активен

## Связи
- Запускается после: `add-project.sh`, `add-serena.sh`, `restore.sh`, `export.sh`
- Проверяет компоненты: CBM, CodeGraph, CodePrism, Serena, graphify (legacy)
- Документация: `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/mcp/codegraph.md`, `.doc/harnes/mcp/codeprism.md`, `.doc/harnes/mcp/serena.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)