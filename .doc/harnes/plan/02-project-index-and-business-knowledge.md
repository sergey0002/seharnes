# Индексация проекта и проверяемая база бизнес-знаний

<!-- meta
type: plan
status: draft
updated: 2026-11-06
related: [../plan.md, ./deepseek.md, ./01-subagent-planning-and-audit.md, ./03-web-testing-system.md, ./04-knowledge-store-and-queue.md, ./05-bug-hunt-and-modernization.md, ../state/17-business-analyst.md]
tags: [harness, indexing, business-logic, testing]
-->

## Суть

План выделяет отдельную систему знаний проекта: карта кода, документация, бизнес-утверждения и карта тестовых сценариев. Агент получает короткий релевантный срез, проверяет исходники и добавляет знания с происхождением и областью действия. Код, требования и результаты тестов остаются разными видами свидетельств.

Результат внедрения: вопрос без задачи работает без Jira; изменение правила инвалидирует связанные знания и тестовые результаты; планировщик получает проверяемые ограничения; тестовый дизайнер получает бизнес-процесс, роли, состояния и независимый ожидаемый результат. Проектные знания никогда не переносятся вместе с универсальным харнесом.

Документ развивает [общий план, разделы 8 и 12](../plan.md#8-исследование-большой-кодовой-базы). Это проектируемые изменения, а не описание уже работающей системы. Код и настройки текущим документом не меняются.

## 1. Границы и определения

| Объект | Назначение | Чего объект не доказывает |
|---|---|---|
| Карта проекта | Языки, модули, входы, команды проверки и границы доверия | Полноту бизнес-требований |
| Структурный граф | Символы, вызовы, импорты, маршруты и зависимости | Все динамические вызовы и реальное runtime-поведение |
| Индекс документации | Разделы, ссылки, термины и поиск по текстам | Актуальность утверждения относительно кода |
| Бизнес-утверждение | Требование или наблюдаемое свойство с областью и свидетельствами | Истину только по наличию цитаты или якоря |
| Карта сценариев | Процессы, роли, состояния, cases и привязки к тестам | Успешный запуск привязанного метода |
| Результат проверки | Выполнение конкретных cases на известных входах | Корректность другого дерева, окружения или конфигурации |

Oracle означает источник ожидаемого результата теста. Evidence означает проверяемое свидетельство: решение, фрагмент исходника, схема, трасса или результат исполнения. Claim означает атомарное утверждение, которое evidence поддерживает либо опровергает.

CI/CD принадлежит проекту. Харнес получает разрешенные команды проверки через проектный adapter, но не переносит и не переписывает deployment pipeline. База знаний описывает процесс; полномочия выполнять операции задаются отдельно.

## 2. Что уже существует и почему нужна переработка

Сохранить JSONdoc: CAS по `expected_revision`, `operation_id`, журнал, блокировку и атомарную запись модели. Сохранить hash-ledger, shadow, карантин, генерируемые представления и разделение короткого факта с полным evidence. Основание: [JSONdoc store](../../../.codex/skills/documentation-router/children/task-doc/scripts/jsondoc/store.py), начало файла и методы `apply/recover`.

| Подтвержденное наблюдение | Где проверено | Изменение |
|---|---|---|
| CLI импортирует отсутствующий `test_impact` вместо существующего `build_test_impact` | `business_analyst.py:18`, `auto_run.py:18` | Исправить входы и добавить subprocess smoke до новых возможностей |
| Business unittest: 22 теста, 21 passed, 1 ERROR старого пути | `tests/test_contracts.py:14` | Разрешать пути единым resolver; тестировать реальный CLI |
| Противоположные statement и quote получили score 1.0 и `verified` | `verify_rules.py:40-54,76-136`; искусственная фикстура аудита | Структурную проверку отделить от подтверждения смысла и поведения |
| `deprecate` при неизменном тексте оставляет правило active | `aggregate_rules.py:250-298`; искусственная фикстура | Lifecycle-событие применять независимо от изменения текста |
| Существующий anchor пропускается без проверки hash тела | `resolve_anchors.py:260-261` | Проверять актуальность зависимостей перед повторным использованием |
| Дата задачи или mtime становятся датой действия правила | `aggregate_rules.py:101-130,167-172` | Развести даты источника, записи и действия |
| Ссылка на метод считается покрытием | `ba_common.py:144-150`, `build_test_impact.py:35-49` | Разделить reference, existence, applicability и execution |
| Каждый extraction input получает все active rules | `extract_rules.py:110-139` | Ограниченный поиск по домену, identity, scope и конфликтам |

Эти проверки не обнаруживали реальные ошибочные выплаты или выдачу прав. Фикстуры демонстрируют поведение функций харнеса. Подробный исходный разбор и ограничения: [общий план, раздел 4.2](../plan.md#42-бизнес-правила).

## 3. Источники правды и производные индексы

### 3.1. Что хранить канонически

1. Исходники и versioned тесты остаются в Git проекта; харнес не создает вторую редактируемую копию кода.
2. Tracker export хранится как неизменяемый snapshot с идентификатором и revision. Локальное принятое решение имеет собственную запись и автора.
3. Нормализованные claims, решения об утверждении, связи и lifecycle-события хранятся через общий JSONdoc storage.
4. Результаты запусков хранятся как неизменяемые run receipts; обновление сводки не переписывает исторический результат.
5. Project manifest задает источники, домены, команды, разрешенные среды и место данных. Значения другого проекта не подставляются по умолчанию.

### 3.2. Что можно пересобрать

| Производный объект | Источники | Условие повторного использования |
|---|---|---|
| Code graph provider | Исходники, конфиги, параметры индексатора | Совпадает project identity; известны generation, coverage и свежесть |
| Индекс jdocmunch | Авторские docs или сгенерированные views | Section hash сопоставим с источником; stale view явно обозначен |
| Domain registry projection | Канонические claims, версии, решения | Совпадает опубликованная model generation |
| Reverse dependency map | Evidence links и структурные связи | Известны версии extraction/schema и unresolved edges |
| Test-flow map | Scenario contracts, runner discovery, Page/Step bindings | Различены обнаруженный метод и исполнившийся case |
| Markdown-энциклопедия | Domain projection | View receipt соответствует модели; иначе `stale_view` |

Сбой графа или поискового индекса не удаляет канонические claims. Потеря view исправляется пересборкой. Потеря канонического evidence требует восстановления из журнала или источника.

### 3.3. Где размещать новые данные

Расширять существующий JSONdoc и реестр бизнес-аналитики. Новый storage API задается `knowledge list/get/apply/related/rebuild`, но использует существующие CAS, журнал и renderer. Создание отдельной БД, vector store или второго event framework в первой версии исключено.

Очередь работ, leases и coverage хранятся в SQLite как производное координационное состояние. Канон утверждений остается в JSONdoc, SQLite не является вторым источником правды. Схема, DDL и правила восстановления: [Хранилище знаний и очередь работ](./04-knowledge-store-and-queue.md).

Project manifest хранит `knowledge_store_ref` и `knowledge_projection_dir`. Для CopyTrust adapter начинает с текущих `.doc/skil_data/business-analyst/` и `.doc/architecture/business-rules/`; новые смысловые поля добавляются совместимо. Эти пути не становятся универсальными константами core.

Полный quote и snapshot остаются в evidence storage. Краткий task/work view содержит claim ID, статус и evidence ref. Один факт не редактируется независимо в task.json, registry.json и Markdown: задается один канонический record, остальные документы содержат ссылки или генерируемые проекции.

### 3.4. Долговечные знания и локальные данные

Текущий `.doc/` попадает под ignore проекта. Поэтому действующие approved facts, oracle contracts, scenario definitions и regression maps нельзя оставить единственной копией в локальной ignored-зоне. Project profile выбирает `versioned_knowledge_sources`: точечно отслеживаемые файлы `.doc` либо отдельный versioned каталог проекта. Решение о месте и составе принимает проект; этот план не меняет `.gitignore`.

Versioned knowledge содержит безопасный воспроизводимый смысл, schema и ссылки на разрешенные источники. Raw tracker exports, персональные данные, credentials, browser sessions, большие transcripts, временные receipts и caches остаются в локальной ignored/redacted-зоне по project retention policy. Если исходный quote закрыт, versioned record хранит безопасную формулировку и проверяемый restricted evidence ref, не публикует quote в Git.

Перед передачей source slice любой модели проверяется project data-egress policy, включая разрешенный provider, redaction и retention. Допуск дешевой модели к extraction не разрешает отправить закрытый проект другому endpoint. Trust boundary evidence/instructions и модельный fallback определены в [документе 01, раздел 8.5](./01-subagent-planning-and-audit.md#85-разрешение-на-передачу-данных-модели).

Проверка долговечности: чистый разрешенный checkout восстанавливает approved rules, oracle и scenario contracts из versioned sources; локальные кеши для этого не нужны. Повторная верификация создает новые receipts. Секреты и raw данные не становятся частью переносимого kit.

### 3.5. Переносимость без смешения проектов

При экспорте харнеса разрешены schemas, generic CLI, extractor contracts, adapters templates и обезличенные fixture examples. Запрещено переносить source project claims/registry, задачи, private docs, графы кода, role mappings, endpoints, fixtures клиентов, sessions и receipts. Целевой проект получает пустой knowledge namespace, собственный ontology profile и новую индексацию.

Версионирование знаний внутри проекта не делает эти знания переносимыми между проектами. Одинаковые RuleRef labels разных проектов не разрешают общий retrieval. Общая библиотека или submodule связывается явным repository/dependency ref; свидетельства другого проекта не импортируются по сходству имени.

## 4. Identity, онтология и область действия

### 4.1. Устойчивые идентификаторы

```text
ProjectRef = stable project_id + repository identities
WorktreeRef = project_id + worktree_id + baseline + dirty-tree fingerprint
SourceRef = source_kind + source_id + revision/hash + location
RuleRef = project_id + rule_id + semantic_version
ScenarioRef = project_id + scenario_id + contract_version
CaseRef = scenario_id + stable case_id
LinkRef = link_id + from_ref + relation + to_ref + evidence_ref
```

Путь и номер строки служат locator, но не постоянным ID. Переименование файла сохраняет alias старого locator и устанавливает новый после проверки. Одинаковые номера задач из разных tracker projects не совпадают. Неизвестный provider возвращает ошибку разрешения, а не догадку.

### 4.2. Доменная онтология проекта

`project-setup` предлагает словарь из entrypoints и существующих docs: домены, сущности, роли, состояния, действия и внешние системы. Владелец проекта принимает или исправляет словарь. Маленький проект начинает с плоского словаря; сложная таксономия заранее не требуется.

Синонимы помогают retrieval, но не объединяют правила автоматически. Два похожих названия роли могут иметь разные права. CopyTrust-словарь orders/payments/tariffs и PHP-каталоги переносятся в CopyTrust adapter.

### 4.3. Область утверждения

Claim хранит `actors`, `entities`, `entrypoints`, `state_predicate`, `config_predicate`, `revision_scope` и известные `effective_from/to`. Для простого утверждения допустима короткая ссылка на scope record. Неизвестная область отмечается `unknown`.

Нормативная версия правила и ревизия кода различны. Одно правило проверяется в нескольких ветках; одна ветка содержит разные конфигурации. Более свежая дата задачи не отменяет старую действующую версию на другой поддерживаемой ветке.

`source_timestamp` показывает время исходного сообщения; `recorded_at` показывает время приема; `effective_from/to` показывает действие только при наличии основания. Filesystem mtime не заполняет effective date.

## 5. Три независимые оси достоверности

| Ось | Статусы | Основание перехода |
|---|---|---|
| `intent_status` | unknown/proposed/approved/conflicted | Принятое решение уполномоченного владельца в известном scope |
| `implementation_status` | unknown/observed/divergent/stale | Проверенный исходник, runtime evidence и сопоставление с требованием |
| `verification_status` | untested/specified/passed/failed/blocked/stale | Контракт и фактически выполненные cases на совпадающих входах |

Скрипт проверяет форму, quote, hash и существование символа. Semantic reviewer проверяет, следует ли statement из источника. Ни один из этих шагов не присваивает бизнес-полномочия модели.

Для `approved` обязательны decision ref, author identity, authority basis, scope и revision решения. Проектный adapter описывает уполномоченные источники. Если полномочия неизвестны, сохранить proposed и запросить решение только когда неопределенность влияет на изменение.

Согласие реализовать технический план не означает автоматического утверждения всех извлеченных бизнес-постулатов. Совпадение ответов трех моделей не заменяет принятое решение.

Старые `verified` мигрируются в `legacy_structural` с исходным receipt. `source_validated` выставляется после проверки snapshot/quote; поведенческая ось остается untested без результата исполнения. История не переписывается задним числом.

## 6. Первичная индексация без полного чтения репозитория

### 6.1. Первый полезный пакет

1. Resolver устанавливает project root, repository identity, worktree, языки и профиль доступа.
2. Читается manifest и карта документации; отсутствующие данные обозначаются, а не выдумываются.
3. Для кода сначала используется доступный граф: `list_projects` -> project-scoped status -> архитектура/entrypoints -> bounded symbol search.
4. Для документации jdocmunch ищет нужный корпус и возвращает headings/sections; весь корпус не загружается.
5. Скрипт строит стартовую карту доменов и unresolved boundaries, не извлекая бизнес-смысл из каждого метода.
6. Выбираются два критичных процесса для пилота: доступ/внешние эффекты либо деньги/состояния по профилю проекта.
7. Агент проверяет релевантные пути от entrypoint до эффектов и связывает требования, код и тесты.
8. Публикуется карта покрытия с пробелами. Остальные домены пополняются по worklist и запросам.

### 6.2. Когда расширять исследование

Shared defaults, публичные сигнатуры, разрешения, транзакции, конкуренция, time/retry и внешние эффекты требуют проверки IN/OUT потребителей. Для callbacks, DI, событий, cron и шаблонов граф дополняется targeted text search, конфигами и разрешенными runtime probes.

Пустой результат неполного графа означает coverage gap. Второй граф вызывается для конкретного неразрешенного вопроса, не как обязательное повторение первого. Schema подтверждается разрешенным schema provider; выдуманные таблицы запрещены.

Onboarding не запускает миграции, запись в БД, browser impersonation и внешнюю публикацию. Эти действия требуют отдельных project permissions.

## 7. Извлечение кандидатов из разных источников

| Источник | Что извлекать | Что сохранить отдельно |
|---|---|---|
| Задачи и решения | Требования, исключения, изменения правил | Предложения, отмененные решения, статус принятия |
| Код | Guards, calculations, state transitions, эффекты и ограничения | Наблюдение реализации без приписанного бизнес-намерения |
| Документация | Описанные процессы, термины, контракты | Актуальность, авторитет источника и расхождения с кодом |
| Тесты | Existing scenarios, fixtures, assertions и oracle refs | Наличие теста, результат запуска и возможное закрепление бага |
| Runtime probes | Конкретное поведение входа/состояния | Ограниченный scope, окружение и воспроизводимость |

### 7.1. Контракт extract-input

Скрипт выдает `work_id`, `source_snapshot_set_id`, `read_set_hash`, `expected_model_revision`, `schema_version`, `extractor_version`, `prompt_version`, bounded source slices, related rule refs, unresolved questions и output schema. Для каждого среза указаны hash, locator, роль и признак усечения. `projection_generation` обозначает версию производного индекса; она не подменяет source snapshot или CAS-ревизию модели.

Малая модель формулирует candidate statement, условия, scope, evidence refs и предполагаемые связи. Модель не пишет active registry, не меняет нормативные ожидания и не скрывает неизвестные условия.

### 7.2. Независимая проверка

1. Детерминированно проверить schema, допустимые refs, точные quotes, hashes и принадлежность проекту.
2. Проверить candidate input snapshot и актуальность относящегося к нему read-set. Несовпадение дает `stale_input`; CAS-ревизия записи проверяется отдельно и не доказывает свежесть кода или Jira.
3. Проверить entailment: цитата или source range действительно поддерживает statement, включая отрицания и исключения.
4. Проверить конфликт с близкими правилами в пересекающемся scope; недостающий конфликтный срез запросить отдельно.
5. Для high-risk semantics использовать независимого reviewer с доступом к исходникам. Экономная модель остается автором кандидата, не единственным арбитром истины.
6. Сохранить результат проверки, ограничения и evidence. Не присваивать поведенческий passed без запуска.

Budget превышен или источник неоднозначен: candidate остается quarantined/needs_review. Отсутствие модели не запускает эвристическое выдумывание правил.

## 8. Инкрементальность, CAS и публикация

### 8.1. Changed-only worklist

Collector объединяет Git changes, dirty/untracked files, tracker deltas, docs changes, schema/config fingerprints и изменения test contracts. Worklist содержит уникальные SourceRef и причины переоценки. Полный обход истории на каждый вопрос исключен.

Reverse edges связывают источник с claims, rules, scenarios, packets и результатами. Изменение зависимости делает потребителей stale; неизменные независимые домены не перечитываются. Изменение extractor/prompt/schema version допускает целевую переоценку даже при том же text hash.

### 8.2. Rename, delete и потерянные источники

- Rename: проверить содержимое/символ, обновить locator, сохранить alias и историю; сходство имени недостаточно.
- Delete: записать tombstone и инвалидировать текущую опору; исторический snapshot не удалять.
- Удаленный комментарий: source evidence становится withdrawn/stale; нормативное решение не отменяется автоматически без проверки полномочий и более поздних решений.
- Измененный quote: старое evidence остается историческим, новое извлечение привязано к новой ревизии.
- Недоступный источник: состояние unknown/unreachable с причиной, без ложного утверждения об удалении.

### 8.3. Граница транзакции

1. Worker получает lease на worklist item и фиксирует source snapshot/read-set и expected model revision отдельно.
2. Worker собирает candidate и proof; каждый output содержит input hashes.
3. Writer повторно проверяет read-set и CAS. Конфликт возвращает item в очередь, не затирает чужую запись.
4. JSONdoc атомарно сохраняет model update, operation ID и journal receipt относительно expected model revision. Запись указывает captured source snapshot, а не обещает глобальную транзакцию с Git/Jira.
5. Projection builder строит новую generation во временной зоне и публикует manifest последним.
6. Renderer записывает view receipt. При ошибке модель сохраняется, view получает stale и план восстановления.

Два worker не получают право записывать одну model revision. Multi-document update не объявляется атомарным только из-за атомарности каждого файла: до реализации общей транзакции использовать staging generation и один publication manifest. Читатель берет только завершенную generation.

Source recheck и model CAS не атомарны относительно внешнего Git/Jira. В управляемом локальном snapshot можно удерживать source generation на время публикации. Для внешних источников знание честно относится к captured snapshot, а новое изменение делает его applicability stale. Planner, auditor, patch runner и test runner повторно проверяют релевантные fingerprints перед использованием. Без этой проверки наличие свежей model revision не является доказательством текущего поведения проекта.

### 8.4. Lifecycle и конфликты

События `create/refine/replace/deprecate/reject/reinstate` имеют source, scope, expected revision и reason. `deprecate` применяется даже к неизменному statement. Replay одного operation ID не создает новую версию.

Конфликт определяется пересечением scope и несовместимыми результатами, а не только одинаковыми строками must/must-not. Вероятное противоречие остается unresolved до proof/решения. Нельзя автоматически выбрать самый поздний текст по timestamp.

Карантин хранит reason, candidates, evidence refs, affected consumers и условия повторной проверки. High-risk конфликт блокирует изменение затронутого контракта; несвязанная работа не блокируется глобально.

## 9. Retrieval для вопроса, задачи и плана

| Режим | Минимальный пакет | Когда расширить |
|---|---|---|
| Вопрос без задачи | Project scope, найденный source range, 1-3 relevant rules, gaps | Вопрос затрагивает общий контракт или источники спорят |
| Небольшая правка | Изменяемый контракт, IN/OUT, relevant rules/cases и точные проверки | Риск доступа, данных, состояний или shared default |
| Полный план | AC/risk IDs, sources, approved intent, observed divergences, scenario refs | Незакрытый high-risk gap или неразрешенный потребитель |
| Аудит плана | Frozen read-set, спорные решения, независимые source refs | Требуется проверить assumptions автора, не весь его transcript |

Retrieval возвращает `items`, `total_or_lower_bound`, `truncated`, `next_cursor`, `generation`, `coverage_gaps`, `invalidated_refs` и размер. Усечение не превращается в отрицательный ответ. Все active rules в каждый prompt больше не передаются.

Начальные экспериментальные бюджеты: краткий вопрос до 1 500 токенов найденного evidence; контекст одной правки до 3 000; отдельный packet малому исполнителю рассчитывает compiler из фактического окна модели. Это soft budgets исследования, не гарантии качества и не запрет открыть нужный источник.

При превышении budget сначала сократить дубли и запросить конкретную секцию. Если существенный контракт не помещается, разбить работу или передать более сильной модели. Нельзя скрывать неполное исследование ради формального лимита.

## 10. От бизнес-процесса к проверяемому тесту

### 10.1. Процесс и decision table

Process record связывает входы, actors/roles, состояния, команды, эффекты и запрещенные действия. Rule определяет ограничение. Scenario объединяет один пользовательский смысл; cases задают разные строки decision table.

Test designer получает approved intent, существенные observed divergences и preserved behavior. Designer выбирает expected и слой; test author переводит контракт в код. Исполнитель не меняет expected ради green.

| Вид поведения | Первый достаточный слой | Дополнительный слой |
|---|---|---|
| Расчет, границы, дата | Unit/table-driven | Интеграция реальных параметров при зависимости от schema/config |
| Транзакция, idempotency, конкуренция | Integration с изолированными данными | HTTP/browser критического пути |
| Права и принадлежность объекта | HTTP/contract/integration ролей | Browser проверяет доступность действия и реальный отказ |
| DOM, форма, wiring, visibility | Browser существующего приложения | Visual проверка для требований к отображению |

### 10.2. Происхождение oracle

Нормативный expected ссылается на принятое решение. Сохраняемое legacy-поведение допускает characterization oracle, явно помеченный как observation. Такой тест не утверждает правильность бизнеса и не должен молча блокировать согласованное исправление.

Expected из нового patch не считается независимым oracle. Допустимы проверенные математические свойства, эталонный контракт, decision table, approved examples и независимая модель поведения. Сравнение двух реализаций с одной общей ошибкой не доказывает корректность.

### 10.3. Единые IDs и reusable bindings

`rule_id` связывает правило с decision table. `scenario_id` общий для plan, test contract, browser flow и receipt. `case_id` различает строки таблицы; runner-specific method и parameter ID хранятся как binding, а не как бизнес-ID.

Устойчивые Page/Step/API helpers принадлежат проектному suite. Flow map хранит семантическое действие, adapter binding, fixture contract, cleanup и source refs. Rename тестового метода меняет binding, но не scenario identity. Существенное изменение смысла создает contract version или новый scenario.

Для UI-change обязательно реальное browser evidence. Существующий Codeception может закрыть browser layer; дублирующий Playwright не требуется. Playwright закрывает исследовательский gap, а долговечный regression test затем сохраняется в versioned suite проекта.

## 11. Сквозной пример без привязки к CopyTrust

Процесс: владелец отправляет черновик на публикацию. Повтор запроса не должен создавать вторую заявку; чужой пользователь не может отправить черновик. Конкретные URL, таблицы, role IDs и selectors предоставляет проектный adapter.

```text
rule_id: BR-PUBLISH-001
version: 1
scenario_id: SC-PUBLISH-001
process_id: PROCESS-PUBLISH
intent_status: approved, только при наличии OWNER-DECISION-001
scope: draft.status=draft; actor owner or foreign; publication feature enabled
oracle_ref: OWNER-DECISION-001@revision-1
```

| case_id | Условие и действие | Expected | Запрещенный эффект |
|---|---|---|---|
| CASE-OWNER-NEW | Владелец отправляет свой черновик с новым request key | Одна заявка; статус pending; подтверждение пользователю | Вторая заявка и повторный внешний эффект |
| CASE-OWNER-REPLAY | Владелец повторяет тот же запрос с тем же key | Возвращается тот же результат; одна заявка | Повторная запись, событие или списание |
| CASE-FOREIGN-DENIED | Другой пользователь отправляет чужой черновик | Отказ; черновик и заявки неизменны | Чужая запись и утечка закрытого содержимого |

Integration binding проверяет число сущностей, состояние и уникальный эффект. HTTP binding проверяет авторизацию. Browser binding проверяет форму, видимость действия и ответ реального приложения; скрытая кнопка не заменяет server-side authorization test.

Fixture создает owner, foreign actor, черновик и уникальный run namespace. Replay использует тот же key внутри одного case. Cleanup удаляет только созданные fixture сущности; внешний эффект идет в test sink. Две сессии изолированы.

Receipt содержит `SC-PUBLISH-001`, конкретные case IDs, `BR-PUBLISH-001@1`, contract hash, fixture/runtime/tree refs и фактические результаты. Plan ссылается на те же IDs. Отдельные повторные ID для browser и business registry не создаются.

Run receipt использует общие статусы `passed`, `failed`, `blocked`, `not_run`, `not_required`. Последний требует policy reason и scope. Claim verification axis из раздела 5 остается отдельной: stale run не подменяется свежим passed, а найденная ссылка на тест не становится выполнением.

## 12. Карта покрытия и честные пробелы

Coverage map строится по process -> entrypoint -> role/state/config -> rule -> scenario/case -> binding -> run. Каждое ребро имеет LinkRef и evidence; автоматическая связь по общему имени остается candidate.

Отдельные gaps: неизвестное требование, нет approved oracle, неразрешенная динамическая связь, stale source, missing test, missing binding, неисполненный case, неподходящая среда, непроверенная роль/конфигурация и failed result. Эти причины нельзя сворачивать в один процент coverage.

Изменение правила выбирает связанные scenarios и соседние существенные эффекты. Отсутствие связи запускает gap review, а не вывод, что тесты не нужны. Graph-selected tests дополняются стабильным project smoke и risk-based checks.

Полнота относится только к объявленной области. Исследованные 10 entrypoints не доказывают отсутствие одиннадцатого. Покрытие строк не доказывает все бизнес-состояния; полный декартов набор ролей/состояний тоже не нужен без риска.

## 13. Изменения существующих компонентов

| Компонент | Конкретное изменение | Сохранить |
|---|---|---|
| `business-analyst/scripts/business_analyst.py`, `auto_run.py` | Исправить import; neutral source adapters; version-bound inputs | Один facade, компактный JSON envelope |
| `extract_rules.py`, `jira_sync.py` | SourceRef/snapshot CAS, bounded related rules, code/docs/test inputs | Delta/hash-ledger и точные quotes |
| `resolve_anchors.py`, `ba_common.py` | Capability symbol resolver, scope/hash validation; убрать CT domains из core | Locator и symbol fingerprints |
| `verify_rules.py` | Structural checks отдельно; semantic findings и independent review contract | Машинные negative checks и карантин |
| `aggregate_rules.py`, `promote_rules.py` | Event lifecycle, single canonical claim refs, scope/version, atomic publication | Историю, snapshots и идемпотентность |
| `impact_rules.py`, `build_test_impact.py` | Reverse dependencies, stable scenario/case IDs, минимальный слой | Генерацию компактного worklist |
| `render_rules.py`, `validate_state.py`, `rollback_rules.py` | Разные статусы осей, stale view, validated replay/restore | Generated views и журнал восстановления |
| JSONdoc `store/contract/batch/search/review` | Shared claim/evidence types, WorkRef, CAS generation и bounded retrieval | Существующий storage и транзакционные механизмы |
| `project-doc`, `doc-verify` | Domain onboarding, claims/coverage, leases, source receipts | Индекс, очереди, историю и sections navigation |
| `task-doc`, `task-intake` | Потреблять claim refs; findings не закрывают AC без evidence | Tracker snapshots и authored decisions |
| `code`, `bug-cause`, `prepare-plan`, `audit-plan` | Query-context по work/risk, read-set и gaps | Graph-first discovery и независимое proof |
| `design-test-scenarios`, `prepare-task-test`, `test-task`, `browser-verify` | Общие scenario contracts/bindings/receipts | Page/Step reuse, реальный runner, browser evidence |
| `project-setup`, `new-project`, `migration-review` | Profile ontology/storage refs, empty target data namespaces | Generic schemas/CLI; target project isolation |

Названия файлов относятся к текущему Codex-зеркалу для проверки; канонический target при внедрении разрешает manifest. `.codex/skills/` независимо не правится. Новые общие modules добавляются существующему `harness-core/scripts/lib/`, без копирования schemas в каждый leaf.

## 14. Порядок внедрения с приемкой и откатом

### K1. Стабилизировать существующий вход

Исправить import/path defects; subprocess smoke всех public entrypoints и 22 исходных business tests. Добавить negative fixtures ложного verified и deprecate. До исправления semantic gate запретить новый automatic active promote. Откат сохраняет evidence и quarantine, не возвращает ложный статус истины.

### K2. Ввести типы identity и три оси статусов

Расширить JSONdoc contract совместимо, добавить SourceRef/RuleRef/ScenarioRef и migration dry-run. Приемка: numeric tasks читаются; legacy verified не становится behavior passed; неизвестный owner не дает approved. Откат использует старую проекцию с legacy label, новые записи не теряются.

### K3. Собрать scoped индексы и retrieval

Настроить graph/docs/test discovery по проекту, worklist и bounded related rules. Приемка: вопрос без Jira; незнакомый JS/Python проект без CopyTrust словаря; усеченный поиск виден; wrong project index отклоняется. Откат оставляет прямое чтение источников с gaps и прежний registry view.

### K4. Добавить invalidation и публикацию generation

Реализовать source deltas, reverse edges, rename/delete, prompt/extractor changes, leases и CAS. Приемка: stale output модели не записывается; два worker не теряют версии; render failure не уничтожает модель; crash не публикует незавершенную generation. Откат переключает читателя на последнюю завершенную generation.

### K5. Пилот бизнес-процессов и тестовых связей

Заполнить два процесса в shadow, независимо проверить oracle и cases, связать runner/browser bindings. Приемка: общий scenario ID проходит plan -> contract -> run; roles/idempotency проверены; локальный GREEN не закрывает чужой scope. Откат оставляет candidates и существующие тесты, не объявляет пилот approved автоматически.

### K6. Масштабировать после измерения

Расширять домены по risk-ranked worklist. Проверить перенос самого харнеса в чистый fixture project: schema/CLI доступны, source claims/clients/tasks/URLs исходного проекта отсутствуют. Проверить восстановление versioned knowledge на чистом checkout исходного проекта без локального `.doc` cache. Переключать default extraction только после приемки качества и стоимости.

## 15. Обязательные отрицательные проверки

1. Подлинная цитата с противоположным statement: structural validity возможна, semantic support отклонен.
2. Метод существует, но возвращает противоположное: нет behavior passed.
3. Старый ответ модели после нового отменяющего комментария: `stale_input`, без promote.
4. Comment удален, источник временно недоступен и explicit deprecate: три разных исхода.
5. Неизменный statement плюс deprecate: правило закрыто в нужном scope; другая ветка не закрыта молча.
6. Rename при том же теле, rename с изменением смысла и delete: разные locator/lifecycle решения.
7. Измененный symbol/schema/config/test инвалидирует потребителей; несвязанный домен не переисследуется.
8. Тот же text hash с новой extractor version допускает целевую переоценку.
9. Concurrent CAS conflict и повтор operation ID: ни потерянной версии, ни дубля события.
10. Сбой между model commit и view render: модель current, view stale; безопасная пересборка.
11. Два provider projects с external ID 42: разные identity и namespaces.
12. Unknown domain/language/provider: gap или adapter request, без CT fallback.
13. Метод теста найден, но не исполнился: referenced/exists, без passed.
14. Browser mock DOM вместо приложения и скрытая кнопка без server check: недостаточно evidence.
15. Expected скопирован из будущего patch: oracle review blocked.
16. Перенос kit с копированием source registry/credentials: transfer test failed.

## 16. Метрики и критерий принятия

Начальная контрольная выборка: 20-30 небольших work items, включая вопросы без задачи, исправления, shared-risk изменения и противоречащие источники. Два пилотных процесса проверяются на одинаковых snapshots до и после изменений. Повторить на целевых сильной и малой моделях; это пилот, а не статистическая гарантия.

Измерять: precision кандидатов по независимой разметке, обнаружение известных отрицательных fixtures, stale-use rate, долю claims без oracle, unresolved gaps, LLM input/output/cached tokens, стоимость, latency и число повторных чтений. Recall оценивать только относительно размеченной области; весь неизвестный бизнес не является известным denominator.

Приемка первой версии: все отрицательные fixtures различаются правильно; ни один stale или structural-only record не становится behavior proof; unchanged повтор не вызывает extraction LLM; changed-only затрагивает доказанные зависимости; median tokens не выше baseline при неизменной приемке качества. Проценты экономии заранее не обещаются.

Для high-risk пилота false approval на контрольных отрицательных примерах недопустим. При неопределенном oracle результат blocked/proposed; это не ошибка продукта и не успешная верификация. Новые default policies включаются только после отдельного решения по пилоту.

## Связи

- [Общий план развития](../plan.md) - архитектура, evidence, WorkContext и пакеты внедрения.
- [Мастер-план сканирования и аудита](./deepseek.md) - цели, требования, очередь, скилы и фазы P0-P7.
- [Субагентное планирование и аудит](./01-subagent-planning-and-audit.md) - использование frozen knowledge slice при планировании.
- [Система web-тестирования](./03-web-testing-system.md) - materialization сценариев, browser bindings и результаты.
- [Хранилище знаний и очередь](./04-knowledge-store-and-queue.md) - канон, SQLite, coverage и восстановление.
- [Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md) - findings, pass library и backlog.
- [Текущее устройство бизнес-аналитики](../state/17-business-analyst.md) - история существующих решений; актуальность сверять по коду.
- [JSONdoc](../jsondoc.md) - существующий контракт хранения и представлений.

## Известные проблемы и ограничения

Документ проектирует систему; новый extraction, schemas и adapters еще не внедрены. Числовые бюджеты являются стартовыми параметрами эксперимента. Semantic review снижает риск ложного знания, но не доказывает полноту требований и не заменяет владельца бизнес-решения.

Исходный аудит подробно проверял бизнес-конвейер и существенные JSONdoc contracts; построчный аудит всех транзитивных helpers, индексаторов и browser backends не выполнен. Перед соответствующим K-пакетом нужны целевые fixtures и свежие source fingerprints. Глобальные настройки, CI/CD, реальные БД и внешние публикации в scope этого документа не входят.

## История изменений

- 2026-11-06: выделен проект индексации, бизнес-знаний и связей с тестовыми сценариями; отделены нормативные требования, наблюдение кода и результаты исполнения.
- 2026-11-06: уточнены разные identity для source snapshot, model CAS и projection generation; описано ограничение атомарности между Git/Jira и storage.
- 2026-11-06: добавлена связь с мастер-планом, хранилищем и очередью, аудитом дефектов. Зафиксировано, что SQLite хранит производное координационное состояние, а канон остается в JSONdoc.

#harness #indexing #business-logic #testing
