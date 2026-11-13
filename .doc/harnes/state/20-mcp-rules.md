# MCP-правила: карта, состав и связи

<!-- meta
type: architecture
status: actual
updated: 2026-11-09
related: [../index.md, ./03-rules.md, ./04-mcp.md, ../mcp/README.md, ../state/15-mcp-stack.md]
tags: [harness, mcp, rules, audit]
-->

---

## Суть

Для каждого MCP-сервера есть отдельное правило `.cursor/rules/mcp/{server}.mdc`.
Общая карта и порядок вызова лежат в `.cursor/rules/mcp.mdc`. Всего 21 правило
серверов и одна карта, то есть 22 MCP-правила. Правило описывает поверхность
вызова: когда брать сервер, методы и аргументы, порядок относительно других
серверов, типовые ошибки и проверку. Документ `.doc/harnes/mcp/{server}.md`
хранит установку, эксплуатацию, перенос и ограничения.

## Состав

| Сервер | Правило | Документ | Связанные правила |
|---|---|---|---|
| `codebase-memory-mcp` | [mcp-codebase-memory](../../../.cursor/rules/mcp/codebase-memory-mcp.mdc) | [документ](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [task-doc](../../../.cursor/rules/task-doc.mdc), [project-doc](../../../.cursor/rules/project-doc.mdc), [doc-verify](../../../.cursor/rules/doc-verify.mdc), [cbm-index-before-push](../../../.cursor/rules/cbm-index-before-push.mdc) |
| `codegraph` | [mcp-codegraph](../../../.cursor/rules/mcp/codegraph.mdc) | [документ](../../../.agents/skills/codegraph/docs/mcp/codegraph.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [task-doc](../../../.cursor/rules/task-doc.mdc), [project-doc](../../../.cursor/rules/project-doc.mdc), [doc-verify](../../../.cursor/rules/doc-verify.mdc) |
| `codeprism` | [mcp-codeprism](../../../.cursor/rules/mcp/codeprism.mdc) | [документ](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) | [gates](../../../.cursor/rules/gates.mdc), [code-editing](../../../.cursor/rules/code-editing.mdc), [task-doc](../../../.cursor/rules/task-doc.mdc) |
| `serena` | [mcp-serena](../../../.cursor/rules/mcp/serena.mdc) | [документ](../../../.agents/skills/serena/docs/mcp/serena.md) | [code-editing](../../../.cursor/rules/code-editing.mdc), [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [task-doc](../../../.cursor/rules/task-doc.mdc), [doc-verify](../../../.cursor/rules/doc-verify.mdc) |
| `mysql` | [mcp-mysql](../../../.cursor/rules/mcp/mysql.mdc) | [документ](../../../.agents/skills/mysql/docs/mcp/mysql.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [task-doc](../../../.cursor/rules/task-doc.mdc) |
| `git` | [mcp-git](../../../.cursor/rules/mcp/git.mdc) | [документ](../../../.agents/skills/git/docs/mcp/git.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [cbm-index-before-push](../../../.cursor/rules/cbm-index-before-push.mdc) |
| `jira-task` | [mcp-jira-task](../../../.cursor/rules/mcp/jira-task.mdc) | [документ](../../../.agents/skills/task-router/children/jira/docs/mcp/jira-task.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc) |
| `context7` | [mcp-context7](../../../.cursor/rules/mcp/context7.mdc) | [документ](../../../.agents/skills/context7/docs/mcp/context7.md) | [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc), [doc-rules](../../../.cursor/rules/doc-rules.mdc) |
| `playwright` | [mcp-playwright](../../../.cursor/rules/mcp/playwright.mdc) | [документ](../../../.agents/skills/playwright/docs/mcp/playwright.md) | [test-task](../../../.cursor/rules/test-task.mdc), [test-priority](../../../.cursor/rules/test-priority.mdc) |
| `phpstan-mcp` | [mcp-phpstan](../../../.cursor/rules/mcp/phpstan-mcp.mdc) | [документ](../../../.agents/skills/phpstan-mcp/docs/mcp/phpstan-mcp.md) | [task-doc](../../../.cursor/rules/task-doc.mdc), [code-editing](../../../.cursor/rules/code-editing.mdc) |
| `php-deps-mcp` | [mcp-php-deps](../../../.cursor/rules/mcp/php-deps-mcp.mdc) | [документ](../../../.agents/skills/php-deps-mcp/docs/mcp/php-deps-mcp.md) | [mcp-codegraph](../../../.cursor/rules/mcp/codegraph.mdc) |
| `semgrep` | [mcp-semgrep](../../../.cursor/rules/mcp/semgrep.mdc) | [документ](../../../.agents/skills/semgrep/docs/mcp/semgrep.md) | [task-doc](../../../.cursor/rules/task-doc.mdc), [code-editing](../../../.cursor/rules/code-editing.mdc) |
| `jdocmunch` | [mcp-jdocmunch](../../../.cursor/rules/mcp/jdocmunch.mdc) | [документ](../../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md) | [doc-rules](../../../.cursor/rules/doc-rules.mdc), [batch-calls](../../../.cursor/rules/batch-calls.mdc), [code-editing](../../../.cursor/rules/code-editing.mdc) |
| `graphiti` | [mcp-graphiti](../../../.cursor/rules/mcp/graphiti.mdc) | [документ](../../../.agents/skills/graphiti/docs/mcp/graphiti.md) | [mcp](../../../.cursor/rules/mcp.mdc) |
| `sourcegraph` | [mcp-sourcegraph](../../../.cursor/rules/mcp/sourcegraph.mdc) | [документ](../archive/mcp/sourcegraph.md) | [mcp-codegraph](../../../.cursor/rules/mcp/codegraph.mdc), [mcp-jdocmunch](../../../.cursor/rules/mcp/jdocmunch.mdc) |
| `xdebug` | [mcp-xdebug](../../../.cursor/rules/mcp/xdebug.mdc) | [документ](../archive/mcp/xdebug.md) | [mcp-phpstan](../../../.cursor/rules/mcp/phpstan-mcp.mdc) |
| `deepwiki` | [mcp-deepwiki](../../../.cursor/rules/mcp/deepwiki.mdc) | [документ](../archive/mcp/deepwiki.md) | [mcp-context7](../../../.cursor/rules/mcp/context7.mdc) |
| `bitbucket-task` | [mcp-bitbucket-task](../../../.cursor/rules/mcp/bitbucket-task.mdc) | [документ](../archive/mcp/bitbucket-task.md) | [mcp-jira-task](../../../.cursor/rules/mcp/jira-task.mdc) |

## Структура правила сервера

1. `Когда` - в каких задачах брать и когда не брать.
2. `Порядок вызова` - шаги и место в маршруте.
3. `Инструменты` - методы, ключевые аргументы, результат.
4. `Ошибки и границы` - типовые сбои, запреты, fallback.
5. `Проверка` - smoke-команда.
6. `Связи` - документ сервера, карта MCP, профильные правила.

Правило не пересказывает документ: установка, эксплуатация, перенос и несколько
проектов остаются в `.doc/harnes/mcp/{server}.md`.

## Порядок и приоритет

Карта [mcp.mdc](../../../.cursor/rules/mcp.mdc) задает ориентир: jdocmunch для
документации, затем CBM, codegraph, codeprism, php-deps, serena, mysql, context7,
playwright, phpstan и semgrep, jira-task, git. В конкретной задаче
порядок задают [bitbucket-tasks](../../../.cursor/rules/bitbucket-tasks.mdc) и
[prepare-plan](../../../.cursor/rules/prepare-plan.mdc).

При расхождении текстов действует приоритет:

1. Поверхность вызова и ограничения инструмента - правило `mcp/{server}.mdc`.
2. Порядок в задаче и обязательные гейты - профильное правило задачи.
3. Установка, порты, эксплуатация и перенос - документ `mcp/{server}.md`.

## Что изменено в доменных правилах

| Правило | Изменение |
|---|---|
| `doc-rules.mdc` | jdocmunch закреплен как основной поиск по `.doc`, добавлены ссылки на правила серверов |
| `code-editing.mdc` | детали Serena вынесены в `mcp-serena`, остались порядок правки, язык и проверка |
| `bitbucket-tasks.mdc` | маршрут MCP заменен ссылками на правила серверов, порядок сохранен |
| `task-doc.mdc` | Reuse и Impact Gate ссылаются на CBM, codegraph, serena, jdocmunch, phpstan и semgrep |
| `project-doc.mdc` | CBM и codegraph через профильные правила, документация через jdocmunch |
| `doc-verify.mdc` | MCP Gate ссылается на правила вместо дублирования деталей |
| `test-task.mdc` | Playwright через `mcp-playwright`, Codeception остается первым |
| `test-priority.mdc` | Playwright gap через `mcp-playwright` |
| `cbm-index-before-push.mdc` | полный набор команд и параметров вынесен в `mcp-codebase-memory` |
| `prepare-plan.mdc` | поиск документации через jdocmunch |
| `mcp.mdc` | добавлена карта, порядок выровнен с задачами и планом |

## Как добавить или изменить сервер

1. Изменить `.cursor/mcp.json`.
2. Обновить правило `.cursor/rules/mcp/{server}.mdc`.
3. Обновить документ `.doc/harnes/mcp/{server}.md`.
4. Добавить строку в [mcp.mdc](../../../.cursor/rules/mcp.mdc), в
   [mcp/README.md](../archive/mcp/README.md) и [state/04-mcp.md](./04-mcp.md).
5. Добавить компонент в
   `component_registry.json` как `rule-mcp-{server}`. Если MCP добавляет обязательный
   предварительный шаг, указать его в `.cursor/rules/gates.mdc`.
6. Запустить `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`.
7. Проверить `harness_mirror.py visibility --summary`, `validate_rules.py`,
   `validate_registry.py` и smoke `test-mcp-servers.mjs --only={server}`.

## Проверка

```bash
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=codebase-memory-mcp
```

Текущее состояние: 41 правило канона, 22 из них MCP (карта и 21 сервер).
Реестр содержит 88 компонентов после добавления always-гейта `rule-gates`. Все рабочие среды получают по 22 MCP-правила.
Из 21 сервера 17 включены, 4 отключены:
`bitbucket-task`, `deepwiki`, `sourcegraph`, `xdebug`.

## Известные ограничения

- Правила отключенных серверов остаются намеренно: они фиксируют причину
  отключения и замену.
- `validate_rules.py` может дать предупреждение о `verify.sh` в правилах, потому
  что проверяет скрипт относительно каталога скилов. Файл
  `.cursor/mcp-stack/verify.sh` существует, это ложное срабатывание.
- Правила CBM и codegraph содержат расширенный разбор методов от параллельной
  сессии. Он сохранен, потому что точнее ранней версии.

## Связи

- [Рулесы канона](./03-rules.md) - общий состав правил
- [MCP-серверы](./04-mcp.md) - состояние, порядок и Kilo-адаптация
- [MCP-стек](./15-mcp-stack.md) - порты, юниты и данные
- [Документы MCP](../archive/mcp/README.md) - конвенция и шаблон
- [Правила документации](../doc_rules.md) - стандарт `.doc/`

---

## История изменений

- 2026-11-01: создан документ по итогам аудита: 19 правил серверов, карта MCP,
  связи с доменными правилами, устраненные дубли и проверки
- 2026-11-02: добавлен `codegraph`: 20 правил серверов, 21 MCP-правило, 20 серверов (16 включённых)
- 2026-11-02: состояние сверено с каноном: 19 серверов (15 включённых, 4
  отключённых), 20 MCP-правил, 19 документов, реестр 54 = 26 скилов и 28
  rule-only компонентов; отмечены три правила с короткими именами
- 2026-11-02: добавлен `codeprism`: 21 MCP-правило (карта и 20 серверов), 20
  серверов (16 включённых), 20 документов в `mcp/`; реестр 55 компонентов
- 2026-11-06: добавлен `graphiti`: 22 MCP-правила (карта и 21 сервер), 21 сервер
  (17 включённых), 69 компонентов реестра
- 2026-11-09: в общий порядок добавлен always-гейт `gates.mdc`; установка нового MCP проверяет visibility правила через harness mirror
- 2026-11-02: добавлен скил `codeprism` под сервер `codeprism-ai`; реестр 56
  компонентов = 28 скилов и 28 rule-only
