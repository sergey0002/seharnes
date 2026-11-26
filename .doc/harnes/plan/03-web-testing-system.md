# Воспроизводимое тестирование web-проектов PHP и JavaScript

<!-- meta
type: plan
status: draft
updated: 2026-11-10
related: [../plan.md, ./deepseek.md, ./01-subagent-planning-and-audit.md, ./02-project-index-and-business-knowledge.md, ./04-knowledge-store-and-queue.md, ../tests.md, ../testaudit.md]
tags: [harness, testing, business-rules, browser, portability]
-->

## Суть

Сохранить существующие Codeception, PHPUnit, Page/Step и машинные артефакты прогонов. Перестроить выбор тестов, хранение постоянной регрессии и условия готовности. Создание второго браузерного стека по умолчанию не требуется.

Целевая система связывает версионированное бизнес-правило, сценарий процесса, конкретный тест и результат запуска на конкретной версии приложения. Задача добавляет изменения к общей регрессии проекта. Проверка без номера задачи использует тот же механизм с локальным change ID.

Детерминированный runner выполняет тесты вне цикла модели. Модель получает короткий вердикт и раскрывает подробности только при ошибке. Написание, аудит тестов, расследование падений и чтение результатов всё равно расходуют токены.

Этот документ задаёт проект улучшения. Код, конфигурации, базы данных и действующие тестовые наборы при подготовке документа не менялись. Запуск продуктовых тестов, браузера и сервисов не выполнялся. Существование конфигурации не подтверждает готовность стенда.

**Граница ответственности:** harness управляет контрактом проверки и подключением провайдеров; проект владеет сценариями, тестами, фикстурами, окружением и CI/CD. Расписание полного прогона и deployment gates остаются проектными решениями.

## 2. Три разных объекта проверки

| Контур | Что доказывает | Пример | Чего не доказывает |
|---|---|---|---|
| H: тесты харнеса | Runner, selection, receipt и адаптер работают правильно | Подмена source hash делает receipt устаревшим | Правильность оплаты или авторизации приложения |
| P: тесты продукта | Поведение приложения соответствует проверенному контракту | Чужой пользователь не отправляет чужой draft | Что агент выбрал все затронутые сценарии |
| E: agent-evals | Агент соблюдает workflow на контрольных заданиях | Малая модель останавливается при отсутствующем oracle | Отсутствие всех ошибок продукта |

Для H, P и E нужны отдельные результаты и метрики. Зелёный selfcheck харнеса нельзя показывать как успешное тестирование задачи. Успешный продуктовый тест не доказывает качество всех последующих планов модели.

Общий workflow планирования и независимого аудита описывает [документ 01](./01-subagent-planning-and-audit.md). Происхождение и версии бизнес-правил описывает [документ 02](./02-project-index-and-business-knowledge.md).

## 3. Что уже существует и что проверено чтением

Обзор начат через свежие дайджесты Harness Mirror для `test-task` и `browser-verify`. Исходники проверены в `.codex/skills/`; этот каталог является представлением, внедрять изменения нужно в фактическом каноне. Статические циклы ссылок Mirror не объявляются рекурсией исполнения.

| Компонент | Фактический механизм | Решение |
|---|---|---|
| `testing-router` | Разделяет подготовку теста, запуск браузера и оркестрацию | Сохранить, добавить taskless и process modes |
| `test-task` | Режим отдельного R/S и финальная проверка задачи | Сохранить этапность; перестать требовать номер Jira для любого изменения |
| `prepare-task-test` | Собирает Cest из Page/Step, добавляет AC-матрицу и PHPUnit для серверных веток | Разделить test contract, oracle audit и генерацию методов |
| `browser-verify` | Codeception первым; Playwright MCP для непокрытых веток | Сохранить отсутствие дублирования; заменить автоматический выбор браузера для любой дыры |
| `task-test.sh` | Preflight, Codeception, артефакты, соседи, итоговый verdict | Сделать совместимым frontend к общему runner, не выбрасывать рабочую реализацию |
| `gates.py` | G0-G13, требования, ветки, наличие методов, машинные результаты | Удалить текстовые заменители доказательства запуска |
| `qa-manifest.py` | Hash кода, тестов, требований, skill и окружения | Исправить scope тестов и пути; добавить версии фикстур и правил |
| `db-isolation.py` | Только явно заданные reset/cleanup hooks, без придумывания SQL | Сохранить принцип; сделать проверки полноты и safety строгими |
| `run-phpunit.py` | Ищет тесты по соглашению Foo.php -> FooTest.php, запускает в PHP-контейнере | Расширить selection; container/path вынести в project adapter |
| `business-analyst/build_test_impact.py` | Из test_refs и test_specs собирает test-plan | Использовать общий registry; отсутствие метода не означает browser E2E |

### 3.1. Подтверждённый стек проекта

- `composer.json` объявляет PHPUnit `4.8.*`; `vendor/phpunit/phpunit/phpunit` существует. `tests/phpunit.xml` использует legacy bootstrap и coverage configuration. Фактический успешный запуск в этом аудите не подтверждался.
- `.tools/codeception/composer.json` объявляет Codeception `^5.3`, PHP `^8.2`, WebDriver и Db. `.tools/codeception/vendor/bin/codecept` существует. Это отдельный runtime от legacy приложения и его PHPUnit.
- `.tools/codeception/tests/Acceptance.suite.yml` включает WebDriver Chrome, Asserts, Db и VisibleBrowser. `populate=false`, `cleanup=false`; автоматический импорт дампа отключён. Изоляцию должны подтверждать проектные hooks и фикстуры.
- `package.json` содержит Vue 2, webpack и ESLint scripts. JS unit-test script, Vitest, Jest и `@playwright/test` в manifest не объявлены; локальные package-файлы этих трёх runners в `node_modules` не найдены при точечной проверке. Установка не выполнялась.
- Playwright MCP доступен в каталоге инструментов этой сессии. Доступность namespace не подтверждает авторизацию, нужный browser context или успешное соединение со стендом.
- `.doc/qa/flows`, `.doc/qa/fragments.md` и `.tools/codeception/tests/Support/{Page,Step}` дают существующую базу повторного использования.

Pest и новый JS unit runner не считать установленными. Выбор или обновление framework должен учитывать PHP/Node версии проекта, а не последнюю версию документации.

### 3.2. Найденные ограничения текущего подхода

| Наблюдение | Доказательство в просмотренном коде | Последствие и исправление |
|---|---|---|
| Регрессионные Cest задачи объявлены локальными и вне git | `prepare-task-test/SKILL.md`, разделы хранения и Hard rules | Другой разработчик не воспроизведёт защиту. Постоянные тесты хранить в versioned suite проекта |
| G1 способен вернуть passed по наличию файлов без запуска | `gates.py`, `g1_unit`: fallback с текстом `прогон не запускался` | Этот результат заменить `not_run`; наличие файла подтверждает discovery, не проверку |
| Red-first и часть требований подтверждаются отметками | `gates.py`, `g7_literals`, `g11_red_first` | Для строгой готовности нужны связанные run receipts; заметку оставить пояснением |
| G12 уже сверяет машинные артефакты и fingerprint | `gates.py`, `g12_machine_run` | Сохранить строгий агрегат. Нельзя выдавать слабый G1 за общий false-green без проверки G12 |
| Отсутствие любого existing method превращается в Playwright gap | `business-analyst/scripts/build_test_impact.py`, `build` | Ошибка слоя: формула требует unit, права доступа API, видимость UI browser |
| BA ищет Page/Step только под `.doc/qa` | `build_test_impact.py`, `load_qa_layers` | Существующие Page под `.tools/codeception/tests/Support` не попадают в этот поиск. Нужен registry paths |
| Manifest тестов не включает root `tests/lib` как test scope | `qa-manifest.py`, `test_files` | PHP-тесты попадают в общий code hash, но test fingerprint неполон. Добавить все provider test roots |
| Manifest skills использует старые плоские `.cursor/skills/{name}` | `qa-manifest.py`, `skill_files` | Resolver должен брать активный package manifest, иначе hash пустого списка маскирует изменения workflow |
| DB matrix parse error трактуется как isolation not required | `db-isolation.py`, `required` | Невалидный input должен давать config_error, без перехода к запуску |
| Aggregate isolation допускает passed при одной passed фазе | `db-isolation.py`, агрегирование `phase_statuses` | Требовать отдельные before и after receipts; failed cleanup блокирует обычную готовность |
| PHPUnit selection опирается на одноимённый класс | `run-phpunit.py`, `related_tests` | Тест общего процесса с другим именем не будет найден. Дополнить явной картой и связями правил |

Наблюдения получены статическим чтением, кроме отдельно описанной проверки Mirror. Инциденты базы из комментария suite не воспроизводились и не считаются новым runtime evidence.

## 4. Целевая архитектура: один контракт, несколько провайдеров

Слой harness принимает `change-set`, `test-contract`, `selection` и `environment-ref`. Провайдер выполняет точную команду своего framework и возвращает нормализованный receipt. Проект задаёт конкретные пути, fixtures, роли и адреса.

| Capability | Для CopyTrust первым | Для нового проекта |
|---|---|---|
| `test.unit.php` | Существующий PHPUnit в совместимом runtime | Установленный PHPUnit/Pest после проверки версии |
| `test.unit.js` | Не настроено; не выдавать ESLint за unit tests | Существующий runner; новый устанавливать отдельным решением |
| `test.integration` | PHPUnit/Codeception с проектными fixtures | Установленный runner и проектные adapters |
| `test.browser` | Codeception WebDriver | Codeception либо Playwright Test, один default |
| `browser.explore` | Playwright MCP при разрешённом доступе | Доступный интерактивный browser tool |

Codeception WebDriver выполняет браузерные сценарии, включая JavaScript приложения. Поэтому PHP-репозиторий не обязан мигрировать на Playwright, чтобы проверять Vue в настоящем браузере. Основание: [Codeception WebDriver](https://codeception.com/docs/modules/WebDriver).

Playwright Test полезен как переносимый JS/TS provider для проекта, который его выбрал. Playwright MCP остаётся средством исследования и диагностики. Запись шагов MCP в чат не заменяет постоянный тестовый файл и runner receipt.

Не добавлять отдельный универсальный язык тестов, который повторяет PHP/JS framework. Общий контракт описывает сценарий, fixture refs и ожидаемые эффекты; исполняемые тесты остаются нормальным кодом выбранного framework.

## 5. Постоянная регрессия проекта и временные результаты задачи

### 5.1. Что хранить в version control

- Сценарии бизнес-процессов и их версии, oracle contracts, связь с бизнес-правилами.
- Unit, integration, API и browser test source, Page/Step, fixture factories и безопасные mock contracts.
- Project provider configuration, lockfiles и версии runtime images без секретов.
- Явные карты `file/symbol -> process/scenario`, reviewed visual baselines и тестовые схемы.

Не переносить реальные клиентские данные, авторизационные cookies, production dumps и приватные screenshots в постоянный набор.

### 5.2. Что остаётся временным

Результаты конкретного запуска, stdout/stderr, browser traces, screenshots падения, временные fixtures и локальные investigation scripts. Политика хранения задаёт TTL, лимит диска и редактирование персональных данных.

Задачный Cest можно создать в рабочей зоне. До закрытия задачи регрессионно полезный тест переносится в versioned suite и получает стабильный scenario ID. Task folder хранит ссылку, change delta и receipts. Нельзя завершить перенос, оставив постоянную защиту только симлинком на локальную `.doc/tasks`.

`task_id` необязателен. Для небольшого чата создаётся локальный `change_id`, связанный с repo/worktree и diff. Ветка и Jira не создаются автоматически ради запуска теста.

## 6. Реестр процессов: проверять целую бизнес-логику по частям

Проект хранит process registry в выбранном им authored формате. JSON/YAML подходит для автоматического выбора; человекочитаемый view генерируется. Канон не должен одновременно существовать в двух редактируемых форматах.

Project manifest назначает единственный canonical scenario-contract source и общую schema/ID policy с документом 02. Business graph в JSONdoc хранит ссылки на этот источник и генерируемые проекции, если сам не выбран canonical store. Независимые редактируемые копии одного scenario contract в YAML и JSONdoc запрещены.

Одна запись сценария содержит:

- `process_id`, стабильный `scenario_id`, `contract_version`, lifecycle и owner. Это ScenarioRef из документа 02; версия runtime binding хранится отдельно.
- `rule_refs` с версиями, требования и независимый источник ожидаемого результата.
- Роли, предусловия, fixture refs, action, ожидаемые ответы, изменения и запреты изменений состояния.
- Конкретные case IDs для границ, отказов и повторов; provider и test method refs.
- Связи с routes/symbols/tables/queues и покрытие этих связей: known, partial или unknown.
- Test data classification, isolation strategy, timeout, внешние сервисы и side-effect permissions.

Текст бизнес-правила не копировать в каждый тест целиком. Тестовый пакет включает точную версию и нужное ожидание; исходный rule ref позволяет проверить происхождение.

### 6.1. Согласованный пример без привязки к CopyTrust

Процесс: создание заявки на публикацию. `BR-PUBLISH-001` v1 определяет отправку собственного draft, повтор с idempotency key и запрет чужой отправки. `SC-PUBLISH-001` связывает три case с источниками oracle.

| Case ID | Действие | Измеримое ожидание | Первый слой |
|---|---|---|---|
| `CASE-OWNER-NEW` | Владелец отправляет свой draft | Одна заявка, нужный статус, UI показывает успех | Integration плюс browser на пользовательский путь |
| `CASE-OWNER-REPLAY` | Повторяется операция с тем же ключом | Заявка не дублируется, возвращается прежний результат | Integration; browser повтор клика только при UI-риске |
| `CASE-FOREIGN-DENIED` | Другой пользователь отправляет этот draft | Предписанный отказ, отсутствуют изменения и утечки данных | API/integration; browser проверяет видимость действия |

HTTP-коды, таблицы и routes определяет project adapter по проверенным требованиям. Документ не придумывает продуктовую схему. Один case допускает проверки на нескольких слоях, если каждый слой доказывает отдельный риск.

### 6.2. Что означает whole-project проверка

Whole-project прогон исполняет все активные стабильные сценарии и необходимые слои проекта, затем публикует отдельно непокрытые правила, quarantined tests и неподдержанные capabilities. Термин не означает доказанную полноту всей бизнес-логики.

Для полной регрессии нужен каталог процессов с ответственными и версиями. Автоматическое извлечение кода находит кандидаты и связи; утверждать ожидаемое бизнес-поведение только по текущей реализации нельзя. Разделение normative и observed знаний описано в [документе 02](./02-project-index-and-business-knowledge.md).

## 7. Жизненный цикл: контракт до кода, результат после каждого шага

1. **Resolve change.** Зафиксировать требования, worktree, scope и риск; найти затронутые process/scenario/rule refs. Не читать все QA flow-документы.
2. **Prepare test contract.** Перечислить случаи, ожидаемые эффекты и prohibited effects. Отдельно определить fixture, слой и метод доказательства.
3. **Audit oracle.** Независимый аудитор проверяет ожидания по требованиям и бизнес-правилам. Автор реализации не должен единолично переписать тест под свой код.
4. **Build/reuse tests.** Найти существующие методы, добавить только отсутствующие cases. Дешёвая модель получает ограниченный пакет со стабильными IDs, complete expected values и разрешёнными файлами.
5. **Expected RED.** Для бага новый тест на baseline должен падать именно на целевом assert. Ошибка подключения, синтаксиса или fixture не является RED.
6. **Implement one step.** Исполнитель меняет один согласованный шаг и не расширяет scope. Проверяется небольшой набор тестов шага и статических checks. После shared/default/signature/state изменения сразу добавляются затронутые инварианты; их первый запуск не откладывается до конца задачи.
7. **Affected-process regression.** После завершения шагов запускать затронутые бизнес-сценарии и защитный smoke. Общий green шага не закрывает shared-flow regression.
8. **Final browser.** Любое изменение UI или пользовательского browser flow проверяется соответствующим сценарием в реальном приложении. Успешный Cest в этом прогоне уже выполняет требование; повторять его в MCP не нужно.
9. **Document and attest.** Сохранить delta, постоянные tests, receipts и remaining gaps. Если документация меняет требование или test code, инвалидировать связанные проверки; повторный полный suite после чисто текстовой правки не обязателен.

Для новой возможности проверенный negative control показывает чувствительность теста к преднамеренно неверному результату или отсутствующей функции в изолированной fixture. Он не заменяет проверку baseline и интегрированного приложения. Если настоящий RED объективно неприменим, project policy отдельно принимает `proof_mode=negative_control` с причиной и необходимыми дополнительными checks. Недоступный runner/стенд остается blocked. Отсутствие baseline нельзя обозначать `red_passed`.

Ни одна модель не получает разрешения исправлять падающий assert заменой expected value без нового oracle review. Два независимых агента также могут разделить ошибочное предположение; вывод проверяется источником и экспериментом.

## 8. Выбор тестов: объединение сигналов с явными пробелами

Runner строит selection как объединение:

1. Явные AC/case изменения и mandatory project tests.
2. Прямая карта files/symbols к scenarios и provider test files.
3. Связанные rules, process transitions и shared contracts.
4. Доступный граф callers/dependencies, включая изменённые schema и fixtures.
5. Малый стабильный smoke для критических путей проекта.

Каждый выбранный тест получает `selection_reason`. Отдельно сохраняются `unknown_edges`, stale index, dynamic dispatch и unmapped changes. Нулевой результат графа при отсутствии покрытия не означает отсутствие регрессии.

Если недостаёт индекса или карта неполна, расширить выбор до доменного набора. Для shared auth, денег, migrations, concurrency или unknown domain запускать более широкий набор согласно project policy либо фиксировать blocked coverage. Дорогой full suite запускается по запросу, расписанию или проектной risk policy. Harness не создаёт CI/CD расписание.

| Изменение | Минимальный осмысленный слой | Дополнительный риск |
|---|---|---|
| Чистая формула | Unit с граничными значениями | Integration при зависимости от округления/хранения |
| Авторизация | API/integration с двумя ролями и отсутствием side effects | Browser на доступность и маршрут действия |
| SQL/транзакция | Integration на изолированной БД | Повтор/конкуренция и migration совместимость |
| Vue состояние/валидация | JS unit/component, если provider настроен | Browser для связки формы, сети и сервера |
| CSS/шаблон | Browser DOM и geometry/visual assertions | Viewports и доступность затронутого элемента |
| Только документация | Links/schema/render, если applicable | Product tests только при изменении контрактов/fixtures |

Повторять один assert в PHPUnit, Cest и MCP ради числа проверок не нужно. Unit права доступа и browser проверка реального маршрута имеют разную цель и не являются бессмысленным дублем.

## 9. Изоляция, воспроизводимость и безопасность

### 9.1. Данные и роли

Каждый run получает namespace и синтетические аккаунты: owner, foreign и нужные service roles. Factory создаёт только необходимые строки; project adapter задаёт допустимые fixtures и cleanup. Схему БД подтверждает mysql `describe_table`; произвольный SQL нельзя выводить из предположений.

HTTP/browser запрос приложения использует другое соединение. Транзакция в процессе теста не гарантирует откат записей web-сервера. Это ограничение прямо отмечает [Codeception Data](https://codeception.com/docs/Data). Предпочтительны disposable database/schema либо lease изолированного стенда с проверенным namespace cleanup.

Обязательные before/after phases имеют собственные receipts. Cleanup выполняется через finally и независимо от assert failures. Неуспешная очистка оставляет run failed/contaminated и запрещает повторное использование environment lease.

`finally` не гарантирует очистку при SIGKILL, потере процесса или машины. Истекший без after receipt lease становится quarantined, а не автоматически свободным. Отдельный разрешенный reconciler проверяет namespace и восстанавливает среду либо уничтожает disposable environment. До успешного reconciliation другие runs этот lease не используют.

Env allowlist должна явно разрешать target URL, database identity и допустимые внешние hosts. Production и неизвестная DB identity блокируют mutating tests. Generic shell reset hook без target validation не считается достаточной защитой.

### 9.2. Время, очереди и внешние системы

- Фиксировать clock, timezone и random seed, когда от них зависит ожидание. PHP и browser clock согласовываются отдельно.
- Await проверяет конкретное бизнес-состояние с timeout; фиксированный sleep не доказывает готовность.
- Queue job содержит run correlation ID; runner дожидается результата или выдаёт timeout с последним состоянием.
- Платежи, почта и сторонние APIs заменяются sandbox/mock contract, если live интеграция не разрешена project policy. Mock-проверка не выдаётся за live integration.
- Повтор теста не скрывает первый провал. Сохраняются все attempts; flaky статус отличен от passed.

### 9.3. Браузер и селекторы

Сохранить Page для локаторов и действий экрана, Step для бизнес-переходов. Registry хранит карту сценария к Page/Step; поиск не должен сканировать весь QA каталог на каждом запросе.

Выбирать доступные role/name и стабильные существующие test IDs. Scoped CSS/XPath остаются fallback для legacy UI. Доступ к `Vue.__vue__` считать хрупким исследовательским обходом, а не основной проверкой публичного поведения.

Новый `data-test` допускается только как согласованная небольшая продуктовая правка; массовое добавление атрибутов ради harness не требуется. Проверка реально отрендеренного атрибута обязательна.

Playwright рекомендует изолированные тесты и ожидания наблюдаемого состояния; их применение уменьшает зависимость от случайной скорости страницы. Эти свойства не заменяют серверную DB-изоляцию. Основание: [Playwright Best Practices](https://playwright.dev/docs/best-practices), [Browser contexts](https://playwright.dev/docs/browser-contexts).

Скриншот без assert не доказывает правильную геометрию. Для CSS-дефекта проверять нужный viewport, bounding boxes, перекрытие, scroll и утверждённый visual baseline. Новый baseline принимает человек или отдельный согласованный review, а не тот же агент автоматически. Основание для snapshot-механики: [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots).

Headed/headless является параметром project environment. Сохранить текущий требуемый видимый Chrome до отдельного решения пользователя. Portable core не должен навязывать WSLg и фиксированные порты всем проектам.

## 10. Run receipts и короткий вывод модели

Один provider run возвращает JSON с `run_id`, статусом, test/case IDs, счётчиками, first failure и artifact refs. Человеку достаточно: что проверено, что не проверено, почему и какой следующий шаг.

Receipt содержит project/worktree/work/scope/stage/run IDs, optional task_ref, fingerprint кода и dirty diff, test source, contract/rule/scenario versions, fixture schema/seed, dependencies/lockfiles, runtime image и browser version, build assets, runner version, environment identity и selection policy. Секретные значения в receipt не записываются.

Нужна проверка связи served build с текущим source/build hash. Зелёный браузер на старых JS assets не подтверждает свежую правку. Удалённый стенд должен отдавать безопасный build identity либо подтверждаться проектным adapter другим способом.

Fingerprint стенда проверяется до и после run либо среда удерживается immutable deployment lease. Изменение build, config или данных вне разрешенных fixture переходов во время запуска делает результат неприменимым к заявленному snapshot. Успешные assertions такого запуска не закрывают свежую проверку.

| Статус | Значение | Может участвовать в итоговой готовности |
|---|---|---|
| `passed` | Нужные assert выполнены на актуальных inputs | Да |
| `failed` | Наблюдаемое ожидание нарушено | Нет |
| `blocked` | Не готовы среда, разрешения или обязательная fixture | Нет |
| `not_run` | Запуск ещё не выполнялся | Нет |
| `not_required` | Слой неприменим по проверенному contract/risk | Да, с причиной |

Canonical run statuses ограничены таблицей. `flaky` хранится отдельно как классификация attempts; `stale` описывает applicability/verification_status receipt после изменения inputs. Исторический `run_status=passed` не переписывается, но устаревший receipt не закрывает свежую проверку. Project policy определяет допустимость нестабильного результата; критический сценарий нельзя скрыть общим зелёным агрегатом.

Coverage reducer сопоставляет точный набор proof slots: `(scenario_id, contract_version, case_id, layer, binding_id, config/role scope)`. Один case может требовать integration и browser результаты. Passed API binding не закрывает обязательный browser slot того же case. Test method rename меняет binding, но не бизнес-case ID. Receipt сохраняет реально исполненные binding/assertion IDs, а минимальный пример ниже намеренно не является полной schema.

Attempt receipts пишутся по мере работы. Итоговый run seal с passed публикуется атомарным manifest только после всех обязательных after/cleanup receipts и повторной проверки fingerprints. До seal run остается incomplete/not_run с промежуточными результатами. Сбой cleanup или публикации не позволяет читателю увидеть итоговую готовность раньше завершения проверки.

Пример минимального receipt, поля иллюстративные:

```json
{
  "schema": "test-receipt/1",
  "project_id": "project-A",
  "worktree_id": "worktree-A",
  "work_id": "local-change-17",
  "scope_id": "publish",
  "stage_id": "R2",
  "run_id": "run-001",
  "task_ref": null,
  "run_status": "passed",
  "applicability": "current",
  "scenario_id": "SC-PUBLISH-001",
  "contract_version": 1,
  "case_ids": ["CASE-FOREIGN-DENIED"],
  "rule_refs": [{"rule_id": "BR-PUBLISH-001", "version": 1}],
  "attempt_classification": "stable",
  "fingerprint_ref": "inputs.manifest.json",
  "artifact_refs": ["provider-results.json"]
}
```

Не определять результат только по exit code shell или `green` из старого run directory. Проверяются достаточное число реально запущенных случаев, отсутствие неожиданного skip и fingerprint. Missing receipt, zero collected tests и parse error не становятся passed.

Полные логи сохраняются локально. На успех модель получает агрегат; на падение только failing case, assert diff и небольшой хвост диагностики. Trace/screenshot открываются адресно. Для Playwright это поддерживает [Trace Viewer](https://playwright.dev/docs/trace-viewer); включение и retention задаются project policy.

## 11. Что менять в конкретных скилах и скриптах

Пути в таблице относительно канонического каталога skills. Перед внедрением resolver обязан определить канон проекта. Генерируемые `.codex/skills` вручную не менять.

| Компонент | Конкретная работа | Контракт результата |
|---|---|---|
| `testing-router/SKILL.md` | Маршруты contract, generate, run, process-regression, full-project | Taskless запрос не требует Jira |
| `prepare-task-test/SKILL.md` | Ожидания и oracle audit до генерации; durable source вместо запрета commit | Case имеет rule/source refs, layer, method и expected effects |
| `test-task/SKILL.md` | Общий change ID, выбор по риску, отдельные step/final modes | Тестирование server-only не требует Cest |
| `browser-verify/SKILL.md` | Убрать утверждение 0 tokens; browser required при UI; не дублировать свежий Cest | Выполнен реальный целевой browser case или blocked |
| `test-task/scripts/task-test.sh` | Делегировать provider runner и сохранять совместимый CLI | Existing команды работают; task/process scopes различаются |
| `test-task/scripts/gates.py` | Удалить passed по файлам/галочкам; uniform statuses; проверка всех mandatory cases | Только актуальные receipts дают ready |
| `test-task/scripts/run-phpunit.py` | Объединить mapping, graph, rule и explicit tests; убрать fixed container из core | Найден тест процесса с именем, отличным от changed class |
| `test-task/scripts/qa-manifest.py` | Все provider roots, активные skill IDs, environment/build identity | Изменение PHPUnit test или fixtures инвалидирует нужный результат |
| `test-task/scripts/db-isolation.py` | Strict matrix parse, before+after, leased target, sanitation | Invalid matrix и неполный cleanup закрываются fail |
| `test-task/scripts/resolve-neighbors.py` | Перейти от соседней задачи к process/scenario relations | Task ID не обязателен для process regression |
| `test-task/scripts/check-ac-matrix.py` | Case-to-test many-to-many с конкретными assertions | Один case может иметь API и UI evidence без ложного дубля ID |
| `test-task/scripts/make-verdict.py`, `make-report.py` | Нормализованные статусы и ссылки, stale/zero/skip guards | Краткий вывод совпадает с машинным receipt |
| `prepare-task-test/scripts/new-task-test.py` | Генерация temporary/durable target через project manifest | Генератор не создаёт хрупкий symlink как единственную регрессию |
| `business-analyst/scripts/build_test_impact.py` | Scenario registry, реальные Page/Step roots и layer-specific gaps | Отсутствующий unit method не становится browser gap |
| `business-analyst/scripts/impact_rules.py` | Version-aware affected rules и stale anchors | Conflicting rule запрещает автоматическое изменение oracle |
| `documentation-router/.../task-doc` | Записывать delta и verified refs вместо копирования test logs | Документирование не переписывает test result |
| Rules `test-priority`, `test-task` | Contract/oracle/RED/step/process/final порядок | Дешёвый этап не отменяет финальную UI проверку |

Новые helpers добавлять к существующему test-task owner: `select-tests.py`, `run-tests.py`, `validate-test-contract.py`, `verify-run-receipt.py`. Provider adapters отделить от project config. Сначала встроить receipts вокруг действующих scripts; не переписывать все runners одним изменением.

Test-task helpers остаются тонкими CLI/provider wrappers. Общие schema, artifact identity, freshness и verification reducer принадлежат существующему `harness-core/scripts/lib/`, как в документах 01/02 и общем плане. Нельзя скопировать свой reducer в каждый runner и получить разные значения green.

## 12. Внедрение с измеримыми критериями

### P0. Зафиксировать baseline и безопасность

Снять inventory scenarios/providers и контрольные результаты на разрешённой изолированной среде. Сохранить исходные dirty changes пользователя. Подготовить H-fixtures для DB target guard, нулевого collection и stale receipt. Ничего не удалять из рабочего suite.

**Приёмка:** H-tests доказывают запрет production/unknown targets, malformed matrix и incomplete cleanup. SIGKILL до after receipt оставляет lease quarantined; промежуточный passed attempt не публикует run seal. Preflight без DB permission не выполняет mutation. Existing runner совместимость сохранена.

### P1. Durable registry и общий change scope

Добавить стабильные process/scenario/case IDs и adapters для существующих Page/Step. Выбрать один небольшой процесс, перенести его полезные локальные tests в version control без изменения oracle. Поддержать taskless change ID.

**Приёмка:** чистая копия проекта получает тот же scenario set; task delta ссылается на постоянный test method. Ни Jira, ни `.doc/tasks` другого разработчика не нужны для его воспроизведения.

### P2. Oracle и evidence contracts

Ввести contract validator, независимый oracle review, structured RED и step receipts. Исправить G1/text proxies и manifest paths. Существующий G12 сохранить до миграции всех producers.

**Приёмка:** тест с неверным expected value отклоняет oracle audit; connection error не считается RED. Изменение code/test/rule/fixture hash делает результат stale. Zero collected cases блокирует готовность.

### P3. Risk-based selection и реальный браузер

Запустить selector в shadow рядом с текущим выбором; сравнить пропущенные cases и время. Добавить process smoke и gap-aware widening. Проверить связку runtime build identity с нужными JS assets.

**Приёмка:** shared policy change выбирает owner/foreign/replay cases и immediate impacted invariants; stale graph расширяет scope. UI change без актуального browser receipt не получает ready. Свежий Cest не запускается повторно через MCP ради отчёта. Deploy во время run и passed API при missing browser slot не закрывают обязательную проверку.

### P4. Повторяемость и переносимость

Прогнать пилот в исходном проекте и отдельной PHP+JS fixture-кодовой базе с другим layout. Второй browser provider подключать только в отдельном fixture-профиле, не в тот же default suite.

**Приёмка:** одинаковые inputs дают одинаковые case IDs и ожидаемые outcomes; test order permutation не меняет результат. Parallel runs с разными namespaces не пересекают данные. Failure cleanup проверяется fault injection.

### P5. Проверить экономию без снижения качества

Сравнить baseline и новую систему на одинаковых изменениях: 1) формула; 2) доступ чужой роли; 3) JS validation; 4) CSS layout; 5) общий flow; 6) отсутствующий provider; 7) taskless fix. Учитывать непринятые результаты и повторную работу.

Метрики: uncached/cached input и output tokens, число model turns, время runner, selected/executed cases, missed seeded defects, flaky attempts, stale receipts, cleanup failures и ручные вмешательства. Порог экономии утвердить после baseline. Обещание фиксированного процента заранее не давать.

E-eval для малой модели содержит готовый contract и намеренно испорченный fixture ref. Ожидается остановка с точным blocker. Второй E-eval проверяет запрет заменить expected value ради green. Третий проверяет обязательный browser case после изменения UI.

## 13. Источники и границы доказательств

Локальные подтверждения: [test-task](../../../.codex/skills/task-router/children/testing-router/children/test-task/SKILL.md), [prepare-task-test](../../../.codex/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md), [browser-verify](../../../.codex/skills/task-router/children/testing-router/children/browser-verify/SKILL.md).

Проверенные scripts: `task-test.sh`, `gates.py`, `run-phpunit.py`, `qa-manifest.py`, `db-isolation.py`, `business-analyst/scripts/build_test_impact.py`. Большие файлы читались по релевантным функциям; полный построчный аудит всех QA scripts не заявляется. `make-verdict.py` и соседние scripts просмотрены по точкам вызова и структуре, их runtime semantics предстоит проверить H-тестами.

Проверенные конфиги и слои: [PHP dependencies](../../../composer.json), [JS dependencies](../../../package.json), [PHPUnit config](../../../tests/phpunit.xml), [Codeception dependencies](../../codeception/composer.json), [Acceptance suite](../../codeception/tests/Acceptance.suite.yml), [BasePage](../../codeception/tests/Support/Page/BasePage.php). Flow registry и fragments найдены через локальную документацию; все отдельные бизнес-процессы не перечитывались.

Внешние официальные документы проверены 2026-11-06. Принцип Arrange/Act/Assert и отдельного fixture lifecycle описывает [PHPUnit Fixtures](https://docs.phpunit.de/en/12.5/fixtures.html). Документ относится к PHPUnit 12.5 и используется только для принципа; его PHP-синтаксис и API нельзя копировать в текущий PHPUnit 4.8.

Проектные предложения об oracle audit, registry, statuses и selection являются архитектурными рекомендациями этого плана. Официальные framework docs подтверждают возможности инструментов, но не обещают отсутствие регрессий или конкретную экономию токенов.

## Связи

- [Общий план](../plan.md) - аудит текущего подхода и очередность WP0-WP12.
- [Мастер-план сканирования и аудита](./deepseek.md) - очередь, фазы и критерии полноты.
- [Субагентное планирование](./01-subagent-planning-and-audit.md) - stage gates, модели, auditors и packets.
- [Индексы и бизнес-знания](./02-project-index-and-business-knowledge.md) - canonical facts, oracle refs и версии сценариев.
- [Хранилище знаний и очередь](./04-knowledge-store-and-queue.md) - run receipts, coverage и generation.
- [Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md) - findings, regression tests и backlog.
- [Текущий тестовый стандарт](../tests.md) и [testaudit](../testaudit.md) - существующие требования, которые мигрируют через regression fixtures.

## Известные проблемы и ограничения

Новые helpers и schema пока являются проектом. Чтение конфигов не подтверждает установленный и готовый runtime. Перед внедрением нужны разрешенный изолированный стенд, проверка совместимости framework/runtime и H-тесты конкретных adapters. Полнота всей бизнес-логики сайта не выводится из зеленого suite: gaps и исключенные проверки публикуются отдельно.

## История изменений

- 2026-11-10: пути рабочей копии Codeception переведены с `.doc/codeception/` на `.tools/codeception/`.
- 2026-11-06: подготовлен отдельный план web-testing системы: аудит существующих механизмов, постоянные бизнес-сценарии, test-first цикл, доказательные receipts и поэтапное внедрение. Код и продуктовые тесты не запускались и не менялись.
- 2026-11-06: после перекрестной проверки уточнены единый владелец сценариев/reducer, proof slots разных слоев, аварийные leases, финальный run seal и смена build во время проверки.

#harness #testing #business-rules #browser #portability
