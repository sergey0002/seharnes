# jDocMunch MCP: индекс документации

<!-- meta
type: config
status: actual
updated: 2026-11-10
related: [../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/13-agent-migration.md, ../../../../../.doc/harnes/state/14-project-migration.md, ../../../../../.doc/harnes/state/15-mcp-stack.md, ../../../../../.doc/harnes/state/05-scripts.md, ../../../../../.cursor/rules/mcp.mdc]
tags: [harness, mcp, docs, search, embeddings, jdocmunch]
-->

---

## Суть

jDocMunch индексирует Markdown-документацию на уровне секций и отдает ее агенту по
идентификаторам: поиск, оглавление, содержимое секции, связи и ссылки. Один общий
индекс на машину в `~/.doc-index`, ключ `owner/name`, поэтому проекты не плодят
отдельные процессы. Транспорт stdio: один процесс на клиента, проект выбирается
параметром `repo` в каждом вызове. Локальный индекс этого проекта:
`local/testdeploy-arch`, 1235 документов и 19107 секций из `.doc/architecture`,
`.doc/harnes`, `.doc/tasks` и `.doc/web`. Для агента это обязательный первый шаг
поиска и чтения документации, правило:
[`.cursor/rules/mcp/jdocmunch.mdc`](../../../../../.cursor/rules/mcp/jdocmunch.mdc).
Канонический лаунчер: `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh`.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/jdocmunch.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Как устроено

### Транспорт и процесс

| Свойство | Значение |
|---|---|
| Транспорт | stdio, `serve` без флагов http/port |
| Процесс | один на клиента (Cursor, Kilo, Codex, DSH, Antigravity), не на проект |
| Версия | `jdocmunch-mcp 1.150.1` (uv tool, `~/.local/bin/jdocmunch-mcp`) |
| Источник | `jgravelle/jdocmunch-mcp`, https://github.com/jgravelle/jdocmunch-mcp |
| Инструментов | 64, схема около 15647 токенов |
| Проект | обязательный `repo` или `repo_group` в поиске |

Эмбеддинги отключены с 2026-11-03. Модель не загружается, векторный sidecar не
строится, память процессом почти не расходуется. Поиск лексический, BM25. Общего
HTTP-процесса у сервера нет, один процесс на клиента.

### Лаунчер и пути

`.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh` - канон. Зеркала скилов получают копию через
`sync-agent-views.sh`, руками они не правятся.

Что делает лаунчер:

1. `PROJECT` находит поиском вверх от своего расположения до каталога с `.cursor` или
   `.git`, поэтому один и тот же файл работает из `.agents/skills/jdocmunch/scripts`
   и после переноса в другой проект.
2. `DOCROOT` по умолчанию `PROJECT/.doc`, переопределяется `JDOCMUNCH_DOCROOT`.
3. `DOC_INDEX_PATH` по умолчанию `~/.doc-index`, переопределяется окружением.
4. Handle репозитория выводит из `source_root` в индексе: сначала точное
   совпадение, затем самый глубокий вложенный корень. Если индекса нет, падает на
   `local/<имя каталога проекта>`.
5. Эмбеддинги выключены, модель и кеш не задаются. Индексация идет с
   `--embeddings off`, векторный sidecar не создается.

Служебные режимы:

```bash
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --repo      # handle для поиска
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --status    # что проиндексировано
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index     # обновить индекс
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh serve       # так запускает MCP-клиент
```

### Хранилище индекса

```
~/.doc-index/
  _groups.jsonc                  группы репозиториев
  _savings.json                  сводка экономии
  telemetry.db                   события ранжирования, если включена телеметрия
  local/<name>.json              основной индекс: doc_paths, sections, file_hashes
  local/<name>.related.json      граф ссылок и родителей
  local/<name>.postings.jsonl    BM25 postings
  local/<name>.summary.json      краткая сводка для doc_list_repos
  local/.corpus_claims/          какой набор документов закреплен за индексом
```

Основной индекс хранит `source_root`, `head_sha`, `source_dirty`,
`sha_certified`, `corpus_selection`, `worktree_lineage_key`. По этим полям видно,
из какого корня и какого состояния git собраны результаты.

### Эмбеддинги отключены

Эмбеддинги выключены 2026-11-03. Модель, кеш `~/.cache/fastembed` и sidecar
`testdeploy-arch.embeddings.jsonl` удалены. Индекс строится с
`--embeddings off`, поиск идет по BM25.

2026-11-09 проверен альтернативный векторизатор Ollama `qwen3-embedding:0.6b`
(1024 измерения, OpenAI-compatible endpoint). Замер на двух стратифицированных
корпусах подтвердил прежнее направление: архитектура выигрывает от векторов,
задачи и точные термины проигрывают. Векторы не включены. Отчет и скрипты:
`.doc/skil_data/jdocmunch/benchmark/README.md`.

## Бенчмарк поиска

Замер 2026-11-03: 22 запроса, 19.5 тыс. секций, попадание считается по документу
в топ-10. Эталоны заданы вручную, поэтому цифры показывают направление.

| Режим | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Среднее время |
|---|---|---|---|---|---|
| lexical, без эмбеддингов | 0.23 | 0.59 | 0.73 | 0.44 | 72 мс |
| hybrid, вес 0.2 | 0.27 | 0.55 | 0.68 | 0.43 | 273 мс |
| hybrid, вес 0.3 | 0.27 | 0.55 | 0.59 | 0.41 | 207 мс |
| hybrid, вес 0.5 (по умолчанию) | 0.27 | 0.45 | 0.55 | 0.39 | 205 мс |
| semantic-only | 0.18 | 0.27 | 0.45 | 0.29 | 90 мс |

По категориям, MRR:

| Категория | lexical | hybrid 0.2 | semantic | Вывод |
|---|---|---|---|---|
| Архитектура | 0.48 | 0.57 | 0.55 | эмбеддинги лучше |
| Русские перефразировки | 0.29 | 0.33 | 0.36 | небольшой плюс |
| Точные термины | 0.51 | 0.50 | 0.11 | lexical |
| Задачи | 0.67 | 0.27 | 0.00 | только lexical |

Причина отказа:

- Номер задачи и идентификатор не имеют семантического соседства. `2606`,
  `watch_debounce_ms`, `embedding_stale` модель раскладывает на куски и теряет
  как целое.
- Планы задач почти одинаковы по структуре. Их векторы образуют плотный кластер,
  и косинус не отличает задачу 2606 от 2607.
- Hybrid с весом 0.5 наполовину доверяет семантике и роняет точные попадания.
  Вес 0.2 помогает архитектуре, но задачи все равно проигрывают lexical.
- Semantic-only для задач дал Hit@3 0. Для точных терминов MRR 0.11 против 0.51
  у lexical.

Практический вывод: задачи, номера, тесты и точные термины ищутся лексически.
Для архитектуры и вопросов словами допустим hybrid с весом 0.2, но сейчас
эмбеддингов нет, поэтому все запросы идут лексически.

Полные результаты старого замера утрачены вместе с `.doc/temp/`. Новый замер
2026-11-09, скрипты и результаты лежат в
`.doc/skil_data/jdocmunch/benchmark/`.

### Повторный замер после отключения

2026-11-03, тот же набор из 22 запросов, но индекс пересобран без эмбеддингов и
в документе уже есть раздел про бенчмарк:

| Режим | Hit@1 | Hit@3 | Hit@5 | MRR@10 |
|---|---|---|---|---|
| lexical | 0.32 | 0.64 | 0.73 | 0.50 |
| default, без эмбеддингов | 0.32 | 0.64 | 0.73 | 0.50 |
| semantic-only | 0.00 | 0.00 | 0.00 | 0.00 |

`default` совпадает с lexical, потому что векторов нет и сервер падает на BM25.
`semantic-only` возвращает пустой результат. По категориям lexical: задачи 0.67,
точные термины 0.51, архитектура 0.48, перефразировки 0.45.

Из 22 запросов изменились 2 ранга, оба поднялись на первое место: `что будет если
векторный индекс собран другой моделью` и `как выбрать корпус поиска
документации`. Причина в том, что новый раздел этой документации содержит те же
слова. Поэтому первый замер остается честным сравнением режимов, а повторный
показывает состояние после отключения, а не прирост алгоритма.

### Повторный замер 2026-11-09 на Qwen

Проверен локальный векторизатор Ollama `qwen3-embedding:0.6b`, 1024 измерения,
OpenAI-compatible endpoint `http://127.0.0.1:11434/v1`. Замер на двух
стратифицированных корпусах: архитектура 17 документов и 616 секций, 15
запросов; задачи и точные термины 12 документов и 243 секции, 9 запросов.
Окно эмбеддинга 300 символов. Рабочий индекс не пересобирался.

| Корпус | lexical MRR | hybrid 0.2 MRR | hybrid 0.5 MRR | semantic-only MRR |
|---|---|---|---|---|
| Архитектура | 0.623 | 0.752 | 0.761 | 0.842 |
| Задачи и точные термины | 0.933 | 0.875 | 0.875 | 0.586 |
| Смешанная выборка | 0.739 | 0.798 | 0.804 | 0.746 |

Hit@1 на смешанной выборке: lexical 0.671, hybrid 0.2 0.717, hybrid 0.5 0.675,
semantic-only 0.646.

Вывод не изменился по направлению: архитектура выигрывает от векторов, задачи и
точные термины остаются за lexical. Если векторы включать, безопасный
компромисс это hybrid 0.2. Полная пересборка 29287 секций при 0.6 с на секцию
займет около 5 часов при окне 300 символов. Отчет и скрипты:
`.doc/skil_data/jdocmunch/benchmark/README.md`.

### Индексы на машине

| Handle | Корень | Документы | Секции | Особенность |
|---|---|---|---|---|
| `local/testdeploy-arch` | `.doc` этого проекта | 1255 | 19500 | `architecture`, `harnes`, `tasks`; сгенерированные каталоги отсечены |
| `local/cms-arch` | `cms/.doc/archiecture` | 52 | 946 | полный набор |
| `local/cms-manifest` | `cms/.doc/manifest` | 5 | 89 | полный набор |

Проверка: `bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --status`.

### Группы репозиториев

Файл `~/.doc-index/_groups.jsonc`, инструменты `list_repo_groups` и
`define_repo_group`.

| Группа | Состав | Назначение |
|---|---|---|
| `cms` | `local/cms-arch`, `local/cms-manifest` | только проект cms |
| `all` | все три индекса | вопрос через границы проектов |
| `seinline` | все три индекса | общий слой storage/driver |

Группы сквозные по проектам. Поиск по группе включает чужие индексы, поэтому в
задачах этого проекта используются `repo`, а не `repo_group=all`.

### Corpus

Корпус задается в лаунчере: `architecture harnes tasks web` под `.doc`. Список
файлов строит `find`, отсекая сгенерированные каталоги: `test-runs/`, `tests/`,
`reports/`, `backups/`, `backup-*`, `_jsondoc/`, `_dialogs/`, `dialogs/`, а в
архитектуре дополнительно `business-rules/`, `technical-facts/`, `ui-rules/`.
Из `.doc/web` индексируется только Markdown, то есть операционная документация
панели `web/README.md`; PHP, JS и CSS не попадают. Переопределение:
`JDOCMUNCH_CORPUS="architecture harnes"`.

Итог последней индексации: 1235 документов, 19107 секций, 17.7 МБ текста.
Разбивка: `architecture` 64, `harnes` 268, `tasks` 902, `web` 1.

Особенности инкрементального прогона:

- поле `corpus_selection` в файле индекса осталось старым
  `subset:a7f3b79500b25593:64`, оно не обновляется; фактический набор смотреть в
  `doc_paths`;
- удаленный файл `architecture/deepseek-harness-06-audit.md` остался в индексе,
  потому что инкрементальный прогон не удаляет отсутствующие файлы;
- полная пересборка `--rebuild` очищает и то, и другое, но пересобирает весь
  корпус; эмбеддинги больше не считаются.

---

## Обновление индекса

Индекс обновляется инкрементально и никогда не пересобирается целиком без
причины. Сервер сам ничего не переиндексирует, обновление запускает человек или
фоновый watcher.

Основная команда:

Примеры записи ниже выполняются только по разрешению пользователя. Пустой поиск
не разрешает `--index`, `--rebuild`, `watch-install`, `delete_index`,
`doc_index_repo` или `define_repo_group`. До разрешения доступны диагностика и
прямое чтение известного документа после поискового гейта.

```bash
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index
```

Что делает прогон:

1. собирает список файлов по корпусу `architecture harnes tasks` и отсекает
   сгенерированные каталоги (см. раздел Corpus);
2. сравнивает хеши файлов с записанными в индексе;
3. заново разбирает только изменённые и новые файлы, эмбеддинги не считает;
4. пишет обновлённые `testdeploy-arch.json`, `.related.json`,
   `.postings.jsonl` и `.summary.json` в `~/.doc-index/local/`. Векторный
   sidecar не создается.

### Что делать в каждом случае

| Событие | Команда | Нужен ли `--rebuild` |
|---|---|---|
| Поправил существующий документ | `--index` | нет, обновится только он |
| Добавил новый `.md` в `architecture`, `harnes` или `tasks` | `--index` | нет, файл попадёт по `find` |
| Добавил новый каталог в корпус | `JDOCMUNCH_CORPUS` плюс `--index` | нет |
| Удалил или переименовал документ | `--index` не уберёт старый путь | да, `--index --rebuild` |
| Первый запуск на новой машине | `--index` | нет, индекс создаётся с нуля |
| Изменил `.cursor/mcp.json` | индекс не нужен, нужен Reload Window | нет |

### Сколько это занимает

| Прогон | Время | Когда |
|---|---|---|
| Инкрементальный после правок | 10-60 с | обычная работа, модель не грузится |
| Полная пересборка | зависит от корпуса, эмбеддинги не считаются | чистка удалённых файлов |

Эмбеддинги выключены, поэтому процессор и память почти не расходуются. Раньше
полный прогон с моделью занимал часы и требовал около 4.5 ГБ памяти, теперь
этого нет. Сервер по-прежнему предупреждает, что MCP-клиент может оборвать
большой вызов, поэтому полный прогон запускать из shell.

### Проверка после обновления

```bash
# сколько файлов попадёт в индекс
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --corpus

# сводка по индексам
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --status
```

Через MCP:

| Инструмент | Что показывает |
|---|---|
| `get_index_overview` | `indexed_at`, `doc_count`, `section_count`, `head_sha` |
| `get_recent_changes` | секции в корзинах `edited_uncommitted` и `stale_index` |
| `verify_index` | побайтовая проверка SHA-256 по всем секциям |
| `doc_health_radar` | свежесть, ссылки, сироты, покрытие индекса |

Признаки того, что индекс отстал:

- поиск не находит только что добавленную правку;
- `get_recent_changes` показывает секцию в `edited_uncommitted`;
- `indexed_at` старее правки файла.

### Автоматическое обновление

Есть фоновый watcher: `jdocmunch-mcp watch` в foreground или
`jdocmunch-mcp watch-install` как служба входа. Сейчас служба не установлена,
`get_watch_status` показывает три watchable репозитория. После включения
проверить `watch-status` и убедиться, что watcher обновляет нужный subset, а не
весь `.doc`.

### Что помнить

- Перезапуск редактора после индексации обычно не нужен: сервер читает индекс в
  момент вызова. Если `search_sections` отдаёт 0, а `search_titles` находит
  документы, клиент держит старый индекс в памяти: сделай Reload Window.
  Reload также нужен после смены конфигурации MCP.
- Удалённые файлы и старое поле `corpus_selection` остаются до `--rebuild`, см.
  П-2.
- Индекс сейчас занимает около 150 МБ: граф ссылок 79 МБ, основной JSON 38 МБ,
  postings 11 МБ, terms 18 МБ. Векторного sidecar нет.
- Резервная копия прежнего индекса перед крупными изменениями:
  `.doc/skil_data/jdocmunch/backup/`, каталог вне git.

---

## API / Интерфейс

### Правила вызова

1. Перед поиском назвать проект: `repo: local/testdeploy-arch`. Без `repo` или
   `repo_group` сервер отвечает `Either repo or repo_group is required`.
2. Handle брать из `doc_resolve_repo` или `--repo`, не угадывать.
   `doc_resolve_repo` принимает путь к каталогу `.doc`; путь к корню проекта
   возвращает `found: false`. В Kilo Code Mode handle задавать литералом, резолвер
   вызывать только для проверки источника.
3. В Kilo Code Mode каждый инструмент возвращает JSON-строку. До чтения полей
   ответ разбирать `JSON.parse`; обращение к `results` на строке даёт ложный
   пустой результат. Независимые поиски паковать в `Promise.all`, рабочий шаблон
   в [`mcp/jdocmunch.mdc`](../../../../../.cursor/rules/mcp/jdocmunch.mdc), раздел "Вызов в среде".
4. Ограничение количества задается `max_results`. Аргумент `limit` не
    поддерживается и молча игнорируется с предупреждением.
5. Сначала дешевые вызовы: `search_sections` с `fields`, затем
    `get_section_excerpt`, и только потом `get_section` целиком.
6. Для пачек секций использовать `get_sections` и `get_section_summaries`.

### Выбор корпуса и скорость

Корпус выбирается по смыслу вопроса через `path_glob`, отдельными вызовами:
задачи (`tasks/*`), архитектура (`architecture/*`), харнес (`harnes/*`), MCP
(`harnes/mcp/*`), панель (`web/*`). Полная таблица и правила разбиения запросов
живут в правиле
[`mcp/jdocmunch.mdc`](../../../../../.cursor/rules/mcp/jdocmunch.mdc), раздел
"Выбор корпуса", и здесь не дублируются.

Замер 2026-11-03 на корпусе 19498 секций:

| Сценарий | Время |
|---|---|
| Первый поиск после старта сервера, загрузка модели | 25-60 с |
| Hybrid-поиск после загрузки | 0.4-0.6 с |
| Lexical-only поиск | около 0.15 с |

Медленный только первый вызов на процесс. Таймаут клиента на 60 с в этот момент
не означает ошибку: запрос завершается, повторный вызов идет по загруженной
модели. `path_glob` проверен на `tasks/*`, `architecture/*`, `harnes/*` и
`harnes/mcp/*`: выдача остается в заданном префиксе.

### Семьи инструментов

| Семья | Ключевые инструменты | Когда |
|---|---|---|
| Индекс и проекты | `doc_list_repos`, `doc_resolve_repo`, `get_index_overview`, `list_docs`, `get_doc` | узнать, что проиндексировано и под каким handle |
| Индексация | `index_local`, `doc_index_repo`, `delete_index`, `verify_index`, `check_embedding_drift` | обслуживание индекса |
| Структура | `get_toc`, `get_toc_tree`, `get_document_outline`, `count_sections`, `search_titles`, `get_all_roles`, `get_all_tags` | навигация без чтения текста |
| Поиск | `search_sections` | гибридный BM25 плюс семантика, основной вход |
| Чтение | `get_section`, `get_sections`, `get_section_context`, `get_section_excerpt`, `get_section_excerpts`, `get_section_summary`, `get_section_summaries`, `describe_section`, `get_section_path`, `get_section_descendants`, `section_neighbors` | достать тело, контекст или соседей |
| Связи | `get_backlinks`, `get_related_sections`, `get_section_blast_radius`, `check_section_delete_safe`, `get_section_diff`, `get_recent_changes`, `find_similar_sections`, `get_tutorial_path` | кто ссылается, что сломается, что устарело |
| Здоровье | `get_doc_health`, `doc_health_radar`, `diff_doc_health_radar`, `get_doc_pr_risk_profile`, `get_broken_links`, `get_orphan_sections`, `get_stale_pages`, `get_wiki_stats` | диагностика документации |
| Термины | `lookup_term`, `list_terms` | глоссарий из жирных определений в тексте |
| OpenAPI | `find_endpoint`, `list_endpoints_by_tag`, `find_operations_using_schema`, `get_schema_graph` | если в корпусе есть спецификации |
| Код | `get_doc_coverage`, `list_undocumented_symbols`, `link_code_to_symbols`, `resolve_related_code_repos` | мост к jcodemunch, сейчас без пары |
| Служебное | `list_repo_groups`, `define_repo_group`, `tune_weights`, `analyze_perf`, `get_session_stats`, `get_watch_status`, `jdocmunch_guide`, `finalize_handoff`, `find_code_examples` | настройка и отчеты |

### Типовые маршруты

Поиск по домену задачи:

```
search_sections(repo, query, max_results, fields=[id,title,doc_path,_score])
get_section_context(repo, section_id)
get_sections(repo, section_ids)
```

Ориентация в документе: `get_document_outline` перед открытием файла, затем
`get_section` по нужному заголовку.

Проверка термина: `lookup_term` ищет только точное совпадение с записью
глоссария. Общий словарь проекта он не заменяет.

---

## Конфигурация

### Переменные окружения

| Переменная | Значение в проекте | Назначение |
|---|---|---|
| `DOC_INDEX_PATH` | `~/.doc-index` | корень хранилища индексов |
| `JDOCMUNCH_DOCROOT` | не задан | корень документации для `--index` |
| `JDOCMUNCH_INDEX_NAME` | не задан | имя индекса в `local/` |
| `JDOCMUNCH_REPO` | не задан | принудительный handle |
| `JDOCMUNCH_CORPUS` | `architecture harnes tasks` | какие подкаталоги `.doc` индексировать |
| `JDOCMUNCH_PERF_TELEMETRY` | не задан | `1` включает телеметрию для `tune_weights` |
| `JDOCMUNCH_RESPONSE_MAX_BYTES` | не задан | потолок ответа, по умолчанию 1 МиБ |
| `JDOCMUNCH_OCR` | не задан | `1` вместе с `--ocr` включает распознавание сканов |

Переменные `JDOCMUNCH_EMBEDDING_PROVIDER`, `JDOCMUNCH_FASTEMBED_MODEL`,
`JDOCMUNCH_FASTEMBED_CACHE` и `JDOCMUNCH_EMBED_CHARS` больше не задаются:
эмбеддинги отключены, модель и кеш удалены.

### Файлы по средам

| Среда | Файл | Что записано |
|---|---|---|
| Cursor | `.cursor/mcp.json` | `${workspaceFolder}/.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh serve` |
| Kilo | `.kilo/kilo.jsonc` | абсолютный путь к канону, генерируется синком |
| Codex JSON | `.codex/mcp.json` | `${workspaceFolder}/.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh` |
| Codex TOML | `.codex/config.toml` | ведется вручную, путь к канону, `startup_timeout_sec = 120` |
| Antigravity, Agents | `.agents/mcp.json`, `.agents/mcp_config.json` | представления, генерируются, раскрытые абсолютные пути |
| Antigravity Windows | `.doc/skil_data/harness-core/antigravity_mcp_config.windows-wsl.json` | запуск через `wsl.exe -- bash -lc` |
| DeepSeek Harness | `.dsh/project.patch.yml` | `mcp-client-jdocmunch`, генерируется синком |
| Отдельный пул скриптов | нет | скрипты MCP лежат в `scripts/` скилов, системные утилиты в `.tools/scripts` |

`alwaysAllow` содержит `doc_list_repos`, `doc_resolve_repo`, `search_sections`,
`get_section`, `get_sections`, `get_doc`, `list_docs`, `get_toc_tree`,
`get_backlinks`, `get_wiki_stats`.

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: bash ${workspaceFolder}/.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh serve` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Примеры

```bash
# Что проиндексировано
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --status

# Handle проекта
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --repo

# Обновить индекс после правок документации
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index

# Полная пересборка для чистки удалённых файлов
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index --rebuild

# Сколько файлов попадет в индекс
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --corpus

# Только архитектура и харнес
JDOCMUNCH_CORPUS="architecture harnes" bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index
```

```bash
# Проверка MCP-регистрации без полного прогона
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=jdocmunch --no-functional

# Сверка MCP-набора по всем средам
python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py \
  --canonical .cursor/mcp.json --kilo .kilo/kilo.jsonc \
  --expanded .agents/mcp.json --codex-toml .codex/config.toml
```

---

## Диагностика

`doc_health_radar` по `local/testdeploy-arch` на 2026-11-01 после расширения корпуса:
сводная оценка 90.4, класс A.

| Ось | Оценка | Сырые данные |
|---|---|---|
| `link_integrity` | 71.58 | 469 битых ссылок на 16.5 тыс. секций |
| `orphan_health` | 71.77 | 2329 секций без входящих ссылок |
| `structural_integrity` | 99.33 | 11 предупреждений: 6 проглатанных блоков, 5 пропусков уровней |
| `embedding_coverage` | 100 | все секции |
| `role_coverage` | 100 | 0 секций без роли |
| `freshness` | 100 | все секции свежие относительно снимка индекса |

Состав по ролям: `concept` 15875, `example` 197, `troubleshooting` 162,
`reference` 108, `api` 78, `changelog` 34, `how_to` 27, `tutorial` 13, `faq` 8.
Теги задач `ct-2193`, `ct-2194`, `ct-2195`, `ct-2196`, `ct-2244` дают по 14
секций. Глоссарий: 23 термина.

Что проверять при подозрении на устаревание:

| Инструмент | Ответ |
|---|---|
| `get_index_overview` | дата индексации, `head_sha`, `source_dirty`, `sha_certified` |
| `get_recent_changes` | секции в корзинах `edited_uncommitted` и `stale_index` |
| `verify_index` | побайтовая проверка SHA-256 по всем секциям |
| `get_stale_pages` | wiki-страницы, чьи источники изменились на диске |
| `get_watch_status` | активен ли фоновый обновлятор |

Текущее состояние `get_watch_status`: служба `jdocmunch-watch` не установлена,
три репозитория помечены как watchable.

---

## Установка и перенос

- Установка: Python-зависимости MCP в venv/launcher; индекс строится `bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index`.
- Перенос: скопировать `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh` и запись `jdocmunch`; индекс пересобрать на новой машине.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=jdocmunch`.

## Миграция и изоляция

Канон и зеркала:

1. Правка только в `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh` и `.cursor/mcp.json`.
2. `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` пересобирает Kilo, Codex JSON,
   Antigravity, Gemini, Agents, Windows-конфиг и `.dsh/project.patch.yml`.
3. `.codex/config.toml` правится вручную, затем проверяется
   `verify_mcp_views.py`.
4. После смены конфига нужен Reload Window, иначе клиент держит старый процесс.

Перенос в другой проект или на другую машину не требует правок лаунчера:

| Что | Как выбирается |
|---|---|
| Корень проекта | из расположения скрипта |
| Корень документации | `JDOCMUNCH_DOCROOT`, иначе `<корень>/.doc` |
| Handle репозитория | `JDOCMUNCH_REPO`, иначе `source_root` из индекса, иначе имя каталога |
| Имя индекса при `--index` | из handle, переопределяется `JDOCMUNCH_INDEX_NAME` |
| Хранилище | `DOC_INDEX_PATH`, иначе `~/.doc-index` |

Изоляция проектов логическая, не через права доступа:

- Поиск не уходит в чужой индекс сам: `repo` обязателен, автоопределения по cwd нет.
- Чужой индекс доступен, если явно передать его handle. `doc_list_repos`
  показывает все проекты.
- Группы `all` и `seinline` намеренно объединяют проекты.
- Жесткая изоляция возможна только отдельным `DOC_INDEX_PATH` на проект, тогда
  процесс физически не видит остальные индексы.

Правило проекта: в задачах testdeploydocker используется
`repo: local/testdeploy-arch`, группы `all` и `seinline` не применяются.

---

## Несколько проектов

- Индекс общий в `DOC_INDEX_PATH`, проекты разделяются handle `owner/name`; в задачах использовать только `local/testdeploy-arch`.
- `repo` обязателен, группы `all` и `seinline` не применять.
- Жесткая изоляция только отдельным `DOC_INDEX_PATH` на проект. Детали в разделе "Миграция и изоляция".

## Связи

- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - место jdocmunch в общем списке и краткие правила
- [Скрипты](../../../../../.doc/harnes/state/05-scripts.md) - лаунчер в скиле jdocmunch
- [Миграция между агентами](../../../../../.doc/harnes/state/13-agent-migration.md) - канон, зеркала, parity, DSH
- [Миграция между проектами](../../../../../.doc/harnes/state/14-project-migration.md) - перенос kit и профили
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - общие HTTP-серверы и проектная изоляция
- [Правила документации](../../../../../.doc/harnes/doc_rules.md) - стандарт `.doc/`, MCP-маршрут

---

## Известные проблемы и ограничения

### П-1: Полная индексация корпуса шла часами

- Симптом: до 2026-11-03 `--index` на 1 тыс. документах занимал 9633 с, около
  2 ч 40 мин, и грузил процессор на 450 процентов.
- Причина: корпус вырос до 19.5 тыс. секций, модель считала эмбеддинги на CPU.
- Ограничение или решение: эмбеддинги отключены, модель и кеш удалены. Полный
  прогон теперь без эмбеддингов, время зависит от корпуса. Запускать из shell,
  а не через MCP-клиент. Полная пересборка нужна только для чистки удаленных
  файлов.
- Файлы: `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh`

### П-2: Инкрементальный прогон не чистит удаленные файлы и метаданные

- Симптом: удаленный `architecture/deepseek-harness-06-audit.md` остается в
  индексе, поле `corpus_selection` показывает старый subset из 64 файлов.
- Причина: `index-local` без `--rebuild` обновляет существующие и добавляет новые
  файлы, но не удаляет отсутствующие и не пересчитывает `corpus_selection`.
- Ограничение или решение: ориентироваться на `doc_paths`; для чистки выполнить
  `--index --rebuild`.
- Файлы: `/home/newuser/.doc-index/local/testdeploy-arch.json`

### П-3: Индекс стареет после правок документации

- Симптом: правка в документе не находится поиском, `get_recent_changes` показывает
  секцию в корзине `edited_uncommitted`.
- Причина: сервер сам не переиндексирует, служба `jdocmunch-watch` не установлена.
- Ограничение или решение: `--index` после правок или `watch-install` для
  фонового обновления всех трех репозиториев.
- Файлы: `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh`

### П-4: `lookup_term` не общий словарь

- Симптом: пустой `matches` на обычное слово.
- Причина: глоссарий строится только из жирных определений в тексте, сейчас 23
  записи; сравнение точное.
- Ограничение или решение: для общего поиска использовать `search_sections`.
- Файлы: `/home/newuser/.doc-index/local/testdeploy-arch.json`

### П-5: Аргумент `limit` игнорируется

- Симптом: результат приходит с `ignored_arguments: ["limit"]` и размером по
  умолчанию.
- Причина: у `search_sections` ограничение называется `max_results`.
- Ограничение или решение: передавать `max_results`.
- Файлы: `.agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh`

### П-6: Один процесс на клиента

- Симптом: несколько редакторов держат несколько процессов и несколько копий
  модели.
- Причина: stdio-транспорт, `serve` не поддерживает http.
- Ограничение или решение: закрывать неиспользуемые клиенты; общий HTTP-процесс
  возможен только через внешний прокси, в харнесе его нет.
- Файлы: `.cursor/mcp.json`

### П-7: Межпроектный поиск не запрещен технически

- Симптом: запрос с чужим handle возвращает документы другого проекта.
- Причина: общий `~/.doc-index`, изоляция только по `repo`, ACL отсутствует.
- Ограничение или решение: держать правило проекта и не передавать чужие
  `repo`/`repo_group`; для жесткой изоляции задать отдельный `DOC_INDEX_PATH`.
- Файлы: `/home/newuser/.doc-index/_groups.jsonc`

### П-8: Связка с кодом не настроена

- Симптом: `resolve_related_code_repos` возвращает пустой список кандидатов.
- Причина: jcodemunch с код-индексом на машине не подключен.
- Ограничение или решение: `get_doc_coverage`, `list_undocumented_symbols`,
  `link_code_to_symbols` работают вхолостую; для кода использовать CBM, codegraph
  и Serena.
- Файлы: `/home/newuser/.doc-index/_groups.jsonc`

### П-9: Качество ссылок и сирот ниже остальных осей

- Симптом: `link_integrity` 71.58 и `orphan_health` 71.77 при общей оценке A.
- Причина: 469 битых ссылок и 2329 секций без входящих ссылок; большую часть
  дают задачи и их артефакты.
- Ограничение или решение: `get_broken_links` и `get_orphan_sections` перед
  массовой правкой документации.
- Файлы: `.doc/architecture/`, `.doc/tasks/`

### П-10: Индекс не привязан к коммиту

- Симптом: `source_dirty: true`, `sha_certified: false`.
- Причина: индекс собран с рабочего дерева, а не с чистого коммита.
- Ограничение или решение: `head_sha` использовать как ориентир, а не как
  гарантию; после правок обновлять индекс.
- Файлы: `/home/newuser/.doc-index/local/testdeploy-arch.json`

### П-11: Kilo Code Mode возвращает JSON-строку

- Симптом: поиск через `execute` даёт `count: 0` при непустом индексе, `s.results` — `undefined`, обращение к любому полю ответа — `undefined`.
- Причина: в Kilo Code Mode инструмент возвращает **JSON-строку**, агент читает `s.results` или `repo.repo` без `JSON.parse`.
- Ограничение или решение: **всегда** разбирать ответ через `JSON.parse` перед доступом к полям. `repo` задавать литералом `local/testdeploy-arch`, `doc_resolve_repo` вызывать с путём к `.doc`.

**Правильный паттерн (копируй как есть):**

```js
const parse = (x) => (typeof x === "string" ? JSON.parse(x) : x);

// Ресолв репозитория
const resolved = parse(await tools.jdocmunch.doc_resolve_repo({ path: "/home/newuser/projects/copytrust/testdeploydocker/.doc" }));
const repo = resolved.repo;  // "local/testdeploy-arch"

// Поиск
const raw = await tools.jdocmunch.search_sections({ repo, query: "ct_log", path_glob: "architecture/*", max_results: 8 });
const s = parse(raw);

// Теперь s.results доступен
const items = (s.results || []).map(x => ({ path: x.doc_path, title: x.title, id: x.id }));
```

- Файлы: [`.cursor/rules/mcp/jdocmunch.mdc`](../../../../../.cursor/rules/mcp/jdocmunch.mdc), раздел "Вызов в среде"

---

## История изменений

- 2026-11-11: добавлены контракт возврата Kilo Code Mode (JSON-строка, `JSON.parse`), путь `.doc` для `doc_resolve_repo`, рабочий шаблон `Promise.all` и проблема П-11. Причина: три поиска в диалоге вернули ложные нули из-за чтения строки как объекта.
- 2026-11-10: разрешение на операции индекса отделено от поиска; ссылка на удалённую карту заменена канонической картой MCP.
- 2026-11-01: создан документ по фактической проверке сервера 1.150.1, индексов,
  групп, здоровья корпуса и прав миграции
- 2026-11-01: лаунчер перенесен из `.dsh/scripts/` в канон `.agents/skills/jdocmunch/scripts/`,
  путь проекта и handle выводятся из расположения скрипта и индекса
- 2026-11-01: подробный документ перенесен в `.doc/harnes/mcp/jdocmunch.md`,
  каталог `mcp/` закреплен как место по одному файлу на сервер
- 2026-11-01: корпус расширен до `architecture`, `harnes` и `tasks`; около 1 тыс. документов, около 16.5 тыс. секций, полная индексация 2 ч 40 мин, инкрементальная 141 с
- 2026-11-01: добавлен раздел Обновление индекса: инкрементальный прогон, случаи, замеры, проверка, watcher и ограничения
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-02: в корпус добавлен `web`, поэтому операционная документация панели
  `.doc/web/README.md` находится через `search_sections`, а не только чтением
- 2026-11-02: добавлены выбор корпуса через `path_glob` и замеры скорости
- 2026-11-03: бенчмарк 22 запросов: lexical Hit@3 0.59 и MRR 0.44 против
  hybrid 0.5 0.45 и 0.39, semantic-only 0.27 и 0.29. Задачи и точные термины
  semantic-only не находит. Эмбеддинги отключены, модель `~/.cache/fastembed`
  (1.1 ГБ) и sidecar 551 МБ удалены, индекс перестроен лексически
- 2026-11-03: повторный замер на лексическом индексе: Hit@1 0.32, Hit@3 0.64,
  MRR 0.50; `semantic_only` вернул 0
  файла; правило jdocmunch стало обязательным первым шагом
- 2026-11-02: полный инкрементальный прогон завершён: 1235 документов, 19107
  секций, 264 изменения, покрытие эмбеддингов 1.0; в индексе есть `web/README.md`
- 2026-11-09: повторный замер на Ollama `qwen3-embedding:0.6b`: архитектура MRR
  0.623 -> 0.752 (hybrid 0.2) и 0.842 (semantic-only), задачи и точные термины
  lexical 0.933 против 0.875 (hybrid) и 0.586 (semantic-only). Векторы не
  включены, рабочий индекс остался лексическим. Отчет:
  `.doc/skil_data/jdocmunch/benchmark/README.md`
