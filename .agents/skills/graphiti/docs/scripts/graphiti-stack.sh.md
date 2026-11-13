# Скрипт: `.agents/skills/graphiti/scripts/graphiti-stack.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md, ../../graphiti/docs/mcp/graphiti.md]
tags: [harness, script, graphiti, docker]
-->

## Суть
Управление Docker-стеком Graphiti MCP: сервер Graphiti и встроенный FalkorDB.
Эмбеддинги считает отдельный Ollama на порту 11434. Скрипт предоставляет единый
интерфейс запуска, остановки, перезапуска, чтения логов и верификации состояния стека.

## Когда запускать
Запускать при старте работы со стеком Graphiti MCP (`up`), перед миграцией или
остановкой (`down`), для диагностики доступности (`status`, `verify`) и при
отладке соединения (`logs`).
Не запускать, если Docker daemon недоступен на хосте.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `command` | нет | строка | нет | `usage` | подкоманда: `up`, `down`, `restart`, `status`, `logs`, `verify` |
| `-h` | `--help` | флаг | нет | | показать справку |
| `--help` | `-h` | флаг | нет | | показать справку |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | операция завершена успешно | продолжить вызов MCP-инструментов Graphiti |
| 1 | ошибка выполнения подкоманды или таймаут health-проверки | изучить вывод `graphiti-stack.sh logs` |

## Что читает и что пишет
Читает переменные из `.cursor/mcp.env` и compose-манифест
`.cursor/mcp-stack/graphiti/docker-compose.yml`.
Управляет состоянием Docker контейнеров и именованных томов `falkordb_data`, `mcp_logs`.
Выводит статус операций и результаты HTTP-запросов health в stdout/stderr.

## Побочные эффекты
Запускает и останавливает контейнеры Docker. Создает тома данных для FalkorDB и логов.
Занимает локальные порты 8000 (MCP), 3000 (FalkorDB Browser), 6379 (FalkorDB).

## Окружение и зависимости
Требует `bash`, `docker compose`, `curl`. Секреты и конфигурация читаются из
`.cursor/mcp.env` (`GRAPHITI_LLM_API_KEY`, `GRAPHITI_GROUP_ID` и сопутствующие параметры).

## Примеры
```bash
bash .agents/skills/graphiti/scripts/graphiti-stack.sh up
bash .agents/skills/graphiti/scripts/graphiti-stack.sh status
bash .agents/skills/graphiti/scripts/graphiti-stack.sh verify
bash .agents/skills/graphiti/scripts/graphiti-stack.sh down
```

## Ограничения
Стек привязан к локальному адресу 127.0.0.1.
Для успешной проверки требуется корректно заполненный файл `.cursor/mcp.env`.

## Связи
Скил: `harness-core`, `graphiti`. Документ MCP: `graphiti/docs/mcp/graphiti.md`.
Правило: `.cursor/rules/mcp-graphiti.mdc`.

## История изменений
- 2026-11-07: составлен нормативный документ скрипта со статусом actual, исключены упоминания Ollama.
