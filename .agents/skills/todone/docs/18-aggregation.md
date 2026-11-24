# Агрегация проектов

## Текущий статус

Рекурсивная агрегация теперь реализована как read-only generated projection.
Основной CLI:

```bash
tcheck aggregate scan --root <root>
tcheck aggregate status --root <root>
tcheck aggregate list --kind tasks --root <root>
tcheck aggregate show <workspace:queue:T-001> --root <root>
tcheck aggregate verify --root <root>
```

Есть и отдельный thin alias:

```bash
python3 todone/scripts/todone-aggregate.py scan --root <root>
```

Агрегатор не изменяет child `task.json`, queue `index.json`, comments, flow
state, documentation modules или artifacts. Он пишет только generated files в
`<root>/.todone/aggregate/`.

`todoc_scan` по-прежнему не реализован и не является частью агрегатора. Он не
анализирует исходный код, не запускает PHPStan/линтеры/SAST и не вызывает агента.

## Как объявить child workspace

Корневой `<root>` включается как implicit root workspace. Для вложенного project
root нужен explicit marker:

```text
<child-root>/.todone/workspace.json
```

Минимальный marker:

```json
{
  "schema": "WORKSPACE-1",
  "workspace_id": "billing",
  "kind": "service",
  "docs_path": "docs",
  "aggregate": true
}
```

`workspace_id` должен быть уникален внутри aggregate root. Queue-level
`tasks/<queue>/.todone/` без marker не считается отдельным project workspace;
такой каталог попадает в warnings. Symlink и исключённые каталоги не обходятся.

## Что собирается

Для каждого workspace агрегатор читает:

- `.todone/queues.json` и queue roots;
- реальные `data/*/task.json`, а не только `index.json`;
- `docs/**/*.module.json` и Markdown без module sidecar как unknown document;
- parent/dependencies/queue refs;
- source path, SHA-256 fingerprint, revision и captured timestamp;
- entity modules (`doc_kind: entity`);
- completeness warnings и invalid/missing sources.

Локальные идентификаторы получают namespace:

```text
billing:main:T-001
billing:entity/Order
```

Одинаковый `T-001` в двух workspace не является конфликтом. Конфликтом является
повторный `workspace_id` или одинаковый global reference с разными источниками.

## Generated layout

```text
<root>/.todone/aggregate/
├── manifest.json       # последний AGGREGATE-1 run
├── latest.json         # производная ссылка на последний run
├── workspaces.json
├── queues.json
├── tasks.json
├── documents.json
├── entities.json
├── relations.json
├── warnings.json
├── export.json         # если выполнен export
└── snapshots/<run-id>/ # immutable run files
    ├── manifest.json
    ├── workspaces.json
    ├── queues.json
    ├── tasks.json
    ├── documents.json
    ├── entities.json
    ├── relations.json
    └── warnings.json
```

`manifest.json` содержит `aggregate_run_id`, completeness, counts, fingerprints,
список источников и warnings. Generated catalog не является source of truth.

## Практический сценарий

```bash
# 1. построить каталог
python3 todone/scripts/tcheck.py aggregate scan --root /projects/product

# 2. посмотреть полноту
python3 todone/scripts/tcheck.py aggregate status --root /projects/product

# 3. получить namespace-список задач
python3 todone/scripts/tcheck.py aggregate list \
  --kind tasks --workspace billing --root /projects/product

# 4. открыть одну агрегированную запись
python3 todone/scripts/tcheck.py aggregate show \
  billing:main:T-001 --root /projects/product

# 5. проверить, не изменились ли исходники после scan
python3 todone/scripts/tcheck.py aggregate verify --root /projects/product

# 6. сравнить два запуска
python3 todone/scripts/tcheck.py aggregate diff \
  --from-run <old-run> --to-run <new-run> --root /projects/product

# 7. перестроить generated view из snapshot
python3 todone/scripts/tcheck.py aggregate rebuild \
  --run-id <run-id> --root /projects/product

# 8. экспортировать детерминированный JSON bundle
python3 todone/scripts/tcheck.py aggregate export \
  --output /tmp/product-aggregate.json --root /projects/product
```

`scan --archive` дополнительно сохраняет source files в immutable snapshot. По
умолчанию агрегатор хранит path/hash/metadata и не копирует полный raw source.
Archive включай только после проверки политики секретов.

## Completeness и ошибки

Результат имеет статус `complete` только если discovery и чтение источников не
дали warnings. При partial read агрегатор всё равно создаёт каталог, но
`manifest.completeness.status` становится `partial`, а причина попадает в
`warnings.json`.

Особенно важны:

- `WORKSPACE_MARKER_MISSING` — child root не объявлен явно;
- `WORKSPACE_ID_DUPLICATE` — повторился workspace ID;
- `TASK_INVALID` — task JSON не читается;
- `TASK_FILE_MISSING` — папка записи неполна;
- `SYMLINK_SKIPPED` — symlink пропущен;
- `AGGREGATE_SOURCE_STALE`/verify — исходный fingerprint изменился.

Нельзя выдавать partial catalog за полную картину и нельзя редактировать task
через `aggregate show`: изменения выполняются в исходном project root обычным
`todone` CLI.

## Граница с `todoc_scan`

Агрегатор объединяет уже существующие локальные tasks и docs. `todoc_scan` —
отдельный будущий scanner pipeline для code/AST/SQL/dependency/security анализа.
Его результаты, если он будет создан, должны входить через отдельный versioned
observation envelope и не становиться verified documentation автоматически.
