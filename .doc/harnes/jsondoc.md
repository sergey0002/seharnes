# JSONdoc: план документации задач и архитектуры

<!-- meta
type: rules
status: draft
scope_size: large
updated: 2026-11-10
audit_status: pending
research_complete: false
execution_contract: sequential-gated
tool_root: .doc/skil_data/task-doc
code_root: .agents/skills/documentation-router/children/task-doc
related: [doc_rules.md, ../tasks/index.md, ../architecture/index.md]
tags: [jsondoc, documentation, migration, harness, search]
-->

## Суть

> **Обновление 2026-11-10.** Подкоманды `plan write`, `plan verify`, `plan template`,
> `plan_writer.py`, `plan_verify.py` и план-валидатор удалены. План теперь только
> авторский `plan.md` через `prepare-plan`. Всё ниже про JSON-план читать как историю.
>
> **Обновление 2026-11-11.** Код `jsondoc.py`, модули `jsondoc/`, схемы и тесты лежат
> в `.agents/skills/documentation-router/children/task-doc/`. Под `tool_root`
> остаются рабочие данные: `state/`, `runs/`, `work/`, `implementation/`.

План новой системы хранения документации: JSON содержит знания и исходный текст,
Markdown становится совместимым представлением. Один локальный Python CLI читает,
ищет, валидирует, обновляет и переносит документы. Никакой БД, MCP-сервера, embeddings
или сетевой службы для поиска не требуется. Теги дают дополнительный поиск по типу
задачи, домену, бизнес-процессу, компоненту и риску.

**Граница текущей работы:** изменяется этот план. Скрипты, схемы, миграция и смена
канона документации ещё не реализованы. Все команды `jsondoc.py` ниже являются
спецификацией будущего CLI, а не доступными сейчас командами.

**Граница готовности:** R1-R8 сохраняют смысловую декомпозицию; исполняемый порядок
теперь задают атомарные J00-J16 и gate-протокол раздела 16. Дополнения 13-20 имеют
приоритет над прежними путями и формулировками 1-12, явно перечисленными в §13.
Ни одна исходная деталь не удалена: изменившиеся решения имеют таблицу замены.
Перенос живого архива запрещён до тестов R1-R6 и dry-run. Этот документ не выдаёт
самопроверку спецификации за прошедший code-level P7: точные code patches и
машинные свидетельства проверок появляются при выполнении соответствующего R.

Навигация: [аудит](#1-аудит-предыдущей-версии), [хранение](#3-хранение),
[формат](#4-контракт-json), [теги](#5-теги-и-связанные-задачи), [CLI](#6-cli),
[запись](#7-запись-и-целостность), [миграция](#8-миграция-без-потери-данных),
[интеграции](#9-интеграция-с-harness), [этапы](#10-порядок-реализации),
[тесты](#11-внутренние-тесты), [приёмка](#12-приёмка-и-ограничения),
[повторный аудит](#13-повторный-аудит-и-обязательные-уточнения),
[окончательная структура](#14-окончательная-структура-файлов),
[стадии задачи](#15-стадии-задачи-дифы-и-документация),
[атомарное выполнение](#16-атомарные-этапы-реализации),
[очередь миграции](#17-скриптовая-миграция-и-агентская-очередь),
[совместимость](#18-проверка-совместимости-всего-harness).

## 1. Аудит предыдущей версии

| Пробел | Исправление в этой версии |
|---|---|
| Пять отдельных CLI, десятки команд для каждого поля | Один `jsondoc.py`, общий batch-update, отдельные внутренние модули только по ответственности |
| JSON-примеры содержали комментарии, неполные объекты и неописанные поля | Валидный минимальный пример; явные типы, defaults, nullable, версии и строгая схема |
| Теги задач отсутствовали | Общий словарь тегов с описаниями, aliases и назначениями у задач |
| План отражал только doc.md, но не stage-планы, findings, AC/R/S и evidence | Каталог всех артефактов задачи и поисковая проекция планов с provenance |
| Конвертер падал на любом нестандартном блоке | Неизвестные блоки сохраняются дословно; структурное покрытие отдельно от сохранности текста |
| Автоматическая миграция обещала понять произвольный Markdown | Скрипт извлекает только доказуемую структуру; неоднозначности сохраняет, не додумывает |
| Render записывал свой hash обратно в JSON | Hash JSON и hash MD хранятся во внешнем receipt; render не меняет knowledge JSON |
| При ручной правке view повторный render затирал текст | `VIEW_CONFLICT`, без перезаписи; явный разбор изменения |
| Один `os.replace` считался атомарностью пары и индексов | JSON - атомарный commit point, receipt-last, recover для производных; ограничения межфайловой атомарности названы |
| Read автоматически перестраивал индекс | Чтение не пишет; stale index виден, обновление отдельной командой |
| Полный reindex после каждого поля | Одна batch-запись, один render, один инкрементальный flush на workflow |
| Связанные задачи обязаны быть локально выгружены | Явное состояние `not_exported`; отсутствие экспорта не стирает связь |
| Исторические пути обязаны существовать сейчас | `current/planned/deleted/historical/unknown`; отдельно путь и revision |
| Нумерация ПК-N без дыр | Стабильные ID не перенумеровываются, допускают пропуски и superseded |
| Общий `pushed=true`, один verdict | Git-события и QA-результаты привязаны к commit/scope/артефакту, не наследуются автоматически |
| Обещание быстрого reindex без замеров | Счётчики I/O, benchmark на fixture и реальном inventory, без фиктивного SLA |
| Три задачи для проверки полной миграции | Автоматическая проверка каждого документа и каждого сохранённого блока |
| TSV объявлялись ненужными заранее | Контракты PS1 и существующие очереди сохраняются до проверенной замены потребителей |
| Писатели переключались раньше правил чтения | Feature-gated mixed mode, сначала совместимые читатели и правила, затем writers и cutover |

## 2. Источники и требования

### 2.1 Sources of truth

| ID | Источник | Что определяет |
|---|---|---|
| T1 | Запрос пользователя в текущем диалоге | Полный план, все новые инструменты/данные/тесты в `.doc/`, задачи в `tasks/{N}`, теги с описаниями |
| T2 | [doc_rules.md](doc_rules.md#правила-для-ai-агентов) | Index Gate, права записи, обратные ссылки, запрет потери секций |
| T3 | [task-doc](../../.agents/skills/documentation-router/children/task-doc/SKILL.md) B1-B5 и post-step | Свежесть task/diff, Reuse/Impact, B3, B4.5 и передача workflow-context |
| T4 | [project-doc](../../.agents/skills/documentation-router/children/project-doc/SKILL.md) | Очередь файлов, Index Gate, CBM, business-process docs, обновление index |
| T5 | [doc-verify](../../.agents/skills/documentation-router/children/doc-verify/SKILL.md) и reference | Сверка docs/code, V6, очередь verification, запрет создавать task doc из verify |
| T6 | [prepare-plan](../../.agents/skills/prepare-plan/SKILL.md) | Domain-first, T/AC/R/S, whole-file evidence, related-task scoring, research ledger |
| T7 | [docscripts](../../.agents/skills/documentation-router/children/project-doc/scripts/) | Реальные выходы индексов и PS1 аргументы, а не предполагаемая замена |
| T8 | [task-change-report](../../.agents/skills/task-router/children/reporting-router/children/task-change-report/SKILL.md) | report-model и workflow-context уже имеют собственные контракты и freshness |
| T9 | doc.md задачи 2612 в проекте Target | Пилотные ПК/решения/related links и partial QA; не шаблон всех исторических docs |
| T10 | `.doc/architecture/index.md` в проекте Target | Дерево решений, разделы, теги, навигация; не просто список файлов |
| T11 | History планов и `doc.md` задач | Не выдавать декларативные gates за доказанное выполнение; не ослаблять проверки ради миграции |
| T12 | [gototask](../../.agents/skills/task-router/children/gototask/SKILL.md), [task-diff](../../.agents/skills/task-router/children/task-diff/SKILL.md) и `.agents/skills/task-router/children/jira/scripts/server.php` | Единственный путь экспорта Jira: task.md остаётся raw export, tracker-снимок пишется только через наш CLI с provenance |
| T13 | [bitbucket-tasks](../../.cursor/rules/bitbucket-tasks.mdc): release base, backport-ветки, ls-remote правила | Git-проекция origin/релизного содержания по шаблонам из config, без сети из CLI и без заявлений о живом origin |
| T14 | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-manifest.py`, `gates.py`, `make-verdict.py`, `record-history.py`, `task-test.sh` | QA-манифест хеширует `task.md,test.md,plan.md,doc.md,ac-matrix.json,requirements.json,diff.files.md`; запись результата с авторендером doc.md меняет вход прогона - нужен input projection до переключения test-task |
| T15 | `task-change-report/scripts/workflow_contract.py`, `templates/*.schema.json`, `generate_report.py` | Существующий механизм freshness/checkpoint переиспользуется: task.json становится источником цепочки, не вторым workflow-context; renderer получает роль `doc_json` |

T9 выбран явно как пилот, а не как ID всей harness-задачи. У jsondoc нет Jira ID;
план и общие исследования живут в `.doc/`, нельзя присвоить им 2612 по открытой вкладке.

### 2.2 Acceptance criteria

| AC | Требование | Источник | Реализация | Проверка |
|---|---|---|---|---|
| AC1 | Все новые runtime tools, схемы, тесты и данные под `.doc/` | T1 | R1 | S1 |
| AC2 | Задача хранит текст, решения, ограничения, планы и evidence без потерь и ложных фактов | T1,T3,T6 | R1,R5 | S1,S5 |
| AC3 | Архитектура сохраняет секции, anchors, ссылки и индекс навигации | T2,T4,T10 | R1,R4,R5 | S4,S5 |
| AC4 | Поиск по свойствам, всем/нескольким задачам, файлам и тегам имеет лимиты и полноту | T1,T7 | R2,R3 | S2,S3 |
| AC5 | Запись безопасна при конфликте, сбое и двух агентах | T2 | R4 | S4 |
| AC6 | Все документы проходят автоматическую staging-миграцию с resume/rollback | T1,T2 | R5,R7 | S5,S7 |
| AC7 | Существующие workflow, TSV, score и permission gates не теряются | T3-T8 | R6 | S6 |
| AC8 | Тесты самодостаточны, без prod/DB/сети/внешних путей | T1 | R1-R8 | S1-S8 |
| AC9 | Экономия контекста не скрывает пропуски, stale данные и blockers | T1,T11 | R3,R8 | S3,S8 |
| AC10 | Синхронизированы инструкции сред; runtime доступность не заявляется по parity | T1,T3 | R6,R8 | S6,S8 |
| AC11 | Jira-снимок (статус, релиз, автор, исполнитель и прочее) и git-проекция (origin push, содержание в релизных ветках) фиксируются с provenance и явной свежестой, без сети из CLI | T12,T13 | R1,R4,R6 | UT24,UT25,IT08 |
| AC12 | Stage/task/R scopes различаются; собственные дифы стадий, планы MD и тесты доступны без догадок по имени папки | T1,T6,T8 | R1,R3,R6; J06,J07 | ST01-ST08 |
| AC13 | Один изолированный комплект новых tools/tests и автоматический gate после каждого J с накопительной регрессией | T1 | R1-R8; J00-J16 | EX01-EX05 |
| AC14 | Полное сохранение архитектуры скриптом и возобновляемая очередь агентского enrichment с evidence | T1,T2,T4,T5 | R5,R7; J09,J10,J14,J15 | MG01-MG08 |

### 2.3 IN/OUT

IN: документация задач, архитектурные Markdown, их derived indexes, skills/rules,
которые их читают или обновляют, новые CLI и внутренние тесты.

OUT: продуктовый PHP/JS/SQL, schema БД, права на push, смена Jira-полномочий, изменение
test verdict, запуск полного Acceptance suite, автоматическое выполнение команд
из документации, перенос всего `.cursor/` в `.doc/`.

Канонические **инструкции** skills/rules остаются в `.cursor/` по AGENTS.md.
Новые **исполняемые инструменты, схемы, fixtures, модели, индексы и отчёты JSONdoc**
полностью в `.doc/`. Если требуется перенести также сам канон skills, это отдельная
смена устройства harness и не часть миграции знаний.

## 3. Хранение

Дерево ниже сохранено как исходный дизайн разбиения обязанностей. Его размещение
`docscripts/_jsondoc` заменено окончательным деревом §14; создавать две структуры
запрещено. Исполняемый CLI живёт в
`.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py`,
данные задач - в `.doc/skil_data/task-doc/`, а примеры ниже используют оба пути.

```text
.doc/
  jsondoc.md                         эта спецификация
  doc_rules.md                       действующие права и процесс
  docscripts/
    jsondoc.py                       единственный публичный CLI
    jsondoc/
      __init__.py
      contract.py                    loading, strict validation, refs, versions
      store.py                       revision, lock, batch-update, receipt
      search.py                      projection, tags, ranking, paging
      render.py                      MD views, anchors
      migrate.py                     inventory, staging, cutover, rollback
      schemas/
        document.schema.json
        tags.schema.json
        update.schema.json
        control.schema.json          tagged variants: receipt, index, config, migration
      tests/
        test_contract.py
        test_store.py
        test_search.py
        test_render.py
        test_migrate.py
        test_integration.py
        fixtures/                    только синтетические данные
  _jsondoc/
    config.json                      пути, feature gate и шаблоны релизных веток, не секреты
    tags.json                        единый словарь тегов
    catalog.json                     generated search index (карточки: title/h1,
                                     doc_type, status, branch, release, tags,
                                     counts, hashes)
    migrations/{RUN}/manifest.json   общая карта, только ссылки и hashes
    test-runs/{RUN}/                 результаты внутренних тестов
    work/                            общие входы/результаты CLI без task ID
  tasks/{N}/
    task.json                        knowledge aggregate, не Jira task.md
    doc.md                           совместимый generated view
    task.md                          исходный Jira export, не заменяется
    plan.md, stage*/plan.md           исходные планы, не переписываются мигратором
    diff.md, diff.files.md            принадлежат task-diff
    test.md, ac-matrix.json           принадлежат QA workflow
    tests/, test-runs/, reports/      существующие тесты и evidence
    _jsondoc/
      receipt.json
      work/                          операции обновления конкретной задачи
      migrations/{RUN}/               original bytes, candidate, coverage, review
      transactions/{TX}/              журнал незавершённой записи и backup
      artifacts/{ID}.json             поисковые проекции plan/stage/прочих текстов
  architecture/
    orders.json, orders.md            knowledge + совместимый view
    index.json, index.md              дерево навигации, не generated список docs
    _jsondoc/{DOC_ID}/                receipt, transactions, migration originals
    _map/                            прежние очереди/TSV сохраняются
  tasks/_map/file-to-tasks.tsv         прежний output сохраняется
```

Все временные файлы writer находятся рядом с target; тесты используют
`.doc/skil_data/task-doc/runs/{RUN}/sandbox/`. У тестовых task fixtures собственный
`sandbox/.doc/tasks/{N}`. Не использовать `/tmp`, home или настоящие папки задач
для mutating tests. Устанавливать `PYTHONDONTWRITEBYTECODE=1`, чтобы не разносить pyc.

Путь корня задаётся `--root`, каталог документации - `--docs-dir .doc`.
Config может менять имена каталогов, шаблон task ID и источники legacy, но не хранит
секреты или доверенные shell-команды. CopyTrust task ID = `[0-9]+`; `2612` сохраняется
строкой. Библиотека не предполагает Jira, ветку или имя продукта.

Не создавать отдельные `tasks/index.json` и `graph.json`, дублирующие catalog.
Один пересоздаваемый `.doc/skil_data/task-doc/state/catalog.json` хранит компактные карточки,
обратные индексы file/tag/link и hashes источников. Канон всегда отдельный документ.

## 4. Контракт JSON

### 4.1 Общие правила

Schema version `1.0`, `kind=task|architecture|artifact|navigation`. JSON без comments,
NaN, Infinity, duplicate keys; unknown fields отвергаются. UTF-8 без BOM на запись,
входной BOM допускается и отражается в migration metadata. Неисправный UTF-8 не
заменяется молча символом replacement. Дата факта может быть `null`; timestamp записи
UTC ISO-8601. Никаких автоматически придуманных дат создания задачи.

Все aggregate objects содержат обязательные поля из примера ниже; неприменимые
коллекции пусты, неизвестные скаляры `null`. `kind` определяет допустимое наполнение:
архитектура имеет `task_id=null`, задача имеет номер из пути. `navigation` сохраняет
дерево решений index.md; `artifact` хранит извлечённые блоки source-плана/заметок.

ID документа: `task:2612`, `arch:orders`, `nav:architecture`,
`artifact:2612:stage2-plan`. ID записи локальный и стабильный, cross-reference всегда
содержит document ID + record ID. Старые `ПК-1`, `Р-1`, `П-19`, `AC1`, `R1`, `S1`,
`T1` сохраняются; `Р-1` решения и `R1` этапы не объединяются по транслитерации.

Массивы сохраняют порядок автора; canonical JSON сортирует только ключи объектов.
Порядок секций задаёт `section_order`. Хеш - SHA256 канонических bytes, а для
исходного архива сохраняется отдельно hash оригинальных bytes.

### 4.2 Минимальная новая задача

Это валидный пример полного envelope без утверждений о реализации или тестах.

```json
{
  "schema_version": "1.0",
  "kind": "task",
  "id": "task:2612",
  "revision": 1,
  "metadata": {
    "task_id": "2612",
    "title": "Услуга архивации ОИС",
    "task_type": "feature",
    "doc_type": null,
    "updated_at": "2026-09-25T15:00:00Z",
    "status": "unknown",
    "source_status": null
  },
  "summary": null,
  "tags": [],
  "sections": [],
  "section_order": [],
  "files": [],
  "findings": [],
  "decisions": [],
  "requirements": [],
  "progress": [],
  "stages": [],
  "notes": [],
  "relations": [],
  "artifacts": [],
  "checks": [],
  "git_events": [],
  "tracker": null,
  "git_state": null,
  "sources": [],
  "history": []
}
```

### 4.3 Записи и поля

Все перечисленные поля обязательны; `!` означает non-null, остальные имеют nullable
значение или пустой массив, если не оговорено иначе. В первой реализации схема
не допускает произвольного `extra` object, который обходил бы проверку.

| Коллекция | Контракт записи |
|---|---|
| metadata | `task_id:string|null`, `title!:string`, `task_type:feature|bug|refactor|support|unknown|null`, `doc_type:string|null` (архитектурный meta.type из doc-index.tsv, не теряется), `branch:string|null` (каноническая ветка задачи: `features/#N`/`bugfixes/#N` по типу; подтверждается git_events/поиском ref, не угадывается), `release:string|null` (выбранный релиз из Jira fixVersion для git-ветки релиза; источник - tracker snapshot, не ручной ввод), `updated_at!:UTC`, `status:unknown|in_progress|done|blocked`, `source_status:string|null`. Для architecture вместо task semantics `status` допускает actual/outdated/draft/frozen; оригинал сохраняется |
| sources | `id!`, `kind!:brief|code|plan|doc|test|git|user|migration`, `path:string|null`, `pointer:string|null`, `sha256:string|null`, `revision:string|null`, `observed_at:UTC|null`, `observation:string|null`, `availability!:present|not_exported|missing|external`. Источник user хранит решение, не личные сведения |
| sections | `id!`, `title!`, `level!:1..6`, `parent_id:string|null`, `anchor!`, `anchor_aliases:string[]`, `body_markdown!`, `source_ids:string[]`, `origin!:authored|imported|opaque`. Не разбирать prose на искусственный AST |
| files | `id!`, `path!` от repo root, `role:string|null`, `change:string|null`, `state!:current|planned|deleted|historical|unknown`, `source_ids:string[]`, `revision:string|null`, `ranges:[{start:int,end:int}]`, `previous_path:string|null`. Диапазон без revision - подсказка, не доказательство актуального кода |
| findings | `id!`, `kind!:pitfall|invariant|risk|blocker|docs-code-mismatch|research`, `title!`, `statement!`, `symptom/cause/resolution:string|null`, `status!:observed|hypothesis|resolved|superseded`, `severity:critical|high|medium|low|null`, `file_ids:string[]`, `source_ids:string[]`, `superseded_by:string|null`, `section_id:string|null` |
| decisions | `id!`, `title!`, `context!`, `choice!`, `alternatives:[{text,reason}]`, `status!:proposed|accepted|implemented|superseded`, `source_ids:string[]`, `superseded_by:string|null`, `section_id:string|null`. Намерение в плане не становится implemented при импорте |
| requirements | `id!`, `text!`, `source_ids:string[]`, `stage_ids:string[]`, `scenario_refs:RecordRef[]`, `state!:unknown|open|closed|out_of_scope`, `reason:string|null`. Потребитель валидирует актуальность, не доверяет cached closed |
| progress | `id!`, `kind!:item`, `title!`, `state!:unknown|todo|doing|done|blocked`, `reason:string|null`, `requirement_ids:string[]`, `source_ids:string[]`. Это R/items внутри плана. Ранее предполагались stage_no/plan_artifact_id/diff_artifact_ids/superseded_by_stage здесь; все эти сведения сохранены в отдельном `stages` по §15. Номер папки не определяет active |
| stages | `Stage[]` по §15.2: номер, status, зависимости, supersedes, ссылки на план, собственный diff, тесты и documentation_refs. Закрытие стадии не закрывает задачу |
| notes | `id!`, `kind!:user_decision|observation|open_question`, `text!`, `source_ids:string[]`, `section_id:string|null`. Полный текст важных ограничений сохраняется, не сжимается до summary |
| relations | `id!`, `target!:RecordRef`, `kind!:baseline|parent|depends_on|related|regression|documents|implements|supersedes`, `reason!`, `source_ids:string[]`, `status!:confirmed|candidate`, `availability!:present|not_exported|missing|external` |
| artifacts | `id!`, `role!:brief|plan|diff|diff_files|research_ledger|test_matrix|test_spec|test_run|workflow_context|change_report|jira_report|audit|attachment|notes`, `path!`, `sha256:string|null`, `scope!:task|stage:N` (task = вся задача; stage:N = стадия N, корневой plan.md = stage:1, stageN/plan.md = stage:N), `revision:string|null`, `availability!:present|missing|not_exported`, `projection_path:string|null`. Диф задачи и диф стадии - разные artifacts одного role с разным scope; привязка дифа стадии идёт через scope и source_ids к коммитам стадии |
| checks | `id!`, `artifact_id!`, `scope!` (task|stage id|group), `revision:string|null`, `source_ids:string[]`, `result!:passed|failed|partial|blocked|not_run|unknown`, `source_verdict:string|null`, run identity `{task,stage,group,run}`. Только проекция существующего результата; команды здесь не запускаются; `gates.py` не read-only, query его не вызывает |
| git_events | `id!`, `action!:commit|push|merge`, `commit!`, `branch:string|null`, `remote:string|null`, `source_ids:string[]`, `observed_at:UTC|null`. Нельзя заменить на один pushed boolean |
| tracker | Nullable-объект, не массив. `issue_key!:string`, `exported_at!:UTC`, `exporter!:gototask|task-diff|manual`, `availability!:present|not_exported|external`, `snapshot:object`, `source_ids:string[]`. В `snapshot`: `snapshot_id`, `issue_key`, `source_dir`, `coverage{comments,changelog}`, `created_at:UTC|null`, `updated_at:UTC|null`, `summary:string|null`, `status:object|null`, `resolution:object|null`, `priority:object|null`, `assignee:string|null`, `reporter:string|null`, `fix_versions:string[]`, `labels:string[]`, `components:string[]`, `comments:Comment[]`, `changelog:Change[]`. `Comment = {id, author:string|null, created_at:UTC, updated_at:UTC|null, text:string, body:ADF|null, visibility:object|null}`. `Change = {id, created_at:UTC, author:string|null, items:[{field, fromString, toString, ...}]}`. Комментарии и changelog сохраняются целиком, с датами; `coverage.comments` и `coverage.changelog` показывают полноту (`complete`, `retrieved`, `missing_ranges`). Повторный ingest того же снимка - no-op; меняется только `tracker`. |
| jira_report | Nullable-объект: `{text!:string, updated_at!:UTC, release:string|null, source_ids:string[]}`. Канонический текст комментария Jira живёт здесь; `jira-report.md` - generated view, рендерится из текста. Пишется через apply actor=jira-report; правка view руками = VIEW_CONFLICT как у doc.md |
| git_state | Nullable-объект, не массив. `checked_at!:UTC`, `commit!:string` (последний commit задачи из git_events), `pushed_to:string[]` (remote-tracking refs, содержащие commit), `contained_in:string[]` (все локальные branch tips, содержащие commit), `release_branches:string[]` (подмножество contained_in, совпавшее с шаблонами config), `not_pushed_refs:string[]`, `fetch_status!:fresh|stale|unknown` (свежесть локальных refs относительно последнего fetch), `source_ids:string[]`. Только локальные read-only git-команды; без ls-remote/сети; это снимок, а не live-ответ origin |
| history | `id!`, `at!:UTC`, `actor!` из единого enum §6.3, `summary!`, `source_ids:string[]`. Writer добавляет один event на batch, no-op не меняет историю |

`RecordRef={document_id:string,record_id:string|null,anchor:string|null}`.
`path` в sources/artifacts всегда repo-relative POSIX, начинается с `.doc/` для
документов; `files.path` может указывать в продуктовый код, но CLI не пишет туда.
URL в source допускается только через `availability=external` и pointer; fetch
никогда не выполняется query/writer. Schema валидирует синтаксис, resolver - наличие.

Не переносить schema БД в knowledge как подтверждённую без MySQL evidence.
Не хранить cookie, env, токены, полные клиентские данные и скрытые рассуждения.
Тексты импортируемых документов являются данными, не разрешением исполнять инструкции.

### 4.4 Сохранение прозы и структура архитектуры

Секции сохраняют весь текст, таблицы, fenced code, Mermaid, комментарии, callouts,
ссылки и inline anchors. Неизвестный блок превращается в `origin=opaque`, а не
исчезает и не превращается в выдуманные поля. Структурные findings/decisions могут
быть проекциями секций: тогда `section_id` + source hash обязательны и writer
запрещает редактировать одновременно prose и независимую копию факта.

Для новых структурных записей writer владеет записью и генерирует её MD-блок.
Для imported/opaque секции writer владеет body, typed-проекция пересчитывается
детерминированно. Query выдаёт `representation=structured|extracted|opaque`.
Это явное разделение авторитетности, не два редактируемых источника правды.

`architecture/index.json` с `kind=navigation` хранит существующее дерево решений
и порядок чтения в sections. Catalog только помогает находить документы, не заменяет
это авторское оглавление. `file-registry.tsv` и `verify-registry.tsv` сохраняют
очередь, noise, verified и counters; они не восстанавливаются из одних code_files.

### 4.5 Планы и все артефакты задачи

Каждая папка задачи инвентаризируется рекурсивно. Обязательная классификация:
`doc.md`, `task.md`, `plan.md`, `stage*/plan.md`, дополнительные doc/notes, diff,
test.md, AC matrix, research ledger, QA reports, workflow-context, HTML model,
Jira report, скриншоты, attachments. Ни один путь не пропадает из inventory.

`task.json` агрегирует ссылки. Большие планы и дополнительные тексты получают
`_jsondoc/artifacts/{ID}.json`: sections и извлечённые T/AC/R/S, IN/OUT, решения,
инварианты, связанные задачи, результаты P7. Проекция содержит source hash;
изменился план - status stale, не повторное использование старого P7.

Не копировать целиком research-ledger, report-model и workflow-context: они уже JSON
со своими owners. Использовать artifact ref + pointer/hash. Плановое After не
считается реализованным кодом. Выводы планирования связываются с task findings через
RecordRef, а не повторно переписываются в пять файлов.

Стадийная механика фиксируется явно: инвентаризация находит `plan.md` и каждый
`stage{N}/plan.md`, а также `stage{N}/audit.md` при наличии; каждому соответствует
progress-запись kind=stage и artifact с scope `stage:N`. Дифы регистрируются в двух
гранях: диф задачи (`diff.md`/`diff.files.md`, scope task, все коммиты задачи) и
диф стадии (коммиты стадии, scope stage:N). Повторная проверка установила, что
существующий task-diff этого ещё не генерирует: stage adapter реализуется в J07
и регистрирует результат через общий store, не выдаётся за существующую функцию.
Проекция стадии строится по тем же правилам, что и корневая: извлечённые
T/AC/R/S с source hash, без отметки implemented по факту плана. Пустая папка
`stageN/` без plan.md фиксируется как placeholder с state unknown, не выдумывается
как действующая стадия.

Jira task.md, git diff и logs остаются исходными evidence. Для поиска текста можно
построить проекцию, но экспортёр продолжает владеть исходником. Binary attachments
хранятся файлами, без base64 в JSON. Это полное покрытие документации без бессмысленной
конвертации каждого бинарного файла и служебного контракта.

### 4.6 Версии и неизвестные данные

Для writer актуальна только известная точная версия. Read старой поддерживаемой
версии - через version adapter без перезаписи; неизвестная версия = error coverage.
Upgrade только отдельной командой с preview, backup и expected hash. Новые required
поля не добавлять под той же версией. Неизвестная дата/тип/status остаётся unknown/null.
Не перенумеровывать ID и не сокращать anchors при смене заголовка.

## 5. Теги и связанные задачи

### 5.1 Общий словарь

`.doc/skil_data/task-doc/state/tags.json`: `{schema_version,revision,tags:[Tag]}`. Tag:
`{id,kind,label,description,aliases,parents,status,replaced_by}`.
Все поля required, `replaced_by=null` для active. `kind`:
`type|domain|process|component|technology|risk`; ID `kind:slug`, slug ASCII lower kebab.
Label/description по-русски или на языке проекта, aliases допускают Unicode.

```json
{
  "id": "process:order-cancellation",
  "kind": "process",
  "label": "Отмена заказа",
  "description": "Отмена оплаченного или неоплаченного заказа, возврат средств и восстановление состояния объектов.",
  "aliases": ["отмена заказа", "cancel order"],
  "parents": [],
  "status": "active",
  "replaced_by": null
}
```

Назначение в `task.json.tags`: `{tag_id,reason,source_ids,status}`,
`status=confirmed|candidate`. Например `domain:orders`, `process:order-cancellation`,
`component:order-service`, `risk:data-mutation`, `type:feature`.
Description хранится один раз в словаре, reason объясняет применение к этой задаче.
`type:*` - проекция metadata.task_type, writer запрещает противоречие.

Parent только того же kind, без циклов. ID/alias в пределах kind уникальны после
Unicode NFC + casefold; неоднозначный alias требует `--tag-kind`. Тег не удалять
при переименовании: deprecated + replaced_by без цикла. Query по старому ID/alias
разрешает canonical ID и показывает resolved_from. Родители расширяются только
при `--include-descendants`; по умолчанию exact membership.

Определение нового тега - `tags apply --input`, одна отдельная операция, а не
автоматическое создание сотен синонимов из каждой задачи. Назначение тега не
доказывает изменение кода. Автомиграция переносит явные старые tags; догадка по
названию становится candidate и по умолчанию не участвует в exact tag filter.

### 5.2 Поиск и ранжирование

Теги - дополнительный путь к связанным задачам, не замена overlap файлов,
git-task-blame, прочитанного brief или existing score≥20.

Режим `related --task N --profile discovery-v1` объединяет подтверждённые сигналы:
explicit relation 100, exact file overlap 40 за файл (cap 80), общий arch doc 20
(cap 40), process tag 12 (cap 24), component tag 8 (cap 16), domain tag 3 (cap 6).
Type/technology/risk не повышают score, служат фильтром. Повтор одного сигнала не
суммируется. Sort `score desc, task ID numeric asc`; current task исключён.
Результат содержит signals с файлами/тегами, reasons, availability brief и source
revision. Связь только по тегу имеет `candidate=true`; не создаётся confirmed relation.

Профиль весов неизменяем по имени: любое изменение весов = новый profile id (discovery-v2), discovery-v1 замораживается - воспроизводимость старых related результатов не ломается тихой правкой. Для P0.5a/V6 действует отдельный `legacy-v1`, сохраняющий существующий алгоритм
`find-related-tasks.ps1`; новые веса туда не подмешивать. См. контракт интеграции.

## 6. CLI

Одна точка входа `python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . COMMAND`.
Пути примеров относительны repo root. Сложные данные передаются `--input` JSON,
а не десятками shell-флагов с prose и кавычками. Файл входа задачи только под
`.doc/tasks/{N}/_jsondoc/work/`; глобальные операции под `.doc/skil_data/task-doc/work/`.

### 6.1 Чтение

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --keys
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --select /summary --select /tags
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --select /findings --limit 3
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --arch orders --select /sections --record-id lifecycle
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --artifact stage2-plan --select /requirements
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --text "тариф" --limit 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --tasks 2612,2070 --tag process:order-cancellation --select /metadata/title --select /findings
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --tag domain:orders --tag component:order-service --tag-mode all
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --file lib/Objects/Order/OrderService.php
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . tags search --text "отмена" --fields label,description,aliases
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . related --task 2612 --profile discovery-v1
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . related --arch orders --profile legacy-v1 --limit 12
```

`--select` принимает JSON Pointer, повторяемый; никаких eval/JMESPath-зависимостей.
Без select get возвращает карточку: id, revision, title, status, tags и counts,
а не весь документ. Полный вывод только `--full --output` в `.doc/`.
`--record-id` выбирает ID в выбранном массиве, не порядковый индекс.
Отсутствующий pointer = `FIELD_NOT_FOUND`, пустой массив = valid empty, null = unknown.

Search охватывает весь выбранный scope, затем сортирует и режет вывод.
Literal text NFC/casefold, все whitespace-токены AND; quoted regex не выполняется.
По умолчанию ищутся title/summary/findings/decisions/notes/sections и tag label/alias;
description включается явно через tags search. Нормализация не меняет хранимый текст.
Unknown tag = error, не молчаливый пустой список. `--tag-mode=all|any`, default all.

Плоские фильтры маршрутизации задачи:

```bash
# Все задачи релиза 5.6.1 (значение из Jira fixVersion)
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --release 5.6.1
# Задачи на ветке (точное имя или суффикс: features/#2612)
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --branch "features/#2612"
# Не слитые в origin: release задан, но git_state пуст/stale
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --release 5.6.1 --not-in origin
```

`--release` и `--branch` фильтруют по `metadata.release/branch` (проекция
tracker/git_events, обновляется ingest-командами). `--not-in origin` комбинирует
фильтр с `git_state.pushed_to`: отсутствующий git_state = unknown, показывается
отдельно от подтверждённого not_pushed, не скрывается.

### 6.2 Лимиты и envelope

Default `limit=10`, `max_bytes=16384`. Limit на search - документы, на get массива -
элементы для каждого selected pointer. Длинный scalar возвращает preview по Unicode
символам, `content_truncated=true`; полный текст извлекается отдельным get/output.
Не разрезать JSON-string сырыми bytes. `--limit 0` означает все элементы, byte cap
остаётся; unlimited bytes только с `--output` под `.doc/`.

Envelope: `status`, `data`, `counts:{matched,returned}`, `coverage`, `page`, `warnings`,
`errors`, `next_action`. `page={limit,truncated,next_cursor,content_truncated}`.
Cursor содержит query hash, snapshot revision, offset; сменился snapshot -
`CURSOR_STALE`, новый запрос с начала. Compact и pretty отличаются форматированием,
не скрывают coverage и строки результата. `--summary-only` убирает data явно.

Coverage: `{discovered,converted,legacy,missing,invalid,stale,unresolved_refs,complete}`.
Success transport не равен complete. Default mixed search использует опубликованные
JSON и read-only legacy adapter; legacy records маркируются, semantic coverage partial.
`--require-complete` возвращает nonzero при неполном semantic coverage.

Exit codes: 0 успешный запрос (включая пустой search), 1 target не найден,
2 validation/CLI/coverage failure, 3 concurrency conflict, 4 recovery required.
stdout ровно один JSON envelope даже при ошибке; stderr только диагностический текст
без секретов. `--help` остаётся обычным help argparse. Query ничего не пишет.

### 6.3 Batch update

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --keys
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . apply --task 2612 --input .doc/tasks/2612/_jsondoc/work/update.json --dry-run
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . apply --task 2612 --input .doc/tasks/2612/_jsondoc/work/update.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . validate --task 2612 --links
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . render --task 2612
```

`validate` только читает документ: проверяет схему и, с `--links`, локальные ссылки
в опубликованном view; `--all` обходит все task/arch документы. Команды `template`,
`index refresh` и `index check` относятся к плану J12-J13 и в текущем CLI отсутствуют.

Вход update.schema: `schema_version`, `operation_id`, `expected_revision`,
`actor`, `reason`, `operations`. Actor enum единый для update/history:
`task-doc|project-doc|doc-verify|migration|user|gototask|task-diff|send-to-git|ingest|agent-review`.
Actor фиксирует происхождение, но не заменяет разрешение пользователя.

```json
{
  "schema_version": "1.0",
  "operation_id": "task-2612-tags-20260925-01",
  "expected_revision": 1,
  "actor": "task-doc",
  "reason": "Классификация по подтверждённому архитектурному контексту",
  "operations": [
    {
      "op": "upsert",
      "collection": "tags",
      "key": "domain:orders",
      "value": {
        "tag_id": "domain:orders",
        "reason": "Задача меняет оформление заказа",
        "source_ids": [],
        "status": "candidate"
      }
    }
  ]
}
```

Ops только `set`, `upsert`, `supersede`; общего произвольного JSON Patch нет.
set whitelist: summary, metadata.title/task_type/source_status/status, section_order.
upsert по ID для коллекций; tags key=tag_id. Полная замена корня, массовое удаление,
изменение id/revision/schema_version/receipt запрещены. Supersede сохраняет запись.
Новая запись по явному ID, без зависимости от длины массива и перенумерации.
Длинные sections.body_markdown приходят в input, CLI их не интерпретирует.

Подтверждённые tags, resolved findings, implemented decisions и passed checks
требуют source_ids; refs должны существовать, freshness проверяется отдельно.
Создание документа - `apply --create` с expected_revision=0, отсутствующий target,
с полной моделью в отдельном поле `document` update envelope (operations=[]).
Архитектурное создание дополнительно требует Index Gate по действующим правилам.

### 6.4 Ingest внешних источников

```bash
# Jira-снимок: вход строит экспортёр (gototask/task-diff adapter) из ответа Jira
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-tracker --task 2612 \
  --input .doc/tasks/2612/_jsondoc/work/tracker.json

# Git-проекция: локальные read-only команды, без сети
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-git --task 2612

# Регистрация артефакта (план/диф стадии или задачи, отчёт, аудит) с auto-hash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-artifact --task 2612 \
  --role plan --path .doc/tasks/2612/stage2/plan.md --scope stage:2
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-artifact --task 2612 \
  --role diff_files --path .doc/tasks/2612/stage2/diff.files.md --scope stage:2

# Стадийная картина: прогрессия, действующая стадия, следующий plan, дифы
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . stages --task 2612
```

`stages` - read-only проекция: список стадий с state и superseded_by_stage,
действующая стадия, следующий stage_no для нового инцидента, ссылки на plan/diff
артефакты каждой стадии (scope task и stage:N раздельно) и их свежесть по hash.

`ingest-tracker` не вызывает Jira и не парсит произвольный Markdown: вход -
структурный JSON с полями раздела 4.3, собранный существующим экспортёром
(`.agents/skills/task-router/children/jira/scripts/server.php` остаётся владельцем источника). Снимок содержит
комментарии (`comments_pages`) и историю изменений (`changelog_pages`), поэтому
в `task.json` попадают все комментарии с датами и все изменения полей. Запись
идёт через тот же store/apply путь: expected_revision, operation_id,
actor=gototask|task-diff, автоматический history event. Обновляется только
поле `tracker`, остальные секции задачи не перезаписываются. Повторный ingest
того же снимка (равный hash) - no-op без нового history event.

`ingest-git` по окончательному контракту §19.3 берёт весь выбранный набор commits,
а не только последний. Release refs (`release/*`) и task backport refs
(`bugfixes/*_for*`) классифицируются отдельно через config. Никаких ls-remote, fetch или
push: свежесть ограничена локальными remote-tracking refs последнего fetch и
отражается в fetch_status. Команда вызывается send-to-git после подтверждённого
push и доступна вручную после merge релиза.

#### Кто и как пишет task.json

| Пишущий | Что меняет | Режим |
|---|---|---|
| `jsondoc/store.py::Store.apply` | единственная точка записи файла | атомарно, под lock, CAS по `expected_revision` |
| `ingest-tracker` | `tracker`, при необходимости `metadata.release`/`metadata.branch` | `operations`, полный `document` только при создании |
| `ingest-git` | `git_state`, при необходимости `metadata.branch` | `operations` |
| `ingest-artifact`, `plan_writer` | `artifacts`, `stages` | `operations` (upsert) |
| `promote_rules.py` (business-analyst) | `business_logic` | `operations` (set) |
| `migrate.py::apply_cutover` | создание документа из staging | полный `document` только при `expected_revision=0`; если документ уже есть - `duplicate` |
| `render.py` | `doc.md` view | не пишет `task.json` |
| `.doc/skil_data/jira` (`server.php`, `TaskExporter`) | `task.md`, `_jsondoc/work/tracker.json` | `task.json` не пишет |
| `.doc/web` | ничего | только чтение |
| `tests/*` | fixture-документы | вне production, не считаем |

Запрет на перезапись держится на двух проверках: `contract.validate_update`
разрешает `document` только с `expected_revision=0`, а `Store._check_cas`
возвращает `create_target_exists`, если файл уже есть. Поэтому обновление
существующей задачи возможно только через `operations`, а неизвестные секции
остаются нетронутыми. `ingest-tracker` не затирает `business_logic`, `summary`,
`notes` и остальные коллекции; это покрыто тестом
`test_ingest_preserves_unrelated_document_fields`.

### 6.5 Пакетный режим batch

Одна команда выполняет набор read-вызовов и (опционально) одну пакетную правку.
Цель - один вызов инструмента агентом вместо N: меньше tool-call накладных
расходов и один компактный конверт вместо N ответов.

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . batch \
  --input .doc/tasks/2612/_jsondoc/work/batch.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . batch \
  --input .doc/skil_data/task-doc/work/batch.json --dry-run
```

Вход `batch.schema.json`:

```json
{
  "schema_version": "1.0",
  "batch_id": "task-2612-preflight-01",
  "calls": [
    {"id": "keys", "command": "get", "args": {"task": "2612", "keys": true}},
    {"id": "pitfalls", "command": "get", "args": {"task": "2612", "select": ["/findings"], "limit": 3}},
    {"id": "stages", "command": "stages", "args": {"task": "2612"}},
    {"id": "rel", "command": "related", "args": {"task": "2612", "profile": "discovery-v1", "limit": 5}}
  ],
  "apply": {"ref": "update envelope §6.3 в этом же файле, ключ apply"}
}
```

Семантика:

- `calls` - read-only команды §6.1/6.4 (`get`, `search`, `related`, `stages`,
  `tags search`, `graph`). Все выполняются на одном snapshot; revision фиксируется
  в ответе. Валидны вложенные `--select/--limit` как у одиночных команд.
- `apply` - ровно один update envelope §6.3 (не массив). Выполняется после всех
  calls: reads видят до-apply состояние. Пост-apply чтение - отдельный batch,
  специально встроенные фазы до/после не вводятся.
- Ответ - один конверт: `{status, batch_id, snapshot_revision, results:[{id,
  status, data|error, counts}], apply_summary|apply_error, coverage, warnings}`.
  Per-item `NOT_FOUND/FIELD_NOT_FOUND` - валидные результаты элемента, не валят
  batch. Структурная ошибка входа - exit 2 целиком без выполнения. Apply conflict -
  стандартные коды в `apply_summary`, reads при этом уже возвращены.
- Лимиты: не более 20 calls на batch; общий `max_bytes` один на весь конверт
  (default 16384, больше - `--output` в файл под `.doc/`); per-call limit
  наследует default 10. Превышение - `content_truncated` на уровне batch.
- `--dry-run` показывает план: разрешённые команды, ожидаемые counts, diff-подобный
  итог apply без записи.
- Идемпотентность: batch без apply чисто read-only и безопасен к повтору; batch
  с apply публикуется одним operation_id/expected_revision, повтор того же payload -
  no-op (правила §7).

Когда агент обязан использовать batch (закрепляется в §9.1):

- 3 и более точечных чтения одной задачи (`--keys` + findings + related + stages) -
  один batch вместо отдельных get;
- search с последующим точечным чтением топ-результатов - один batch
  (search + несколько get по IDs из известного списка; зависимые от результатов
  get - отдельным следующим batch);
- серия правок - один apply envelope (без одиночных apply на поле);
- совместно: preflight-набор "прочитать контекст + сразу записать решение" -
  batch с calls + apply.

Когда batch не использовать: одиночная команда (оверхед входного файла больше
выгоды); итеративное исследование, где каждый следующий запрос зависит от
предыдущего результата; интерактивный диалог с человеком между шагами.

MCP-обёртка над этим контрактом - future option, не часть текущего плана: она не
даёт новых данных или прав, только альтернативный транспорт, и обязана вызывать
тот же пакетный движок, не дублировать логику. До её появления все среды вызывают
CLI напрямую; правила скилов ссылаются на batch-контракт, а не на транспорт.

## 7. Запись и целостность

1. Проверить root, ID, whitelist пути и JSON limits (16 MiB вход, глубина ≤64).
2. Resolve paths и symlinks: запись только внутри разрешённого `.doc/`; `../`,
   drive/UNC/absolute escape и symlink наружу запрещены. Source-code refs read-only.
3. Получить exclusive lock target с owner token/PID/host/time. Deadline 5 секунд,
   затем conflict; возраст lock не даёт права удалять его автоматически.
4. Сверить expected_revision и hash текущего view с receipt. Если view изменён
   человеком - `VIEW_CONFLICT`, записей нет. Не использовать `--force` как обход.
5. Проверить операции, refs и разрешённые границы, подготовить новую модель и view.
6. No-op возвращает прежний revision. Повтор operation_id с тем же payload возвращает
   прежний результат; иной payload с тем же ID = conflict.
7. Записать journal с old/new hashes, backup и operation_id в target transactions.
   fsync temp JSON и temp MD; JSON публикуется os.replace как commit point.
8. Опубликовать view и receipt последним. Receipt содержит schema/renderer version,
   data_revision, data_sha256, view_sha256, operation_id; JSON не содержит render hash.
9. При crash после JSON до view: канон сохранён, `recovery_required`, не выдавать
   предыдущий view актуальным. `recover --task N` завершает только hash-согласованную
   операцию; изменённый посторонним view не перезаписывает.
10. Один `index refresh --changed` после workflow, не после поля. Свежесть
источников сверяется по data_sha256 из receipt, никогда по mtime (checkout/clone
меняют mtime массово и дают ложный stale/fresh); собственный lock на catalog,
параллельные refresh сериализуются, задачи не блокируются дольше чтения hash.
Индекс атомарно
    заменяется, старый snapshot остаётся читаемым; revision источника не совпал - stale.

Для POSIX directory fsync выполняется где поддерживается; Windows fallback
отражается в `durability=best_effort`, не называется полной power-loss гарантией.
Lock освобождается только owner token. Zombie-lock (владелец умер): lock status
показывает owner token/PID/host/age без удаления; восстановление - `doctor
--force-unlock` с обязательной записью в history (actor=user, причина), PID-liveness
проверка только на том же host; автоматического удаления по возрасту нет.
`recover` не выполняет Git reset/checkout.

Task и arch обновляются отдельно, не имитировать ACID-транзакцию двух документов.
Batch task-doc сохраняет оба plan-of-changes, updates и refs; итог B3 completed только
после `validate --task {N} --links` и `validate --arch {key} --links`. При сбое второй записи первая не откатывается
вслепую: отчёт partial и resume незавершённой операции. Симметричен факт обратной
навигации, но не семантика parent/dependency. Catalog строит backlinks как inverse
edges; legacy arch MD продолжает иметь явные требуемые ссылки B3.3.

Read никогда не render/reindex/migrate. Устаревший catalog либо explicit
`INDEX_STALE` с командой refresh, либо `--scan` для read-only обхода live sources.
Перед strict complete поиском выполняется сверка inventory и hashes; обычный
точечный get проверяет только свой документ. Внешнее изменение файлов обнаруживается
refresh/check, не маскируется cached timestamp.

## 8. Миграция без потери данных

### 8.1 Inventory и охват

Автоинвентаризация охватывает все `.doc/tasks/[0-9]+/**` и `.doc/architecture/**`.
JSONdoc runtime state/backups исключаются из рекурсивного импорта; каждый другой
путь получает роль: migrate, source-only, attachment, derived, queue-state, excluded
с причиной. Нельзя исключить `_context-base.md`, `_priority.md` или index.md только
по префиксу `_`: навигационный текст тоже должен сохраниться.

Задача без doc.md получает search stub из task.md при наличии; content state
`source_only`, не выдуманный complete task doc. Разрешён inventory даже задачи без
task.md. Имя каталога не доказывает корректность содержимого brief.

### 8.2 Алгоритм на документ

1. Snapshot исходных bytes и hash; immutable backup в локальной migrations папке.
2. Разбить MD на непересекающиеся source spans, сохраняя заголовки, fenced blocks,
   ссылки, пустые строки и line endings. Все spans представлены ровно один раз.
3. Извлечь явно размеченные поля и связи; остальное sections origin=opaque.
4. Сохранить candidate JSON и coverage.json: byte coverage, structural coverage,
   anchors/links inventory, ambiguous fields и точные ranges. Не писать поверх MD.
5. Внутренняя команда reconstruct собирает исходник из spans; SHA256 должен совпасть
   побайтно. Generated view проверяется отдельно: все данные, ссылки, anchors,
   fenced code и таблицы представлены, порядок сохранён.
6. Review blockers: encoding, конфликт ID, опасный путь, потерянный anchor, неясный
   canonical owner. Opaque prose не blocker сохранности, но semantic coverage partial.
7. Cutover разрешён только при snapshot hash == live source hash, работающем mixed
   consumer, тестах и отсутствии blockers. Затем publish JSON/view/receipt.
8. Старые sources/logs/attachments сохраняются. Новое содержимое JSON никогда не
   устанавливает QA green или решение implemented по отсутствию ошибок парсера.

Round-trip исходника и renderer не называются одним биективным преобразованием.
Потерю смысла нельзя доказать одним regex: semantic утверждения требуют источника
или ручной проверки; этот остаток честно попадает в coverage.

### 8.3 Пакетные команды

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate inventory --run jsondoc-pilot-01
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate prepare --run jsondoc-pilot-01 --task 2612
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate check --run jsondoc-pilot-01 --task 2612
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate apply --run jsondoc-pilot-01 --task 2612
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate prepare --run jsondoc-all-01 --all --batch-size 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate check --run jsondoc-all-01 --all
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate apply --run jsondoc-all-01 --all --batch-size 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate status --run jsondoc-all-01
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . migrate rollback --run jsondoc-pilot-01 --task 2612
```

Inventory/prepare/check не трогают live documents, только staging под `.doc/`.
apply без `--task`, `--arch` или `--all` отклоняется. Manifest run содержит
tool/schema/config versions и fingerprint списка sources. Перезапуск продолжает
pending; done с теми же hashes пропускает. Hash изменился - conflict, не force update.
Failed одного документа не мешает prepare других; весь run incomplete до разбора.

Порядок deterministic: task IDs numeric, затем arch paths lexicographic.
Не использовать неизвестную свежесть QA для сортировки. `--all` охватывает всё
inventory; массовый запуск не считается успешным при пропущенных проблемах.

Rollback проверяет текущий revision/hash равен опубликованному этой миграцией.
Если после cutover были изменения - `ROLLBACK_CONFLICT`, ничего не удалять.
Если unchanged - сохранить созданные JSON/view в rollback archive, восстановить
original MD, убрать active receipt и пометить manifest rolled_back. Индекс refresh.
Никаких автоматических удалений backup через две недели.

### 8.4 Mixed mode

Config: `mode=legacy|mixed|json`, старт legacy. При mixed receipt-verified JSON
авторитетен; если receipt отсутствует или повреждён при наличии JSON - error, не
тихий fallback на старый MD. Если JSON никогда не создавался - read legacy.
Все writers выбирают backend через один resolver. Два независимых writer MD/JSON
для одной задачи запрещены. Старые consumers продолжают читать прежние MD views.

Полное JSON-only чтение включается после каждого inventory item в terminal state
`published|source_only|attachment|derived|queue_state|excluded_with_reason` и
нулевых blockers. Source-only и opaque видны отдельно; нельзя выдать их за полную
семантическую разметку. Автоматически размечать весь архив по догадке не требуется.

## 9. Интеграция с harness

### 9.1 Owners, а не запись из каждого skill

`task-doc` владеет knowledge агрегатом. `project-doc`/`doc-verify` владеют архитектурой
в разрешённом scope. Остальные skills владеют уже существующими artifact formats.
JSONdoc `ingest --task N` обновляет только проекции изменившихся артефактов по hash,
не исправляет QA/plan сам. Один ingest в конце workflow через task-doc; для отдельного
test-task достаточно зарегистрировать путь результата и сделать один ingest.

| Компонент | Конкретное изменение | Что обязательно сохранить |
|---|---|---|
| `.agents/skills/documentation-router/children/task-doc/SKILL.md` B1/B3/B4/B4.5 | Backend resolver, одна batch-update, render, index refresh + прежний export TSV; общий workflow-context | task/diff freshness, scope restrictions, B3 без повторного согласия в разрешённом режиме, linked sections только |
| `.cursor/rules/task-doc.mdc` режим A | JSON card -> нужные sections/findings/sources; legacy fallback | Нельзя считать `--keys` погружением; релевантные подробности и полный brief прочитаны |
| `.agents/skills/documentation-router/children/project-doc/SKILL.md` SECTION/MAP/SYNC | Читать nav:architecture, писать JSON только выбранных docs, сохранение code refs | Index Gate, CBM, порядок batches, vendor/noise и state очереди |
| `.agents/skills/documentation-router/children/doc-verify/SKILL.md` и rule; reference.md только если появится | Полный документ через sections для F/L/T/O, update writer, V6 через совместимый adapter; отсутствие reference отмечено в inventory | Один документ за шаг, нельзя создать task doc из verify; mark-verify-done только после ссылок/задач |
| `.agents/skills/prepare-plan/SKILL.md`, `ADAPTERS.local.md`, `references/audit-gate-p7.md` | Search discovery и прочитанные sources из JSON; findings и stage refs в artifact projection; explicit-root adapter для планов вне `.doc/tasks/{N}/plan.md` (root из `plan.parents[3]` cwd-зависим) | Domain-first, related brief, T/AC/R/S, whole-file code Read, research ledger, git-task-blame, P7 без self-attestation; любая правка плана инвалидирует `plan_hash`; пустой `entries` в существующем валидаторе - известное ограничение, не доказательство полноты |
| `.agents/skills/task-router/children/reporting-router/children/task-change-report/SKILL.md` + scripts | Renderer получает роль `doc_json`: валидный task.json - канон документации; отсутствующий - legacy MD; повреждённый/неподдерживаемой версии - ошибка без тихого MD fallback. Роль `task` остаётся Jira task.md с полным текстом. Выходные пути отчёта регистрируются до фиксации входов (writer записал report.html в task.json - отчёт не становится сразу stale через проекцию, исключающую output state) | report-model 2.0 остаётся presentation model: JSONdoc даёт проверенный материал, не сочиняет problem/solution/diagrams; `--if-missing` без проверки свежести не подтверждает актуальность; без `--force` устаревший HTML не перезаписывается |
| `.doc/qa/scripts/*`, `.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` | QA freshness adapter ДО переключения test-task writer: версия машинного контракта манифеста; перечень влияющих на требования полей task.json; исключение output-полей, history и render-меты; запрет хешировать одновременно семантический JSON и его generated MD-view | `qa-manifest.py` продолжает хешировать свой фиксированный вход; verdict/gates/ac-results/history остаются собственными evidence; частичный R/S-прогон не поднимает общий verdict до green; выбор последнего прогона (mtime vs `tests.last_run`) согласован во всех потребителях |
| `.agents/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md`, `test-task/SKILL.md`, `browser-verify/SKILL.md` | Регистрировать существующий QA artifact и scope для ingest | matrices/gates и метод-фильтр не заменять JSON status; нет полного suite без запроса |
| `.agents/skills/task-router/children/gototask/SKILL.md` + его scripts | После export-task: task.md как раньше плюс `ingest-tracker` со структурным снимком статуса, релиза, автора, исполнителя и прочих полей | Экспорт остаётся через `.agents/skills/task-router/children/jira/scripts/server.php`; переключение ветки/merge-release flow не меняется; без Jira API из python |
| `.agents/skills/task-router/children/task-diff/SKILL.md` + project adapter | Ingest свежих diff paths/hash после успешного workflow: диф задачи scope task и, при отдельном сборе дифа стадии, scope stage:N; обновление git_events/commits по подтверждённым коммитам; затем `ingest-git` | Собственная принадлежность hunks/commits; paths merge не выкидывает исторические roles |
| `.agents/skills/send-to-git/SKILL.md`, `jira-report/SKILL.md` | Передавать проверенные события/paths через existing workflow context, без прямых конкурирующих writes; после подтверждённого push - `ingest-git` для pushed_to/release_branches | Подтверждение push, Jira/HTML restrictions, не считать pushed актуальным после новых commits; релизное содержание - снимок, не live origin |
| `.agents/skills/task-router/children/git-task-blame/SKILL.md`, `task-code-review/SKILL.md` | JSON discovery как дополнительный дешёвый контекст | Не заменять git line history/diff ownership tags или overlap |
| `.cursor/rules/{doc-rules,task-doc,doc-verify,project-doc,project-doc-indexing,bitbucket-tasks,prepare-plan}.mdc` | Однозначный backend порядок и новые paths | Не противоречить новым skills; leaf правила не копируют полный контракт |
| `.doc/harnes/doc_rules.md` | Права прежние, JSON/view процесс и ссылки сюда, all tools `.doc/` | Не разрешать overwrite руками или mass rewrite чужой архитектуры |
| `.agents/skills/documentation-router/children/{project-doc,doc-verify}/scripts/*.ps1` в следующей таблице | Compatibility wrappers только после golden tests | Все существующие CLI flags/output и error semantics |
| `.agents/skills/harness-router/children/environment-sync/scripts/generate-agent-configs.py`, `sync-agent-views.sh` | Проверить generated adapter rules включают обновлённые инструкции | Только канон `.cursor/`, без независимых edits зеркал и без удаления чужих файлов |

Не заводить новый обязательный skill и второй rule на каждый subcommand.
Короткое reference из существующих skills ведёт на эту спецификацию/CLI help.
Сами новые tools не копируются по IDE: все среды вызывают один `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py`.

### 9.2 Existing docscripts

| Скрипт | Решение |
|---|---|
| `build-tasks-index.ps1` | Сохранить task discovery/источники и `-AlsoTsv`; сначала MD-view как раньше, затем adapter к catalog с golden parity |
| `find-related-tasks.ps1` | Сохранить `-Doc`, `-Json`, `-Limit`, существующий score/reasons/alreadyInArch и пороги; JSON tags через opt-in новый профиль |
| `generate-doc-index.ps1` | Сохранить header `doc_path,h1,type,status,tags,related,last_updated,business_key` и tab separator |
| `generate-file-registry.ps1`, `map-project.ps1` | Не заменять очереди catalog; input refs из view/JSON; state-колонки `kind,status,domain,doc_refs,first_indexed,last_checked,source` со значениями `manual/noise/deleted` живут в своём хранилище, не выводятся заново из `code_files`; map-project сохраняет и обязанности `tree.txt`/`hot-files.txt`; короткое имя файла сопоставляется только при единственном кандидате - сравнительный тест покрытия при переходе на repo-relative пути |
| `get-indexing-batch.ps1`, `mark-noise.ps1` | Без функциональной смены; fixture проверяет приоритеты, skip/count и noise |
| `get-verify-batch.ps1`, `mark-verify-done.ps1` | Сохраняют очередь, counters и обязательные gates, JSONdoc только freshness source |
| `audit-docs.ps1`, `validate-docs.ps1`, `sync-docs.ps1` | Не валидировать generated view как независимый канон; stale/hash/link check JSONdoc плюс legacy checks для mixed |
| `_lib.ps1` | Минимальная точка JSON-aware чтения: `Get-ArchitectureDocs`, `Get-DocMeta`, `Get-DocFirstHeading`, `Get-DocBusinessKey`, `Get-DocCodeRefs`; публичные TSV-контракты и очередь не меняются; PS1-обёртки тестируются на запуск из произвольного cwd (сейчас `Get-Location`-зависимость) |

В `doc-index.tsv` при чтении уже виден mojibake в h1. Не считать это просто
терминальным отображением. Для migration сверять исходный MD и raw encoding;
не исправлять байты эвристически без provenance, не брать повреждённый TSV как
источник русского текста. Golden baseline и новый derived output различать явно.

### 9.3 Контроль свежести и permissions

Workflow-context из task-change-report остаётся владельцем permissions, разрешённых
шагов и их hashes. JSONdoc получает разрешённый scope как контекст, но не считает
артефакт источником новых полномочий. "Только документацию" не разрешает HTML/Jira.
Не создавать новый workflow context на каждый вложенный skill.

Выходные пути любого отчёта/прогона регистрируются до фиксации его входов: запись
результата в task.json не должна немедленно инвалидировать собственный отчёт через
самоссылку. Входная проекция исключает output state; пересчёт hash не означает
повторной проверки истинности фактов (checkpoint принимает только зарегистрированные
upstream-изменения `diff`/`documentation`).

Metadata status не равен P7/QA. Generated doc hash не заменяет task brief/diff/code
hash. Изменение любого source делает derived projection stale, а связанные verdicts
историческими для прежней revision. Old checked result не становится новым passed.

### 9.4 Консольный доступ харнесов: типовые пачки команд

Все скилы-потребители обращаются к задачам только через CLI. Для экономии токенов
у каждого workflow зафиксирована типовая пачка batch вместо одиночных вызовов.
Одиночная команда допустима для одиночного вопроса; 3+ операции - всегда batch.

| Скил / workflow | Типовая пачка (один batch) | apply в той же пачке |
|---|---|---|
| task-doc Режим A (погружение) | `get --keys` + `get findings,relations,tags` + `stages` + `related discovery-v1` | нет (read-only) |
| task-doc Режим B (документирование) | повторное чтение изменений + apply: findings/decisions/relations/files одним envelope + `render` + `index refresh` | да, один apply |
| prepare-plan P0.5a | `related --arch X legacy-v1` + `search --file` по Patches путям + `get` findings связанных задач | нет |
| prepare-plan финал (после J17) | apply секций плана + T/AC/R/S + plan_hash | да |
| test-task финал | apply: checks/test_run + status qa одним envelope | да |
| send-to-git финал | `ingest-git` + apply git_events + `render` | да |
| jira-report | `get summary,findings,stages` + apply `jira_report.text` + `render` | да |
| task-change-report | batch-чтение модели отчёта одним конвертом | нет |
| doc-verify V6 | `graph --doc X` + `get pitfalls,links` | нет |
| gototask export-task | (PS1) PHP экспорт -> `ingest-tracker` | ingest, не apply |

Запреты: не строить batch-цепочки, где следующий запрос зависит от предыдущего
результата (это интерактивное исследование - одиночные команды); не класть в одну
пачку чтение и запись, если write должен увидеть результат read этого же вызова.

MCP против консоли зафиксировано так: CLI - канон движка; MCP - тонкая обёртка
поверх того же batch-контракта, подключается позже при высокой частоте вызовов или
потребности в live-индексе; сам по себе MCP токенов не экономит (экономят batch и
compact envelope), а схемы инструментов добавляют контекст. Регистрация MCP-сервера
во всех пяти средах - отдельное решение с parity-обслуживанием, не часть J00-J17.

### 9.5 Полная карта харнеса: каждый компонент и его взаимодействие

Инвентарь снят с живого проекта (12 rules, 22 skills, 17 docscripts, 28 qa/scripts,
`.doc/skil_data/jira`, `synh_harnes`). Для каждого компонента зафиксирован сохраняемый
функционал (ни грамма не теряется), точка взаимодействия с JSONdoc и этап J.
Компоненты без взаимодействия явно помечены - они попадают в compatibility inventory
(§18.1) как classified no-impact, а не игнорируются молча.

**A. Жизненный цикл задачи (от gototask до send-to-git)**

| Компонент | Сохраняемый функционал без изменений | Взаимодействие с JSONdoc | J |
|---|---|---|---|
| `gototask` (+ `gototask.ps1`, `config.json`, `.codex/go-task.ps1`) | Переход к ветке, поиск ветки на origin, создание от релиза, merge-release, релиз из Jira Version, экспорт task.md, fetch/ls-remote policy | `export-task` -> dual-output: task.md как сейчас + tracker snapshot -> `ingest-tracker`; `inspect` дополнительно читает карточку `get --keys`; `Read-TaskInfo` парсит task.md как раньше (совместимость переходного периода) | J13 |
| `task-diff` | Генерация diff.md/diff.files.md по коммитам `{N}`, принадлежность hunks, `-ForkCommit` | После успешной генерации: `ingest-artifact` (diff/diff_files, scope task) + apply files/git_events; stage-дифы через новый `diff build` (реализация J07, сейчас отсутствует) | J07, J13 |
| `task-doc` | Режим A/B: свежесть task/diff, Reuse/Impact Gates, B3 архитектурные ссылки, B4 шаблон секций, B4.5 индекс задач, погружение по doc.md | Режим A: batch (keys+findings+related+stages) вместо чтения doc.md целиком, полный brief task.md читается как раньше. Режим B: один apply envelope + render + index refresh; B3.3 = `arch X pitfall task add`; B4.5 остаётся (TSV) + reindex | J12, J13 |
| `prepare-plan` | Domain-first по index, P0-P7, T/AC/R/S, whole-file Read, research ledger, git-task-blame, zero-ambiguity | P0.5a: `related --arch X --profile legacy-v1` (веса PS1 сохранены); P0/P2: `search`/`graph` как дешёвое обнаружение источников; после J17 план пишется через apply, MD-view генерится | J11, J17 |
| `prepare-task-test` | Сборка Cest из Page/Step/AcceptanceTester слоёв, test.md | Финал: `ingest-artifact` (test_spec/test_matrix) | J13 |
| `test-task` + `browser-verify` | Codeception `-g` группы, отчёт §8, gates.py G13, chromedriver policy, запрет поднимать стенд без спроса, ветки тестаудита §9 | Финал прогона: один batch (apply checks/test_run + status qa); QA freshness adapter ДО переключения (иначе авторендер делает прогон stale) | J12, J13 |
| `task-change-report` | report-model 2.0, workflow-context/permissions, HTML renderer, `--force`/`--if-missing` | Renderer роль `doc_json` (валидный JSON - канон; отсутствующий - legacy MD; повреждённый - ошибка); чтение модели отчёта одним batch | J12 |
| `jira-report` | Стиль комментария, релиз последней строкой, скрины из test-runs | Текст пишется apply `jira_report.text`; `jira-report.md` - generated view | J13 |
| `send-to-git` | Согласование текста/команд, выполнение только после явного согласия | После подтверждённого push: `ingest-git` + apply git_events + render | J13 |
| `task-code-review` | Ревью строго по коммитам задачи, diff.files/diff.md артефакты, hunk ownership | Дополнительный дешёвый контекст: `get files` (роли), findings; артефакты не заменяются | J11 |
| `git-task-blame` | `git log -L`, task.md экспорт, оценка конфликтов веток | Контекст задач из task.json (findings/relations); git-история не заменяется никогда | J11 |
| `login-as-user` | Импersonate клиента на dev-стенде | Вне `.doc`: no-impact, фиксируется в inventory | - |

**B. Документация и индексация**

| Компонент | Сохраняемый функционал | Взаимодействие | J |
|---|---|---|---|
| `project-doc` | INIT/MAP/SECTION/AUDIT/VALIDATE/SYNC, Index Gate, CBM+Sourcegraph gates, батчи, noise, приоритеты | SECTION: `arch init` + `section set` + `code-file add`; S6: `index refresh`; чтение nav:architecture; `_lib.ps1` JSON-aware точки | J11, J13 |
| `project-doc-indexing` (rule) | Цикл батчей 15/30 файлов, mark-noise, запись в arch doc, карта | Шаг 5 = `code-file add`, шаг 6 = `index refresh`; очереди file-registry сохраняются | J13 |
| `doc-verify` | 1 документ за шаг, F/L/T/O проверки, V6 score>=20, П-N при баге, mark-verify-done gates, Obsidian | Чтение sections из JSON; правки через arch writer; V6: `graph --doc X` / related legacy-v1; verify-registry 6 колонок не меняется | J11, J13 |
| `bitbucket-tasks` (rule) | Порядок чтения перед задачей, структура папки, MCP-маршрут, политика веток/ls-remote, send-to-git согласование | Порядок чтения: task.md -> `get --task N --keys` -> diff; структура папки в правиле дополняется task.json/_jsondoc | J13 |

**C. Мета-харнес**

| Компонент | Сохраняемый функционал | Взаимодействие | J |
|---|---|---|---|
| `harness-improvement` | Полная история компонента до правки, минимальная правка, parity | Перед правками jsondoc_scripts: компоненты в registry; сам workflow не меняется | J13 |
| `sync-agent-views.sh` + `generate-agent-configs.py` + `generate-mcp-config.py` | Генерация зеркал 3 сред, parity-report | Включить обновлённые правила/скилы в generated views; parity не равен runtime-регистрации (проверяется отдельно) | J13 |
| Rules `harness-improvement`, `text-style`, `yadisk-screenshot`, `test-task` | Триггеры и ограничения как есть | Только ссылки на новые пути инструментов, где упоминаются | J13 |

**D. Внешние скилы без взаимодействия (inventory no-impact)**

`yadisk-screenshot` - своя зона артефактов вне `.doc/tasks`/`architecture`;
MCP-серверы (serena, mysql,
context7, playwright, codebase-memory, sourcegraph) - JSONdoc не является MCP-клиентом.
Каждый фиксируется в compatibility inventory с обоснованием, smoke при наличии fixtures.

**E. Скрипты**

| Скрипт | Сохраняемое | Решение |
|---|---|---|
| `build-tasks-index`, `find-related-tasks`, `generate-doc-index`, `generate-file-registry`, `map-project`, `get-indexing-batch`, `mark-noise`, `get-verify-batch`, `mark-verify-done`, `audit-docs`, `validate-docs`, `sync-docs`, `_lib.ps1` | Контракты §9.2: golden TSV/веса/очереди/cwd | Обёртки/JSON-aware чтение после golden tests |
| `_batch-ai-links.py` | Массовая простановка AI-блоков при индексации | Переключить чтение arch docs на JSON sections (J11), запись через arch writer |
| `_fix_indexed_files_order.py`, `_restore_cicd_from_transcript.py` | Разовые recovery-утилиты | Inventory classified, не адаптируются; использование фиксирует owning workflow |
| `export-rebase-project.ps1` | Экспорт документации проекта | Проверить чтение через `_lib`; view/JSON дают то же содержимое (J11 golden) |
| `.doc/qa/scripts/*` (28) | verdict/gates/ac-results/history как evidence | J12: manifest/выбор прогона adapters; остальные (run-phpunit, static-on-diff, db-isolation, doctor...) - inventory no-impact: читают diff/tests, не doc-структуру |
| `.doc/skil_data/jira`: `server.php`, `src/`, `export_task.py` | PHP transport, Markdown builder, MCP export_task_md | J13 dual-output (task.md + snapshot из одного сбора); `export_task.py` - паритет или deprecation решение; `diag-auth.php`, `test-adf-converter.php`, `config.env` - без изменений |
| `.codex/go-task.ps1`, `.codex/task-diff.ps1` | Форвардинг параметров в canonical | Интерфейс сохранён; фактический forwarding фиксируется golden (IT01), расхождение adapter/canonical исправляется точечно |

**F. Порядок сквозного прохода задачи после полного перехода**

```text
gototask (export dual -> ingest-tracker)
-> task-doc A: batch погружение
-> prepare-plan: related/search + план (J17: apply)
-> реализация
-> task-diff: diff + ingest-artifact + git_events (+ diff build для stage)
-> test-task/browser-verify: прогоны -> batch apply checks/qa
-> task-change-report: doc_json роль
-> jira-report: apply jira_report.text
-> send-to-git: push -> ingest-git + apply
-> task-doc B: apply findings/decisions + render + index refresh
```

Каждый переход сохраняет существующие permissions/gates; JSONdoc добавляет только
хранение и выборки, не новые полномочия.

## 10. Порядок реализации

Diff разделён по независимым причинам R, а не по числу tools. Сейчас N относится
только к плану: один изменяемый файл `.doc/jsondoc.md`. Число будущих code patches
уточняется перед каждым R; произвольного общего N, выдаваемого за факт, нет.

### R1. Контракт и фундамент

Closes AC1,AC2,AC3,AC8,AC11(контракт). Sources T1-T4,T9,T10,T12,T13. Files: CLI, contract.py, четыре schema,
tests/test_contract.py и fixtures под `.doc/skil_data/task-doc/`.
Before: JSONdoc отсутствует; MD и existing JSON contracts действуют отдельно.
After: versioned строгие модели из раздела 4, tags/update/control schemas и read-only
template/validate/get на fixture. Не создавать JSON в живых task directories.

S1: `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p test_contract.py`.
Expected: valid task/arch/navigation/artifact accepted; unknown field, duplicate key,
invalid ref/type и escaping path rejected; fixture source bytes unchanged.

### R2. Теги

Closes AC4,AC8. Sources T1,T4. Files: search.py tag functions, test_search.py,
tags fixture; `.doc/skil_data/task-doc/state/tags.json` создаётся только на этапе настройки.
After: schema/alias resolver/assignment/candidates/deprecation/parents с правилами §5.
S2: `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p test_search.py`.
Expected: exact AND/OR membership, ambiguous alias error, cycle error, tag-only
result candidate, description lookup без чтения всех task JSON.

### R3. Query и index

Closes AC4,AC9. Sources T6,T7. Files: search.py, CLI query subcommands, control schema,
tests/test_search.py, compatibility fixtures.
After: §6 projection, bounded output, pure reads, catalog refresh/check, deterministic
rank with separate legacy-v1. Полный index build один раз, incremental по hashes.
S3: тот же test_search.py + `jsondoc.py ... benchmark --fixture`.
Expected: нет silent omission, stale cursor rejected, 0-hit success, compact JSON
валиден, incremental untouched model bodies не перечитывает без необходимости.

### R4. Writer и renderer

Closes AC3,AC5,AC11(ingest). Sources T2,T3,T12,T13. Files: store.py, render.py, tests/test_store.py,
test_render.py. After: §7 commit protocol, writer whitelist, anchors и conflict-safe
MD generation, ingest-tracker/ingest-git через общий apply-путь. Renderer не меняет knowledge revision.
S4: `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p 'test_store.py'`
и `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p 'test_render.py'`.
Expected: две записи одной revision дают одну success/одну conflict; failpoint между
JSON/MD даёт recovery_required; ручная правка view не стирается; повтор - no-op.

### R5. Lossless migration

Closes AC2,AC3,AC6. Sources T1,T2,T9,T10. Files: migrate.py, test_migrate.py и corpus.
After: §8 inventory/staging/reconstruct/check/apply/rollback. Пока только fixture.
S5: `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p test_migrate.py`.
Expected: source byte coverage 100%, opaque blocks preserved, stale live hash
блокирует apply, повтор resume не дублирует rows, rollback после новой записи refused.

### R6. Совместимый harness

Closes AC7,AC10,AC11(интеграция). Sources T2-T8,T12-T15. Files: перечисленные §9 canonical SKILL/rules,
doc_rules.md, PS1 adapters только нужных entrypoints; test_integration.py.
Before anchors: B4 "Запись в doc.md", B4.5 "Обновить индекс задач"; project-doc
S5/S6; doc-verify V6; prepare-plan P0.5a; существующий workflow-context post-step.
After: заменить правила MD-write для published JSON на `apply/render/index refresh`,
оставить legacy paths через resolver; источник brief и gates не менять; экспортёры
gototask/task-diff/send-to-git подключают ingest-tracker/ingest-git в свои финальные шаги.
QA freshness adapter (T14) и doc_json-роль renderer (T15) выполняются ДО переключения
test-task/task-doc writers, иначе авторендер doc.md после записи результата делает
прогон stale немедленно.
Полный нормативный After задают §6-9, кодовые patches исполнитель строит перед R6
по свежим полным файлам и проверяет P7; не объявлять старые line numbers вечными.
S6: `python3 -m unittest discover -s .doc/skil_data/task-doc/tests -p test_integration.py`.
Expected: task-doc → architecture backlinks → indexes → HTML handoff сохраняет
scope; read-only запрос не запускает writer; не создаётся doc.md из verify.

### R7. Пилот и массовый перенос

Closes AC6. Sources T1,T9. После R1-R6 настроить mixed mode и выполнить команды §8.3
сначала в clone fixture пилота, затем явно на 2612; архитектурный pilot orders в
отдельном проходе. Live migration требует отдельной команды выполнения, не этот план.
S7: каждый inventory item имеет coverage и status; graph показывает все исходные
ссылки без придуманных подтверждений. Затем --all batches, unresolved conflicts не
скрываются. Никакого замера "всё прошло" только на трёх случайных документах.

### R8. Приёмка, эффективность, включение

Closes AC8-AC10. Sources T1,T11. Full selftest, view link regression, compatibility
с PS1, parity инструкций, runtime discovery отдельно. Status ready новой системы
только по evidence тестов, docs switched и полного inventory, не по одной schema.
`verdict.green` не равен готовности задачи: готовность требует gates и закрытой
таблицы веток G13; существующие QA evidence-файлы не заменяются сводкой task.json.
S8: команды §11, summary zero failures, known coverage явно показано. Сохранить
замеры и решение о включении в `.doc/skil_data/task-doc/runs/{RUN}/acceptance.json`.

## 11. Внутренние тесты

### 11.1 Где и как

Tests и synthetic fixtures только `.doc/skil_data/task-doc/tests/`.
`selftest` создаёт `.doc/skil_data/task-doc/runs/{RUN}/sandbox`, задаёт TMPDIR/TEMP/TMP
туда для subprocess и запускает unittest. Очистка только своей sandbox после hash/
ownership проверки. Failures и логи сохраняются. Нет MySQL/browser/Git push/сети.

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . selftest --suite all
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . selftest --suite integration
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . benchmark --fixture
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . validate --all --links
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . index check
```

Suite contract/schema стандартной unittest discover командой также работает;
setUp создаёт sandbox под `.doc/skil_data/task-doc/state/test-runs`, а не default tempfile location.
PS1 integration отдельно на PowerShell 5.1 Windows и pwsh Linux. Недоступная среда
= not_run, не passed. Cross-OS результаты нужны до утверждения о полной portable
совместимости, не блокируют локальную разработку R1.

### 11.2 Test matrix

| ID | Предусловие/действие | Точный ожидаемый результат | Этап |
|---|---|---|---|
| UT01 | validate минимальных kind fixtures | Accepted, исходные bytes не меняются | R1 |
| UT02 | unknown field/version, bool вместо int, duplicate key, invalid UTF-8 | exit 2, код конкретной ошибки, 0 writes | R1 |
| UT03 | missing exported task/historical file | Relation retained, availability missing/not_exported, warning; нет fake data | R1 |
| UT04 | absolute/UNC/../symlink escape input и output | PATH_OUTSIDE_ROOT, 0 writes вне sandbox | R1,R4 |
| UT05 | два aliases одного kind, parent/replacement cycle | AMBIGUOUS_TAG или TAG_CYCLE | R2 |
| UT06 | поиск alias/description/NFC, deprecated ID | Canonical ID + resolved_from; описание не размножается в задачах | R2 |
| UT07 | candidate vs confirmed tags, all/any | Default excludes candidate; explicit include включает | R2 |
| UT08 | filter tags+file+text, pagination 23 совпадений по 10 | 10/10/3, total 23, без дублей и пропусков | R3 |
| UT09 | cursor после обновления snapshot | CURSOR_STALE, не смешанные страницы | R3 |
| UT10 | multibyte text >16 KiB output | Валидный JSON, content_truncated, полный путь извлечения | R3 |
| UT11 | пустой search; unknown pointer; null field | Соответственно exit 0 empty / exit 2 / valid null | R3 |
| UT12 | read/get/search на legacy/mixed без refresh | 0 filesystem writes, coverage не скрыт | R3 |
| UT13 | repeat operation ID same/different payload | duplicate/no-op либо conflict; history не удваивается | R4 |
| UT14 | два subprocess same revision | Ровно 1 commit и 1 conflict; файл валиден | R4 |
| UT15 | failpoints before JSON, after JSON, before receipt | Старый канон либо recovery_required; никогда ложный passed | R4 |
| UT16 | changed generated MD и render | VIEW_CONFLICT; ручные bytes неизменны | R4 |
| UT17 | render дважды | Байт-в-байт совпадение view; revision JSON неизменна | R4 |
| UT18 | Russian headings, repeated titles, custom anchors, П-N gaps | Все старые targets разрешаются, ID не перенумерованы | R4 |
| UT19 | fenced JSON/Mermaid/HTML/comment/table/CRLF/BOM/no final newline | reconstruct SHA256 == original SHA256 | R5 |
| UT20 | неизвестная секция, отсутствующий doc.md, corrupt source | Opaque preserved / source_only / blocked; ни одного dropped item | R5 |
| UT21 | live source changed после prepare | MIGRATION_SOURCE_CHANGED; apply 0 writes | R5 |
| UT22 | interrupt/resume batch | Опубликованное не дублируется, pending продолжены | R5 |
| UT23 | rollback unchanged/changed revision | Restore original либо ROLLBACK_CONFLICT; ничего чужого не удалено | R5 |
| UT24 | ingest-tracker с полным/частичным/повторным снимком и изменённым task.md | null_value отделён от not_returned/forbidden; равный content hash no-op; новый экспорт делает старый снимок историческим, без потери evidence | R4 |
| UT25 | ingest-git на sandbox git-fixture (init, commit, branch, remote-tracking ref) без сети | pushed_to/contained_in/release_branches соответствуют fixture; шаблон из config; отсутствие commit в git_events даёт unknown, не пустое множество | R4 |
| UT26 | stages на fixture: stage3 явно active, stage2 superseded, пустая stage4 | active=3 по evidence, placeholder4 не active; next_allocatable=5, resume4 отдельно; scopes diff разделены | R3 |
| IT01 | PS1 legacy fixtures и migrated views | Сохранены набор кандидатов, точные веса legacy (TSV 40/файл, arch link 50, mention 20, overlap min(30,6N), already-linked 10), сортировка score desc + id asc, default limit 8, reasons, alreadyInArch; мощности 0/1/many как отдельные fixtures | R6 |
| IT02 | queues noise/verified/indexed до/после refresh | Состояния и counters не сброшены | R6 |
| IT03 | task-doc B3: сбой второго документа | partial + resume, отсутствующая обратная ссылка видна | R6 |
| IT04 | workflow "только документацию" | Никаких HTML/Jira/push, permission context прежний | R6 |
| IT05 | QA passed на commit A, task теперь B | old result historical/stale, не current passed | R6 |
| IT06 | plan proposed + AC refs + stage2 + research ledger | План не promoted to implemented; exact original refs/hash | R6 |
| IT07 | file/tag overlap без прочитанного brief | Candidate only, не принятие требований чужой задачи | R6 |
| IT08 | gototask adapter на fixture-экспорте: task.md + tracker.json | task.md байт-в-байт как сейчас; ingest-tracker публикует снимок с exporter=gototask; повторный экспорт без изменений - no-op без нового history event | R6 |
| IT09 | повреждённый/неизвестной версии task.json рядом с doc.md | Ошибка восстановления канона; тихий MD fallback отсутствует | R6 |
| IT10 | test-run записан, затем авторендер doc.md | Входной hash содержательных требований QA-манифеста не меняется; прогон не становится stale | R6 |
| IT11 | изменено требование/test/matrix | Прогон stale, задача не ready; старый manifest не переписывается ради зелёного | R6 |
| IT12 | HTML существует, вход изменился | Без `--force` HTML нетронут; `--if-missing` не выдаёт `freshness_checked: true` | R6 |
| IT13 | renderer сгенерировал отчёт, writer записал его путь в task.json | Отчёт не помечен stale сам через себя: выход зарегистрирован до хеширования входов | R6 |
| IT14 | полный прогон из другого cwd (PS1 wrapper + python CLI) | Результаты идентичны запуску из project root | R6 |
| IT15 | stage R прогон passed при общей задаче failed | Общий task verdict не становится green; checks хранит run identity | R6 |
| IT16 | task-diff fixture: диф задачи + диф stage:2 | Оба артефакта зарегистрированы с корректным scope и hash; stage progress получил diff_artifact_ids; повторный ingest того же файла - no-op | R6 |
| AT01 | полный inventory архива | Каждый путь имеет роль, 0 lost spans/anchors, конфликты перечислены | R7 |
| AT02 | mirror sync + runtime config | File parity отдельно; отсутствие runtime probe = n/a | R8 |
| AT03 | cold/warm query и incremental refresh corpus | counts/bytes/files-read/duration, одинаковые результаты | R8 |

### 11.2a Дополнительные случаи по внешнему аудиту

| ID | Случай |
|---|---|
| UT15a | failpoint after view / before receipt: view опубликован, receipt нет -> recovery_required, повторный render добивает receipt, канон не теряется |
| UT29 | import jsondoc разрешается пакетом, не скриптом jsondoc.py (shadowing) |
| UT35 | dry-run не создаёт lock/journal/backup; результат помечен stale_if_revision_changed, не commit |
| UT37 | envelope errors[] содержит стабильный machine-код ошибки, не русский prose |
| UT38 | config branch template проверяется как fnmatch по уже полученным ref names, никогда не интерполируется в командную строку |
| UT40 | два параллельных index refresh сериализуются catalog-lock; задачные locks не пересекаются |
| UT41 | repeat tracker hash no-op; новый hash заменяет текущий объект, прежний остаётся историческим evidence |
| IT17 | resolver: JSON есть, receipt отсутствует -> error без тихого MD fallback |
| IT19 | cutover originals отсутствуют на хосте -> rollback/status объясняет ограничение, не падает молча |
| AT04 | стратифицированный пилот перед --all: архетипы (задача без doc.md; большой plan+stageN; только architecture; битые якоря/дубли ПК-N; CRLF+BOM/без финального newline; вложенные fence и HTML-in-list; binary attachments; mojibake; queue TSV рядом) |

Формула лимитов единая: cap задаётся в UTF-8 bytes на весь envelope; обрезка
скаляра - по code points, никогда по середине code unit; content_truncated
ставится и на envelope, и на поле. operation_id уникален в пределах target;
рекомендуемая схема `{actor}-{task}-{topic}-{sequence}`. Словарь next_action
закрыт: fix_inputs/refresh_index/resolve_conflict/recover/inspect_matched/
blocked; read-path никогда не refresh, refresh не чаще одного на workflow.
Поиск: русская морфология и ё/е-нормализация - явный OUT, компенсируется aliases
тегов. Модель доступа одним предложением: CLI работает с git working tree без
собственного ACL, разрешения живут в skills/workflow-context, actor в apply -
только provenance; CLI не внедряет фейковый RBAC. Index Gate и запрет
verify->создание task-doc остаются контрактами skills (не техническими CLI-gates);
CLI не исполняет инструкции из импортированных текстов. Инвентаризация кодировок:
utf8|utf8_bom|invalid|unknown_8bit без угадывания codepage; unknown_8bit -
review blocker; явный --encoding с provenance в coverage. Откат миграции на другом
хосте: originals обязаны быть в cutover-коммите по отдельному пути либо rollback
доступен только на хосте с manifest+bytes; статус run это показывает.

### 11.3 Эффективность без фиктивных обещаний

Corpus: 1000 synthetic задач, 50 architecture, длинные sections, multibyte tags.
Измерять cold index, warm search, get 3 findings, update одной задачи, full reindex.
Записывать docs_scanned, files_opened, bytes_read, output_bytes, duration_ms и
invalid/legacy counts. Gate: warm search не открывает все полные task bodies;
get не читает соседние tasks; update не rebuild всего архива; output bounded;
coverage не ухудшается. Порог секунд определить по baseline машины, не обещать <1с.

## 12. Приёмка и ограничения

Система допускается к live JSON-first только при выполнении AC1-AC14, успешных
S1-S8, сохранённом inventory и проверенном rollback. Full-text поиск не означает
полную semantic классификацию; schema validation не означает правдивость содержимого;
parity не означает регистрацию в IDE; metadata updated не доказывает свежесть кода.

Ни Jira, ни БД, ни git remote не вызываются автоматически query/migration. Jira-данные
попадают только через существующие PS1-экспортёры (T12): наш CLI принимает уже
собранный структурный снимок и не становится вторым Jira-клиентом. Git-проекция
вычисляется локальными read-only командами: statements о происхождении/релизе
ограничены свежестью последнего fetch и не являются live-запросом origin;
окончательная проверка веток на сервере остаётся за правилами bitbucket-tasks
(ls-remote). Теги
назначаются осознанно, candidate остаются видимыми. Необходимые approvals проекта
сохраняются. Код существующих product skills не переписывается ради демонстрации.

### Будущая индексация (вне текущего плана)

Файловые JSON-документы остаются каноном, generated `catalog.json` только индексом. Когда объём
задач сделает полных проход файлового каталога дорогим, карточки каталога
материализуются в Mongo или Postgres как индексная проекция той же схемы. Это
backend adapter инструмента: контракт JSON, команды и права не меняются, источник
правды не переезжает - переезжает только поисковый индекс. Выбор БД, схема
проекции и правила пересборки - отдельный план по `harness-improvement`, не часть
текущей миграции.

## Аудит плана

Это повторный проектный аудит, не повторная отметка старого checklist. Переработаны
ownership, canonical/views, межфайловые сбои, миграция, теги, search limits, очереди,
совместимость consumers и тесты. Новые факты в текущем workspace имеют приоритет
над прошлым чатом: audit archive сейчас сообщает 6 published pairs и 0 legacy,
а не прежние 13 MD-only. Это наблюдение текущей выборки, не миграция нами архива.

Tool ladder для текущей doc-only работы: graph/PHP call graph/MySQL/security/type/
browser - N/A, продуктовый код и schema не меняются; локальный Read/grep/PS1 source
inspection достаточен для документных контрактов. История `git log` для локальных
doc/harness путей не вернула commits; git-task-blame продуктовых диапазонов N/A.
Нельзя переносить этот N/A на будущие изменения runtime scripts без новой оценки.

Code-level P7 ready пока не заявлен: новые schemas/CLI ещё не существуют, точные
After-коды и per-step тестовые результаты должны быть проверены в R1-R8. План
устраняет решения "на усмотрение исполнителя" на уровне формата/процесса; ошибки
в реальном implementation выявляются тестами, не самодекларацией документа.

## Связи

- [doc_rules.md](doc_rules.md) - действующие права и процесс
- `.doc/architecture/index.md` в проекте Target - навигация, которую нужно сохранить
- Индекс задач в проекте Target - существующее представление индекса задач
- [task-doc](../../.agents/skills/documentation-router/children/task-doc/SKILL.md) - владелец knowledge задач
- [project-doc](../../.agents/skills/documentation-router/children/project-doc/SKILL.md) - владелец domain docs
- [doc-verify](../../.agents/skills/documentation-router/children/doc-verify/SKILL.md) - verification pipeline
- [prepare-plan](../../.agents/skills/prepare-plan/SKILL.md) - research/AC/R/S contract
- [task-change-report](../../.agents/skills/task-router/children/reporting-router/children/task-change-report/SKILL.md) - workflow-context и HTML
- [harness-improvement](../../.agents/skills/harness-router/children/improvement/SKILL.md) - изменения канона и parity

## История изменений

- 2026-09-25: исходный черновик форматов и пяти CLI.
- 2026-09-25: повторный аудит. Один CLI, все runtime assets под `.doc/`, task-local
  evidence, теги/aliases/описания, lossless staging, CAS/receipt/recovery, bounded
  reads, owners existing artifacts, внутренние tests и AC/R/S, mixed-mode cutover.
- 2026-09-25: добавлены AC11, T12/T13: tracker-снимок Jira (статус, релиз,
  автор, исполнитель, labels, sprint и прочее) через ingest-tracker от экспортёров
  gototask/task-diff; git_state (pushed_to, contained_in, release_branches,
  fetch_status) через локальный read-only ingest-git после push/merge; UT24/UT25,
  IT08 и золотые веса legacy related-tasks в IT01.
- 2026-09-25: по аудиту потребителей: T14/T15; QA freshness adapter и doc_json-роль
  renderer обязательны ДО переключения писателей (qa-manifest хеширует doc.md);
  регистрация выходов до хеширования входов (IT13); metadata.doc_type, run identity
  в checks, state-колонки file-registry, `_lib.ps1` как точка JSON-aware чтения,
  explicit-root adapter prepare-plan; IT09-IT15.
- 2026-09-25: стадии: artifacts scope `task|stage:N` (корневой plan = stage:1),
  progress kind=stage с stage_no/plan_artifact_id/diff_artifact_ids/superseded_by_stage,
  команды `stages` и `ingest-artifact`, инвентаризация stageN/plan.md и пустых
  placeholder-папок, дифы задачи и стадии раздельно (UT26, IT16); задел будущего
  индекса Mongo/Postgres как adapter поверх неизменного файлового канона.
- 2026-09-25: критерий размещения данных (§19.8): записи-знания в агрегате, сырьё
  рядом с refs, бинарники файлами; планы переносятся в JSON последним этапом J17
  (после стабилизации миграции doc.md); jira_report.text каноном в task.json,
  jira-report.md - generated view; batch-режим §6.5 с BT01-BT04; консольный доступ
  харнесов §9.4 с типовыми пачками и правилом 3+ операций = batch; MCP зафиксирован
  как поздняя обёртка, не экономящая токены сама по себе.
- 2026-09-25: полная карта харнеса §9.5: инвентарь 12 rules, 22 skills, 17 docscripts,
  28 qa/scripts, .jira и synh_harnes; для каждого - сохраняемый функционал, точка
  взаимодействия (batch/apply/ingest), этап J, сквозной порядок прохода задачи;
  ранее неучтённые `_batch-ai-links.py`, `_fix_indexed_files_order.py`,
  `_restore_cicd_from_transcript.py`, `export-rebase-project.ps1`,
  `generate-mcp-config.py` классифицированы.
- 2026-11-06: `validate --task|--arch|--all [--links]` реализован: схема документа
  и локальные ссылки опубликованного view, exit 1 при ошибке. Пример §6.3 приведён
  к текущему CLI, `--require-complete` и `--scope` убраны; `template`,
  `index refresh` и `index check` помечены как план J12-J13.
- 2026-11-10: раздел 21 с механическим валидатором плана удалён. План ведёт
  авторский `plan.md` через `prepare-plan`, проверку выполняет `audit-plan`.

## 13. Повторный аудит и обязательные уточнения

Это дополнение сохраняет предыдущие решения и исправляет конфликты, накопившиеся
при расширении плана. При реализации использовать таблицу ниже, а не одновременно
два варианта. До J01 пример envelope §4.2 дополняется `stages:[]`; progress больше
не используется как второй независимый реестр стадий.

| Ранее в документе | Окончательный контракт |
|---|---|
| Прежнее размещение JSONdoc внутри docscripts | Только `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py` и `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/`; никаких новых shim-файлов в docscripts не создавать |
| Прежний общий каталог `_jsondoc` под `.doc/` | `.doc/skil_data/task-doc/state/`, `runs/`, `work/` по §14; task-local `_jsondoc/` остаётся под задачей |
| R1-R8 как слишком крупные executable stages | R остаются причинами; выполнение J00-J16 с явными зависимостями и тестами |
| `state!=superseded`, хотя такого enum не было | Стадии имеют собственный status, superseded включён; progress содержит только items/R |
| Действующая = максимальный номер | Активная выбирается явным state + scope; несколько активных = ambiguity; done/placeholder не активные |
| Корневой план всегда stage:1 | При явном initial stage scope да; старый root task-plan не переклассифицируется автоматически, пока mapping не подтверждён |
| Следующий stage = max+1 без учёта пустых папок | Отдельно next_actionable, latest_documented, next_allocatable; occupied placeholders резервируют номера |
| В diff_artifact_ids стадии и task diff одновременно | Stage содержит только свой diff pair; task diff отдельный, без подмены scope |
| Существующий task-diff автоматически знает стадии | Наличие stage-папки этого не доказывает; реализация проверяется отдельно, отсутствие функции покрывает J07 |
| Последний коммит определяет попадание всей задачи в release | Проверяется полный подтверждённый набор task/stage commits и ref-tip; squash/cherry-pick не равны ancestry |
| `bugfixes/*_for*` считается релизной веткой | Это backport task branch, не release branch; классификации разделены |
| Jira status/author только строки, комментариев нет | Typed references с ID/label, полная доступная пагинация comments, typed custom fields и coverage; §19 |
| Указание одного source_id доказывает корректность | Provenance + freshness нужны, но truth и разрешение на действие проверяет агент/owner workflow |
| Рендер report path в task.json не меняет hash | Это верно только для явно определённой input projection, не полного JSON hash; §18.3 |
| `reference.md` doc-verify подразумевается существующим | На исследовании файл отсутствовал; применяются текущий SKILL/rule/doc_rules, missing reference в inventory, не источник evidence |
| Schema таблица допускает `source_ids` у artifacts, но поля нет | Добавить `source_ids:string[]` к artifacts; все tables/examples проходят schema tests в J01 |
| Проверка всех scripts означает запуск любых scripts | Inventory всех; запуск только безопасных тестовых adapters/fixture suites. Destructive/network scripts не запускать вслепую |

План имеет две оси готовности: `design` и `implementation`. Этот повторный аудит
улучшает design. `implementation=not_started`, тесты нового кода ещё не выполнены.
Не менять `audit_status` на passed только потому, что написан подробный документ.
Для ограниченного mixed-mode пилота нужны gates J00-J13 и fixture rehearsal.
Для окончательного JSON-first режима нужны gates J00-J16. Это не основание спрашивать
подтверждение на каждом безопасном внутреннем шаге после команды реализовать план.

## 14. Окончательная структура файлов

Все **новые** CLI, libraries, schemas, synthetic fixtures, helper tests, общие run logs,
candidate inputs и инструменты проверки JSONdoc собраны в `.doc/skil_data/task-doc/`.
Существующие `.doc/docscripts`, `.doc/qa`, `.doc/skil_data/jira` и `.agents/skills` не переносятся
и не копируются: там допустимы только необходимые изменения существующих adapters.
Документы и реальные task-specific evidence остаются рядом с задачами.

```text
.doc/
  jsondoc.md
  jsondoc_scripts/
    jsondoc.py                          одна публичная команда
    jsondoc/
      __init__.py
      contract.py                       модель, строгая валидация, sources
      store.py                          CAS, locks, receipts, recovery
      search.py                         pointers, tags, pagination, catalog
      render.py                         только представления
      stages.py                         scopes, progression, stage diff manifest
      ingest.py                         Jira/Git/artifact нормализация
      migrate.py                        inventory, spans, staging, rollback
      review.py                         lease-очередь агентского enrichment
      verify.py                         selftest, verify-stage, compatibility
    schemas/
      document.schema.json
      tags.schema.json
      update.schema.json
      control.schema.json               ref/receipt/index/migration discriminators
      tracker-export.schema.json
      stage-diff.schema.json
      review-item.schema.json
      test-result.schema.json
    tests/
      support.py                        sandbox root, fake Git/Jira transport
      suites.json                       test IDs -> modules -> implementation J
      test_contract.py
      test_store.py
      test_render.py
      test_search.py
      test_stages.py
      test_diff.py
      test_tracker.py
      test_git.py
      test_migrate.py
      test_review.py
      test_compatibility.py
      test_freshness.py
      test_security.py
      fixtures/                         обезличенные golden/synthetic
        documents/
        legacy-md/
        tracker/
        stage-diff/
        compatibility/
    state/
      config.json                       project adapter и mode flag
      tags.json                         словарь, не копии в каждой задаче
      catalog.json                      derived; rebuildable
      compatibility.json                inventory skills/scripts и test bindings
      execution.json                    состояния J00-J16, ссылки на receipts
      migration/{RUN}/manifest.json     глобальная карта без копий task evidence
      review-queue.json                 pointers, leases и состояния
    work/                               общие request JSON, без live-task данных
    runs/{RUN}/
      results.json                      machine outcomes и hashes
      report.md                         компактная сводка (generated)
      commands.json                     argv, cwd, timeout, exit; без секретов
      logs/                             bounded stdout/stderr
      sandbox/                          все временные repos/DB mocks/fixtures
    implementation/
      diff.md, diff.files.md             полный диф разработки JSONdoc (не product task)
      J00/ ... J16/
        stage.json                      scope, inputs, outcomes, evidence refs
        diff.md, diff.files.md           снимок изменений именно этого J
  tasks/{N}/
    task.json, task.md, doc.md
    diff.md, diff.files.md               task-wide canonical diff
    stages.json                         только если требует существующий adapter;
                                        новый дублирующий канон не создавать
    stage{K}/
      plan.md                           авторский план, пока MD
      diff.md, diff.files.md             stage-only pair
      diff.manifest.json                как выбраны commits и что сравнивалось
      test.md, ac-matrix.json            stage scope, если стадия тестируется
      tests/                            только специфичные stage tests при нужде
      test-runs/{RUN}/                   результаты stage, не task root
      audit.md                          если существует; не mandatory копия doc.md
      doc.md                            только уже существующий или явно нужный
    _jsondoc/
      receipt.json, work/, transactions/
      artifacts/{ID}.json
      tracker/{snapshot_id}/
        issue.json, manifest.json
        comments/page-{n}.json
        changelog/page-{n}.json
      migrations/{RUN}/
        original/                       task-local backups
        candidate.json, coverage.json
        spans/{id}.bin                  candidate payload для reconstruct
        reviews/{ID}.json
  architecture/
    {name}.json, {name}.md
    _jsondoc/{DOC_ID}/
      receipt.json, transactions/, migrations/{RUN}/
        original/, candidate.json, coverage.json
        spans/{id}.bin, reviews/{ID}.json
  .jira/                                существующий exporter, без новой auth системы
```

Tree показывает полный allowlist новых файлов, не требование создавать пустые
каталоги заранее. J создаёт только свои необходимые files. Никаких `test_tmp.py`,
`patch_once.py`, `_fix_jsondoc_2.py`, `test.json` в корне repo/task или вне этого tree.
Разовый диагностический код - stdin без сохранения либо файл в `work/` с owner ID.
Не включать `.pyc`, venv, sandbox, raw credentials и test run outputs в tool package.

Набор fixtures проекта и реальные миграционные originals различаются: обезличенные
fixtures в tests, реальные сведения конкретной задачи только в tasks/N.
`cleanup --run RUN --dry-run` перечисляет только sandbox/work своего run.
`cleanup --run RUN --apply` не удаляет results, originals, review evidence, активные
locks или чужие файлы. Отсутствие отдельного запроса cleanup не блокирует следующий J;
runner удаляет собственную успешную временную sandbox, при failure сохраняет её.

## 15. Стадии задачи, дифы и документация

### 15.1 Три уровня, которые нельзя смешивать

- Task - общая Jira-задача, общий task diff и общий doc.md/task.json.
- Stage - initial работа, новая итерация/инцидент или согласованная стадия, со своим
  планом, scope diff и QA. Имя каталога не задаёт её готовность.
- R/S или J - независимый шаг реализации и его проверка внутри конкретного плана.
  Прохождение J не создаёт stage2 Jira-задачи. У JSONdoc нет Jira ID, его J evidence
  хранится в `jsondoc_scripts/implementation`, не в выдуманной tasks/2612.

### 15.2 Stage contract

В aggregate добавить `stages:Stage[]`; `progress.kind` ограничить `item` (R/items).
Если старый draft уже имел progress stage entries, migrator переносит их по явному
mapping без двух канонов. Stage required fields:

```text
id: string                      stage:2
number: int >= 1
title: string
status: unknown|planned|active|blocked|implemented|verified|closed|superseded
placeholder: boolean
trigger: string|null
depends_on: stage ID[]
superseded_by: stage ID|null
plan_artifact_id: string|null
diff_artifact_ids: string[]      только stage diff и stage diff_files
diff_manifest_id: string|null
test_artifact_ids: string[]
test_run_ids: string[]
documentation_refs: RecordRef[]
requirement_ids: string[]
source_ids: string[]
```

Последовательность status не выводится из наличия файлов. `implemented` - есть
evidence изменения, `verified` - целевые проверки прошли для текущего scope,
`closed` - нет незакрытых требований этого stage. QA failed не стирает implemented.
Зависимости ацикличны, superseded имеет существующий target, self-link запрещён.

`stages --task N` возвращает:
`active_stage_id`, `active_candidates`, `latest_documented_stage_id`,
`next_actionable_stage_ids`, `next_allocatable_number`, `stages[]`, `coverage`.
Правила точные:
1. active_stage_id только если одна explicit active стадия; несколько -
   `STAGE_AMBIGUOUS` и required `--stage`, не выбор max.
2. next_actionable = planned с закрытыми depends_on; если несколько, не начинать
   автоматически одну по номеру; возвращаются candidates.
3. latest_documented - максимальный номер с валидным планом, чисто навигация.
4. next_allocatable = max всех зарегистрированных/занятых номеров + 1; пустая
   stage6 резервирует 6. Возобновление stage6 - отдельная операция, не новая stage7.
5. Отсутствие root plan не мешает stage2; initial stage1 не выдумывается как verified.
6. Новый stage не создаётся `get`, `search` или `stages`; это явный `apply`.

### 15.3 Документация и тесты стадий

Общего task `doc.md` достаточно как основного знания. Он содержит таблицу stages
со ссылками на планы, stage diffs, QA verdicts и stage-specific findings. Каждое
решение/находка может иметь `scope={kind:task|stage,id}`; агрегирование не стирает
историческую стадию. Не требовать одинаковый полный doc.md в каждой stage папке.
Существующий stage/doc.md сохранить и зарегистрировать, не удалить при миграции.

У каждой реализуемой стадии свой QA scope и свой результат. Отдельные исходные
tests необязательны: можно запускать общий reusable test по точному stage фильтру.
Но stage/test.md (или manifest тестового сценария) и stage/test-runs должны явно
показывать что проверялось. Повтор целой task suite допустим как integration check,
не подмена результата конкретной стадии. Отсутствующий stage Cest не означает
отсутствие теста, если есть корректная ссылка на общий метод и доказанный selector.

### 15.4 Stage diff как проверяемый scope

Task diff остаётся output существующего task-diff по правилам task ownership.
Stage diff не копия task diff и не `git diff HEAD~1` по догадке. Для stage нужны:
точный список commit OIDs либо явные base/head refs + resolved OIDs, task ownership,
worktree snapshot (если разрешены uncommitted changes), excluded commits/paths и
source plan hash. Все refs фиксируются в `diff.manifest.json`.

Минимальный manifest: `schema_version,task_id,stage_id,selection_mode,base_oid,
head_oid,commit_oids,path_scope,uncommitted,source_plan_sha256,generated_at,
diff_sha256,files_sha256,ownership_evidence,coverage`.
`selection_mode=commits|range|workspace_delta`; `uncommitted` содержит path + old/new
hash для каждого path. Range не включает чужие коммиты без явного exclusion отчёта.

Для committed stage output содержит per-commit patches в заданном порядке и
отдельную сводку путей, не ложно утверждает net diff при cherry-picks/merge.
Для range net diff разрешён только когда весь диапазон соответствует stage scope.
Empty diff допускается для planning-only stage, помечается `empty_reason`, а не
выдаётся за выполненную реализацию. Итоговое поведение функции определяется
fresh Read текущего кода; diff ownership не заменяет его.

Рабочее дополнение CLI (реализуется J07, не подразумевается доступным сейчас):

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . diff build --task 2612 --stage 2 --input .doc/tasks/2612/_jsondoc/work/stage2-diff.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . diff check --task 2612 --stage 2
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --stage 2 --select /artifacts
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . stages --task 2612
```

`diff build` вызывает существующий generator если он действительно поддерживает
точный scope. Иначе новый adapter в `jsondoc_scripts/jsondoc/stages.py` выполняет
фиксированные read-only Git argv, не shell-строки из JSON. Root task diff никогда
не перезаписывается stage вызовом. Смена selection/plan/commits делает diff stale.
Stage plan, stage QA и stage HTML не могут принимать task-wide diff вместо stage diff.

## 16. Атомарные этапы реализации

### 16.1 Единый цикл без лишних подтверждений

После команды пользователя реализовать план агент выполняет J00-J16 по порядку,
без вопроса "продолжать?" после каждого зелёного шага. Сейчас разрешено только
редактирование плана. При будущей реализации каждый J:

1. Читает входы stage и текущие target files, снимает hashes и baseline изменяемых
   ignored/untracked файлов. Чужие изменения не включает в diff и не откатывает.
2. Реализует только результат J и его tests. До test-run не меняет stage на passed.
3. Запускает целевой suite J; затем все уже готовые suites `through J`.
4. Выполняет совместимость потребителей, затронутых этим J, из registry §18.
5. Пишет `results.json`, scoped diff pair и stage.json; gate связывает их hashes.
6. Gate passed - автоматически следующий J. Failure - исправление текущего J,
   новый run; прежний failed evidence остаётся. После 3 одинаковых неустранённых
   ошибок фиксирует blocked с причиной, не крутит бесконечный цикл.

Команды после bootstrap J00 (все cwd/root явные):

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . selftest --stage J04 --run J04-001
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . selftest --through J04 --run J04-regression-001
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . compatibility check --stage J04 --run J04-compat-001
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . execution verify-stage --stage J04
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . execution next
```

`execution next` только сообщает следующий шаг, не исполняет код или prompt из
файла. `execution verify-stage` проверяет stage scope, непустой набор нужных tests,
результаты без пропусков обязательных checks, baseline/output hashes и dependency
gates. Нет режима "все тесты ещё не написаны, поэтому passed".

Запреты/permissions не снимаются автоматизмом: push, destructive операции,
настоящая БД, доступ к Jira/remote и новые секреты только по существующим правилам.
Внутренние fixture tests их не требуют. Live migration запускается после отдельной
команды на выполнение миграции либо явно включённого пользователем scope всей
реализации; промежуточные внутренние approvals для безопасных J не нужны.

### 16.2 Карта J -> результат -> проверка

Каждый J завершает одну наблюдаемую возможность. Если реализация большого J
требует технических commits, это не создаёт новые stages задачи.

| J | Зависит | Files внутри jsondoc_scripts, если не указан внешний adapter | Конкретный финал | Целевой suite и literal outcome | R/AC |
|---|---|---|---|---|---|
| J00 | нет | jsondoc.py, jsondoc/__init__.py, verify.py, tests/support.py, suites.json | Рабочий CLI --help, sandbox runner, environment/inventory baseline; бизнес-функций ещё нет | bootstrap: 0 exit, JSON result, запись только в runs/RUN, ненулевой test count | R1/AC1,8,13 |
| J01 | J00 | contract.py, все schemas, test_contract.py, fixtures/documents | Строгий документ/Stage/Source/Tracker contract, examples синхронны | contract: invalid keys/types/refs/version rejected; примеры из плана parse+validate | R1/AC2,3,11,12 |
| J02 | J01 | store.py, test_store.py | Create/update/no-op/CAS/receipt/recover одного JSON без renderer | store: UT13-UT15, conflict без потери обеих версий | R4/AC5 |
| J03 | J02 | render.py, test_render.py | Idempotent MD view и VIEW_CONFLICT; JSON hash не циклический | render: UT16-UT18, JSON revision unchanged, no overwrite ручных правок | R4/AC3,5 |
| J04 | J03 | search.py базовая часть, test_search.py | Read-only get/select/limit/cursor с coverage, без full archive scan для get | query: UT08-UT12, 10/10/3 results и no writes | R3/AC4,9 |
| J05 | J04 | search.py taxonomy/catalog, fixtures tags/ranking | Alias/description/AND/OR/candidate и file/tag related search, index refresh | tags-index: UT05-UT07 + golden legacy-v1 отдельно от discovery-v1 | R2,R3/AC4,7 |
| J06 | J05 | stages.py, test_stages.py | Stage selection, scope refs, next_actionable/allocatable, общий doc index stages | stages: ST01-ST04, multiple active blocked, placeholder не active | R1,R3/AC12 |
| J07 | J06 | stages.py diff adapter, test_diff.py | Stage diff/files/manifest и общий task diff разделены | diff: ST05-ST08, два scope без overwrite; dirty unrelated file не включён | R6/AC7,12 |
| J08 | J07 | ingest.py, test_tracker.py, test_git.py | Jira snapshot/comments fixture и Git containment полного набора commits | sources: JR01-JR03,JR05 на входных fixtures, GT01-GT05; exporter implementation ещё не заявляется | R4/AC11 |
| J09 | J08 | migrate.py, test_migrate.py | Inventory/prepare/reconstruct/check без live cutover | migrate: UT19-UT23, byte coverage 100%, opaque сохранены | R5/AC2,3,6 |
| J10 | J09 | review.py, review-item.schema, test_review.py | Возобновляемая leased agent queue, review acceptance/source hash | review: MG01-MG08; stale review не принимается | R5/AC14 |
| J11 | J10 | test_compatibility.py, существующие .agents/skills/documentation-router/children/project-doc/scripts/_lib.ps1 и нужные wrappers | Legacy+JSON docs consumers совместимы, queue states прежние | doc-compat: IT01,IT02,IT14 и весь classified inventory | R6/AC7 |
| J12 | J11 | test_freshness.py + существующие QA/report/plan adapters §18.3 | Версионированные input projections, no self-invalidation, scoped QA/report | freshness: IT05,IT06,IT09-IT15, stage diff mismatch rejected | R6/AC7,9 |
| J13 | J12 | existing Jira exporter/bridge + canonical SKILL/rules + tests | Dual-output Jira/JSON, mixed-aware writers и читатели во всех IDE | workflow: JR01-JR05 с реальным PHP exporter на mock transport (включая JR04), IT03,IT04,IT08,IT16, permissions + parity/config | R6/AC7,10,11 |
| J14 | J13 | только run/evidence; runtime code только bugfix с повтором affected gates | Clone-пилоты task и architecture, затем разрешённый live пилот с rollback rehearsal | pilot: AT01 на пилотах; 0 lost spans/links, revisions coherent | R7/AC6 |
| J15 | J14 | migration manifest/queue/task-local artifacts | Все документы staged, все mandatory reviews обработаны, controlled batches publish | archive: every inventory path classified; unresolved blockers=0 для опубликованного scope | R7/AC6,14 |
| J16 | J15 | acceptance manifest, benchmark outputs, config mode | Все нужные suites прошли вместе, clean footprint, portable exceptions честно названы | full: selftest --suite all + compatibility --all + index check + migration status | R8/AC8-AC14 |
| J17 | J16 | prepare-plan SKILL/scripts adapter, plan view renderer, test_plan_json.py | Планы как JSON: prepare-plan пишет через apply (sections + T/AC/R/S + plan_hash), plan.md/stageN/plan.md - generated views; validate_plan работает от JSON-модели, MD-валидация остаётся для legacy | plans: UT30-UT32, план rebuild round-trip, P7 аудит читает view идентично MD | R6/AC2,12 |

Новые command names bootstrap/through/compatibility фиксируются в suites.json на J00.
Tests будущего J не запускаются как случайно пустой suite в текущем. Full acceptance
проверяет покрытие всех заявленных IDs. Нельзя реализовать J13 раньше J12 ради
быстрого включения JSON writes.

### 16.3 Stage receipt и диф разработки JSONdoc

`implementation/Jxx/stage.json`:
`{stage_id,dependencies,status,plan_sha256,input_hashes,output_hashes,
test_run_refs,compatibility_run_ref,diff_refs,blockers,completed_at}`.
Status `pending|running|failed|blocked|passed`; only gate пишет passed. План изменился
- stale затронутые стадии по requirement mapping, не всё подтверждать задним числом.

Git может игнорировать `.doc/` и `.cursor/`. Поэтому диф J строится по captured
before/after bytes и path hashes, а не по пустому `git diff`. Формат unified diff,
плюс files list с operation add/update/delete; binary refs hash-only. Общий диф
JSONdoc = baseline до J00 против финального состояния, не механическая конкатенация
частичных patches. Параллельные чужие правки = `BASELINE_CONFLICT`, изолированная
фиксация вручную агентом, без revert чужого. История тестов и outputs не включается
в implementation diff как исходный код; артефакты ссылаются отдельно.

## 17. Скриптовая миграция и агентская очередь

### 17.1 Почему два прохода

Только агент может неверно пересказать незнакомый legacy-документ. Только regex
теряет семантику нестандартных секций. Поэтому механизм разделён:
скрипт гарантирует сохранение bytes, ссылок и boundaries; агент уточняет домены,
бизнес-связи, типизированные findings и неочевидные теги. Ни один этап не заменяет
другой и не пересоздаёт архитектуру с нуля.

Существующие `get-indexing-batch` и `get-verify-batch` остаются очередями исследования
кода/проверки документации. Новая review очередь только для JSON-конвертации,
использует тот же компактный batch-паттерн, но не смешивает состояния verified/noise
и не заново индексирует весь продукт. У каждого review item ссылка на уже имеющийся
doc/verify record, если он есть.

### 17.2 Состояния и вход review

`pending -> leased -> submitted -> accepted`, отдельно `blocked|stale|deferred`.
Причины очереди: ambiguous section, opaque critical flow, conflicting IDs/anchors,
missing reverse link, tag mapping ambiguous, metadata conflict, encoding warning.
Каждый architecture doc получает один обязательный review; простой task doc с
полностью детерминированной конвертацией может пройти автоматический mapping check.
Все critical invariants/permissions/money/auth sections требуют read-only review
независимым от автора enrichment агентом. Никакой массовой LLM-генерации raw JSON.

Item schema:
`{id,document_id,source_path,source_sha256,candidate_sha256,reason_codes,
required_sections,evidence_paths,status,lease:{owner,token,expires_at},
attempts,result_path,coverage,blockers}`. Task review result хранится у задачи,
arch review result у architecture/_jsondoc/DOC, в общей очереди только pointer.

Команды:

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . review status --run jsondoc-all-01
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . review next --run jsondoc-all-01 --kind architecture --limit 1 --claim --owner agent-session
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . review submit --input .doc/architecture/_jsondoc/orders/migrations/jsondoc-all-01/reviews/review-01.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . review validate --item arch-orders-01
```

`next` без --claim read-only, с --claim - CAS lease, timeout lease не означает
удаление чужой работы. Reclaim только отдельной командой с token/status проверкой.
После изменения source_hash submitted результат stale и применяется к новому source
только после повторного рассмотрения. Submit не публикация, validate не разрешение
выйти за документный scope.

### 17.3 Чеклист агента одного документа

1. Прочитать source документ целиком или все ordered sections без пробелов.
   Выдача списка keys не считается чтением архитектуры.
2. Сверить original spans и candidate, особенно code fences, таблицы, якоря,
   ограничения, негативные сценарии, внешние ссылки и историю задач.
3. Назначить существующие tags; новые - proposal с описанием, не массовое добавление.
4. Связать задачи и arch docs с exact anchors/source spans. Не угадывать task ID из
   числа в примере кода. `not_exported` сохранять без автоматического Jira fetch.
5. Найденное расхождение docs/code оформить finding отдельно. Перенос знаний сам
   по себе не разрешает исправлять продукт или пересказывать историю как актуальную.
6. Подготовить typed enrichment patch + sources, не замещающий original sections.
7. Запустить review validator: 100% byte coverage, link/anchor parity, no dangling
   typed refs, source freshness, validated taxonomy, сохранённый text preview.
8. Accepted - следующий item без вопроса пользователю. Blocker - подробный reason,
   продолжить независимые items; не пометить всю миграцию завершённой.

### 17.4 Не терять значение при enrichment

Original body остаётся доступным и после semantic enrichment. Структурная запись
отсылает к source span; утверждение без source не accepted. Если новый typed текст
кратче исходного, это summary, а не замена. Сопоставление неоднозначных заголовков
хранит aliases, новые anchors не ломают старые inbound links.

Coverage выдаёт отдельно `text_preserved`, `structure_extracted`,
`semantic_reviewed`, `code_verified`. Первые три не означают code_verified.
Каждый показатель имеет denominator, count и missing IDs. Публикация opaque-safe
JSON возможна по политике mixed mode, но mandatory semantic review для architecture
должен завершиться перед заявлением о полном переходе архитектуры.

## 18. Проверка совместимости всего harness

### 18.1 Динамический полный реестр

J00 автоматически инвентаризирует все доступные canonical skills, rules и scripts
из `.agents/skills`, `.cursor/rules`, `.doc/docscripts`, `.doc/qa/scripts`, `.doc/skil_data/jira`,
`.doc/skil_data/harness-core` и реально обнаруженных adapters, а не фиксирует вечное число 22.
Для каждого entry: path/hash, kind, entrypoints, reads/writes, runner, impact class,
safe_test_command_argv, fixture, expected artifacts, result, not_run_reason.

Impact class `producer|consumer|stateful_index|orchestrator|isolated|unsafe_external`.
Нет незарегистрированных relevant entries. Изменился source hash - нужна новая
совместимость этого entry. Registry generated; списки argv валидируются по allowlist
runner, команды из текстов документов никогда не исполняются.

Внешние tests запускаются в sandbox-копии необходимого harness и fixture repo,
чтобы existing hardcoded paths не изменяли live `.doc/`. Не импортировать модуль с
опасными top-level side effects ради "проверки". --help тоже не гарантирует
безопасность script: сначала Read entrypoint, затем разрешённый runner.

### 18.2 Матрица покрытия

| Группа | Обязательная проверка | Что не делать |
|---|---|---|
| task-doc/project-doc/doc-verify | Чтение/write routing legacy/mixed/JSON, refs/Index Gate, stage navigation, trigger fixtures | Не считать grep пути доказательством всего поведения агента |
| prepare-plan/git-task-blame/task-code-review | scope ownership, T/AC/R/S, refs, missing evidence, stage2 и root path | Не ослаблять P7, не делать JSON search заменой code/history Read |
| gototask/task-diff/Jira exporter | Fixture Jira pages + legacy task.md golden; task/stage diff fixture Git repos | Не переключать живую ветку, не обращаться в настоящую Jira для unit tests |
| test-task/prepare-task-test/browser-verify | AC matrix/gates/input projections/group-stage identity на fixtures | Не поднимать браузер, Selenium, DB и стенд ради документационного теста |
| task-change-report/jira-report/send-to-git | Existing regression suites в sandbox + doc_json role + restrictions chain | Никакого push/PR/публикации Jira, не затереть старый HTML |
| harness-improvement | Existing schema/writer/query/lifecycle/preflight/parity tests в sandbox | Не менять historical audit evidence ради compatibility |
| docscripts индексации/сверки | Golden TSV, candidates/ranking/cwd, queue state preservation | Не сбрасывать реальные очереди |
| sync-agent-views/generate-agent-configs | Dry-run/staged fixture output + native rule form + file parity | Не `rm -rf` живые зеркала и не считать byte parity runtime регистрацией |
| login-as-user/yadisk | Inventory всех, syntax/config/path smoke, isolated fixtures если существуют | Не вызывать внешние сервисы, не скачивать чужие данные; no-impact с evidence |

Для каждого skill нужны минимум trigger-positive и trigger-negative примеры,
источник разрешений, читаемые/пишущие artifacts, resolver path и fallback. Статический
checker ловит старый jsondoc path, несуществующие команды, конфликт инструкции
"пиши doc.md" с JSON mode и дублирующие ownership. Семантический smoke выполняет
агент на synthetic workflow без продуктового кода; результат хранится отдельно
от static passed. Недоступный runtime IDE = not_run, не n/a без причины и не passed.

Полная совместимость означает: каждый relevant producer/consumer имеет проверенный
fixture-run; isolated/no-impact имеет объяснение и safe smoke; unsafe_external
имеет mock coverage и явный запрет live execution. All tests passed не равно
"все внешние сервисы проверены в production".

### 18.3 Нормативные hash projections

В существующем `workflow_contract.py` input hash исключает steps/jira, но source
task.json hash всё ещё меняется при любом output update. Одной предварительной
регистрации report path недостаточно. В J12 добавить версию input projection и
exact typed source descriptor; старые context schemas продолжают читать legacy.

`jsondoc-input-v1` - все knowledge fields, кроме revision, metadata.updated_at,
history, checks, git_state и output-only artifacts roles test_run/change_report/
jira_report/audit. Исключаются также stages.test_run_ids, stage test output refs,
выходные documentation_refs и sources, достижимые только из исключённых outputs.
Sources, достижимые из оставшихся knowledge fields, сохраняются вместе с hashes.
Не удалять общий source, если на него ссылается требование или решение. Проекция
обходит RecordRef и source_ids детерминированно, dedupe по ID; dangling refs = error.
Metadata status/progress оставлять входом отчёта, если они
меняют его содержание. Если изменение verdict должно попасть в HTML, HTML обязан
стать stale: это не self-invalidation bug. Output-only запись path не меняет input.

`jsondoc-qa-input-v1` - requirements, accepted decisions, applicable invariants,
confirmed relation scopes, test specification/plan/matrix source hashes, selected
stage identity/diff manifest и code revision. Не брать free-form summary из QA
output как requirement. Публикация результата не изменяет input; изменение смысла
требования/плана/test selection изменяет hash обязательно.

Descriptors фиксируют projection_version, scope, source path и semantic_sha256;
file_sha256 отдельно для целостности. В J12 добавить в actual schema/validator
workflow-context новый descriptor, а не подставлять semantic hash в старое поле
file hash. Old manifests не переписывать; они остаются evidence старой схемы.

### 18.4 Новые тестовые IDs

| IDs | Обязательные случаи |
|---|---|
| ST01-ST04 | multiple active; stage placeholder occupied; missing root plan; dependencies/supersedes cycle |
| ST05-ST08 | own stage diff; root diff unchanged; foreign commit rejected; stage tests don't promote task QA |
| EX01-EX05 | zero tests cannot pass; source edit invalidates gate; cumulative suite stops next; clean footprint; resume failed J without repeating successful effects |
| MG01-MG04 | source spans lossless; opaque critical gets queue; two claims one winner; stale review rejected |
| MG05-MG08 | task-local evidence paths; independent critical review; unknown tags candidates; full archive completion requires mandatory reviews |
| JR01-JR05 | all comment pages; permission-truncated comments; edited/deleted distinction; exporter half-publication recover; existing Markdown golden |
| GT01-GT05 | multi-commit partial containment; shallow unknown; squash not ancestor; local cached ref not live; backport task branch not release |
| UT30-UT32 | план: apply пишет секции плана, view рендерится байт-стабильно; plan_hash инвалидируется любой правкой секции; legacy MD-план валидируется старым валидатором без изменений |
| UT33-UT34 | release: metadata.release выводится из tracker fixVersion (первый + config fallback как Get-DefaultReleaseBranch), branch - из task_type; новый ingest-tracker обновляет оба и делает старые значения историческими; search --release/--branch/--not-in origin различает unknown и подтверждённый not_pushed |
| BT01-BT04 | batch: 4 разных command в одном конверте на одном snapshot; batch+apply одной ревизией; per-item NOT_FOUND не валит остальные; 21-й call отклоняется |

Все эти IDs привязать к test methods в suites.json; claims без метода помечаются
missing, не manual pass. Agent semantic reviews имеют method=agent-review,
измеримый checklist и evidence, но не маскируются под Python unit tests.

## 19. Проверенные уточнения Jira, Git, стадий и контракта

### 19.1 Что установлено по существующему коду

| Источник | Установленный факт | Следствие для реализации |
|---|---|---|
| `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1`, параметры и output :697-709 | Нет Stage/Scope/OutputDir/EndCommit или commit-list. Есть только root diff.md/diff.files.md | J07 реализует точный stage adapter, не вызывает выдуманный флаг |
| `.codex/task-diff.ps1`:11-42 | Часть объявленных flags не передаётся canonical script | Сначала golden tests фактического forwarding, затем точечная правка existing wrapper; новый код stage engine в jsondoc_scripts |
| task-diff `-ForkCommit` | Только нижняя граница task-number-filtered log base..taskRef | Не использовать как изолированный diff старой стадии без верхней границы |
| `.agents/skills/task-router/children/gototask/scripts/gototask.ps1` | Нет registry стадий или active/next resolver | J06 новая функция, существующие пустые папки не источник статуса |
| `.doc/tasks/2467/doc.md`, stage3/plan.md, root diff.md | Root diff включает несколько стадий; stage3 ready/passed - статус плана, не реализации | Перед stage diff нужна явная commit ownership map |
| `.doc/tasks/2548/stage1v2/plan.md`, stage1v3/plan.md | Несколько вариантов stage1, stage3 QA-only может быть done раньше stage2 | Номер папки не chronology реализации; version-aware mapping обязательный |
| `.agents/skills/task-router/children/jira/scripts/server.php`, `src/TaskExporter.php::export` | Экспорт идёт через PHP TaskExporter; отдельный export_task.py не этот маршрут | Не добавлять второй Python Jira client |
| `.doc/skil_data/jira/src/JiraClient.php` | Comments постраничные, но missing total/empty page могут завершить без completeness; changelog embedded expand без полной пагинации | Доработать coverage/export существующего транспорта |
| `gototask.ps1::Export-TaskMd` и dispatch export-task | До dispatch возможны fetch/ls-remote; ошибка taskExport.ok не всегда приводит к nonzero | Offline fixtures не запускают полный live gototask; исправить error propagation без смены branch policy |
| task-diff script | Читает task.md, не экспортирует Jira | В таблицах §9 не трактовать task-diff как самостоятельный Jira exporter |
| doc-verify canonical/mirror | Указанный reference.md отсутствует | Missing source отмечается в compatibility inventory; не придумывать содержимое |

Эти факты корректируют предыдущие утверждения чата о шести реализованных стадиях
1612 и уже существующих stage diffs. Папка может быть пустой, план может быть draft.
Проверка не переключала ветки и не запрашивала live Jira.

### 19.2 Jira: полный доступный снимок, а не несколько строк

Tracker object §4.3 расширяется без потери перечисленных полей. Версия 1.0 ещё не
выпущена, поэтому final schema сразу содержит:

```text
issue: {id,key,self,summary,description,issue_type,project}
status: {id,name,category:{id,key,name}|null}
resolution,priority: {id,name}|null
creator,reporter,assignee: {id,name,display_name,active}|null
created_at,updated_at,resolved_at: timestamp|null
fix_versions,affects_versions: [{id,name,released,archived,release_date}]
components: [{id,name,description}]
labels: string[]
parent,subtasks,issue_links: typed refs с link type/direction
custom_fields: [{field_id,label,value_type,value,availability}]
comments: snapshot reference + total/retrieved/coverage
changelog: snapshot reference + total/retrieved/coverage
attachments: [{id,filename,mime,size,download_ref,availability}]
field_availability: [{field_id,state,reason}]
snapshot: {id,observed_at,tracker_updated_at,source_hash,exporter_version,
           coverage,source_ids,task_md_sha256}
```

`availability=present|null_value|not_returned|forbidden|unsupported|error`.
Null assignee означает unassigned только при null_value, а не при отсутствии права
читать поле. Sprint/story points/custom release fields описываются через field IDs
из проекта; ничего не угадывать по имени или customfield_100xx из другого проекта.
Jira fixVersion - заявленный релиз, Git containment - отдельный наблюдаемый факт.

Полные доступные comments/changelog сохраняются постранично у задачи:
`.doc/tasks/{N}/_jsondoc/tracker/{snapshot_id}/comments/page-{n}.json`,
`changelog/page-{n}.json`, `manifest.json` и typed issue snapshot. Task aggregate
хранит refs/coverage и компактные searchable сведения, не копию всей переписки.
Страницы schema-valid, content hashes и IDs нужны для updated/dedup/resume.

Comment: `id,author,created_at,updated_at,body,body_format,visibility,source_ids`.
Body сохраняется как полученный text/ADF, Markdown-представление отдельно generated.
Не терять code/attachments/links и edited timestamp. Отсутствие комментария в
partial response не равно удалению; deletion только explicit evidence/complete
authoritative collection. Restricted комментарии недоступны, не обходить permissions.
Emails/avatar payload/credentials не нужны для business search и не копируются;
ID/display_name автора и исполнителя сохраняются по запросу пользователя.

Pagination: явные startAt/maxResults/total/isLast где API их даёт; reconcile IDs,
ожидаемые offsets и terminal condition. Ранняя пустая страница или ошибка -> partial
с missing диапазонами; retry bounded и resumable, не объявлять all comments fetched.
Предыдущее полное состояние при partial refresh сохраняется, partial candidate не
заменяет complete snapshot молча. Freshness = наблюдение на дату, не обещание live.

Existing PHP exporter остаётся transport owner. После сбора ответа он строит
нормализованный export JSON по tracker-export.schema и прежний task.md. Публикация
парой через manifest-last с двумя hashes; сбой JSONdoc ingest не отменяет успешное
получение Jira, но весь dual-export status partial/nonzero, явный retry local ingest.
Нельзя вернуть ok:true только из-за наличия старого task.md. При JSONdoc disabled
старый export работает без обязательной новой зависимости.

J13 targets: `.doc/skil_data/jira/src/JiraClient.php` getIssue/listIssueComments/listIssueChanges/
paginate/request, `TaskExporter::export`, `.agents/skills/task-router/children/jira/scripts/server.php` CLI/MCP summary,
`gototask.ps1::Export-TaskMd` и dispatch. Shared `ReleaseExporter` return contract
проверяется отдельно. `.doc/skil_data/jira/export_task.py` фиксируется как альтернативный
manual exporter; если остаётся активным, использует тот же ingest envelope, не
оставляется тайным MD-only writer. Не менять auth config и не печатать секреты.

Golden test task.md: неизменный input -> прежние bytes/формат. Получение ранее
потерянных страниц changelog может законно дополнить документ: это расширение данных,
не требование байтовой идентичности с заведомо неполным старым экспортом.

CLI чтения переписки (bounded и read-only):

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --select /tracker/status
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . tracker comments --task 2612 --limit 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --text "архивация" --fields tracker.comments,summary
```

Комментарии входят в full search только при `--fields tracker.comments` либо
configured profile; search hit содержит comment ID/snippet/source path, не всю
переписку. Input snapshot не хранит tool commands для выполнения.

Конечное состояние task.md: сырые данные Jira уже полностью живут в
`_jsondoc/tracker/{snapshot_id}/` (issue + comments + changelog постранично).
Пока генерацию ведёт PHP-экспортёр, task.md остаётся его direct output и входящим
evidence (dual-write: task.md + snapshot из одного сбора, golden байт-в-байт).
После mode=json task.md становится generated view из snapshot: канон - снимок,
файл рендерится, удаляется и восстанавливается без потери данных. Полный текст
переписки не копируется в task.json намеренно: агрегат остаётся компактным для
bounded reads, task.json хранит refs/coverage на snapshot.

Проекция релиза и ветки в metadata (одна задача - одна ветка):

- `metadata.release` = выбранный fixVersion из tracker-снапшота (первый, при
  нескольких - как `Get-DefaultReleaseBranch` в gototask; fallback в config).
  Отсутствует fixVersion - null, не выдумывается. Разрешение в git-ветку релиза
  идёт по шаблону config (`5.6.1` -> `release/5.6.1`), self-referencing связь
  tracker <-> git containment фиксируется в git_state.
- `metadata.branch` = каноническая ветка задачи по типу (`features/#N` /
  `bugfixes/#N`), подтверждается фактическими git_events/refs; расхождение типа и
  фактической ветки (bugfix заведён как feature) сохраняется как warning, не
  молчаливая перезапись.
- Команды обновления обеих проекций - существующие ingest, без новых сущностей:
  `ingest-tracker` обновляет release (новый экспорт Jira), `ingest-git` обновляет
  branch/pushed_to/release_branches. gototask-финал = один batch:
  ingest-tracker + ingest-git + render. Поиск - плоские фильтры §6.1
  (`--release`, `--branch`, `--not-in origin`), карточки catalog содержат оба поля.

### 19.3 Git: подтверждение origin и релиза

`git_state` не один commit и не общий boolean. Final model:
`{observed_at,scope,commit_set_hash,commits,remote_observations,containment,coverage}`.
Commit set - подтверждённые task-owned OIDs или stage manifest. Для каждой target
ref: `remote,ref,tip_oid,observation_kind,observed_at,ancestry:{present,absent,unknown},
result,missing_commits,reason,patch_equivalence`.

`result=all|partial|none|unknown`; `patch_equivalence=not_checked|candidate|verified`
отдельно от ancestry. Локальные remote-tracking refs -> observation_kind=local_cache.
Remote confirmation берётся из существующего разрешённого `fetch`/`ls-remote`
workflow с exact OID/time; jsondoc query/ingest сам не выполняет сеть. Факт старого
push success не доказывает присутствие ref сегодня после deletion/force-push.

Ancestry: `git merge-base --is-ancestor COMMIT TIP`, в фиксированных argv без shell.
0=present, 1=not ancestor при полной истории, другие коды=unknown/error.
Shallow/missing objects/incomplete commit set -> unknown, не none. Squash/cherry-pick
может доставить изменение без исходного OID: state `not_ancestor`, delivery unknown
до отдельного evidence. Не выводить "не вошло в релиз" только по not ancestor.
Backport ветка задачи не становится релизом по `_for5606`; release targets из config
проверяются отдельно, обе naming формы `_for5606`/`_for_5.6.0.6` сохраняются как refs.

### 19.4 Stage версии и существующие legacy layouts

Каноническая модель ровно одна: стадия N = один актуальный план `stageN/plan.md`,
один stage-диф, один набор stage-проверок; у задачи один общий task-диф. Переработка
плана той же стадии обновляет этот же plan.md (история правок живёт в git), а не
создаёт новую папку или новую стадию.

`stage1v2`/`stage1v3` - единственный legacy-случай в архиве (задача 2548, сам план
v3 называет себя доработкой того же stage 1). Это только правило чтения при миграции:
папки `stage{K}v{M}` маппятся в стадию K, актуален план с наибольшим M, остальные
сохраняются как исторические source-планы той же стадии через artifacts с scope
`stage:K`. Новая система папки-версии не создаёт, Stage-контракт отдельной сущности
"версий плана" не получает. Legacy root plan может быть task-scoped и stage1-scoped
одновременно по различным refs, но файл один; artifact identity включает scope
binding, а source bytes общие. R/AC/S IDs namespaced `document_id + план стадии +
local_id`.

Тестовый corpus ST дополнить: stage3 verified QA-only при stage2 planned не закрывает
stage2; legacy stage1v3 актуальнее stage1v2 в рамках стадии 1, не создаёт стадию;
stage6 placeholder запрещает повторно
выделить номер 6 как новый; root task diff нескольких стадий не принимается для
stage-only report. Проверка по 2467/2548 - чтение, fixture только обезличенная копия.

### 19.5 Проверяемый lossless payload

Coverage в §8 требует конкретного manifest, а не совпадения backup с самим собой.
Каждый span:
`{id,start_byte,end_byte,order,section_id,payload_path,payload_sha256,encoding,
semantic_kind}`. Диапазоны полуоткрытые [start,end), contiguous, no overlaps, sum
length == исходным bytes; BOM и line endings отдельные spans либо в payload.
Payload хранится в candidate-local `spans/{id}.bin`, не подменяется ссылкой на
original backup. Он технический lossless sidecar, не текст для поиска.

`reconstruct` читает только candidate spans в order, проверяет каждый hash и
собирает stream. Original используется исключительно как ожидаемый hash. Потеря/
двойное включение span тестируется негативной fixture. После publish task/arch
sections содержат полный UTF-8 knowledge текст, sidecar остаётся evidence миграции,
не runtime-зависимость каждого get. Render fidelity отдельно проверяет текстовые
блоки, anchors, links, code fences и таблицы; это не тот же byte round-trip.

Secrets/личные данные в legacy source: автоматически не размножать по generated
views/index/logs. Item blocked `SENSITIVE_SOURCE`; raw source не удаляется, вывод
без secret. Redaction является отдельной явной операцией с manifest исключений;
такой результат называется redacted preservation, а не 100% unchanged bytes.

### 19.6 Дополнительные CLI-контракты без недоговорённостей

| Команда | Side effects и строгий контракт |
|---|---|
| `ingest-artifact` | Только существующая task, explicit role/path/scope; ID `artifact:{task}:{scope}:{role}:{sha256(normalized path)[0:12]}`. Content hash меняется внутри того же ID. Auto-create задачи запрещён, expected revision обязателен при write |
| `ingest --task N` | План обновления всех зарегистрированных проекций изменившихся sources; default dry-run, `--apply` публикует одним batch. Не запускает exporter/gates/report |
| `recover --task/--arch` | Только known transaction journal, exclusive lock и expected hashes. Чужой ручной файл = conflict. Без auto stale-lock deletion |
| `upgrade --task/--arch --to VERSION` | Dry-run по умолчанию; известный version adapter, backup и CAS; никакого массового silent upgrade при read |
| `validate --scope workflow --input CONTEXT` | Read-only links/freshness для указанных refs; не запускает workflow и не делает permission grant |
| `tags apply --input FILE` | Только dictionary CAS, проверка aliases/parent/replacement cycles; task assignments отдельно |
| `doctor` | One-pass fsck: JSON без receipt, receipt без JSON, orphan transactions/, stale work-файлы, карточка catalog на удалённый файл, tags-assignment на deprecated без replaced_by, zombie locks (status без kill), неполные workflow (см. workflow_id в apply); тот же envelope/coverage, не третий индекс |
| `view diff --task N` / `view import` / `view discard` | Разбор VIEW_CONFLICT: diff receipt vs working tree; import = перенос правок как migrate-подобные операции с provenance (не тихий overwrite JSON); discard = восстановление generated view с записью в history |
| `lock status --task/--arch` | Read-only инспекция lock: owner token, PID, host, возраст; без удаления |
| `upgrade --task/--arch --to VERSION` | (уже в §19.6) preview/backup/CAS |
| `selftest --stage/--through/--suite` | Ровно один selector; unknown/empty selector error. Сохраняет test result под runs, не пишет live task data |
| `compatibility check --all` | Все classified entrypoints; unsafe live scripts заменяются fixture runner, not_run виден |

Все mutating envelopes имеют operation_id и expected_revision. History.actor имеет
тот же enum что update.actor; stage trigger/user request хранится источником, не
новым actor enum. В field tables `source_ids` ведут к source запись c sha256,
pointer/span и availability; проекция дополнительно хранит `projection_source_id`
и `projection_source_sha256`, чтобы refresh однозначно проверял её актуальность.

### 19.7 Schema engine и определения create/update

Stdlib validator не объявляется универсальным JSON Schema engine. J01 поддерживает
только keywords использованных schemas: `$ref`, `type` (включая nullable), `enum`,
`const`, `properties`, `required`, `additionalProperties:false`, `items`,
`minItems`, `uniqueItems`, `minLength`, `pattern`, `minimum`, `maximum`, `oneOf`.
Остальные keywords в schema = startup error, не молчаливое игнорирование. `oneOf`
используется только для непересекающихся `kind/op` tagged variants, ровно одна ветвь.
Dates/refs/actor/projections/cycles валидируются отдельными semantic checks;
bool никогда не проходит integer. Полнота keyword traversal отдельный test.

Create/update envelope - две explicit schema branches. Create содержит `document`
и пустой operations, expected_revision=0; update не содержит document и требует
существующий target. Empty update допускается как no-op. `ingest-*` не создаёт
task knowledge молча: exporter с JSONdoc enabled сначала вызывает explicit create
stub с unknown/null данными, затем apply source snapshot в той же journal операции.
Отключённый JSONdoc не требует создания task.json для старого Jira export.

Fresh observation без изменения business content не создаёт новый history event,
но observation time обновляется в source receipt, а не скрытым изменением knowledge.
Content hash исключает exported_at/checked_at timestamps и включает сами данные;
полный receipt hash включает времена для трассировки.

### 19.8 Критерий размещения данных и планы в JSON

Единый критерий, что хранится в `task.json`, что рядом и что остаётся файлом:

| Тип данных | Где живёт | Критерий |
|---|---|---|
| Записи-знания: findings, decisions, relations, tags, stages, tracker, git_state, jira_report | поля `task.json` | редактируются как записи (upsert по ID), не как текст |
| Полная переписка Jira, changelog, большие сырые данные | `_jsondoc/tracker/`, refs из агрегата | читать целиком редко; агрегат держит refs ради bounded reads |
| Бинарники: скриншоты, SVG, HTML | файлы + metadata (path, sha256, size) | base64 в JSON раздувает агрегат |
| Планы (до J17) | авторский MD + проекция в artifacts | prepare-plan/validate_plan работают от MD |
| Планы (после J17) | JSON-модель плана (sections + T/AC/R/S + plan_hash), MD - generated view | план пишется целиком через apply, построчное ручное редактирование не требуется; git-история правок сохраняется в revisions task.json |
| diff.md, task.md | файл до смены владельца генерации, затем view | см. §19.2, §13 |

Планы переносятся в JSON последним этапом J17, потому что на них завязаны
prepare-plan SKILL, validate_plan.py и research ledger с MD-контрактом. Раньше J16
это делать нельзя: миграция doc.md и переключение писателей должны завершиться
первыми. После J17 создание/правка плана - один apply (секции + матрицы + хеш),
аудит P7 читает view идентично MD; legacy MD-планы продолжают валидироваться
старым валидатором без изменений. Двух канонов одного плана быть не может:
JSON-модель или MD-source, статус виден в artifact metadata.

Структура папки задачи из §14 остаётся канонической; изменения по этому разделу:
`plan.md`/`stage{K}/plan.md` после J17 помечаются generated, а `_jsondoc/artifacts/`
хранит JSON-модель плана вместо проекции.

## 20. Итог повторного аудита и старт выполнения

### 20.1 Условия перехода к реализации

План содержит формат, расположение каждого нового вида файлов, owners, CLI,
ошибки, тесты, dependency порядок J00-J16 и сценарий миграции. Исходные разделы
сохранены, исправления выделены и связаны с обнаруженными реальными контрактами.
Сейчас подготовка плана завершена; новые schemas и tests ещё предстоит создать.
Начальный stage J00 не должен запускать live migration или менять product files.

Короткая инструкция исполнителю после разрешения реализации:

```text
Read .doc/doc_rules.md and this plan, including normative sections 13-20.
Use .doc/skil_data/task-doc as the sole new tools/tests workspace.
Execute J00, run its actual tests, save gate evidence, then J01 and so on.
After each J run its suite + cumulative suites + impacted compatibility checks.
Never mark a stage passed with zero tests or stale/missing evidence.
Do not ask to continue after a passed in-scope stage.
Stop dependent work on unresolved conflict, forbidden action or failed gate.
Preserve unrelated changes, task/stage scopes and historical evidence.
```

R/S, J и product stages теперь имеют разные namespace, а их связи явные. Формат
Git/Jira не выдаёт кеш за актуальное состояние сервера. Mongo/Postgres остаются
future index adapter; JSON файлы - канон, catalog rebuildable.

### 20.2 Что ещё нельзя утверждать до исполнения

Нельзя заявлять code-level P7 passed, успешную совместимость всех runtime IDE или
отсутствие потерь всего архива до corresponding tests/reviews. Статус этого файла
остаётся draft design с конкретным execution contract, а не фиктивный ready план
с непроверенными Before/After и пустым research ledger. Для начальной разработки
достаточно изложенного контракта. Limited mixed-mode live pilot разрешён после
J00-J13 и clone rehearsal при пользовательском scope миграции; J14-J15 собирают
evidence пилота/архива, J16 разрешает окончательный JSON-first cutover. Циклического
требования пройти live-публикацию до получения права на её пилот нет.

### 20.3 История этого аудита

- Полностью прочитаны исходные 988 строк плана; независимо проверены stage/diff,
  Jira export, schema/lifecycle, compatibility и migration риски.
- Исправлены ложное предположение о наличии stage-diff режима, max-stage selection,
  Jira comments/changelog completeness, lifecycle enum и output hash feedback.
- Добавлены isolated tree, 17 атомарных этапов, targeted+cumulative gates,
  task/stage документация, all-harness inventory и очередь script+agent migration.
- Новые runtime files, реальные task/arch JSON и массовая миграция в рамках этого
  аудита не создавались. Изменение основной спецификации только `.doc/jsondoc.md`.

## 21. Механический валидатор плана: удалено

Раздел удалён 2026-11-10. План ведёт авторский `plan.md` через `prepare-plan`,
проверку выполняет `audit-plan`. JSON-модели плана, `plan_sha256` и
механического P7.0 в харнесе нет.
