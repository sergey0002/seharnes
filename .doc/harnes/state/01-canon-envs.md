# Канон, среды, синхронизация и проверки

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ../doc_rules.md, ../dirtree.md]
tags: [harness, canon, sync, parity, registry]
-->

---

## Суть

Канон харнеса распределён между `.cursor/`, `.agents/skills/` и корневым `AGENTS.md`. Среды получают представления через `sync-agent-views.sh`. Управляемые зеркала руками не правятся: синхронизация удаляет лишние файлы. Соответствие проверяет `verify_parity.py` с freshness-гейтом по `canon_hash`. Правки харнеса идут через `harness-improvement`.

---

## 1. Канонические корни (Single Source of Truth)

Канонические пути, назначение каталогов `.cursor/`, `.agents/` и `.tools/`, размещение
скриптов и правила для каждой среды задаёт [dirtree.md](../dirtree.md). Машинная карта
для документации: [canon-paths.yaml](./canon-paths.yaml); скрипт синхронизации задаёт
пути в коде и карту не читает.

### Границы харнеса

Харнес это только агентская конфигурация: правила, скилы, скрипты скилов и канона,
MCP-конфиги и их серверы. Каталог `.doc/` это документация проекта, в харнес он не
входит. Состав каталогов и запреты: [dirtree.md](../dirtree.md), разделы 1-5.

- Документация не индексируется картой харнеса: скан читает только `.cursor/`,
  `.codex/`, `.kilo/`, `.agents/`, `.dsh/`.
- Связи из скилов и правил на пути вне этих префиксов отбрасываются при разборе и
  при повторном скане, поэтому правки документации не меняют граф.
- Скилы, правила и скрипты харнеса работают без документации. Документация может
  ссылаться на харнес, но харнес на неё не опирается.

Поведение зеркала описано в [19-harness-mirror.md](./19-harness-mirror.md).

---

## 2. Зеркала сред

| Среда | Каталог | Особенность |
|---|---|---|
| Cursor | `.cursor/` (канон) | `${workspaceFolder}`, `envFile`, прямое чтение |
| Codex CLI | `.codex/` | rules как `.md` без Cursor-frontmatter; `rules-index.md` содержит обязательные правила, on-demand правила и сгенерированную glob-таблицу для условных правил; `go-task.ps1` / `task-diff.ps1` форвардят к канону |
| Kilo | `.kilo/` | нативный `kilo.jsonc`; always-правила находятся в `instructions`, остальные в `.kilo/rules-index.md`; условные правила также перечислены в сгенерированной glob-таблице, поскольку Kilo не прикрепляет их по пути автоматически |
| Antigravity | `.agents/` | `rules`, `skills`, `mcp_config.json` с раскрытыми путями; legacy `.antigravity/` и `.gemini/` не генерируются |
| Agents | `.agents/` | универсальные рантаймы, полный набор |
| DeepSeek Harness | `.dsh/project.patch.yml`, `DSH-RULES.md`, `.dsh/skills/dsh-router/`, `.dsh/adapters/`, `.dsh/scripts/`, `.dsh/models.overlay.json` | генерируются MCP (15 `mcp-client`), inline always и on-demand индекс; conditional-правила получают generated glob-блок; скил-маршрутизатор `dsh-router` (ранг 100, вне реестра канона); адаптеры shell/mcp-names/models/digest; шимы `.dsh/scripts/run-ps1.sh` и `.dsh/scripts/smoke.sh`; модели: одна `deepseek-account/deepseek-flash`, `llm-pi-ai` выключен |

Генераторы живут в `.agents/skills/harness-router/children/environment-sync/scripts/`:

- `generate-agent-configs.py` - skills/rules + Kilo remote + single wrap + permissions fragment.
- `generate-mcp-config.py` - MCP с раскрытием `${workspaceFolder}` для Antigravity/Gemini.
- `sync-agent-views.sh` - оркестратор: генераторы, копии, LF-нормализация, parity, freshness-гейт.

Сгенерированные артефакты лежат в `.doc/skil_data/`:

- `.doc/skil_data/harness-router/antigravity_mcp_config.json` - нативный MCP-конфиг для Antigravity/Gemini.
- `.doc/skil_data/harness-core/antigravity_mcp_config.windows-wsl.json` - конфиг для Windows-процесса Antigravity через `wsl.exe`.
- `.doc/skil_data/harness-core/parity-report.json` - отчет паритета с `generated_at` и `canon_hash`.
- `.doc/skil_data/harness-core/kit-manifest.json` - манифест kit.
- `.doc/skil_data/harness-core/README.md` - навигация по артефактам.

План отчетной цепочки send-to-git / task-doc / task-change-report / jira-report:
`.agents/skills/harness-router/children/environment-sync/references/report-workflow-plan.md`.
Операционное описание синка: `.agents/skills/harness-router/children/environment-sync/README.md`.

---

## 3. Parity и freshness

Проверка:

```bash
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py \
 --canonical .agents/skills \
 --view .codex/skills --view .agents/skills \
 --manifest .doc/skil_data/harness-core/parity-report.json
```

Правила:

- Сравнение по LF-нормализованным байтам. Окончания строк не считаются дрейфом (P1).
- Правила сравниваются по stem и по телу без Cursor-frontmatter: в каноне `.mdc`, в Codex и Kilo `.md`.
- MCP сверяется отдельным скриптом `verify_mcp_views.py`: набор имен, флаги enabled/disabled, отсутствие нераскрытых `${...}`. Команды запуска не сравниваются, они у адаптеров разные.
- Классификация правил одна для всех сред: `environment-sync/scripts/rule_model.py` выдаёт `always`, `conditional`, `agent_requested` или `manual`, причём `alwaysApply: true` важнее `globs`. `gate: true` требует inline-инжект; `attach: glob` требует path-trigger или generated glob-блок для сред без поддержки globs. `verify_rule_triggers.py` проверяет генерацию, `harness_mirror.py visibility` проверяет фактическую матрицу. Синк падает при нарушении контракта.
- Отчет содержит `generated_at` (UTC) и `canon_hash` (sha256 манифеста канона).
- `--check` падает, если отчет отсутствует, не `passed` или устарел. Внутри синка проверка идет сразу после записи и потому тавтологична; как внешний гейт (pre-commit, CI) она ловит "канон изменен, синк не запускался".
- Parity проверяет файлы, не runtime-регистрацию. Runtime отдельно дает `runtime_registration.py`.

---

## 4. LF-политика

Текстовые файлы харнеса (`.md`, `.mdc`, `.json`, `.jsonc`, `.py`, `.ps1`, `.sh`, `.js`)
нормализуются в LF при генерации и копировании. Секреты (`mcp.env`) копируются
с той же нормализацией окончаний, значения не меняются.

---

## 5. Секреты

Вне git: `mcp.env` (Cursor/Codex), `.doc/skil_data/jira/config.env`, `.doc/.bitbucket/config.env`,
живой SG-токен в `mcp.json`. В репозиторий только `*.example` / `*.dist`.
Каталоги харнеса и `.doc/` исключены через локальный `.git/info/exclude`, не `.gitignore`.

`${env:VAR}` в Kilo-конфиг не инлайнится. Значения подставляет в рантайме
`run-with-mcp-env.sh` из `mcp.env`. Детали: [04-mcp.md](./04-mcp.md).

---

## 6. Таймауты

Зафиксированы в `prepare-plan/ADAPTERS.local.md`, раздел Timeouts (P6):

| Операция | Cold | Warm |
|---|---|---|
| MCP вызов | 90s | 60s |
| `git log -L` на диапазон | 120s | 60s |
| export-task, find-related-tasks | 120s | 60s |
| build-index | 180s | 90s |
| plan verify | 120s | 60s |
| plan verify `--require-syntax` | 180s | 180s |

Превышение - тир `timeout` + Grep-компенсация, не слепой повтор.

---

## 7. Реестр и валидаторы

Реестр: `.agents/skills/harness-router/children/improvement/scripts/component_registry.json`.
88 компонентов в реестре; состав проверяет `validate_registry.py`. У оркестраторов поле `skill_dependencies`
(test-task, browser-verify, prepare-plan, harness-improvement).

Проверки:

```bash
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py --rules-dir .cursor/rules --skills-dir .agents/skills
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py --canonical .agents/skills --view .codex/skills --view .agents/skills --rules-canonical .cursor/rules --rules-view .codex/rules --rules-view .kilo/rules --rules-view .agents/rules
python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py --canonical .cursor/mcp.json --kilo .kilo/kilo.jsonc --expanded .agents/mcp.json --codex-toml .codex/config.toml
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_rule_triggers.py --root .
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility --summary
python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
```

- `validate_registry.py` - состав реестра, существование зависимостей.
- `validate_rules.py` - ссылки на скилы/скрипты, триггеры, кросс-ссылки как info,
настоящие циклы как warning. Delta `added/removed/unchanged` против
`.cursor/.validate-rules-last.json` (P12).
- `runtime_registration.py` - раздельно `file_parity` и `runtime_registration`.
Наличие файла не доказывает доступность в рантайме. `harness_mirror.py visibility` отдельно
проверяет инжект правил, glob-trigger и индексы сред.

Факт 2026-09-30: registry passed, rules passed 14/22 issues 23 info, parity passed
3 вью.

---

## 8. Сводная матрица: компонент - среда - артефакт

| Компонент | Канон | Зеркала (авто) | Основной артефакт |
|---|---|---|---|
| Скилы (28) | `.agents/skills/` | `.codex` (копия для Codex); Kilo читает `.agents` | SKILL.md плюс scripts внутри скила |
| Рулесы (37) | `.cursor/rules/*.mdc` | `.md` в Codex и Kilo; `.mdc` в `.agents`, Antigravity ждет `.md` с `trigger` (M9) | триггеры плюс ограничения |
| MCP (20, из них 16 включённых) | `.cursor/mcp.json` плюс mcp.env | mcp.json / mcp_config.json / config.toml / kilo.jsonc | пути раскрыты, секреты из env |
| Скрипты MCP и инструментов | `scripts/` скила-владельца | копия вместе с деревом скилов | лаунчеры и обёртки |
| Системные утилиты | `.tools/scripts/` | не зеркалируются | общие утилиты и пакетные обёртки |
| Документация (docscripts 19) | `.agents/skills/documentation-router/children/project-doc/scripts/` | не зеркалируются - общие | `_map/*.tsv`, tasks/index.md |
| QA-скрипты (28) | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/` | не зеркалируются - общие | test-runs, вердикты G0-G13 |
| Генератор сред | `.doc/skil_data/harness-core/` | - | parity-report.json |
| SG-стек | `sourcegraph-local/` | один на машину | индекс репозиториев `:7080` |

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Рулесы](./03-rules.md) - состав правил канона
- [MCP](./04-mcp.md) - серверы и Kilo-адаптация
- [Правила документации](../doc_rules.md) - стандарт `.doc/`
- [Добавление среды нового редактора](../add-editor-environment.md) - точки изменения, opencode, merge и проверки
- `.agents/skills/harness-router/children/improvement/SKILL.md` - порядок правки харнеса

---

## Известные проблемы и ограничения

- Зеркала - реальные копии. Рассинхрон возможен до следующего синка. Канон всегда правее зеркала.
- `verify_parity.py` не проверяет runtime-регистрацию скила в IDE. Для этого `runtime_registration.py`.
- Kilo remote sourcegraph требует доступа к `127.0.0.1:7080` с машины Kilo-рантайма, иначе тир red с Grep-компенсацией.

---

## История изменений

- 2026-11-11: генераторы указаны по фактическому пути в `environment-sync/scripts`; нативный MCP-артефакт Antigravity перенесён в `harness-router`, ссылка на несуществующий `.doc/synh_harnes` заменена.
- 2026-11-11: раскладка каталогов и причины выбора корней перенесены в [dirtree.md](../dirtree.md); здесь остались синхронизация, parity и границы харнеса.
- 2026-11-09: уточнены источники канона, удаление лишних файлов зеркал и использование карты путей.
- 2026-10-01: вынесено из `readmy.md` в `.doc/harnes/`
- 2026-10-02: аудит против кода: реестр 28 (22 скила + 6 rule-only), таймауты и freshness-гейт подтверждены
- 2026-10-19: паритет расширен на rules, добавлена MCP-проверка `verify_mcp_views.py`, гейт свежести стал режимом `--check`, добавлены `test_sync_views.py` и очистка устаревших артефактов; реестр исправлен на 29 (22 скила + 7 rule-only)
- 2026-10-19: добавлен импорт канона в DeepSeek Harness (`generate-dsh-config.py`: `.dsh/project.patch.yml` и `DSH-RULES.md`), шаг встроен в синк
- 2026-10-20: расширен слой DSH: `models.overlay.json` (маршрутизация моделей через генератор, функция `load_overlay` + рекурсивный `render_entry`), скил `.dsh/skills/dsh-router/`, адаптеры `.dsh/adapters/` (shell/mcp-names/models/prepare-plan-digest). Факт оболочки (устарело, см. запись ниже): `pwsh`/`node` в WSL отсутствуют, PowerShell-скрипты идут через `powershell.exe` + UNC. План workflow: `plan/07-dsh-final.md`, скрипты/тесты: `plan/06b-dsh-scripts-and-testing.md`, H-отчёт: `h-test-report.md`
- 2026-10-30: MCP-стек на systemd, graphify/CBM по HTTP, скриптов 20; детали в [15-mcp-stack.md](./15-mcp-stack.md)
- 2026-10-29: `sourcegraph` отключен в каноне, маршрут переведен на graphify; DSH 14 mcp-client
- 2026-10-31: добавлен `harness-mirror` (зеркало харнеса в JSON, формат v2.1), реестр 32 (24 скила + 8 rule-only).
- 2026-11-01: `.cursor/mcp.json`, `alwaysAllow` для serena приведён к реальному набору на LSP-бэкенде (убран `get_type_hierarchy`, добавлены `find_referencing_symbols`, `find_declaration`, `get_diagnostics_for_file`); синк и гейты зелёные
- 2026-10-30: добавлен `business-analyst` (23 скила), `business-rules` (17 рулесов), реестр 31 (23 скила + 8 rule-only).
- 2026-10-29: factual audit: рулесов 16 (добавлен `cbm-index-before-push`), реестр 30 (22 скила + 8 rule-only), MCP 18 (15 включённых, добавлен `graphify`), скриптов канона 18, docscripts 19, DSH-патч 15 mcp-client. Детали graphify: [04-mcp.md](./04-mcp.md)
- 2026-10-20: аудит DSH исправил факты оболочки: `node` в WSL есть (v24.17.0), `pwsh` не в PATH, поставлен портативный pwsh 7.4.6 в `~/.local/pwsh`, PowerShell идёт через `.dsh/scripts/run-ps1.sh` (gototask 6 с вместо больше 180 с через `powershell.exe` + UNC). MCP-клиентов в патче 14 (добавлены `xmlriver`, `xmlriver-ws`). Генератор получил `--no-llm` и `--no-model-selection`, патч воспроизводим побайтно. Проверка: `.dsh/scripts/smoke.sh`. Отчёт: deepseek_harnes/06-аудит.md
- 2026-11-01: добавлена карта `mcp.mdc` и правила `mcp-*`, канон правил 36, реестр 54 (26 скилов + 28 rule-only)
- 2026-11-01: канон скриптов 22, добавлен `jdocmunch-mcp.sh` (перенос из kit `.dsh/scripts`)
- 2026-11-02: счётчик скилов в дереве канона приведён к факту: 25
- 2026-11-05: Kilo-адаптер перестал инжектить все 38 правил: `generate-agent-configs.py` читает `alwaysApply` из `.mdc`, в `instructions` попадают 7 всегда-правил, остальные 31 идут в `.kilo/rules-index.md`; стартовый промпт сократился примерно на 43k токенов, поведение совпало с Cursor agent-requested
- 2026-11-05: классификация правил вынесена в общий `rule_model.py`; Qoder, Qwen, Antigravity, DSH и Kilo используют один порядок `always` > `globs` > `description`; добавлен `verify_rule_triggers.py` и шаг `rule-triggers` в синке; исправлен блочный `globs` у Antigravity
- 2026-11-05: Codex получил генерируемый `.codex/rules-index.md` и ссылку в `.codex/AGENTS.md`, поэтому обязательные и on-demand правила находятся без чтения всех 38 файлов
- 2026-11-09: добавлены inline-гейты, generated glob-блоки для Kilo/Codex/DSH и проверка видимости в синке и harness mirror; правило `gates.mdc` зарегистрировано как компонент
