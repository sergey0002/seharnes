# MCP-серверы (18: 14 включённых, 4 отключённых)

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ./01-canon-envs.md, ./07-workflows.md, ./15-mcp-stack.md]
tags: [harness, mcp]
-->

---

## Суть

В `.cursor/mcp.json` 18 записей: 14 включённых и 4 отключённых
(`deepwiki`, `bitbucket-task`, `sourcegraph`, `xdebug`). DSH-патч профиля `full` получает все
включённые серверы, отключённые не попадают. Секреты в `.cursor/mcp.env`.
Порядок в задачах: codebase-memory-mcp, codegraph, codeprism, mysql, serena,
context7, playwright, phpstan/semgrep. `codegraph` - локальный индекс PHP и JS
для одного вызова `codegraph_explore`: исходник, путь вызовов и blast radius. Он
заменил graphify в активном маршруте. `codeprism` - граф знаний PHP, JS и TS на
пакете `codeprism-ai`: контекст символа, вызывающие, влияние, поток данных и
security gate перед записью; индекс постоянный. Таймаут вызова 90s cold и 60s
warm, дальше тир timeout плюс Grep-компенсация.

Текущее состояние: 18 правил серверов и главная карта `mcp.mdc`.
Документы 14 включенных серверов лежат в `docs/mcp/` их скилов; документы
четырех отключенных серверов остаются в их скилах и правилах.
Legacy graphify сохранен отдельно и не используется.
Три правила названы короче ключа сервера: `mcp-codebase-memory`,
`mcp-php-deps`, `mcp-phpstan`; полный список в разделе 3.

---

## 1. Состав

| Сервер | Запуск | Статус | Роль |
|---|---|---|---|
| `codebase-memory-mcp` | HTTP `127.0.0.1:9131/mcp` (`mcp-codebase-memory.service`) | активен | Граф кода: классы, вызовы, cross-service. Один сервер, проект параметром `project` |
| `sourcegraph` | HTTP `127.0.0.1:7080/.api/mcp/v1` плюс token | отключен | Legacy полнотекст. Заменен codegraph для связей и `multi-search.sh`/`rg` для литералов и regex |
| `serena` | HTTP `127.0.0.1:9121/mcp` (`mcp-serena-testdeploydocker.service`), cms `:9122` | активен | LSP: символы, references, точечные правки. Один процесс на проект, клиенты по HTTP |
| `mysql` | `scripts/run-with-mcp-env.sh` плюс `mysql-mcp-proxy.mjs` | активен | Схема и данные стенда. `describe_table` канон схемы, execute только с разрешения |
| `playwright` | npx `@playwright/mcp@0.0.38`, headed chrome | активен | Браузерная верификация UI, живой DOM, скрины |
| `context7` | npx `@upstash/context7-mcp@3.2.2` | активен | Документация внешних библиотек |
| `git` | uvx `mcp-server-git` | активен | status, log, diff, show, blame |
| `codegraph` | `scripts/codegraph-mcp.sh`, `codegraph serve --mcp` | активен | Локальный индекс PHP и JS в `.codegraph/`: `codegraph_explore` отдает исходник, путь вызовов и blast radius одним вызовом. Индекс обновляется сам, `codegraph.json` исключает сторонние библиотеки |
| `codeprism` | `scripts/codeprism-mcp.sh`, `scripts/codeprism_serve.py`, `codeprism-ai==0.1.11` в `.cursor/tools/codeprism-ai/venv` | активен | Граф знаний PHP, JS и TS: контекст символа, вызывающие, влияние, поток данных, security gate. Индекс SQLite в user-data, область и исключения в `.codeprism.toml`, живое обновление при сохранении файлов. Скил `.agents/skills/codeprism` |
| `phpstan-mcp` | `scripts/node-mcp.sh` плюс `.tools/mcp-servers/php-toolchain` | активен | Статический анализ PHP |
| `php-deps-mcp` | тот же `.tools/mcp-servers/php-toolchain`, mode php-deps | активен | phpcallgraph и phpda, граф вызовов PHP |
| `semgrep` | uvx `semgrep mcp` | активен | Security-сканы |
| `xdebug` | npx `xdebug-mcp` | отключен | Runtime-отладка, когда расхождение видно только в рантайме |
| `jira-task` | docker exec в `.agents/skills/task-router/children/jira/scripts/server.php` | активен | Экспорт `task.md`, `list_release_tasks`. Вызывают скрипты скилов, не агент вручную |
| `jdocmunch` | `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh serve` | активен | Обязательный первый шаг по документации: секции, ссылки, термины по ID |
| `graphiti` | Docker `zepai/knowledge-graph-mcp:1.1.3`, HTTP `127.0.0.1:8000/mcp/`, автозапуск `graphiti-stack.service` | активен | Временной граф знаний: эпизоды, сущности, факты с датами. FalkorDB в контейнере, LLM `deepseek-v4.1-flash-1017` через OpenAI-совместимый шлюз, эмбеддинги через Ollama `qwen3-embedding:0.6b` на `11434`, автозапуск `ollama-qwen.service` |
| `deepwiki` | npx | отключен | Резерв внешней документации |
| `bitbucket-task` | docker exec в `.doc/.bitbucket/server.php` | отключен | Legacy трекер, заменен jira-task |

Привязки индексации: `mcp.index.md`. Инструкции: [правило CBM](../../../.cursor/rules/mcp/codebase-memory-mcp.mdc)
и [документация сервера](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), `.cursor/sourcegraph-mcp.md`,
`.cursor/README-MCP-SETUP.md`.

MCP-маршрут для `.doc/`: [../doc_rules.md](../doc_rules.md), раздел MCP-маршрут.

Массовый поиск по `.doc/` идет скриптом `.tools/scripts/multi-search.sh`, не MCP: `.doc/` целиком Serena не обходит (см. [3.3.4](#334-поиск-по-документации)). MCP-вызовы без зависимости пакуются через `execute` + `Promise.all`, встроенные `grep`/`read` пачками через `multi-search.sh` / `multi-exec.sh` (правило `batch-calls`).

---

## 2. Kilo-адаптация

Генератор `generate-agent-configs.py`, состояние 2026-09-28:

- stdio-серверы переходят в Kilo `type: local` с тем же argv. Обертка
`run-with-mcp-env.sh` добавляется один раз, двойной `bash bash` исключен.
- http и sse-серверы переходят в Kilo `type: remote` (url плюс headers), не дропаются.
`sourcegraph` жив в Kilo как remote. Всего в `kilo.jsonc` 18 серверов, все из канона.
- `${env:VAR}` не инлайнится. Значения подставляет обертка из `mcp.env` в рантайме.
- Абсолютные пути под root нормализуются в `${workspaceFolder}`-форму.
- `alwaysAllow` и `disabledTools` фиксируются в шапке `kilo.jsonc` плюс отдельным
`.kilo/kilo-permissions.fragment.jsonc` (`{server}_{tool}: allow/deny`, 86 записей на 2026-11-01).
Применение ручным слиянием в `permission`, не автомат.
- Шапка `kilo.jsonc`: generated-by, do-not-edit, env-объяснение, skipped-типы.

---

## 2a. Общий HTTP-стек

codebase-memory вынесен из клиентов в общий HTTP-слой на systemd: один на все
проекты (9131), serena по процессу на проект. Транспорт Streamable HTTP через
`mcp-proxy`, только `127.0.0.1`. `codegraph` работает по stdio и порта не требует.
Legacy graphify (9130) остановлен и выведен из канона.

Полная карта, лимиты, данные, добавление проекта и перенос:
[15-mcp-stack.md](./15-mcp-stack.md).

---

## 3. Детали по серверам

Канон конфигурации один, `.cursor/mcp.json`; клиентские файлы генерируются и
вручную не правятся. Подробности по каждому серверу вынесены в
[`mcp/`](../archive/mcp/README.md), один файл на сервер: конфигурация, инструменты,
правила вызова и ограничения. Здесь только маршрут.

| Сервер | Статус | Транспорт | Документ |
|---|---|---|---|
| `codebase-memory-mcp` | активен | HTTP 9131 | [codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) |
| `codegraph` | активен | stdio | [codegraph.md](../../../.agents/skills/codegraph/docs/mcp/codegraph.md) |
| `codeprism` | активен | stdio | [codeprism.md](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) |
| `serena` | активен | HTTP 9121, cms 9122 | [serena.md](../../../.agents/skills/serena/docs/mcp/serena.md) |
| `mysql` | активен | stdio | [mysql.md](../../../.agents/skills/mysql/docs/mcp/mysql.md) |
| `git` | активен | stdio | [git.md](../../../.agents/skills/git/docs/mcp/git.md) |
| `jira-task` | активен | stdio, docker exec | [jira-task.md](../../../.agents/skills/task-router/children/jira/docs/mcp/jira-task.md) |
| `context7` | активен | stdio | [context7.md](../../../.agents/skills/context7/docs/mcp/context7.md) |
| `playwright` | активен | stdio | [playwright.md](../../../.agents/skills/playwright/docs/mcp/playwright.md) |
| `phpstan-mcp` | активен | stdio | [phpstan-mcp.md](../../../.agents/skills/phpstan-mcp/docs/mcp/phpstan-mcp.md) |
| `php-deps-mcp` | активен | stdio | [php-deps-mcp.md](../../../.agents/skills/php-deps-mcp/docs/mcp/php-deps-mcp.md) |
| `semgrep` | активен | stdio | [semgrep.md](../../../.agents/skills/semgrep/docs/mcp/semgrep.md) |
| `jdocmunch` | активен | stdio | [jdocmunch.md](../../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md) |
| `graphiti` | активен | HTTP 8000 | [graphiti.md](../../../.agents/skills/graphiti/docs/mcp/graphiti.md) |
| `sourcegraph` | отключен | HTTP 7080 | [sourcegraph.md](../archive/mcp/sourcegraph.md) |
| `xdebug` | отключен | stdio | [xdebug.md](../archive/mcp/xdebug.md) |
| `deepwiki` | отключен | stdio | [deepwiki.md](../archive/mcp/deepwiki.md) |
| `bitbucket-task` | отключен | stdio, docker exec | [bitbucket-task.md](../archive/mcp/bitbucket-task.md) |

Правило ведения: документ включенного сервера лежит в `{skill}/docs/mcp/{server}.md`,
отключенного в `.doc/harnes/archive/mcp/{server}.md`. Имя файла
совпадает с ключом в `.cursor/mcp.json`. Правило сервера лежит в
`.cursor/rules/mcp/{server}.mdc`, имя совпадает с ключом, исключений нет.
У каждого сервера есть отдельное правило с порядком вызова, параметрами и
границами; документ в `mcp/` хранит подробности. Главная карта:
[`.cursor/rules/mcp.mdc`](../../../.cursor/rules/mcp.mdc) - назначение, порядок и
ссылки на правило и документ каждого сервера. Новый сервер добавляется в канон,
главную карту, правило, таблицу выше и отдельным файлом по шаблону из
[README](../archive/mcp/README.md).

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [mcp/README.md](../archive/mcp/README.md) - документы по каждому серверу
- [MCP-правила](./20-mcp-rules.md) - карта, 21 правило серверов и связи с правилами задач
- [Канон и среды](./01-canon-envs.md) - синк и parity
- [MCP-стек](./15-mcp-stack.md) - юниты, порты, лимиты, данные, перенос
- [Эксплуатация](./11-dev-environment.md) - память WSL2 и профиль ресурсов
- [Контур планирования](./08-plan-contour.md) - лестница Tier 0-8
- [Правила документации](../doc_rules.md) - MCP-маршрут
- Продуктовая инфра поиска: `../architecture/sourcegraph-local.md` (не дублируется сюда)

---

## Известные проблемы и ограничения

- Выбор проекта: CBM - параметр `project` из `list_projects`; codegraph -
  `projectPath=<root>` в вызове; serena - отдельный юнит на проект.
- Детали и ограничения конкретных серверов живут в их файлах:
  [codegraph](../../../.agents/skills/codegraph/docs/mcp/codegraph.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md),
  [codebase-memory-mcp](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md),
  [sourcegraph](../archive/mcp/sourcegraph.md), [jdocmunch](../../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md).
  Здесь не дублируются.
- SG-токен в Kilo remote headers в открытом виде, как в каноне. Каталог `.kilo/` исключен из git, в коммиты не попадает, при ручном копировании вычищать самому.
- `alwaysAllow` применяется только ручным слиянием fragment, автомат отключен осознанно.

---

## История изменений

- 2026-11-11: количество записей сверено с каноном: 18 серверов, 14 включённых, 4 отключённых; документы отключённых серверов живут в их скилах.
- 2026-11-11: php-toolchain перенесён в `.tools/mcp-servers`; `phpstan-mcp` и `php-deps-mcp` запускаются из этого каталога, копии в зеркалах удалены.
- 2026-11-09: `graphiti` переведён с FastEmbed 7997 (`e5-small`, 384) на Ollama 11434 (`qwen3-embedding:0.6b`, 1024); Ollama работает как systemd user unit `ollama-qwen.service` с автозапуском.
- 2026-11-07: созданы 11 недостающих скилов MCP; документы всех 17 включенных серверов размещены в скилах, аудит и история сохранены, ссылки обновлены. Документы четырех отключенных серверов остались в `.doc/harnes/mcp/`.
- 2026-11-06: `graphiti` получил автозапуск: юнит `graphiti-stack.service`, контейнеры `graphiti*`, `up` при входе в систему. До этого канон считал сервер включённым, а фактически порт 8000 был пуст.
- 2026-11-06: аудит дублей MCP вынесен в [24-mcp-duplicates-audit](./24-mcp-duplicates-audit.md): 89 процессов, 6.5 ГБ, что дублируется законно (serena, Intelephense, dsh, playwright) и что нет (jdocmunch, mysql, php-toolchain, codeprism, codegraph).
- 2026-10-01: вынесено из `readmy.md` в `.doc/harnes/`
- 2026-10-29: добавлен `graphify` (18 записей, 15 включённых), `xdebug` помечен отключённым по канону; описано требование к `graphify-out/graph.json` и проба в smoke-тесте
- 2026-10-29: `sourcegraph` отключен (14 включённых, 4 отключённых), маршрут переведен на graphify плюс `multi-search.sh`/`rg`
- 2026-10-30: graphify и CBM переведены на общие HTTP-серверы под systemd, serena по проекту; детали в [15-mcp-stack.md](./15-mcp-stack.md)
- 2026-10-29: добавлен Docker-вариант graphify (HTTP, один процесс на все проекты, выбор через `project_path`)
- 2026-11-01: добавлен `jdocmunch` (19 записей, 15 включённых); раздел 3 с деталями по каждому серверу (транспорт, `alwaysAllow`, правила), перенесён из временной папки `.doc/harnes/mcp/`
- 2026-11-01: лаунчер `jdocmunch` перенесён из `.dsh/scripts/` в канон `.cursor/scripts/`; путь проекта и handle выводятся из расположения скрипта и индекса, зеркала пересобраны синком
- 2026-11-01: раздел 3.3 serena переписан по результатам проверки: матрица рабочих и нерабочих инструментов, опциональные инструменты, проверка точности `replace_symbol_body`, поведение поиска по `.doc`, сравнение четырёх PHP-бэкендов и правила использования. Убрано неверное утверждение, что `find_referencing_symbols` для PHP не работает
- 2026-11-01: канон `.cursor/mcp.json`, `alwaysAllow` для serena приведён к реальному набору: убран недоступный `get_type_hierarchy`, добавлены `find_referencing_symbols`, `find_declaration`, `get_diagnostics_for_file`; зеркала перегенерированы `sync-agent-views.sh`, fragment 86 правил
- 2026-11-01: детали по серверам вынесены в `.doc/harnes/mcp/`, один файл на сервер; раздел 3 стал таблицей ссылок
- 2026-11-01: инструкция CBM разделена: поверхность вызова в `.cursor/rules/mcp/codebase-memory-mcp.mdc`, эксплуатация и установка в `mcp/codebase-memory-mcp.md`; `.cursor/codebase-memory-mcp.md` удалён как не переносившийся в зеркала
- 2026-11-01: добавлена главная карта `.cursor/rules/mcp.mdc` с назначением, порядком и ссылками на правило и документ каждого из 19 серверов; добавлены разделы установки, переноса и нескольких проектов в документы серверов
- 2026-11-02: состояние сверено с каноном: 19 серверов (15 включённых, 4 отключённых), 19 правил `mcp-*`, 19 документов и главная карта; отмечены три правила с короткими именами
- 2026-11-01: роль graphify уточнена по проверке на живом сервере: 10 инструментов, fallback на `WorkingDirectory` без `project_path`, проверка свежести через `graph_stats`; подробности в [graphify.md](../archive/mcp/graphify.md)
- 2026-11-02: `graphify` выведен из канона, код заменен на `codegraph`; 19 серверов (15 включённых), 19 активных правил
- 2026-11-02: `jdocmunch` закреплён как обязательный первый шаг при любом упоминании документации; корпус дополнен `.doc/web`, панель документации теперь ищется через `search_sections`
- 2026-11-02: добавлен `codegraph` (19 записей, 15 включённых): локальный индекс PHP и JS, MCP stdio через `.cursor/scripts/codegraph-mcp.sh`, правило `mcp/codegraph.mdc` и документ `mcp/codegraph.md`
- 2026-11-02: добавлен `codeprism` (20 записей, 16 включённых): метрики JS, TS и Vue через release v0.3.5, MCP stdio через `.cursor/scripts/codeprism-mcp.sh`, цель `frontend`; правило `mcp/codeprism.mdc` и документ `mcp/codeprism.md`
- 2026-11-06: добавлен `graphiti` (21 запись, 17 включённых): временной граф знаний на FalkorDB, HTTP на `127.0.0.1:8000/mcp/`, LLM `gpt-6-luna` через OpenAI-совместимый шлюз, эмбеддинги через FastEmbed API (`fastembed-api:7997`, `intfloat/multilingual-e5-small`); правило `mcp/graphiti.mdc` и документ `mcp/graphiti.md`
- 2026-11-02: `codeprism` заменен на `codeprism-ai` 0.1.11 (knight22-21): PHP, постоянный SQLite-индекс, 21 инструмент, security gate; цель это корень проекта. Добавлен скил `.agents/skills/codeprism`, бинарник rustic-ai удален
