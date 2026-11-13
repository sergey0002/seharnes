# Скрипт: `.agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, verify_mcp_views]
-->

## Суть
Валидатор согласованности MCP-серверов по агентским view (Kilo, Qwen, Codex TOML, expanded views). Проверяет 5 инвариантов: 1) каждый view объявляет точно канонический набор серверов (нет лишних, нет отсутствующих); 2) enabled/disabled состояние совпадает с каноном (Kilo использует `enabled: true/false`, остальные — `disabled: true/false`); 3) expanded views (Antigravity, Gemini, agents) не содержат неразрешённых `${workspaceFolder}` или `${env:...}` токенов; 4) Kilo раскрывает `${workspaceFolder}` и держит `${env:...}` вне распаршенных значений (секреты в mcp.env, загружаются runtime wrapper); 5) опционально Codex TOML объявляет тот же набор серверов (топ-левел `[mcp_servers.name]`). Не сравнивает command semantics (адаптеры могут отличаться wrapper, абсолютными путями, нативной схемой). Возвращает JSON-отчёт с ошибками.

## Когда запускать
- После `sync-agent-views.sh` (верификация результата синхронизации).
- При команде «проверь MCP», «аудит MCP», «верифицируй view».
- В CI после изменений `.cursor/mcp.json` или ручной правки view-конфигов.
- Агент запускает перед работой с MCP для уверенности в консистентности.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --canonical |  | Path | да |  | Путь к `.cursor/mcp.json` |
| --kilo |  | Path | нет |  | Путь к `.kilo/kilo.jsonc` |
| --expanded |  | Path | нет | [] | View с раскрытыми путями (повторяемый: .agents/mcp.json, .codex/mcp.json, .qoder/settings.json) |
| --qwen |  | Path | нет |  | Путь к `.qwen/settings.json` |
| --codex-toml |  | Path | нет |  | Путь к `.codex/config.toml` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверки прошли (errors=0) | View согласованы |
| 1 | Есть ошибки (нарушения инвариантов) | Исправить view-конфиги, перезапустить sync |

## Что читает и что пишет
**Читает:**
- `.cursor/mcp.json` — канон (mcpServers с enabled/disabled)
- `.kilo/kilo.jsonc` — Kilo view (mcp object с enabled флагами, JSONC с комментариями)
- Expanded views (`.agents/mcp.json`, `.codex/mcp.json`, `.qoder/settings.json`) — mcpServers с disabled флагами
- `.qwen/settings.json` — Qwen view (mcpServers + mcp.excluded для disabled)
- `.codex/config.toml` — Codex TOML (секции `[mcp_servers.name]`)

**Пишет:**
- JSON-отчёт в stdout: `{canonical, servers, checked[], errors[], status}`

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.11+ (argparse, json, re, pathlib, tomllib).
- Нет внешних зависимостей.

## Примеры
```bash
# Полная проверка всех view
python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py \
  --canonical .cursor/mcp.json \
  --kilo .kilo/kilo.jsonc \
  --expanded .agents/mcp.json \
  --expanded .codex/mcp.json \
  --expanded .qoder/settings.json \
  --qwen .qwen/settings.json \
  --codex-toml .codex/config.toml
```

Пример вывода (успех):
```json
{
  "canonical": ".cursor/mcp.json",
  "servers": 14,
  "checked": [".kilo/kilo.jsonc", ".agents/mcp.json", ".codex/mcp.json", ".qoder/settings.json", ".qwen/settings.json", ".codex/config.toml"],
  "errors": [],
  "status": "passed"
}
```

Пример вывода (ошибки):
```json
{
  "canonical": ".cursor/mcp.json",
  "servers": 14,
  "checked": [".kilo/kilo.jsonc", ".agents/mcp.json"],
  "errors": [
    ".kilo/kilo.jsonc: server extra codeprism",
    ".agents/mcp.json: server missing serena",
    ".codex/mcp.json: unresolved placeholder ${env:MYSQL_PASSWORD}",
    ".qwen/settings.json: enabled server mysql is in mcp.excluded"
  ],
  "status": "failed"
}
```

## Ограничения
- Не проверяет семантику command/args/url — только имена, enabled/disabled, раскрытие токенов.
- Qwen схема: enabled серверы в `mcpServers`, disabled — в `mcp.excluded` (не в `disabled` флаге).
- Kilo JSONC: комментарии `//` и `/* */` стираются перед парсингом.
- Codex TOML: `tomllib` проверяет синтаксис, набор серверов и их состояние; семантику команд проверяет генератор Codex в режиме `--check`.
- Токен `${workspaceFolder}` считается валидным для Kilo/expanded (раскрывается клиентом); `${env:...}` — невалидным в expanded (должен быть в mcp.env).

## Связи
- Вызывается: `mcp-audit` скил, `sync-agent-views.sh` (пост-верификация), агент вручную, CI
- Зависит от: `.cursor/mcp.json`, view-конфигов, `sync-agent-views.sh`
- Результат используется: блокировка push при ошибках, исправление view перед работой

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
- 2026-11-09: проверка Codex TOML читает именованные секции и сверяет состояние серверов.
