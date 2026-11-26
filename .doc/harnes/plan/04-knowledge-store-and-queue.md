# Хранилище знаний и очередь работ

<!-- meta
type: plan
status: draft
updated: 2026-11-06
related: [../plan.md, ./deepseek.md, ./02-project-index-and-business-knowledge.md, ../jsondoc.md, ../state/17-business-analyst.md]
tags: [harness, knowledge, storage, queue, sqlite, json]
-->

---

## Суть

Документ задает форматы хранения и механику очереди для подсистемы сканирования
кодовой базы. Канонические утверждения, дефекты, сценарии и решения хранятся в
JSONdoc с CAS и журналом. Очередь, leases, coverage и поисковый индекс живут в
SQLite и всегда пересобираются из канона и источников.

Документ готов к внедрению: содержит схемы записей, DDL, правила claim,
восстановление после сбоя, миграцию текстовых очередей, CLI и приемочные тесты.
Код этим документом не меняется.

---

## 1. Решение в одном экране

| Объект | Хранилище | Формат | Источник истины |
|---|---|---|---|
| Claim, finding, scenario, decision, link | JSONdoc | Один JSON на запись, CAS, журнал | Да |
| Project manifest | JSONdoc или проектный файл | JSON | Да |
| Очередь, lease, retry, coverage | SQLite | Таблицы с WAL | Нет, производное |
| Поисковый индекс | SQLite FTS5 | Виртуальная таблица | Нет, производное |
| Domain docs, ER, state, flow | Markdown и Mermaid | Генерируемые views | Нет, производное |
| Evidence blob | Файловое хранилище проекта | JSON и вложения по hash | Да, если это исходное свидетельство |
| Run receipt | JSONdoc или файл receipt | JSON | Да, исторический результат |

Правило: канон не дублируется в SQLite. SQLite не является вторым источником
правды. Удаление SQLite не теряет знания.

---

## 2. Границы канона и производных данных

### 2.1. Канон

1. Утверждение бизнес-правила с областью действия.
2. Дефект с доказательством и статусом.
3. Сценарий проверки с oracle.
4. Решение владельца.
5. Связь между утверждением, кодом, таблицей, тестом и задачей.
6. Project manifest с identity проекта и adapters.

Канон проходит CAS по `expected_revision`, получает `operation_id` и попадает
в журнал JSONdoc. Ручная правка сгенерированного view запрещена.

### 2.2. Производные данные

1. Очередь работ.
2. Leases и heartbeat.
3. Счетчики покрытия.
4. Поисковый индекс FTS5.
5. Кеш evidence slice.
6. Проекции Markdown и Mermaid.

Производные данные можно удалить и пересобрать. Они не входят в экспорт
проектных знаний.

### 2.3. Что не хранить в SQLite

1. Полные тексты утверждений как единственную копию.
2. Секреты, токены, пароли и приватные ключи.
3. Сырые персональные данные.
4. Большие логи и transcripts.
5. Единственную копию evidence.

---

## 3. Идентификаторы

| Тип | Формат | Правило |
|---|---|---|
| Project | `prj_` + ULID | Создается при bootstrap, не меняется |
| Claim | `clm_` + ULID | Уникален в проекте, версия хранится отдельно |
| Finding | `fnd_` + ULID | Уникален в проекте |
| Scenario | `scn_` + ULID | Уникален в проекте |
| Decision | `dec_` + ULID | Уникален в проекте |
| Link | `lnk_` + ULID | Уникален в проекте |
| Evidence | `evd_` + sha256 | Хеш содержимого или нормализованного locator |
| Work item | `wrk_` + sha256(kind, scope_key, generation) | Детерминированный, защищает от дублей |

ULID дает сортировку по времени и не требует координации. Детерминированный
work ID важнее случайного: повторная постановка той же единицы в той же
generation не создает вторую запись.

Locator `file:line` не является постоянным ID. При переименовании файла
сохраняется alias старого locator и создается новый после проверки.

---

## 4. Схемы канонических записей

### 4.1. Project manifest

```json
{
  "schema": "harness.project/1",
  "project_id": "prj_01J...",
  "name": "example",
  "repo": {
    "vcs": "git",
    "root": "/path/to/repo",
    "remote": "origin",
    "default_branch": "main",
    "baseline_sha": "b0e9bf1"
  },
  "stack": {
    "languages": ["php", "javascript"],
    "frameworks": [],
    "package_managers": ["composer", "npm"],
    "runtime": "php7.1"
  },
  "commands": {
    "install": [],
    "build": [],
    "lint": [],
    "test": [],
    "run": []
  },
  "entrypoints": [
    {"kind": "http", "key": "admin/m_router.php", "source": "manual", "confidence": "high"},
    {"kind": "cron", "key": "m_cron.php", "source": "manifest", "confidence": "high"}
  ],
  "data_stores": [
    {"kind": "mysql", "identity": "main", "schema_source": "mysql", "confidence": "high"}
  ],
  "domains": [
    {"id": "orders", "name": "Заказы", "owners": []}
  ],
  "trust_boundaries": [
    {"id": "client", "description": "Кабинет клиента"},
    {"id": "admin", "description": "Админка"}
  ],
  "storage": {
    "canon": "jsondoc",
    "queue": ".doc/state/scan.db",
    "views": ".doc/architecture",
    "evidence": ".doc/knowledge/evidence"
  },
  "adapters": {
    "graph": "codebase-memory-mcp",
    "source": "codegraph",
    "symbols": "serena",
    "database": "mysql",
    "types": "phpstan-mcp",
    "security": "semgrep",
    "test_runner": "codeception",
    "browser": "playwright"
  },
  "generation": "gen_2026_11_06_01",
  "created_at": "2026-11-06T00:00:00Z",
  "updated_at": "2026-11-06T00:00:00Z"
}
```

Неизвестное значение помечается `null` или `unknown`. Запрещено подставлять
команду, endpoint или домен по догадке.

### 4.2. Claim

```json
{
  "schema": "harness.claim/1",
  "id": "clm_01J...",
  "version": 1,
  "kind": "business_rule",
  "title": "Возврат при отмене оплаченного заказа",
  "statement": "При отмене оплаченного заказа деньги возвращаются на лицевой счет клиента один раз.",
  "scope": {
    "domains": ["orders", "payments"],
    "actors": ["client", "admin"],
    "entities": ["order", "balance"],
    "entrypoints": ["order.cancel"],
    "state_predicate": "order.status = paid",
    "config_predicate": null,
    "revision_scope": "branch:main"
  },
  "status": {
    "intent": "approved",
    "implementation": "observed",
    "verification": "passed"
  },
  "confidence": 0.93,
  "evidence": [
    {
      "id": "evd_abc",
      "kind": "code",
      "locator": "lib/Objects/Order/OrderService.php:412",
      "source_hash": "sha256:...",
      "excerpt": "returnOrderToBalance(...)"
    },
    {
      "id": "evd_def",
      "kind": "test",
      "locator": ".doc/tasks/2077/tests/OrderCest.php:88",
      "source_hash": "sha256:..."
    }
  ],
  "links": {
    "symbols": ["lib.Objects.Order.OrderService.returnOrderToBalance"],
    "tables": ["order", "client_balance"],
    "scenarios": ["scn_01J..."],
    "findings": [],
    "tasks": [2077]
  },
  "exceptions": [],
  "provenance": {
    "source": "code",
    "extractor": "knowledge-extract/1",
    "model": "model-id",
    "prompt_hash": "sha256:...",
    "created_at": "2026-11-06T00:00:00Z"
  }
}
```

Три оси статуса независимы. `approved` требует decision ref и полномочий.
`passed` требует run receipt. `observed` не означает `approved`.

### 4.3. Finding

```json
{
  "schema": "harness.finding/1",
  "id": "fnd_01J...",
  "version": 1,
  "pass": "transactions",
  "severity": "S1",
  "confidence": "confirmed",
  "title": "Частичное списание при ошибке второго шага",
  "statement": "Списание баланса и создание заказа не входят в одну транзакцию.",
  "scope": {
    "domains": ["payments"],
    "entrypoints": ["payment.charge"],
    "symbols": ["PaymentService.charge"],
    "tables": ["client_balance", "order"]
  },
  "evidence": [
    {
      "kind": "code",
      "locator": "lib/Objects/Payment/PaymentService.php:210",
      "source_hash": "sha256:...",
      "excerpt": "updateBalance(); createOrder();"
    }
  ],
  "reproduction": {
    "kind": "test",
    "command": "codecept run unit PaymentServiceTest",
    "expected": "Баланс не меняется при ошибке создания заказа",
    "actual": "Баланс уменьшается, заказ не создан",
    "receipt": "run_2026_11_06_01"
  },
  "impact": "Потеря денег клиента при сбое второго шага.",
  "recommendation": "Обернуть оба шага в транзакцию и добавить compensation.",
  "fingerprint": "sha256:...",
  "status": "confirmed",
  "provenance": {
    "source": "audit",
    "pass_version": "1",
    "model": "model-id",
    "prompt_hash": "sha256:...",
    "created_at": "2026-11-06T00:00:00Z"
  }
}
```

### 4.4. Scenario

```json
{
  "schema": "harness.scenario/1",
  "id": "scn_01J...",
  "version": 1,
  "process": "order-cancel",
  "claim_ids": ["clm_01J..."],
  "title": "Отмена оплаченного заказа возвращает деньги один раз",
  "preconditions": [
    "Клиент авторизован",
    "Заказ в статусе paid",
    "Баланс клиента известен"
  ],
  "action": {
    "kind": "http",
    "entrypoint": "order.cancel",
    "input": {"order_id": 1}
  },
  "expected": [
    "Заказ переходит в canceled",
    "Баланс увеличивается на сумму заказа",
    "Повторная отмена не создает второй возврат"
  ],
  "state_after": [
    "order.status = canceled",
    "balance.delta = +amount"
  ],
  "layer": "acceptance",
  "oracle": {
    "kind": "claim",
    "ref": "clm_01J..."
  },
  "bindings": {
    "test_file": null,
    "test_method": null,
    "page": "OrderPage",
    "step": "cancelPaidOrder"
  },
  "status": "specified"
}
```

`oracle.kind`: `claim`, `decision`, `spec`, `observed`. `observed` не получает
статус `passing` без решения владельца, если утверждение нормативное.

### 4.5. Decision

```json
{
  "schema": "harness.decision/1",
  "id": "dec_01J...",
  "version": 1,
  "title": "Повторная отмена не возвращает деньги второй раз",
  "statement": "Повторная отмена уже отмененного заказа не создает второй возврат.",
  "scope": {"domains": ["orders", "payments"]},
  "authority": {
    "role": "business_owner",
    "identity": "owner-id",
    "basis": "decision-record-123"
  },
  "status": "approved",
  "effective_from": "2026-11-06",
  "links": {"claims": ["clm_01J..."]},
  "created_at": "2026-11-06T00:00:00Z"
}
```

### 4.6. Link

```json
{
  "schema": "harness.link/1",
  "id": "lnk_01J...",
  "from_ref": "clm_01J...",
  "relation": "implemented_by",
  "to_ref": "lib.Objects.Order.OrderService.returnOrderToBalance",
  "evidence_id": "evd_abc",
  "confidence": 0.9,
  "created_at": "2026-11-06T00:00:00Z"
}
```

Отношения: `implemented_by`, `tested_by`, `reads`, `writes`, `affects`,
`conflicts_with`, `supersedes`, `mentions`, `derived_from`.

### 4.7. Evidence

```json
{
  "schema": "harness.evidence/1",
  "id": "evd_abc",
  "kind": "code",
  "source": "git",
  "locator": "lib/Objects/Order/OrderService.php:412",
  "source_hash": "sha256:...",
  "excerpt_hash": "sha256:...",
  "redacted": true,
  "retention": "project-policy",
  "created_at": "2026-11-06T00:00:00Z"
}
```

Полный текст цитаты хранится только в разрешенной зоне. В публичную запись
попадает безопасная формулировка и ссылка.

---

## 5. SQLite: очередь и производный индекс

### 5.1. Требования к окружению

1. SQLite 3.35 или новее для `UPDATE ... RETURNING`.
2. WAL включен.
3. `busy_timeout` не меньше 5000 мс.
4. Один файл на проект.
5. Версия схемы хранится в `schema_migrations`.

Проверка версии:

```bash
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

Если версия ниже 3.35, используется транзакция `SELECT` + `UPDATE` с
проверкой `changes()`.

### 5.2. DDL

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_items (
  id TEXT PRIMARY KEY,
  generation TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN (
    'bootstrap', 'module', 'entrypoint', 'entity', 'integration',
    'pass', 'test', 'doc', 'revalidate'
  )),
  scope_key TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 100,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
    'queued', 'leased', 'running', 'blocked', 'done', 'failed', 'skipped', 'stale'
  )),
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  not_before TEXT,
  lease_owner TEXT,
  lease_until TEXT,
  depends_on TEXT NOT NULL DEFAULT '[]',
  payload TEXT NOT NULL DEFAULT '{}',
  result_ref TEXT,
  result_hash TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (generation, kind, scope_key)
);

CREATE INDEX IF NOT EXISTS idx_work_ready
  ON work_items(status, not_before, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_work_lease
  ON work_items(lease_until)
  WHERE status IN ('leased', 'running');

CREATE TABLE IF NOT EXISTS work_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_id TEXT NOT NULL REFERENCES work_items(id),
  event TEXT NOT NULL,
  worker TEXT,
  detail TEXT,
  result_hash TEXT,
  created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_work_events_dedupe
  ON work_events(work_id, event, result_hash)
  WHERE result_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS coverage (
  generation TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  axis TEXT NOT NULL,
  total INTEGER NOT NULL DEFAULT 0,
  covered INTEGER NOT NULL DEFAULT 0,
  gaps INTEGER NOT NULL DEFAULT 0,
  gap_reasons TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (generation, scope_key, axis)
);

CREATE TABLE IF NOT EXISTS knowledge_index (
  record_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  generation TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
  record_id UNINDEXED,
  kind UNINDEXED,
  title,
  body,
  tokenize = 'unicode61'
);
```

Все значения времени хранятся в UTC в формате ISO-8601. Сравнение строк
корректно только при одинаковом формате и часовом поясе.

### 5.3. Атомарный claim

```sql
BEGIN IMMEDIATE;

UPDATE work_items
SET status = 'leased',
    lease_owner = ?,
    lease_until = ?,
    attempts = attempts + 1,
    updated_at = ?
WHERE id = (
  SELECT id
  FROM work_items
  WHERE status = 'queued'
    AND (not_before IS NULL OR not_before <= ?)
  ORDER BY priority ASC, created_at ASC
  LIMIT 1
)
RETURNING *;

COMMIT;
```

Правила:

1. `BEGIN IMMEDIATE` берет write lock до чтения.
2. Один worker не может взять две единицы одной транзакцией.
3. `lease_until` выставляется на 5 минут; heartbeat продлевает.
4. `attempts` растет при каждом claim.
5. Если `attempts >= max_attempts`, единица переходит в `failed`.

Fallback без `RETURNING`:

```sql
BEGIN IMMEDIATE;
SELECT id FROM work_items
WHERE status = 'queued' AND (not_before IS NULL OR not_before <= ?)
ORDER BY priority, created_at LIMIT 1;
UPDATE work_items
SET status = 'leased', lease_owner = ?, lease_until = ?, attempts = attempts + 1, updated_at = ?
WHERE id = ? AND status = 'queued';
SELECT changes();
COMMIT;
```

### 5.4. Heartbeat и восстановление

Heartbeat:

```sql
UPDATE work_items
SET lease_until = ?, updated_at = ?
WHERE id = ? AND lease_owner = ? AND status IN ('leased', 'running');
```

Восстановление просроченных:

```sql
UPDATE work_items
SET status = 'queued',
    lease_owner = NULL,
    lease_until = NULL,
    last_error = 'lease expired',
    updated_at = ?
WHERE status IN ('leased', 'running')
  AND lease_until < ?;
```

Правило: worker, потерявший lease, не пишет результат. Перед записью он
проверяет `lease_owner` и `lease_until`.

### 5.5. Завершение и ошибка

Успех:

```sql
BEGIN IMMEDIATE;
UPDATE work_items
SET status = 'done', result_ref = ?, result_hash = ?, lease_owner = NULL, lease_until = NULL, updated_at = ?
WHERE id = ? AND lease_owner = ?;
INSERT INTO work_events(work_id, event, worker, result_hash, created_at)
VALUES (?, 'done', ?, ?, ?);
COMMIT;
```

Ошибка:

```sql
BEGIN IMMEDIATE;
UPDATE work_items
SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
    not_before = ?,
    last_error = ?,
    lease_owner = NULL,
    lease_until = NULL,
    updated_at = ?
WHERE id = ? AND lease_owner = ?;
INSERT INTO work_events(work_id, event, worker, detail, created_at)
VALUES (?, 'failed', ?, ?, ?);
COMMIT;
```

Backoff: 1, 5, 15 минут. После `max_attempts` единица остается `failed` до
ручного `retry` или изменения generation. Ручной `retry` сбрасывает `attempts`
в 0 и ставит новый `not_before`.

### 5.6. Идемпотентность

1. Work ID детерминирован.
2. Handler получает `operation_id = work_id + attempt`.
3. Запись канона идет через CAS и `expected_revision`.
4. Повторное завершение с тем же `result_hash` не создает новую версию.
5. `work_events` хранит историю; дубликат события с тем же `result_hash`
   игнорируется.

Повторная постановка уже завершенной единицы не создает вторую строку. Она
переводит существующую запись в `queued` и сохраняет историю:

```sql
INSERT INTO work_items (id, generation, kind, scope_key, priority, status, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
ON CONFLICT(generation, kind, scope_key) DO UPDATE SET
  status = 'queued',
  not_before = excluded.updated_at,
  updated_at = excluded.updated_at
WHERE work_items.status IN ('done', 'failed', 'skipped', 'stale');
```

Если единица в статусе `queued`, `leased` или `running`, повторная постановка
ничего не меняет. Это защищает от дублей при изменении одного файла несколько
раз.

### 5.7. Зависимости

`depends_on` хранит массив work IDs. Перед claim проверяется, что все
зависимости в статусе `done`. Если зависимость `failed`, единица получает
`blocked` с причиной. Циклы запрещены и проверяются при постановке.

### 5.8. Generation и stale

1. Generation меняется при смене extractor, schema, prompt или baseline SHA.
2. Новая generation создает новые work items; старые получают `stale`.
3. Reader по умолчанию читает только текущую generation.
4. Переключение generation атомарно: сначала завершаются критичные единицы,
   затем публикуется новая проекция.

---

## 6. Coverage

### 6.1. Оси

| Ось | Что считает |
|---|---|
| `inventory` | Файлы, entrypoints, таблицы, интеграции |
| `claims` | Области с извлеченными утверждениями |
| `scenarios` | Утверждения со сценариями |
| `tests` | Сценарии с исполняемыми методами |
| `docs` | Домены со свежими views |
| `findings` | Проходы, завершенные без дефекта или с дефектом |

### 6.2. Причины пробелов

```text
no_requirement
no_oracle
no_test
no_binding
not_executed
environment_mismatch
dynamic_link_unresolved
parse_failure
budget_exhausted
source_stale
not_applicable
```

Причины не сворачиваются в один процент. Отчет показывает каждую отдельно.

### 6.3. Запрос покрытия

```sql
SELECT axis, total, covered, gaps, gap_reasons
FROM coverage
WHERE generation = ? AND scope_key = ?
ORDER BY axis;
```

---

## 7. Поисковый индекс

1. `knowledge_index` хранит краткий текст записи.
2. `knowledge_fts` строится из `knowledge_index`.
3. Индекс пересобирается при изменении записи.
4. Полнотекстовый поиск не заменяет смысловой; embeddings не входят в первую
   версию.
5. Если позже понадобится vector search, используется `sqlite-vec` как
   производный индекс, не как канон.

Запрос:

```sql
SELECT record_id, kind, title
FROM knowledge_fts
WHERE knowledge_fts MATCH ?
ORDER BY rank
LIMIT 20;
```

---

## 8. Файловая раскладка

```text
.doc/
  state/
    scan.db
    scan.db-wal
    scan.db-shm
  knowledge/
    project.json
    records/
      claims/{claim_id}.json
      findings/{finding_id}.json
      scenarios/{scenario_id}.json
      decisions/{decision_id}.json
      links/{link_id}.json
    evidence/
      {evidence_id}.json
    receipts/
      {run_id}.json
    projections/
      domains/
      er/
      states/
      flows/
  architecture/
    business-rules/
    domains/
```

Правила:

1. Один JSON на запись. Это дает независимый CAS и читаемый diff.
2. Для массового экспорта допускается JSONL, но он не является каноном.
3. `projections/` можно удалить и пересобрать.
4. `scan.db` можно удалить и пересобрать.
5. Evidence с секретами не попадает в versioned export.

---

## 9. CLI

Единая точка входа: `knowledge`.

```bash
knowledge init --repo . --name example
knowledge scan enqueue --kind module --scope lib/Objects/Order --priority 10
knowledge scan claim --worker worker-1 --lease 5m
knowledge scan heartbeat --id wrk_... --worker worker-1 --lease 5m
knowledge scan complete --id wrk_... --worker worker-1 --result run_123
knowledge scan fail --id wrk_... --worker worker-1 --error "parse failed"
knowledge scan status --generation gen_...
knowledge scan retry --id wrk_... --not-before 5m
knowledge scan gc --older-than 30d

knowledge claim list --domain orders --status approved
knowledge claim get clm_...
knowledge finding list --severity S0,S1 --status confirmed
knowledge scenario list --claim clm_...
knowledge scenario bind scn_... --test-file ... --test-method ...
knowledge coverage report --generation gen_...
knowledge render --generation gen_...
knowledge rebuild --from-json --generation gen_...
knowledge export --safe-only --out ./knowledge
```

Коды выхода:

| Код | Значение |
|---|---|
| 0 | Успех |
| 1 | Ошибка валидации |
| 2 | Конфликт CAS или lease |
| 3 | Неизвестный проект или generation |
| 4 | Нарушение политики безопасности |
| 5 | Бюджет исчерпан, создан gap |

---

## 10. Provider interface

```python
class QueueProvider:
    def enqueue(self, item) -> str: ...
    def claim(self, worker_id, lease_seconds) -> dict | None: ...
    def heartbeat(self, work_id, worker_id, lease_seconds) -> bool: ...
    def complete(self, work_id, worker_id, result_ref, result_hash) -> bool: ...
    def fail(self, work_id, worker_id, error) -> bool: ...
    def release_expired(self, now) -> int: ...
    def status(self, generation) -> dict: ...
```

Первая реализация: `SQLiteQueueProvider`. Позже допускаются
`PostgresQueueProvider` и `TemporalProvider` без изменения вызовов скилов.

---

## 11. Почему не текстовые очереди

| Текущий механизм | Проблема |
|---|---|
| `current-batch.txt` | Нет atomic claim и статуса |
| `current-verify-batch.txt` | Нет lease и восстановления |
| `verify-registry.tsv` | Нет retry, приоритета и dead-letter |
| `state.json` business-analyst | Хорош для hash-ledger, не для конкурентных worker |

Миграция:

1. Прочитать текущие очереди.
2. Создать work items с deterministic ID.
3. Сохранить старые файлы как read-only архив.
4. Переключить скрипты на provider.
5. Удалить запись в старые очереди после успешной миграции.

---

## 12. Альтернативы и решение

| Вариант | Плюсы | Минусы | Решение |
|---|---|---|---|
| SQLite | Нет сервера, ACID, WAL, один файл, переносимый | Один хост, ограниченная конкурентность | Берем в первой версии |
| Postgres `SKIP LOCKED` | Много worker, надежность | Нужен сервер и администрирование | Provider позже |
| Temporal | Durable workflows, human approvals | Тяжелая инфраструктура, сложность | Только при нескольких хостах |
| BullMQ, Redis | Готовые очереди, много worker | Нужен Redis, меньше переносимости | Не берем |
| Celery, RQ | Экосистема Python | Брокер, сложность, не атомарный канон | Не берем |
| Файлы и TSV | Просто | Нет claim, lease, retry | Заменяем |

Вывод: SQLite дает максимум надежности при нулевой инфраструктуре. Внешний
брокер добавляется только по измеренной потребности.

---

## 13. Безопасность и retention

1. Evidence проходит redaction до записи.
2. Секреты и токены заменяются на `[redacted]`.
3. Полный источник хранится по ссылке и hash, а не копией в публичной зоне.
4. `knowledge export` по умолчанию исключает restricted evidence.
5. Retention задается project manifest.
6. Удаление записи фиксируется в журнале JSONdoc.
7. SQLite не содержит секретов и полных персональных данных.
8. Доступ к очереди и канону разделяется по ролям проекта.

---

## 14. Приемочные тесты

| Тест | Ожидание |
|---|---|
| Round-trip claim | Запись и чтение не меняют поля |
| CAS conflict | Вторая запись с устаревшей ревизией отклонена |
| Two workers | Одна единица выдана ровно одному worker |
| Kill -9 | Просроченный lease возвращен в очередь, дубль не создан |
| Retry | После трех ошибок статус `failed`, событие записано |
| Stale generation | Старые items не выдаются по умолчанию |
| Wrong project | Запрос чужого project_id отклонен |
| Corrupted db | `rebuild` восстанавливает индекс из канона |
| Redaction | Секрет не попадает в evidence и export |
| Budget | При исчерпании бюджета создан gap, статус не `done` |
| Coverage | Каждая ось считается отдельно, причины не смешиваются |
| FTS | Поиск находит claim по statement и title |

---

## Связи

- [Мастер-план сканирования и аудита](./deepseek.md) - цели, методология, фазы.
- [Индексация и база бизнес-знаний](./02-project-index-and-business-knowledge.md) - identity, три оси, lifecycle.
- [Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md) - finding contract и pass library.
- [JSONdoc](../jsondoc.md) - CAS, журнал, render, receipts.
- [Business analyst](../state/17-business-analyst.md) - текущие зоны хранения и ограничения.
- [Скрипты](../state/05-scripts.md) - текущие текстовые очереди.

---

## Известные проблемы и ограничения

Схемы и DDL являются проектом. Перед внедрением нужны миграция существующего
registry, проверка версии SQLite и crash-тесты на реальном проекте. SQLite
подходит для одного хоста; несколько хостов требуют Postgres или Temporal
provider. Полнотекстовый индекс не заменяет смысловой поиск. Redaction
снижает риск утечки, но не заменяет проектную политику данных.

---

## История изменений

- 2026-11-06: создан документ хранения и очереди. Зафиксированы JSONdoc-канон, SQLite-производное состояние, DDL, claim, lease, retry, recovery, coverage, CLI, миграция текстовых очередей и приемочные тесты.

#harness #storage #queue #sqlite #json #knowledge
