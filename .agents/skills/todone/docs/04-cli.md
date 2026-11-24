# CLI: полный практический контракт

Запуск из корня репозитория:

```bash
python3 todone/scripts/tqueue.py <команда> ...
python3 todone/scripts/ttask.py <команда> ...
python3 todone/scripts/tcheck.py <команда> ...
```

Если скрипты установлены/обёрнуты в PATH, те же вызовы пишутся как `tqueue`,
`ttask`, `tcheck`. Флаги идут после точки входа и подкоманды. Полная справка
генерируется кодом:

```bash
python3 todone/scripts/tqueue.py --help
python3 todone/scripts/ttask.py <команда> --help
python3 todone/scripts/tcheck.py <команда> --help
```

## Общие флаги

Каждая команда наследует:

| Флаг | Назначение |
|---|---|
| `--root PATH` | корень проекта, где ищутся `.todone`, `tasks`, `types`, `flows` |
| `--queue ALIAS` | алиас очереди; без него берётся единственная/очевидная очередь |
| `--json` | один JSON-объект без обычного текста |
| `--fields a,b` | срез полей строкового вывода (`id`, `type`, `status`, `priority`, `phase`, `title`, `path`) |
| `--quiet` | только stderr при ошибке; обычный stdout подавляется |
| `--limit N` | ограничить число строк обычного вывода |
| `--by NAME` | кто выполняет правку; для мутаций обязателен там, где нужен аудит |

Обычный успешный вывод заканчивается `состояние: … | next: …`. В JSON поля
`counts` и `next` добавляются, если команда их вычисляет. `--quiet` не означает
«выполнить меньше»: он меняет только печать.

## `tqueue`: очередь как порядок

| Команда | Что делает | Основные флаги |
|---|---|---|
| `find` | читает реестр; `--scan` ищет незарегистрированные `tasks/*` | `--scan` |
| `init ALIAS` | регистрирует и создаёт пустой индекс очереди | `--path` |
| `list` | строки индекса с отбором | `--status`, `--type`, `--release`, `--phase`, `--owner`, `--overdue`, `--parked`, `--order` |
| `next` | первые кандидаты со статусом `ready`, `in_progress`, `blocked` | `--count` |
| `summary` | количество по 8 статусам | — |
| `done` | закрытые и отменённые | `--release` |
| `sort` | пересчитывает/печатает порядок | `--order`, `--save` |
| `gantt` | строка-полоса для записей со сроком | `--release` |
| `board` | в работе, следующие, блоки, parked, просроченные | — |
| `index-rebuild` | строит индекс из `data/`, сохраняя состояние flow, если оно было | — |

Примеры:

```bash
tqueue init site --root .
tqueue list --queue site --status ready --order due
tqueue next --queue site --count 3
tqueue board --queue site
tqueue index-rebuild --queue site
tqueue list --queue site --json --fields id,status,title
```

`next` не вызывает `claim`, не меняет статус и не создаёт записи. `index-rebuild`
не должен использоваться как способ исправлять тело записи: он только заново строит
производный список по существующим папкам.

## `ttask`: запись как работа

### Создание и чтение

```bash
ttask new «Название» --type default --queue site
ttask new «Внешний вход» --from-file input.json --source-system jira \
  --source-id PROJ-1 --queue site --by importer
ttask show T-001
ttask show T-001 --mode full  # допустимы body, full, comments, digest, handoff
ttask show T-001/C-2
ttask show T-001/AC-1
ttask show D-001
```

Режим без `--mode` выбирается адаптивно: при небольшой ленте — `full`, при
большой — `digest`. В явном режиме выбранный текст не усечён. Для `handoff`
`--last K` выбирает последние K реплик плюс все `handoff`.

| Адрес/режим | Состав |
|---|---|
| `body` | тело JSON без `comments` |
| `full` | тело и вся лента дословно |
| `comments` | вся лента дословно |
| `digest` | тело и оглавление ленты |
| `handoff` | тело, последние K и все `handoff` |
| `comment` / `T-001/C-2` | одна реплика |
| `element` / `T-001/AC-1` | один адресуемый элемент |
| `report` / `D-001` | отчёт закрытия |

### Поля и массовые правки

```bash
ttask set T-001 --title «Новое название» --phase core --priority 1 --by lead
ttask set T-001 --acceptance «Команда возвращает 0» \
  --acceptance «Документация обновлена» --by lead
ttask status T-001 T-002 --status ready --by lead
ttask set --ids T-001,T-002 --release v1 --by lead
printf 'T-001\nT-002\n' | ttask set --ids - --phase core --by lead
ttask set T-001 --extra reproduce='python3 -m unittest …' --by developer
```

`--goals`, `--acceptance`, `--in-scope`, `--out-of-scope`, `--context`,
`--files-hint`, `--steps`, `--verify`, `--open-questions`, `--notes` повторяются.
`--depends-on` принимает список через запятую. `--type` и `--id` у `set` не
являются способом правки: они специально дают `TYPE_IMMUTABLE`/`ID_IMMUTABLE`.

### Состояние, владелец и закрытие

```bash
ttask status T-001 --status ready --by lead
ttask status --all --type feature --status parked --reason «ждём API» --by lead
ttask claim T-001 --by developer
ttask unclaim T-001 --by developer
ttask reopen T-001 --reason «нужна дополнительная проверка» --by lead
ttask report-skeleton T-001 --by developer
ttask close T-001 --report report.json --verdict met --by developer
```

Любая операция, которая меняет данные, получает аудитора через `--by`, если это
требуется обработчиком. Закрытие и перевод в `closed` идут через одни и те же
гейты типа; красный гейт не меняет статус.

### Лента, указатели и артефакты

```bash
ttask comment add T-001 --body «решили оставить формат JSON» \
  --kind human --by lead
ttask comment add T-001 --body «нужно уточнить API» --question --by lead
ttask comment list T-001 --kind proposal
ttask comment brief T-001 --last 3
ttask comment apply T-001 --comment C-4 --note «принято» --by lead
ttask comment reject T-001 --comment C-5 --note «риск слишком велик» --by lead

ttask ref add T-001 --kind file --path src/app.py --symbol run \
  --lines 12-40 --note «точка изменения» --found-by grep --by developer
ttask ref remove T-001 --path src/app.py --note «файл удалён из области» --by lead
ttask ref rename T-001 --old src/app.py --new src/core.py \
  --note «модуль перенесён» --by developer

ttask artifact add T-001 --kind tests --path artifacts/test.log \
  --note «полный stdout» --by tester
ttask artifact rename T-001 --old artifacts/test.log --new artifacts/tests.log \
  --note «уточнили имя» --by tester
ttask evidence T-001 --kind tests --path artifacts/tests.log \
  --note «доказательство прогона» --by tester
```

`artifact add` и `evidence` проверяют существование файла внутри папки записи.
`ref` хранит адрес и пояснение, но не копирует содержимое. `link PARENT CHILD
--note …` создаёт `kind: queue` указатель в родителе; `tree` показывает иерархию.

### Digest и пакет

```bash
ttask digest T-001
ttask digest T-001 --part body
ttask digest T-001 --part toc
ttask digest T-001 --part comments:1-5
ttask pack T-001 --mode handoff --last 3 --agent developer
```

`digest` пишет `digest.md` и помечает его производным артефактом. `pack` не пишет
рабочие данные: он строит запечатанный текстовый пакет с инструкцией, брифом,
записью, выбранной лентой, refs, artifacts и контрактом возврата.

### Поток и транзакция

```bash
ttask flow start --flow jira-fix --from T-001 --batch 3 --by lead
ttask flow state T-001 --flow jira-fix
ttask flow next T-002
ttask batch ops.json --dry-run --by lead
ttask batch ops.json --by lead
ttask link T-001 T-002 --note «план продолжает вход» --by lead
```

`batch --dry-run` только печатает план. Реальный пакет либо применяет все
операции, либо откатывает `.todone` очереди целиком.

## `tcheck`: контроль и конфигурация

| Команда | Назначение |
|---|---|
| `doctor` | сводная диагностика очередей, типов, потоков, ролей, tools и прозы |
| `validate [ids]` | схема, факты, поля типа и гейты выбранных записей |
| `schema [NAME]` | ключи/перечисления реализованных схем; без имени — все |
| `selftest` | команды, флаги, объявления типов/потоков, коды и проза поставки |
| `types list/show/fields` | типы, гейты, capabilities, поля, инструкции и агенты |
| `flows list/show` | определения потоков и шаги |
| `roles list/show/set/unset` | роли и модели проекта |
| `tools list/bind/unbind` | привязки возможностей среды |
| `import jira/openspec/speckit` | локальный файл во внешнее зеркало; Jira дополнительно получает JIRA-MIRROR-1 artifacts |
| `intake start/list/show/capture/ask/answer/fix/validate/finalize/audit/cancel` | persistent постановка задачи, provenance, typed finalization и read-only audit |

Примеры:

```bash
tcheck validate --all --strict --queue site
tcheck doctor --root . --all --strict --prose
tcheck schema TASK
tcheck schema
tcheck types show feature
tcheck types fields fix
tcheck flows show release-testing
tcheck roles list
tcheck roles set developer --tier balanced --mode subagent \
  --tools read,edit,bash --models model-id --by lead
tcheck tools bind test-runner --command 'python3 -m unittest' \
  --note «запуск тестов из корня» --by lead
tcheck import jira --file jira.json --id PROJ-1 --by importer
tcheck intake start --root . --queue site --title «Экспорт» --by lead
tcheck intake list --root .
```

`intake start` создаёт persistent conversational draft. Operational draft task,
ранжирование вариантов, запись подтверждённого факта и typed finalization
требуют явного opt-in/команды; audit создаёт отдельный read-only `plan-audit`
child и не меняет target task.

## `tcheck docs`: documentation workspace, catalog и resolver

Эти команды работают только с documentation workspace текущего `--root`.
Сначала создай manifest:

```bash
tcheck docs init --root <root> --workspace-id <id> --product-id <id>
# custom point inside project root; the pointer survives a later process restart
tcheck docs init --root <root> --docs-path documentation \
  --workspace-id <id> --product-id <id>
tcheck docs check --root <root>
```

`--docs-path` is persisted as `DOC-PATH-1` in
`<root>/.todone/docs-path.json`. It is accepted by all `tcheck docs` actions and
by `ttask document`; paths outside `--root` are rejected, and an existing
workspace cannot be moved implicitly.

Явный intent записи вызывается отдельной командой `ttask document`:

```bash
ttask document --root <root> --by writer \
  --doc-key entity/order --kind entity \
  --content "# Order\n\nКаноническое описание Order."
```

При вызове без `--content` создаётся bounded capture с intent
`задокументируй`; с `--content` дополнительно записывается валидированный DOC-1
module. Для chat capture передай JSON-файл через `--from-chat`. Активные задачи
можно указать позиционно, а `--changed-file` допускает несколько исходных
файлов:

```bash
ttask document T-001 T-002 --root <root> --by writer \
  --doc-key change/release-1 --changed-file src/app.py

ttask document --from-chat capture.json --root <root> --by writer
```

### Доступные операции catalog/resolver

| Вызов | Результат |
|---|---|
| `tcheck docs catalog` | собирает локальный generated catalog из `*.module.json` под `<root>/<docs_path>` и пишет `.todone/catalog/docs.json` |
| `tcheck docs show --key family/name` | показывает текущий модуль, Markdown, machine sidecar и claims sidecar |
| `tcheck docs resolve --mode catalog` | возвращает bounded список модулей |
| `tcheck docs resolve --mode module --key family/name` | выбирает модуль по ключу |
| `tcheck docs resolve --mode machine --key family/name` | выбирает machine projection |
| `tcheck docs resolve --mode impact --task-ref queue:kind:T-001` | ищет модули по task ref |
| `tcheck docs resolve --mode for-task --task-ref queue:kind:T-001` | строит контекст для задачи |
| `tcheck docs resolve --mode path --file src/app.py` | ищет модули по source path |
| `tcheck docs resolve --mode test-map --key test-map/name` | выбирает test-map context |
| `tcheck docs resolve --mode reconstruct --key architecture/name` | bounded reconstruction context |
| `tcheck docs stale` | показывает модули с устаревшим fingerprint |
| `tcheck docs render --key family/name` | проверяет баланс Markdown fences |
| `tcheck docs policy show` | показывает effective workspace policy |
| `tcheck docs policy set ...` | изменяет policy с проверкой approval/scope |

Для ограничения ответа используй `--limit` и `--chars`; JSON-вывод включается
общим `--json`. `catalog`/`resolve` не изменяют канонический текст модуля,
а `render` — это check, не второй renderer/source of truth.

### Policy

Поддерживаемые значения:

```text
automation: ask | always | manual | disabled
enforcement: advisory | required | critical
cadence: slice | aggregate | both | explicit
update_after: implementation | slice_tests | all_tests | explicit_command
verify: on_update | after_final_tests | on_close
```

`manual` отключает автоматические запуски, но оставляет явный `ttask document`.
На уровне конкретного шага FLOW-DOC вопрос (`document_now`, `skip_once`,
`switch_to_manual`, `cancel`) управляет только этим run и сохраняется в
append-only flow decision ledger. На уровне workspace policy действует для
всех потоков, если более узкий flow/task/run override не переопределяет её.

`disabled` запрещает и автоматический, и явный documentation path; для
workspace-level disable нужен явный `--confirm`:

```bash
tcheck docs policy set --automation disabled --confirm \
  --reason "временная остановка" --by owner --root <root>
```

Понижение `required`/`critical` до `advisory` требует approval; изменение scope
`flow`, `task` или `change` записывается в отдельный decision ledger и не меняет
workspace policy молча.

## `tcheck aggregate`: рекурсивный generated catalog

Агрегатор работает по explicit child markers и не редактирует дочерние roots:

```bash
tcheck aggregate scan --root <root>
tcheck aggregate status --root <root>
tcheck aggregate list --kind tasks --workspace billing --root <root>
tcheck aggregate show billing:main:T-001 --root <root>
tcheck aggregate diff --from-run <old> --to-run <new> --root <root>
tcheck aggregate rebuild --run-id <run> --root <root>
tcheck aggregate verify --root <root>
tcheck aggregate export --output /tmp/aggregate.json --root <root>
```

`scan --archive` сохраняет source files в immutable snapshot; без `--archive`
сохраняются path, metadata и SHA-256. Generated catalog находится в
`<root>/.todone/aggregate/`, а source of truth остаётся в child `task.json`,
локальных docs modules и queue storage.

`tcheck docs catalog/resolve` — другой контур: он работает внутри одного
documentation workspace. `tcheck aggregate` объединяет несколько объявленных
workspace с namespace и provenance. `todoc_scan` всё ещё не реализован и не
запускается агрегатором. Подробности — в [18-aggregation.md](18-aggregation.md).

## Коды возврата

- `0` — команда выполнена; для контроля находок нет ошибок;
- `1` — найдены ошибки/находки или транзакция откатилась;
- `3` — нужен ответ/обязательный вход (`ASK_USER`).

Ошибки печатаются в stderr с кодом, предметом, объяснением, действием и командой.
