# Сканирование кодовой базы, база знаний и аудит

<!-- meta
type: plan
status: draft
updated: 2026-11-06
related: [../plan.md, ./01-subagent-planning-and-audit.md, ./02-project-index-and-business-knowledge.md, ./03-web-testing-system.md, ./04-knowledge-store-and-queue.md, ./05-bug-hunt-and-modernization.md]
tags: [harness, scan, business-logic, audit, testing, storage, queue]
-->

---

## Суть

Документ задает универсальную подсистему харнеса для незнакомой кодовой базы:
инвентаризация, извлечение бизнес-правил, поиск дефектов, генерация тестов,
модернизация и поддержание документации в актуальном виде. Система работает
очередью единиц сканирования, хранит проверяемые утверждения с доказательствами
и публикует человекочитаемые представления отдельно от машинного канона.

Главный вывод: один проход не дает полноты и не находит все дефекты. Полнота
достигается только как измеримое покрытие объявленной области с явно
перечисленными пробелами, повторными проходами и исполняемыми проверками.

Документ описывает цели, требования, находки, методологию, архитектуру,
форматы хранения, очередь, скилы, порядок внедрения и приемку. План готов к
внедрению: заданы фазы P0-P7, карта файлов, приемочные фикстуры, отрицательные
проверки и метрики. Код и настройки этим документом не меняются.

---

## 1. Цели и требования

### 1.1. Цели

| ID | Цель | Результат |
|---|---|---|
| G1 | Понять незнакомый репозиторий без полного чтения | Карта стека, входов, данных, границ доверия и пробелов |
| G2 | Извлечь бизнес-логику из кода, docs, задач, тестов и runtime | Проверяемые утверждения с областью действия и доказательствами |
| G3 | Найти дефекты логики, данных, безопасности и производительности | Подтвержденные findings с воспроизведением и приоритетом |
| G4 | Связать правила с исполняемыми тестами | Цепочка claim -> scenario -> case -> test -> run receipt |
| G5 | Поддерживать документацию актуальной | Генерируемые представления с проверкой свежести |
| G6 | Дать план модернизации legacy | Приоритетный backlog с characterization tests и метриками |
| G7 | Встроить процесс в каждую задачу | Планирование, реализация, review, тест и отчет используют знания |
| G8 | Переносить харнес в другой проект без чужих данных | Пустой knowledge namespace и проектные adapters |

### 1.2. Функциональные требования

| ID | Требование | Проверка |
|---|---|---|
| R1 | Bootstrap незнакомого репозитория | Определены стек, команды install/build/lint/test/run, entrypoints, data stores, внешние системы и trust boundaries. Неизвестное помечено `unknown`, а не угадано |
| R2 | Инвентаризация области | Каждый файл, entrypoint и таблица получают статус `covered`, `skipped` или `gap` с причиной |
| R3 | Структурный граф | Используются CBM и codegraph; зафиксированы generation, `indexed_at` и известные пробелы парсера |
| R4 | Извлечение утверждений | Claim содержит statement, scope, evidence, три оси статуса и provenance |
| R5 | Проверка утверждений | Структурная, смысловая и поведенческая проверки разделены; противоречие не становится `approved` |
| R6 | Аудит дефектов | Проходы по state, money, authz, input, transactions, concurrency, data, performance, security, operability, API, architecture |
| R7 | Доказательство дефекта | Finding содержит evidence, reproduction или статическое доказательство, impact и fingerprint |
| R8 | Генерация тестов | Scenario contract с oracle, preconditions, action, expected, state after и layer |
| R9 | Исполнение тестов | Run receipt хранит commit, environment, команду, результат и артефакты |
| R10 | Документация | Domain docs, ER, state machines и flow diagrams генерируются из канона |
| R11 | Инкрементальность | Изменение файла инвалидирует связанные claims, findings, views и тесты |
| R12 | Интеграция с задачами | План и review цитируют claim IDs, findings и scenarios; изменение поведения обновляет знания |
| R13 | Очередь работ | Единая durable queue с lease, retry, приоритетом, зависимостями и восстановлением после сбоя |
| R14 | Ограничение бюджета | Для каждой единицы заданы лимит файлов, токенов и времени; превышение дает `gap`, а не скрытое усечение |
| R15 | Переносимость | Универсальные schemas, CLI и adapters отделены от проектных данных, путей, URL и учетных записей |

### 1.3. Нефункциональные требования

| ID | Требование |
|---|---|
| N1 | Evidence-first: утверждение без доказательства не публикуется как факт |
| N2 | Fail-closed: при сомнении статус `proposed` или `quarantine`, не `approved` |
| N3 | Идемпотентность: повторный запуск не создает дублей и не теряет версии |
| N4 | Crash-safe: падение worker не публикует незавершенную generation |
| N5 | Resumable: работа продолжается с последней завершенной единицы |
| N6 | Детерминизм: IDs и fingerprints не зависят от порядка обхода |
| N7 | Изоляция проектов: запрещены чужие графы, claims, tasks, fixtures и endpoints |
| N8 | Секреты не попадают в артефакты, логи и модели |
| N9 | Стоимость ограничена бюджетом на единицу и на прогон |
| N10 | Все записи канона проходят CAS и журнал операций |
| N11 | Производные индексы и views можно пересобрать без потери канона |
| N12 | Процесс работает без нативных субагентов, но использует их при наличии |

### 1.4. Что система не обещает

| Ожидание | Реальность |
|---|---|
| Найти все баги | Невозможно в общем случае. Есть статические, динамические и смысловые пробелы |
| За один проход получить полную документацию | Первый проход дает карту и приоритеты. Полнота требует coverage ledger и повторных проходов |
| Заменить владельца бизнес-решения | Система предлагает `proposed`; `approved` требует полномочий и решения человека |
| Гарантировать идеальную архитектуру | SOLID и OOP контекстны. Система дает измеримые улучшения и обратимые шаги |
| Заменить нагрузочное и пенетрационное тестирование | Аудит находит кандидатов и статические дефекты, но не доказывает поведение под нагрузкой и не заменяет pentest |
| Доказать отсутствие дефектов | Отрицательное утверждение ограничено объявленной областью и известными evidence |

### 1.5. Критерии успеха

| Критерий | Стартовая цель |
|---|---|
| Инвентаризация объявленной области | 100 процентов файлов, entrypoints и таблиц имеют статус и причину |
| Покрытие процессов высокого риска claims и scenarios | Не меньше 80 процентов для денег, прав, данных и внешних эффектов |
| Привязка approved claims к тестам | Не меньше 70 процентов на пилоте, рост после калибровки |
| Воспроизводимость S0/S1 findings | 100 процентов имеют reproduction или формальное доказательство |
| Ложные срабатывания после triage | Не больше 15 процентов |
| Свежесть сгенерированных views | 100 процентов имеют совпадающий source hash |
| Надежность очереди | Ноль потерянных единиц в crash-тесте; повторный запуск не создает дублей |
| Стоимость единицы | Укладывается в проектный бюджет; превышение фиксируется как `gap` |
| Регрессия после модернизации | Ноль новых S0/S1; целевые метрики улучшены и измерены |

---

## 2. Главный вывод

| Вопрос | Ответ |
|---|---|
| Можно ли найти все баги одним сканированием | Нет. Статический граф не видит динамические вызовы, runtime-конфигурацию и данные. Смысловые ошибки требуют oracle |
| Можно ли за один проход получить полноценную документацию | Нет. Первый проход дает инвентаризацию и карту. Домены, правила и тесты пополняются очередью |
| Нужна ли очередь | Да. Без durable queue теряются единицы работы, а повторный запуск создает дубли и гонки |
| Нужна ли отдельная база знаний | Нужен один канон утверждений и производные индексы. Вторая редактируемая копия запрещена |
| Даст ли система идеальный код после исправлений | Нет. Даст измеримое улучшение: меньше подтвержденных дефектов, выше покрытие сценариев, контролируемая сложность и обратимость |
| Что можно гарантировать | Полноту объявленной области, происхождение каждого вывода, явные пробелы и воспроизводимость результатов |

Правильная формулировка результата: не "идеальная система", а "система с
известным покрытием, подтвержденными дефектами, исполняемыми проверками и
измеримыми улучшениями".

---

## 3. Находки текущего состояния

### 3.1. Что уже работает

| Компонент | Что дает | Ограничение |
|---|---|---|
| `codebase-memory-mcp` 0.12.1 | Граф кода, `search_graph`, `trace_path`, `detect_changes`, `query_graph`, `doc_links`, кластеры | Маршруты legacy PHP извлекаются неполно; `.doc/` исключен из индекса |
| `codegraph` 1.6.2 | Исходник, путь вызовов и blast radius одним вызовом | Markdown не индексирует; сообществ по плотности нет |
| `serena` | Символы, references, диагностика PHP | Не индексирует `.doc/`; JS и TPL только файловые правки |
| `phpstan-mcp`, `semgrep` | Типы, статические и security-проверки | Не заменяют runtime и бизнес-оракул |
| JSONdoc | CAS, журнал, render, receipts | Схемы пока заточены под задачи и business rules |
| `business-analyst` | Hash-ledger, shadow, quarantine, registry, render, impact | Вход построен вокруг Jira; извлечение из кода без задачи не оформлено |
| `project-doc`, `doc-verify` | Индексация, сверка docs с кодом, очереди батчей | Очереди текстовые; lease и восстановление после сбоя отсутствуют |
| `prepare-plan`, `test-task` | Blast radius, research ledger, ветки логики, Codeception | Нет единого scenario registry на весь проект |
| Codeception, Playwright | Исполняемые UI и acceptance проверки | Нет полной привязки утверждений к методам |

### 3.2. Подтвержденные разрывы

| Наблюдение | Где проверено | Следствие |
|---|---|---|
| Извлечение правил начинается с Jira | `state/17-business-analyst.md:30`, `.agents/skills/business-analyst/SKILL.md:1` | Нет режима "извлеки правила из кода без задачи" |
| CBM `manage_adr` не используется | `adr_present: false`, `manage_adr outline` вернул 0 разделов | Решения живут в `.doc/`, что соответствует канону |
| `.doc/` не входит в граф кода | `index_status`: `.doc` в `not_indexed`, причина `excluded BY DESIGN` | Канон docs не связан с code nodes |
| Связь docs с кодом есть только для `docs/**` | `doc_links.mentions: 935`; источники `docs/reverse-engineering/*.md` | Старые reverse-engineering заметки связаны, канон харнеса нет |
| Межпроектные связи не строились | `cross_repo: never_run` | `td-docs-arch` и `td-docs-tasks` не связаны с кодом |
| `get_architecture` дает слабые entrypoints для legacy PHP | 37 Route, почти все статические ассеты tinyMCE, `handler` пустой; entry_points это Vue methods | Очередь нельзя строить только по `get_architecture` |
| Очереди документации хранятся в тексте | `current-batch.txt`, `current-verify-batch.txt`, `verify-registry.tsv`, `state/05-scripts.md:80` | Нет atomic claim, lease, retry и dead-letter |
| Нет проактивного аудита дефектов | `bug-cause` ищет причину известного бага | Нет pass library для поиска неизвестных дефектов |
| Нет скила модернизации | `prepare-plan` работает по задаче | Нет project-wide backlog рефакторинга |
| Тесты не привязаны к правилам | `state/17-business-analyst.md:685`: 54 planned, реальные методы не привязаны | Нельзя доказать покрытие правила исполнением |
| Нет golden set | `state/17-business-analyst.md:655` | Precision и recall извлечения не измерены |
| Нет бюджета токенов | `state/17-business-analyst.md:655` | Большой репозиторий может исчерпать контекст без явного `gap` |
| `manage_adr` запрещен как второй источник правды | `.doc/harnes/doc_rules.md:567`, `.cursor/rules/mcp/codebase-memory-mcp.mdc:116` | Решения и правила не пишутся в CBM |

### 3.3. Что переиспользовать без переделки

1. JSONdoc CAS, журнал, renderer и receipts.
2. Hash-ledger, shadow, quarantine и три оси статусов из плана 02.
3. MCP-маршрут CBM -> codegraph -> serena -> mysql -> phpstan/semgrep.
4. Codeception, Playwright, Page и Step objects.
5. `prepare-plan` blast radius и research ledger.
6. Проектные adapters и запрет на перенос проектных данных.

Новые компоненты добавляются как расширение этих механизмов. Второй граф,
второй vector store и второй event framework в первой версии не создаются.

### 3.4. Что взять из Sourcegraph и других инструментов

| Возможность | Что полезно | Решение |
|---|---|---|
| Точный индекс компилятора, SCIP или LSIF | Связи точнее tree-sitter для PHP и JS | Не в первой версии. Добавить как provider, если графовых пробелов станет много |
| Кросс-репозиторный поиск | Единый поиск по нескольким репозиториям | Локально покрывается CBM, codegraph и jdocmunch; внешний сервис не нужен |
| Batch changes | Массовые изменения с review | Берем процесс: modernization backlog и серия обратимых патчей |
| Code monitors | Реакция на изменения кода | Берем идею: change-driven re-scan и revalidate |
| Язык поисковых запросов | Сложные выборки | Достаточно `multi-search.sh`, `rg` и `query_graph` |
| Saved searches | Повторяемые проверки | Хранить как pass или semgrep rule, не как внешний query |

Sourcegraph остается отключенным legacy. Из него берется модель точного индекса
и мониторинга изменений, а не возврат сервера в обязательный маршрут.

---

## 4. Методология

### 4.1. Лестница доказательств

| Уровень | Evidence | Что доказывает |
|---|---|---|
| E0 | Git commit, file hash, snapshot | Что именно исследовалось |
| E1 | Граф CBM или codegraph | Структурную связь |
| E2 | Прочитанный исходник с locator | Фактический код |
| E3 | Конфиг, схема БД, runtime log, trace | Фактическую конфигурацию и поведение |
| E4 | Исполненный тест или воспроизведение | Наблюдаемое поведение |
| E5 | Решение владельца | Нормативное требование |

Утверждение не поднимается выше уровня, подтвержденного evidence. Наличие
цитаты не делает утверждение истинным. Совпадение ответов моделей не заменяет
E5.

### 4.2. Единицы сканирования и глубина

| Единица | Пример | Первый проход | Глубина по риску |
|---|---|---|---|
| `repo` | Весь репозиторий | Стек, команды, entrypoints, data stores | L0-L1 |
| `module` | `lib/Objects/Order` | Файлы, классы, зависимости | L1-L2 |
| `entrypoint` | HTTP route, CLI, cron, queue consumer, webhook | Путь до эффекта | L2-L3 |
| `entity` | Таблица, агрегат, состояние | Схема, инварианты, переходы | L2-L4 |
| `integration` | Платежный провайдер, SMTP, внешний API | Контракт, retry, ошибки | L2-L3 |
| `pass` | `authz`, `transactions`, `performance` | Вопрос прохода | L3-L4 |
| `scenario` | Бизнес-процесс | Oracle и cases | L4 |
| `modernization` | Кандидат на рефакторинг | Метрика и тест | L5 |

Уровни глубины:

| Уровень | Содержание |
|---|---|
| L0 | Инвентаризация по графу без чтения тел |
| L1 | Карта модулей, входов, данных и зависимостей |
| L2 | Чтение ключевых функций и извлечение claims |
| L3 | Аудит по pass library и проверка контрпримеров |
| L4 | Исполняемые тесты, runtime evidence и воспроизведение |
| L5 | План модернизации с characterization tests и метриками |

Риск задает глубину. Деньги, права, персональные данные, внешние эффекты и
разрушающие операции идут на L3-L4. Косметика и мертвый код остаются на L1-L2.

### 4.3. Очередь, бюджет и остановка

1. Resolver создает generation и очередь единиц.
2. Worker берет единицу по приоритету и риску.
3. Для единицы задан бюджет: файлы, токены, время, максимальное число чтений.
4. Исследование останавливается, когда evidence достаточно для текущего уровня.
5. Превышение бюджета дает `gap` с причиной, а не молчаливое усечение.
6. Результат пишется в канон через CAS, затем обновляются views и coverage.
7. Следующая единица берется только после завершения текущей транзакции.

Приоритет единицы: `risk x exposure x uncertainty / effort`. Деньги и доступ
идут раньше косметики. Зависимости не позволяют запускать `pass`, пока не
собрана карта его области.

### 4.4. Статусы и вердикты

Claim:

| Ось | Статусы |
|---|---|
| `intent_status` | `unknown`, `proposed`, `approved`, `conflicted` |
| `implementation_status` | `unknown`, `observed`, `divergent`, `stale` |
| `verification_status` | `untested`, `specified`, `passed`, `failed`, `blocked`, `stale` |

Finding:

| Поле | Значения |
|---|---|
| `status` | `suspected`, `reproduced`, `confirmed`, `fixed`, `verified`, `wontfix`, `false_positive` |
| `severity` | `S0`, `S1`, `S2`, `S3`, `S4` |
| `confidence` | `confirmed`, `high`, `medium`, `low` |

Stale означает, что изменился source hash, extractor, schema или prompt.
Stale не удаляет запись, а исключает ее из active views и инициирует
перепроверку.

### 4.5. Инкрементальность и инвалидация

1. Изменение файла вычисляет `detect_changes` и затронутые символы.
2. Обратные связи находят claims, findings и scenarios, которые ссылались на символы.
3. Записи получают `stale`, их views исключаются из active.
4. В очередь добавляется `revalidate` с приоритетом выше нового сканирования.
5. После проверки создается новая версия claim, старая уходит в history.
6. Изменение extractor, schema или prompt поднимает generation и инвалидирует
   все производные результаты, зависящие от них.

Полная переиндексация не запускается на каждый коммит. Она нужна только при
смене generation, крупном рефакторинге или потере индекса.

### 4.6. Поиск дефектов

Аудит идет вопросами, а не перечитыванием всего кода. Для каждой единицы
выбираются проходы по риску: состояние, деньги, права, ввод, транзакции,
конкурентность, retry, данные, производительность, безопасность, эксплуатация,
API, архитектура. Каждый проход обязан вернуть либо finding с evidence, либо
явный `no_finding` с указанием проверенной области и остаточного риска.

Полная библиотека проходов, severity, воспроизведение и модернизация:
[Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md).

### 4.7. Генерация тестов

1. Бизнес-процесс раскладывается на decision table: условия, действия, ожидаемый
   результат, состояние после.
2. Oracle берется из approved claim, решения владельца, спецификации или
   наблюдаемого поведения с явной пометкой.
3. Для каждой строки создается scenario contract с preconditions, action,
   expected, state after и layer.
4. Case привязывается к существующему Page или Step object; новый селектор
   добавляется только при отсутствии переиспользуемого.
5. Тест запускается, результат пишется в run receipt.
6. Покрытие считается по scenarios, а не по строкам кода.

Если oracle неизвестен, scenario получает `oracle_unknown` и не превращается в
автоматический assert. Детали: [Воспроизводимое web-тестирование](./03-web-testing-system.md).

### 4.8. Документация

1. Канон claim, finding, scenario и decision хранится в JSONdoc.
2. Domain docs, ER, state machines и flow diagrams генерируются из канона.
3. Ручная правка сгенерированного view запрещена.
4. `doc-verify` сверяет утверждения с кодом и помечает drift.
5. Каждый документ содержит source hashes, generation и дату.

---

## 5. Архитектура решения

```text
git / tracker / docs / runtime logs / DB schema
        |
        v
  Source adapters (project manifest)
        |
        v
  Scanner orchestrator  <---->  SQLite work queue
        |                              |
        |                              v
        |                       coverage + leases
        v
  Evidence collectors (CBM, codegraph, serena, mysql, semgrep, phpstan, tests)
        |
        v
  Claim / Finding / Scenario / Decision records (JSONdoc canon)
        |
        +--> Docs renderer (Markdown + Mermaid) --> jdocmunch
        |
        +--> Test designer --> Codeception / Playwright --> run receipts
        |
        +--> Modernization backlog --> prepare-plan / task flow
```

### 5.1. Компоненты

| Компонент | Ответственность | Не делает |
|---|---|---|
| Scanner orchestrator | Generation, очередь, приоритеты, остановка | Не извлекает смысл и не пишет docs |
| Source adapters | Читают проект, tracker, docs, schema, logs | Не решают, что истинно |
| Evidence collectors | Вызывают MCP и локальные инструменты, сохраняют ссылки | Не публикуют claims |
| Knowledge core | CAS, схемы, ID, версии, инвалидация | Не вызывает модели |
| Extraction worker | Готовит evidence slice и валидирует ответ модели | Не утверждает без проверки |
| Audit engine | Запускает pass library, дедуплицирует findings | Не исправляет код |
| Docs renderer | Собирает Markdown и Mermaid из канона | Не правит сгенерированные views руками |
| Test designer | Строит scenarios и bindings, запускает тесты | Не выдумывает oracle |
| Modernization planner | Строит backlog и метрики | Не делает big-bang rewrite |
| Coverage service | Считает покрытие по осям и пробелы | Не сворачивает разные gaps в один процент |

### 5.2. Владение артефактами

| Артефакт | Владелец записи | Читатели |
|---|---|---|
| Project manifest | `codebase-scan` | Все компоненты |
| Claim, finding, scenario, decision | `knowledge-extract`, `bug-hunt` | Docs, tests, task flow |
| Queue и coverage | Scanner orchestrator | Все worker |
| Domain docs и diagrams | Docs renderer | Люди и агенты |
| Run receipt | Test runner | Coverage, review, report |
| Modernization backlog | Modernization planner | `prepare-plan`, task flow |

### 5.3. Поток данных

1. Bootstrap создает manifest и generation.
2. Очередь получает единицы `module`, `entrypoint`, `entity`, `integration`.
3. Evidence collectors собирают структурные и runtime данные.
4. Extraction worker создает claims и scenarios.
5. Audit engine добавляет findings.
6. Knowledge core проверяет CAS, версии и инвалидацию.
7. Renderer публикует docs; test designer создает и запускает тесты.
8. Coverage service обновляет карту пробелов.
9. Task flow читает релевантный срез знаний при планировании и review.

---

## 6. Хранение

### 6.1. Три уровня

| Уровень | Что хранит | Формат | Можно ли пересобрать |
|---|---|---|---|
| Канон | Claims, findings, scenarios, decisions, links | JSONdoc records с CAS | Нет, только восстановить из журнала или источника |
| Производное состояние | Очередь, leases, coverage, поисковый индекс | SQLite | Да, из канона и источников |
| Представления | Domain docs, ER, state, flow, coverage report | Markdown и Mermaid | Да, из канона |

Канон не дублируется в SQLite. SQLite не является вторым источником правды.
Подробные схемы, DDL, CLI и правила восстановления:
[Хранилище знаний и очередь работ](./04-knowledge-store-and-queue.md).

### 6.2. Почему JSONdoc, а не новая база

1. CAS, журнал, receipt и render уже работают.
2. Текстовый канон дает review, diff и merge.
3. SQLite удобен для координации, но плохо подходит для смыслового review.
4. Вторая редактируемая копия создает конфликт версий.
5. Проектные знания остаются переносимыми и не смешиваются с чужими.

### 6.3. Диаграммы

| Диаграмма | Канонические данные | Представление |
|---|---|---|
| ER | Сущности, атрибуты, связи, источник схемы | Mermaid `erDiagram` |
| State machine | Состояния, переходы, guards, события | Mermaid `stateDiagram-v2` |
| Business flow | Шаги, роли, входы, выходы, ошибки | Mermaid `flowchart` |
| Sequence | Участники, вызовы, ответы | Mermaid `sequenceDiagram` |

Диаграмма не хранится только картинкой. Исходные узлы и связи лежат в каноне,
рендер пересобирается.

### 6.4. Где лежат данные

1. Универсальные схемы и CLI входят в harness kit.
2. Проектный manifest задает пути хранения.
3. Канон по умолчанию лежит в локальной зоне проекта, как текущий
   `.doc/skil_data/business-analyst/`.
4. Безопасная версионируемая часть может экспортироваться в отдельный каталог
   проекта по решению владельца.
5. Секреты, raw tracker exports, персональные данные, sessions и большие
   transcripts в версионируемую зону не попадают.
6. Перенос харнеса создает пустой namespace и не копирует claims, findings,
   scenarios, tasks, fixtures и receipts.

### 6.5. Почему не отдельная graph DB

1. CBM уже хранит граф кода и принимает Cypher через `query_graph`.
2. Связи знаний немногочисленны по сравнению с кодом и живут в JSONdoc.
3. Neo4j, Memgraph или Kuzu добавляют сервер, драйвер, бэкап и второй источник связей.
4. При сложных многошаговых запросах сначала используется CBM `query_graph`.
5. Отдельная graph DB вводится только по измеренной потребности и как
   производный индекс, не как канон.

---

## 7. Очередь

Решение: SQLite в режиме WAL как координационное состояние, а не канон.

| Свойство | Реализация |
|---|---|
| Atomic claim | `BEGIN IMMEDIATE` и `UPDATE ... RETURNING` |
| Lease | `lease_owner`, `lease_until`, heartbeat |
| Восстановление | Просроченные lease возвращаются в `queued` |
| Retry | `attempts`, `max_attempts`, `not_before` с backoff |
| Dead letter | `failed` после лимита, с `last_error` |
| Идемпотентность | Deterministic ID, CAS и `operation_id` |
| Зависимости | `depends_on` JSON, проверка перед claim |
| Приоритет | Риск, влияние и неопределенность |
| Инвалидация | `generation`, статус `stale` |
| Наблюдаемость | `work_events`, счетчики, coverage |

Почему не текстовые файлы:

1. Нет atomic claim, два worker берут одну единицу.
2. Нет lease и восстановления после падения.
3. Нет retry, backoff и dead-letter.
4. Нет запросов покрытия и приоритетов.
5. Постоянные конфликты и diff-шум.

Почему не Temporal, BullMQ, Celery или Redis в первой версии:

1. Нужен внешний сервер или брокер.
2. Сложнее переносить между машинами и окружениями.
3. Для локального одного агента это избыточная инфраструктура.
4. Провайдер можно добавить позже: Postgres `SKIP LOCKED`, Temporal или
   Redis-очередь, если появится несколько хостов и долгие human approvals.

Полная схема, SQL, состояния и тесты очереди:
[Хранилище знаний и очередь работ](./04-knowledge-store-and-queue.md).

---

## 8. Скилы и инструменты

### 8.1. Новый корневой маршрутизатор

Предлагается `knowledge-router` с дочерними скилами:

| Скил | Триггер | Ответственность |
|---|---|---|
| `knowledge-router` | просканируй проект, собери базу знаний, найди баги в проекте, план модернизации | Маршрутизация и общий контракт |
| `codebase-scan` | незнакомый репозиторий, bootstrap, инвентаризация | Manifest, очередь, coverage, первичная карта |
| `knowledge-extract` | извлеки бизнес-правила из кода | Claims, evidence, версии, конфликты |
| `bug-hunt` | найди логические и другие дефекты | Pass library, findings, triage |
| `modernize` | модернизируй legacy, SOLID, производительность | Backlog, characterization tests, метрики |

`knowledge-router` не заменяет `documentation-router`, `testing-router` и
`task-router`. Он поставляет им знания и получает от них docs, тесты и задачи.

### 8.2. Изменения существующих скилов

| Скил | Изменение |
|---|---|
| `business-analyst` | Становится source adapter: Jira, docs, code, tests, runtime. Ядро извлечения и проверки сохраняется |
| `project-doc` | Читает claims и coverage; очередь заменяется на общий SQLite provider |
| `doc-verify` | Проверяет claim против кода и помечает drift; очередь общая |
| `task-intake` | Создает задачу и очередь первичного сканирования ее области |
| `task-doc` | Потребляет claim IDs и findings; не закрывает AC без evidence |
| `prepare-plan` | Читает claims, findings и scenarios; добавляет режим modernization |
| `bug-cause` | Остается реактивным; использует findings и pass evidence как вход |
| `prepare-task-test` | Строит Cest из scenario contracts и переиспользуемых Page/Step |
| `test-task` | Запускает связанные scenarios и пишет receipts |
| `task-code-review` | Проверяет diff против claims и finding fingerprints |
| `send-to-git` | Перед push проверяет свежесть generation и незакрытые S0/S1 |

### 8.3. Карта инструментов

| Вопрос | Инструмент |
|---|---|
| Структура, вызовы, blast radius | `codebase-memory-mcp` |
| Исходник и путь вызовов одним вызовом | `codegraph` |
| Символ, references, диагностика PHP | `serena` |
| Схема и данные | `mysql describe_table` |
| Типы и статический анализ | `phpstan-mcp` |
| Security-паттерны | `semgrep` |
| Документация | `jdocmunch` |
| История и авторство | `git` |
| UI и acceptance | Codeception, затем `playwright` |
| Runtime-поведение | логи, `ingest_traces`, наблюдаемые вызовы |

Порядок не меняет действующие правила MCP. CBM остается первым для структуры,
codegraph вторым для исходника и blast radius, serena для символов.

---

## 9. Рабочие сценарии

### 9.1. Bootstrap незнакомого репозитория

1. Пользователь вызывает `knowledge-router` с командой "просканируй проект".
2. `codebase-scan` создает project manifest и generation.
3. Определяются языки, пакеты, команды, entrypoints, data stores, внешние
   системы, auth и trust boundaries.
4. Проверяется `list_projects`, `index_status`, `get_architecture` и coverage.
5. Строится стартовая очередь: модули, входы, сущности, интеграции.
6. Публикуется карта с явными пробелами и приоритетами.
7. Выбираются два процесса высокого риска для пилота.

Условие остановки: инвентаризация завершена, области высокого риска названы, неизвестное
помечено.

### 9.2. Сканирование домена

1. Worker берет `module` или `entrypoint`.
2. Собирает evidence из графа, исходников, схемы, docs, задач и тестов.
3. Извлекает claims и сохраняет их как `proposed`.
4. Проверяет структуру, смысл и, где возможно, поведение.
5. Публикует domain doc, ER и state diagram.
6. Создает scenarios и связывает их с claims.
7. Обновляет coverage и добавляет пробелы в очередь.

### 9.3. Полный аудит проекта

1. Приоритет: деньги, права, данные, внешние эффекты, затем остальное.
2. Для каждой области запускаются проходы по риску.
3. Findings дедуплицируются по fingerprint.
4. S0 и S1 требуют воспроизведения или формального доказательства.
5. Findings связываются с claims, scenarios и тестами.
6. Формируется modernization backlog.
7. Публикуется отчет с покрытием, пробелами и остаточным риском.

### 9.4. Работа над задачей

1. `gototask` и `task-intake` создают задачу.
2. `prepare-plan` получает релевантные claims, findings, scenarios и историю.
3. План цитирует claim IDs и evidence, а не пересказывает их.
4. Реализация, которая меняет поведение, обновляет claim и создает regression test.
5. `task-code-review` сверяет diff с claims и finding fingerprints.
6. `test-task` запускает связанные scenarios и пишет receipt.
7. `task-report` использует бизнес-смысл и результаты тестов.

### 9.5. Изменение и повторная проверка

1. Коммит или PR запускает `detect_changes`.
2. Затронутые символы находят связанные claims, findings и scenarios.
3. Записи получают `stale`, views исключаются из active.
4. В очередь добавляется `revalidate`.
5. Проверка обновляет версии или подтверждает актуальность.
6. Coverage и docs пересобираются только для затронутой области.

### 9.6. Генерация тестов из правил

1. `knowledge-extract` создает claim.
2. `prepare-task-test` или `test-task` строит decision table.
3. Oracle берется из approved claim или решения владельца.
4. Создаются scenario contracts и cases.
5. Case привязывается к существующим Page и Step objects.
6. Тест запускается, результат и артефакты пишутся в receipt.
7. Покрытие обновляется по scenario, а не по строкам.

---

## 10. Порядок внедрения

| Фаза | Область | Выход | Откат |
|---|---|---|---|
| P0 | Baseline и безопасность | Метрики, фикстуры, feature flag | Отключить flag |
| P1 | Канон, схемы, JSONdoc | Типы claim, finding, scenario, decision | Старые схемы читаются |
| P2 | Очередь SQLite | Lease, retry, recovery, coverage | Вернуться к текстовым очередям |
| P3 | Bootstrap и инвентаризация | Manifest, карта, coverage | Ручной обход |
| P4 | Извлечение знаний | Claims из кода, docs, тестов, runtime | Shadow без публикации |
| P5 | Аудит дефектов | Pass library и findings | Только существующий bug-cause |
| P6 | Тесты и coverage | Scenario registry и receipts | Существующие Cest |
| P7 | Модернизация и rollout | Backlog, метрики, перенос | Отключить новый маршрут |

### P0. Baseline и безопасность

1. Зафиксировать текущие метрики: размер графа, покрытие, число тестов,
   известные дефекты, стоимость прогона.
2. Подготовить фикстуры: незнакомый JS или Python проект, legacy PHP проект,
   seeded-bug проект, проект с противоречивыми требованиями, multi-tenant
   проект.
3. Ввести feature flag `knowledge_v1`.
4. Исправить известные дефекты входа business-analyst из плана 02, K1.
5. Запретить автоматический `approved` до прохождения semantic gate.

Приемка: baseline воспроизводится, фикстуры работают, флаг выключен по
умолчанию.

### P1. Канон и схемы

1. Расширить JSONdoc contract типами `claim`, `finding`, `scenario`, `decision`,
   `link`.
2. Добавить stable IDs, provenance, evidence refs и три оси статусов.
3. Реализовать миграцию существующего registry без потери истории.
4. Добавить `knowledge list/get/apply/related/rebuild`.
5. Проверить CAS, журнал и render на новых типах.

Приемка: round-trip, конфликт версий, откат, старые данные читаются.

### P2. Очередь и coverage

1. Реализовать SQLite provider и DDL из документа 04.
2. Добавить claim, heartbeat, retry, dead-letter, recovery, generation.
3. Перевести `project-doc` и `doc-verify` на общий provider.
4. Реализовать coverage по осям.
5. Добавить crash-тест и тест двух worker.

Приемка: ноль потерянных единиц, ноль дублей, восстановление после kill -9.

### P3. Bootstrap и инвентаризация

1. Создать skill `codebase-scan`.
2. Реализовать project manifest и detection стека.
3. Реализовать discovery entrypoints без опоры только на CBM routes.
4. Собрать команды install/build/lint/test/run и проверить их или пометить
   `unknown`.
5. Построить первичную карту и coverage report.

Приемка: незнакомый проект без CopyTrust-словаря получает карту; ни один
entrypoint не выдуман.

### P4. Извлечение знаний

1. Обобщить `business-analyst` на источники code, docs, tests, runtime.
2. Реализовать evidence slice и строгий JSON ответа модели.
3. Разделить structural, semantic и behavior gates.
4. Реализовать invalidation по source hash.
5. Опубликовать domain docs, ER и state diagrams.

Приемка: правило из кода без Jira; противоположная цитата отклонена; stale
запись не попадает в active view.

### P5. Аудит дефектов

1. Создать skill `bug-hunt` и pass library.
2. Подключить semgrep, phpstan, graph queries, DB constraints, runtime logs.
3. Реализовать finding schema, severity, confidence, fingerprint и dedupe.
4. Реализовать triage и false-positive workflow.
5. Подготовить seeded-bug фикстуру.

Приемка: известные seeded bugs найдены; S0/S1 воспроизводятся; ложные
срабатывания учтены.

### P6. Тесты и покрытие

1. Реализовать scenario contract и oracle kinds.
2. Связать `prepare-task-test` и `test-task` с knowledge.
3. Реализовать run receipts и coverage matrix.
4. Проверить, что regression в seeded-фикстуре ловится тестом.
5. Добавить отчет о пробелах.

Приемка: claim -> scenario -> test -> run прослеживается; `oracle_unknown` не
превращается в assert.

### P7. Модернизация и rollout

1. Создать skill `modernize`.
2. Реализовать backlog с severity, effort, risk, metric и characterization test.
3. Подключить `prepare-plan` и `task-code-review`.
4. Обновить docs харнеса, registry, зеркала и parity.
5. Провести пилот на двух проектах.
6. Проверить перенос в чистый проект без чужих данных.

Приемка: backlog измерим; после исправления нет новых S0/S1; метрики улучшены;
перенос не содержит проектных данных.

Порядок первого спринта: P0, затем P1 и P2. Нельзя начинать P4 до прохождения
P1 и P2, иначе claims пишутся без CAS и durable queue.

### 10.4. Карта файлов

Канон правится только в `.cursor/` и `.agents/`. Зеркала `.codex/`, `.kilo/`,
`.agents/rules`, `.qoder/` и `.qwen/` генерируются синком и вручную не правятся.

| Путь | Действие | Назначение |
|---|---|---|
| `.agents/skills/knowledge-router/SKILL.md` | Создать | Маршрутизация знаний и общий контракт |
| `.agents/skills/knowledge-router/children/codebase-scan/SKILL.md` | Создать | Bootstrap, manifest, инвентаризация |
| `.agents/skills/knowledge-router/children/knowledge-extract/SKILL.md` | Создать | Claims, evidence, версии |
| `.agents/skills/knowledge-router/children/bug-hunt/SKILL.md` | Создать | Pass library и findings |
| `.agents/skills/knowledge-router/children/modernize/SKILL.md` | Создать | Backlog, метрики, characterization tests |
| `.agents/skills/knowledge-router/scripts/knowledge_cli.py` | Создать | CLI `knowledge` |
| `.agents/skills/harness-core/scripts/lib/knowledge/ids.py` | Создать | ULID, fingerprints, stable refs |
| `.agents/skills/harness-core/scripts/lib/knowledge/store.py` | Создать | JSONdoc adapter и CAS |
| `.agents/skills/harness-core/scripts/lib/knowledge/queue.py` | Создать | SQLite provider, lease, retry |
| `.agents/skills/harness-core/scripts/lib/knowledge/coverage.py` | Создать | Оси покрытия и gap reasons |
| `.agents/skills/harness-core/scripts/lib/knowledge/render.py` | Создать | Markdown и Mermaid views |
| `.agents/skills/business-analyst/SKILL.md` и `scripts/` | Изменить | Source adapters code, docs, tests, runtime |
| `.agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1` | Изменить | Общий queue provider |
| `.agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1` | Изменить | Общий queue provider |
| `.agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1` | Изменить | Завершение work item |
| `.cursor/rules/knowledge.mdc` | Создать | Триггеры и маршрут knowledge-router |
| `.cursor/rules/mcp/codebase-memory-mcp.mdc` | Изменить | Роль CBM в knowledge-маршруте |
| `.doc/harnes/index.md` | Изменить | Карточки новых скилов и plan |
| `.doc/harnes/state/05-scripts.md` | Изменить | Очередь provider после внедрения |
| `.doc/harnes/state/17-business-analyst.md` | Изменить | Source adapters и новые ограничения |

После правки канона выполняется
`.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`
и проверка parity.

---

## 11. Приемочные проверки

### 11.1. Фикстуры

| Фикстура | Что проверяет |
|---|---|
| Unknown JS или Python repo | Bootstrap без проектных словарей |
| Legacy PHP repo | Парсерные пробелы, `.tpl`, cron, CLI |
| Seeded-bug repo | Precision и recall pass library |
| Contradictory requirements repo | Отказ от `approved`, quarantine |
| Multi-tenant repo | Изоляция данных и authz |
| Race-condition repo | Воспроизведение конкурентного дефекта |
| N+1 repo | Производительность и доказательство |

### 11.2. Обязательные отрицательные сценарии

1. Цитата подтверждает противоположное утверждение: semantic gate отклоняет.
2. Метод существует, но поведение противоположное: behavior gate не дает `passed`.
3. Два worker берут одну единицу: второй получает отказ или другую единицу.
4. Worker убит во время записи: generation не публикуется, lease восстанавливается.
5. Изменен extractor: старые claims получают `stale`, views не active.
6. Проект A пытается прочитать claims проекта B: отказ.
7. В evidence попадает секрет: redaction блокирует публикацию.
8. Бюджет исчерпан: единица получает `gap`, а не ложную полноту.
9. Oracle неизвестен: тест не генерирует утверждение.
10. S0 finding без воспроизведения: не закрывается как `confirmed`.

### 11.3. Definition of Done

1. Все единицы объявленной области имеют статус и причину.
2. Высокорисковые процессы имеют claims, scenarios и тесты.
3. Все S0/S1 findings воспроизведены или доказаны.
4. Docs свежие, source hash совпадает.
5. Coverage показывает пробелы, а не только процент.
6. Очередь прошла crash-тест и тест двух worker.
7. Перенос в чистый проект не содержит чужих данных.
8. Стоимость укладывается в бюджет.

---

## 12. Метрики

| Метрика | Формула | Цель |
|---|---|---|
| Inventory coverage | covered / (covered + gap + skipped) | 100 процентов объявленной области |
| High-risk claim coverage | процессы с claims / все процессы высокого риска | Не меньше 80 процентов на пилоте |
| Test binding | approved claims с исполняемым тестом / все approved claims | Не меньше 70 процентов |
| Finding precision | confirmed / все triaged findings | Не меньше 85 процентов |
| Finding recall | найденные seeded bugs / все seeded bugs | Измеряется на фикстуре |
| Doc freshness | views с совпадающим hash / все views | 100 процентов |
| Queue reliability | завершенные без потерь / все единицы | 100 процентов в crash-тесте |
| Regression escape | дефекты, найденные после релиза / все дефекты | Снижение по проекту |
| Cost per unit | токены и время / единица | В проектном бюджете |
| Modernization delta | метрика до и после | Улучшение с обратимостью |

Нельзя сворачивать разные gaps в один процент. Отдельно считаются: нет
требования, нет oracle, нет теста, нет binding, тест не запускался, среда
неподходящая, результат failed, динамическая связь не разрешена.

---

## 13. Риски и ограничения

1. Статический граф неполон: DI, callbacks, магические методы, шаблоны,
   generated code и runtime config.
2. Legacy PHP и JS содержат файлы с ошибками парсинга и минифицированные
   библиотеки.
3. Требования могут отсутствовать или противоречить друг другу.
4. Модель может дать ложное утверждение или пропустить дефект.
5. Смысловая проверка не доказывает полноту.
6. Security-аудит не заменяет pentest; performance-аудит не заменяет load test.
7. Большой репозиторий требует sampling и risk-based очереди.
8. Модернизация без characterization tests повышает риск регрессии.
9. SOLID и OOP контекстны; механическое применение вредит.
10. Стоимость и время растут с глубиной; бюджет обязателен.

---

## Связи

- [Общий план развития харнеса](../plan.md) - аудит, архитектура, WP0-WP12.
- [Планирование и аудит на субагентах](./01-subagent-planning-and-audit.md) - независимые аудиты, роли, frozen inputs.
- [Индексация и база бизнес-знаний](./02-project-index-and-business-knowledge.md) - identity, три оси, lifecycle, пилот.
- [Воспроизводимое web-тестирование](./03-web-testing-system.md) - oracle, cases, runners и receipts.
- [Хранилище знаний и очередь работ](./04-knowledge-store-and-queue.md) - схемы, DDL, CLI, lease и восстановление.
- [Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md) - pass library, severity, triage, backlog.
- [Business analyst](../state/17-business-analyst.md) - текущая реализация и известные ограничения.
- [JSONdoc](../jsondoc.md) - контракт хранения и представлений.
- [Тесты](../tests.md) и [testaudit](../testaudit.md) - стандарты проверки.

---

## Известные проблемы и ограничения

Документ проектирует подсистему; новые скилы, схемы, очередь и provider еще не
внедрены. Числовые цели являются стартовыми параметрами пилота, а не
гарантией. Полнота ограничена объявленной областью и доступными evidence.
Документ не заменяет проектное решение о бизнес-правилах и не дает права
автоматически утверждать требования.

---

## История изменений

- 2026-11-06: создан мастер-план сканирования, базы знаний, аудита, тестов и модернизации. Собраны находки по CBM, codegraph, business-analyst, очередям и тестам; зафиксированы границы обещаний и порядок внедрения P0-P7.
- 2026-11-06: план сделан готовым к внедрению: добавлены цели и требования, критерии успеха, архитектура, форматы хранения, очередь SQLite, скилы, сценарии, приемка и метрики.
- 2026-11-06: добавлены заимствования из Sourcegraph, решение против отдельной graph DB и карта файлов внедрения. Зафиксированы канонические пути и порядок синка зеркал.

#harness #scan #business-logic #audit #testing #storage #queue
