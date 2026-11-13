# MCP: codebase-memory-mcp

<!-- meta
type: config
status: actual
updated: 2026-11-10
related: [../../../../../.cursor/rules/mcp.mdc, ../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/15-mcp-stack.md]
tags: [harness, mcp, graph, memory]
-->

---

## Суть

Граф кода на всю машину: классы, функции, вызовы, импорты, маршруты, SQL-таблицы,
межсервисные связи и векторный индекс для смыслового поиска. Один HTTP-процесс
обслуживает все проекты, проект выбирается параметром `project`. Это первый
инструмент маршрута по коду, до codegraph и Serena.

Как вызывать методы, какие аргументы передавать и когда брать сервер: правило
[`.cursor/rules/mcp/codebase-memory-mcp.mdc`](../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc).
Здесь конфигурация, область индексации, эксплуатация и установка.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/codebase-memory-mcp.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | HTTP, Streamable HTTP через `mcp-proxy --stateless` |
| URL | `http://127.0.0.1:9131/mcp` |
| Служба | `mcp-codebase-memory.service` |
| Бинарник | `~/.local/bin/codebase-memory-mcp`, версия 0.12.1 |
| Лаунчер | `.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.sh --ui=false` |
| Проект | параметр `project`, имя из `list_projects` |
| Автоиндексация | выключена, `auto_index=false`, `auto_index_limit=50000` |
| Наблюдатель | включён: `auto_watch=true`, `watcher_enabled=true`, `watch_non_git=false` |
| Демон | `codebase-memory-mcp --cbm-daemon-internal`, живёт дольше клиента |
| Лимит памяти | юнит 6 ГБ, бюджет процесса около 3 ГБ |

Канон конфигурации один, `.cursor/mcp.json`, блок `codebase-memory-mcp`.
Клиентские файлы (`.kilo/kilo.jsonc`, `.codex/mcp.json`, `.agents/mcp_config.json`)
генерируются `sync-agent-views.sh` и вручную не правятся. Legacy `.antigravity/` и
`.gemini/` удалены.

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `url: http://127.0.0.1:9131/mcp` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

В версии 0.12.1 сервер отдаёт 17 методов:

`index_repository`, `list_projects`, `index_status`, `check_index_coverage`,
`get_graph_schema`, `get_architecture`, `search_graph`, `search_code`,
`trace_path`, `get_code_snippet`, `get_file_outline`, `query_graph`,
`compare_graphs`, `detect_changes`, `manage_adr`, `ingest_traces`, `delete_project`.

В `alwaysAllow` канона 10 методов только на чтение: `list_projects`,
`index_status`, `get_graph_schema`, `get_architecture`, `search_graph`,
`search_code`, `trace_path`, `get_code_snippet`, `query_graph`, `detect_changes`.
`index_repository` и `delete_project` требуют подтверждения. Урезанная
поверхность доступна флагом запуска `--tool-profile=analysis|scout`.

Аргументы, режимы и правила выбора метода - в правиле
[`mcp/codebase-memory-mcp.mdc`](../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc).

---

## Режимы индексации

| Режим | Что делает | Когда |
|---|---|---|
| `fast` | только структура, без семантики | перед `git push` |
| `moderate` | структура плюс семантика с фильтрацией | нужен `semantic_query` |
| `full` | все проходы плюс семантика | после крупного рефакторинга |
| `cross-repo-intelligence` | связывает сервисы, `target_projects` | межпроектные связи |

Дополнительно: `persistence: true` пишет снимок графа в
`.codebase-memory/graph.db.zst` внутри репозитория, `async: true` запускает
индексацию в демоне, `status: true` с тем же `repo_path` возвращает состояние
задачи.

---

## Что попадает в индекс

Область: корень git-репозитория. Исключения берутся из `.gitignore`, из
`.git/info/exclude` и из `.cbmignore` в корне. Факт: CBM 0.12.1 читает
`.git/info/exclude` тоже.

В этом репозитории действуют три источника:

1. `.gitignore`: `node_modules/`, `vendor/`, `templates_c/`, `cache/`, `.env*`,
   `frontend/dist/`, `/tools/docker-test/dump*.sql` и прочее.
2. `.git/info/exclude`: `/.cursor/`, `/.codex/`, `/.kilo/`, `/.agents/`,
   `/.serena/`, `/.playwright-mcp/`, `/.doc/`,
   `/graphify-out/`, `/.codegraph/`, `/sourcegraph-local/`, `/tools/docker-dev/`.
3. `.cbmignore`: `graphify-out/`, `.codegraph/` и `backups/`.

Состояние индекса этого проекта на 2026-11-01:

| Показатель | Значение |
|---|---|
| Файлов в индексе | 3787 |
| Узлов / рёбер | 45 823 / 204 736 |
| Векторов для смыслового поиска | 29 128 |
| Языки | PHP 1481, JavaScript 1110, HTML 180, CSS 146, SQL 45, Vue 42, YAML 8, Bash 1 |
| Не проиндексировано по правилам | 1353 файла |
| Разобрано частично | 144 файла |
| Не разобрано совсем | 73 файла |

Метки узлов: `Function`, `Method`, `File`, `Variable`, `Module`, `Class`,
`Section`, `Folder`, `Table`, `Interface`, `EnvVar`, `Route`, `Resource`, `View`,
`Process`. Типы рёбер: `CALLS`, `USAGE`, `DEFINES`, `WRITES`, `DEFINES_METHOD`,
`SIMILAR_TO`, `CONTAINS_FILE`, `IMPORTS`, `OVERRIDE`, `INHERITS`, `MENTIONS`,
`THROWS`, `TESTS`, `IMPLEMENTS`, `HTTP_CALLS`.

`.doc/` в индекс не входит: для документации есть jdocmunch. Проекты
`td-docs-arch` и `td-docs-tasks` индексируются отдельно и вручную, наблюдатель их
не трогает.

---

## Как обновляется индекс

Инкремент опирается на таблицы `file_hashes` (`rel_path`, `sha256`, `mtime_ns`,
`size`) и `lsp_surface` (`surface_sha`, `defs_json`, `ref_bloom`): неизменённые
файлы не переразбираются.

| Механизм | Состояние | Что делает |
|---|---|---|
| Автоиндексация при подключении | выключена | полная переиндексация при старте клиента не запускается |
| Наблюдатель файлов | включён | на изменение в git-репозитории запускает обновление в демоне, `strategy=git` |
| Ручной вызов | основной путь | `index_repository` перед `git push`, `mode=fast` |
| Runtime-трейсы | по требованию | `ingest_traces` добавляет наблюдаемые вызовы |
| ADR | по требованию | `manage_adr` хранит записи решений |

Наблюдатель не гарантирует свежесть. Прогон может завершиться ошибкой, тогда
`indexed_at` стареет, а граф отстаёт от рабочего дерева. Признак свежести только
`indexed_at` из `index_status`, а не факт включённого наблюдателя.

Порядок перед push: тесты, commit, `index_repository(mode="fast")`, push. Полный
свод: [`.cursor/rules/cbm-index-before-push.mdc`](../../../../../.cursor/rules/cbm-index-before-push.mdc).

---

## Данные и эксплуатация

### Юнит и лимиты

| Параметр | Значение |
|---|---|
| Юнит | `mcp-codebase-memory.service` |
| MemoryHigh | 4G |
| MemoryMax | 6G |
| CPUQuota | 300% |
| TasksMax | 256 |
| Restart | always |
| Окружение | `CBM_CACHE_DIR=~/.local/share/mcp-stack/codebase-memory`, `CBM_MEM_BUDGET_MB=4096`, `CBM_WORKERS=6` |

Общее для HTTP-стека: `PATH` с nvm и `~/.local/bin`, логи в
`~/.local/state/mcp-shared/`, `WantedBy=default.target`.

### Данные

| Что | Путь | Размер |
|---|---|---|
| Индексы CBM | `~/.local/share/mcp-stack/codebase-memory` (старый `~/.cache/codebase-memory-mcp` симлинк сюда) | около 290 MB |
| Проекты | testdeploydocker 218 MB, cms 38 MB, `td-docs-arch` 6 MB, `td-docs-tasks` 30 MB | у каждого свой файл SQLite |
| Лог демона | `~/.local/share/mcp-stack/codebase-memory/logs/cbm-daemon.log` | растёт |
| Снимок для команды | `<repo>/.codebase-memory/graph.db.zst` | по `persistence: true` |

Таблицы основной БД: `nodes`, `edges`, `file_hashes`, `index_coverage`,
`index_coverage_meta`, `lsp_surface`, `node_vectors`, `token_vectors`,
`project_summaries`, `doc_link_candidates`, `doc_link_unresolved`,
`observed_calls`, `observed_paths`, `projects`, `store_meta`.

---

## Установка и перенос

### Бинарник

Linux и WSL: нужен архив `codebase-memory-mcp-ui-linux-amd64`, он же дает
встроенный UI. Windows: `codebase-memory-mcp-ui-windows-amd64.zip`, путь
`%LOCALAPPDATA%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe`.

```bash
VER=v0.12.1
mkdir -p ~/.local/bin
curl -fsSL -o /tmp/cbm-ui.tar.gz \
  "https://github.com/DeusData/codebase-memory-mcp/releases/download/${VER}/codebase-memory-mcp-ui-linux-amd64.tar.gz"
tar -xzf /tmp/cbm-ui.tar.gz -C /tmp
mv -f /tmp/codebase-memory-mcp ~/.local/bin/
chmod +x ~/.local/bin/codebase-memory-mcp
codebase-memory-mcp --version
```

Обновление и удаление: `codebase-memory-mcp update`,
`codebase-memory-mcp uninstall` (конфиги агентов, без бинарника и кэша).

### Новый проект

```bash
cat .gitignore > .cbmignore 2>/dev/null || true
cat .git/info/exclude >> .cbmignore 2>/dev/null || true
printf '\n*.min.js\n*.min.css\n*.map\n*.sql\n*.db*\nscripts/plugins/\ndompdf/\nstorage/\ncache/\n' >> .cbmignore
codebase-memory-mcp cli index_repository --repo-path /path/to/project --mode fast
codebase-memory-mcp cli list_projects
```

Затем в `.cursor/rules/mcp/codebase-memory-mcp.mdc` подставить имя проекта, если оно
отличается от правила `home-newuser-projects-<slug>`. Путь всегда абсолютный
корень git-репозитория, не подкаталог.

### Сброс индекса

```bash
rm -rf ~/.local/share/mcp-stack/codebase-memory/<slug>.db
```

Разумно, когда файл вырос из-за прошлых ошибок, например от индексации
домашнего каталога или раздутого `.cbmignore`.

---

## Веб-интерфейс cbm-ui

`cbm-ui` показывает граф в браузере на `http://localhost:9749`. Агентам он не
нужен, им достаточно MCP. Автозапуск отключён: каждый экземпляр резервирует
`budget_mb = total_ram / 2`, то есть около 7 ГБ при 14 ГБ памяти.

```bash
.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh
# открыть http://localhost:9749
tmux kill-session -t cbm-ui
```

Лаунчер поднимает UI только при `CBM_ENABLE_UI=1`.

---

## CLI

CLI работает без клиента и удобен для проверки фактов.

```bash
codebase-memory-mcp cli list_projects
codebase-memory-mcp cli --json index_status --project home-newuser-projects-copytrust-testdeploydocker
codebase-memory-mcp cli index_repository --repo-path /path/to/project --mode fast
codebase-memory-mcp cli search_graph --project <project> --query "order service" --limit 5
codebase-memory-mcp cli check_index_coverage --project <project> --scopes .doc
```

Передача сырого JSON в аргументе объявлена устаревшей, лучше флаги, `--args-file`
или stdin. `--json` печатает полный конверт MCP.

---

## Диагностика

| Симптом | Причина | Действие |
|---|---|---|
| Граф не содержит свежих правок | автоиндексация выключена, наблюдатель мог упасть | проверить `indexed_at` в `index_status`, затем `index_repository` |
| Два CBM в списке серверов | клиент не перезагружен, профиль DSH содержит проектные клиенты | reload, проверить профиль DSH |
| CBM показывает старый путь | база хранит старый slug | `index_repository` на актуальный корень |
| CBM занимает много памяти | бюджет `total_ram / 2` | не держать UI постоянно, следить за `.cbmignore` |
| `project` не находится | проект не проиндексирован | `list_projects`, затем `index_repository` |
| Пустой `search_graph` | неверный `project` или индекс отсутствует | `list_projects`, `index_status` |

---

## Несколько проектов

- Один HTTP-процесс на машину, проект выбирается параметром `project` из `list_projects`.
- Индекс хранится отдельным файлом на проект; `index_repository` обновляет только указанный проект.
- Добавление проекта: `.cursor/mcp-stack/add-project.sh`, затем `index_repository` и проверка `index_status`.
- Никогда не передавать проект другого репозитория: графы не смешиваются.

## Связи

- [Карта MCP](../../../../../.cursor/rules/mcp.mdc) - место сервера в общем списке
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - состав и общие правила
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - юнит, порт, лимиты, данные
- [Правило вызова](../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc) - методы, аргументы, когда брать
- [Индексация перед push](../../../../../.cursor/rules/cbm-index-before-push.mdc) - обязательный порядок
- [codegraph](../../../codegraph/docs/mcp/codegraph.md) - второй граф кода: исходник, вызывающие, blast radius
- [serena](../../../serena/docs/mcp/serena.md) - символы и references

---

## Известные проблемы и ограничения

### П-1: Наблюдатель падает, индекс стареет

- Симптом: `indexed_at` в `index_status` старше рабочего дерева, в
  `cbm-daemon.log` повторяется `daemon.index.result status=failed` и
  `watcher.index.err rc=-1`.
- Причина: прогон обрывается на `pipeline.abort_reason=semantic_inputs_changed`,
  когда файлы меняются во время индексации, и на `parse_timeout` для файла
  `scripts/plugins/vue-inputmask/phone-codes/phone-us.js` размером 38 МБ.
- Решение: перед важной работой сверять `indexed_at` и запускать
  `index_repository(mode="fast")` вручную; тяжёлый файл закрывать `.cbmignore`.
- Файлы: `.cursor/rules/cbm-index-before-push.mdc`, `.cbmignore`.

### П-2: Часть файлов не разбирается

- Симптом: `index_status` показывает 144 частично разобранных и 73 неразобранных
  файла, в основном Smarty `.tpl` и старые PHP-страницы в `admin/`.
- Причина: разборщик не покрывает Smarty-синтаксис и нестандартный legacy-код.
- Ограничение: для таких файлов поиск идет через `search_code` по литералам,
  `multi-search.sh` и codegraph, а не через символы.
- Файлы: `index_status`, `check_index_coverage`.

### П-3: `.cbmignore` в репозитории короткий

- Симптом: ожидаемых по документации правил в `.cbmignore` нет.
- Причина: почти всё закрывает `.git/info/exclude`, который CBM тоже читает.
- Ограничение: правило не читает `.git/info/exclude` в старых версиях, поэтому
  при смене версии проверить `check_index_coverage --scopes .doc`.
- Файлы: `.cbmignore`, `.git/info/exclude`.

---

## История изменений

- 2026-11-10: ссылка на удалённую карту документов заменена канонической картой MCP; discovery-описание отделяет код от документации и схемы БД.
- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-01: сюда перенесена эксплуатационная документация из
  `.cursor/codebase-memory-mcp.md` (установка, UI, CLI, перенос, диагностика);
  уточнены факты: 17 методов, чтение `.git/info/exclude`, реальный `.cbmignore`,
  состояние наблюдателя и покрытия индекса
