# MCP-стек: общие HTTP-серверы и проектная изоляция

<!-- meta
type: architecture
status: actual
updated: 2026-11-07
related: [../index.md, ./04-mcp.md, ./11-dev-environment.md, ./13-agent-migration.md, ./14-project-migration.md, ../mcp/README.md, ../tests.md]
tags: [harness, mcp, systemd, codegraph, cbm, serena, multi-project]
-->

---

## Суть

Состав серверов, инструменты, флаги и правила вызова - [04-mcp.md](./04-mcp.md).
Здесь только эксплуатация общего HTTP-слоя: юниты, порты, лимиты, данные, перенос.

CBM, Serena и CodePrism вынесены из клиентов в HTTP-службы systemd. Клиенты
разделяют процесс соответствующей службы. Другие MCP, в том числе CodeGraph,
могут запускать отдельные stdio-процессы для клиентов.

```
Kilo / Cursor / dsh ── HTTP ──> 9131 codebase-memory (один процесс, все проекты по project)
                           └───> 9121 / 9122 serena (один процесс на проект)
                          └───> 9201 codeprism (один процесс для testdeploydocker)
Kilo / Cursor / dsh ── stdio ─> codegraph (локальный индекс .codegraph, автосинк)
```

Правило: CBM обслуживает все проекты одним процессом, serena не может
(активный проект глобальный), поэтому у serena один юнит на проект. CodeGraph
работает по stdio и не требует общего порта. Legacy graphify (9130) остановлен.
CodePrism хранит активный проект в процессе и требует отдельную службу и базу
для каждого проекта. Codex использует stdio-мост к HTTP-службе проекта.

---

## 1. Раскладка

| Сервер | Endpoint | Область | Unit | Документ |
|---|---|---|---|---|
| codebase-memory | `http://127.0.0.1:9131/mcp` | все проекты, проект в `project` | `mcp-codebase-memory.service` | [codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) |
| codegraph | stdio | один проект на индекс, `projectPath` для другого | - | [codegraph.md](../../../.agents/skills/codegraph/docs/mcp/codegraph.md) |
| codeprism testdeploydocker | `http://127.0.0.1:9201/mcp` | один проект, один процесс для клиентов | `mcp-codeprism-<sha256 пути>.service` | [codeprism.md](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) |
| graphiti | `http://127.0.0.1:8000/mcp/` | все проекты, проект в `group_id` | `graphiti-stack.service` (oneshot), контейнер `graphiti`, Ollama `ollama-qwen.service` | [graphiti.md](../../../.agents/skills/graphiti/docs/mcp/graphiti.md) |
| serena testdeploydocker | `http://127.0.0.1:9121/mcp` | один проект | `mcp-serena-testdeploydocker.service` | [serena.md](../../../.agents/skills/serena/docs/mcp/serena.md) |
| serena cms | `http://127.0.0.1:9122/mcp` | один проект | `mcp-serena-cms.service` | [serena.md](../../../.agents/skills/serena/docs/mcp/serena.md) |
| dsh web | `:3080`, `:3081` | клиенты | `dsh-web.service`, `dsh-web-cms.service` | - |

Порты: 9131 CBM, 9121-9199 serena, 9201 CodePrism testdeploydocker, 3080/3081 dsh, 8000 graphiti,
3000 FalkorDB Browser, 11434 Ollama. 9130 graphify - legacy, остановлен.

---

## 2. Юниты и лимиты

| Unit | MemoryHigh | MemoryMax | CPUQuota | TasksMax | Restart |
|---|---|---|---|---|---|
| `mcp-codebase-memory` | 4G | 6G | 300% | 256 | always |
| `mcp-serena-<slug>` | 2G | 4G | 200% | 512 | always |
| `mcp-codeprism-<sha256 пути>` | - | - | - | - | on-failure |
| `graphiti-stack` | - | - | - | - | oneshot, `Restart` нет |

Общее: `PATH` с nvm и `~/.local/bin`, логи в `~/.local/state/mcp-shared/`,
`WantedBy=default.target`.

`graphiti-stack.service` поднимает Graphiti при старте автоматически:
`ExecStart=graphiti-stack.sh up`, `ExecStop=graphiti-stack.sh down`, `RemainAfterExit=yes`,
лог `~/.local/state/graphiti-stack.log`. Юнит не может требовать `docker.service`:
в user-скоупе такого юнита нет, поэтому в `After=` только `network-online.target`.
До 2026-11-06 graphiti был включён в каноне, но не запускался: порт 8000 пуст,
контейнеров нет, MCP-клиент тратил время на попытки подключения.

Окружение и команда запуска каждого юнита описаны в файле сервера:
[codebase-memory](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md).
`dsh-web.service` ждёт порт `9131`, `After=`/`Wants=` на CBM;
`dsh-web-cms.service` ждёт docker.socket.

---

## 3. Скрипты

| Скрипт | Роль |
|---|---|
| `.tools/scripts/mcp-shared-server.sh <port> <cmd...>` | `mcp-proxy` из uv-кеша, fallback `uvx`, `--stateless` |
| `.tools/scripts/wait-for-ports.sh <port...>` | Ждёт TCP-порты, таймаут `MCP_WAIT_TIMEOUT` |
| `.agents/skills/codegraph/scripts/codegraph-mcp.sh` | stdio-запуск CodeGraph, поиск CLI в PATH и nvm |
| `.agents/skills/codegraph/scripts/codegraph-ui.sh` | Локальный просмотрщик CodeGraph |
| `.cursor/mcp-stack/add-project.sh <root>` | Печатает инструкции для CBM и CodeGraph, проверяет `.codegraph` |
| `.cursor/mcp-stack/add-serena.sh <root> [port]` | Создает юнит serena на проект |
| `.cursor/mcp-stack/add-codeprism.py <root> <port> --output-dir <dir>` | Создает unit CodePrism для проекта, без запуска службы |
| `.cursor/mcp-stack/verify.sh [root]` | Юниты, CBM `list_projects`, serena, codegraph `status`, проект и готовность индекса CodePrism |
| `.cursor/mcp-stack/export.sh [out.tar.gz]` | Архив стека одного проекта |
| `.cursor/mcp-stack/restore.sh <archive> [root] [--no-start]` | Разворачивает стек, ставит машинные юниты и serena под новый slug |
| `.agents/skills/graphiti/scripts/graphiti-stack.sh [up|down|status|logs|verify]` | Управляет Graphiti контейнером: FalkorDB и MCP; эмбеддинги считает Ollama на 11434 |

---

## 4. Данные

| Что | Путь | Размер |
|---|---|---|
| Канон и секреты | `.cursor/mcp.json`, `.cursor/mcp.env` | мало |
| Логи | `~/.local/state/mcp-shared/` | растут |
| Граф Graphiti | том `graphiti_falkordb_data` | растёт с числом эпизодов |
| Эмбеддинги Ollama | `~/.local/ollama-models/` | около 640 МБ на модель `qwen3-embedding:0.6b` |

Пути данных каждого сервера и размеры: [codebase-memory](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md),
[codegraph](../../../.agents/skills/codegraph/docs/mcp/codegraph.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md).

---

## 5. Клиенты

Канон `.cursor/mcp.json` содержит `type: http` для CBM, serena и CodePrism, `codegraph`
подключен как stdio. `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` раскладывает по средам.

| Среда | Формат |
|---|---|
| Kilo | `type: remote` + `url` |
| DSH | `transport: streamable-http` + `url` |
| Codex, Antigravity, Gemini, Agents | `url` и `serverUrl` |
| Antigravity на Windows | отдельный `%USERPROFILE%\.gemini\config\mcp_config.json`: HTTP как URL, stdio через `wsl.exe ... bash -lc` |
| Codex serena | тонкий `mcp-proxy` на 9121 (config.toml) |
| Codex CodePrism | stdio-мост читает HTTP-адрес из канона проекта и использует offline-кеш `mcp-proxy` |

Важно для DSH: профиль `~/.dsh/profiles/web/cordis.patch.yml` не должен содержать
проектных MCP-клиентов, иначе они дублируются с проектным патчем. Профиль держит
только UI, LLM и tools.

---

## 6. Новый проект

```bash
# 1. индекс codegraph
codegraph init --yes /path/to/project

# 2. CBM: один общий сервер 9131
#    index_repository(repo_path=/path/to/project)

# 3. serena: свой юнит на проект
bash .cursor/mcp-stack/add-serena.sh /path/to/project 9123

# 4. codegraph уже в .cursor/mcp.json, путь задает .agents/skills/codegraph/scripts/codegraph-mcp.sh
# 5. разложить по средам
cd /path/to/project && bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh

# 6. проверить
bash .cursor/mcp-stack/verify.sh /path/to/project
```

CBM: `index_repository(repo_path=<root>)`, затем `project` из `list_projects` в
каждом вызове. CodeGraph: индекс в `<root>/.codegraph/`, обертка запускает его с
корнем проекта, для другого проекта передается `projectPath`. Свежесть CodeGraph
проверяется `codegraph status`: `pendingChanges` и `lastIndexed`. Legacy Graphify
(`project_path`, `graph.json`) не используется.

---

## 7. Перенос на другую машину

```bash
bash .cursor/mcp-stack/export.sh
bash .cursor/mcp-stack/restore.sh stack.tar.gz /path/to/project [--no-start]
```

Архив: канон, скрипты, юниты CBM и serena, данные CBM и serena, `MANIFEST`.
Индекс CodeGraph и виртуальное окружение CodePrism не переносятся. Архив может
содержать секреты из `.cursor/mcp.env`, поэтому его нужно хранить защищённо.

Restore:

1. ставит `mcp-codebase-memory.service`, только если его еще нет; существующие
   машинные юниты не перезаписывает;
2. ставит serena-юнит под новым slug и при занятом порте выбирает свободный;
3. правит абсолютные пути только в новых юнитах и файлах проекта;
4. БД CBM остается со старым slug, после переноса нужен `index_repository`;
5. CodeGraph на новой машине поднимается `codegraph init --yes`.
6. CodePrism в восстановленном каноне отключается, адрес исходного сервера удаляется;
   отдельную службу и порт целевого проекта нужно настроить и проверить перед включением.

---

## 8. Проверка

```bash
bash .cursor/mcp-stack/verify.sh /home/newuser/projects/copytrust/testdeploydocker
```

Проверяет CBM `list_projects`, serena-юнит и порт, codegraph `status`, а также
корень проекта и готовность графа CodePrism через `get_graph_stats`.

```bash
ss -ltnp | grep -E ':9131|:9121|:9122'
ps -eo pid,ppid,rss,args | grep -E '[c]odebase-memory-mcp|[m]cp-proxy --host|[s]erena start-mcp-server|[c]odegraph.*serve'
```

Норма: один `mcp-proxy` и один child на CBM; по одному serena на проект; один
CodeGraph-демон на проект. 9130 graphify в норме отсутствует.

### Результаты проверки 2026-10-30 (тогда graphify был активен)

| Проверка | Результат |
|---|---|
| graphify, CBM, serena: tools/list | OK |
| graphify: один процесс, два проекта | 24137 узлов testdeploydocker, 10065 cms, без пути ошибка |
| CBM: `list_projects` | 4 проекта, у каждого свой файл SQLite |
| serena: активный проект | 9121 testdeploydocker, 9122 cms |
| Процессы | 1 graphify.serve, 1 CBM, 2 serena, 3 mcp-proxy |
| Синк сред | parity, mcp-views, parity-fresh passed |
| Перенос проекта | export/restore в песочницу, машинные юниты не перезаписаны, serena переименована и порт подобран |
| Полный smoke MCP | shared OK; context7 и playwright timeout из-за недоступного npm registry; mysql SKIP, relay 3306 занят живым клиентом |

---

## 9. Диагностика

| Симптом | Причина | Действие |
|---|---|---|
| Порт занят при restore | старый сервис жив | restore сам берет следующий для serena |
| Antigravity не видит MCP | LS на Windows читает `%USERPROFILE%\.gemini\config\mcp_config.json`, а синк писал только WSL-симлинк | `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`, затем Reload Window |
| Antigravity: stdio-сервер сразу падает | в Windows-конфиге Linux-команда без обертки | проверить `antigravity_mcp_config.windows-wsl.json`: `command` должен быть `wsl.exe` |

Диагностика отдельного сервера: [codebase-memory](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md),
[codegraph](../../../.agents/skills/codegraph/docs/mcp/codegraph.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md).

---

## Связи

- [Точка входа](../index.md)
- [MCP-серверы](./04-mcp.md)
- [Dev-окружение](./11-dev-environment.md)
- [Миграция между агентами](./13-agent-migration.md)
- [Миграция между проектами](./14-project-migration.md)
- [Аудит дублей MCP](./24-mcp-duplicates-audit.md) - копии по проекту и по клиенту, база на проект, план перевода на общий HTTP

---

## Известные проблемы и ограничения

- Клиенты, запущенные до перехода на HTTP, держат stdio-child до reload.
- `restore.sh` не создает службу CodePrism: сервер целевого проекта настраивают отдельно и проверяют его корень до включения клиента.
- Перенос kit отключает CodePrism в известных представлениях целевого проекта. Автоматическая регистрация службы CodePrism и сквозной перенос во все среды не подтверждены. Существующий `.codex/config.toml` целевого проекта и некоторые DSH-patch останавливают перенос до записи; нестандартные конфигурации требуют отдельной проверки.
- Ограничения конкретных серверов перенесены в их файлы: [codebase-memory](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md),
  [codegraph](../../../.agents/skills/codegraph/docs/mcp/codegraph.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md), [graphiti](../../../.agents/skills/graphiti/docs/mcp/graphiti.md).
- Legacy graphify (юнит 9130) остановлен; в стек не входит.

---

## История изменений

- 2026-11-09: Graphiti переведён с FastEmbed 7997 (`e5-small`, 384) на Ollama 11434 (`qwen3-embedding:0.6b`, 1024); Ollama работает как systemd user unit `ollama-qwen.service` с автозапуском.
- 2026-11-07: CodePrism testdeploydocker переведен на локальную HTTP-службу 9201, общую для клиентов; добавлены отдельный unit на проект и stdio-мост Codex.
- 2026-11-06: добавлен стек Graphiti: MCP на 8000, FalkorDB в контейнере `graphiti`, эмбеддинги через существующий FastEmbed API (`fastembed-api:7997`), запуск через `docker run`, контейнер переименован в `graphiti`
- 2026-11-06: у Graphiti убран общий дефолт `main`: проект задаёт свой `group_id` в `.cursor/mcp.env`, FalkorDB хранит его отдельным графом, то есть у проекта своя база без отдельного контейнера.
- 2026-11-06: Graphiti получил автозапуск: юнит `graphiti-stack.service` (oneshot, `up` при старте, `down` при остановке), контейнеры `graphiti*`, лог `graphiti-stack.log`. Без `Requires=docker.service`: в user-скоупе такой юнит отсутствует. Аудит дублей MCP - [24-mcp-duplicates-audit](./24-mcp-duplicates-audit.md).
- 2026-11-02: graphify выведен из стека, 9130 остановлен; активный граф - codegraph stdio, CBM остается на 9131
- 2026-10-30: graphify сведен в один multi-project процесс на 9130; CBM один на 9131; serena по юниту на проект
- 2026-10-30: Serena переведена на systemd-юниты и HTTP (9121/9122)
- 2026-10-30: CBM 0.12.1, 4 проекта, `.cbmignore`, лимит 6G
- 2026-10-30: создан после перевода graphify и CBM на общие HTTP-серверы
- 2026-11-01: детали юнитов, данных и диагностики перенесены в `.doc/harnes/mcp/`, здесь остался общий HTTP-слой и процедуры
- 2026-11-01: уточнено поведение graphify без `project_path`: не ошибка, а проект из `WorkingDirectory` юнита; добавлена проверка свежести через `graph_stats`
