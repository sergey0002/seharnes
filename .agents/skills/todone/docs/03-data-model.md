# Модель данных и раскладка

## Полный путь от проекта до записи

Для проекта с корнем `<root>` и очередью `site` по умолчанию используется такая
структура:

```text
<root>/
├── .todone/
│   ├── queues.json              # реестр очередей проекта: алиас → путь
│   ├── roles.json               # роли, уровни, режимы, инструменты, модели
│   └── tools.json               # привязки capabilities проекта
├── tasks/
│   └── site/                    # каталог очереди; можно заменить --path
│       └── .todone/
│           ├── index.json       # производный индекс очереди
│           ├── index.json.bak   # резерв прежнего индекса после записи
│           ├── settings.json    # необязательные пороги чтения
│           └── data/
│               └── T-001-feature/
│                   ├── task.json
│                   ├── task.json.bak
│                   ├── report.json       # если создан отчёт
│                   ├── digest.md         # если создан digest
│                   └── artifacts/…       # файлы, на которые ссылается запись
├── intake/
│   └── <session-id>/draft.json   # INTAKE-1, events и captured inputs
└── …

После явного `tcheck aggregate scan` root также получает generated
`.todone/aggregate/` с `AGGREGATE-1` manifest, namespaced catalogs и snapshots.

`roles.json` и `tools.json` относятся к корню проекта, а `index.json`, `settings.json`
и `data/` — к конкретной очереди. Путь очереди хранится в `queues.json` как
абсолютный путь, даже если он задан относительным `--path`.

## Documentation workspace

Если documentation path включён явно, `<root>/<docs_path>/manifest.json` описывает
workspace `WORKSPACE-1`, а canonical modules располагаются по семействам. По
умолчанию `docs_path=docs`; explicit `tcheck docs init --docs-path <path>`
сохраняет выбор в `<root>/.todone/docs-path.json` (`DOC-PATH-1`):

```text
<root>/<docs_path>/
├── manifest.json
├── entities/order.md
├── entities/order.module.json
├── entities/order.machine.json   # если передан machine sidecar
├── entities/order.claims.json    # если передан claims sidecar
└── ...
<root>/.todone/catalog/docs.json  # generated local catalog
```

`ttask document` — единственный текущий intent writer для этого домена;
`tcheck docs catalog/resolve` читают и строят производные представления. Все
операции используют сохранённый `docs_path`; при явном вызове можно передать
`--docs-path`, но смена уже выбранного пути не выполняется молча. Несколько
объявленных roots объединяются read-only командой
`tcheck aggregate`; generated catalog не становится источником правды.

## Источники правды

| Файл/дом | Источник правды? | Что можно делать |
|---|---:|---|
| `data/T-NNN-тип/task.json` | да | читать только через ядро/CLI, править через CLI |
| `.todone/index.json` очереди | нет, производный | пересоздать `tqueue index-rebuild`, не редактировать руками |
| `queues.json` | конфигурация проекта | изменять командами `tqueue init` |
| `roles.json` | конфигурация проекта | изменять `tcheck roles set/unset` |
| `tools.json` | конфигурация проекта | изменять `tcheck tools bind/unbind` |
| `<docs_path>/<family>/<name>.md` + `.module.json` | да для документационного модуля | писать через `ttask document`, читать через `tcheck docs`; default `<docs_path>=docs` |
| `.todone/docs-path.json` | конфигурация точки записи | изменять только `tcheck docs init --docs-path` при создании workspace |
| `.todone/catalog/docs.json` | нет, производный | пересоздать `tcheck docs catalog` |
| `.todone/intake/<session>/draft.json` | да для conversational draft | изменять через `tcheck intake`, не редактировать вручную |
| `.todone/aggregate/*.json` | нет, generated | пересоздать `tcheck aggregate scan` или `rebuild` |
| `digest.md` | нет, производный | пересоздать `ttask digest <id>` |
| `report.json` | рабочий документ отчёта | создать каркасом, заполнить и передать `ttask close` |
| инструкции Markdown | конфигурация/проза | читать; обновлять как поставку с последующим doctor |

Каждая запись и индекс пишутся атомарно через временный файл и `os.replace`; если
файл существовал, рядом сохраняется `.bak`. Это защищает от неполной записи, но
не делает ручное редактирование безопасным: формат всё равно должен изменяться CLI.

## TASK-6: `task.json`

Запись содержит следующие группы ключей.

### Идентичность и очередь

| Ключ | Смысл |
|---|---|
| `id` | `T-NNN`; назначается один раз и неизменен |
| `kind` | тип-плагин; назначается один раз и неизменен |
| `title` | заголовок |
| `status` | `draft`, `ready`, `in_progress`, `blocked`, `parked`, `mirror`, `closed`, `cancelled` |
| `priority` | целое для порядка; по умолчанию `2` |
| `phase` | свободная метка фазы |
| `release` | `null` или непустая строка релиза |
| `parent` | id родительской записи или `null` |
| `depends_on` | массив id зависимостей |
| `parallelizable` | факт, можно ли выполнять параллельно |
| `module` | модуль/область |
| `owner` | владелец после `claim` |
| `started_at` | время первого перехода в работу |
| `due` | срок `ГГГГ-ММ-ДД` |
| `estimate_h` | числовая оценка часов |
| `created_at` | время создания |
| `change_kind` | вид изменения |

`release` в текущем TASK-6 — nullable string для локальной рабочей метки. Для
Jira она не является канонической identity релиза: Project Version хранится
вне issue, а issue может ссылаться на несколько `fixVersions` и `versions` с
разными смыслами. Локальный Jira profile сохраняет `release_ref` для
version id, раздельные `fixVersions`/affected `versions` и валидированный
`JIRA-MIRROR-1` projection; task lifecycle при этом не меняется. Сетевой
version registry и API acquisition не являются текущим runtime.

### Смысловые поля и массивы

`problem` — обычная строка наблюдаемой проблемы. Остальные перечисленные ниже
поля — массивы объектов `{ "id": "…", "text": "…" }`; адрес элемента нужен для
критериев, отчётов и команд чтения.

| Поле | Префикс адреса | Назначение |
|---|---|---|
| `problem` | — | наблюдаемая проблема |
| `goals` | `G-N` | цели |
| `acceptance` | `AC-N` | критерии приёмки |
| `in_scope` | `IN-N` | границы работы |
| `out_of_scope` | `OUT-N` | исключённые области |
| `context` | `CT-N` | факты контекста |
| `files_hint` | `F-N` | ориентиры по файлам |
| `steps` | `S-N` | план действий внутри записи |
| `verify` | `V-N` | способы проверки |
| `open_questions` | `Q-N` | вопросы, которые нельзя додумывать |
| `notes` | `N-N` | текстовые пометки; отдельной сущности note нет |

Текст не получает жёсткого лимита. Проверяется наличие, тип, enum и pattern, если
они объявлены типом; «достаточно» определяется смыслом гейта и человеком.

### Расширения записи

- `extra` — словарь полей, объявленных `FIELD-1` у типа. Неизвестное или
  обязательное незаполненное поле даёт находку.
- `refs` — массив указателей `REF-1`: `kind`, `path`, `symbol`, `lines`, `note`,
  `found_by`. `note` обязателен. Разрешённые виды: `file`, `symbol`, `doc`, `url`,
  `queue`, `report`.
- `artifacts` — массив `ARTEFACT-1`: `kind`, `derived`, `path`, `note`. Файл
  должен реально существовать внутри папки записи. Виды: `spec`, `refs`, `tests`,
  `report`, `log`, `digest`, `other`.
- `comments` — лента `COMMENT-1`. Виды реплик: `human`, `agent`, `import`,
  `proposal`, `handoff`. Внешний id хранится в `external_id`; решение proposal
  записывается в `resolution`, `resolved_by`, `resolved_at`.
- `source` — контракт `SOURCE` (внутренний идентификатор версии — `SRC-2`), обычно только у зеркала. `raw` хранит вход дословно.
- `report` — сохранённая копия отчёта после успешного закрытия; физический
  документ остаётся в `report.json`, а поле позволяет читать отчёт через
  `ttask show <id> --mode report`.

### Статусы

| Статус | Значение | Участвует в очереди |
|---|---|---:|
| `draft` | ещё формируется | да |
| `ready` | можно брать | да |
| `in_progress` | выполняется | да |
| `blocked` | остановлено, причина в `blocked_reason` | да |
| `parked` | отложено без сущности «заметка» | да |
| `mirror` | внешний вход; ручная правка запрещена | нет, сортируется в конец |
| `closed` | закрыто через гейт | да, но в работу не выбирается как кандидат |
| `cancelled` | отменено | да, но в работу не выбирается |

## INDEX-1: `index.json`

Верхний объект содержит `schema`, `alias`, `updated_at`, `order` и `items`.
Каждая строка `items` содержит:

```text
id, path, type, title, status, priority, phase, release,
owner, due, estimate_h, parent, flow, flow_step, flow_run, flow_item,
flow_revision, updated_at
```

`path` — относительный путь от `.todone/` очереди до папки записи. Тела, цели,
комментарии, raw и результаты в индекс не копируются. `flow`, `flow_step`,
`flow_run`, `flow_item` и `flow_revision` — производное состояние участия
записи в потоке; отдельного state-файла нет. `flow_item` нужен для dynamic
fan-out, `flow_revision` — для новой обычной записи после route revision.

Базовый порядок индекса: `priority -> phase -> id`. `mirror` уходит в конец.
`list` и `sort` могут выбрать поле `priority`, `phase`, `due`, `id` или
`updated_at`; `sort --save` сохраняет новый порядок в индекс.

## REPORT и D-NNN

`ttask report-skeleton` создаёт `report.json` с id `D-NNN`, id задачи, детьми,
результатом, реализацией, изменёнными файлами, алгоритмом, verification,
evidence, статусом каждого `AC-N`, попытками, отклонениями, рисками, событиями,
временем и автором завершения. `ttask show D-NNN` находит этот файл среди
записей и показывает отчёт в режиме `report`.

`--verdict met|not_met|blocked` заполняет пустые статусы acceptance, но отчёт всё
равно должен пройти гейты типа.

## Производные файлы

`digest.md` строится из полного тела, оглавления ленты и всей ленты дословно.
Он объявляется артефактом `kind: digest`, `derived: true`, но источником остаётся
`task.json`. После любой правки `tcheck doctor` может выдать `DIGEST_STALE`; снова
выполни `ttask digest <id>`.

## Настройки чтения

В `settings.json` можно задавать только эти числовые параметры:

| Ключ | Значение по умолчанию | Для чего |
|---|---:|---|
| `adaptive_comments` | 10 | сколько реплик допускает автоматический режим `full` |
| `adaptive_chars` | 8000 | размер ленты для автоматического `full` |
| `digest_chars` | 40000 | порог предложения производного digest |
| `handoff_last` | 3 | последние реплики для handoff-пакета |
| `toc_chars` | 4000 | порог оглавления длинных справочников |
| `flow_max_batch` | 5 | общий предел порции потока |

Эти пороги не режут тексты. Они выбирают режим, размер пакета или подсказку.
