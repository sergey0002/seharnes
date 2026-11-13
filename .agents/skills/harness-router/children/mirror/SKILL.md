---
name: mirror
description: >-
  Зеркало харнеса: один JSON на один файл правил, скила, конфига или скрипта, граф
  связей и просмотрщик в существующей панели. Разбор детерминированный, склейка
  блоков возвращает исходный файл байт в байт, смысл и связи дописывает агент.
  Use when the user says зеркало харнеса, карта харнеса, harness mirror,
  собери граф скилов, визуализируй харнес, покажи связи скилов.
---

# Harness Mirror

Один файл харнеса - один JSON. Скрипт отвечает за структуру, хеши, обратимость и связи по литералам. Агент дописывает описание, жизненный цикл, источники правды и связи, которых нет в тексте.

Подробности, быстрый старт и все команды: [references/implementation.md](./references/implementation.md). Операционные сценарии, автозапуск и диагностика: [references/operations.md](./references/operations.md). Нормативный формат: [references/node-format.md](./references/node-format.md), машинная схема: [assets/harness-node.schema.json](./assets/harness-node.schema.json). Краткое описание без ссылок: [README.md](./README.md).

## Область

Правила, скилы, конфиги, скрипты и MCP-серверы канона. Продуктовый код, задачи и документация не входят: `.doc/` в индекс не попадает и на граф не влияет. MCP-сервер это синтетический узел из `.cursor/mcp.json`: имя, транспорт, команда и имена переменных, без значений.

Канон задаётся adapter-файлом или аргументом. По умолчанию: `.cursor/rules`, `.agents/skills`, `.cursor/scripts`, `.cursor/mcp-stack`.

## Adapters

| Adapter | Смысл |
|---|---|
| `CANON_ROOT` | каталог канона |
| `DATA_DIR` | узлы, граф, кеш, просмотрщик |
| `VIEWER_URL` | адрес просмотра |
| `SYNC`, `PARITY_CHECK` | существующие механизмы проекта, скилл их не заменяет |

Значения проекта лежат в `ADAPTERS.local.md`, он помечен `transferable: false` и не переносится.

## Шаги

### H1. Скан

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan --include-mirrors --include-dsh
```

Скрипт считает хеш, пропускает неизменённое, режет файл на блоки, проверяет обратимость, находит литеральные ссылки и пишет узел. Смысловые поля остаются пустыми, `analysis.status = pending`. Задания агенту заранее не генерируются.

### H2. Задание агенту

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py prompt --node skill:task-doc
```

Агент читает исходный файл и возвращает только анализ: `description`, `lifecycle`, `sources_of_truth`, `relations` с `origin: agent`, `global_relations`. Текст блоков не переписывается.

### H3. Применение

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py apply --node skill:task-doc --json analysis.json
```

Проверяются блок, якорь, тип связи, происхождение и путь цели. Ошибка не меняет узел.

### H4. Сборка и просмотр

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py build
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py serve --port 8090
```

`build` пишет `graph.json`, добавляет ребра `mirrors` с состоянием `equal` или `drift` и копирует просмотрщик. Кнопка панели «Пересобрать граф харнеса» запускает `rebuild`: `scan` по изменённым файлам, затем `build`. `serve` поднимает просмотр с записью на `127.0.0.1` и API правки. Панель проекта отдаёт тот же просмотрщик только на чтение.

Карточки показывают иерархию папок и файлов, связи идут дугами. Режим `связи по типам` раскладывает карточки колонками по типу, там связи видно целиком; галочка `только связанные` убирает карточки без связей. По умолчанию видны только узлы канона, поэтому один скил не повторяется по средам; зеркала включаются галочкой.

### H5. Правка блока

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py get --node rule:doc-rules
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py set --node rule:doc-rules --block b003 --content new-section.md
```

Писать можно только в канон. Старая версия узла уходит в `nodes/.history/`, файл пересобирается и проверяется, при расхождении исходник восстанавливается. То же доступно из браузера через `PUT /api/node` при запущенном `serve`. Зеркала пересобирает существующий `sync-agent-views.sh`.

### H6. Проверка

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py check
```

Уникальность идентификаторов, хеши, обратимость, якоря, цели связей, согласованность проекций.

## Среды

Скил работает в Cursor, Kilo Code, Codex, Antigravity, Gemini, Agents и DeepSeek Harness без правки файлов: только Python 3 stdlib, без сети, MCP, базы и модели. Среда определяется по префиксу пути.

Зеркала не дублируют анализ: при совпадении `content_sha256` узел наследует смысл канона. Свой механизм переноса скилл не создаёт, синхронизация и паритет остаются за проектом.

## Видимость правил

`visibility` строит матрицу `inline`, `glob`, `index`, `skill`, `choice` или `none` для каждой среды. Команда завершается ошибкой, если правило с `gate: true` не inline или правило с `attach: glob` потеряло автоматический или сгенерированный glob-trigger. `check` включает те же инварианты, а `build` добавляет поле `injection` к узлам канонических правил.

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility --summary
```

## Ограничения

- Связи только по явным упоминаниям.
- Правка идёт только в канон; зеркала пересобирает `sync-agent-views.sh`.
- Без шага H2 смысловой слой пустой.
- Файлы секретов и файлы с похожими на токены значениями не разбираются.

## Связи

- [README](./README.md) - быстрый старт, команды, маршруты, диагностика
- [Устройство](./references/implementation.md) - полное описание команд, данных и проверок
- [Формат узла](./references/node-format.md) - поля и инварианты
- [Панель](./references/panel-integration.md) - статический просмотр
