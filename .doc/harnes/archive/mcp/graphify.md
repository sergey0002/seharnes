# MCP: graphify (legacy)

> **Статус: legacy.** С 2026-11-02 Graphify не входит в `.cursor/mcp.json` и не
> используется в задачах. Активный сервер - [codegraph](./codegraph.md), его
> правило - [mcp/codegraph.mdc](../../../.cursor/rules/mcp/codegraph.mdc). Ниже
> сохранено описание старого контракта для истории и разбора старых задач.

<!-- meta
type: config
status: actual
updated: 2026-11-01
related: [./README.md, ../state/04-mcp.md]
tags: [harness, mcp, graph]
-->

---

## Суть

AST-граф кода для сообществ, god-узлов и кратчайшего пути между узлами. Один HTTP-процесс на все проекты, проект передается `project_path` в каждом вызове. Берется после CBM, когда нужны связи вне прямого графа вызовов.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/codegraph.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | HTTP, Streamable |
| URL | `http://127.0.0.1:9130/mcp` |
| Служба | `mcp-graphify.service` (user unit), `Restart=always` |
| Рабочий каталог юнита | корень проекта; без `project_path` сервер берет именно его |
| Проект | `project_path=<absolute project root>` в каждом вызове |
| Артефакт | `graphify-out/graph.json`, в git не входит |
| Сборка графа | `uvx --offline --from graphifyy graphify update .` |
| Версия пакета | `0.9.97`, epoch `v0.9.97-s29-g7154a062ba57` |
| Альтернатива | Docker-образ `copytrust-graphify:0.9.97`, тот же принцип `project_path` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `url: http://127.0.0.1:9130/mcp` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

Сервер отдает 10 инструментов. В `alwaysAllow` первые семь, PR-инструменты
доступны, но требуют `gh` и GitHub-remote.

| Инструмент | Вход | Выход |
|---|---|---|
| `graph_stats` | `project_path` | Nodes, Edges, Communities, EXTRACTED/INFERRED/AMBIGUOUS, коммит сборки, предупреждение об устаревании |
| `query_graph` | `question`, `mode` (`bfs`/`dfs`), `depth` 1-6, `token_budget`, `context_filter` | строки `NODE` с файлом, строкой и сообществом, плюс уведомление об обрезке |
| `get_node` | `label` или `node_id`, `project_path` | сигнатура, файл, строка, тип, сообщество, степень; при совпадении имен список кандидатов |
| `get_neighbors` | `label` или `node_id`, `relation_filter`, `token_budget` | входящие и исходящие связи с типом, уверенностью и местом |
| `get_community` | `community_id` (нумерация с нуля), `token_budget` | имя сообщества и его узлы с файлами |
| `god_nodes` | `top_n`, `exclude_hubs_percentile` | самые связные узлы с числом ребер |
| `shortest_path` | `source`, `target`, `max_hops`, `undirected` | путь с типами связей и уверенностью слабейшего шага |
| `list_prs` | `repo`, `base` | открытые PR с CI и импактом по графу |
| `triage_prs` | `repo`, `base` | PR, готовые к ревью, с импактом |
| `get_pr_impact` | `pr_number`, `repo` | файлы, сообщества и число затронутых узлов |

Идентификатор узла: путь в нижнем регистре через `_` плюс символ. Класс
`lib/Objects/Order/Order.php` это `lib_objects_order_order_order`, метод отдельным
узлом вида `.getStatus()`. Неоднозначное имя уточняется формой `path::Symbol`.

---

## Правила использования

1. Передавать `project_path` абсолютным корнем проекта. Без него сервер берет
   проект, на котором стартовал, поэтому ошибки нет, но на общей службе это
   неявный выбор проекта.
2. Брать после CBM, когда нужны сообщества, god-узлы и путь между узлами.
3. Литералы, `.js` и `.tpl` искать `multi-search.sh` или `rg`, не графом.
4. `.doc/` в граф не входит, для задач только Read или `multi-search.sh`.
5. `.tpl` не индексируется: расширения нет в списке поддерживаемых пакета.
   `.sql` не индексируется, пока в среде не установлен `tree_sitter_sql`.

---

## Где граф дает ответ

| Вопрос по задаче | Что брать | Почему graphify |
|---|---|---|
| какие модули связаны с правкой | `get_neighbors`, `shortest_path` | показывает связи вне прямого вызова, включая обратные |
| какие общие компоненты затронет изменение | `god_nodes` | самые связанные узлы дают карту риска регрессии |
| границы модуля и его состав | `get_community` | сообщества считаются по плотности связей, а не по папкам |
| как связаны две подсистемы | `shortest_path` с `undirected` | путь через промежуточные классы и сервисы |
| обзор незнакомого репозитория | `graph_stats`, `god_nodes`, `query_graph` | быстрый вход без чтения кода |
| проверка, что граф не отстал | `graph_stats` | строка `Built at commit` сравнивается с HEAD |

Не решает: поиск литералов и строк, `.tpl`, `.doc/`, точные сигнатуры и правки.
Для этого CBM, Serena, `multi-search.sh` и jdocmunch.

---

## Эксплуатация

### Юнит и лимиты

| Параметр | Значение |
|---|---|
| Юнит | `mcp-graphify.service` |
| MemoryHigh | 2G |
| MemoryMax | 4G |
| CPUQuota | 200% |
| TasksMax | 256 |
| Restart | always |
| Окружение | `GRAPHIFY_MAX_CONTEXTS=8` |
| Запуск | `mcp-shared-server.sh 9130 bash graphify-mcp-serve.sh --multi` |

### Данные

| Что | Путь | Размер |
|---|---|---|
| Граф проекта | `<project>/graphify-out/graph.json` | 12-23 MB на проект |

Артефакт локальный, в git не входит, строится `graphify update .`.

### Диагностика

| Симптом | Причина | Действие |
|---|---|---|
| `graph.json not found` | нет `project_path` или граф не построен | передать абсолютный корень, затем `update` |
| Два `graphify.serve` | клиент держит старый stdio | reload клиента |
| Граф устарел | не было `update` | `graphify update .`, перезапуск `mcp-graphify` |

## Установка и перенос

Установка на машину:

1. Прогреть кеш один раз с сетью: `uvx --from "graphifyy[mcp]" python -c "import mcp, graphify"`.
   Дальше все запуски идут офлайн из `~/.cache/uv`.
2. Проверить пакет: `uvx --offline --from graphifyy graphify --version`.
3. Построить граф проекта: `uvx --offline --from graphifyy graphify update <root>`.
   Граф появляется в `<root>/graphify-out/graph.json`, в git не коммитится.
4. Поставить user unit `~/.config/systemd/user/mcp-graphify.service`:
   `ExecStart` вызывает `.cursor/scripts/mcp-shared-server.sh 9130 bash .cursor/scripts/graphify-mcp-serve.sh --multi`,
   `WorkingDirectory` равен корню проекта, `GRAPHIFY_MAX_CONTEXTS=8`, логи в
   `~/.local/state/mcp-shared/graphify-9130.log`.
5. `systemctl --user daemon-reload && systemctl --user enable --now mcp-graphify`.
6. Добавить запись в `.cursor/mcp.json`: `type: http`, `url: http://127.0.0.1:9130/mcp`,
   `alwaysAllow` на семь инструментов.
7. Разложить конфиг по средам: `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`.
8. Проверить: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=graphify` и
   `graph_stats` с `project_path`.

Перенос на другую машину:

- Копируются лаунчер `.cursor/scripts/graphify-mcp-serve.sh`, скрипт
  `.cursor/scripts/mcp-shared-server.sh`, unit, запись в `.cursor/mcp.json`.
- Граф не переносится: на новой машине он строится `graphify update <root>`,
  артефакт может занимать 12-23 МБ на проект.
- Быстрый вариант для всего стека: `bash .cursor/mcp-stack/export.sh` и
  `bash .cursor/mcp-stack/restore.sh <archive> <root>`.
- Если systemd недоступен, поднимается Docker-вариант:
  `.doc/skil_data/harness-core/graphify-docker/README.md`, порт 7811.

## Несколько проектов

- Один процесс обслуживает все проекты, проект выбирается `project_path` в
  каждом вызове. Отдельный юнит на проект не нужен.
- Контексты графов кешируются LRU, по умолчанию 8 штук (`GRAPHIFY_MAX_CONTEXTS`).
  Больше 8 активных проектов вытесняют самый старый контекст.
- Граф у каждого проекта свой: `<root>/graphify-out/graph.json`. Общих данных нет,
  проекты не смешиваются.
- Новый проект: `graphify update <root>`, затем
  `bash .cursor/mcp-stack/add-project.sh <root>` печатает готовый блок для
  `.cursor/mcp.json`.
- Вызов без `project_path` не падает, а берет проект из `WorkingDirectory` юнита.
  На общей службе это неявный выбор, поэтому `project_path` передается всегда.
- Неверный путь дает явную ошибку
  `graph.json not found: <path>/graphify-out/graph.json`, чужой граф не подставляется.
- После пересборки графа перезапуск юнита не нужен, сервер читает файл заново.
- Проверено на двух проектах: testdeploydocker 24158 узлов, cms 6556 узлов.

## Связи

- [Карта MCP](./README.md) - общий список
- [MCP-серверы](../state/04-mcp.md) - маршрут и правила
- [MCP-стек](../state/15-mcp-stack.md) - юнит 9130, LRU контекстов
- [Инструкция graphify](../../../.cursor/graphify-mcp.md) - вызовы и ограничения
- [Docker-вариант](../../synh_harnes/graphify-docker/README.md) - когда systemd недоступен

---

## Известные проблемы и ограничения

### П-1: Сервер красный, лаунчер завершается с ошибкой

- Симптом: клиент показывает graphify недоступным, `graph.json not found`.
- Причина: граф не построен или лаунчеру не передан путь к артефакту.
- Ограничение или решение: `graphify update .`, затем перезапуск клиента.
  Живость проверяет `test-mcp-servers.mjs`, пустой граф ловит проба `graph_stats`.
- Файлы: `.cursor/scripts/graphify-mcp-serve.sh`, `.agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs`

### П-2: Граф устарел после правок кода

- Симптом: в выдаче старые строки и связи, `graph_stats` пишет
  `graph may be stale`.
- Причина: `update` не запускался, автоиндексации у graphify нет.
- Ограничение или решение: `graphify update .` перед работами по задаче.
  Свежесть видна в `Built at commit`, совпадение с HEAD это норма.
- Файлы: `graphify-out/graph.json`

### П-3: `.sql` в графе нет

- Симптом: `update` пишет `45 .sql file(s) contributed nothing to the graph
  because a dependency is missing: tree_sitter_sql not installed`.
- Причина: в среде запуска нет парсера SQL, расширение поддерживается пакетом.
- Ограничение или решение: установить `graphifyy[sql]` в среду запуска и повторить
  `update`. До установки схему читать через MCP `mysql`.
- Файлы: `sql/**/*.sql`

### П-4: Шаблонов Smarty в графе нет

- Симптом: `.tpl` не находится ни через `query_graph`, ни через `get_node`.
- Причина: расширения `.tpl` нет в списке поддерживаемых, файл пропускается.
- Ограничение или решение: шаблоны искать `rg` и `multi-search.sh`, связи View
  читать Serena. 562 шаблона вне графа.
- Файлы: `templates/**/*.tpl`, `admin/templates/**/*.tpl`

### П-5: `list_prs`, `triage_prs`, `get_pr_impact` отказывают

- Симптом: `gh CLI not found or not authenticated`.
- Причина: инструментам нужен `gh` с авторизацией и GitHub-remote, репозиторий
  живет на GitVerse.
- Ограничение или решение: PR-анализ не используется, задачи и ветки через
  `gototask` и `task-diff`.
- Файлы: `.cursor/mcp.json`

### П-6: Часть файлов дает узлы без символов

- Симптом: `update` пишет `code file(s) yielded no symbols`.
- Причина: разметка, конфиги и тонкие обертки не дают объявлений.
- Ограничение или решение: такие файлы читать через Read, граф по ним не помогает.
- Файлы: `graphify-out/.graphify_build_state.json`

### П-7: Два процесса `graphify.serve`

- Симптом: в `ps` два сервера, ответы расходятся.
- Причина: клиент держит старый stdio-процесс после перехода на HTTP.
- Ограничение или решение: reload окна клиента, один процесс на машину.
- Файлы: `.cursor/mcp.json`

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-01: проверено на живом сервере: 10 инструментов с аргументами и выходом, `project_path` не обязателен, `.tpl` и `.sql` не индексируются, PR-инструменты требуют `gh`; граф пересобран на HEAD
