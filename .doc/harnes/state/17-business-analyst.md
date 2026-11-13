# Business analyst: анализ задач и хранение бизнес-знаний

<!-- meta
type: architecture
status: deprecated
version: 2.1
updated: 2026-11-10
related: [../index.md, ./02-skills.md, ./03-rules.md, ./05-scripts.md, ./06-jsondoc.md, ./07-workflows.md]
tags: [harness, business-logic, jira, json, hash-ledger, quarantine, registry, transactions, recovery, tests]
-->

---

> **Снято с харнеса 2026-11-10.** Скилы `business-analyst` и `task-business-analysis`,
> правило `business-rules.mdc`, скрипты анализа и план-гейты удалены из канона.
> Документ остаётся историческим описанием. Новый анализ бизнес-правил не ведётся.

## Суть

Атомарный скил `task-business-analysis` сохраняет бизнес-контекст задачи:
сущности, правила, факты, ограничения, критерии и исключённые требования.
Планирование, подготовка тестов и документация переиспользуют актуальный анализ.
Смысл и конфликты определяет агент; скрипты подбирают очередь, проверяют
структуру и свежесть, хранят данные через единый `BusinessStore`.

Кандидаты и цитаты остаются в рабочей зоне аналитика. В `task.json` через JSONdoc
попадают проверенные факты и отдельно неподтверждённые записи. Принятое требование
без реализующего кода остаётся `proposed/pending`, наличие требования не доказывает
реализацию.

Первичный повод правок: неверно сформулированное правило могло получить verified
без смысловой сверки и стать основанием плана. Удалены безусловный no_conflict,
поиск конфликтов по одинаковому тексту и разрешение замены только по дате задачи.
Старые правила и план задачи 2077 автоматически не исправлялись.

Контур реализован в объёме ядра. Часть интеграций осталась частичной: Jira MCP
adapter, CBM anchors, runner `test-task --impact`, пилот и golden set.

План: [`plan.md`](../../buisnes_analis/plan.md).

### Где лежали инструкции

Скил `business-analyst`, правило `business-rules.mdc`, скрипты и ссылки в этом
разделе удалены 2026-11-10 вместе с контуром. Ссылки на
`.agents/skills/business-analyst/` и
`.agents/skills/task-router/children/task-business-analysis/` ниже исторические и
не открываются. Документ остается описанием прежнего устройства.

Подробные форматы и аргументы хранятся в документах владельца. Этот документ
фиксирует интеграцию и результаты внедрения, без второй копии схем.

---

## 1. Статус реализации

| Блок | Статус | Где |
|---|---|---|
| Схемы данных | реализовано | `../../buisnes_analis/schemas/` |
| Jira JSON sync | реализовано на `tracker.json` и `task.json` | `jira_sync.py` |
| Hash-ledger | реализовано | `state.json` |
| Извлечение кандидатов | prepare/commit, LLM на уровне скила | `extract_rules.py`, `SKILL.md` |
| Code anchors | реализовано: CBM `search_graph` с fallback на `rg` и PHP-скан | `resolve_anchors.py` |
| Auto verify и score | реализовано | `verify_rules.py` |
| Shadow | реализовано | `auto_run.py --shadow` |
| Quarantine | реализовано | `quarantine.json` |
| Promote в task.json | реализовано через JSONdoc | `promote_rules.py` |
| Согласованная публикация | registry, facts, links, quarantine, published-review и analysis входят в один журнал `prepared/committed` | `publish_transaction.py`, `task_business_analysis.py` |
| Recovery публикации | roll-forward по old/new hashes, повторное применение JSONdoc envelope, безопасный orphan-lock reap | `publish_transaction.py`, JSONdoc `store.py` |
| История verified facts | stable `candidate_id`, `fact_revision`, `fact-history/{N}.json`; refine/replace только с evidence | `promote_rules.py` |
| Единый драйвер | JSON backend, атомарная запись документа, lock и compare-and-swap | `business_store.py` |
| Справочник сущностей | ID, name, description, aliases, версии и история | `knowledge.json`, `entity list/get/save` |
| Анализ задачи | кэш по входам, требования и закреплённые правила | `task_business_analysis.py`, `knowledge.json` |
| Агентская сверка | каждый кандидат со всем действующим реестром; rank не исключает правила | `reconcile_rules.py`, `review.json` |
| Связи задач | introduced_by, changed_by, applies_to, verified_by | драйвер, `knowledge.json` |
| Registry, snapshots, rollback | через драйвер; публикация одной задачи без переутверждения всей базы | `business_store.py`, `task_business_analysis.py` |
| Журнал версий | явное решение агента и основание; дата задаёт только порядок | `registry.json`, `history` |
| Публичные docs | реализовано: `index.md` только active, `history.md`, `conflicts.md` | `render_rules.py` |
| Impact и test plan | подготовка матрицы и плана | `impact_rules.py`, `build_test_impact.py` |
| gototask hook | analysis-prepare, без извлечения и автопубликации | `gototask.ps1` |
| Гейт готового плана | fingerprint анализа, версии правил и покрытие AC/R/S | `plan_verify.py`, `validate_plan.py` |
| Jira MCP adapter | частично: читается tracker/task JSON | `jira_sync.py` |
| `test-task --impact` | частично: план есть, runner не подключён | `build_test_impact.py` |
| Лимиты batch | реализовано: `--max-tokens`, `--max-minutes`, checkpoint, resume | `auto_run.py` |
| Пилот и golden set | не начато | - |

---

## 2. Поток данных

```text
gototask / task-intake / прямой запрос / prepare-plan P0.7
  -> analysis-prepare
     -> актуальный анализ: cache_hit, переиспользование
     -> needs_analysis / needs_review: task-business-analysis
        -> первичные источники, сущности, кандидаты, anchors
        -> review-prepare: весь реестр на каждый кандидат
        -> агентская сверка по первичным задачам
        -> вопрос пользователю только при неразрешённой неоднозначности
        -> review-complete / review-check
         -> analysis-complete: одна recoverable-публикация
            -> registry.json, task.json facts, links, quarantine, archives,
               published-review.json и analysis в knowledge.json
         -> promote: отдельная публикация только task.json facts через тот же journal
  -> analysis-context
     -> план: версии правил и requirement -> AC -> R -> S
     -> подготовка тестов и документирование: тот же анализ
  -> plan-check на готовности и повторном аудите
```

Главный инвариант: кандидат и цитата не попадают в `.doc/tasks/{N}/`. В задачу
попадает только verified fact с `evidence_ref` на рабочую зону аналитика.

---

## 3. Зоны хранения

### 3.1 Рабочая зона аналитика

```text
.doc/skil_data/business-analyst/
  registry.json
  quarantine.json
  knowledge.json
  registry.snapshots/
  analysis.snapshots/{N}/{hash}.json
  fact-history/{N}.json
  transactions/{id}/journal.json + staged/ + backup/
  publish.lock
  evidence/{N}/{hash}.json
  work/{N}/
    jira.json
    candidates.json
    state.json
    review-input.json
    review.json
    published-review.json
    analysis-input.json
    verification.json
    promotion.json
    test-matrix.json
    test-plan.json
    shadow-report.json
    run.log
```

Код и тесты находятся в `.agents/skills/business-analyst/scripts/` и `tests/`,
рабочие данные в папку скила не записываются. Прямые записи registry/quarantine/
knowledge запрещены. Подробности: [модель хранения](../../../.agents/skills/business-analyst/references/storage.md#канон-и-интерфейс).

### 3.2 Зона задачи

```text
.doc/tasks/{N}/task.json
  business_logic.facts[]
  business_logic.unconfirmed[]
  business_logic.linked_rule_ids[]
```

`unconfirmed[]` хранит правила из карантина с пометкой «не подтверждено»:
`reason`, `metrics.score`, `metrics.checks`, `metrics.quarantine_id`,
`metrics.next_check_at`, `metrics.attempts`, `anchor_status`, `test_status`.
Это не active-правила и не источник registry.

В `business_logic.facts[]` запрещены:

- `quote`;
- `candidate`;
- `confidence`;
- `raw_text`;
- `comment_body`.

### 3.3 Публичная документация

```text
.doc/architecture/business-rules/
  index.md
  orders.md
  payments.md
  tariffs.md
  deposition.md
  auth.md
  items.md
  registry.md
```

Генерируется из `registry.json`. Руками не правится.

---

## 4. Пошаговый pipeline

### 4.1 `jira_sync.py`

Вход:

- `.doc/tasks/{N}/_jsondoc/work/tracker.json`;
- `.doc/tasks/{N}/task.json`.

Что делает:

- ADF конвертирует в чистый текст;
- удаляет ботов и системных авторов;
- редактирует email, телефоны, карты, секреты;
- считает `text_sha256` и `adf_sha256`;
- считает `snapshot_id`;
- сохраняет `work/{N}/jira.json`.

Выход:

```json
{
  "issue_key": "CT-2548",
  "snapshot_id": "...",
  "description": {"text": "...", "text_sha256": "..."},
  "comments": [{"id": "79674", "text_sha256": "...", "text": "..."}],
  "changelog": [],
  "links": []
}
```

Ограничение: Jira MCP adapter не расширялся, используется существующий
`tracker.json`. Это следующий шаг.

### 4.2 `extract_rules.py`: prepare и commit

Смыслового извлечения в Python нет. Скрипт делит работу на две операции.

`prepare`:

- читает `jira.json` и `state.json`;
- проверяет `snapshot_id`, `text_sha256` комментариев и `cond_sha256` условий;
- неизменённые данные не отдаёт;
- пишет `extract-input.json` с новыми комментариями, описанием, `seen_conditions`,
  домен-подсказками и схемой ответа;
- возвращает `needs_llm: true`, если есть что анализировать.

`commit`:

- читает `candidates.llm.json` от агента;
- проверяет `kind`, `domain`, `statement`, `conditions`;
- проверяет, что каждая `quote` есть в источнике;
- считает `quote_sha256` и `cond_sha256`;
- отбрасывает уже известные условия;
- присваивает `candidate_id`;
- пишет `candidates.json` и обновляет `state.json`.

Без `candidates.llm.json` задача остаётся `needs_llm`. Правила не выдумываются
эвристикой.

### 4.3 `resolve_anchors.py`

Вход:

- `candidates.json`;
- код проекта.

Что делает:

- сначала запрашивает CBM `search_graph` через CLI `codebase-memory-mcp`, берёт
  методы и функции с их диапазоном строк и `qn`;
- отбрасывает `tests/`, `sql/`, `templates/`, `vendor/`, `.doc/` и классы
  `*Exception`, `*Error`, `*Trait`, `*Interface`;
- ранжирует якоря: папка домена выше прочих, `Controller` понижается, совпадение
  ключевых слов в имени символа добавляет вес; берёт до трёх якорей;
- если CBM недоступен или ничего не нашёл, переходит на `rg` и PHP-скан;
- по возможности использует backticked-токены и CamelCase;
- для `admin`-задач сначала ищет в `admin/`;
- находит класс и метод;
- считает `symbol_sha256` по телу метода;
- сохраняет `file`, `symbol`, `line_start`, `line_end`, `role`, `anchor_quality`
  (`cbm` для CBM, `heuristic` для `rg`, `agent` для явной пары).

CBM отключается флагом `--no-cbm` или переменной `BA_DISABLE_CBM=1`; handle
проекта задаётся `BA_CBM_PROJECT`, иначе выводится из пути репозитория.
`trace_path` и `get_file_outline` пока не используются: `search_graph` уже даёт
файл, диапазон строк и квалифицированное имя. При отсутствии якоря кандидат
уходит в quarantine `no_anchor`.

### 4.4 `verify_rules.py`

До verify требуется полный актуальный отчёт агента. no_conflict и no_duplicate
зависят от решения агента; отсутствие отчёта не означает отсутствие конфликтов.
Скрипт проверяет непустоту условий, но атомарность смысла определяет агент.
Цитата и PHP-символ не доказывают правильность бизнес-формулировки.

Проверки:

| Проверка | Вес |
|---|---:|
| `quote_exists` | 0.25 |
| `condition_atomic` | 0.15 |
| `domain_valid` | 0.10 |
| `code_anchor_exists` | 0.20 |
| `test_spec_literal` | 0.15 |
| `no_duplicate` | 0.10 |
| `no_conflict` | 0.05 |

Порог: 0.80, для money/permission/status-transition/idempotency 0.85.
Обязательные: `quote_exists`, `condition_atomic`, `code_anchor_exists`,
`no_duplicate`, `no_conflict`.

Выход:

- `verification.json` со score и checks;
- `quarantine.json` для непрошедших.

### 4.5 `promote_rules.py`

Вход:

- `verification.json`;
- `candidates.json`;
- `task.json`.

Что делает:

- берёт `result=verified` в `business_logic.facts`;
- берёт `result=quarantined` в `business_logic.unconfirmed` с метриками;
- добавляет `evidence_ref`, `code_anchors`, `test_refs`;
- пишет через JSONdoc `store.apply` с `set business_logic`;
- использует стабильный `candidate_id`, а legacy positional ID сопоставляет только при миграции;
- обрабатывает duplicate адресно и не блокирует другие verified candidates;
- требует explicit `refine`/`replace` и `change_evidence` для изменения факта;
- сохраняет заменённую версию в `fact-history/{N}.json`;
- пишет через общий publication journal и JSONdoc.

Проверено на копии задачи: JSONdoc применяет `business_logic`, сохраняет revision,
`ingest-tracker` не затирает факты.

Неподтвержденные правила пишутся рядом:

```json
"unconfirmed": [
  {
    "id": "BQ-2548-02",
    "candidate_id": "RC-2548-05",
    "title": "Лимит субъектов",
    "statement": "...",
    "status": "unconfirmed",
    "reason": "no_anchor",
    "anchor_status": "missing",
    "test_status": "planned",
    "metrics": {
      "score": 0.65,
      "checks": {"code_anchor_exists": false, "quote_exists": true},
      "quarantine_id": "Q-2548-21",
      "next_check_at": "2026-11-01T00:00:00Z",
      "attempts": 0
    }
  }
]
```

### 4.6 `aggregate_rules.py`

Что делает:

- читает verified facts из всех `task.json`;
- определяет дату задачи: resolution, created_at, updated_at;
- применяет явные решения reconciliation, дата задаёт только порядок;
- требует решение replace/refine и основание для изменения версии;
- не определяет дубли по тексту или хешу;
- сохраняет все `source_tasks`;
- выдаёт стабильные ID `BR-{DOMAIN}-{NNN}`;
- сохраняет `registry.snapshots/`;
- не анализирует смысл и не обнаруживает конфликты текстовой эвристикой;
- сохраняет существующие неразрешённые конфликты;
- увеличивает `revision`.

Полная aggregate блокируется при старых фактах без reconciliation. `aggregate`
остаётся legacy-пересборкой registry и quarantine с отдельным CAS; согласованную
публикацию правила, факта, analysis и связей выполняет `analysis-complete` через
`publish_transaction.py`. Скрипты не выполняют semantic matching: смысловые
`comparisons` и `action` приходят из `review.json`, а валидатор проверяет полноту,
evidence и допустимые relation. Подробности: [правило](../../../.agents/skills/business-analyst/references/storage.md#канон-и-интерфейс).

### 4.7 `render_rules.py`

Генерирует:

- `architecture/business-rules/index.md` только с действующими правилами;
- `architecture/business-rules/history.md` со всеми версиями;
- `architecture/business-rules/conflicts.md` только с неразрешёнными противоречиями;
- доменные страницы с блоком "Действует сейчас" и отдельной историей;
- строку `## Бизнес-правила` в `architecture/index.md`, если её нет.

Карточка содержит ID, версию, `valid_from`, короткий заголовок, подробное самостоятельное правило, задачи, код, тесты, тип, статус, `verified_at` и `evidence_ref`. Внутренние `conditions` в публичную карточку не выводятся. Сырые цитаты не выносятся.

### 4.8 `impact_rules.py` и `build_test_impact.py`

`impact_rules.py`:

- читает `diff.files.md`;
- читает `relations` задачи;
- находит active rules по `code_anchors` и `source_tasks`;
- пишет `test-matrix.json`.

`build_test_impact.py`:

- читает `test-matrix.json`;
- собирает существующие методы, Page/Step;
- если метода нет, ставит `gap=playwright`;
- пишет `test-plan.json`.

Ограничение: `test-task --impact` ещё не подключён к раннеру.

---

## 5. Hash-ledger

`state.json`:

```json
{
  "task_id": 2548,
  "last_snapshot_id": "...",
  "description": {"text_sha256": "..."},
  "comments": {
    "79674": {
      "text_sha256": "...",
      "processed_at": "...",
      "extractor_version": "v6",
      "prompt_hash": "...",
      "model": "agent",
      "candidate_ids": ["RC-2548-01"]
    }
  },
  "conditions": {
    "cond_sha256": ["RC-2548-01"]
  }
}
```

Правила:

- комментарий с тем же `text_sha256` не анализируется;
- условие с тем же `cond_sha256` не создаёт новый кандидат;
- изменение форматирования не меняет хеш после нормализации;
- изменение смысла меняет `text_sha256` и запускает delta;
- удалённый комментарий должен уводить правило в quarantine.

Проверка на 2548: второй запуск `extract` дал `cache_hit: true`, 0 новых
кандидатов.

---

## 6. JSONdoc contract

Изменения в JSONdoc:

- `document.schema.json`: добавлено свойство `business_logic`;
- `contract.py`: `business_logic` разрешён в `set` whitelist;
- `update.schema.json` и `document.schema.json`: actor `business-analyst`;
- `promote_rules.py` пишет `business_logic` через `Store.apply`.

Форма:

```json
{
  "business_logic": {
    "facts": [
      {
        "id": "BF-2548-01",
        "rule_id": "BR-ORD-001",
        "domain": "orders",
        "statement": "...",
        "conditions": [
          {
            "id": "C1",
            "type": "must",
            "text": "...",
            "code_anchors": [
              {"file": "lib/...", "symbol": "Class::method", "symbol_sha256": "..."}
            ],
            "test_refs": ["AC-04"]
          }
        ],
        "source_tasks": [2548],
        "evidence_ref": ".doc/skil_data/business-analyst/work/2548/candidates.json#RC-2548-01",
        "status": "verified",
        "verified_at": "...",
        "verified_by": "auto"
      }
    ],
    "linked_rule_ids": []
  }
}
```

---

## 7. Схемы

| Схема | Роль |
|---|---|
| `candidate.schema.json` | кандидат с цитатами и условиями |
| `verification.schema.json` | score, checks, result |
| `state.schema.json` | hash-ledger |
| `task-facts.schema.json` | только verified facts, без цитат |
| `registry.schema.json` | канон правил |
| `quarantine.schema.json` | причины и повторы |

Схемы этого списка описывают первоначальное ядро. Они не являются полной
спецификацией новых entities/links/analyses: актуальный контракт драйвера
проверяется его кодом и тестами, описан в
[storage.md](../../../.agents/skills/business-analyst/references/storage.md#канон-и-интерфейс).

---

## 8. Shadow и quarantine

Shadow:

```bash
python3 .agents/skills/business-analyst/scripts/auto_run.py --root . --task 2548 --shadow
```

Пишет `shadow-report.json`, не пишет `task.json` и registry.

Quarantine reasons:

- `low_score`;
- `missing_quote`;
- `not_atomic`;
- `no_anchor`;
- `conflict`;
- `duplicate_needs_merge`;
- `stale_source`;
- `pii_redacted`;
- `ambiguous`.

Неразрешённый смысл или отсутствие источника блокируют принятие зависимых
требований. Отсутствие кода может оставлять принятое будущее требование в
proposed/pending; такой статус не подтверждает реализацию. Успешная повторная
проверка закрывает запись, обоснованное отклонение сохраняется как rejected,
дубль связывается с существующим правилом. История не удаляется, next_check_at
сам по себе не запускает модель. Контракт: [карантин](../../../.agents/skills/business-analyst/references/storage.md#жизненный-цикл-карантина).

---

## 9. Code anchors

Anchor:

```json
{
  "file": "lib/src/Booking/SpecialistBookingService.php",
  "symbol": "SpecialistBookingService::confirmForPayment",
  "line_start": 405,
  "line_end": 470,
  "symbol_sha256": "...",
  "role": "implementation",
  "anchor_quality": "heuristic"
}
```

`symbol_sha256` считается по телу метода, а не по номеру строки. Это устойчивее
line hash. При переименовании или сдвиге строк якорь переразрешается.

---

## 10. Registry, snapshots, rollback

Registry:

```text
.doc/skil_data/business-analyst/registry.json
.doc/skil_data/business-analyst/registry.snapshots/000001.json
.doc/skil_data/business-analyst/registry.history.jsonl
```

Rollback:

```bash
python3 .agents/skills/business-analyst/scripts/business_analyst.py --root . rollback --last-good
```

Проверено на тестовой копии: registry вернулся к предыдущему snapshot.

Kill switch:

- `AUTO_PROMOTE=false`;
- `AUTO_AGGREGATE=false`;
- `AUTO_ACTIVE=false`.

Проверено: `AUTO_PROMOTE=false` не пишет task.json, `AUTO_AGGREGATE=false` не
обновляет registry.

---

## 11. gototask hook

В `gototask.ps1` после apply:

```text
business_analyst.py --root . analysis-prepare --task N
```

Хук только проверяет кэш и готовит вход. При needs_analysis/needs_review агент
выполняет task-business-analysis до планирования. Хук не публикует правила;
BUSINESS_ANALYST_PROMOTE не включает публикацию в новом хуке.

Отключается hook:

```text
BUSINESS_ANALYST_AUTO=0
```

PowerShell-парсер `gototask.ps1` проходит без ошибок.

---

## 12. Skill и rule

Skill `.agents/skills/business-analyst/SKILL.md`:

- триггеры: собрать бизнес-логику, обновить постулаты, impact, проверить код;
- режимы: sync, extract, anchors, verify, promote, aggregate, render, impact,
  test-impact, rollback, validate;
- правила: обязательная агентская сверка, вопрос человеку только для спорного
  требования, нет цитат в task.json, shadow для пилота низкоуровневого auto.

Rule `.cursor/rules/business-rules.mdc`:

- кандидаты вне задач;
- task.json только verified facts;
- hash-ledger;
- auto quarantine;
- code anchors и test matrix;
- запрет `--all` до пилота.

---

## 13. CLI и runbook

Проверка:

```bash
python3 .agents/skills/business-analyst/scripts/business_analyst.py --root . validate --task 2548
```

Shadow:

```bash
python3 .agents/skills/business-analyst/scripts/business_analyst.py --root . auto --task 2548 --shadow
```

Вход для полного бизнес-анализа задачи:

```bash
python3 .agents/skills/business-analyst/scripts/business_analyst.py --root . analysis-prepare --task 2548
```

needs_analysis/needs_review передаётся атомарному скилу. Низкоуровневый auto не
заменяет выполнение агента. Контекст готового анализа получают analysis-context;
точные аргументы: [фасад](../../../.agents/skills/business-analyst/docs/scripts/business_analyst.py.md#аргументы).

Массовый shadow с лимитами и продолжением:

```bash
python3 .agents/skills/business-analyst/scripts/auto_run.py --root . --all --changed-only --shadow \
  --max-tasks 20 --max-tokens 100000 --max-minutes 30 --resume
```

`auto_run.py` пишет `run/checkpoint.json` после каждой задачи и `run/failures.json`
при ошибках. `--resume` пропускает уже обработанные задачи из checkpoint.
Остановка по `--max-tokens` или `--max-minutes` сохраняет checkpoint и возвращает
`stopped` в отчёте.

Тесты:

```bash
python3 -m unittest discover -s .agents/skills/business-analyst/tests -v
```

---

## 14. Безопасность и retention

- email, телефоны, карты, секреты редактируются в `ba_common.redact_text`;
- `--redact-only` в плане, отдельный режим;
- `.doc` не коммитится;
- candidates и verification хранятся 365 дней;
- run.log 90 дней;
- task facts и registry бессрочно;
- браузерные тесты только dev/test.

---

## 15. Проверка и evidence

Проверки изменений 2026-11-09:

| Проверка | Результат |
|---|---|
| business-analyst unittest | 71 тест прошёл: драйвер, публикация, stable fact IDs, duplicate/refine, recovery, CAS, конкурентные записи и покрытие плана |
| JSONdoc unittest | 20 тестов `test_store.py` прошли после проверки owner-token lock и recovery |
| Markdown-план | `python3 .agents/skills/prepare-plan/tests/test_validate_plan.py` прошёл |
| gototask PowerShell | синтаксический разбор без Git/сети прошёл; переход к живой задаче не запускался |
| Аудит нового скила | passed, score 100 |
| Registry/rules/skills/docs | ошибок нет; остаются 6 предупреждений о legacy-документах и обязательных секциях сторонних скриптов |
| Sync/parity/visibility | passed |
| Живая задача 2077 | analysis-check вернул needs_analysis; старые правила и план не переутверждались |

Полный JSONdoc suite из корня проекта дал 7 ошибок импорта tests.support.
Повторный запуск из каталога компонента прошёл; продуктовый код ради запуска
не менялся. Следующие численные показатели относятся к историческому запуску
2026-10-30, повторно не измерялись и не доказывают текущую корректность правил.

- Unit/integration/contract тесты: 9, все зелёные.
- `validate_state.py --root .`: `ok: true`, 0 ошибок.
- Обработано 16 задач, 54 verified facts.
- Типы: 38 `business_rule`, 11 `technical_fact`, 5 `ui_rule`.
- Anchors: 40 exact, 14 partial, 0 missing.
- Тесты: 54 `planned`, автоматических привязок пока нет.
- Автоматический отчёт того запуска показывал 0 конфликтов; смысловая совместимость этим не подтверждена.
- `task.json` 16 задач заполнен `business_logic.facts`.
- Лента Jira в локальной панели обновлена из `tracker.json` и `task.md`: комментарии и changelog перенесены в `task.json tracker.snapshot`.
- В `report-model.json` добавлен `business_changes[]` из verified facts; панель и HTML показывают бизнес-слой до технических изменений.
- Публичные docs сгенерированы в `business-rules`, `technical-facts`, `ui-rules`.
- commit отклоняет цитаты, которых нет в источнике.
- Повторный prepare на неизменённой задаче даёт `cache_hit`.
- Promote проверен на копии задачи: JSONdoc применил `business_logic`.
- Rollback проверен на копии registry.
- Kill switch проверен.

---

## 16. Что осталось

| Пункт | Почему не сделано | Следующий шаг |
|---|---|---|
| Jira MCP adapter | сейчас tracker/task JSON | расширить MCP tools, pagination, changelog, clean text |
| `test-task --impact` | test-plan есть | передать матрицу в раннер Codeception/Playwright |
| `trace_path`, `get_file_outline` | `search_graph` закрывает якоря | подключать при необходимости путей вызовов |
| Пилот 20-30 задач | нет | shadow на задачах с возвратами QA |
| Golden set | нет | expected rules/quotes/anchors/tests |
| Массовый `--all` | риск качества | после пилота и калибровки |

---

## 17. Соответствие фазам плана

| Фаза | Статус | Evidence |
|---|---|---|
| 0. Схемы, ledger, защита | сделано | схемы, `validate_state`, локи, redaction |
| 1. Jira MCP | частично | `jira_sync.py` на tracker/task JSON |
| 2. Extractor + state | сделано | delta, cache hit, state |
| 3. Anchors + gototask | частично | anchors есть, gototask hook есть, CBM нет |
| 4. Auto verify + promote | сделано | score, shadow, quarantine, JSONdoc |
| 5. Aggregate + render | сделано | registry, snapshots, rollback, render |
| 6. Impact + tests | частично | matrix и plan, runner нет |
| 7. Batch pilot | не начато | - |
| 8. Golden set | не начато | - |

---

## 18. Известные ограничения

- JSON backend реализован; YAML/Graphiti явно отклоняются до реализации и миграции backend.
- `analysis-complete` использует общий publication journal для registry, task facts, links, quarantine, published-review и analysis. Recovery продолжает `prepared` вперёд по old/new hashes; прямые писатели в обход JSONdoc/BusinessStore остаются вне кооперативной гарантии.
- Словарь нового проекта заполняется агентом по источникам. Массовая индексация старых задач и исправление прежних правил не выполнялись.
- Полнота отчёта подтверждает обход очереди, но не безошибочность смыслового решения модели.
- Показатели partial/planned в следующих пунктах относятся к историческому запуску, актуальное количество не измерялось.

- Извлечение выполняет агент через `prepare` и `commit`; эвристики в Python нет.
- 14 anchors остаются partial: доменный класс или общий метод, а не точный метод.
- Все 54 теста имеют статус planned, реальные Cest/PHPUnit методы не привязаны.
- `test-plan.json` не запускает тесты.
- Нет golden set, поэтому precision/recall не измерены.
- Semantic matcher не реализован: `reconcile_rules` ранжирует структурные связи, а смысловые `action/comparisons` приходят из `review.json` от агента.
- Jira MCP adapter остаётся следующим шагом; CBM anchors подключены через `search_graph` с fallback на `rg`.
- У старых экспортов Jira нет `snapshot.comments/changelog`; для них нужен `backfill_activity.py` или повторный gototask.

---

## 19. Как расширять

1. Jira MCP: `jira_get_issue`, `jira_get_comments_delta`, `jira_get_changelog`,
   `jira_search_updated_since`.
2. CBM anchors: подключён `search_graph`; при необходимости добавить `trace_path` и `get_file_outline`.
3. LLM extractor: JSON schema, repair prompt, prompt hash в `state.json`.
4. `test-task --impact`: читать `test-plan.json`, выбирать Cest/Playwright.
5. Golden set: 20-30 задач с expected rules/quotes/anchors/tests.
6. Пилот: shadow на задачах с возвратами QA, затем калибровка порога.

---

## Связи

- [Атомарный анализ задачи](../../../.agents/skills/task-router/children/task-business-analysis/SKILL.md)
- [Хранение бизнес-знаний](../../../.agents/skills/business-analyst/references/storage.md)
- [Сверка правил агентом](../../../.agents/skills/business-analyst/references/reconciliation.md)

- [Точка входа харнеса](../index.md)
- [Скилы](./02-skills.md)
- [Рулесы](./03-rules.md)
- [Скрипты](./05-scripts.md)
- [JSONdoc](./06-jsondoc.md)
- [Workflows](./07-workflows.md)
- [План business analyst](../../buisnes_analis/plan.md)
- [Скил business-analyst](../../../.agents/skills/business-analyst/SKILL.md)
- [Правило business-rules](../../../.cursor/rules/business-rules.mdc)

---

## История изменений

- 2026-11-09: задокументированы единый драйвер JSON, справочник сущностей, типизированные связи задач, атомарный анализ и повторное использование, агентская сверка всей базы, карантин, закрепление требований в плане и результаты проверок. Исправлены устаревшие описания автопубликации и текстового поиска конфликтов; старые правила и планы не исправлялись автоматически.
- 2026-11-09: обновлена документация харнеса по текущему publication journal: analysis входит в транзакцию, recovery проверяет owner-token JSONdoc lock, facts используют stable candidate IDs, duplicate обрабатывается адресно, а semantic matching остаётся агентским решением.

- 2026-10-30: создан документ по реализованному ядру business-analyst v6: схемы, скрипты, hash-ledger, shadow, quarantine, JSONdoc, registry, rollback, impact, тесты и ограничения.
- 2026-11-08: подключены CBM anchors (`search_graph` с fallback на `rg`, фильтр классов-исключений, доменное ранжирование); добавлены `--max-tokens`, `--max-minutes`, checkpoint, resume и failures в `auto_run.py`; исправлен путь схемы в `test_contracts.py`.
