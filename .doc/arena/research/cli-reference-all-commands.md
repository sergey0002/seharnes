# Справочник CLI-команд проекта `seharnes`

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** полный справочник всех CLI-точек входа (Python + shell) по всему репозиторию.
**Способ:** каждый парсер запрашивался напрямую (`--help` + help-свёздок), поэтому атрибуты и описания — авторитетные (как в самом скрипте).

**Содержание:**
- [0. Общие конвенции](#0-общие-конвенции)
- [1. Harness core & router](#1-harness-core--router)
- [2. environment-sync (синхронизация сред)](#2-environment-sync-синхронизация-сред)
- [3. new-project (перенос/экспорт кита)](#3-new-project-переносэкспорт-кита)
- [4. Управление скилами](#4-управление-скилами)
- [5. MCP-аудит, миграция, документы, improvement](#5-mcp-аудит-миграция-документы-improvement)
- [6. project-setup / onboard](#6-project-setup--onboard)
- [7. task-router (втекст задач)](#7-task-router-втекст-задач)
- [8. documentation-router](#8-documentation-router)
- [9. exhaustive-research / codeprism / иные скилы](#9-exhaustive-research--codeprism--иные-скилы)
- [10. todone (трекер)](#10-todone-трекер)
- [11. Shell-скрипты и утилиты](#11-shell-скрипты-и-утилиты)
- [12. Кодовые возвраты](#12-кодовые-возвраты)

---

## 0. Общие конвенции

Подавляющая часть скриптов держит **общие флаги**. Везде, где они присутствуют, значения одинаковые:

| Флаг | Значение |
|------|----------|
| `-h, --help` | вывести справку и выйти. |
| `--root ROOT` | корень проекта (по умолчанию — cwd). |
| `--json` / `--jsonl` | машиночитаемый вывод: `--json` — один объект, `--jsonl` — построчные события. |
| `--check` | проверить без записи (verify-only); часто失败 при дрейфе. |
| `--dry-run` | вывести план действий без внесения изменений. |
| `--yes` / `--force` | пропускать интерактивное подтверждение / принудительно. |
| `--exclude`, `--keep` | (обычно repeatable) исключить / оставить путь. |
| `--warn-only` | показать предупреждения, не failed. |
| `--non-interactive` | обещание «никогда не задавать вопросов» (наследственно от engine). |

**Совет:** для каждого скрипта всегда читайте `--help` — в этом справочнике приведены основные опции; вaraw-help при желании можно перепроверить.

---

## 1. Harness core & router

### `harness_cli.py` — управляющий CLI harness
**Что делает:** sentralный пункт управления: диагностика, установка хуков, синхронизация, экспорт, onboard, MCP-аудит, verify.
**Синтаксис:** `harness_cli.py [-h] [--root ROOT] {doctor,setup-hooks,sync,export,setup,mcp-audit,verify} ...`

#### `doctor`
**Что делает:** общая диагностика структуры и гейтов.
- `--task TASK` — deprecated (plan-validator удалён).
- `--skip-gates` — только проверки config/adapters.
- `--junk` — показать лишние файлы и каталоги.
- `--compact` — пропустить гейты генерируемых views.
- `--mode {standard,strict}` — strict failed при обнаружении хлама.
- `--checks CHECKS` — запятыми список гейтов (config-checks всегда идут).
```
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py --root . doctor
```

#### `setup-hooks`
**Что делает:** установить pre-commit хук harness.
- `--yes` — без подтверждения.
```
python3 .../harness_cli.py setup-hooks --yes
```

#### `sync`
**Что делает:** запустить синхронизацию видимости агентов.
- `--dry-run` — без записи.
- `--yes` — без подтверждения.
- `--env ENV` — конкретная среда.

#### `export`
**Что делает:** экспортировать harness-кит в цель.
- `--target TARGET` — цель (обязательно).
- `--project-name PROJECT_NAME`.
- `--profile {Full,Core,Developer,Project}`.
- `--mode {migrate,clean,update}`.
- `--yes`, `--dry-run`, `--skip-preflight`, `--skip-tools`, `--no-review`, `--no-backup`.

#### `setup`
**Что делает:** подготовка окружения (PHP-container, MySQL, порты).
- `--check`, `--php-container PHP_CONTAINER`, `--mysql {keep,disable,set}`, `--mysql-database`, `--mysql-port`, `--serena-port`, `--web-port`, `--skip-indexes`.

#### `mcp-audit`
**Что делает:** аудит MCP-видимости.
- `--usage` — включить скан использования.

#### `verify`
**Что делает:** проверить состояние (без опций, смотри вспом. help).

---

### `harness_mirror.py` — граф узлов harness
**Что делает:** ведёт «один JSON-узел на файл harness»: скан, анализ, применение, проверка, viewer.
**Синтаксис:** `harness_mirror.py [-h] [--root ROOT] [--data DATA] {scan,prompt,apply,get,bundle,lint,review,audit,set,build,rebuild,check,visibility,serve} ...`
- `--root ROOT` — корень; по умолчанию — ближайший `.git`/`.cursor`.
- `--data DATA` — каталог данных относительно root.

| Субкоманда | Что делает | Атрибуты |
|-----------|------------|----------|
| `scan` | построить/обновить узлы | `--paths [PATHS ...]`, `--include-mirrors`, `--include-dsh`, `--force` (игнорировать кэш) |
| `prompt` | вывести задачу анализа для узла | `--node NODE` |
| `apply` | слить анализ агента в узел | `--node NODE`, `--json JSON` (stdin), `--model MODEL` |
| `get` | вывести узел с рёбрами | `--node NODE`, `--slim` (без блоков) |
| `bundle` | компактный вид скила: файлы, триггеры, рёбра | `--skill SKILL` |
| `lint` | структурная проверка всего канона | — |
| `review` | пакет semantic-review: digest, outline, issues | `--node NODE`, `--skill SKILL`, `--all` |
| `audit` | компактный отчёт аудита узла/скила | `--node NODE`, `--skill SKILL` |
| `set` | заменить блок или весь файл скила/правила | `--node NODE`, `--block BLOCK`, `--file` (весь файл), `--content CONTENT` (stdin) |
| `build` | записать `graph.json` и viewer | — |
| `rebuild` | обновить изменившиеся источники + записать graph/viewer | — |
| `check` | проверить инварианты | — |
| `visibility` | матрица видимости правил по средам | `--summary` (без полной матрицы) |
| `serve` | статика viewer + write-API | `--host HOST`, `--port PORT` |

```
python3 .../harness_mirror.py --root . scan
python3 .../harness_mirror.py visibility --summary
```

### `rebuild-routers.py`
**Что делает:** пересобрать таблицы routerов.
- `--root ROOT`, `--check` (проверить), `--write` (записать), `--json`.

### `render_policy_docs.py`
**Что делает:** проецировать машинные таблицы политик в Markdown между маркерами (проза вне маркеров не трогается).
- `--root ROOT`, `--check` (fail при дрейфе), `--write` (заменить замаченные блоки), `--json`.

### `lib/artifact_status.py`
**Что делает:** прочитать статус артефакта (plan.md).
- positional `path`, `--root ROOT`, `--json`.

### `lib/prompt_budget.py`
**Что делает:** просчёт бюджета количества слов в рюмах скилов.
- `--skills SKILLS`, `--limit LIMIT`, `--json`.

---

## 2. environment-sync (синхронизация сред)

### `sync-agent-views.sh` — ВХОДНЫЙ orchestrator
**Что делает:** основная команда синхронизации всех агентных views: рендер + verify + скан скилов.
**Синтаксис:** `sync-agent-views.sh [--local-only] [--install-windows-mcp] [--replace-managed-mcp] [--allow-drift] [--strict]`
- `--local-only` — только локальный workspace, без глобальной синхронизации Gemini.
- `--install-windows-mcp` — установить windows-wsl MCP.
- `--replace-managed-mcp` — заменить управляемые MCP-записи Qoder.
- `--allow-drift` — не failed при дрейфе (вместо `--strict`).
- `--strict` — failed при любом FAIL.
**Что внутри:** `render_agent_views.py` → синхр. глобальных Gemini-symlinks (если `agents` enabled) → 6 verify-шагов (parity, render-check, rule-triggers, rule-visibility, mcp-views, parity-fresh) → скан скилов.
```
bash .../environment-sync/scripts/sync-agent-views.sh --local-only --strict
```

### `render_agent_views.py` — render-движок
**Что делает:** рендер всех views с помощью авторитетных генераторов (никогда не запускает скрипты из render-root).
- `--root ROOT` (обязательно).
- `--check` — verify без записи.
- `--replace-managed-mcp` — заменить проверенные Qoder MCP-записи.
```
python3 .../render_agent_views.py --root . --check
```

### `environment_policy.py` — читатель registry
**Что делает:** читать environments.json и управлять enabled-списками.
- `--root ROOT`, `--enabled ENV`, `--list-enabled`, `--list-enabled-shell`.

### `compact_agent_views.py`
**Что делает:** удалить генерируемые views, чтобы repo оставался компактным (Qoder-дерево скилов удаляется только при точном совпадении с каноном).
- `--root ROOT`, `--check` (показать без удаления), `--apply` (удалить), `--force` (без проверки содержимого).

### `generate-agent-configs.py`
**Что делает:** генерировать native Codex/Kilo views (canonical-root скилов — `.agents/skills`).
- positional `root`, `--check-discovery` (проверить регистрацию без записи).

### `generate-codex-mcp.py`
**Что делает:** заменить только MCP-настройки Codex из канонического `.cursor/mcp.json` (атомарная запись, `alwaysAllow` → warning).
- `--root ROOT` (обязательно), `--config CONFIG` (existing TOML), `--check` (сравнить), `--audit-canon` (отчёт блокировок без чтения/записи TOML).
- **Коды:** 0 — ok, 1 — `--check` различие, 2 — ошибка аргументов.

### `generate-mcp-config.py`
**Что делает:** из `.cursor/mcp.json` сгенерировать `mcp_config.json` для Antigravity/Gemini (inline env, раскрытие `${workspaceFolder}`/`${env:}`).
- `--host {native,windows-wsl}`, `--distro DISTRO`, `--out OUT_OPTION`, positional `root`, `out`.

### `generate-{opencode,omp,qoder,qwen}-config.py`
**Что делает:** генерировать соответствующий project-view.
- `--root ROOT`; `--check` (verify без записи).
- qoder дополнительно: `--preflight` (проверка unmanaged Qoder-data), `--replace-managed-mcp`.

### `generate-antigravity-rules.py`
**Что делает:** генерировать правила Antigravity.
- `--root ROOT`, `--rules-dir RULES_DIR`, `--out OUT`, `--check`.

### `generate-dsh-config.py`
**Что делает:** из канона Cursor сгенерировать DeepSeek-Harness profile-patch (`.dsh/project.patch.yml` + `DSH-RULES.md`).
- `--root ROOT`, `--patch-out PATCH_OUT`, `--rules-out RULES_OUT`, `--rules-mode {full,compact}`, `--mcp-profile {full,research,implementation,verification}`, `--servers SERVERS`, `--exclude EXCLUDE`, `--no-mcp`, `--overlay OVERLAY`, `--no-llm`, `--no-model-selection`, `--check`, `--force`.
- **Коды:** 0/1/2 (см. help).

### `verify_parity.py`
**Что делает:** проверить views на совпадение с каноном (пакеты — байтово после нормализации переводов строк; правила — по телу без frontmatter).
- `--canonical CANONICAL`, `--view VIEW` (repeatable), `--manifest MANIFEST`, `--rules-canonical`, `--rules-view` (repeatable), `--check` (проверить свежесть манифеста без записи), `--allow-extra`, `--mcp-canonical`, `--mcp-view` (repeatable).

### `verify_rule_triggers.py`
**Что делает:** проверить парность триггеров правил между средами.
- `--root ROOT`, `--canonical`, `--kilo`, `--kilo-index`, `--qoder`, `--qwen`, `--qwen-skills`, `--antigravity`, `--dsh`, `--codex`, `--codex-index`, `--opencode`, `--opencode-index`.

### `verify_generated_copies.py`
**Что делает:** проверить, что discovery-only views содержат wrappers (не прямые копии); «junk» — unexpected content.
- `--root ROOT`.

### `setup-workspace.py`
**Что делает:** скопировать workspace source→target и запустить sync-in-target (требует `rsync`, `bash`, `python3`, `node`).
- `--source SOURCE`, `--target TARGET` (оба обязательны).
- **Код:** 78 — failure (без retry/cleanup).

### `workspace-gate.py`
**Что делает:** gate-проверка workspace.
- positional `command`, `--prepare`, `--source SOURCE`.

### `workspace-mcp.py`
**Что делает:** управлять MCP-сервером workspace.
- `--server {git,phpstan-mcp,php-deps-mcp}`, `--loaded-env`.

---

## 3. new-project (перенос/экспорт кита)

### `harness_transfer.py` — engine переноса
**Что делает:** рид-only engine: fetch, inventory, plan, verify + применение approved-плана. Не выполняет candidate-файлы.
**Синтаксис:** `harness_transfer.py [-h] {inventory,fetch,plan,verify,approve,apply,rollback,render,compact,export,adopt} ...`

| Субкоманда | Что делает | Ключевые атрибуты |
|-----------|------------|-------------------|
| `inventory` | рид-only inventaria source/target | `--source-kind {local,git}`, `--source`, `--repo`, `--commit`, `--target`, `--path`, `--root`, `--exclude`, `--max-file-bytes`, `--jsonl`, `--non-interactive` |
| `fetch` | fetch одного ref в bare-кэш (без checkout) | `--url URL`, `--cache CACHE`, `--ref REF`, `--allow-local`, `--timeout TIMEOUT`, `--jsonl`, `--non-interactive` |
| `plan` | рид-only preview обновления | `--source-kind`, `--source`, `--repo`, `--commit`, `--target`, `--path`, `--root`, `--exclude`, `--max-file-bytes`, `--jsonl`, `--non-interactive`, `--profile {core,developer,project}`, `--operation {install,update,repair}`, `--base-commit`, `--use-receipt`, `--local`, `--use-local-policy`, `--state-dir`, `--release-manifest` |
| `verify` | сравнить файлы цели с receipt | `--target`, `--root`, `--path`, `--max-file-bytes`, `--full` (вне receipt), `--jsonl`, `--non-interactive` |
| `approve` | валидировать решения и зафиксировать план | `--plan PLAN`, `--decisions DECISIONS`, `--jsonl`, `--non-interactive` |
| `apply` | применить один approved-план | `--plan PLAN`, `--approved APPROVED`, `--state-dir`, `--render`/`--no-render`, `--jsonl`, `--non-interactive` |
| `rollback` | откат активного journaled-прогона | `--target`, `--state-dir`, `--max-file-bytes`, `--jsonl`, `--non-interactive` |
| `render` | регенерировать agent-views trusted-generators | `--target`, `--check`, `--jsonl`, `--non-interactive` |
| `compact` | удалить генерируемые views из рабочего дерева | `--target`, `--check`, `--apply`, `--force`, `--jsonl`, `--non-interactive` |
| `export` | копировать harness-кит в проект | `--source`, `--target`, `--profile {core,developer,project}`, `--mode {install,update,mirror}`, `--project-name`, `--skip-runtime-deps`, `--skip-tools`, `--exclude`, `--keep`, `--dry-run`, `--yes`, `--jsonl`, `--non-interactive` |
| `adopt` | preview/commit legacy-adoption | `--target`, `--root`, `--profile`, `--plan`, `--decisions`, `--max-file-bytes`, `--state-dir`, `--jsonl`, `--non-interactive` |

```
python3 .../harness_transfer.py plan --source-kind local --source . --target /tmp/x --profile developer --operation update
```

### `export_kit.py` — engine экспорта
**Что делает:** экспорт кита: один walker, три режима (`install/update/mirror`), без per-adapter-копий. Файловый набор из `assets/kit.json`.
- `--source SOURCE`, `--target TARGET` (обязательный), `--profile {core,developer,project}`, `--mode {install,update,mirror}`, `--project-name PROJECT_NAME`, `--skip-runtime-deps`, `--skip-tools`, `--exclude EXCLUDE` (repeatable), `--keep KEEP` (repeatable), `--dry-run`, `--json`.

### `harness_wizard.py` — мастер-превью
**Что делает:** интерактивный/флаговый мастер для рид-only preview (задаёт source/operation/target, делегирует `plan`). Не копирует и не применяет.
- `--source-kind {local,git}`, `--source`, `--repo`, `--commit`, `--target`, `--profile {core,developer,project}`, `--operation {install,update}`, `--root`, `--path`, `--base-commit`, `--release-manifest`, `--use-receipt`, `--local`, `--use-local-policy`, `--max-file-bytes`, `--non-interactive`, `--yes`.

### `profile_manifest.py`
**Что делает:** собрать файл-мапу profile из kit.json (без записи в цель). `core` пропускает task/tracker.
- `--root ROOT`, `--profile {core,developer,project}`, `--json`.

### `git-preview.py`
**Что делает:** preview конкретных路径 из local bare Git-store без применения.
- `--repo REPO`, `--commit COMMIT`, `--base-commit` / `--use-receipt`, `--target TARGET`, `--path PATH` / `--root ROOT`, `--local LOCAL`, `--use-local-policy`, `--max-file-bytes MAX_FILE_BYTES`.

### `release_manifest.py`
**Что делает:** вывести derived release-manifest из одного Git-commit (snapshot, sizes, SHA-256).
- `--root ROOT`, `--commit COMMIT`, `--out OUT`, `--json`, `--max-file-bytes MAX_FILE_BYTES`.

### `release-repo-check.py`
**Что делает:** проверить, видны ли essential harness-файлы в release-репо (рид-only diagnostic).
- `--root ROOT`.

---

## 4. Управление скилами

### `add_skill.py`
**Что делает:** установить локальный скин в канон + документация + registry + sync + validators.
- `--root ROOT`, `--name NAME` (repeatable), `--all`, `--from {codex,qoder,qwen,kilo,agents}`, `--force`, `--allow-absolute-paths`, `--dry-run`, `--yes`, `--no-sync`, `--no-validate`, `--json`.

### `scan_local_skills.py`
**Что делает:** найти скилы вне baseline-пакета.
- `--root ROOT`, `--baseline BASELINE` (default `kit-manifest.json`), `--write-baseline`, `--include-generated`, `--json`.

### `remove_skill.py`
**Что делает:** удалить скин из канона, mirrors и документации (с backup, индексами, router, checks).
- `--root ROOT`, `--name NAME`, `--dry-run`, `--yes`, `--force`, `--no-backup`, `--no-sync`, `--no-validate`, `--json`.

### `create_skill.py`
**Что делает:** создать каркас нового скила и зарегистрировать.
- `--root ROOT`, `--name NAME`, `--title TITLE`, `--description DESCRIPTION`, `--parent PARENT`, `--kind {leaf,orchestrator}`, `--with-test`, `--force`, `--dry-run`, `--no-validate`, `--json`.

### `audit_skill.py`
**Что делает:** проверить один/все скилы на соответствие проектным правилам (структура, frontmatter, README, skill.json, scripts, tests, docs, индексы, registry, router, зависимости).
- `--root ROOT`, `--name NAME` (repeatable), `--all`, `--strict`, `--json`.

### `skill-creator / scaffold_skill.py`
**Что делает:** сгенерировать портативный 17-agent-пакет Agent Skill.
- `name` (positional), `--output-dir`, `--description`, `--archetype {atomic,script,multi-agent,user-invoked}`, `--invocation {model,user}`, `--license`, `--author`, `--version`, `--compatibility`, `--resources RESOURCES`, `--no-openai-yaml`, `--display-name`, `--short-description`, `--mirror-project`, `--mirror-targets`, `--force`, `--json`.

### `skill-creator / package_and_verify.py`
**Что делает:** проверить портативность 17 агентов и упаковать `.skill`.
- `skill_dir` (positional), `--output-dir`, `--verify-only`, `--auditor-script AUDITOR_SCRIPT`, `--no-external-auditor`, `--json`.

### `skill-auditor / static_audit.py`
**Что делает:** детерминированный статический пред-аудит для Skill/.skill/AGENTS.md/.mdc/profile/fleet.
- `target` (positional), `--target-type {auto,skill,agents-md,cursor-mdc,agent-profile,fleet}`, `--output/-o OUTPUT`, `--fail-on-critical`, `--self-audit-safe`.
- **Коды:** 0/1/2 (см. help).

### `skill-auditor / eval_runner.py`
**Что делает:** A/B & runtime benchmark для skill-auditor.
**Синтаксис:** `eval_runner.py [-h] {prepare,score} ...`
- `prepare`: `--evals EVALS`, `--workspace WORKSPACE`, `--applicability APPLICABILITY`.
- `score`: `--judgments JUDGMENTS`, `--output/-o`, `--markdown-out`, `--lang`, `--fail-on-regression`.
- **Коды:** 0/1/2.

### `skill-auditor / score_aggregator.py`
**Что делает:** слить static + findings в итоговый score, ROI-ranking, SARIF.
- `--static STATIC`, `--findings FINDINGS [FINDINGS ...]`, `--output/-o`, `--markdown-out`, `--sarif-out`, `--compare-prev`, `--config`, `--lang`, `--policy {strict,balanced,permissive}`, `--fail-on-gate`.

### `skill-auditor / self_test.py`
**Что делает:** запустить regression self-tests для skill-auditor. (без опций, кроме `-h`).

---

## 5. MCP-аудит, миграция, документы, improvement

### `mcp-audit / verify_mcp_views.py`
**Что делает:** проверить MCP-наборы серверов во всех views (drift, orphans, state, раскрытие токенов).
- `--canonical CANONICAL`, `--kilo KILO`, `--expanded EXPANDED` (repeatable), `--qwen QWEN`, `--opencode OPENCODE`, `--codex-toml CODEX_TOML`.

### `mcp-audit / scan-usage.py`
**Что делает:** сканировать использование MCP.
- `--root ROOT`.

### `migration-review / review_migration.py`
**Что делает:** после миграции проверить локальные скилы, правила, MCP и предложить безопасные шаги.
- `--root ROOT`, `--json`, `--interactive`, `--report-only`, `--apply`, `--apply-skills`, `--apply-rules`, `--apply-mcp`, `--rm-backup`, `--yes`.

### `doc-mcp / doc_mcp.py`
**Что делает:** работа с документацией MCP.
- `--list`, `--move`, `--audit`, `--policy-root POLICY_ROOT`.

### `doc-script / doc_script.py`
**Что делает:** работа с документацией скриптов (скелеты, аудит, классификация).
- `--script SCRIPT`, `-f/--force/--overwrite`, `--all`, `--audit`, `--list`, `--inventory` (entrypoint/library/test), `--policy-root POLICY_ROOT`.

### `doc-skill / doc_skill.py`
**Что делает:** README-документация скилов.
- `--skill SKILL`, `--audit`, `--list`, `--policy-root POLICY_ROOT`.

### `improvement / runtime_registration.py`
**Что делает:** проверить canonical-файлы и runtime-registration отдельно.
- `--component COMPONENT`, `--root ROOT`, `--config CONFIG`.

### `improvement / validate_structure.py`
**Что делает:** проверить раскладку каталогов harness.
- `--root ROOT`, `--json`, `--warn-only`, `--junk`, `--fail-on-junk`, `--require-policy`.

### `improvement / validate_rules.py`
**Что делает:** статически проверить правила и скилы (без claims о runtime).
- `--rules-dir RULES_DIR`, `--skills-dir SKILLS_DIR`.

### `improvement / validate_skills.py`
**Что делает:** проверить harness-скилы.
- `--skills-root SKILLS_ROOT`, `--warn-only`, `--json`, `--policy-root POLICY_ROOT`.

### `improvement / validate_docs.py`
**Что делает:** проверить component-документы.
- `--root ROOT`, `--warn-only`, `--json`.

### `improvement / validate_registry.py`
**Что делает:** проверить малый schema component-registry.
- positional `registry`.

---

## 6. project-setup / onboard

### `onboard-project.py`
**Что делает:** onboard-мигированного проекта (container, MySQL, порты, git-exclude, индексы).
- `--root ROOT`, `--project-name PROJECT_NAME`, `--php-container PHP_CONTAINER`, `--mysql {keep,disable,set}`, `--mysql-database`, `--mysql-port`, `--serena-port`, `--web-port`, `--jdoc-repo JDOC_REPO`, `--add-harness-to-git`, `--include-harness`, `--exclude-docs` / `--include-docs`, `--add-docs-to-git`, `--skip-indexes`, `--reindex-project-docs`, `--check`, `--yes`.

---

## 7. task-router (втекст задач)

### task-intake
- **`intake_state.py`** — компактный preflight intake (читает задачу, branch, identity, freshness). `--path PATH`, `--root ROOT`, `--task TASK`.
- **`intake_orchestrator.py`** — детерминированная часть intake (state + Jira-export + tracker + diff). `--root ROOT`, `--task TASK`, `--force`, `--skip-export`, `--skip-diff`, `--no-network`.
- **`intake_analysis.py`** — детерминированный каркас diff-анализа. `--root ROOT`, `--task TASK`, `--output OUTPUT`.
- **`doc_sections.py`** — применить doc-sections из JSON. `--root ROOT`, `--task TASK`, `--input INPUT`, `--apply`, `--finalize`, `--no-network`.

### task-spec (`task_spec.py`)
**Что делает:** работа со спецификацией задачи.
**Синтаксис:** `task_spec.py [-h] [--root ROOT] {start,add,attach,show,finalize,current,use,list} ...`
- `start`: `--title`, `--slug`.
- `add`: `--text`, `--stdin`, `--kind {remark,bug,requirement,decision,question}`, `--id`.
- `attach`: `--path`, `--caption`, `--id`.
- `show`: `--id`. `current`: —. `use`: `--id`. `list`: —. `finalize`: `--file`, `--title`, `--id`.

### analytics (`task-analytics.py`)
**Что делает:** аналитика задач (привязка, атрибуция, отчёт).
**Синтаксис:** `task-analytics.py [-h] [--db DB] [--root ROOT] {scan,report,attribute,anchor,assign,detach,backfill-anchors,validate} ...`
- `scan`: `--task`, `--session`, `--latest`, `--after`, `--before`, `--dry-run`, `--allow-partial`, `--idle-minutes`.
- `report`: `--task`, `--append-history`, `--stage`.
- `attribute`: `--task`, `--session`, `--latest`, `--after`, `--before`, `--dry-run`, `--allow-partial`, `--idle-minutes`.
- `anchor`: `--task`, `--branch`, `--quote`, `--created-at`. `assign`: `--session`, `--task`, `--branch`, `--force`. `detach`: `--session`, `--task`, `--reason`. `backfill-anchors`, `validate`: —.

### testing-router / test-task
**Что делает:** прогоны тестов задачи, gates, отчёты.
- **`task-test.sh`** — прогон браузерных тестов + артефакты + verdict. `--task`, `--run-dir`, `--group`, `--filter`, `--grep`, `--env`, `--profile`, `--level`, `--phase`, `--require-browser`, `--require-db`, `--rm`, `--json`, `--html`, `--xml`, `--output`, `--exit-code`, `--skip-neighbors`, `--steps`, `--stage-num`, `--run-dir`.
- **`gates.py`** — гейты. `--json`, `--skip-static`; positional `task`.
- **`doctor.py`** — диагностика. `--task`, `--json`, `--require-browser`, `--require-db`.
- **`preflight.sh`** — preflight проверки. `--level`, `--skip-prod`, `--skip-check`, `--skip-static`, `--force-prod`.
- **`run-phpunit.py`** — запуск PHPUnit. `--task`, `--run-dir`, `--profile {task,changed,full,baseline}`.
- **`check-ac-matrix.py`** — матрица acceptance-критериев. `--task`, `--run-dir`, `--phase {source,result}`.
- **`check-selectors.py`** — проверка селекторов. `--task` (all/пустое — весь repo).
- **`db-isolation.py`** — изоляция БД. `--task`, `--run-dir`, `--phase {before,after}`.
- **`collect-data-test.py`** — собрать data-test map (без argparse; читает SCAN_DIRS, пишет `data-test.tsv`).
- **`collect-shots.py`** — собрать screenshots (без argparse; требует корень репо).
- **`compare-runs.py`** — сравнить прогоны. `--task`, `--run-dir`.
- **`llm-review.py`** — LLM-review. `--task`, `--run-dir`.
- **`make-report.py`** — сделать отчёт. `--task`, `--run-dir`.
- **`make-verdict.py`** — verdict. `--task`, `--group`, `--run-dir`, `--exit-code`.
- **`record-history.py`** — записать историю. `--task`, `--run-dir`.
- **`resolve-neighbors.py`** — соседние задачи. `--task`, `--output OUTPUT`.
- **`qa-lint.py`** — QA-лиnting. `--task`, `--run-dir`, `--with-support`.
- **`qa-manifest.py`** — QA-manifest. `--task`, `--group`, `--output`, `--check CHECK`.
- **`static-on-diff.py`** — статика по строкам патча. `--level LEVEL` (8/9), `--eslint-ci`, `--eslint-strict-repo`, `--no-php`, `--no-eslint`, `--slack SLACK`; positional `task`.
- **`branch-audit.py`** — аудит ветки. positional `task`.
- **`build-testanalyze.py`** — собрать корпуз testanalyze. `--all`, `--staged-only`, `--multi-stage`, `--task`, `--with-diffs`, `--full-diff`, `--refresh-jira`, `--limit`, `--skip-readme`.
- **`cleanup-test-runs.py`** — удалить старые прогоны. `--root`, `--days`, `--task`, `--include-files`, `--apply`, `--ignore-reports`, `--json`, `--now NOW`.
- **`migrate-task-tests.py`** — миграция тестов задачи. `--dry-run`.
- **`new-task-test.py`** — новый Cest-тест задачи. `task`, `name` (positional), `--title`, `--force`.

### reporting / task-change-report
- **`generate_report.py`** — generate change-report (⚠ имеет SyntaxError: f-string с backslash — скрипт не запускается, нужен фикс).
- **`workflow_contract.py`** — рид-only workflow-preflight. `--context CONTEXT`, `--project-root PROJECT_ROOT`.

---

## 8. documentation-router

### `task-doc / jsondoc.py`
**Что делает:** работа с JSON-документами задач (apply/render/search/validate/ingest).
**Синтаксис:** `jsondoc.py [-h] --root ROOT [--docs-dir DOCS_DIR] {selftest,execution,baseline,get,search,related,apply,render,validate,batch,ingest-tracker,ingest-git,recover} ...`
- `get`: `--task`, `--arch`, `--keys`, `--select POINTERS`, `--limit`, `--record-id`.
- `search`: `--kind {task,architecture}`, `--text`, `--tag`, `--tag-mode {all,any}`, `--file`, `--release`, `--branch`, `--tasks`, `--limit`.
- `related`: `--profile {discovery-v1,legacy-v1}`, `--task`, `--arch`, `--limit`.
- `apply`: `--task`, `--arch`, `--input INPUT`, `--dry-run`.
- `render`: `--task`, `--arch`. `validate`: `--task`, `--arch`, `--all`, `--links`.
- `batch`: `--input INPUT`, `--dry-run`. `baseline`: `--run RUN`.
- `execution`: `{next,verify-stage}`. `selftest`: `--stage`, `--through`, `--suite`, `--run RUN`.
- `ingest-tracker`: `--task`, `--input INPUT`. `ingest-git`: `--task`. `recover`: `--task`, `--arch`.

### project-doc
- **`check-links.py`** — проверить ссылки в документах. `--root`, `--only ONLY`, `--skip SKIP`, `--skip-historical`, `--quiet`.
- **`check-doc-text.py`** — проверить текст доков. `--root`, `--task`, `--file`, `--baseline`, `--write-baseline`.
- **`task-identity.py`** — проверить согласованность identity-файлов задачи. `--all`, `--tsv`; positional `task`. **Коды:** 0 ok, 2 mismatch, 4 не найдена.

---

## 9. exhaustive-research / codeprism / иные скилы

### `exhaustive-research / check_gates.py`
**Что делает:** проверить гейты research-прогона.
- positional `target` (research/<task-id>), `--init-v6 DIR` (создать v6-дерево), `--force` (перезаписать непустой init-target).

### `codeprism / codeprism_serve.py`
**Что делает:** serve проект CodePrism.
- positional `project`, `--transport {stdio,http}`, `--port PORT`.

### `codegraph / codegraph-ui.sh`
**Что делает:** UI codegraph.
- `--open` / `--no-open`, `--port PORT`, `--read-only`.

### `graphiti / graphiti-stack.sh`
**Что делает:** lifecycle docker-стека graphiti.
- `up|down|restart|status|logs|verify`, `--env-file`, `--force-recreate`, `--max-time`, `--tail`.

### `phpstan-mcp / phpstan-task.sh`
**Что делает:** phpstan для задачи (передаёт `--level`, `--error-format`, git-flagы).

### `copy-project / copy-project.sh`
**Что делает:** копировать проект (git-based).
- `--source DIR`, `--target DIR`, `--force`, `--include-tracked-changes`, `--report FILE`.

---

## 10. todone (трекер)

**Что делает:** локальный трекер записей/очередей. **Три точки входа + алиасы**, общий контракт вывода (одна строка на объект, срез `--json/--fields/--quiet/--limit`, ошибка — одна строка из 4 частей).
**Общие флаги (все точки входа):** `--root` (корень проекта), `--queue` (алиас очереди), `--json`, `--fields` (запятыми), `--quiet` (только ошибки), `--limit` (сколько строк), `--by` (кто правит).

**Входные точки** (тонкие обёртки, состав команд в `tdcore/*_cli.py`; вызвать как модуль):
- **`ttask`** → `task_cli.py`: `new`, `show`, `pack`, … (запись как работа).
- **`tqueue`** → `queue_cli.py`: `find`, `init`, `list`, … (очередь как порядок).
- **`tcheck`** → `check_cli.py`: `doctor`, `validate`, … (контроль, типы, потоки, роли).
- **`todone-aggregate.py`** — алиас `tcheck aggregate`.
- **`todone-autodoc.py`** — алиас `tcheck autodoc`.

**Пример задачи (ttask):**
```
python3 -m tdcore.task_cli new --title "Задача" --type bug --status draft --priority 3
```
**Пример контроля (tcheck):**
```
python3 -m tdcore.check_cli doctor --all --strict
```
> Примечание: точки входа используют relative-import — вызовите как модуль из пакета `tdcore` (не напрямую `python3 cli.py`).

---

## 11. Shell-скрипты и утилиты

### `.cursor/mcp-stack`
- **`restore.sh <archive.tar.gz> [project-root] [--no-start]`** — восстановить mcp-стек из архива; `--no-start` — только копия без systemd.
- **`verify.sh [project_root]`** — проверить mcp-стек (`--json`, `--now`, `--ui`, `--yes`, `--user`).
- **`add-codeprism.py --output-dir DIR project port`** — подготовить CodePrism unit (не устанавливать).

### `.doc/web/install.sh` и `.doc/web2/install.sh`
**Что делает:** установка web-panel.
- `--build`, `--check`, `--project`, `--root`, `--version`, `--help`.

### `.doc/web/bin/build-actions.py` (и web2)
**Что делает:** собрать/проверить panel action-registry (рид-only по скиллам).
- `--check` (validate actions.json + overlay), `--draft` (записать actions.draft.json).

### `.tools/scripts`
- **`multi-exec.sh`** — выполнить несколько команд/read. `--input FILE`, `--cmd "id=X :: cmd"`, `--read "id=X :: path [+offset] [limit]"`, `--mode {sequential,parallel}`, `--timeout SEC`, `--max-output BYTES`, `--truncate BYTES`.
- **`multi-search.sh`** — несколько поисков. `--root DIR`, `--pattern STR` (repeatable), `--include GLOB`, `--max-per-file N`, `--max-total N`, `--context N`, `--truncate N`, `--json`, `--no-heading`, `--no-ignore-vcs`, `--max-count`.
- **`php-docker.sh`** — helper для PHP-docker.

### `.tools/php85-scan`
- **`composer_matrix.py`** — матрица composer (lock). positional `lock`, `--json JSON`, `--md MD`.
- **`deprecation_summary.py`** — сумма deprecation из лога. positional `log`, `--json JSON`, `--top TOP`.
- **`fix_implicit_nullable.py`** — фикс implicit-nullable. `--report REPORT`, `--write`, `--root ROOT`.

### `testing-router / test-task` (shell)
- **`test-batch.sh`** — batch-прогон задач. `N [N ...] | --file tasks.txt`.
- **`disposable-db.sh`** — disposable-БД. `--no-data`, `--routines`, `--triggers`.

---

## 12. Кодовые возвраты

Общие по проекту:
- `0` — успех.
- `1` — ошибка аргументов / дрейф (`--check`) / несовпадение.
- `2` — critical blocker (gates, eval regression, static_audit critical, score_aggregator gate).
- `78` — `setup-workspace.py` failure (без retry/cleanup).
- task-identity: `0` ok, `2` mismatch, `4` не найдена.

---

## Заключение

Справочник покрывает **все CLI-точки входа проекта** (99 Python-скриптов + shell-оркестраторы). Ключевые точки:
- **Управление:** `harness_cli.py`, `harness_mirror.py`.
- **Синхронизация сред:** `sync-agent-views.sh` + `render_agent_views.py` + генераторы.
- **Перенос/экспорт:** `harness_transfer.py`, `export_kit.py`, `harness_wizard.py`.
- **Скилы:** add/remove/create/audit/scan/scaffold/package.
- **Задачи:** intake, task_spec, analytics, testing-router (task-test.sh, gates, doctor, …).
- **Документы:** jsondoc, check-links, task-identity.
- **Трекер:** todone (ttask/tqueue/tcheck).

**Примечания:**
- `generate_report.py` (task-change-report) содержит SyntaxError (f-string с backslash) — скрипт в настоящий момент не запускается.
- Скрипты `collect-data-test.py`, `collect-shots.py` — без argparse (запускаются напрямую с контекстом корня).
- `todone` — вызывать как модуль (`python3 -m tdcore.*`), direct-вызов падает на relative-import.

*Справочник сгенерирован по авторитетным `--help`-выводам каждого скрипта репозитория.*
