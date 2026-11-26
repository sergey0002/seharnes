---
name: environment-sync
description: Синхронизация правил, скилов и MCP между средами.
---

# environment-sync

## Когда применять

- Когда нужен сценарий environment-sync в управлении харнесом.

## Вход

- Корень проекта и конфиги `harness-router`.

## Шаги

1. Из корня проекта выполнить `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`. До записи скрипт проверит Qoder: неизвестные файлы, ссылки и MCP-серверы блокируют синхронизацию и требуют отдельного решения. Изменённые управляемые файлы Qoder заменяются без резервных копий. Различия существующего MCP требуют просмотра и отдельного флага `--replace-managed-mcp`; неизвестные серверы этот флаг не удаляет.
2. Проверить результаты генераторов, parity и `verify_rule_triggers.py`. Codex и Cursor читают `.agents/skills` напрямую. Старые копии скилов и распознанный legacy `.codex/AGENTS.md` удаляются без резервных копий. Antigravity получает `.agents/skills.json`, DSH получает указатели вложенных скилов.
3. Проверить visibility-контракт через `harness_mirror.py --root . visibility --summary`. `gate: true` обязан быть inline во всех средах; `attach: glob` обязан срабатывать по пути или присутствовать в сгенерированной glob-таблице.
4. При ошибке исправить канон или генератор и повторить синк. Не редактировать views вручную.

## Самостоятельная копия workspace

Когда нужна независимая копия проекта, а не общая установка, работает маршрут SOURCE/TARGET. SOURCE не меняется, TARGET создаётся пустым или только с собственной `.git`.

1. `scripts/setup-workspace.py --source ABS_SOURCE --target PWD` копирует дерево, пересобирает включённые среды внутри TARGET, проверяет копию и ставит `.workspace-ready.json`.
2. `scripts/workspace-gate.py --prepare --source ABS_SOURCE` выполняется внутри setup; отдельно запускается в prelaunch режиме по маркеру и команде клиента.
3. `scripts/workspace-mcp.py --server git|phpstan-mcp|php-deps-mcp` даёт ACP локальный stdio сервер из cwd сессии и закрепляет `MCP_WORKSPACE` за TARGET.

Границы: gate и wrapper работают только из физического TARGET, `MCP_ENV_FILE` не остаётся в окружении сервера, путь SOURCE в управляемом MCP запрещён. Публикация prefix и каталога Kandev остаётся действием оператора после реализации и проверки установленного клиента.

## Выход

- Синхронизированные представления и отчет с результатами parity, trigger и visibility проверок.

## Ограничения

- Не дублировать код родителя.
- Не хранить состояние в скиле.
- Не создавать постоянные резервные копии представлений. Перед sync, rebuild или doctor запрещены самодельные tar-архивы и полные снимки Mirror.

## История изменений

- 2026-11-24: добавлен маршрут самостоятельной копии workspace: `setup-workspace.py`, `workspace-gate.py`, `workspace-mcp.py` и общий PHP root guard.
- 2026-11-24: добавлена среда `omp` (oh-my-pi): генератор `generate-omp-config.py` пишет только `.omp/mcp.json`, потому что omp читает правила, скилы и `AGENTS.md` из канона нативно, а вложенные файлы доступны по ссылкам из корневых роутеров; `environment_policy.py` разрешает пространство `.omp`, `harness_mirror.py visibility` и doctor знают новую среду.
- 2026-11-20: введена декларативная политика сред через `environments.json` с переключателем `enabled`; добавлен `environment_policy.py` (чтение переключателей, список управляемых путей, безопасная очистка); синхронизация и перенос используют `render_agent_views.py` с фильтрацией по `enabled`; `compact_agent_views.py` читает список управляемых копий из реестра; `verify_rule_triggers.py`, `harness_mirror.py` и doctor фильтруют проверки по `enabled`; отключены Qoder, Qwen, DSH, Agents (Antigravity) и Cursor (канон); включены Codex, Kilo, OpenCode; Cursor остался каноном с `enabled: false`; добавлен OpenCode v2: `generate-opencode-config.py` пишет `opencode.json` (`mcp.servers`, `disabled`), `.opencode/rules` и компактный индекс; `compact_agent_views.py` читает список управляемых копий из реестра и не удаляет изменённые MCP-записи.
- 2026-11-19: удалено создание постоянных резервных копий; запрещены самодельные архивы перед sync, rebuild и doctor.
- 2026-11-12: исправлены native discovery, bootstrap Codex, тип globs Antigravity и ссылки правил. Канон остаётся прежним.
