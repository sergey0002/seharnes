# Скрипт: `.agents/skills/harness-router/children/mcp-audit/scripts/check-mcp.sh`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-mcp]
-->

## Суть
Обёртка для полной проверки MCP-серверов проекта: сначала запускает `onboard-project.py --check` (валидация конфигурации проекта: PHP контейнер, MySQL MCP, Serena порт, CodePrism, индексы, git exclude, синхронизация), затем запускает `test-mcp-servers.mjs` (функциональное тестирование каждого MCP-сервера: spawn, tools/list, функциональные пробы tools/call). Используется скилом `mcp-audit` для команды «проверь MCP», «аудит MCP».

## Когда запускать
- При команде «проверь MCP», «аудит MCP», «добавь MCP».
- В CI после изменений в `.cursor/mcp.json` или `.cursor/mcp.env`.
- После миграции проекта для верификации MCP-стека.
- Агент запускает перед работой с MCP для уверенности в работоспособности.

## Аргументы
Скрипт передаёт все аргументы (`"$@"`) в `test-mcp-servers.mjs`. Основные:
| Аргумент | Что делает |
|---|---|
| --only=server1,server2 | Тестировать только перечисленные серверы |
| --no-functional | Пропустить Phase 2 функциональные пробы (только spawn + tools/list) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверки прошли (onboard-project --check + test-mcp-servers) | MCP стек здоров |
| 1 | Есть ошибки в onboard-project или test-mcp-servers | Исправить конфигурацию/серверы |
| 127 | Команда не найдена (python3/node) | Установить зависимости |

## Что читает и что пишет
**Читает (через вызываемые скрипты):**
- `.cursor/mcp.json` — канон MCP серверов
- `.cursor/mcp.env` — переменные окружения
- `.doc/onboard-report.json` — отчёт онбординга (onboard-project.py)
- Конфиги проектов для codegraph, CBM, Serena

**Пишет:**
- Ничего (только stdout/stderr от под-скриптов).

## Побочные эффекты
- `onboard-project.py --check` не вносит изменений (read-only).
- `test-mcp-servers.mjs` спавнит MCP-процессы (временные), не оставляет артефактов.

## Окружение и зависимости
- `python3` — для `onboard-project.py`.
- `node` — для `test-mcp-servers.mjs`.
- `bash` — для запуска скрипта.
- MCP-серверы должны быть установлены (через `.tools/scripts/...`, `scripts/` скила или глобально).

## Примеры
```bash
# Полная проверка всех MCP
bash .agents/skills/harness-router/children/mcp-audit/scripts/check-mcp.sh

# Только конкретные серверы
bash .agents/skills/harness-router/children/mcp-audit/scripts/check-mcp.sh --only=codebase-memory-mcp,serena

# Только Phase 1 (быстро)
bash .agents/skills/harness-router/children/mcp-audit/scripts/check-mcp.sh --no-functional
```

## Ограничения
- Зависит от успешного завершения обоих под-скриптов.
- `onboard-project.py --check` требует git, docker (опционально), codegraph CLI (опционально).
- `test-mcp-servers.mjs` может занимать 1-3 минуты (параллельные пробы с таймаутами).
- Не проверяет MCP-серверы, отключённые в mcp.json (disabled: true) — они пропускаются с SKIP.

## Связи
- Вызывается: `mcp-audit` скил, агент вручную, CI
- Зависит от: `onboard-project.py`, `test-mcp-servers.mjs`
- Результат используется: решение о готовности MCP-стека к работе

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)