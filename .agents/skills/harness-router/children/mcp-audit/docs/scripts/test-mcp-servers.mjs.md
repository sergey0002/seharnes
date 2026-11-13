# Скрипт: `.agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, test-mcp-servers]
-->

## Суть
Функциональный тестер MCP-серверов из `.cursor/mcp.json`. Двухфазный: Phase 1 — спавн процесса (stdio или HTTP), инициализация MCP (initialize + notifications/initialized), запрос tools/list, проверка что сервер ответил списком инструментов. Phase 2 (опционально, по умолчанию включена) — функциональные пробы для критических серверов: реальный вызов `tools/call` с рабочими аргументами и проверка полезной нагрузки ответа. Серверы, прошедшие Phase 1 но провалившие Phase 2, помечаются `DEGRADED` (зелёный спавн, красный в практике). Параллельный запуск (конкурентность 5 для Phase 1, 2 для Phase 2). Поддерживает stdio (с Content-Length framing для PHP-серверов) и HTTP/SSE транспорты. Пропускает disabled серверы и out-of-scope (xdebug). Предугадывает занятые порты (MySQL relay 3306). Выводит сводку с итоговым статусом каждого сервера.

## Когда запускать
- В составе `check-mcp.sh` (после `onboard-project.py --check`).
- При команде «проверь MCP», «аудит MCP», «тестируй MCP серверы».
- В CI после изменений MCP-конфигурации.
- Агент запускает для верификации работоспособности стека перед работой.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --only | | string | нет | | Тестировать только перечисленные серверы (через запятую, имена из mcp.json) |
| --no-functional | | flag | нет | | Пропустить Phase 2 функциональные пробы (только spawn + tools/list) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все серверы OK или SKIP (нет FAIL/TIMEOUT/DEGRADED) | MCP стек здоров |
| 1 | Есть FAIL, TIMEOUT или DEGRADED | Исправить конфигурацию/запуск проблемных серверов |

## Что читает и что пишет
**Читает:**
- `.cursor/mcp.json` — конфигурация серверов (command, args, env, url, type, disabled)
- `.cursor/mcp.env` — переменные окружения (подставляются в command/args/env через `${env:VAR}`, `${workspaceFolder}`, `${userHome}`)
- Наличие файлов-маркеров для функциональных проб: `lib/Objects/Register/RegisterMVC.php` (serena), `.codegraph/` (codegraph), порт 3306 (MySQL relay)

**Пишет:**
- Ничего (только stdout: лог проб, сводка, итоговый статус).

## Побочные эффекты
- Спавнит временные процессы MCP-серверов (убивает по завершении/таймауту).
- Не оставляет постоянных артефактов.

## Окружение и зависимости
- Node.js 18+ (fetch, child_process, net, fs, path, url).
- MCP-серверы должны быть установлены/доступны через command/args из mcp.json.
- `bash` — для запуска через `check-mcp.sh`.

## Примеры
```bash
# Полная проверка (Phase 1 + 2)
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs

# Только Phase 1 (быстро)
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --no-functional

# Только конкретные серверы
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=codebase-memory-mcp,serena,mysql
```

Пример вывода:
```
Workspace: /home/user/project
MYSQL_DATABASE: copytrust

=== Phase 1: process spawn (tools/list) ===
OK       codebase-memory-mcp — 17 tools: list_projects, search_graph, trace_path, ...
OK       serena — 28 tools: find_symbol, get_symbols_overview, ...
OK       mysql — 5 tools: list_tables, describe_table, execute, ...
SKIP     graphify — disabled in mcp.json
SKIP     xdebug — out of harness scope
FAIL     phpstan-mcp — spawn: ENOENT: no such file or directory
TIMEOUT  codeprism — no functional answer in 90s

=== Phase 2: functional probes (tools/call) ===
OK       codebase-memory-mcp — functional: list_projects
DEGRADED serena — find_symbol answered but OrderService not found (project not activated?)
OK       mysql — functional: list_tables
SKIP     codegraph — нет .codegraph: функциональная проверка codegraph не применима

=== Summary ===
OK            codebase-memory-mcp
OK→DEGRADED   serena — find_symbol answered but OrderService not found...
OK            mysql
SKIP          graphify
FAIL          phpstan-mcp
TIMEOUT       codeprism
SKIP          xdebug
SKIP          sourcegraph
SKIP          deepwiki
SKIP          bitbucket-task
```

## Ограничения
- Функциональные пробы определены жёстко в `FUNCTIONAL_PROBES` (codebase-memory-mcp, serena, mysql, git, codegraph) — не расширяемые без правки скрипта.
- Serena требует ~15s warmup (PROBE_WARMUP_MS) перед initialize — без этого таймаут при параллельном запуске.
- PHP stdio серверы (server.php) используют Content-Length framing — автоопределение по `server.php` в args/command.
- uvx/npx серверы получают увеличенный таймаут (90s) на cold start.
- Не тестирует авторизацию/токены (Sourcegraph token и т.д.) — только tools/list и заданные пробы.
- Параллельность Phase 2 = 2 (тяжелые пробы).

## Связи
- Вызывается: `check-mcp.sh`, `mcp-audit` скил, агент вручную
- Зависит от: `.cursor/mcp.json`, `.cursor/mcp.env`, установленных MCP-серверов
- Результат используется: решение о готовности стека, выявление DEGRADED серверов (serena без проекта, CBM без индекса)

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
- 2026-11-07: исправлен заголовок раздела "Аргументы" под audit