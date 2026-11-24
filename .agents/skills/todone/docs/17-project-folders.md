# Как работать с папками проекта

У `todone` есть четыре разных дома. Их нельзя смешивать: каталог установки,
project root, очередь и отдельная запись имеют разные источники правды.

## 1. Каталог установки

```text
todone/
├── scripts/       # CLI и runtime
├── docs/          # документация поставки
├── references/    # справочники полей, схем, ролей, ловушек
│   └── child-skills/  # процедуры по рабочим намерениям
├── assets/        # данные поставки (типы, потоки, схемы, шаблоны, примеры, фикстуры)
│   ├── types/     # встроенные type definitions
│   ├── flows/     # встроенные flow definitions
│   ├── schemas/   # versioned machine schemas
│   ├── templates/ # стартовые JSON-формы
│   ├── examples/  # примеры проектов
│   │   └── v6-project/
│   └── fixtures/  # valid/negative fixtures
└── tests/         # acceptance tests
```

Встроенные `assets/types/` и `assets/flows/` читаются кодом из поставки. Не клади сюда задачи
конкретного продукта и не используй `todone/flows/` как project state.

## 2. Project root

`--root <root>` указывает каталог проекта. По умолчанию documentation
workspace пишется в `<root>/docs`, но `tcheck docs init --docs-path <path>`
может выбрать другую точку внутри root. Она сохраняется в
`<root>/.todone/docs-path.json` (`DOC-PATH-1`) и используется после restart;
смена уже выбранного пути требует отдельной migration policy.

```text
<root>/
├── .todone/
│   ├── queues.json                    # registry: alias → queue path
│   ├── docs-path.json                 # DOC-PATH-1 pointer, if custom/default docs enabled
│   ├── roles.json                     # project roles
│   ├── tools.json                     # capability bindings
│   ├── flows/<id>/                    # full project override of a flow
│   ├── types/<id>/                    # project type extensions/overrides
│   ├── flow-decisions.json            # flow choice/control ledger, when used
│   ├── flow-transitions.json          # immutable flow transition ledger
│   ├── documentation-policy-decisions.json
│   └── catalog/docs.json              # generated documentation catalog
├── docs/
│   ├── manifest.json                  # WORKSPACE-1, if docs enabled
│   ├── entities/                      # DOC-1 modules
│   ├── requirements/
│   ├── contracts/
│   ├── workflows/
│   ├── decisions/
│   ├── test-maps/
│   └── changes/
└── tasks/
    └── <queue-alias>/                 # queue storage
```

В этом примере `docs/` — значение по умолчанию; при custom path этот каталог
заменяется на `<root>/<docs_path>`, а структура manifest/modules остаётся той же.

Project `.todone/flows/<id>/flow.json` целиком заменяет встроенное определение с
тем же id, а не сливается с ним по ключам. После изменения override запускай
`tcheck flows show`, `tcheck selftest` и `tcheck doctor`.

## 3. Queue root

Путь очереди регистрируется в `<root>/.todone/queues.json`. Типовая очередь:

```text
<root>/tasks/site/
└── .todone/
    ├── index.json       # производный индекс
    ├── settings.json    # queue settings
    └── data/
        └── T-001-feature/
            ├── task.json
            ├── task.json.bak
            ├── report.json
            ├── digest.md
            └── artifacts/
```

`task.json` — source of truth записи. `index.json` — производный список и flow
coordinates. Его нельзя править вручную; для восстановления используй:

```bash
tqueue index-rebuild --root <root> --queue site
```

`.bak` и `digest.md` не являются новым домом фактов. `report.json` — рабочий
документ закрытия, а после успешного close его копия также доступна в записи.

## 4. Что где менять

| Нужно изменить | Правильный дом | Команда/правило |
|---|---|---|
| запись, status, поля, refs | `tasks/<queue>/.todone/data/.../task.json` через runtime | `ttask set/status/ref/...` |
| порядок и index metadata | queue `.todone/index.json` производно | `tqueue sort/index-rebuild` |
| project roles/tools | `<root>/.todone/roles.json`, `tools.json` | `tcheck roles/tools` |
| flow definition | `todone/flows/` или project override | `tcheck flows`, затем tests/doctor |
| docs module | `<root>/<docs_path>/<family>/` | `ttask document`, `tcheck docs`; default `docs_path=docs` |
| docs policy | manifest/decision ledger | `tcheck docs policy ...` |
| большой task result | папка записи `artifacts/` | `ttask artifact/evidence` |
| чужой факт | bounded ref | `ttask ref` или `ttask link` |

Не создавай отдельный `state.json` для flow, не копируй один факт в несколько
canonical owners и не записывай результат напрямую из модели в JSON.

## 5. Несколько project roots

Каждый независимый project root имеет свой registry и может иметь собственные
queues, docs manifest, flows и policies. Несколько roots объединяются только
явным `tcheck aggregate scan` через workspace markers; обычные `tcheck docs`
вызовы их не смешивают. Для большого дерева см. [агрегацию](18-aggregation.md).
