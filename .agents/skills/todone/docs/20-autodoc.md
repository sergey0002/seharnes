# Autodoc: deterministic audit and offline documentation

Этот раздел описывает фактически реализованный механизм в `scripts/tdcore/autodoc.py`.
Он не заменяет канонические task, flow, type, schema или Markdown-файлы: autodoc
читает их и создаёт производный bundle и offline HTML. Единственная запись в
канонический Markdown — owned Mermaid source block во время `generate`; команды
`discover`, `bundle`, `render`, `audit` и `verify` остаются read-only для source.

## Быстрый старт

Из корня проекта:

```bash
python3 scripts/tcheck.py autodoc generate \
  --root . \
  --bundle .todone/autodoc/bundle.json \
  --html docs_html \
  --audit
```

Та же операция доступна через совместимый alias:

```bash
python3 scripts/todone-autodoc.py generate --root . --audit
```

Проверка отдельных стадий:

```bash
python3 scripts/tcheck.py autodoc discover --root . --json
python3 scripts/tcheck.py autodoc bundle --root . --bundle .todone/autodoc/bundle.json
python3 scripts/tcheck.py autodoc render --bundle .todone/autodoc/bundle.json --html docs_html
python3 scripts/tcheck.py autodoc diagram --bundle .todone/autodoc/bundle.json --html docs_html
python3 scripts/tcheck.py autodoc audit --bundle .todone/autodoc/bundle.json
python3 scripts/tcheck.py autodoc verify --bundle .todone/autodoc/bundle.json --html docs_html
```

`discover` не пишет catalog или bundle. `bundle` пишет только названный JSON,
`render` — только названный каталог HTML, `audit` — report рядом с bundle,
`verify` ничего не меняет. Ошибки имеют exit code `1`; успешная проверка — `0`.
Нужное явное решение, например небезопасная reconstruction target policy,
возвращает `3` через общий CLI contract.

## Архитектура и lifecycle

Pipeline состоит из фиксированных стадий:

```text
preflight → read-only discovery → source inventory → adapters
→ stable entity/relation registry → AUTODOC-BUNDLE-1
→ local SVG/HTML render → deterministic audit → verify
```

`Aggregate.read_only_scan()` является общим read-only источником дерева
workspace/queue/task/document. Autodoc не создаёт aggregate snapshot во время
`discover` и не превращает generated catalog в source of truth. Дополнительные
адаптеры в bundle:

- `WorkspaceAdapter` — implicit root и explicit `WORKSPACE-1` markers;
- `Todone` projection — registry, queues, task JSON, elements, comments, refs,
  artifacts, report и source mirror;
- type и flow inventory — `types/*/type.json`, `flows/*/flow.json` и project
  overlays в `.todone/types`/`.todone/flows`;
- documentation/Markdown — `docs_path`, `.module.json`, raw Markdown и sidecars;
- contract/config — `schemas`, `templates`, `fixtures`, roles, tools и policy;
- explicit legacy evidence adapter — только явно переданный `--legacy-root`; sibling
  `/home/user/preza` и `PREZA_ROOT` автоматически не сканируются и не являются
  source-of-truth.

Каждый источник остаётся доступным через source digest и provenance. Если
adapter не может прочитать явно объявленный источник, это `unknown`, `warning`
или `invalid`, а не пустой успешный список. В частности, explicit `.todoc` marker
без поддержанного runtime даёт `todoc_unavailable`.

`disabled` и `manual` documentation policy относятся к автоматическим
documentation path согласно существующему `DocumentationWorkspace`: `manual`
оставляет явное намерение `задокументируй`, а обычное обсуждение само по себе не
создаёт нормативный факт. Autodoc не меняет policy и не записывает task/doc во
время чтения.

## Data model и provenance

Корневой bundle имеет `schema: AUTODOC-BUNDLE-1`, `bundle_id` и
`canonical_digest`. В нём находятся:

- `inventory` — stable entity IDs для workspaces, queues, tasks, documents, types,
  flows, schemas, templates, policies, tools и roles;
- `entities` — `entity_id`, `kind`, `namespace`, `status`, `source_refs`,
  `provenance`, `raw_ref`, `revision` и normalized data;
- `relations` — `contains`, `parent`, `depends_on`, `documents`, `uses`,
  `flows_to`, `route_to` и остальные зарегистрированные relation kinds;
- `sources` — canonical relative path, media type, byte size, SHA-256, raw
  UTF-8/base64 bytes если policy разрешает, redaction и source-of-truth status;
- `documents` — `AUTODOC-MARKDOWN-1` envelopes и Markdown compatibility report;
- `diagrams` — independent `AUTODOC-DIAGRAM-1` specs, source refs и asset digest;
- `warnings`, `unknowns`, `audit_input` и `reconstruction`.

Stable IDs имеют форму `workspace:<id>`, `queue:<workspace>:<alias>`,
`task:<workspace>:<queue>:<id>`, `doc:<key>@r<revision>`, `flow:<id>`,
`type:<id>` и `source:<sha256>`. Provider-specific raw task/source data не
сжимается в generic task: normalized projection и raw source существуют вместе.
Если два adapter output конфликтуют по identity, сохраняются оба source и
создаётся finding; last-write-wins не используется.

`created_at`, `bundle_id`, `canonical_digest` и output metadata не входят в
canonical digest. Порядок arrays стабилен. Поэтому повторная сборка с теми же
source bytes даёт тот же digest, даже если время запуска различается.

## Project, queue и task folders

Autodoc использует существующие folder rules:

```text
project/
├── .todone/
│   ├── workspace.json       # explicit workspace marker, если объявлен
│   ├── queues.json           # queue registry
│   ├── roles.json
│   ├── tools.json
│   ├── types/                # project type overlays
│   └── flows/                # project flow overlays
├── tasks/<queue>/.todone/
│   ├── index.json            # derived queue index
│   └── data/<id>/task.json   # canonical task
├── docs/                     # configurable docs_path
├── types/<type>/type.json
├── flows/<flow>/flow.json
├── schemas/
└── templates/
```

Корень без `workspace.json` получает implicit workspace ID из имени каталога.
Child workspace появляется только при explicit marker. Queue path за пределами
workspace не архивируется молча: в bundle остаётся unknown и причина policy gap.
Symlink не обходится без explicit разрешения, а traversal/absolute path всегда
отклоняются.

## Aggregation

Recursive aggregate остаётся отдельным реализованным projection/API:

```bash
python3 scripts/tcheck.py aggregate scan --root .
python3 scripts/tcheck.py aggregate status --root .
python3 scripts/tcheck.py aggregate verify --root .
```

`autodoc` не создаёт второй aggregate. Он вызывает read-only aggregate wrapper,
затем нормализует его rows в stable entities/relations и добавляет типы, flows,
Markdown, schemas и provenance. Aggregate catalog может быть rebuilt отдельно;
generated index/catalog не считается canonical source при reconstruction.

## Markdown contract

Каждый UTF-8 Markdown source получает `AUTODOC-MARKDOWN-1` record:

- исходные bytes и SHA-256 в соответствующем `AUTODOC-SOURCE-1`;
- canonical relative path, document key, revision и provenance;
- frontmatter, headings/anchors, paragraphs, lists, tables, blockquotes, fences,
  inline code, links и images;
- AST/token stream и `raw_unknown` constructs;
- safe escaped HTML и compatibility entries для raw HTML, unsafe URL, missing
  image, broken local link и unclosed fence.

Поддерживается dependency-free safe subset. Raw HTML не исполняется, а
показывается как escaped unknown block. `javascript:`, `data:`, `file:` и
`vbscript:` URL redacted. Ссылки на Markdown target разрешаются к generated
page; неразрешимые targets попадают в report. Таблицы, fenced code, списки и
Unicode не выбрасываются.

`render` строит docs page с TOC, heading anchors, compatibility report и
локальной ссылкой на raw `.md`. Сборка из уже скопированного bundle не требует
доступа к исходному root. Fenced block с языком `mermaid` получает отдельный
`AUTODOC-DIAGRAM-1`: его точный source остаётся в Markdown, а HTML показывает
SVG от локального Mermaid adapter и свёрнутый исходник.

`autodoc generate` по умолчанию поддерживает этот source-of-truth режим для
flow-инструкций: если owned block отсутствует, он атомарно добавляется в
канонический `.md`; если flow изменился, блок пересобирается. Изменение
Mermaid source человеком в Markdown принимается как новый source-of-truth и
не затирается. В wrapper записываются source/projection/spec digests, а
повторный запуск идемпотентен. `--augment-md` оставлен совместимым явным
алиасом, `--no-augment-md` отключает запись Markdown и оставляет только
производный HTML.

## Offline HTML и diagrams

Каталог `docs_html` содержит `index.html`, `manifest.json`, `search.json`,
`graph.json`, local `assets/app.css`, `assets/app.js`, source downloads, pages
для overview/architecture/entities/tasks/docs/flows/types/schemas/audit/sources/
reconstruction и SVG diagrams. CDN, external fonts, external CSS/JS/image
assets и filesystem links не нужны.

Каждая flow page перечисляет все steps, `input_from`, routes, dependencies,
gates, optional/parallel flags, fan-out/fan-in metadata, controls, persisted
queue-index coordinates и проблемные nodes. Диаграммы строятся только через
локальный Mermaid SDK `mermaid@12.3.0`: pinned runtime находится в
`scripts/tdcore/vendor/mermaid/mermaid.min.js`, а `render.cjs` использует
bundled DOM host и не делает network fetch. Python отвечает только за
`AUTODOC-DIAGRAM-1` и deterministic Mermaid source; ручной вывод SVG-примитивов
в renderer запрещён.

Каждый diagram spec дополнительно хранит `renderer`, `renderer_version`,
`renderer_adapter`, `renderer_runtime`, `renderer_offline`, точный
`mermaid_source`, `mermaid_source_digest`, provenance Markdown-файла/строки и
SVG digest. Для projection flow также сохраняется digest исходной flow-графики:
по нему генератор отличает устаревший owned block от ручного изменения
Markdown. Accessibility directives добавляются только в render input и не
подменяют source, который читает человек.

SVG имеет `role=img`, title, description, legend, stable layout и визуально
различает optional/parallel/gate/problem и unresolved edges. Связи, Mermaid
source и SVG spec хранятся независимо от HTML; generated output также содержит
локальный `assets/vendor/mermaid/mermaid.min.js` и renderer provenance.

Вёрстка проверяется машинно: breadcrumbs, search, TOC, focusable links,
heading hierarchy, `aria` labels, narrow viewport CSS и отсутствие external
asset tags. HTML manifest содержит page/asset digests и bundle digest.

## CLI flags и outputs

Для всех autodoc commands действуют общие `--root`, `--json`, `--quiet`,
`--limit`, `--by`. Дополнительно:

- `--bundle` — путь к bundle input/output;
- `--html` — declared generated HTML directory;
- `--archive` — разрешить embedding approved binary bytes;
- `--redact` — применить policy redaction;
- `--include`/`--exclude` — comma-separated source prefixes;
- `--legacy-root` — explicit legacy preza root;
- `--output` — audit report path;
- `--target` и `--force` — explicit reconstruction target;
- `--augment-md` — совместимый alias поддержки owned Mermaid blocks;
- `--no-augment-md` — не менять канонические Markdown-файлы в этой генерации.

`--json` печатает один machine object. Никакой command не объявляет доступным
API, которого нет в текущем `scripts/tdcore/autodoc.py`.

## Preza migration и parity

Только при явном `--legacy-root /path/to/preza` bundle может добавить
`AUTODOC-PREZA-MIGRATION-1` и вложенный строгий контракт
`PREZA-PARITY-1` (`schemas/preza-parity-1.json`). Inventory охватывает quick
start, architecture SVG, entity cards, lifecycle, commands/flags, types, flows,
schemas/templates, file catalog, checks, FAQ, live facts, footer/version и
`facts-v07.json`. Для каждой строки есть legacy evidence reference, digest,
target page, provenance refs и status `preserved`, `transformed`, `deprecated`
или `unknown`; этот evidence не становится source-of-truth.
`PREZA-PARITY-1` машинно требует все 14 section ids и все 15 inventory families:
`entity_sections`, `lifecycle`, `schema_notes`, `faq`, `command_notes`,
`file_overrides`, `commands`, `types`, `flows`, `schemas`, `templates`,
`file_notes`, `checks`, `live_facts`, `svg`; у каждого item обязательны id,
source, target, digest, status и provenance refs.

Текущие facts берутся из bundle; `facts-v07.json` остаётся baseline evidence, а
не source of truth, поэтому live facts могут иметь честный статус `unknown`.
Legacy single-page HTML не парсится для создания bundle. Architecture SVG
сохраняется отдельным legacy asset до завершения semantic parity. Пропавшая
секция, asset, command, FAQ или check становится parity finding/unknown, а не
тихим удалением. Acceptance fixture pairs находятся в
`fixtures/runtime/preza-parity-1.{valid,invalid-extra}.json`.

## Audit, verify и reconstruction

`autodoc audit` сначала валидирует schema/source identity, затем проверяет tree,
relations, dependency SCC, flow reachability/dead ends/routes, task quality,
Markdown drift и reconstruction safety. Finding содержит stable code, severity,
verdict impact, entity/relation/source refs, algorithm, message, action и
provenance. Verdict: `approved`, `changes_required` или `blocked`.

`verify` отдельно проверяет bundle schema, canonical digest, embedded source
digests, Markdown source links, HTML manifest/page digests, local paths и
offline assets. Reviewable audit findings остаются в `audit.json` и не
маскируются под digest failure.

`reconstruct` восстанавливает только raw source-of-truth records с доступными
bytes, во временный каталог и затем атомарно публикует target. Он отклоняет
absolute/traversal paths, duplicate targets и symlink escape; scripts/commands
не исполняются. Generated aggregate/index/catalog/HTML/SVG пропускаются или
rebuild-ятся существующими инструментами. Report перечисляет restored,
skipped, redacted и human-decision sources.

## Troubleshooting

**`AUTODOC_BUNDLE_INVALID`.** Проверьте `tcheck schema --file bundle.json` и
не редактируйте canonical JSON вручную; rebuild создаёт новый atomic output.

**`AUTODOC_DIGEST_MISMATCH`.** Bundle или embedded source были изменены после
сборки. Пересоберите bundle из unchanged source и повторите render/verify.

**`AUTODOC_OUTPUT_NOT_OWNED`.** `--html` содержит не-autodoc files. Выберите
пустой каталог или каталог с `manifest.json` schema `AUTODOC-HTML-1`; механизм не
удаляет чужие outputs молча.

**`AUTODOC_UNKNOWN_SOURCE` или `todoc_unavailable`.** Это provenance gap.
Добавьте explicit supported source/adapter policy либо осознанно оставьте
`unknown`; отсутствие файла не превращается в пустую документацию.

**Markdown compatibility warning.** Откройте docs page, compatibility report и
raw download. Исходник не менялся; unsupported syntax виден в `raw_unknown`.

**Reconstruction blocked.** Проверьте `reconstruction.requires_human`,
`redaction`, external queue policy и target path. Не используйте `--force`, если
нужно сохранить существующий target.

## Acceptance и regression

Acceptance fixtures находятся в `fixtures/runtime/autodoc-*.json` и покрывают
valid/unknown-key contracts для bundle, entity, relation, source, diagram, audit,
HTML, Markdown, reconstruction, packet и preza migration. Vertical acceptance
тесты проверяют deterministic digest, provenance/raw bytes, cycle/broken route
findings, local links/assets, safe HTML/SVG, reconstruction path guards и
standalone alias.

После autodoc изменённые канонические источники должны оставаться byte-identical
при обычных `discover`, `bundle`, `render`, `audit` и `verify`. Scanner plan
`/home/user/todone.scan.md` этим механизмом не читается и не меняется.
