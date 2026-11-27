# Аудит скрипта синхронизации сред (environment-sync)

**Проект:** `seharnes`
**Объект аудита:** Skill `.agents/skills/harness-router/children/environment-sync/` — скрипт синхронизации конфигураций агентных сред (Cursor, Codex, Kilo, OpenCode, omp, Qoder, Qwen, Antigravity/Gemini, DSH) из канонического workspace в проекционные «views» каждого редактора.
**Дата аудита:** 2026-11-26
**Образ ветки:** `arena/7bf00d32-seharnes`, базовый commit `408da959`
**Статус:** подробный аудит, выполнен на реальной runtime-загрузке репозитория.

---

## 1. Что такое environment-sync и почему это важно

Environment-sync — это **второй главный движок** после экспорта harness. Если `harness_transfer.py` / `export_kit.py` (new-project) переносит *кит* (src, docs, скилы, canonical-конфиги) в цель, то environment-sync **из канонического состояния workspace («источник») проецирует видимость каждого агентного редактора («цель/view»)**:

- правила (`.cursor/rules` → `.codex/rules`, `.kilo/rules`, `.opencode/rules`, …);
- MCP-конфиги (`.cursor/mcp.json` → `.codex/mcp.json`, `.kilo/kilo.jsonc`, `opencode.json`, `.omp/mcp.json`, …);
- скрипты-пулы и `mcp.env`;
- навыки (`.qoder/skills`, `.agents/skills.json`, `.dsh/skills`);
- правила-триггеры и permission-фрагменты.

Главная идея — **один канон, много проекций**. Редакторы понимают разные форматы, поэтому один канонический источник (`.cursor/rules`, `.cursor/mcp.json`, `.agents/skills`) переводится в формат каждой среды через **авторитетные генераторы** (`generate-*-config.py`).

**Структура skill:**

```
environment-sync/
├── SKILL.md                      (50 л.)   — описание workflow
├── README.md                     (45 л.)   — поведение enabled/disabled, ручная sync
├── skill.json
├── scripts/                      20 скриптов, 5365 л.
│   ├── sync-agent-views.sh       (88 л.)   — ВХОДНЫЙ скрипт (оркестратор)
│   ├── render_agent_views.py     (139 л.)  — render-движок
│   ├── environment_policy.py     (99 л.)   — читатель registry + safe_path
│   ├── rule_model.py             (166 л.)  — единая модель правил
│   ├── compact_agent_views.py    (295 л.)  — уборка disabled-видов
│   ├── generate-*-config.py      (9 ген.)  — генераторы по средам
│   ├── verify_*.py, workspace-*.py, setup-workspace.py
├── docs/scripts/*.md             (19 л.)   — доки на каждый скрипт
├── references/report-workflow-plan.md
└── tests/                        (9 файлов, 61 тест)
```

---

## 2. Методология аудита

1. **Структурное изучение:** осмотр всех 20 скриптов, SKILL/README, registry, rule-model.
2. **Static:** `py_compile` всех `.py` → **OK**.
3. **Runtime-прогоны на реальном репозитории** (`--root .`):
   - `render_agent_views.py --check` **до** генерации → `failed` (correct drift);
   - `render_agent_views.py` (write) → `rendered`, 4 генератора `passed`;
   - `render_agent_views.py --check` **после** генерации → `passed` (идемпотентность);
   - `sync-agent-views.sh --local-only --strict` → **полный прогон, все verify-шаги `PASS`**;
   - прямой прогон `generate-codex-mcp.py --check`.
4. **Тесты:** `python3 -m unittest discover -s tests` → **61 тест, 6 failures + 1 error + 11 skipped**.
5. **Проверка сохранности git:** после runtime-прогонов `git status` → только `?? .doc/arena/` (views gitignored, код не тронут).

**Важно:** все runtime-прогоны выполнялись в write-режиме, но попадают в gitignored-проекции (`.codex`, `.kilo`, `.omp`, `opencode.json`, `.opencode`, `.doc/skil_data/...`), поэтому **репозиторий не загрязняется** — это проверено.

---

## 3. Registry и policy-слои (environment_policy.py)

### 3.1 environments.json — авторитетный список сред

`harness-core/assets/environments.json`, `schema: 1`, **9 сред**:

| id       | enabled | adapter    | generated-paths (проекции) |
|----------|---------|------------|----------------------------|
| cursor   | **False** | cursor | *(канон, не генерируется)* |
| codex    | True    | codex      | `.codex/rules`, `.codex/rules-index.md`, `.codex/config.toml`, `.codex/mcp.json`, `.codex/scripts`, `.codex/mcp.env`, `.codex/tools/composer.phar` |
| kilo     | True    | kilo       | `.kilo/rules`, `.kilo/rules-index.md`, `.kilo/kilo.jsonc`, `.kilo/mcp.json`, `.kilo/scripts`, `.kilo/mcp.env`, `.kilo/kilo-permissions.fragment.jsonc` |
| qoder    | False   | qoder      | `.qoder/rules`, `.qoder/skills`, `.qoder/settings.json` |
| qwen     | False   | qwen       | `.qwen/rules`, `.qwen/skills`, `.qwen/settings.json` |
| agents   | False   | agents     | `.agents/rules`, `.agents/mcp.json`, `.agents/mcp_config.json`, `.agents/skills.json`, `.agents/scripts`, `.agents/mcp.env`, `.doc/skil_data/.../antigravity_mcp_config.json`, `.doc/skil_data/.../antigravity_mcp_config.windows-wsl.json` |
| opencode | True    | opencode   | `.opencode/rules`, `.opencode/rules-index.md`, `.opencode/permissions.fragment.json`, `opencode.json` |
| omp      | True    | omp        | `.omp/mcp.json` (только MCP) |
| dsh      | False   | dsh        | `.dsh/skills`, `.dsh/project.patch.yml`, `DSH-RULES.md`, `DSH-BOOTSTRAP.md` |

**Оценка:** registry — **один источник правды**, чёткий и валидированный. `load()` читает trusted-registry и перекрывает root-local `environments.json` (override для конкретного workspace), проверяет `schema==1`, отклоняет неизвестные/дубли/некорректные сред. **Качество: отличное.**

### 3.2 safe_path — защита от path-traversal и symlink-эвекции

`environment_policy.py:safe_path()`:
- отклоняет `..` и `\`;
- ограничивает путь в namespaces, генерируемых средой;
- проверяет symlink-родителей (не выходит за пределы).

**Оценка:** protection-слой серьёзный и правильный — генераторы не могут выйти за пределы разрешённых проекций. Это препятствует диверству через crafted `environments.json`.

---

## 4. Единая модель правил (rule_model.py)

**4 типа правил** и их перевод:

| kind | alwaysApply | цель (trigger) |
|------|-------------|----------------|
| `always` | true | `always_on` / baseline |
| `conditional` | globs/paths | `glob` / `paths` |
| `agent_requested` | description | `model_decision` / `skill` |
| `manual` | — | manual |

**Приоритет:** `always` > `conditional`. `rebase_links()` перенаправляет ссылки на правила при их перемещении.

**Оценка:** единая модель правил, транслирируемая во все адаптеры, — это **сильная архитектурная ветка**. `verify_rule_triggers.py` проверяет, что каждый адаптер честно переводит kind → trigger (Codex — файл-копия без engine, что корректно фиксируется).

---

## 5. Render-движок (render_agent_views.py) — центральный модуль

**Контракт (139 л.):**

1. **Только авторитетные генераторы.** Движок вызывает генераторы из install (`scripts/generate-*-config.py`), **никогда не выполняет скрипты из сгенерированного root** — защита от execution-injection.
2. **Guards при записи:**
   - отклоняет linked `AGENTS.md`;
   - отклоняет linked сгенерированные outputs (symlink-view);
   - проверяет symlink-родителей.
3. **Шаги генерации** (в порядке):
   - `generate-qoder-config` — preflight (gate);
   - `generate-agent-configs.py` — правила Codex/Kilo/...;
   - `generate-codex-mcp.py` — `.codex/config.toml`;
   - per-entry `generator` (по registry);
   - `generate-mcp-config.py` — native + windows-wsl; копия в `.agents/mcp.json`;
   - копия scripts-пула + `mcp.env`;
   - `generate-antigravity-rules.py`.
4. **Compact:** `compact_agent_views.py` (disabled_only) — pre/post.
5. **`--check`** = verify-only (ничего не пишет).

**Оценка:** архитектура **очень качественная**: fail-closed, trusted-generator-exec, guards, atomic-записи в генераторах. Render-режим здоров, идемпотент.

---

## 6. Аудит по каждой среде (режим write / check)

### 6.1 Cursor (enabled=False, канон)
- Не генерируется — **это канон** (`.cursor/rules`, `.cursor/mcp.json`). Все остальные среды — проекции канона.
- **Оценка: корректно.** Cursor = источник правды.

### 6.2 Codex (enabled=True)
- Генератор `generate-codex-mcp.py` (336 л.):
  - читает `.cursor/mcp.json` (канон),
  - проверяет `alwaysAllow` (только список строк), при наличии → **warning**: `alwaysAllow ignored; existing Codex approval policy retained (14)`;
  - для disabled HTTP-серверов с literal header → warning `inert stub prevents unauthenticated start (1)` и подменяет command на `exit 1`-stub (защита);
  - атомарная запись: `NamedTemporaryFile` + `os.fsync` + `os.replace`; сохраняет `st_mode` (`os.fchmod`);
  - `--check`: `unchanged` / `different` → `exit 0/1`.
- **Runtime:** write → `passed`; `--check` до генерации → `exit 1 (different)`; после → `passed`.
- **Находка Н-ЭС-4:** **semantic-loss** — Codex игнорирует `alwaysAllow` из канона (14 шт). Approval-policy канона не переносится в Codex. Это зафиксировано warningом, но **информация о потере доступности теряется** — результат правильный, но пользователь не видит, что разрешения не перенесены.
- **Оценка: генератор качественный (атомарность, validation), но есть semantic-loss по approval-policy.**

### 6.3 Kilo (enabled=True)
- `generate-agent-configs.py` → `.kilo/rules`, `.kilo/rules-index.md`, `.kilo/kilo.jsonc`.
- MCP в `.kilo/kilo.jsonc` + permission-фрагмент `.kilo/kilo-permissions.fragment.jsonc`.
- **Runtime:** write → `passed`; `.kilo/kilo.jsonc` создан (7457 л.).
- **Оценка: корректно.**

### 6.4 OpenCode (enabled=True)
- `generate-opencode-config.py` (396 л.) → `.opencode/rules`, `opencode.json`, permission-фрагмент.
- **Runtime:** write → `passed`; `opencode.json` (4654 л.), `.opencode/rules/audit-plan.md` созданы.
- **Оценка: корректно.**

### 6.5 omp (oh-my-pi, enabled=True)
- `generate-omp-config.py` (236 л.) → **только** `.omp/mcp.json` (самом минимальная проекция).
- **Runtime:** write → `passed`; `.omp/mcp.json` (4319 л.) создан.
- **Оценка: корректно, минимально-инvasive.**

### 6.6 Qoder (enabled=False)
- `generate-qoder-config.py` (507 л.) — gate/preflight в render (запускается всегда, даже при disabled, как gate).
- `compact` удаляет `.qoder/skills` **только** если он точно совпадает с canonical skill-tree (защита от удаления пользовательского); discovery-wrappers защищены.
- **Оценка: fail-closed-compact — качественно.**

### 6.7 Qwen (enabled=False)
- `generate-qwen-config.py` (450 л.) → `.qwen/rules`, `.qwen/skills`, `.qwen/settings.json`.
- **Оценка: генератор готов, но не активирован по умолчанию.**

### 6.8 agents / Antigravity + Gemini (enabled=False)
- `generate-antigravity-rules.py` (133 л.) + `generate-agent-configs`.
- Генерирует `.agents/mcp.json`, `.agents/skills.json` и **глобальные** `antigravity_mcp_config*.json` (native + windows-wsl) в `.doc/skil_data/...`.
- **Синхронизация global Gemini-symlinks:** `sync-agent-views.sh` копирует `~/.gemini/config/mcp_config.json` (+ windows-wsl вариант) **только** если `agents` enabled и не `--local-only`.
- **Оценка: правильно управляется через enabled-gate; global-мутация защищена.**

### 6.9 DSH (enabled=False)
- `generate-dsh-config.py` (644 л.) → `.dsh/skills`, `.dsh/project.patch.yml`, `DSH-RULES.md`, `DSH-BOOTSTRAP.md`.
- **Находка Н-ЭС-2:** тест `test_dsh_kit` падает — `FileNotFoundError: .../new-project/scripts/rebase_project.ps1`. Этот Windows-`.ps1`-ссылка **отсутствует в репозитории** (только Linux-код в shipping). Gemerator есть, но test-wiring ссылается на несуществующий файл.
- **Оценка: генератор готов, tests-wiring не портативна.**

---

## 7. Аудит orchestration-скрипта (sync-agent-views.sh)

**Входные опции:** `--local-only`, `--install-windows-mcp`, `--replace-managed-mcp`, `--allow-drift`, `--strict`.

**Поток:**
1. `environment_policy.py --list-enabled-shell` → список активных сред.
2. `render_agent_views.py` (write) — генерация всех views.
3. **Global Gemini-symlink sync** (только если `agents` enabled и не local-only).
4. **Verify-pipeline** (через `verify_step`, накапливает `FAILURES`):
   - `parity` — `verify_parity.py` (canonical vs views, hash);
   - `render-check` — `render_agent_views.py --check` (идемпотентность);
   - `rule-triggers` — `verify_rule_triggers.py` (kind→trigger mapping);
   - `rule-visibility` — `harness_mirror.py visibility --summary` (**соседний skill** `mirror/`);
   - `mcp-views` — `verify_mcp_views.py` (**соседний skill** `mcp-audit/`);
   - `parity-fresh` — `verify_parity.py --check` (drift vs canonical);
   - skill-scan — `scan_local_skills.py` (**соседний skill** `add-skill/`), с предложением install local-skills.
5. Выход `1` на любом FAIL, если не `--allow-drift`.

**CANON/PARITY/MCP-массивы** собираются динамически под enabled-среды (codex/kilo/qoder/agents/qwen/opencode/omp). **Оценка: orchestration надёжный, fail-closed, динамический сбор под active-среды.**

**Находка Н-ЭС-6 (cross-skill coupling):** sync **зависит от скриптов соседних скилов** (`mirror/`, `mcp-audit/`, `add-skill/`). Это по метро-проектной архитектуре, но создаёт **слабую узловую точку**: если ветка/кит ломаёт mirror/mcp-audit/add-skill, sync падает вне своей вины. На сегодня все 3 ключа существуют и прогоняются.

---

## 8. Verification-pipeline — реальные результаты

Runtime-прогон `sync-agent-views.sh --local-only --strict`:

```
PASS parity        (hash canonical .agents/skills vs views)
PASS render-check  (идемпотентность)
PASS rule-triggers (38 правил, kind→trigger честно)
PASS rule-visibility (harness_mirror visibility)
PASS mcp-views     (.cursor/mcp.json vs .omp/mcp.json, codex, kilo, ...)
PASS parity-fresh  (drift vs canonical)
skill-scan:        канон 77 скилов; manifest не найден;
                   создать baseline: scan_local_skills.py --write-baseline
                   зеркала расходятся: 0, конфликт версий: 0
=== All Agent Views (including MCP config) Successfully Synced ===
```

**Находка Н-ЭС-3 (soft-degradation):** `kit-manifest.json` **отсутствует** (`.doc/skil_data/harness-core/kit-manifest.json` нет, есть только `parity-report.json`). Parity-fresh **проходит**, но с пометкой `manifest не найден: канон нельзя отличить от пакета`. Это **не failure**, а soft-degradation — парность по-прежнему считается, но упускается возможность чётко отличить канон от пакета.

**Оценка: pipeline здоров на реальном workspace, все 6 verify-шагов PASS, exit 0.**

---

## 9. Compact-слой (compact_agent_views.py)

- **disabled_only** — удаляет только проекции disabled-сред;
- **protected-paths** — Qoder skill-tree удаляется **только** при точном совпадении с canonical (не удаляет пользовательское);
- discovery-wrappers защищены;
- pre/post render.

**Оценка: качественная, осторожная уборка.**

---

## 10. setup-workspace.py (workspace-copy / gate)

**Контракт:**
- требует `rsync`, `bash`, `python3`, `node` (hard-dependencies);
- проверяет source/target раздельны, target пуст (только `.git`);
- validate-обход: symlinks (absolute → reject, cross-namespace → reject, ancestor-symlink → reject);
- rsync с `--exclude` (EXCLUDED + PATTERNS `*.pid`, `*-wal`, …);
- запускает `sync-agent-views.sh --local-only --strict --replace-managed-mcp` в target;
- запускает `workspace-gate.py --prepare`;
- пишет `.workspace-ready.json`.
- **Ошибки → `exit 78`**, без retry/cleanup.

**Находка Н-ЭС-2 (environment-dependency / test-portability):** в чистой среде без `rsync` (как в audit-sandbox) → **exit 78**, и тесты `test_t1/t4/t5/t6` падают именно поэтому. Это **не баг кода** — это hard-dependency, но:
- нигде не представлена мягкая деградация (fallback на `cp`/tar) — скрипт резко ломается без rsync;
- тесты workspace-copy **не портируемы** в окружение без rsync/node-sdk.

**Находка Н-ЭС-2b:** `test_t12` падает — `@modelcontextprotocol/sdk` (npm) не установлен в sandbox → MCP-сервер закрывается. Опять же environment-dependency, не кодовой баг.

**Оценка: логика корректна и fail-closed, но hard-dependency на rsync/node делает setup непроизвольным в минимальных окружениях.**

---

## 11. Аудит тестов

`tests/` (9 файлов, **61 тест**): `test_codex_mcp`, `test_dsh_config`, `test_dsh_kit`, `test_generated_copies`, `test_nested_discovery`, `test_omp_config`, `test_render_agent_views`, `test_sync_views`, `test_workspace_copy`.

**Результат: `FAILED (failures=6, errors=1, skipped=11)`**

Разбор падений (все — **environment/portability**, не функциональные баги core-логики):

| Тест | Причина падения | Класс |
|------|------------------|-------|
| `test_t1_copies_ignored_tree_without_sharing` | `78 != 0 : workspace setup failed` — нет `rsync` | env-dependency |
| `test_t4_skips_runtime_exclusions_and_keeps_lockfiles` | `78` — нет `rsync` | env-dependency |
| `test_t5_symlink_policy` | `78` — нет `rsync` | env-dependency |
| `test_t6_each_stage_failure_leaves_unfinished_copy` | `.workspace-setup.started` не создан — нет `rsync` | env-dependency |
| `test_t12_php_alias_branches_use_local_target` | `@modelcontextprotocol/sdk` не установлен (npm) | env-dependency |
| `test_check_mode_on_installed_harness` | codex `--check` → exit 1 (`different`) — тест ожидает `passed` на не-сгенерированном harness | **test-assumption/fail-closed** |
| `test_rebase_copies_kit_and_excludes_it_from_git` (error) | `rebase_project.ps1` отсутствует (Windows-файл) | missing-file |

**Оценка:**
- **6 из 7 падений — не функциональные баги**, а зависимость от окружения (rsync/npm) и несуществующего Windows-файла. Core-логика (render, rule-model, policy, генераторы) **не содержит падающих функциональных тестов** — это сильный знак качества.
- **Находка Н-ЭС-7 (test-assumption):** `test_check_mode_on_installed_harness` падает, потому что `--check` на *не-сгенерированном* harness **правильно** возвращает fail (drift). Тест сделан под подготовленную среду, но не учитывает initial-drift. Это **корректное fail-closed поведение**, ошибка в ожидании теста, не в коде.
- **skipped=11** — часть tests применимы только к конкретным средам.

---

## 12. Результаты runtime-прогонов (сводка)

| Probe | Результат |
|-------|-----------|
| `py_compile` всех скриптов | **OK** |
| `render_agent_views.py --check` (первый, до генерации) | `failed` — **правильный** detect drift (codex `different`, exit 1) |
| `render_agent_views.py` (write) | `rendered`, 4 генератора `passed`, enabled `[codex, kilo, opencode, omp]` |
| `render_agent_views.py --check` (после write) | `passed` — **идемпотентность подтверждена** |
| `generate-codex-mcp.py --check` (прямо) | `different`, exit 1 (до генерации) |
| `sync-agent-views.sh --local-only --strict` | **все 6 verify-шагов `PASS`, exit 0**, `Successfully Synced` |
| `git status` после прогонов | только `?? .doc/arena/` — **views gitignored, код не тронут** |
| tests | 61, 6 failures + 1 error (env-dependency) |

**Созданные проекции:** `.codex/config.toml` (3038 л.), `.kilo/kilo.jsonc` (7457 л.), `opencode.json` (4654 л.), `.omp/mcp.json` (4319 л.), `.opencode/rules/audit-plan.md`.

---

## 13. Нахождения (findings)

### Н-ЭС-1. `--check` на не-сгенерированном workspace читается как «генератор упал»
`render_agent_views.py --check` при дрейфе выводит `generator failed: generate-codex-mcp.py (exit 1)` — технически это **правильный** fail-closed, но сообщение не показывает полезную причину («view отличается от канона, запустите write»). **Семантика верна, UX-улучшение возможно.**

### Н-ЭС-2. Hard-dependency на `rsync`/`node`/npm-sdk без fallback → падения в минимальных окружениях
`setup-workspace.py` требует `rsync` (и генераторы — node-sdk). В окружении без rsync → `exit 78`, тесты workspace-copy падают. **Логика корректна, но непроизвольна.** Указать, что это env-contract, не кодовой баг.

### Н-ЭС-2b. `rebase_project.ps1` отсутствует → test_dsh_kit error
Тест ссылается на Windows-скрипт `rebase_project.ps1`, которого нет в shipping-репозитории (только Linux-код). Missing-file в test-wiring.

### Н-ЭС-3. `kit-manifest.json` отсутствует → soft-degradation parity-fresh
`parity-report.json` есть, `kit-manifest.json` — нет. Parity-fresh проходит, но без baseline не может строго отличить канон от пакета. **Не failure, деградация.**

### Н-ЭС-4. Semantic-loss: Codex игнорирует `alwaysAllow` (14 шт)
`generate-codex-mcp.py` штамбует warning `alwaysAllow ignored; existing Codex approval policy retained` — то есть **approval-policy канона не переносится** в Codex. Результат безопасный (fail-closed на stub), но теряется заявленная доступность. Пользователь должен это видеть.

### Н-ЭС-5. Disabled-среды готовы, но не активны по умолчанию
qoder/qwen/agents/dsh — генераторы готовы, registry-запрещены. **Не баг, дизайн**, но стоит помнить, что их включение меняет проекции + global-Gemini-мутацию.

### Н-ЭС-6. Cross-skill coupling: sync опирается на скрипты соседних скилов
`mirror/scripts/harness_mirror.py`, `mcp-audit/scripts/verify_mcp_views.py`, `add-skill/scripts/scan_local_skills.py`. Сильная связка, единая точка ломания при переносе/обнове соседних скилов.

### Н-ЭС-7. `test_check_mode_on_installed_harness` падает из-за initial-drift (test-assumption)
`--check` правильно завершается fail на не-сгенерированном harness; тест ожидает `passed`. **Корректное fail-closed, ошибка в ожидании теста.**

---

## 14. Вердикт

**Environment-sync — высококачественный, зрелый модуль.** Это не «скрипт-копиромаститель», а **система проекций-синхронизации** с:

- **чётким разделением** canonical (Cursor) vs views (остальные);
- **авторитетным registry** (`environments.json`) и **safe_path-защитой**;
- **единой model-правил** (rule_model) со проверкой триггеров;
- **trusted-generator-execution** (никогда не запускает сгенерированные скрипты);
- **atomic-записями + защитой symlink**;
- **fail-closed** verified-pipeline, идемпотентным `--check`.

**Runtime-прогон на реальном workspace: FULLY PASS** (6 verify-шагов, exit 0). Core-логика **не содержит функциональных багов**.

**Неровности — исключительно environment-portability, semantic-loss и test-assumptions:**
- hard-dependency на rsync/node (Н-ЭС-2/2b) — скрипт непроизволь в минимальных окружениях;
- Codex `alwaysAllow` semantic-loss (Н-ЭС-4);
- отсутствующий `kit-manifest.json` (Н-ЭС-3);
- cross-skill coupling (Н-ЭС-6);
- тесты падают по env-причинам, не по логике (Н-ЭС-7).

**Общая оценка: 8.5–9 из 10.** Зрелый, безопасный, fail-closed движок; шероховатости — лишь на периферии окружений и semantic-потерь, без функциональных дефектов ядра.

---

## 15. Рекомендации (в порядке приоритета)

1. **Н-ЭС-4 (semantic-loss):** в `generate-codex-mcp.py` поднять `alwaysAllow ignored` из warning в явное notice в render/verify-отчёте, чтобы пользователь видел потерю approval-policy.
2. **Н-ЭС-2 (portability):** либо задокументировать rsync/node как hard-contract, либо добавить fallback (tar/cp) в `setup-workspace.py`; тесты workspace-copy сделать skip-при отсутствии rsync.
3. **Н-ЭС-3:** генерировать `kit-manifest.json` при первом sync (`scan_local_skills.py --write-baseline`), чтобы parity-fresh строго различал канон/пакет.
4. **Н-ЭС-6:** задокументировать зависимость sync от mirror/mcp-audit/add-skill или вынести shared-verify в общий пакет.
5. **Н-ЭС-7:** пересмотреть `test_check_mode_on_installed_harness` — ожидать fail на initial-drift, `passed` только после write.
6. **Н-ЭС-1:** улучшить UX `--check`-drift: выдавать читаемый «views differ from canonical — run write».

---

## 16. Связи и история

- Связанный аудит transfer: `.doc/arena/research/audit-harness-transfer-quality.md`.
- CLI-аудит: `.doc/arena/research/audit-harness-transfer-cli.md`.
- Canonical-процедура: `.doc/harnes/seharnes-transfer.md`.
- Registry: `.agents/skills/harness-router/children/harness-core/assets/environments.json`.
- Соседние скилы-зависимости: `harness-router/children/{mirror,mcp-audit,add-skill}/scripts/`.
