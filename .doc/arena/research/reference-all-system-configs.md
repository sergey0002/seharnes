# Эталонные конфиги системы harness

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** справочник **эталонных (канонических) конфигов** harness. Средние конфиги разработки (Cursor, Antigravity, Codex и пр.) вынесены отдельно как результат клонирования. **DSH исключён** (не актуален пока).

**Конвенции меток:**
- **эталон / authored** — ручной, источник правды.
- **derived** — производный/переходный.
- **generated** — сгенерированный (результат клонирования).
- **state** — состояние/кэш (локальное).

---

## 1. Что такое «эталон»

**Эталон (canonical)** — набор конфигов, которые являются **источником правды** для всей системы. Из них:
- строится раскладка путей,
- задаются правила переноса,
- определяются среды и их клонирование,
- проецируются все agent-views.

**Не эталон** (вынесено отдельно, §5): конфиги конкретных сред разработки — `.codex/`, `.kilo/`, `opencode.json`, `.omp/`, `.qoder/`, `.qwen/`, Antigravity/Gemini — они **результат клонирования** из эталона.

**DSH** (§6) — полностью исключён: генератор и конфиги DeepSeek-Harness на данный момент не актуальны.

---

## 2. Эталонные конфиги (canonical)

### 2.1 Канон раскладки путей

#### `.doc/harnes/state/canon-paths.yaml`
- **Статус:** эталон (tracked).
- **Роль:** Canonical Roots Manifest — единственный источник правды по путям harness.
- **Структура:** `schema_version`, `manifest`, `canonical_roots` (rules/skills/mcp_config/mcp_env/scripts/mcp_servers), `policies` (ссылки), `local_extension`, `layout` (раскладка каталогов, forbidden_roots), `distribution` (copy_policy: copy/merge/exclude/preserve по профилям).
- **Читает (Python-CLI):** `validate_structure.py` (секция `layout`), `canon_paths.py` (строгий reader), `doc_mcp.py`, `doc_script.py`, `doc_skill.py`.

#### `.doc/harnes/state/canon-paths.local.yaml`
- **Статус:** local (опциональное; отсутствует по умолчанию).
- **Роль:** локальное расширение; разрешённые секции: `custom_components`.

### 2.2 Правила переноса

#### `.agents/skills/harness-router/children/harness-core/assets/kit.json`
- **Статус:** эталон (adapter-файл, tracked).
- **Роль:** правила переноса — что переносится.
- **Структура:** `schema: 1`, `copy` (13), `rootFiles` (9), `skipDirs` (30), `skipFiles` (29), `skillEntryPoints` (11), `pathExcludes` (8), `stateDirs` (4).
- **Читает (Python-CLI):** `kit_selection.py`, `profile_manifest.py`, `export_kit.py` (`export`).
- **Связь:** производный от canon-paths.yaml; переход на один walker — open-task.

#### `.doc/rebase_project.md` (документ правил переноса)
- **Статус:** эталон (tracked, 2222 л.).
- **Роль:** каноническая процедура переноса kit — профили, сценарии, git-exclude, экспорт.

### 2.3 Реестр сред (определяет клонирование)

#### `.agents/skills/harness-router/children/harness-core/assets/environments.json`
- **Статус:** эталон (tracked).
- **Роль:** реестр сред — **источник для клонирования**.
- **Структура:** `schema`, `environments`. Поля одного env: `id, enabled, adapter, rules, skills, mcp, instructions, generated`.
- **Среды (за исключением DSH):** cursor (canon), codex, kilo, opencode, omp (enabled), qoder, qwen, agents (disabled).
- **Читает (Python-CLI):** `environment_policy.py` (load/list-enabled), `render_agent_views.py`, `sync-agent-views.sh`.
- **См. §4 (клонирование сред).**

### 2.4 Эталонные правила

#### `.cursor/rules/*.mdc` (38 файлов)
- **Статус:** эталон (tracked).
- **Роль:** эталонные правила-конфиг (Cursor-native `.mdc` с frontmatter-триггерами).
- **Структура одного правила:**
  ```yaml
  ---
  name: "…"
  description: "… triggers …"
  alwaysApply: false
  ---
  # тело
  ```
- **Триггеры:** `alwaysApply` (always) / `description`-globs (conditional) / agent_requested / manual (см. `rule_model.py`).
- **Читает (Python-CLI):** `verify_rule_triggers.py`, `generate-agent-configs.py`, `rule_model.py`, генераторы при клонировании.

### 2.5 Эталонный MCP-конфиг

#### `.cursor/mcp.json`
- **Статус:** эталон (tracked).
- **Роль:** эталонная MCP-карта серверов (единый источник для всех адаптере).
- **Содержимое:** `mcpServers` (18 серверов: bitbucket-task, codebase-memory-mcp, codegraph, codeprism, context7, deepwiki, graphiti, git, jira-task, mysql, php-deps-mcp, phpstan-mcp, playwright, semgrep, serena, sourcegraph, xdebug, jdocmunch).
- **Читает (Python-CLI):** `generate-codex-mcp.py`, `generate-mcp-config.py`, `verify_mcp_views.py`, `scan-usage.py`.

#### `.cursor/mcp.env`
- **Статус:** secret (git-excluded, отсутствует по умолчанию).
- **Роль:** секреты MCP-серверов.
- **Читает:** `generate-mcp-config.py` (inline env), `workspace-mcp.py` (`--loaded-env`).

#### `mcp.index.md`, `.doc/mcp.index.md`
- **Роль:** индекс MCP-конфига (корневые файлы kit).

### 2.6 Policy-конфиги (валидация)

#### `.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml`
- **Статус:** эталон (preliminary policy).
- **Роль:** правила формата скила.
- **Структура:** `schema_version, policy_id: skill_format, owner, rules` (SF01: обязательные файлы SKILL.md/README.md/skill.json; SF02: разрешённые каталоги).
- **Читает:** `validate_skills.py`, `validate_structure.py`.

#### `.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml`
- **Статус:** эталон (preliminary policy).
- **Роль:** правила документации компонентов.
- **Структура:** `policy_id: component_docs`, rules (CD01: README forbid_links/forbidden_literals «Заполнить:», «Описание уточняется», «Скил установлен»).
- **Читает:** `validate_docs.py`, `doc_skill.py`, `doc_script.py`, `doc_mcp.py`.

### 2.7 Реестр компонентов

#### `.agents/skills/harness-router/children/improvement/scripts/component_registry.json`
- **Статус:** эталон (tracked).
- **Роль:** реестр компонентов harness.
- **Структура:** `version: 1`, `components` (8): add-skill, copy-project, remove-skill, skill-authoring, migration-review, new-project, neiroslop, mcp-audit.
- **Читает:** `validate_registry.py`.

### 2.8 Schema-конфиги

#### `.agents/skills/harness-router/children/improvement/assets/skill.schema.json`
- **Статус:** эталон.
- **Роль:** JSON-Schema для `skill.json`.
- **Обязательные поля:** `schema, name, kind, entry, readme, resources, tests, children, dependencies, generated`.
- **Читает:** `validate_skills.py`, `audit_skill.py`, `add_skill.py`, `create_skill.py`.

#### `.agents/skills/harness-router/children/mirror/assets/harness-node.schema.json`
- **Статус:** эталон.
- **Роль:** JSON-Schema для узла mirror-графа.
- **Читает:** `harness_mirror.py`.

### 2.9 Metadata скилов (эталон)

| Файл | Роль | Читает |
|------|------|--------|
| **`SKILL.md`** (77 скилов) | каноническое описание скила | все скилы, `audit_skill.py`, генераторы |
| **`skill.json`** (77) | машинная metadata | `validate_skills.py`, `add_skill.py`, `scan_local_skills.py` |
| **`README.md`** (по скилу) | документация скила | `doc_skill.py`, `validate_docs.py` |

### 2.10 Root-конфиги (эталон, входят в kit)

| Файл | Роль |
|------|------|
| `AGENTS.md` | канональное agent-направление |
| `mcp.index.md`, `.doc/mcp.index.md` | индекс MCP |
| `kilo.json` | Kilo root-config |
| `.codeprism.toml` | CodePrism config |
| `.cbmignore` | exclude для codebase-memory |
| `.doc/harnes/state/26-tools.md` | inventory инструментов |

### 2.11 Состояние/манифесты (state, локальное)

| Файл | Роль | Статус |
|------|------|--------|
| `.doc/skil_data/harness-core/parity-report.json` | отчёт парности канон↔views | state |
| `.doc/skil_data/harness-core/kit-manifest.json` | baseline скилов для scan | state (absent по умолчанию) |
| `.doc/harnes/state/.validate-rules-last.json` | fingerprint-кэш проверки правил | state (gitignored) |
| `.cursor/.validate-rules-last.json` | fingerprint-кэш (дублирующий) | tracked |

**Читает:** `verify_parity.py --check`, `scan_local_skills.py --baseline`, `validate_*`.

---

## 3. Эталон — сводная таблица

| Конфиг | Категория | Роль | Читает (Python-CLI) |
|--------|-----------|------|---------------------|
| `canon-paths.yaml` | раскладка путей | верхний канон | validate_structure, canon_paths |
| `kit.json` | перенос | правила переноса | kit_selection, profile_manifest, export_kit |
| `environments.json` | среды | реестр (клонирование) | environment_policy, render_agent_views |
| `.cursor/rules/*.mdc` | правила | эталонные правила | verify_rule_triggers, генераторы |
| `.cursor/mcp.json` | MCP | эталон MCP | generate-*-mcp, verify_mcp_views |
| `policies/skill-format.yaml` | валидация | формат скила | validate_skills |
| `policies/component-docs.yaml` | валидация | доки компонентов | validate_docs |
| `component_registry.json` | реестр | компоненты | validate_registry |
| `skill.schema.json` | schema | metadata скила | validate_skills, audit_skill |
| `harness-node.schema.json` | schema | узел mirror | harness_mirror |
| `SKILL.md` / `skill.json` | metadata | скилы | валидаторы, генераторы |
| root-конфиги | root | корень проекта | export_kit |

---

## 4. Клонирование сред (с учётом эталона)

Среды разработки **не живут своими конфигами** — они **клонируются из эталона**. Механизм:

```
эталон (canonical sources)
  ├── .cursor/rules/*.mdc         (эталонные правила)
  ├── .cursor/mcp.json           (эталон MCP)
  └── .agents/skills/            (эталон скилов + skill.json)
        │
        ▼
environments.json (реестр: что клонировать, какой адаптер, generated-paths)
        │
        ▼
render_agent_views.py + generate-*-config.py (trusted-генераторы)
        │
        ▼
клонированные views сред (результат, §5)
```

**Ключевые точки клонирования:**
- **`environments.json`** — определяет список сред, их `adapter`, `enabled` и `generated`-пути. Это каноническое описание «как клонировать».
- **`render_agent_views.py`** — orchestrator: вызывает trusted-генераторы из install, **никогда не запускает скрипты из render-root** (защита от injection).
- **`generate-*-config.py`** — генераторы: проецируют эталон (правила, MCP) в формат каждой среды.
- **`environment_policy.py --list-enabled`** — выбирает активные среды для клонирования.
- **`verify_parity.py` / `verify_mcp_views.py` / `verify_rule_triggers.py`** — проверяют, что клонированные views совпадают с эталоном.

**Идея:** один эталон, N клонированных сред. Изменение эталона → повторный render → все клонированные views обновляются. Данные сред не правятся напрямую как второй канон.

---

## 5. Конфиги сред разработки — отдельно (результат клонирования, не канон)

> Вынесено отдельно: **это не наша зона**. Эти конфиги — **результат клонирования** из эталона (§4), gitignored runtime-проекции. При необходимости править клонирование — править **эталон**, а не views.

Клонированные конфиги сред (по `environments.json`):

| Среда | Конфиги (clone) | Generator |
|-------|------------------|-----------|
| Codex | `.codex/config.toml`, `.codex/mcp.json`, `.codex/mcp.env` | `generate-codex-mcp.py`, `generate-agent-configs.py` |
| Kilo | `.kilo/kilo.jsonc`, `.kilo/mcp.json`, `.kilo/rules` | `generate-agent-configs.py`, `generate-mcp-config.py` |
| OpenCode | `opencode.json`, `.opencode/rules` | `generate-opencode-config.py` |
| omp | `.omp/mcp.json` | `generate-omp-config.py` |
| Qoder | `.qoder/settings.json`, `.qoder/skills`, `.qoder/rules` | `generate-qoder-config.py` (disabled) |
| Qwen | `.qwen/settings.json`, `.qwen/rules` | `generate-qwen-config.py` (disabled) |
| agents/Antigravity+Gemini | `.agents/mcp.json`, `.agents/skills.json`, global mcp_config | `generate-mcp-config.py` (disabled) |

**Status:** generated (gitignored). **Читает:** `verify_parity.py`, `verify_mcp_views.py`, `render_agent_views.py --check`.

---

## 6. DSH — исключён

**DSH (DeepSeek-Harness) исключён из справочника** — не актуален пока.

Исключено из рассмотрения:
- `generate-dsh-config.py` (генератор DSH);
- конфиги `.dsh/project.patch.yml`, `DSH-RULES.md`, `DSH-BOOTSTRAP.md`;
- DSH-документы `.doc/harnes/dsh/*.json`;
- запись DSH в `environments.json` (в реестр сред он есть, но в данном документе не учитывается).

При восстановлении актуальности DSH опять включается как среда в §4 (клонирование) и §5 (views).

---

## 7. Иерархия

```
ЭТАЛОН (canonical)
├── canon-paths.yaml     ── раскладка путей
├── kit.json             ── правила переноса
├── environments.json    ── реестр сред (определяет клонирование)
├── .cursor/rules/*.mdc  ── эталонные правила
├── .cursor/mcp.json     ── эталон MCP
├── policies/*.yaml      ── валидация
├── component_registry.json, schema, skill metadata
└── root-конфиги

КЛОНИРОВАНИЕ (§4)
└── environments.json → render → генераторы → views

VIEWS (§5, не канон)
└── .codex/ .kilo/ opencode.json .omp/ .qoder/ .qwen/ .agents/
```

**Принцип:** править **эталон**; клонированные views пересобираются из него. DSH — вне зоны на данный момент.

---

## 8. Связи

- Эталон раскладки + переноса: `.doc/arena/research/reference-configs-paths-transfer.md`.
- Аудит переноса: `.doc/arena/research/audit-harness-transfer-quality.md`.
- Аудит environment-sync (клонирование): `.doc/arena/research/audit-environment-sync.md`.
- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`.
- Рефлексия kit: `.agents/skills/harness-router/children/harness-core/references/kit.md`.

*Справочник собран по статическому анализу репозитория; средние конфиги вынесены отдельно, DSH исключён.*
