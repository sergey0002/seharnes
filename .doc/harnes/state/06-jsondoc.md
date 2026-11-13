# JSONdoc-движок

<!-- meta
type: architecture
status: actual
updated: 2026-11-10
related: [../index.md, ./05-scripts.md, ./07-workflows.md]
tags: [harness, jsondoc, batch, search]
-->

---

## Суть

JSONdoc - JSON-first хранение документации задач и архитектуры. `task.json` - канон
знаний, `doc.md` - generated view (ручная правка запрещена, `VIEW_CONFLICT`).
Архитектура аналогично: `{name}.json` - канон, `{name}.md` - view. Один CLI
`python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root .` для всех сред, без MCP-сервера
и БД. План `jsondoc.md` выполнен полностью (J00-J17), операционная сводка
`jsondoc.md` (канон, 2117 строк). Здесь рабочая выжимка команд и операционное состояние (перенесено из jsondoc-status.md, удален 2026-10-02).

---

## 1. Данные

- Задачи: `.doc/tasks/{N}/task.json` (178 папок, 176 с task.json; снято 2026-10-02). Плюс `task.md` (Jira-экспорт, не правится),
`doc.md` (view), `plan.md` и `stage*/plan.md` (view планов), `diff.md`, `diff.files.md`,
`test.md`, `ac-matrix.json`, `research-ledger.json`, `tests/`, `test-runs/`,
`reports/change-report/`, `_jsondoc/` (receipt, модели, верификации, миграции).
- Архитектура: `.doc/architecture/{name}.json` (50 доменных) плюс `{name}.md` (view).
`index.md` и `_priority.md` остаются навигационными MD.
- Словарь тегов: `.doc/skil_data/task-doc/state/tags.json`. Семь базовых доменов:
orders, payments, tariffs, deposition, auth, admin, frontend. Назначения тегов
задачам пока нет, это осознанная работа через `tags apply`, догадки запрещены.
- Конфиг: `.doc/skil_data/task-doc/state/config.json` (`mode: json` - JSON-first чтение включено).
- Состояние этапов: `.doc/skil_data/task-doc/state/execution.json` (J00-J17 passed).

Валидность JSONdoc для задачи: есть `task.json` и receipt `_jsondoc/receipt.json`.
Нет receipt или CLI недоступен - legacy fallback по `doc.md`.

---

## 2. Команды чтения

```bash
# Карточка документа или ключи
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --keys
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --select /summary --select /tags
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --task 2612 --select /findings --limit 3
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . get --arch orders --select /sections --record-id lifecycle

# Поиск
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --text "тариф" --limit 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --file lib/Objects/Order/OrderService.php --limit 10
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --tag domain:orders
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --release 5.6.1
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --branch "features/#2612"
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . search --kind task --release 5.6.1 --not-in origin

# Теги и связи
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . tags search --text "отмена" --fields label,description,aliases
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . related --task 2612 --profile discovery-v1 --limit 5
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . related --arch orders --profile legacy-v1 --limit 12
```

Фильтры `search`: `--text`, `--tag` с `--tag-mode all|any`, `--file`, `--release`,
`--branch`, `--tasks`, `--limit`. Default `limit=10`, `max_bytes=16384`.
Без select `get` возвращает карточку (id, revision, title, status, tags, counts),
не весь документ. Отсутствующий pointer - `FIELD_NOT_FOUND`, пустой массив - valid
empty, null - unknown. Неизвестный тег - ошибка, не пустой список.

Профили `related`:

- `discovery-v1` - по задаче: explicit relation 100, file overlap 40 за файл (cap 80),
общий arch 20 (cap 40), process tag 12 (cap 24), component 8 (cap 16), domain 3 (cap 6).
Связь только по тегу - `candidate=true`, не confirmed relation.
- `legacy-v1` - по arch-документу, байт-совместим с `find-related-tasks.ps1`:
TSV match 40 за файл, arch link 50, mention 20, code overlap min(30, 6 хитов),
already in arch 10. Сортировка score desc, id asc, default limit 8.

---

## 3. Пакетный режим batch

Один запуск выполняет до 20 read-вызовов на одном snapshot плюс опционально один
`apply`. Реализация `jsondoc/batch.py` (`MAX_CALLS=20`), CLI `jsondoc.py batch`,
тесты `tests/test_batch.py` BT01-BT04.

Допустимые calls: `get`, `search`, `related`, `stages`, `tags_search`.

Входной файл только под work-зоной:

- операция задачи: `.doc/tasks/{N}/_jsondoc/work/batch.json`;
- глобальная операция: `.doc/skil_data/task-doc/work/batch.json`.

Пример read-пачки:

```json
{
 "batch_id": "task-2612-preflight-01",
 "calls": [
 {"id": "keys", "command": "get", "args": {"task": "2612", "keys": true}},
 {"id": "pitfalls", "command": "get", "args": {"task": "2612", "select": ["/findings"], "limit": 3}},
 {"id": "stages", "command": "stages", "args": {"task": "2612"}},
 {"id": "rel", "command": "related", "args": {"task": "2612", "profile": "discovery-v1", "limit": 5}}
 ]
}
```

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . batch --input .doc/tasks/2612/_jsondoc/work/batch.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . batch --input .doc/skil_data/task-doc/work/batch.json --dry-run
```

Семантика:

- `calls` выполняются на одном snapshot, видят состояние до apply.
- `apply` - ровно один update envelope (6.3), после всех calls. Чтение после
записи - отдельным следующим batch.
- Ответ один envelope: `{status, batch_id, snapshot_revision, results, apply_summary}`.
Per-item `NOT_FOUND` и `FIELD_NOT_FOUND` - валидные результаты элемента, не валят batch.
- Batch без apply чисто read-only и безопасен к повтору. Batch с apply публикуется
одним `operation_id` и `expected_revision`, повтор того же payload - no-op.
- Структурная ошибка входа - exit 2 целиком без выполнения. Apply conflict -
стандартные коды в `apply_summary`, reads уже возвращены.

Когда использовать (3 и более операций - всегда batch):

- 3 и более точечных чтения одной задачи (`--keys` плюс findings плюс related плюс stages).
- search с точечным чтением топ-результатов по известным ID.
- Серия правок одним apply envelope.
- Preflight "прочитать контекст плюс сразу записать решение" - calls плюс apply.

Когда не использовать:

- Одиночная команда (оверхед входного файла больше выгоды).
- Итеративное исследование, где следующий запрос зависит от предыдущего результата.
- Чтение плюс запись, если write должен увидеть результат read из этой же пачки.

Типовые пачки по скилам (контракт `jsondoc.md` 9.4):

| Скил | Пачка | Apply |
|---|---|---|
| task-doc A (погружение) | `get --keys` плюс findings, relations, tags плюс stages плюс related discovery-v1 | нет |
| task-doc B (документирование) | повторное чтение изменений плюс apply findings, decisions, relations, files одним envelope плюс render | да |
| prepare-plan P0.5a | `related --arch legacy-v1` плюс `search --file` по Patches плюс `get` findings связанных | нет |
| prepare-plan финал | apply секций плана плюс T, AC, R, S плюс plan_hash | да |
| test-task финал | apply checks, test_run плюс status qa одним envelope | да |
| send-to-git финал | `ingest-git` плюс apply git_events плюс render | да |
| jira-report | `get` summary, findings, stages плюс apply `jira_report.text` плюс render | да |
| task-change-report | batch-чтение модели отчета одним конвертом | нет |
| doc-verify V6 | graph плюс `get` pitfalls, links | нет |
| gototask export | PHP экспорт, затем `ingest-tracker` | ingest, не apply |

Слово batch перегружено и не означает везде JSONdoc: indexing batch
(`get-indexing-batch.ps1`), verify batch (`get-verify-batch.ps1`), `test-batch.sh` -
разные механизмы.

---

## 4. Запись и ingest

```bash
# Шаблон и запись update envelope
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . template --kind task
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . apply --task 2612 --input .doc/tasks/2612/_jsondoc/work/update.json --dry-run
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . apply --task 2612 --input .doc/tasks/2612/_jsondoc/work/update.json
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . validate --task 2612 --links
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . render --task 2612
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . index refresh --changed
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . index check

# Jira-снимок строит экспортер, CLI только применяет
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-tracker --task 2612 --input .doc/tasks/2612/_jsondoc/work/tracker.json

# Git-проекция локальными read-only командами, без сети
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-git --task 2612
```

Actor единый enum: task-doc, project-doc, doc-verify, migration, user, gototask,
task-diff, send-to-git, ingest, agent-review. Actor фиксирует происхождение,
не заменяет разрешение пользователя.

Ops только `set`, `upsert`, `supersede`. Полная замена корня, массовое удаление,
смена id, revision, schema_version запрещены. Подтвержденные tags, resolved findings,
implemented decisions и passed checks требуют `source_ids`.

---

## 4a. business_logic

Для business-analyst в JSONdoc добавлена коллекция `business_logic`.

Изменения:

- `document.schema.json`: свойство `business_logic` с `facts[]` и `linked_rule_ids[]`;
- `contract.py`: `business_logic` разрешён в `set` whitelist;
- `update.schema.json` и `document.schema.json`: actor `business-analyst`;
- `promote_rules.py` пишет через `Store.apply` операцию `set business_logic`;
- `Store.load/apply/recover` соблюдают общий publication lock BusinessStore и
  возвращают `RECOVERY_REQUIRED` при pending BA-журнале;
- recovery JSONdoc удаляет только подтверждённый локальный orphan lock с
  отсутствующим PID; живой PID и другой host не удаляются.

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
            "code_anchors": [{"file": "...", "symbol": "...", "symbol_sha256": "..."}],
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
    "linked_rule_ids": ["BR-ORD-001"]
  }
}
```

Запрещены в facts: `quote`, `candidate`, `confidence`, `raw_text`, `comment_body`.
`ingest-tracker` не затирает `business_logic`: проверено на копии задачи.

Согласованная публикация `analysis-complete` включает `task.json` вместе с
registry, links, quarantine, published-review и analysis в журнал
`business-analyst/transactions/{id}`. JSONdoc сохраняет собственные revision,
receipt и operation_id внутри этого протокола.

## 5. Интеграция со скилами

- task-doc B: backend resolver, одна batch-update, render, index refresh плюс
прежний export TSV. Режиму A соответствует batch `keys` плюс findings плюс
related плюс stages вместо чтения `doc.md` целиком.
- gototask: после export-task `task.md` как раньше плюс `ingest-tracker` со снимком
статуса, релиза, автора, исполнителя. Экспорт через `.agents/skills/task-router/children/jira/scripts/server.php`, без
Jira API из python.
- task-diff: ingest свежих diff paths и hash после workflow, затем `ingest-git`.
- send-to-git: после подтвержденного push `ingest-git` для pushed_to и release_branches.
- prepare-plan: search discovery и sources из JSON, findings и stage refs в projection.
  План пишется как авторский `plan.md`, проверку выполняет `audit-plan`.
- find-related-tasks.ps1: сохраняет `-Doc`, `-Json`, `-Limit`, score и пороги.
JSON tags через opt-in профиль. Внутри fast path на `related legacy-v1`.
- build-tasks-index.ps1: сохраняет discovery и `-AlsoTsv`. Сначала MD-view как
раньше, затем adapter к catalog с golden parity.
- test-task и browser-verify: регистрируют существующий QA artifact и scope для ingest.
Матрицы и gates не заменяются JSON status.
- task-change-report: renderer роль `doc_json`. Валидный task.json - канон,
отсутствующий - legacy MD, поврежденный - ошибка без тихого fallback.
- git-task-blame и task-code-review: JSON discovery как дополнительный дешевый
контекст, не замена git line history.

Не заводить новый обязательный скил и второй рулес на каждый subcommand. Короткое
reference из существующих скилов ведет на спецификацию и CLI help.

---

## Живое состояние внедрения (26.09.2026, план jsondoc.md J00-J17 passed)

План `../jsondoc.md` (бывший `.doc/jsondoc.md`, перемещен 2026-10-02) выполнен полностью: этапы J00-J17 прошли гейты, состояние
в `.doc/skil_data/task-doc/state/execution.json` (next_stage: None). Операционная
сводка - этот документ (разделы ниже, перенесены из удаленного jsondoc-status.md).

- Задачи: 174 в JSON-first (120 полных task.json плюс 54 поисковых стаба; doc.md -
generated view, оригиналы в `_jsondoc/migrations`, rollback доступен).
- Архитектура: 50 доменных документов опубликованы через review-очередь
(submit плюс approve 50/50); `_priority` и index - навигационные MD.
- Планы: 126 legacy-планов и 57 стадий зарегистрированы. Новые планы пишет
`prepare-plan` как авторский `plan.md`; механического валидатора плана нет,
проверку выполняет `audit-plan`.
- Режим: config mode=json включен.
- Тесты: 183 теста в 16 модулях; PHP dual-output (task.md байт-в-байт плюс
tracker.json).
- Интеграция: gototask после экспорта вызывает ingest-tracker; send-to-git после
push - ingest-git; task-doc A/B работает через batch/apply при валидном task.json;
find-related-tasks.ps1 делегирует поиск связей в jsondoc related;
generate-doc-index.ps1 строит TSV прямо из JSON; validate_plan.py обслуживает
legacy MD-планы.

---

## Этапы J00-J17 с evidence (все passed, 2026-09-26)

| Этап | Содержание | Evidence |
|---|---|---|
| J00 | CLI `jsondoc.py`, selftest-раннер, execution state machine | runs/J00-003 |
| J01 | 4 схемы (document/tags/update/control), строгий contract-валидатор | runs/J01-005 |
| J02 | Store: CAS, exclusive lock, receipt, recover, идемпотентность operation_id | runs/J02-J05-reg-002 |
| J03 | Renderer: MD-view, VIEW_CONFLICT, байт-стабильность | там же |
| J04 | get/select/limit/cursor, coverage без скрытых пропусков | там же |
| J05 | Теги (aliases/parents/deprecation), discovery-v1 related, batch BT01-04 | runs/J05-batch-reg-003 |
| J06 | Стадии: active/next_actionable/next_allocatable, placeholder ST01-04 | runs/J06-J07-reg-003 |
| J07 | Stage-diff manifest на реальном git ST05-08, fixed argv | там же |
| J08 | ingest-tracker (Jira-снапшоты, пагинация JR01-05), ingest-git GT01-05 | runs/J08-reg-002 |
| J09 | Lossless-миграция: byte-spans, reconstruct, cutover UT19-22 | runs/J09-reg-004 |
| J10 | Review-очередь с lease/CAS (MG) | там же |
| J11 | legacy-v1 золотые веса PS1 плюс pwsh smoke плюс cwd-независимость | runs/J11-reg-003 |
| J12 | Freshness-проекции report/qa | runs/J12-reg-001 |
| J13 | PHP dual-output плюс gototask hook плюс скилы/rules плюс parity | runs/J13-reg-001 |
| J14 | Живые пилоты: задача 2612 и arch orders | runs/J14-pre-002 |
| J15 | Массовый перенос: задачи плюс архитектура | runs/jsondoc-all-01/* |
| J16 | Приёмка: полная регрессия, coverage, parity | runs/J16-accept-001 |
| J17 | Планы: регистрация 126 legacy; писатель новых планов снят 2026-11-10 | runs/J17-reg-001 |

Machine state: `.doc/skil_data/task-doc/state/execution.json` (`J00-J17 = passed`,
`next_stage: None`). Сводный прогон 186 тестов в 16 модулях (selftest --through J17)
плюс живые проверки вне unittest: PHP dual-export (docker php 7.1) и pwsh smoke
реального `find-related-tasks.ps1`.

## Совместимость харнеса (проверено при приемке)

| Компонент | Проверка | Результат |
|---|---|---|
| Зеркала 3 сред | verify_parity | passed |
| PHP экспортер | test-dual-export.php в docker: task.md байт-в-байт плюс tracker.json, повтор идемпотентен | PASS |
| gototask | Export-TaskMd вызывает ingest-tracker; сбой ingest не валит экспорт | ok |
| find-related-tasks.ps1 | живой прогон на generated orders view | работает, контракт сохранен |
| Правила | task-doc.mdc (режим B mixed), bitbucket-tasks.mdc (порядок чтения task.md -> task.json --keys -> diff) | обновлены, зеркала синхронны |
| task-doc SKILL B4 | запись через batch/apply при валидном task.json, иначе legacy | обновлен |
| send-to-git SKILL | финальный ingest-git после push | обновлен |
| validate_plan.py | legacy MD-планы | без изменений, работает |
| qa/scripts, docscripts PS1 | очереди/TSV не тронуты; J11 золотые веса | ok |

## Обработка внешнего аудита (внесено в план и код)

Принято и внесено в план (разделы 7, 5.2, 6, 8, 11.2a, 12): zombie-lock плюс
`doctor --force-unlock` политика, failpoint after view, сверка свежести по
data_sha256 (не mtime), `unmatched_branches` в git_state, неизменяемость профилей
весов (изменение весов = discovery-v2, не правка v1), команды doctor/view diff/
view import/lock status/upgrade, формулы UTF-8 лимитов, формат operation_id,
словарь next_action, AT04 стратифицированный пилот, encoding-классификация,
политика originals/rollback на другом хосте, RBAC-ноугол, русская морфология OUT,
UT27-UT41/IT17-IT19 выборочно.

## Правки второго внешнего аудита (2026-09-26)

1. Zone-изоляция архитектуры: `store._zone()` писал общий
   `architecture/_jsondoc/receipt.json` для всех 50 документов (данные только
   последнего) и общий lock. Исправлено на `_jsondoc/{stem}/`; 50 изолированных
   receipts пересобраны (operation_id `receipt-recovery-2026-09-26`); прежние общие
   файлы сохранены как `receipt.json.legacy-common` / `operations.json.legacy-common`.
2. Фатальный TypeError в `search --tag`: `resolve_tags(t)` вызывался без `docs`.
   Исправлено; пропуск теста tag-фильтра закрыт живой проверкой.
3. Словарь тегов: `state/tags.json` заполнен 7 базовыми доменами (orders, payments,
   tariffs, deposition, auth, admin, frontend); `--tag` работает (matched 0 честен:
   назначений тегов задачам нет).
4. Регресс после правок: полный unittest discover зеленый (176 тестов).

Принято, отложено (не блокеры, см. ограничения): `catalog.json` плюс
`index refresh/check` (поиск сканирует диск ~0.2с на 224 файлах, реализация индекса
по плану 11.3 отдельная задача); верхние CLI-обертки `stages`, `diff build/check`,
`tags apply`, `doctor`, `view diff/import/discard`, `lock status` (логика в модулях
есть, в парсер не вынесены, `stages` доступен через batch);
`implementation/Jxx/diff.md` снимки этапов не велись (stage.json с evidence есть).

## Откат

- Каждая публикация обратима: original в `_jsondoc/*/migrations/{run}/`, receipt
  связывает пару, `migrate rollback` реализован частично (восстановление вручную
  по staging при неизмененном view; автоматический rollback для live-архива по
  потребности, файлы на месте).
- Повторная миграция того же источника - no-op/duplicate, конфликты источника
  ловятся `MIGRATION_SOURCE_CHANGED`.

## Прочие известные ограничения

- `changelog_pages` в PHP dual-output пусты (embedded changelog без пагинации);
  JR-полнота changelog - будущая доработка экспортера.
- J17 изначально был blocked (переписка prepare-plan), закрыт в том же сеансе
  после реализации plan_writer; P7-аудит нового формата планов планом не требовался
  (формат проверяется тестами UT30-32).

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Скрипты](./05-scripts.md) - где лежит движок
- [Скилы задач](./02-skills.md) - потребители batch и ingest
- [Рабочие цепочки](./07-workflows.md) - место в цикле задачи
- [Контур планирования](./08-plan-contour.md) - авторский plan.md и аудит
- Нормативная спецификация: `../jsondoc.md` (канон движка: схемы, контракты, миграция, остается)

---

## Известные проблемы и ограничения

- Словарь тегов заполнен семью доменами, назначений задачам нет. `matched 0` честен.
- `catalog.json` и `index refresh/check`: поиск сканирует диск напрямую (~0.2s на
224 файлах). Реализация индекса - отдельная задача.
- Верхние обертки `stages`, `diff build/check`, `tags apply`, `doctor`, `view diff`,
`lock status`: логика в модулях есть, в парсер не вынесены.
- Arch `code_verified: false` у всех доменных: сверка с кодом не проводилась,
review опирался на roundtrip, контракт и структуру.
- 56 source_only задач не в JSON-поиске до первого документирования.

---

## История изменений

- 2026-10-01: вынесено из `readmy.md` в `.doc/harnes/`
- 2026-10-30: добавлена коллекция `business_logic`, actor `business-analyst`, интеграция с promote_rules.py.
- 2026-11-09: task JSONdoc подключён к общему BA publication lock; recovery безопасно обрабатывает только подтверждённый локальный orphan lock.
- 2026-10-02: аудит против кода: 178 папок задач (176 с task.json), batch MAX_CALLS=20 подтвержден, count помечен датой снятия
- 2026-11-10: убраны команды и упоминания писателя и валидатора JSON-плана. План ведёт `prepare-plan` как авторский `plan.md`, проверку выполняет `audit-plan`.
