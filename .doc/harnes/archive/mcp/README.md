# MCP-серверы: по одному документу на сервер

<!-- meta
type: index
status: actual
updated: 2026-11-07
related: [../index.md, ../state/04-mcp.md, ../state/13-agent-migration.md, ../state/15-mcp-stack.md]
tags: [harness, mcp, index]
-->

---

## Суть

Этот индекс ссылается на подробную документацию MCP-серверов.
Документ включенного сервера лежит в `{skill}/docs/mcp/{server}.md`,
отключенного в `.doc/harnes/mcp/{server}.md`. Каждый активный MCP имеет скил
с `SKILL.md`, `README.md` и `skill.json`. Общая картина остается в
[state/04-mcp.md](../state/04-mcp.md): состав, порядок в задачах, Kilo-адаптация и
общий HTTP-стек. Канон конфигурации один, `.cursor/mcp.json`; клиентские файлы
генерируются синком.

Целевая раскладка правил MCP: `.cursor/rules/mcp/{server}.mdc`, имя равно ключу
сервера, главное правило `mcp.mdc` ссылается на каждый файл. Плоский вид для
Antigravity и перенос правил-шагов в `references/` скила описаны отдельно:
[rules-placement.md](./rules-placement.md).

DeepSeek Harness получает серверы не файлом правил, а патчем
`.dsh/project.patch.yml` от `generate-dsh-config.py`; правила MCP попадают в
`DSH-RULES.md` как on-demand таблица. При переносе правил в папку `mcp/`
генератор DSH обязан обходить каталог рекурсивно, иначе серверы останутся в
патче, а их правила исчезнут из индекса.

Установка нового сервера с проверкой всех сред и переноса:
[component-install.md](../component-install.md), раздел 4.

---

## Правило

1. У включенного сервера один документ `{skill}/docs/mcp/{server}.md`.
   У отключенного сервера документ остается в `.doc/harnes/mcp/{server}.md`.
2. Имя файла документа совпадает с ключом сервера в `.cursor/mcp.json`,
   исключений нет.
3. Отдельного файла для отключенного сервера не избегаем: файл нужен, чтобы
   зафиксировать причину отключения и замену.
4. `state/04-mcp.md` не дублирует детали: там таблица состава и ссылки на файлы.
5. Главная карта - `.cursor/rules/mcp.mdc`: назначение каждого сервера, порядок
   вызова и ссылки на правило и документ. Она обновляется при добавлении сервера.
6. Разделение ответственности. Файл сервера хранит конфигурацию, область индексации,
   эксплуатацию, данные и ограничения. Правило сервера хранит поверхность вызова
   для агента: методы, аргументы, что возвращают, когда брать. Правило лежит в
   `.cursor/rules/mcp/{server}.mdc`, имя совпадает с ключом. Один и тот же текст
   в двух местах не дублируется, только ссылки, как требует
   [doc_rules.md](../doc_rules.md).
7. При изменении `.cursor/mcp.json` обновляется файл сервера и `state/04-mcp.md`,
   затем зеркала пересобираются `sync-agent-views.sh`. Для DSH дополнительно
   проверяется `generate-dsh-config.py --check` и `DSH-RULES.md`.

**Текущее состояние 2026-11-06.** В каноне 21 сервер: 17 включённых и 4
отключённых (`bitbucket-task`, `deepwiki`, `sourcegraph`, `xdebug`). К ним 21
активное правило `mcp-*` и 21 документ плюс главная карта `mcp.mdc`. Legacy
graphify сохранен отдельными файлами и в активном маршруте не используется.
Документы всех 17 включенных серверов находятся в скилах. Наборы инструментов
сверены с исходниками: semgrep 9, xmlriver 7, xmlriver-ws 7, leantime 16,
context7 2, git 13, playwright 20+. В каждом документе есть разделы установки,
переноса и нескольких проектов.

Проверка размещения, наличия файлов скила, дублей и локальных ссылок:
`python3 .agents/skills/harness-router/children/doc-mcp/scripts/doc_mcp.py --audit`.

---

## Состав

| Сервер | Статус | Транспорт | Документ |
|---|---|---|---|
| `codebase-memory-mcp` | активен | HTTP 9131 | [codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) |
| `codegraph` | активен | stdio | [codegraph.md](../../../.agents/skills/codegraph/docs/mcp/codegraph.md) |
| `codeprism` | активен | stdio | [codeprism.md](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) |
| `serena` | активен | HTTP 9121, cms 9122 | [serena.md](../../../.agents/skills/serena/docs/mcp/serena.md) |
| `mysql` | активен | stdio | [mysql.md](../../../.agents/skills/mysql/docs/mcp/mysql.md) |
| `git` | активен | stdio | [git.md](../../../.agents/skills/git/docs/mcp/git.md) |
| `jira-task` | активен | stdio, docker exec | [jira-task.md](../../../.agents/skills/task-router/children/jira/docs/mcp/jira-task.md) |
| `leantime` | активен | stdio | [leantime.md](../../../.agents/skills/task-router/children/leantime/docs/mcp/leantime.md) |
| `context7` | активен | stdio | [context7.md](../../../.agents/skills/context7/docs/mcp/context7.md) |
| `playwright` | активен | stdio | [playwright.md](../../../.agents/skills/playwright/docs/mcp/playwright.md) |
| `phpstan-mcp` | активен | stdio | [phpstan-mcp.md](../../../.agents/skills/phpstan-mcp/docs/mcp/phpstan-mcp.md) |
| `php-deps-mcp` | активен | stdio | [php-deps-mcp.md](../../../.agents/skills/php-deps-mcp/docs/mcp/php-deps-mcp.md) |
| `semgrep` | активен | stdio | [semgrep.md](../../../.agents/skills/semgrep/docs/mcp/semgrep.md) |
| `xmlriver` | активен | stdio | [xmlriver.md](../../../.agents/skills/xmlriver/docs/mcp/xmlriver.md) |
| `xmlriver-ws` | активен | stdio | [xmlriver-ws.md](../../../.agents/skills/xmlriver/docs/mcp/xmlriver-ws.md) |
| `jdocmunch` | активен | stdio | [jdocmunch.md](../../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md) |
| `graphiti` | активен | HTTP 8000 | [graphiti.md](../../../.agents/skills/graphiti/docs/mcp/graphiti.md) |
| `sourcegraph` | отключен | HTTP 7080 | [sourcegraph.md](./sourcegraph.md) |
| `xdebug` | отключен | stdio | [xdebug.md](./xdebug.md) |
| `deepwiki` | отключен | stdio | [deepwiki.md](./deepwiki.md) |
| `bitbucket-task` | отключен | stdio, docker exec | [bitbucket-task.md](./bitbucket-task.md) |

Правило на каждый сервер: `.cursor/rules/mcp/{server}.mdc`. Оно описывает корректный
вызов, порядок относительно других MCP и границы. Документ в этом каталоге хранит
подробности, правило ссылается на него.

---

## Шаблон файла

```markdown
# MCP: {server}

<!-- meta
type: config
status: actual
updated: YYYY-MM-DD
related: [./README.md, ../state/04-mcp.md]
tags: [harness, mcp, {тема}]
-->

## Суть
Что это и зачем, 2-4 предложения.

## Когда вызывать
Когда брать сервер, в каком порядке относительно других MCP, когда не брать.

## Конфигурация
Таблица: тип, запуск, URL или служба, окружение, статус.

## Текущие значения
Фактические значения из канона: URL, порт, служба, таймауты, лимиты, каталог
данных, область индексации, переменные окружения, статус. Секреты не печатаются,
только имена переменных.

## Инструменты и аргументы
Все инструменты сервера: аргументы, что возвращают, что в alwaysAllow, что требует
подтверждения, что недоступно.

## Правила использования
Нумерованный список: когда брать, когда не брать, что подставлять.

## Установка и перенос
Как ставится сервер, какие файлы и ключи переносятся, чем проверяется.

## Несколько проектов
Как сервер ведет себя при нескольких проектах: общий процесс или отдельный,
что задает проект, какие данные общие.

## Проверка
Команды проверки сервера и ожидаемый результат.

## Связи
Ссылки на карту, state/04-mcp.md, профильные документы.

## Известные проблемы и ограничения
### П-N: Название
- Симптом:
- Причина:
- Ограничение или решение:
- Файлы:

## История изменений
- YYYY-MM-DD: что изменилось и почему
```

Обязательные секции те же, что в [doc_rules.md](../doc_rules.md): `Суть`,
`Связи`, `Известные проблемы и ограничения`, `История изменений`. Полный список
обязательных разделов и требований к детализации задан в
[component-docs.md](../component-docs.md), раздел 5.

---

## Как добавить сервер

1. Добавить запись в `.cursor/mcp.json` по правилам канона.
2. Создать `.doc/harnes/mcp/{server}.md` по шаблону.
3. Создать правило `.cursor/rules/mcp/{server}.mdc` по тому же шаблону: когда, порядок вызова, инструменты и параметры, ошибки, проверка.
4. Добавить строку в главную карту `.cursor/rules/mcp.mdc`, в таблицу состава выше и в [state/04-mcp.md](../state/04-mcp.md).
5. Запустить `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`.
6. Обновить `.codex/config.toml` вручную, он не генерируется.
7. Проверить: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only={server}` и
   `python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py`.
8. Перезагрузить окно клиента, иначе старый процесс останется в памяти.

---

## Проверка

```bash
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=jdocmunch --no-functional

python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py \
  --canonical .cursor/mcp.json --kilo .kilo/kilo.jsonc \
  --expanded .agents/mcp.json --codex-toml .codex/config.toml
```

---

## Связи

- [Точка входа](../index.md) - карта харнеса
- [MCP-серверы](../state/04-mcp.md) - состав, порядок в задачах, Kilo-адаптация
- [Миграция между агентами](../state/13-agent-migration.md) - канон, зеркала, parity
- [MCP-правила](../state/20-mcp-rules.md) - карта, 19 правил серверов и связи с доменными правилами
- [MCP-стек](../state/15-mcp-stack.md) - общие HTTP-серверы, порты, лимиты
- [Правила документации](../doc_rules.md) - стандарт `.doc/` и MCP-маршрут
- [Скрипты](../state/05-scripts.md) - лаунчеры в `.cursor/scripts`

---

## История изменений

- 2026-11-01: каталог `mcp/` закреплен как постоянное место, один сервер равен
  одному файлу; созданы документы на все 19 серверов, подробный `jdocmunch.md`
  перенесен из `state/20-jdocmunch.md`
- 2026-11-01: добавлена главная карта `.cursor/rules/mcp.mdc`, в шаблон
  добавлены разделы установки, переноса и нескольких проектов; документы
  серверов дополнены этими разделами и точными аргументами инструментов
- 2026-11-02: добавлены ссылка на `rules-placement.md`, целевая папка
  `.cursor/rules/mcp/`, проверка `DSH-RULES.md` и предупреждение о рекурсии DSH
- 2026-11-02: добавлена ссылка на инструкцию установки MCP в `component-install.md`
- 2026-11-02: добавлен `codeprism` (20 серверов, 16 включённых): метрики JS, TS
  и Vue, release v0.3.5, документ [`codeprism.md`](../../../.agents/skills/codeprism/docs/mcp/codeprism.md)
- 2026-11-06: добавлен `graphiti` (21 сервер, 17 включённых): временной граф знаний
  на FalkorDB, HTTP на `127.0.0.1:8000/mcp/`, документ [`graphiti.md`](../../../.agents/skills/graphiti/docs/mcp/graphiti.md)
- 2026-11-02: `codeprism` переведен на `codeprism-ai` 0.1.11, PHP и постоянный
  индекс; добавлен скил `.agents/skills/codeprism`, документ обновлен
