# Очереди: порядок без копирования тела

## Что такое очередь

Очередь — именованный каталог работ и производный порядок. Она отвечает на вопросы
«какие записи есть?», «что брать дальше?», «что горит?», но не хранит смысловое
тело записи. Поэтому очередь можно пересобрать из `data/`, не восстанавливая факты
из копии.

## Два уровня `.todone`

Это важное различие:

```text
<root>/.todone/queues.json         # project-level registry
<root>/.todone/roles.json          # project-level roles
<root>/.todone/tools.json          # project-level capability bindings

<root>/tasks/site/.todone/index.json   # queue-level index
<root>/tasks/site/.todone/settings.json
<root>/tasks/site/.todone/data/
```

`--root` указывает на проект. `--queue site` выбирает запись реестра; путь из
реестра указывает на каталог очереди. Если очередь создана `--path`, она может
находиться вне `tasks/site`, но в реестре всё равно будет абсолютный путь.

## Реестр `QUEUES-1`

`queues.json` содержит `schema`, `updated_at` и массив `queues`. Элемент имеет
`alias`, `path`, `updated_at`. Реестр нужен, чтобы проект мог иметь несколько
очередей и чтобы CLI не угадывал рабочий каталог.

Разрешение очереди идёт так:

1. явный `--queue ALIAS`;
2. очередь, чей путь совпадает с текущим каталогом или его родителем;
3. единственная запись реестра;
4. иначе `QUEUE_NOT_RESOLVED` с требованием назвать алиас.

## Создать и найти

```bash
tqueue find --root .
tqueue find --root . --scan
tqueue init site --root .
tqueue init release --root . --path /work/release-queue
tqueue list --queue site --root .
```

`init` создаёт индекс с пустым `items`, но `data/` до первой записи не обязан
существовать. `find --scan` полезен после ручного перемещения каталога: он только
показывает незарегистрированное, а не регистрирует молча.

## Строка индекса

Индекс хранит для каждой записи только:

```text
id, path, type, title, status, priority, phase, release,
owner, due, estimate_h, parent, flow, flow_step, flow_run, flow_item,
flow_revision, updated_at
```

`flow`, `flow_step`, `flow_run`, `flow_item` и `flow_revision` входят в индекс
потому, что это состояние маршрута, а не смысловые поля записи. При
`queue.save(record)` тело сначала атомарно пишется в `task.json`, затем строка
upsert-ится и индекс тоже сохраняется.

## Порядок

Базовый порядок — `priority -> phase -> id`; `priority` не задан, он считается
позицией после целочисленных приоритетов. Зеркало сортируется в конец и не
участвует в `next_candidates`.

```bash
tqueue list --queue site
tqueue list --queue site --status ready --order due
tqueue sort --queue site --order priority --save
tqueue next --queue site --count 5
tqueue summary --queue site
tqueue board --queue site
tqueue gantt --queue site --release v1
```

`next` возвращает статусы `ready`, `in_progress`, `blocked` в порядке индекса.
Это намеренно не «только ready»: заблокированная или уже начатая работа должна
быть видна на доске. `board` дополнительно группирует `in_progress`, `blocked`,
`parked` и просроченные записи. Просроченные — записи с `due` раньше текущей даты,
которые не `closed` и не `cancelled`.

## Индекс как кэш

Признаки рассинхронизации:

- строка указывает на отсутствующую папку (`INDEX_ORPHAN`);
- папка с `task.json` не имеет строки (`RECORD_UNLISTED`);
- мета строки отличается от записи (`INDEX_MISMATCH`);
- путь индекса ведёт за пределы queue-level `.todone`.

Исправление:

```bash
tqueue index-rebuild --queue site
tcheck validate --all --strict --queue site
```

Пересборка читает только папки записей и сохраняет старые `flow`/`flow_step`,
`flow_run`, `flow_item` и `flow_revision`, если для того же id они уже были в
индексе. Она не редактирует task.json и не создаёт отсутствующие записи.

## Жизнь записи в очереди

```text
draft → ready → in_progress → closed
                 ├→ blocked → in_progress
                 ├→ parked  → in_progress
                 └→ cancelled
```

`ttask claim` — предпочтительный переход в работу: он ставит owner и, если запись
была `draft` или `ready`, переводит её в `in_progress`. Ручной `ttask status`
нужен для публикации, блокировки, parked, cancelled и явного управления потоком.
