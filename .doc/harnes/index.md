# Харнес агента - точка входа

<!-- meta
type: index
status: actual
updated: 2026-11-11
related: [doc_rules.md, ./dirtree.md, ./state/01-canon-envs.md, ./plan/deepseek.md]
tags: [harness, index]
-->

---

## Суть

Документация харнеса разделена по владельцам. `state/` описывает состояние,
устройство и workflow. README внутри скила описывает его назначение;
`docs/scripts/` и `docs/mcp/` внутри скила содержат документы его компонентов.
`plan/` описывает еще не выполненные изменения:
roadmap и предложения с проверенными по коду статусами (для внедрения).
Раскладка каталогов и назначение компонентов описаны в [dirtree.md](./dirtree.md).
Канон харнеса - `.cursor/`, этот каталог - только документация. Документация не входит
в харнес: карта харнеса её не индексирует, связи на `.doc/` отбрасываются, скилы и
правила работают без неё. Границы: [state/01-canon-envs.md](./state/01-canon-envs.md),
раздел "Границы харнеса".
Аудиты-исходники `harnes_audit/` и `harnesaudit.md` удалены 2026-10-02,
все содержание разложено по двум разделам ниже.

> **AI:** точка входа. Для работы с харнесом иди в `state/`, для внедрения
> улучшений - в `plan/` (статусы проверены кодом 2026-10-02). Перед правкой
> харнеса - [harness-improvement](../../.agents/skills/harness-router/children/improvement/SKILL.md).

---

## Какой перенос выбрать

Три операции переносят разные объекты. Выбирай одну по результату:

| Нужно | Механизм | Точка входа |
|---|---|---|
| Обновить представления Cursor, Codex, Kilo и других сред в одном проекте | Синхронизация из канона | [environment-sync](../../.agents/skills/harness-router/children/environment-sync/README.md); архитектура: [state/13-agent-migration.md](./state/13-agent-migration.md) |
| Установить или обновить kit харнеса в другом проекте | Экспорт kit с backup и режимом переноса | [new-project](../../.agents/skills/harness-router/children/new-project/README.md); процедура: [state/14-project-migration.md](./state/14-project-migration.md) и [rebase_project.md](../rebase_project.md) |
| Скопировать Git-снимок приложения в новую папку без харнеса | Копирование проекта | [copy-project](../../.agents/skills/harness-router/children/copy-project/README.md) |

`migration-review` разбирает конфликты после переноса kit; он не заменяет ни одну
из трёх операций.

---

## state/ - реальное состояние харнеса

| Документ | Тема |
|---|---|
| [state/01-canon-envs.md](./state/01-canon-envs.md) | Канон `.cursor/`, 6 представлений сред, синк, parity с freshness-гейтом, LF, секреты, таймауты, валидаторы |
| [state/02-skills.md](./state/02-skills.md) | Карта 20 корневых скилов и их детей, ссылки на карточки и канон, реестр и валидаторы |
| [state/03-rules.md](./state/03-rules.md) | Рулесы канона: `context-router`, карта `mcp.mdc`, отдельные `mcp-*` на каждый MCP-сервер, `batch-calls`, `cbm-index-before-push`, `code-editing` |
| [state/04-mcp.md](./state/04-mcp.md) | 19 MCP-серверов (15 включённых), порядок, Kilo-адаптация, permissions fragment, общий HTTP-стек; раздел 3 - таблица ссылок на файлы серверов в `mcp/` |
| [state/05-scripts.md](./state/05-scripts.md) | Скрипты по владельцам: `.tools/scripts` для системных утилит, `scripts/` скилов для MCP и инструментов, документация в `{skill}/docs/scripts`, прочие контуры |
| [state/06-jsondoc.md](./state/06-jsondoc.md) | JSONdoc-движок: данные, команды, batch, теги, `business_logic`, интеграция со скилами |
| [state/07-workflows.md](./state/07-workflows.md) | Схемы взаимодействия: задача, документация, мета-контур, синк, отчеты |
| [state/08-plan-contour.md](./state/08-plan-contour.md) | Prepare-plan: фазы P0-P7, Tier 0-8, граф T-AC-R-S, гейт P7, пофазный разбор скила |
| [state/09-transfer.md](./state/09-transfer.md) | Устаревший подробный снимок переноса kit; текущая карта: [state/14-project-migration.md](./state/14-project-migration.md) |
| [state/11-dev-environment.md](./state/11-dev-environment.md) | Эксплуатация платформы: WSL2, профиль памяти, системные настройки; регламенты CBM, Sourcegraph и Serena перенесены в `mcp/` |
| [state/12-batch-calls.md](./state/12-batch-calls.md) | Пакетные вызовы: правило `batch-calls`, скрипты `multi-search` / `multi-exec`, экономика 8-18%, резервы S1-S5 (внедрено 2026-10-02) |
| [state/13-agent-migration.md](./state/13-agent-migration.md) | Синхронизация харнеса между средами: источники, генераторы, перезапись, исключения и проверки |
| [state/14-project-migration.md](./state/14-project-migration.md) | Миграция между проектами: профили Core/Developer/Project, что копируется, merge MCP, проверки после переноса |
| [state/15-mcp-stack.md](./state/15-mcp-stack.md) | Общий HTTP-стек MCP: systemd-юниты, порты, лимиты, add-project/verify, export/restore; детали серверов в `mcp/` |
| [state/16-task-analytics.md](./state/16-task-analytics.md) | Автономный анализ диалогов Kilo: `kilo.db` read-only, привязка к задачам, токены, время, артефакты в `.doc/tasks/{N}/dialogs` |
| [state/17-business-analyst.md](./state/17-business-analyst.md) | Историческое описание снятого с харнеса бизнес-анализа: сущности, реестр, карантин, версии правил |
| [state/18-task-text-and-report.md](./state/18-task-text-and-report.md) | Текстовый контракт задачи, business_changes в change-report, панель, активность Jira, релизы и покрытие условий |
| [state/19-harness-mirror.md](./state/19-harness-mirror.md) | Зеркало харнеса: область только харнес без `.doc/`, один JSON на файл, формат v2.1, граф, просмотрщик, зеркала и drift, тест в Kilo |
| [state/20-mcp-rules.md](./state/20-mcp-rules.md) | MCP-правила: карта и 21 правило серверов, структура, приоритет при расхождении, связи с доменными правилами, аудит и проверки |
| [state/21-harness-migration-2026-11-02.md](./state/21-harness-migration-2026-11-02.md) | Итог миграции: канон `.agents/skills`, правила MCP, DSH, 26 скилов, 36 правил, 180 документов, проверки |
| [state/22-panel-service.md](./state/22-panel-service.md) | Сервис `copytrust-tools`: панель и харнес-миррор на 8077, задания с AJAX, цены и провайдеры, стоимость, переносимость, проверки |
| [state/23-rule-transfer-2026-11-05.md](./state/23-rule-transfer-2026-11-05.md) | Перенос правил по средам: общий `rule_model.py`, четыре вида правила, индексы Kilo и Codex, гейт `verify_rule_triggers.py` |
| [state/24-mcp-duplicates-audit.md](./state/24-mcp-duplicates-audit.md) | Дубли MCP по процессам: 89 процессов и 6.5 ГБ, законные копии на проект, лишние копии на клиент, база на проект в codeprism и jdocmunch, план перевода на общий HTTP |
| [state/25-codeception-tools-move-2026-11-11.md](./state/25-codeception-tools-move-2026-11-11.md) | Перенос рабочей копии Codeception в `.tools/codeception`: симлинки задач, docker-маунт корня, хостовый запуск с `register_argc_argv`, список файлов и проверки |
| [state/26-tools.md](./state/26-tools.md) | Каталог `.tools`: окружения Docker, Codeception, MCP php-toolchain, сканеры и 14 системных утилит `.tools/scripts`, порты, границы и правила |
| [wsl-port-forwarding.md](./wsl-port-forwarding.md) | WSL port forwarding в nat режиме: проблема localhostForwarding, решение через netsh + Task Scheduler, полный список портов |
| [jsondoc.md](./jsondoc.md) | КАНОН: нормативная спецификация JSONdoc-движка (схемы, CLI, batch, миграция, стадии, этапы J00-J17). Выжимка state/06 |
| [testaudit.md](./testaudit.md) | КАНОН: воспроизводимое тестирование, раздел 9 ветки логики. Выжимка state/02 раздел 1a |
| [tests.md](./tests.md) | КАНОН QA: принципы, слои, чек-лист 13 категорий раздел 7, стандарт отчета раздел 8 |
| [dirtree.md](./dirtree.md) | КАНОН: раскладка каталогов харнеса, назначение `.agents/`, `.cursor/`, `.tools/`, размещение скриптов, архитектура скила |
| [skill-format.md](./skill-format.md) | КАНОН: структура скила, README, `skill.json`, дочерние скилы, правила путей и проверки |
| [component-docs.md](./component-docs.md) | КАНОН: как документируются скилы, скрипты и MCP, шаблоны и проверки |
| [component-install.md](./component-install.md) | КАНОН: установка нового скила, скрипта и MCP во все среды и проекты, чеклист и проверки |
| [add-editor-environment.md](./add-editor-environment.md) | Добавление среды нового редактора: точки изменения, opencode, merge при синке, локальные скилы и правила, проверки |
| [doc-script](../../.agents/skills/harness-router/children/doc-script/SKILL.md) | Документы существующих скриптов внутри скила-владельца |
| [doc-skill](../../.agents/skills/harness-router/children/doc-skill/SKILL.md) | README вместо отдельных карточек скилов |
| [doc-mcp](../../.agents/skills/harness-router/children/doc-mcp/SKILL.md) | Размещение и аудит документов MCP внутри скилов |
| [readmy_doc.md](./readmy_doc.md) | Гайд системы документирования (дерево файлов, циклы, скрипты, версии v4.0-v4.4) |
| [readmy.md](./readmy.md) | Legacy-указатель для старых ссылок: содержимое удалено, разделы ведут в `state/` и `dirtree.md` |
| [doc_readme.md](./doc_readme.md) | Старый операционный readme системы документации (дубль readmy_doc, перенос из .doc/) |

## mcp/ - документы по MCP-серверам

Один документ на сервер: конфигурация, инструменты, правила вызова и ограничения.
Документы включенных серверов лежат в `docs/mcp/` скила-владельца.
Правило ведения и шаблон: [mcp/README.md](./archive/mcp/README.md). Главная карта MCP:
[.cursor/rules/mcp.mdc](../../.cursor/rules/mcp.mdc). Общая картина и
порядок в задачах остаются в [state/04-mcp.md](./state/04-mcp.md).

| Сервер | Статус | Транспорт | Документ |
|---|---|---|---|
| `codebase-memory-mcp` | активен | HTTP 9131 | [codebase-memory-mcp](../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) |
| `codegraph` | активен | stdio | [codegraph](../../.agents/skills/codegraph/docs/mcp/codegraph.md) |
| `codeprism` | активен | stdio | [codeprism](../../.agents/skills/codeprism/docs/mcp/codeprism.md) |
| `serena` | активен | HTTP 9121, cms 9122 | [serena](../../.agents/skills/serena/docs/mcp/serena.md) |
| `mysql` | активен | stdio | [mysql](../../.agents/skills/mysql/docs/mcp/mysql.md) |
| `git` | активен | stdio | [git](../../.agents/skills/git/docs/mcp/git.md) |
| `jira-task` | активен | stdio, docker exec | [jira-task](../../.agents/skills/task-router/children/jira/docs/mcp/jira-task.md) |
| `context7` | активен | stdio | [context7](../../.agents/skills/context7/docs/mcp/context7.md) |
| `playwright` | активен | stdio | [playwright](../../.agents/skills/playwright/docs/mcp/playwright.md) |
| `phpstan-mcp` | активен | stdio | [phpstan-mcp](../../.agents/skills/phpstan-mcp/docs/mcp/phpstan-mcp.md) |
| `php-deps-mcp` | активен | stdio | [php-deps-mcp](../../.agents/skills/php-deps-mcp/docs/mcp/php-deps-mcp.md) |
| `semgrep` | активен | stdio | [semgrep](../../.agents/skills/semgrep/docs/mcp/semgrep.md) |
| `jdocmunch` | активен | stdio | [jdocmunch](../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md) |
| `graphiti` | активен | HTTP 8000 | [graphiti](../../.agents/skills/graphiti/docs/mcp/graphiti.md) |
| `sourcegraph` | отключен | HTTP 7080 | [sourcegraph](./archive/mcp/sourcegraph.md) |
| `xdebug` | отключен | stdio | [xdebug](./archive/mcp/xdebug.md) |
| `deepwiki` | отключен | stdio | [deepwiki](./archive/mcp/deepwiki.md) |
| `bitbucket-task` | отключен | stdio, docker exec | [bitbucket-task](./archive/mcp/bitbucket-task.md) |

Правила размещения MCP, папка `.cursor/rules/mcp/`, плоский вид Antigravity и
перенос правил-шагов в скилы: [rules-placement.md](./archive/mcp/rules-placement.md).

## Скилы: README внутри владельца

Каталог карточек `skills/` удален. Документация каждого скила находится в его
`README.md`, инструкции для агента в `SKILL.md`, файлы ресурсов в `skill.json`.

| Группа | Точка входа |
|---|---|
| Управление харнесом | [harness-router](../../.agents/skills/harness-router/README.md) |
| Управление задачами | [task-router](../../.agents/skills/task-router/README.md) |
| Документация | [documentation-router](../../.agents/skills/documentation-router/README.md) |
| Планирование | [prepare-plan](../../.agents/skills/prepare-plan/README.md) |
| Аудит плана | [audit-plan](../../.agents/skills/task-router/children/audit-plan/README.md) |
| Бизнес-анализ (снят с харнеса) | [state/17-business-analyst.md](./state/17-business-analyst.md) |
| Проверка площадки | [copytrust](../../.agents/skills/copytrust/README.md) |
| Исследование кода | [code](../../.agents/skills/code/README.md) |
| Исследование и выбор решения | [exhaustive-research-decision-v6](../../.agents/skills/exhaustive-research-decision-v6/README.md) |
| Аудит скиллов | [skill-auditor](../../.agents/skills/skill-auditor/README.md) |
| Создание скиллов | [skill-creator](../../.agents/skills/skill-creator/README.md) |
| Редактура русского текста | [neiroslop](../../.agents/skills/neiroslop/README.md) |

### Дочерние скилы пакета исследования

| Скил | Точка входа |
|---|---|
| briefing-intake | [briefing-intake](../../.agents/skills/exhaustive-research-decision-v6/children/briefing-intake/README.md) |
| criteria-synthesis | [criteria-synthesis](../../.agents/skills/exhaustive-research-decision-v6/children/criteria-synthesis/README.md) |
| cursor-state-handoff | [cursor-state-handoff](../../.agents/skills/exhaustive-research-decision-v6/children/cursor-state-handoff/README.md) |
| domain-safety-verification | [domain-safety-verification](../../.agents/skills/exhaustive-research-decision-v6/children/domain-safety-verification/README.md) |
| evidence-provenance | [evidence-provenance](../../.agents/skills/exhaustive-research-decision-v6/children/evidence-provenance/README.md) |
| existing-solution-scouting | [existing-solution-scouting](../../.agents/skills/exhaustive-research-decision-v6/children/existing-solution-scouting/README.md) |
| output-contract-and-format-compliance | [output-contract-and-format-compliance](../../.agents/skills/exhaustive-research-decision-v6/children/output-contract-and-format-compliance/README.md) |
| research-assignment | [research-assignment](../../.agents/skills/exhaustive-research-decision-v6/children/research-assignment/README.md) |
| triz-contradiction-resolution | [triz-contradiction-resolution](../../.agents/skills/exhaustive-research-decision-v6/children/triz-contradiction-resolution/README.md) |
| variant-feature-evaluation | [variant-feature-evaluation](../../.agents/skills/exhaustive-research-decision-v6/children/variant-feature-evaluation/README.md) |

### Группировка менеджеров

| Менеджер | Дочерние скилы |
|---|---|
| `harness-router` | harness-core, project-setup, new-project, copy-project, environment-sync, mcp-audit, mirror, index, improvement, add-skill, remove-skill, skill-authoring, migration-review, doc-script, doc-skill, doc-mcp |
| `task-router` | task-spec, task-core, gototask, task-diff, task-intake, task-code-review, git-task-blame, jira, analytics, kaiten, testing-router, reporting-router, audit-plan |
| `testing-router` | test-task, prepare-task-test, browser-verify |
| `documentation-router` | project-doc, doc-verify, task-doc |
| `reporting-router` | task-report, task-change-report |
| `copytrust` | platform-logs, platform-browser-test |
| `code` | bug-cause |

Состав дочерних скилов хранится в манифесте и таблице родительского роутера.

---

## deepseek-harness-* - документация харнеса DeepSeek Harness

Документация DSH переведена в `.doc/architecture/`: JSON-канон и
сгенерированный MD-вид. Правки через `jsondoc apply` плюс `render`.

| Документ | Тема |
|---|---|
| [deepseek-harness-index.md](./dsh/deepseek-harness-index.md) | Точка входа DSH-харнеса: устройство, установка, workflow, модели, скрипты |
| [deepseek-harness-01-ustroystvo.md](./dsh/deepseek-harness-01-ustroystvo.md) | Устройство: зоны, слои, что чем генерируется |
| [deepseek-harness-02-ustanovka.md](./dsh/deepseek-harness-02-ustanovka.md) | Установка: pwsh, генератор, patch, smoke |
| [deepseek-harness-03-workflow.md](./dsh/deepseek-harness-03-workflow.md) | Workflow: задача, план, аудит, тест, доки |
| [deepseek-harness-04-modeli.md](./dsh/deepseek-harness-04-modeli.md) | Модели: один маршрут, llm-pi-ai, субагенты |
| [deepseek-harness-05-skripty.md](./dsh/deepseek-harness-05-skripty.md) | Скрипты, MCP, имена инструментов |
| [deepseek-harness-07-scenarios.md](./dsh/deepseek-harness-07-scenarios.md) | Сценарии 2026-10-20: N-1..N-10, что осталось открытым |

## plan/ - не реализовано (статусы проверены кодом 2026-11-06)

| Документ | Тема |
|---|---|
| [plan/deepseek.md](./plan/deepseek.md) | Мастер-план: сканирование незнакомой кодовой базы, база знаний, аудит, тесты, модернизация, очередь и порядок P0-P7 |
| [plan/01-subagent-planning-and-audit.md](./plan/01-subagent-planning-and-audit.md) | Поэтапные planner workers, профильные audit skills, модели по ролям, frozen inputs и режим без субагентов |
| [plan/02-project-index-and-business-knowledge.md](./plan/02-project-index-and-business-knowledge.md) | Карта проекта, claims из кода и задач, три оси статусов, инвалидация и тестовые контракты |
| [plan/03-web-testing-system.md](./plan/03-web-testing-system.md) | Постоянные сценарии бизнес-процессов, Codeception и Playwright, fixtures, выбор регрессии и receipts |
| [plan/04-knowledge-store-and-queue.md](./plan/04-knowledge-store-and-queue.md) | JSONdoc-канон, SQLite-очередь, DDL, lease, retry, recovery, coverage и миграция текстовых очередей |
| [plan/05-bug-hunt-and-modernization.md](./plan/05-bug-hunt-and-modernization.md) | Pass library, контракт finding, severity, triage, воспроизведение, SOLID, performance и backlog модернизации |
| [plan/субагенты.md](./plan/субагенты.md) | Переносимые малые субагенты: манифест ролей, скил delegation-router, контракт пакета и отчета, адаптеры Kilo, Qoder, OpenCode, Qwen, вложенность и пилот |

---

## Быстрые команды

```bash
# Анализ диалогов: полный прогон и проверка артефактов
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --allow-partial
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py validate
```

```bash
# Синхронизация зеркал 3 сред из канона + parity + freshness-гейт
./.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh

# Проверки харнеса
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py --rules-dir .cursor/rules --skills-dir .agents/skills

# Пакетное чтение задачи через JSONdoc
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . batch --input .doc/tasks/{N}/_jsondoc/work/batch.json
```

---

## Что откуда взято (покрытие без потерь)

| Источник (удален) | Куда разложен |
|---|---|
| `harnes_audit/muse-spark1.3.md` (888) | state/08 (разбор скила разделы 1-11), state/10 (метод, F1-F10, история), state/04 (MCP потери) |
| `harnes_audit/report.md` (246), `audit2-report.md` (163) | state/10 (внедрения F1-F9, 9 из 15 P) |
| `harnes_audit/audit2.md` (392) | plan/02 (отложенные P4-P14), state/10 (внедренные), state/01 (LF, freshness, реестр, delta) |
| `harnes_audit/plan_audit.md` (377) | plan/03 (оркестратор x3 полный) |
| `harnes_audit/planx.md` (232) | plan/04 (полный) |
| `harnesaudit.md` (540) | plan/01 (полный roadmap с якорями) |
| `rebase_project.md` v1.23, `rebase_project.ps1`, `rebase_project_gi.ps1` | state/09 (полная карта; сами файлы-каноны оставлены как исполняемые) |
| `harnes.html` (999 строк) | state/01 (+сводная матрица раздел 12 html), state/04, state/05, state/06 (+живое состояние J00-J17 из раздела 13 html), state/07 (схемы раздела 10 html), state/08 (контур раздела 09 html), state/09 (+аудит скриптов R1-R7 из раздела 11.4 html); сам файл удален 2026-10-02 |
| `readmy.md` | Указатель: разделы ведут в `state/01` - `state/08` и `dirtree.md`; инвентарь в файле не хранится |

---

## Удаление исходников (выполнено 2026-10-02)

Удалены: `harnes_audit/muse-spark1.3.md`, `report.md`, `audit2.md`,
`audit2-report.md`, `plan_audit.md`, `planx.md`, `harnesaudit.md`,
каталог `harnes_audit/` целиком, `harnes.html` (аудит 2026-10-02: все 13 секций
проверены, уникальное дополнено в state/01 матрица, state/06 живое состояние,
state/09 аудит R1-R7, остальное уже покрывалось), `jsondoc-status.md` (аудит
2026-10-02: этапы J00-J17 с evidence, совместимость, правки двух внешних аудитов,
откат и ограничения перенесены в state/06; ссылки в .cursor/README.md,
readmy_doc.md, synh_harnes/README.md переведены).

Оставлены (исполняемые каноны и legacy, не дубликат плана/состояния):

- `.doc/rebase_project.md`, `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1`, `.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1` - каноны переноса, их читают скрипты и процесс экспорта
- `.doc/skil_data/harness-core/README.md`, `report-workflow-plan.md` - операционные документы у скриптов
- readmy.md и readmy_doc.md перенесены в корень каталога 2026-10-02 из `.doc/`
- `jsondoc.md` - нормативная спецификация движка (корень каталога). Перемещен из `.doc/` 2026-10-02. Выжимка в state/06
- `testaudit.md`, `tests.md` - каноны тестирования (корень каталога). tests.md переехал из `.doc/` 2026-10-02

---

## Про архитектуру

Каталог `.doc/architecture/` не содержит описаний харнеса: там только продуктовые
домены. Смежные инфраструктурные документы остаются продуктовыми: `sourcegraph-local.md`,
`local-dev-resources.md`, `cicd.md`. Упоминания `task-doc #N` в историях изменений
архитектуры - обратные ссылки по `doc_rules.md`, не трогать.

---

## .doc/plan/ - миграция харнеса

Планы миграции лежат в `.doc/plan/`, отдельно от roadmap в `.doc/harnes/plan/`.
Здесь только исполняемые планы приведения харнеса к новым правилам.

| Документ | Тема |
|---|---|
| harnesmigrations.md (удалён) | Миграция 26 скилов к формату: README, `skill.json`, локальные скрипты, документы 180 исполняемых файлов, синк, parity, export Full и Core, DSH |
| harnesaudit-2026-11-02.md (удалён) | Аудит плана и структуры: 30 находок, оценки, DSH-разрывы, решения |

---

## Связи

- [Правила документации](doc_rules.md) - стандарт, читать первым
- [Реальное состояние](./state/01-canon-envs.md) - с чего начинается харнес
- [План улучшений](./idea/01-roadmap-hpta.md) - что не внедрено
- `.cursor/README.md` - гайд канона
- `AGENTS.md` (корень репо) - корневой указатель

---

## История изменений

- 2026-11-11: удалены ссылки на снятые скилы `business-analyst` и `task-business-analysis`; бизнес-анализ остался только историческим документом `state/17-business-analyst.md`, упоминание `business-rules` убрано.
- 2026-11-11: добавлен канон раскладки каталогов `dirtree.md`; раскладка из `readmy.md` и `state/01-canon-envs.md` заменена ссылкой. Устаревший инвентарь `readmy.md` удален, файл стал указателем.
- 2026-11-10: добавлен скил `audit-plan` в таблицу скилов и в группировку `task-router`; аудит плана вынесен из `prepare-plan`.
- 2026-11-09: обновлена навигация к атомарному бизнес-анализу и драйверу хранения; состояние, точки вызова, результаты проверок и ограничения описаны в state/17-business-analyst.md.

- 2026-11-09: обновлена навигация к документу синхронизации сред разработки.
- 2026-10-21: починены все локальные ссылки в `.doc` (0 битых): удалены 342 старые staging-копии миграций, 521 ссылка исправлена в 274 файлах, добавлен `docscripts/check-links.py` и проверка в `smoke.sh`
- 2026-10-21: документация DSH переведена в `.doc/architecture/deepseek-harness-*` (JSON-канон плюс MD-вид), каталог `.doc/deepseek_harnes` удален, ссылки обновлены
- 2026-10-01: каталог создан из readmy.md / harnes.html (13 документов)
- 2026-10-02: реструктуризация в два раздела plan/ и state/ со сверкой статусов по коду; исходники аудитов удалены
- 2026-10-02: аудит harnes.html (999 строк, 13 секций), уникальное дополнено, файл удален
- 2026-10-02: doc_readme.md и auditplan.md (plan/05) перенесены в harnes; gitverce.md и deploytask.md перенесены в architecture/ рядом с cicd (канон cicd.json обновлен через jsondoc apply, view перерендерен); исправлен баг jsondoc CLI kind для apply/render/recover --arch
- 2026-10-02: аудит jsondoc-status.md (пересен в state/06, удален); каноны jsondoc.md, testaudit.md, tests.md, readmy_doc.md, readmy.md собраны в корне .doc/harnes/ (тогда считались каноническими документами харнеса; с 2026-11-01 документация из харнеса выведена, см. запись ниже); все ссылки канона, qa и rebase переведены
- 2026-10-02: пакетные вызовы внедрены и консолидированы в state/12-batch-calls.md; планы plan/massgrep.md, plan/massgrep-audit.md, plan/massgrep-audit-summary.md удалены как реализованные
- 2026-10-20: аудит DSH: обновлены state/01-canon-envs.md (14 MCP-клиентов, pwsh вместо powershell.exe, шимы run-ps1/smoke, одна модель) и h-test-report.md (H3-H6 зелёные)
- 2026-10-30: добавлен state/17-business-analyst.md: автономный сбор бизнес-логики, hash-ledger, JSONdoc business_logic, registry и тесты
- 2026-10-30: добавлен state/18-task-text-and-report.md: текстовый контракт, business_changes, панель, лента Jira, релизы и покрытие условий
- 2026-11-01: добавлен раздел skills/: карточка на каждый корневой скил (зачем нужен и как работает), вложенные файлы описаны внутри карточки
- 2026-11-01: state/04-mcp.md дополнен деталями по каждому серверу (транспорт, alwaysAllow, правила), добавлен jdocmunch
- 2026-11-01: добавлен раздел `mcp/`, один файл на MCP-сервер; подробный `mcp/jdocmunch.md` заменяет `state/20-jdocmunch.md`
- 2026-11-01: добавлен скил harness-index: маршруты работы с индексом, справочник команд, смысловой аудит
- 2026-11-01: документация выведена из харнеса: карта харнеса больше не индексирует `.doc/`, связи на документацию отбрасываются, скилы и правила работают без неё (границы в `state/01-canon-envs.md`, механика в `state/19-harness-mirror.md`)
- 2026-11-01: лаунчер jdocmunch перенесён в канон `.cursor/scripts/` по правилу миграции, path-независимый handle, зеркала пересобраны синком
- 2026-11-01: state/04-mcp.md, раздел 3.3 serena переписан по проверке: матрица инструментов, PHP-бэкенды, поиск по `.doc`
- 2026-11-01: регламенты CBM, Sourcegraph и Serena перенесены из state/11 и state/15 в `mcp/`, в общих документах остались ссылки
- 2026-11-01: правило `mcp-codebase-memory` стало полным справочником вызова (17 методов, аргументы, когда брать), эксплуатация CBM перенесена в `mcp/codebase-memory-mcp.md`, старая kit-инструкция `.cursor/codebase-memory-mcp.md` удалена
- 2026-11-01: правило `mcp-graphify` стало полным справочником вызова (10 инструментов, аргументы, выход, примеры, границы), документ `mcp/graphify.md` дополнен установкой, переносом, работой с несколькими проектами и разбором П-1 - П-7; поведение без `project_path` и свежесть графа уточнены в state/04 и state/15
- 2026-11-03: завершённый документ перенесён в `state/22-panel-service.md` как описание реализованного сервиса: панель и харнес-миррор на 8077, задания с AJAX, цены и провайдеры, стоимость, переносимость, selfcheck 15 из 15
- 2026-11-05: выполнен аудит путей после переноса скилов в иерархию. Исправлены корневые вычисления в 16 скриптах test-task, путях jsondoc, xmlriver, page-content, leantime, jira и зеркальных ссылках; документация и `component_registry.json` приведены к `.agents/skills/**`; parity passed, selfcheck 15 из 15.
- 2026-11-06: добавлен план `plan/субагенты.md`: переносимые малые субагенты, единый манифест ролей, контракт пакета и отчета, адаптеры Kilo, Qoder, OpenCode и Qwen Code, политика вложенности и пилот экономии токенов.
