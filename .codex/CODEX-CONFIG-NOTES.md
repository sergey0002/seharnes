# Codex — заметки по конфигурации (глобальная + проектная)

## Два уровня конфигов

| Уровень | Путь | Что задаёт |
|---------|------|------------|
| **Глобальный** | `%USERPROFILE%\.codex\config.toml` | модель, провайдер (codex-sale), `model_reasoning_effort`, trust repos, sandbox Windows |
| **Проектный** | `.codex/config.toml` (при `trust_level = "trusted"`) | MCP-серверы; проектные инструкции в корневом `AGENTS.md` |

**Обновление 2026-11-12:** подключение `model_instructions_file = "AGENTS.md"` удалено. Проектные инструкции загружаются из корневого `AGENTS.md`, скилы из `.agents/skills`.

**Wrappers (не читать SKILL.md):** `go-task.ps1`, `task-diff.ps1` в корне `.codex/`.
**Канон скилов:** `.agents/skills/`; Codex и Cursor читают его напрямую. Старые зеркала убирает синхронизация.
В `config.toml` включён `[sandbox_workspace_write] network_access = true` для git fetch и docker.
Корневой `AGENTS.md` содержит управляемый bootstrap; `.codex/rules-index.md` перечисляет обязательные и on-demand правила.

Codex **мержит** их: глобальный + проектный для trusted-репозитория.

## Текущий глобальный конфиг (проверено 2026-06-05)

```toml
model = "gpt-5.4"
model_reasoning_effort = "medium"   # было "high" — провоцировало циклы update_plan
model_provider = "codex-sale"

[projects.'c:\projects\copytrust\testdeploydocker']
trust_level = "trusted"

[windows]
sandbox = "elevated"
```

Провайдер `codex-sale`: `~/.codex/codex-sale.env` + `auth.json`.

## Что видно в логах сессии (причина зацикливания)

Файл: `%USERPROFILE%\.codex\sessions\2026\06\05\rollout-*.jsonl`

1. **`update_plan`** — каждые ~15–30 с новый план со шагом «прочитать локальные инструкции» (`in_progress`), без перехода к правкам.
2. **`reasoning_effort: high`** — в turn_context (из глобального config до правки).
3. **Системные skills** `~/.codex/skills/.system/openai-docs` и `skill-creator` — срабатывают на «Codex зацикливается» и уводят в диагностику manual/skills вместо правок.
4. **`approval_policy: never`** + **`sandbox_mode: danger-full-access`** — из UI сессии (не из project config).

## Рекомендации в UI Codex App

- Personality: **Pragmatic** (меньше «проверю инструкции»).
- Reasoning: **Medium** (согласовано с config.toml).
- После смены config — **новый thread**, не продолжать старый зацикленный.

## Системные skills (не трогать в репо)

`%USERPROFILE%\.codex\skills\.system\` — `openai-docs`, `skill-creator`, `skill-installer`, `imagegen`, `plugin-creator`. Управляются Codex App, не проектом.

## Синхронизация Cursor ↔ Codex

| Компонент | Cursor (канон UI) | Codex (runtime) | Codex (зеркало JSON) |
|-----------|-------------------|-----------------|----------------------|
| MCP серверы | `.cursor/mcp.json` | **`.codex/config.toml`** `[mcp_servers.*]` | `.codex/mcp.json` |
| Секреты | `.cursor/mcp.env` | `.codex/mcp.env` | — |
| Инструкции | `AGENTS.md` + rules | `.codex/AGENTS.md` + rules | — |

**Важно:** Codex **не читает** `mcp.json` в рантайме — только `config.toml`. Файл `.codex/mcp.json` — зеркало для сравнения с Cursor и `test-mcp-servers.mjs`.

После правок в `.cursor/mcp.json` — вручную синхронизировать `[mcp_servers]` в `.codex/config.toml` и `.codex/mcp.json`.

### Codex видит только `playwright-browser`

В глобальном `%USERPROFILE%\.codex\config.toml` часто только один сервер. Остальные — в **проектном** `.codex/config.toml`, но он подгружается только если:

1. Открыт **корень репо** `...\testdeploydocker` (не родитель `copytrust` и не multi-root «все проекты»).
2. Проект **trusted** в Codex (`[projects.'…'] trust_level = "trusted"` в global config).
3. Перезапуск панели Codex после trust.

Проверка:

```powershell
powershell -NoProfile -File .codex\scripts\verify-codex-mcp.ps1
codex mcp list   # из корня testdeploydocker
```

В чате Codex: `/mcp` — должны быть serena, mysql, git, codebase-memory-mcp, sourcegraph, …

## Проектные правки против цикла

См. `.codex/AGENTS.md` → **Anti-Loop Guard** и **update_plan**.
