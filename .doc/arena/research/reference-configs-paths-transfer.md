# Конфиги harness: конфиг директорий и конфиг правил переноса

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** два канонических конфига, управляющие раскладкой и переносом — **конфиг директорий** (`canon-paths.yaml`) и **конфиг правил переноса** (`kit.json`), плюс сопутствующие policy-конфиги.

---

## 1. Конфиг директорий — `canon-paths.yaml`

**Путь:** `.doc/harnes/state/canon-paths.yaml`
**Статус в git:** tracked (в репозитории).
**Обновлён:** 2026-11-11
**Роль:** **Canonical Roots Manifest** — «единственный источник правды» (Single Source of Truth) по всем путям harness.

**Что это:** регламент раскладки каталогов. Задаёт, где лежат канонические корни (правила, скилы, MCP, скрипты) и как каждый путь распределяется по профилям (core/developer/project) при переносе.

**Кто читает:**
- `validate_structure.py` (improvement) — читает **секцию `layout`** и проверяет раскладку каталогов.
- `canon_paths.py` (harness-core) — строгий reader (парсинг + валидация `distribution`).
- `doc_mcp.py`, `doc_script.py`, `doc_skill.py` — через `canon_paths.py` для policy-root.

**Структура:**

```yaml
schema_version: 1
manifest:            # метаданные: path, role=policy, owner=harness-core, required_profiles
canonical_roots:     # канонические корни
  path_manifest: ".doc/harnes/state/canon-paths.yaml"
  rules:           ".cursor/rules"          # 38 .mdc с триггерами
  skills:          ".agents/skills"         # SKILL.md, scripts/, skill.json
  mcp_config:      ".cursor/mcp.json"       # MCP-карта серверов
  mcp_env:         ".cursor/mcp.env"        # секреты (git-excluded)
  scripts:         ".tools/scripts"         # системные утилиты
  mcp_servers:     ".tools/mcp-servers"     # php-toolchain (phpstan, php-deps)
policies:            # ссылки на policy-конфиги
  skill_format:     ".agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml"
  component_docs:   ".agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml"
local_extension:     # опциональное локальное расширение (absent по умолчанию)
  path: ".doc/harnes/state/canon-paths.local.yaml"
  allowed_sections: ["custom_components"]
layout:              # машинно-проверяемая раскладка (читается validate_structure)
  scripts: { system, skill, stack }
  docs: { script_skill, script_tools, mcp_skill, mcp_disabled, state }
  tools_inventory, skill_data, task_tests, temp_dir, test_path_markers, forbidden_roots
distribution:        # атрибуты переноса для каждого пути
  - ref: "canonical_roots.rules"
    role: "authored"
    profiles: ["core", "developer", "project"]
    copy_policy: "copy"        # copy | merge | exclude | preserve
    owner: "harness-core"
    doc_policy: "required"
    scan_policy: "owned"
```

**Ключевые смыслы `distribution.copy_policy`:**
- `copy` — копируется в kit/профиль.
- `merge` — сливается (например `.cursor/mcp.json` — MCP-конфиг).
- `exclude` — исключается (секреты `mcp.env`, состояние `state`).
- `preserve` — остаётся на месте (локальные проэктные).

**Почему разные каталоги** (из comments конфига):
- `rules: .cursor/rules/` — Cursor-native .mdc с frontmatter-триггерами; IDE читает напрямую.
- `skills: .agents/skills/` — канон; generated-views различаются по средам.
- `mcp_config: .cursor/mcp.json` — единый источник для всех адаптере; секреты в `.cursor/mcp.env`.
- `scripts: .tools/scripts/` — системные утилиты (multi-search, multi-exec, php-docker, node-mcp…).
- `mcp_servers: .tools/mcp-servers/` — php-toolchain; не зеркалится в views агентов.

---

## 2. Конфиг правил переноса — `kit.json`

**Путь:** `.agents/skills/harness-router/children/harness-core/assets/kit.json`
**Статус в git:** tracked.
**Роль:** **конфиг правил переноса** — задаёт, что именно переносится (каталоги, корневые файлы, entrypointы), что исключается (skipDirs/skipFiles), какие пути local/state.

**Что это:** правила сборки kit (набора для переноса). По ним `kit_selection.py` выбирает файлы, `profile_manifest.py` строит карту профилей, `export_kit.py`/`harness_transfer.py export` копируют.

**Кто читает:** `kit_selection.py`, `profile_manifest.py`, `export_kit.py`.

**Структура (`schema: 1`):**

| Ключ | Кол-во | Что значит |
|------|--------|-------------|
| `copy` | 13 | каталоги/файлы, входящие в kit |
| `rootFiles` | 9 | файлы в корне проекта |
| `skipDirs` | 30 | каталоги, которые не копируются |
| `skipFiles` | 29 | файлы/паттерны, не копируемые |
| `skillEntryPoints` | 11 | entrypoint-скилы, входящие в kit |
| `pathExcludes` | 8 | пути, исключённые из переноса |
| `stateDirs` | 4 | состояние/индексы/временные (не в Git и kit) |

**`copy` (13):**
`.cursor`, `.codex`, `.agents`, `.kilo`, `.opencode`, `.omp`, `.serena`, `.doc/harnes`, `.doc/web`, `.doc/qa`, `.tools/codeception`, `.tools/mcp-servers`, `.tools/scripts`
> Примечание: `.doc/qa` — в kit, но проектные флоу переносятся отдельно.

**`rootFiles` (9):**
`AGENTS.md`, `mcp.index.md`, `kilo.json`, `.codeprism.toml`, `.cbmignore`, `.doc/rebase_project.md`, `.doc/mcp.index.md`, `.doc/harnes/state/canon-paths.yaml`, `.doc/harnes/state/26-tools.md`

**`skillEntryPoints` (11):** code/bug-cause, documentation-router/doc-verify, project-doc, task-doc, task-router/audit-plan, git-task-blame, gototask, task-code-review, task-diff, task-intake, harness-router/harness-core.

**`pathExcludes` (8):**
`.doc/skil_data`, `.doc/tasks`, `.doc/temp`, `.doc/tmp`, `.doc/web/state`, `.doc/qa/tmp-runs`, `.cursor/tools/codeprism-ai/venv`, `.agents/skills/login-as-user`

**`skipDirs` (30):** node_modules, vendor, `__pycache__`, .venv*, cache, runs, work, reports, test-runs, logs, output, `_output`, `.pytest_cache`, tmp-runs, plans, worktrees, backups, upstream, team-memory, artifacts, memories, `.state`, `.data`, venv, registry.snapshots, out.

**`skipFiles` (29):** секреты (`mcp.env`, `.env`, `*.token`), локальные (`*.local.*`, `ADAPTERS.local.md`, `actions.local.json`, `project.local.yml`), временные (`*.log`, `run.log`), бинарники (`*.phar`, `*.pyc`), артефакты (`*.fail.png`, `*.fail.html`, `dump.sql`, `DSH-RULES.md`), `package-lock.json`, `registry.json`, `out_copytrust.json` (legacy).

**`stateDirs` (4):** `.doc/skil_data`, `.doc/temp`, `.doc/tmp`, `.doc/skil_data/jdocmunch`.

---

## 3. Связь между двумя конфигами

Из `references/kit.md`:

- **`canon-paths.yaml` — единственный authored регламент путей.**
- `kit.json`, `profile_manifest.py` и PowerShell-списки — **производные/переходные**; **нельзя править как второй канон**.
- `kit.json` пока остаётся **authored adapter-файлом**. `profile_manifest.py` строит по нём карту Core/Developer/Project; `cmd_export --dry-run` использует эту карту.
- **Фактический PowerShell-export ещё копирует по своим спискам**, поэтому **полный переход на один walker и генерация `kit.json` из `canon-paths.yaml` остаются открытыми задачами**.
- В `canon-paths.yaml` уже есть секции `distribution`, но профильная карта пока берёт состав из `kit.json`.

**Итог:** `canon-paths.yaml` — канон «как устроены пути», `kit.json` — правила «что из этого переносится». Полная конвергенция (один walker, kit.json генерируется из canon-paths) — TODO.

---

## 4. Сопутствующие конфиги (policies и реестр)

### 4.1 Policy-конфиги (валидационные правила)
Указываются в секции `policies` canon-paths.yaml; читаются `validate_skills.py` / `validate_docs.py` через `canon_paths.py`.

- **`skill-format.yaml`** (`policy_id: skill_format`) — правила формата скила: `SF01` (обязательные файлы: SKILL.md, README.md, skill.json), `SF02` (разрешённые каталоги: scripts, docs, references, assets, tests), severity/enabled/scope.
- **`component-docs.yaml`** (`policy_id: component_docs`) — правила документации компонентов: `CD01` (для README: `forbid_links`, `forbid_relations_section`, forbidden_literals: «Заполнить:», «Описание уточняется», «Скил установлен»), `CD02`…

> Оба — «preliminary policy»: строгая валидация потребляет безопасную подмножество, не разрешая policy смягчать установленные trusted-правила.

### 4.2 `component_registry.json`
**Путь:** `.agents/skills/harness-router/children/improvement/scripts/component_registry.json`
**Роль:** реестр компонентов harness. `version: 1`; `components`: 8 — add-skill, copy-project, remove-skill, skill-authoring, migration-review, new-project, neiroslop, mcp-audit.
**Кто читает:** `validate_registry.py`.

### 4.3 `.validate-rules-last.json` (кэш fingerprint проверки)
- `.doc/harnes/state/.validate-rules-last.json` — **gitignored** (локальный кэш fingerprints правил).
- `.cursor/.validate-rules-last.json` — tracked (дублирующий fingerprint-список).
**Роль:** запись хэшей проверённых правил для детекции дрейфа (последняя проверка).

### 4.4 `canon-paths.local.yaml` (локальное расширение)
**Упоминается** в `local_extension` canon-paths.yaml, но **отсутствует на диске** по умолчанию. Разрешённые секции: `custom_components`. Создаётся по необходимости для локальных дополнений.

### 4.5 `.doc/harnes/state/09-transfer.md` (документ правил переноса)
**Роль:** подробный снимок переноса kit (108 КБ) — профили/сценарии, git-exclude, раскладка на машине, инвентарь AI-kit, матрица skill/rule, export скриптом `rebase_project.ps1`, процедура FULL, профиль CORE. Устаревший снимок (2026-09), но исчерпывающий референс по правилам переноса.

---

## 5. Иерархия и потоки

```
canon-paths.yaml  (канон раскладки + distribution + policies)
   ├── reads: validate_structure.py (layout), canon_paths.py (strict reader)
   ├── references policies: skill-format.yaml, component-docs.yaml
   └── local_extension: canon-paths.local.yaml (optional)

kit.json  (правила переноса: copy/skip/entrypoint/state)
   ├── reads: kit_selection.py, profile_manifest.py, export_kit.py
   └── derived profile map: core/developer/project

component_registry.json  (реестр компонентов) → validate_registry.py
.validate-rules-last.json (fingerprint-кэш) → дрейф-детект
```

**Главный вывод:** в harness есть чёткая иерархия — `canon-paths.yaml` (какие пути и как распределяются) как **верхний канон**, `kit.json` (что переносится) как **переходный/authored-adapter**. Полная конвергенция (один walker, kit.json генерируется из canon-paths) — открытая задача (см. `references/kit.md`).

---

## 6. Связи

- Аудит переноса: `.doc/arena/research/audit-harness-transfer-quality.md`.
- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`.
- Canonical-процедура: `.doc/harnes/seharnes-transfer.md`.
- Рефлексия kit: `.agents/skills/harness-router/children/harness-core/references/kit.md`.
- Строгий reader: `.agents/skills/harness-router/children/harness-core/scripts/canon_paths.py`.
