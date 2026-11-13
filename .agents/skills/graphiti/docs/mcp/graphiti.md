# MCP: graphiti

<!-- meta
type: config
status: actual
updated: 2026-11-09
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/15-mcp-stack.md]
tags: [harness, mcp, graphiti, memory, falkordb, ollama]
-->

## Суть

Graphiti - временной граф знаний: эпизоды, сущности и связи с датами действия.
MCP-сервер даёт агенту долговременную память между сессиями. Сервер работает по
HTTP на `127.0.0.1:8000/mcp/`, хранит граф в FalkorDB (внутри контейнера),
LLM вызывает через OpenAI-совместимый шлюз `ai.starimg.ru` (модель `deepseek-v4.1-flash-1017`),
эмбеддинги считает локальный Ollama (`qwen3-embedding:0.6b` на порту 11434,
1024 измерения, мультиязычная).

## Когда вызывать

Когда нужна память, а не поиск по коду или документации:

- что уже решали по проекту и почему;
- какие ограничения и договорённости называл пользователь;
- как менялись решения во времени.

Не брать для структуры кода (это codebase-memory-mcp и codegraph), для текста
документации (jdocmunch) и для секретов. Поверхность вызова и аргументы:
[правило graphiti](../../../../../.cursor/rules/mcp/graphiti.mdc).

## Конфигурация

| Свойство | Значение |
|---|---|
| Тип | HTTP, MCP endpoint `/mcp/` |
| URL | `http://127.0.0.1:8000/mcp/` |
| Образ | `zepai/knowledge-graph-mcp:1.1.3` |
| База | FalkorDB внутри контейнера `graphiti`, `redis://localhost:6379`, граф `default_db` |
| LLM | OpenAI-совместимый шлюз `ai.starimg.ru`, модель `deepseek-v4.1-flash-1017`, 4096 токенов, режим `json_object` |
| Эмбеддинги | Ollama на `127.0.0.1:11434`, `qwen3-embedding:0.6b`, 1024 измерения, endpoint `/v1/embeddings` |
| Секреты | `.cursor/mcp.env`, ключ `GRAPHITI_LLM_API_KEY` |
| Конфиг сервера | `.cursor/mcp-stack/graphiti/config.yaml` |
| Управление | `.agents/skills/graphiti/scripts/graphiti-stack.sh` |

## Текущие значения

| Параметр | Значение |
|---|---|
| Контейнер сервера | `graphiti` (образ `zepai/knowledge-graph-mcp:1.1.3`) |
| Сервис эмбеддингов | Ollama в WSL, systemd user unit `ollama-qwen.service`, вне Docker |
| Порты хоста | `127.0.0.1:8000` MCP, `127.0.0.1:3000` FalkorDB Browser, `127.0.0.1:6379` FalkorDB, `127.0.0.1:11434` Ollama |
| Порт FalkorDB | `127.0.0.1:6379` (опубликован для FalkorDB Browser) |
| Данные графа | том `falkordb_data` |
| Логи | том `mcp_logs`, `/var/log/graphiti` |
| Модель эмбеддингов | `qwen3-embedding:0.6b`, 1024 измерения, endpoint `/v1/embeddings` |
| Группа по умолчанию | `copytrust-testdeploydocker`, обязательна, общего `main` нет |
| `SEMAPHORE_LIMIT` | `2` |
| Телеметрия | выключена, `GRAPHITI_TELEMETRY_ENABLED=false` |
| Переменные окружения | `GRAPHITI_LLM_API_KEY`, `GRAPHITI_LLM_API_URL`, `GRAPHITI_LLM_MODEL`, `GRAPHITI_STRUCTURED_OUTPUT_MODE`, `EMBEDDER_API_URL`, `EMBEDDER_API_KEY`, `EMBEDDER_MODEL`, `EMBEDDER_DIMENSIONS`, `GRAPHITI_GROUP_ID`, `GRAPHITI_SEMAPHORE_LIMIT`, `FALKORDB_URI`, `FALKORDB_PASSWORD`, `FALKORDB_DATABASE` |

Секреты в документ не попадают, здесь только имена переменных.

## Приоритет настроек

Сервер собирает конфиг из четырёх источников, старший перекрывает младший
(`config/schema.py`, `settings_customise_sources`):

1. аргументы CLI (`--model`, `--group-id` и другие);
2. переменные окружения (`EMBEDDER_API_URL`, `GRAPHITI_GROUP_ID`), вложенные через `__`;
3. `config.yaml`;
4. `.env` внутри контейнера;
5. значения по умолчанию в Pydantic-моделях.

Практический вывод: `config.yaml` должен содержать `${VAR:default}` для того, что
меняется по проекту. Жёстко записанное значение в YAML отключает переменную
окружения для этого поля, потому что env подставляется в поле уже после разбора YAML.
Именно так раньше терялся `EMBEDDER_API_URL`: в YAML был жёсткий `http://127.0.0.1:7997`.

## Полный справочник настроек

### server

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `transport` | `http` \| `stdio` \| `sse` | `http` | Транспорт MCP. `sse` устарел |
| `host` | строка | `127.0.0.1` | Адрес прослушивания |
| `port` | число | `8000` | Порт MCP |

### llm

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `provider` | `openai` \| `azure_openai` \| `anthropic` \| `gemini` \| `groq` | `openai` | Провайдер модели |
| `model` | строка | `deepseek-v4.1-flash-1017` | Имя модели |
| `temperature` | float или пусто | пусто | Не задано для reasoning-моделей |
| `max_tokens` | число | `4096` | Предел ответа модели |
| `structured_output_mode` | `json_schema` \| `json_object` | `json_schema` | `json_object` подставляет схему в промпт для провайдеров без строгой схемы |

Провайдеры LLM и их ключи:

| Провайдер | Ключи |
|---|---|
| `openai` | `api_key`, `api_url`, `organization_id` |
| `azure_openai` | `api_key`, `api_url`, `api_version`, `deployment_name`, `use_azure_ad` |
| `anthropic` | `api_key`, `api_url`, `max_retries` |
| `gemini` | `api_key`, `project_id`, `location` |
| `groq` | `api_key`, `api_url` |

### embedder

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `provider` | `openai` \| `azure_openai` \| `gemini` \| `voyage` | `openai` | Провайдер эмбеддингов; Ollama подключается как `openai` через `api_url` |
| `model` | строка | `text-embedding-3-small` | Имя модели эмбеддингов |
| `dimensions` | число | `1536` | Размерность вектора; должна совпадать с моделью |

Провайдеры эмбеддингов: `openai` (`api_key`, `api_url`, `organization_id`),
`azure_openai` (как у LLM), `gemini` (`api_key`, `project_id`, `location`),
`voyage` (`api_key`, `api_url`, `model`).

Смена модели или размерности на непустом графе требует переиндексации: старые
векторы несовместимы, поэтому граф очищают и наполняют заново.

### database

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `provider` | `falkordb` \| `neo4j` | `falkordb` | Хранилище графа |

`falkordb`: `uri`, `username`, `password`, `database`.
`neo4j`: `uri`, `username`, `password`, `database`, `use_parallel_runtime`.

### graphiti

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `group_id` | строка | `main` в коде, у проекта своё имя | Пространство графа; в FalkorDB отдельный граф на каждое значение |
| `episode_id_prefix` | строка | пусто | Префикс UUID эпизодов |
| `user_id` | строка | `mcp_user` | Идентификатор пользователя для операций |
| `entity_types` | список `{name, description}` | 10 типов из конфига | Типы сущностей для извлечения |
| `edge_types` | список `{name, description}` | пусто, используются стандартные | Типы связей |
| `edge_type_map` | список `{source, target, edge_types}` | пусто | Ограничение связей по парам типов, `Entity` как шаблон |

### Корневой уровень

| Ключ | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `destroy_graph` | bool | `false` | Очистить граф при старте; включать только осознанно |
| `SEMAPHORE_LIMIT` (env) | число | `10` в коде, `2` в проекте | Сколько эпизодов обрабатывать параллельно |

`SEMAPHORE_LIMIT` считается по лимиту провайдера: 3 RPM - 1-2, 60 RPM - 5-8,
500 RPM - 10-15, 5000 RPM - 20-50. Слишком высокое значение даёт ошибки 429,
слишком низкое - простой квоты.

### Аргументы CLI

`--config`, `--transport`, `--host`, `--port`, `--llm-provider`,
`--embedder-provider`, `--database-provider`, `--model`, `--small-model`,
`--temperature`, `--embedder-model`, `--group-id`, `--user-id`, `--destroy-graph`.

`--config` задаёт путь к YAML и пишется в `CONFIG_PATH`. Путь по умолчанию внутри
образа - `/app/mcp/config/config.yaml`, в проекте он смонтирован из
`.cursor/mcp-stack/graphiti/config.yaml`.

### Типы сущностей по умолчанию

В конфиге включены 10 типов: `Preference`, `Requirement`, `Procedure`, `Location`,
`Event`, `Organization`, `Document`, `Topic`, `Person`, `Object`.
`Requirement` хранит `project_name` и `description`; `Preference` намеренно имеет
низкий порог срабатывания и перекрывает остальные типы. Типы без своих полей
(`Preference`, `Procedure` и другие) хранят только имя и сводку.

### Типы связей

Если `edge_types` и `edge_type_map` пусты, сервер работает со стандартными
связями graphiti-core (`RELATES_TO` и подобные). Встроенные расширенные модели
образа: `RelatesTo`, `MentionedIn`, `WorksFor` (поле `role`), `LocatedAt`,
`ParticipatesIn`, `Owns`, `Requires`. Они подключаются, только если перечислены
в `edge_types`.

## Инструменты и аргументы

| Инструмент | Аргументы | Результат |
|---|---|---|
| `get_status` | - | Состояние сервера и подключения к базе |
| `add_memory` | `name`, `episode_body`, `group_id`, `source`, `source_description`, `uuid`, `reference_time`, `excluded_entity_types`, `custom_extraction_instructions`, `previous_episode_uuids`, `update_communities`, `saga`, `saga_previous_episode_uuid` | Эпизод в очереди |
| `add_triplet` | `source_node_name`, `edge_name`, `fact`, `target_node_name`, `group_id`, `source_node_uuid`, `target_node_uuid` | Факт без извлечения |
| `search_nodes` | `query`, `group_ids`, `max_nodes` (10), `entity_types`, `center_node_uuid` | Сущности |
| `search_memory_facts` | `query`, `group_ids`, `max_facts` (10), `center_node_uuid`, `edge_types`, `valid_at_after`, `valid_at_before`, `invalid_at_after`, `invalid_at_before` | Факты с датами |
| `summarize_saga` | `saga_name`, `group_id` | Сводка цепочки эпизодов |
| `build_communities` | `group_ids` | Сообщества и сводки |
| `get_episode_entities` | `episode_uuids`, `group_id` | Сущности и факты эпизода |
| `get_entity_edge` | `uuid`, `group_id` | Один факт |
| `get_episodes` | `group_ids`, `max_episodes` (10) | Последние эпизоды |
| `delete_entity_edge` | `uuid`, `group_id` | Удаление факта, требует подтверждения |
| `delete_episode` | `uuid`, `group_id` | Удаление эпизода с каскадом, требует подтверждения |
| `clear_graph` | `group_ids` | Очистка группы, требует подтверждения |

Всего 13 инструментов. `alwaysAllow` в каноне: чтение, `add_memory`, `add_triplet`,
`summarize_saga`, `build_communities`. Удаление и очистка требуют подтверждения.

### Детали аргументов

`add_memory.source`: `text` (обычный текст), `json` (строка JSON, не словарь),
`message` (реплики диалога). Для `json` используется обычное JSON-экранирование.

`add_memory.reference_time`: дата события в ISO-8601. Без часового пояса считается
UTC. Без значения берётся текущее время. Это двувременная модель: дата приёма
эпизода и дата события хранятся раздельно.

`add_memory.excluded_entity_types`: исключает указанные типы из извлечения только
для этого эпизода.

`add_memory.custom_extraction_instructions`: текстовое указание модели извлечения
для одного эпизода.

`add_memory.previous_episode_uuids`: явная история для контекста, перекрывает
автоматический подбор предыдущих эпизодов.

`add_memory.update_communities`: `true` обновляет сводки сообществ после эпизода.
Дороже, по умолчанию `false`.

`add_memory.saga` и `saga_previous_episode_uuid`: имя цепочки эпизодов и UUID
предыдущего звена для порядка.

`add_triplet`: пишет связь напрямую, без извлечения LLM. Узлы находятся или
создаются по имени, дубли по имени схлопываются, эмбеддинги считаются. Годится
для точного факта, когда автоматическое извлечение искажает смысл.

`search_memory_facts`: `valid_at_*` и `invalid_at_*` фильтруют по времени действия
факта. Разбор дат - через `parse_reference_time`, неверная дата возвращает ошибку.

`get_episodes`: возвращает до `max_episodes` эпизодов, самый свежий первым.

`build_communities`: дорогая операция по всем сущностям группы, запускать по
необходимости, а не после каждой записи.

`clear_graph`: без `group_ids` чистит граф по умолчанию. Опасная операция.

### Очередь и конкурентность

`add_memory` возвращает ответ сразу, извлечение идёт в фоне. Эпизоды одной группы
обрабатываются последовательно (`services/queue_service.py`), поэтому свежий факт
может не найтись сразу после записи. Число одновременно обрабатываемых эпизодов
ограничено `SEMAPHORE_LIMIT`.

## Правила использования

1. Перед записью вызвать `search_memory_facts`, чтобы не дублировать факт.
2. Писать в `add_memory` короткий самодостаточный эпизод: объект, решение,
   причина. Один эпизод - одно событие.
3. Указывать `reference_time`, если факт относится к прошлой дате.
4. Использовать один `group_id` на проект. В FalkorDB каждый `group_id` живёт в
   отдельном графе, поэтому граф и есть база проекта. Значение `main` не
   используется: оно общее для всех проектов.
5. Не писать секреты, токены и персональные данные клиентов.
6. После `add_memory` помнить про очередь: поиск сразу может не найти факт.
7. Удаление и очистку выполнять только по явной просьбе пользователя.

## Установка и перенос

```bash
# 1. образы
docker pull zepai/knowledge-graph-mcp:1.1.3

# 2. секреты и проектное имя группы
# добавить GRAPHITI_* и EMBEDDER_* в .cursor/mcp.env по образцу .cursor/mcp.env.example

# 3. запуск через compose-обёртку (сервер, FalkorDB; эмбеддинги через Ollama)
bash .agents/skills/graphiti/scripts/graphiti-stack.sh up

# 4. проверка
curl http://127.0.0.1:8000/health
bash .agents/skills/graphiti/scripts/graphiti-stack.sh verify
```

`graphiti-stack.sh` понимает команды `up`, `down`, `restart`, `status`, `logs`,
`verify`. Секреты берутся из `.cursor/mcp.env`. Стек слушает только `127.0.0.1`.

Переносятся: запись в `.cursor/mcp.json`, `.cursor/mcp-stack/graphiti/`,
`.agents/skills/graphiti/scripts/graphiti-stack.sh`, имена `GRAPHITI_*` и `EMBEDDER_*`, правило и
документ. Тома данных при переносе не копируются, граф создаётся заново.
Эмбеддинги обслуживает сервис Ollama на порту 11434.

## Несколько проектов

Один стек обслуживает все проекты. Проект задаётся `group_id` в каждом вызове.
Имя группы проекта записывается в `.cursor/mcp.env` в `GRAPHITI_GROUP_ID`, например
`copytrust-testdeploydocker` и `copytrust-cms`. FalkorDB хранит каждый `group_id` в
отдельном графе, поэтому у проекта своя база без отдельного контейнера. Отдельный
контейнер на проект не нужен и не создаётся.

`GRAPHITI_GROUP_ID` обязателен и не имеет общего дефолта. Пустое значение останавливает
запись, чтобы данные не попали в чужой граф. Конфиг сервера (`config.yaml`) и compose
остаются одни на все проекты; проектные значения приходят из env-файла проекта.

## Миграция проекта

При переносе проекта в новый каталог/машину Graphiti мигрирует как часть harness-кода,
но не как данные:

| Что | Переносится | Корректно | Примечание |
|---|---|---|---|
| `config.yaml`, `docker-compose.yml`, `graphiti-stack.sh` | да, через копирование `.cursor/mcp-stack/` | да | все пути через `${VAR:default}`, жёстких путей проекта нет |
| `mcp.env` (с `GRAPHITI_GROUP_ID`) | нет | да | секреты и проектная группа не тащатся; на Target создаётся из примера |
| Данные графа (FalkorDB том) | нет | да | при переносе не копируются, граф заполняется заново под новым `group_id` |
| Процесс/контейнер | один на все проекты | да | порт 8000 общий, проект отличается только `group_id` |

При миграции через `export.sh`/`restore.sh` каталог `.cursor/mcp-stack/graphiti/` теперь
включается в архив, поэтому конфиг не теряется. При миграции через `new-project` kit
`mcp.env` не копируется — новый проект получает свой `GRAPHITI_GROUP_ID` равный имени
своего каталога (скрипт `rebase_project.ps1` подставляет его автоматически).

Важно: контейнер назван нейтрально (`graphiti`), без привязки к имени исходного проекта.

## Проверка

```bash
curl http://127.0.0.1:8000/health
docker run --rm --network host python:3.12-slim python3 -c "
import json, urllib.request
url='http://127.0.0.1:8000/mcp'
headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
req=urllib.request.Request(url, data=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1'}}}).encode(), headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    sid = r.headers.get('mcp-session-id')
headers2 = dict(headers); headers2['Mcp-Session-Id'] = sid
req=urllib.request.Request(url, data=json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_status','arguments':{}}}).encode(), headers=headers2)
with urllib.request.urlopen(req, timeout=10) as r:
    print(r.read()[:500].decode())
"
```

Ожидаемый результат: `health` отвечает, `tools/list` возвращает 13 инструментов,
`get_status` показывает `status: ok` и подключение к FalkorDB.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - конвенция и состав
- [Состояние MCP](../../../../../.doc/harnes/state/04-mcp.md) - состав и порядок
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - порты и общий HTTP-слой
- [Правило graphiti](../../../../../.cursor/rules/mcp/graphiti.mdc) - поверхность вызова

## Известные проблемы и ограничения

### П-1: Нет аутентификации

- Симптом: любой локальный процесс может читать и удалять граф.
- Причина: reference-реализация сервера без авторизации.
- Ограничение или решение: порт слушает только `127.0.0.1`, наружу не публикуется.

### П-2: Запись асинхронна

- Симптом: сразу после `add_memory` поиск не находит факт.
- Причина: извлечение сущностей и фактов идёт через очередь.
- Ограничение или решение: подождать обработку и повторить поиск, проверить
  `get_episodes`.

### П-3: Зависимость от внешнего LLM и локальных эмбеддингов

- Симптом: `get_status` показывает `ok`, но эпизоды падают с `Connection error`.
- Причина: недоступен шлюз `ai.starimg.ru` или сервис эмбеддингов Ollama на порту 11434;
  адрес эмбеддера в `config.yaml` не совпадает с env.
- Ограничение или решение: проверить доступность сервиса по `${EMBEDDER_API_URL}`,
  ключ `GRAPHITI_LLM_API_KEY` и что в `config.yaml` стоит `${EMBEDDER_API_URL:...}`,
  а не жёсткий адрес.

### П-4: Смена модели эмбеддингов

- Симптом: после смены модели или размерности поиск перестаёт находить факты.
- Причина: старые векторы несовместимы с новой размерностью.
- Ограничение или решение: очистить граф и наполнить заново, `dimensions` должен
  совпадать с реальной размерностью модели.

## История изменений

- 2026-11-09: Graphiti переведён на Ollama `qwen3-embedding:0.6b` (1024 измерения, порт 11434);
  compose и `config.yaml` больше не ссылаются на FastEmbed 7997. Ollama работает как systemd user unit
  `ollama-qwen.service` с автозапуском.
- 2026-11-07: подтверждена активная конфигурация FastEmbed на порту 7997 (`http://host.docker.internal:7997/v1`).
  Уточнена история: в проекте Ollama отсутствует; записи от 2026-11-06 о попытке перехода на Ollama
  сохраняются как архивный след черновой настройки, текущий рабочий стек использует FastEmbed.
- 2026-11-06: добавлен полный справочник 13 инструментов с аргументами, всех ключей
  `config.yaml`, переменных окружения, приоритета источников настроек и типов сущностей
  и связей. Раздел "Текущие значения" приведен к фактическому стеку.
- 2026-11-06: архивная запись: черновая попытка настройки на Ollama `qwen3-embedding:0.6b`
  (в проекте не используется, отменена в пользу FastEmbed).
- 2026-11-06: убран общий дефолт `main`, проект задает свой `group_id`.
- 2026-11-06: контейнер назван `graphiti`; тома данных перенесены под проектные имена.
- 2026-11-06: `export.sh` теперь включает `.cursor/mcp-stack/graphiti/` в архив;
  `rebase_project.ps1` при создании `mcp.env` подставляет `GRAPHITI_GROUP_ID` =
  имя каталога нового проекта.
- 2026-11-06: все 13 инструментов Graphiti MCP протестированы на реальном содержимом
  `.doc/architecture/index.md` (запись, поиск фактов и узлов, триплет, саги,
  сообщества, удаление, очистка) — все работают.
- 2026-11-06: сервер установлен. Образ `zepai/knowledge-graph-mcp:1.1.3`,
  FalkorDB внутри контейнера, LLM `deepseek-v4.1-flash-1017` через `ai.starimg.ru`.
  Контейнер named `graphiti`.
