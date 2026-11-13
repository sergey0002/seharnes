# Система работы с документацией (Readme)

> **Устарел:** заменен [index.md](./index.md) и разделом `state/`.
> Актуальные скилы: [.agents/skills/](../agents/skills/); актуальные MCP-серверы:
> [state/04-mcp.md](./state/04-mcp.md). Числа и списки ниже не обновляются.

<!-- meta
type: architecture
status: frozen
updated: 2026-09-26
related: [readmy.md, ../doc_rules.md, ../architecture/index.md]
tags: [readme, documentation, indexing, workflow]
-->

---

## Суть

Это операционный readme по системе документации CopyTrust.
Он описывает:
- как система работает **сейчас**;
- где лежат её источники правды;
- какие ограничения есть у текущих scripts;
- какие rules / skills / MCP-конфиги реально участвуют в workflow;
- какой incremental workflow нужен агенту, чтобы продолжать документирование проекта
  с минимальным расходом токенов.

Главный принцип: **агент не должен каждый раз перечитывать весь проект**.
Он работает через карту, очереди, короткие section-срезы и уже существующие business-docs.

---

## Что уже есть сейчас

### Канонические точки входа

1. `.doc/harnes/doc_rules.md` — обязательный стандарт по формату и ссылкам.
2. `.doc/architecture/index.md` — вход в существующую архитектурную документацию.
3. `.doc/architecture/_map/` — машинный слой карты проекта и state-файлов.

### Базовые scripts

| Скрипт | Что делает сейчас | Ограничение |
|---|---|---|
| `map-project.ps1` | Генерирует `tree.txt` + `hot-files.txt` и вызывает `generate-doc-index.ps1` + `generate-file-registry.ps1` | Сам покрытие не ведёт; за него отвечает `generate-file-registry.ps1` |
| `generate-file-registry.ps1` | Строит/обновляет реестр файлов `file-registry.tsv` (indexed/not_indexed/manual/noise/deleted) | Safety Gate: abort при потере >50% файлов реестра |
| `generate-doc-index.ps1` | TSV-индекс arch-доков `doc-index.tsv` | Отстаёт от диска: 46 записей при 50 файлах |
| `get-indexing-batch.ps1` | Батч индексации 15/30 файлов → `current-batch.txt` | Очередь `not_indexed` пуста: индексация завершена |
| `mark-noise.ps1` | Пометка плагинов/минифицированных файлов как noise | |
| `get-verify-batch.ps1` | Очередь сверки doc-verify (`verify-registry.tsv`), выдаёт следующий документ | 1 шаг = 1 документ |
| `mark-verify-done.ps1` | Отметка документа сверенным в `verify-registry.tsv` | |
| `build-tasks-index.ps1` | Пересборка `.doc/tasks/index.md` + `_map/file-to-tasks.tsv` (`-AlsoTsv`) | |
| `find-related-tasks.ps1` | Поиск задач по файлам/докам (score, `-Json`) | |
| `export-rebase-project.ps1` | Обёртка экспорта переноса харнеса (канон `rebase_project.ps1`) | |
| `_batch-ai-links.py` | Массовая простановка AI-блоков в arch-доки | |
| `audit-docs.ps1` | Ищет активные файлы без упоминаний, docs без meta, stale docs, isolated docs | Смотрит на симптомы, но не ведёт постоянный реестр покрытия |
| `validate-docs.ps1` | Проверяет meta и базовые обязательные секции | Пока не полностью совпадает с `doc_rules.md` |
| `sync-docs.ps1` | Сравнивает docs с git-изменениями после `updated:` | Зависит от meta-слоя и не решает задачу полного покрытия |

### Подтверждённые ограничения текущего состояния

- Архитектурных docs уже много, но они неоднородны по структуре и именованию.
- `validate-docs.ps1` на 2026-05-27 дал **276 ошибок**.
- `audit-docs.ps1` на 2026-05-27 показал активные файлы без покрытия и docs без meta.
- `indexing-state.json` остался без скрипта-обработчика (`indexing-state.ps1` удалён):
  state-файл осиротевший; очередью индексации управляет `file-registry.tsv`.
- `_map/` содержит устойчивый слой покрытия: `file-registry.tsv` (статусы файлов),
  `doc-index.tsv`, `verify-registry.tsv`.

---

## Источники правды

### Человеко- и агентно-читаемый слой

| Файл | Роль |
|---|---|
| `.doc/harnes/doc_rules.md` | Стандарт формата, ссылок, поведения агентов |
| `.doc/doc_readme.md` | Этот operational readme |
| `.doc/harnes/readmy.md` | Указатель на актуальные документы харнеса; раскладка в `harnes/dirtree.md` |
| `.doc/architecture/index.md` | Навигация по architecture docs |
| `.doc/architecture/*.md` | Смысловые документы по доменам и процессам |
| `.doc/tasks/{N}/doc.md` | Знания и подводные камни по конкретным задачам |

### Машинный слой `_map/`

| Файл | Роль | Комментарий |
|---|---|---|
| `file-registry.tsv` | Реестр файлов проекта | Статусы indexed/not_indexed/manual/noise/deleted; 3 364 живых записи |
| `file-registry-archive.tsv` | Архив удалённых записей | 6 702 записи со статусом deleted |
| `doc-index.tsv` | TSV-индекс architecture-доков | Отстаёт: 46 записей при 50 файлах на диске |
| `verify-registry.tsv` | Очередь сверки doc-verify | Ведётся `get-verify-batch.ps1` / `mark-verify-done.ps1` |
| `current-batch.txt` | Текущий батч индексации | Создаётся `get-indexing-batch.ps1` |
| `current-verify-batch.txt` | Текущий батч сверки | Создаётся `get-verify-batch.ps1` |
| `hot-files.txt` | Топ активных файлов по git за 90 дней | Для приоритизации батчей |
| `tree.txt` | Дерево директорий проекта | Generated |
| `indexing-state.json` | Осиротевший state-файл | Скрипт-обработчик удалён, не используется |

### Важное правило

Generated-файлы карты можно пересобирать.
Persistent-маркеры прогресса и покрытия должны жить **только** в отдельных state/register files
(`file-registry.tsv`, `doc-index.tsv`, `verify-registry.tsv`), а не внутри generated-списков
типа `tree.txt`. Удалённые ранее `php-files.txt`, `section-*.txt` больше не генерируются.

---

## Связанные rules, skills, MCP и configs

Нет, в прошлой версии `doc_readme.md` были описаны не все operational artifacts.
Ниже — компактный реестр того, что реально участвует в workflow документации.
Состав харнеса: раскладка в [dirtree.md](dirtree.md), скилы в [state/02-skills.md](state/02-skills.md), правила в [state/03-rules.md](state/03-rules.md).

### `.doc/` — канонический слой документации

| Файл | Назначение |
|---|---|
| [`.doc/harnes/doc_rules.md`](doc_rules.md) | Канонический стандарт docs |
| [`harnes/readmy.md`](readmy.md) | Указатель на актуальные документы харнеса |
| [`.doc/architecture/index.md`](../architecture/index.md) | Вход в architecture docs |
| [`.agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1`](../docscripts/map-project.ps1) | Построение карты проекта |
| [`.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1`](../docscripts/build-tasks-index.ps1) | Индекс задач ↔ файлы (`.doc/tasks/index.md`) |
| [`.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1`](../docscripts/find-related-tasks.ps1) | Поиск задач для arch-doc / doc-verify |
| `.agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1` | Батч индексации (15/30 файлов) |
| `.agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1` | Пометка шума в реестре |
| `.agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1` / `mark-verify-done.ps1` | Очередь сверки doc-verify |
| `.agents/skills/documentation-router/children/project-doc/scripts/audit-docs.ps1` | Аудит docs |
| `.agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1` | Валидация docs |
| `.agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1` | Выявление устаревших docs |
| `.agents/skills/documentation-router/children/project-doc/scripts/_lib.ps1` | Общая библиотека scripts |

### `.codex/` — Codex entrypoint и mirror MCP-kit

| Файл | Назначение |
|---|---|
| [`.codex/AGENTS.md`](../../.codex/AGENTS.md) | Инструкции Codex/Cursor по repo workflow |
| [`.codex/recommendations.md`](../../.codex/recommendations.md) | Рекомендованный порядок инструментов |
| [`.codex/rules/mcp-codebase-memory.md`](../../.codex/rules/mcp-codebase-memory.md) | Правило CBM для агента |
| [`.codex/config.toml`](../../.codex/config.toml) | Конфиг MCP для Codex |
| [`.codex/rules/doc-rules.md`](../../.codex/rules/doc-rules.md) | Wrapper на `.doc/harnes/doc_rules.md` |
| [`.codex/rules/bitbucket-tasks.md`](../../.codex/rules/bitbucket-tasks.md) | Правила task workflow |
| [`.codex/skills/task-router/children/gototask/SKILL.md`](../../.codex/skills/task-router/children/gototask/SKILL.md) | Переход к задаче |
| [`.codex/skills/documentation-router/children/project-doc/SKILL.md`](../../.codex/skills/documentation-router/children/project-doc/SKILL.md) | Индексация / document project |
| [`.codex/skills/task-router/children/task-diff/SKILL.md`](../../.codex/skills/task-router/children/task-diff/SKILL.md) | Генерация diff задачи |
| [`.codex/skills/documentation-router/children/task-doc/SKILL.md`](../../.codex/skills/documentation-router/children/task-doc/SKILL.md) | Документация задачи |
| [`.codex/skills/yadisk-screenshot/SKILL.md`](../../.codex/skills/yadisk-screenshot/SKILL.md) | Импорт скрина/файла с Яндекс.Диска |

### `.cursor/` — Cursor rules и MCP-config

| Файл | Назначение |
|---|---|
| [`.cursor/recommendations.md`](../../.cursor/recommendations.md) | Рекомендации по инструментам для Cursor |
| [`.cursor/rules/mcp/codebase-memory-mcp.mdc`](../../.cursor/rules/mcp/codebase-memory-mcp.mdc) | Правило CBM: методы, аргументы, когда брать |
| [`.cursor/mcp.json`](../../.cursor/mcp.json) | MCP-конфигурация Cursor |
| [`.cursor/rules/doc-rules.mdc`](../../.cursor/rules/doc-rules.mdc) | Wrapper на doc rules |
| [`.cursor/rules/project-doc.mdc`](../../.cursor/rules/project-doc.mdc) | Правило/скил индексации для Cursor |
| [`.cursor/rules/task-doc.mdc`](../../.cursor/rules/task-doc.mdc) | Правило docs по задачам |
| [`.cursor/rules/bitbucket-tasks.mdc`](../../.cursor/rules/bitbucket-tasks.mdc) | Правило task workflow |
| [`.cursor/rules/yadisk-screenshot.mdc`](../../.cursor/rules/yadisk-screenshot.mdc) | Правило импорта со скрина Я.Диска |
| [`.agents/skills/task-router/children/gototask/SKILL.md`](../../.agents/skills/task-router/children/gototask/SKILL.md) | Переход к задаче |
| [`.agents/skills/task-router/children/task-diff/SKILL.md`](../../.agents/skills/task-router/children/task-diff/SKILL.md) | Генерация diff задачи |

### `.agents/` — repository-local skills

| Файл | Назначение |
|---|---|
| [`.agents/skills/task-router/children/gototask/SKILL.md`](../../.agents/skills/task-router/children/gototask/SKILL.md) | Локальный вариант перехода к задаче |
| [`.agents/skills/documentation-router/children/project-doc/SKILL.md`](../../.agents/skills/documentation-router/children/project-doc/SKILL.md) | Локальный вариант индексации проекта |
| [`.agents/skills/task-router/children/task-diff/SKILL.md`](../../.agents/skills/task-router/children/task-diff/SKILL.md) | Локальный вариант diff |
| [`.agents/skills/documentation-router/children/task-doc/SKILL.md`](../../.agents/skills/documentation-router/children/task-doc/SKILL.md) | Локальный вариант task-doc |
| [`.agents/skills/yadisk-screenshot/SKILL.md`](../../.agents/skills/yadisk-screenshot/SKILL.md) | Локальный вариант screenshot skill |

### Какие MCP реально фигурируют в documentation workflow

Текущие конфиги `.cursor/mcp.json` и `.codex/config.toml` подтверждают использование
(15 серверов, активны 13):
- `codebase-memory-mcp`
- `sourcegraph`: полнотекст по коду (HTTP 127.0.0.1:7080)
- `serena`
- `mysql`
- `context7`
- `playwright`
- `phpstan-mcp`
- `php-deps-mcp`
- `semgrep`
- `git`
- `xdebug`
- `jira-task` — экспорт задач из Jira (канон)
- `deepwiki`: отключён
- `bitbucket-task` — legacy, отключён

Для документации и индексации канонический маршрут остаётся таким:
1. `codebase-memory-mcp`
2. `serena`
3. `mysql` — если затронута модель данных
4. `context7` — только внешняя документация
5. `phpstan-mcp` / `semgrep` / `playwright` — verification layer

### Что из этого считать каноном

- **Канон для docs**: `.doc/harnes/doc_rules.md`, `.doc/doc_readme.md`, `.doc/architecture/index.md`
- **Канон для Codex workflow**: `.codex/AGENTS.md`, `.codex/recommendations.md`, `.codex/config.toml`
- **Канон для Cursor workflow**: `.cursor/mcp.json`, `.cursor/recommendations.md`, `.cursor/rules/*.mdc`
- **`.agents/skills/*`** — локальные репозиторные skill-копии, их тоже надо держать согласованными
  с `.codex/skills/*`, если они участвуют в реальном запуске

---

## Правило именования architecture docs

Новый doc должен называться по **бизнес-процессу**, **домену** или **shared subsystem**,
который он описывает.

### Хорошо

- `payments.md`
- `orders.md`
- `item.md`
- `shared-infrastructure.md`

### Плохо

- `PaymentService.md`
- `ArticlesController.md`
- `FaqController.md`
- `OrderXhrController.md`

### Исключения

Технический doc допустим, если это действительно cross-cutting подсистема:
- инфраструктура;
- DI/container;
- shared ORM/DB layer;
- общая event/notification subsystem;
- тяжёлый legacy-узел, используемый многими доменами.

Перед созданием нового doc всегда проходит **Index Gate**:
1. прочитать `index.md`;
2. проверить существующие `.doc/architecture/*.md`;
3. понять, можно ли дописать в уже существующий business-doc;
4. только потом создавать новый файл.

---

## Как работает индексация сейчас

Индексация проекта завершена: очередь `not_indexed` в `file-registry.tsv` пуста.
Рабочие циклы ниже применяются для новых файлов и для сверки существующих доков.

### Индексация новых файлов

1. Собрать/обновить карту:
   `powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1`
2. Получить батч:
   `powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 15`
3. Отфильтровать шум:
   `powershell .agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1 -Paths "path1","path2"`
4. Агент:
   - читает `doc_rules.md`;
   - читает `architecture/index.md`;
   - ищет существующий целевой doc (Index Gate);
   - при необходимости использует CBM/sourcegraph/serena/mysql;
   - дополняет или создаёт architecture doc;
   - в том же проходе обновляет `index.md`.
5. Зафиксировать покрытие:
   `powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1`
   (бектики в doc переводят файлы в `indexed`).

### Сверка существующих доков (doc-verify)

1. Статус очереди:
   `powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Status`
2. Взять следующий документ:
   `powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Count 1`
3. Агент сверяет документ с кодом (MCP Gate: CBM → sourcegraph → serena),
   точечно правит секции, чинит связи и задачи.
4. Отметить шаг:
   `powershell .agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1 -Path <doc.md> -Issues <N>`

### Что важно понимать

Покрытие фиксируется реестром, а не вручную: `generate-file-registry.ps1` переводит файл
в `indexed`, если файл упомянут в бектиках architecture-дока. Параметра `-Resume`
у `map-project.ps1` нет: актуальное состояние всегда берётся из реестров `_map/`.

---

## Как индексировать огромный проект без переполнения контекста

Правильный ответ: **не пытаться скормить модели весь проект**.
Нейронка не должна читать 1490 PHP + 1109 JS + 560 TPL (+42 vue) напрямую в одном диалоге.

### Запрещённая стратегия

Плохо:
- открыть дерево проекта целиком;
- затем читать десятки или сотни файлов подряд;
- затем пытаться «в голове» собрать индексы;
- затем писать docs по памяти.

Это ломает:
- контекстное окно;
- точность;
- консистентность naming;
- возможность продолжения с места остановки.

### Правильная стратегия: multi-pass indexing

#### Pass 1 — Machine map

Собирается карта проекта скриптами:
- `map-project.ps1`
- `_map/file-registry.tsv` (инвентарь и статусы файлов)
- `_map/hot-files.txt`
- `_map/tree.txt`

Списки `_map/php-files.txt`, `_map/js-files.txt`, `_map/tpl-files.txt`
и `_map/vue-components.txt` удалены из генератора как источник шума.

На этом этапе агент **не читает код подробно**.
Он получает только inventory проекта.

#### Pass 2 — Domain catalog

Проект режется не по классам, а по **business domains / flows**.
Для этого задуман `section-catalog.json` (не внедрён), где домен описывается:
- aliases;
- patterns;
- target doc;
- типом (`domain`, `flow`, `infra`, `legacy`).

Это ключевой шаг, который переводит карту файлов в бизнес-логику.

#### Pass 3 — Section slice

Для одного домена собирается локальный срез:
- `collect-section.ps1` удалён; вместо section dump используется батч
  `get-indexing-batch.ps1` (группировка по директориям) и фильтр `file-registry.tsv`
  по домену/директории.

Именно этот срез, а не весь проект, должен читаться агентом.

#### Pass 4 — Business-doc selection

До чтения кода агент решает:
- есть ли уже подходящий doc;
- какой doc является каноническим для домена;
- какие дубли нужно merge-ить.

Для этого нужны:
- `index.md`;
- существующий `doc-index.tsv` (TSV-индекс arch-доков);
- naming policy по бизнес-смыслу.

#### Pass 5 — Targeted code reading

Только после section-среза агент точечно читает:
- 3–10 ключевых файлов домена;
- 1–3 смежных файла по graph traces;
- при необходимости route/controller/service цепочку;
- связанные JS/Vue/TPL, если это пользовательский flow.

То есть чтение идёт **от карты к домену, от домена к нескольким файлам**, а не наоборот.

#### Pass 6 — Registry update

После обновления doc агент не должен «забывать», что домен обработан.
Нужно обновить:
- `index.md`
- `file-registry.tsv`
- `doc-index.tsv`

`indexing-state.json` осиротевший (скрипт-обработчик удалён) и не обновляется.

Именно это позволяет потом сказать:
> «продолжи документирование проекта»

и не начинать всё заново.

### Как сохранить покрытие при перестройке карты

**Сохраняется (внедрено).**
- `map-project.ps1` пересоздаёт только generated inventory (`tree.txt`, `hot-files.txt`);
- `file-registry.tsv` хранит покрытие файлов (статусы переживают rebuild);
- `doc-index.tsv` хранит лёгкий индекс docs;
- `section-catalog.json` и `cleanup-queue.txt` не внедрены.

Тогда rebuild карты безопасен:
- paths обновились;
- новые файлы появились в inventory;
- старые coverage-метки не стёрлись;
- новые файлы получили статус `not_indexed` и попали в очередь.

### Как формировать корректные индексы по бизнес-логике

Нельзя строить индекс только из имён классов и папок.
Нужна связка из нескольких источников:
- folder topology из `_map`;
- routes / controllers / entrypoints;
- CBM graph (`search_graph`, `trace_path`, `cross_service`);
- JS/Vue/TPL proximity;
- существующие business docs;
- task-doc знания о подводных камнях.

Условно:
- `Articles.php`, `ArticlesDataManager.php`, `admin/scripts/Articles/list.js`, `templates/articles/*`
  должны индексироваться как **`articles.md`**,
  а не как четыре отдельных технических блока.

### Рекомендуемый размер одной сессии индексации

Для большого проекта безопасная единица работы:
- **1 домен / 1 флоу за сессию**;
- или **5–7 cleanup docs за сессию**;
- или **1 cross-cutting map** отдельной сессией.

Это даёт:
- предсказуемый объём контекста;
- нормальную проверяемость;
- устойчивые checkpoints.

---

## Замечания к skill / rule индексации проекта

Да, для project indexing skill нужны явные доработки.
Сейчас основной разрыв не в том, что skill отсутствует, а в том, что ему не хватает
устойчивого state-layer и доменного каталога.

### Что должен требовать `project-doc`

1. **Не читать весь проект напрямую.**
   Только `doc_rules.md` → `index.md` → `_map` state → один батч (`current-batch.txt`) → точечный code read.

2. **Не создавать class-centric docs по умолчанию.**
   Сначала искать business-doc.

3. **После каждого SECTION обновлять не только очередь, но и покрытие.**
   То есть skill должен знать про:
   - `file-registry.tsv`
   - `doc-index.tsv`
   - `verify-registry.tsv`

4. **Разделять indexing и cleanup.**
   Старая документация не должна чиниться вперемешку с созданием новой доменной docs,
   если это не мешает текущему домену.

5. **Уметь продолжать с checkpoint.**
   Если сессия оборвалась, агент должен продолжить текущий `in-progress`,
   а не пересобирать проект в голове заново.

### Что стоит поправить в rule-слое

- В `project-doc` / `project-doc.mdc` явно описать persistent state files.
- Запретить финализацию раздела без обновления coverage registry.
- Явно ввести business-domain naming policy.
- Явно разделить `domain indexing`, `flow indexing`, `cleanup` и `cross-cutting maps`.

---

## Что делать с существующей документацией

Существующие docs не надо просто массово удалять или переписывать заново.
Их нужно разложить по корзинам.

### Корзина A — оставить и дополнять

Это docs, которые уже соответствуют бизнес-смыслу или shared subsystem:
- `payments.md`
- `tariffs.md`
- `shared-infrastructure.md`
- `item.md` / `deposition.md` — если подтверждён их правильный смысловой scope

### Корзина B — merge в business-doc

Это docs, которые слишком технические, но содержат полезные факты.
Перечисленные ниже файлы уже слиты и удалены ранее; список оставлен как история:
- `payment-service.md` → `payments.md`
- `payment-command.md` → `payments.md`
- `order-service-methods.md` → `orders.md`
- `register-service-full.md` / `register-service.md` → единый доменный doc

### Корзина C — format cleanup

Это docs, которые ценны по содержанию, но не проходят rules:
- нет `<!-- meta -->`
- нет `## Суть`
- нет `## Связи`
- нет `## История изменений`

Для них нужна cleanup-очередь, а не заново написанная архитектура.

### Корзина D — freeze / legacy reference

Это узлы, которые могут остаться отдельными как technical/legacy reference,
если они реально описывают shared legacy-подсистему и не вписываются в бизнес-doc.

### Практическое правило

Новый домен документируется так:
1. найти лучший существующий doc;
2. если он технический, но уже содержит 70% смысла — дописать и потом запланировать rename/merge;
3. если docs-дубликаты мешают — занести их в merge backlog;
4. не создавать третий параллельный doc на ту же тему.

---

## Целевой incremental workflow для агента

Ниже — модель, к которой нужно привести систему. Она совместима с текущими rules и scripts.

### Команда пользователя

> «продолжи документирование проекта»

### Что должен сделать агент

1. Прочитать:
   - `.doc/harnes/doc_rules.md`
   - `.doc/doc_readme.md`
   - `.doc/architecture/index.md`
2. Проверить state-слой:
   - `_map/file-registry.tsv` — реестр покрытия
   - `_map/doc-index.tsv` — индекс docs
   - `_map/verify-registry.tsv` — очередь сверки
3. Если есть `in-progress` работа — продолжить её.
4. Если очередь индексации пуста, но покрытие неполное — выбрать следующий домен
   по `file-registry.tsv` (файлы not_indexed, группировка по директориям).
5. Собрать короткий section-context: батч `get-indexing-batch.ps1` или срез
   `file-registry.tsv` по домену.
6. Обновить один целевой business-doc.
7. В том же проходе обновить `index.md`.
8. Обновить state/registry layer.
9. Вернуть пользователю:
   - что сделано;
   - какой документ обновлён;
   - какие файлы покрытия добавлены;
   - что логично делать следующим.

### Почему это экономит токены

Агент читает не весь проект, а только:
- правила;
- индекс docs;
- state-файлы;
- один section dump;
- 1–2 целевых документа.

Именно поэтому persistent-слой в `_map/` критичен: он заменяет повторное чтение тысяч файлов.

---

## Obsidian-режим

### Что уже можно делать

- открыть `.doc/architecture/` как vault;
- использовать markdown links как основной формат;
- строить graph view по существующим ссылкам и тегам.

### Что желательно добавить

Факт: `.doc/architecture/.obsidian/app.json` существует, но пуст (`{}`);
исключение `_map/` не настроено.

- исключение `_map/` в `.obsidian/app.json`;
- единый словарь тегов через `index.md` и meta;
- цветовые группы только после стабилизации структуры docs.

### Что пока не нужно делать принудительно

- массово переводить docs на YAML frontmatter;
- переключать систему на `[[wikilinks]]`;
- переименовывать `index.md` в `_index.md`.

Пока scripts не готовы к этим форматам, canonical mode должен оставаться максимально совместимым.

---

## Проверки и контроль качества

### Уже сейчас

- `validate-docs.ps1` — структурная проверка docs;
- `audit-docs.ps1` — активные uncovered files, stale docs, isolated docs;
- `sync-docs.ps1` — выявление docs, которые не догнали код.

### Актуальная цепочка (внедрена)

После любого meaningful update architecture-doc выполняется цепочка:
1. `validate-docs.ps1` по изменённому doc;
2. refresh `doc-index.tsv` (через `map-project.ps1`);
3. refresh `file-registry.tsv` (через `map-project.ps1`);
4. при сверке: `mark-verify-done.ps1`.

Это и есть нужный generator-verifier loop для documentation workflow.

---

## Известные проблемы и ограничения

### П-1: (закрыто) Слой покрытия внедрён

Слой покрытия реализован: `file-registry.tsv` (статусы файлов), `doc-index.tsv`
(индекс docs), `verify-registry.tsv` (очередь сверки). `indexing-state.json` осиротевший
и не используется.

### П-2: (неактуально) `collect-section.ps1` удалён

Скрипт удалён как источник шумных выборок: single-pattern срезы плохо покрывали
составные домены. Вместо них используются батчи `get-indexing-batch.ps1`,
сгруппированные по директориям.

### П-3: Существующий массив docs требует отдельной cleanup-волны

Сначала нужно выровнять format debt и naming debt,
иначе любое новое индексирование будет продолжать старую неоднородность.

### П-4: `doc_readme.md` должен оставаться operational readme, а не складом всех деталей

Сюда нужно добавлять ссылки и workflow, но не копировать целиком содержимое rules/skills/configs.
Подробности должны оставаться в соответствующих файлах.

---

## Связи

- [Раскладка каталогов харнеса](dirtree.md): назначение каталогов, размещение скриптов и архитектура скила
- [Правила работы с документацией](doc_rules.md) — обязательный стандарт
- [Оглавление архитектуры](../architecture/index.md) — текущая навигация по docs
- [Codex AGENTS](../../.codex/AGENTS.md) — repo workflow для Codex/Cursor
- [Cursor MCP config](../../.cursor/mcp.json) — список подключённых MCP
- [Codex MCP config](../../.codex/config.toml) — mirror MCP-конфиг для Codex

---

## История изменений

- 2026-05-27: readme расширен после аудита scripts/rules/state; добавлены текущие ограничения системы, целевой incremental workflow, правила business naming, роль persistent state-файлов и безопасный Obsidian-режим.
- 2026-05-28: добавлен реестр связанных rules/skills/MCP/configs из `.doc`, `.codex`, `.cursor`, `.agents`; отдельно описан процесс индексации огромного проекта без переполнения контекста, требования к `project-doc` и стратегия работы с существующей документацией.
- 2026-05-30: синхронизирован статус machine-layer с фактом (`section-catalog.json` уже существует), добавлено явное примечание про `indexing-state-q2.json` как неканонический state-файл.
- 2026-09-26: актуализация по сверке с диском: состав scripts и `_map/` приведён к факту (file-registry, doc-index, verify-registry), циклы индексации и сверки переписаны под существующие скрипты, MCP-реестр расширен до 15 серверов (активны 13), ссылки на несуществующий plan.md заменены на readmy.md.
- 2026-11-05: ссылки на скилы Codex приведены к иерархии `skills/task-router/children/...` и `skills/documentation-router/children/...`; плоские пути `gototask`, `task-diff`, `project-doc`, `task-doc` больше не существуют.
