# Тестовая система: как устроена и как ей пользоваться

<!-- meta
type: guide
status: actual
updated: 2026-09-26
related: [index.md, browser-setup.md, fragments.md, ../tests.md, ../testanalyze/test-system-plan.md]
tags: [qa, e2e, codeception, gates, workflow]
-->

---

## Суть

Система отвечает на один вопрос: **можно ли отдавать задачу тимлиду и
ручному тестировщику**. Ответ даёт не человек и не отчёт, а набор гейтов,
которые либо зелёные, либо нет.

Состав выведен из разбора 13 задач, которые не приняли с первого раза
(исторический testanalyze/report-plan-test.md).
Каждый гейт закрывает конкретный класс багов, который в этих задачах ушёл
в ручное тестирование.

---

## Четыре команды на задачу

```bash
bash .doc/qa/scripts/check-tests.sh       # секунды, без браузера и стенда
bash .doc/qa/scripts/task-test.sh 2236    # прогон, артефакты, verdict.json
python3 .doc/qa/scripts/gates.py 2236     # готово или нет
bash .doc/qa/scripts/test-batch.sh 15 16 17 # последовательный список задач
```

Быстрый workflow для новых задач:

```bash
python3 .doc/qa/scripts/doctor.py --task 2236 --json
python3 .doc/qa/scripts/branch-audit.py 2236
bash .doc/qa/scripts/task-test.sh 2236 --phase preflight
bash .doc/qa/scripts/task-test.sh 2236 --phase unit
bash .doc/qa/scripts/task-test.sh 2236 --phase browser
python3 .doc/qa/scripts/gates.py 2236 --json
```

`doctor.py` проверяет mounts, контейнеры, PHP/Composer/Doctrine, env и приложение.
Для `preflight` и `unit` браузер не требуется. Для `browser` и полного режима
добавляются проверки ChromeDriver/Selenium и настоящих DB isolation hooks.
`branch-audit.py` показывает незакрытые R/S-сценарии до запуска браузера.

Фазы позволяют не повторять дорогой слой:

| Фаза | Что выполняется | Браузер |
|---|---|---|
| `preflight` | doctor, AC source, static, lint, manifest | нет |
| `unit` | doctor, AC source, task PHPUnit | нет |
| `browser` | preflight + unit + DB isolation + Codeception | да |
| `all` | обратная совместимость, полный pipeline | да |
| `finalize` | verdict/gates для существующего run-dir | нет |

Для полного PHPUnit baseline используйте `QA_PHPUNIT_PROFILE=full` или
`baseline`. Известное падение PHPUnit 4 классифицируется как `baseline_failed`;
оно не смешивается с failure task-specific тестов.

Первую гонять часто, она почти бесплатна. Вторую после каждой значимой
правки. Третью перед тем, как сказать «сделано».

Для релизного набора задач используйте `test-batch.sh`. Он последовательно
запускает для каждого номера `check-tests.sh`, `task-test.sh` и `gates.py`,
сохраняет общий summary и возвращает ошибку, если хотя бы одна задача не готова.
Полный Acceptance suite этот скрипт не запускает.

---

## Раскладка

```
.doc/tasks/{N}/
├── task.md            из Jira
├── plan.md            от prepare-plan
├── test.md            сценарии + чек-лист 13 категорий
├── tests/             тесты задачи           <- в git НЕ идут
│   └── {Slug}Cest.php
└── test-runs/{дата}_{группа}/
    ├── verdict.json   машинный итог прогона
    ├── gates.json     машинный итог гейтов
    ├── checkpoints.jsonl
    ├── run.log
    └── *.png          скриншоты checkpoint()

.doc/codeception/tests/
├── Acceptance/
│   ├── *Cest.php              тесты флоу, не привязанные к задаче
│   └── Task/{N} -> симлинк на .doc/tasks/{N}/tests
└── Support/
    ├── AcceptanceTester.php   вход, фикстуры БД, checkpoint()
    ├── Page/                  селекторы экранов
    └── Step/                  бизнес-сценарии из Page
```

Тесты задач не попадают в git: `.doc/` исключён через `.git/info/exclude`.
Codeception находит их по симлинку (`Finder::followLinks()` включён в
`Loader.php`).

Неймспейс теста — `Tests\Acceptance\Task\T{N}`. Номер в неймспейсе, а не в
имени файла: два `QualityWarningCest` в разных задачах не столкнутся.

То, что уже лежит в `tools/codeception/` и отслеживается git, заморожено.
Новое туда не добавляем, синхронизировать копии не нужно.

---

## Три слоя переиспользования

Тест задачи не пишется с нуля, потому что навигация одна и та же, меняется
только проверяемая логика.

| Слой | Где | Что содержит | Пример |
|---|---|---|---|
| Page | `Support/Page/` | селекторы и примитивы одного экрана | `WizardPage::fillStep2()` |
| Step | `Support/Step/` | бизнес-сценарий из нескольких Page | `DepositionSteps::createDraft()` |
| Actor | `AcceptanceTester` | вход, фикстуры БД, диагностика | `devLoginAsClient()`, `checkpoint()` |
| Cest | `.doc/tasks/{N}/tests/` | только логика конкретной задачи | `QualityWarningCest` |

**В Cest задачи сырых селекторов быть не должно.** Ни XPath, ни
`contains(@class`, ни `document.querySelector`.

Причина не в эстетике. Селектор внутри Cest не сверяется с реестром
`data-test`. Когда шаблон переименует атрибут, `waitForElement()` честно
упадёт, а вот `dontSeeElement()` начнёт проходить **всегда**: тест зелёный,
регрессия не ловится. Селекторы в Page сверяются автоматически.

---

## checkpoint() — что он на самом деле делает

`$I->checkpoint('метка')` после каждого значимого действия собирает:

- скриншот шага
- ошибки консоли (`console.error`, `onerror`, `unhandledrejection`)
- видимые модалки, отдельно модалку ошибки
- тосты `.toasted`
- дельту DOM к предыдущему checkpoint

Пишет строку в `_output/checkpoints.jsonl`, оттуда её забирает `verdict.json`.
Сам тест не валит: это диагностика. Жёсткие проверки — `seeNoConsoleErrors()`
и `dontSeeErrorModal()`.

Этим закрываются категории 6, 8 и 9 чек-листа `tests.md` §7.

---

## Гейты

```bash
bash .doc/qa/scripts/preflight.sh {N}         # smarty clear + max-статика по патчу + check
bash .doc/qa/scripts/task-test.sh {N}         # браузерный прогон
python3 .doc/qa/scripts/gates.py {N}          # готово или нет
python3 .doc/qa/scripts/gates.py {N} --skip-static
python3 .doc/qa/scripts/gates.py {N} --json
```

| Гейт | Что проверяет | Какой баг ловит |
|---|---|---|
| G0 | PHPStan L8 + ESLint patch-max **только строки патча** | кривые правки в море легаси |
| G1 | юнит-тесты задачи, если есть | формулы и расчёты |
| G2 | тест и `test.md` существуют | «проверил руками, тест потом» |
| G3 | последний прогон зелёный | не запускали после последней правки |
| G4 | нет ошибок консоли и модалок | JS-ошибка при внешне рабочем UI |
| G5 | чек-лист заполнен без пустых пунктов | проверили только happy path |
| G6 | есть `seeInDatabase` | UI показал, а в данных не сохранилось |
| G7 | литералы из `task.md` в тестах | проверяли пересказ, а не требование |
| G8 | стенд жив после прогона | тест испортил dev-данные |
| G9 | `.doc/` не в git | тесты утекли в репозиторий |
| G10 | селекторы не мёртвые и не сырые | ложно-зелёный `dontSeeElement` |
| G11 | red-first для задач-ошибок | «фикс» не чинил описанный баг |
| G12 | машинный AC, lint, PHPUnit, DB и hash-контроль: полный набор артефактов run-dir (static, lint, phpunit, ac-check, db-isolation, соседи, comparison, llm-review, manifest) и свежесть fingerprints | зелёный текстовый отчёт без машинных доказательств; прогон stale после правки кода |
| G13 | каждый R из Decomposition закрыт в `test.md` § Ветки логики | этап плана без проверки, склейка нескольких исходов в один AC |

### Локальная статика vs CI (важно)

Всё жёсткое живёт в `.doc/` и **не попадает в git**.

| | CI (GitVerse deploy) | Локаль (preflight / G0) |
|---|---|---|
| PHPStan | level **0**, весь `lib/src`+`admin` | level **8** (до 9), **только строки патча** |
| Frontend check | `yarn lint:basic` на `frontend/entry` | ESLint **patch-max** на js/vue из diff |
| Сборка | `yarn prod` | `yarn prod` если в diff есть `frontend/entry` |
| Cache | `rm templates_c` на стенде после деплоя | `preflight` чистит `templates_c`/`cache` до тестов |

Шкала ESLint: `lint:basic` (CI, мягкий) < `lint:strict` (в репо, CI пока не gate)
< `.doc/qa/eslint/patch-max.js` (локаль, максимум, вне git).

«Vue-тесты» в деплое - это ESLint + `yarn prod`, не jest/vitest. Unit Vue в проекте нет.

PHP на хосте часто нет: сайт в `copytrust-dev-php-apache` (7.1), PHPStan 2.x
через Docker `copytrust-codecept:8.3`. См. cicd.md §9.3 (`../architecture/cicd.md#93-локальный-phpstan-и-eslint-по-патчу`; missing in kit).

G1 и G11 пропускаются, если неприменимы. G7 и G11 проверяются по явной
отметке в `test.md` — решение должно быть записано, а не остаться в голове.

Красный блокирующий гейт означает «не готово», даже если прогон зелёный.
Чинить причину, а не подгонять под гейт.

---

## Скрипты

| Скрипт | Зачем |
|---|---|
| `check-tests.sh` | всё быстрое без браузера: реестр, селекторы, загрузка Cest |
| `preflight.sh` | smarty clear + статика по патчу (max) + опционально yarn prod + check-tests |
| `static-on-diff.py` | PHPStan L8 + ESLint patch-max только по строкам git-diff задачи |
| `task-test.sh` | фазовый прогон, артефакты, `verdict.json` |
| `doctor.py` | fail-fast проверка Docker, PHP, env, app и WebDriver |
| `branch-audit.py` | сравнение R/S из plan.md с test.md |
| `harness-selftest.py` | offline self-test QA scripts и AC dedup |
| `disposable-db.sh` | create/drop отдельной schema-only QA БД |
| `gates.py` | готовность задачи |
| `new-task-test.py` | заготовка Cest и `test.md` по правилам |
| `collect-data-test.py` | реестр `data-test` в `_map/data-test.tsv` |
| `check-selectors.py` | мёртвые селекторы в Page, сырые в Cest |
| `check-tests-load.php` | загрузка Cest, битые симлинки, коллизии классов |
| `make-verdict.py` | сборка `verdict.json` из артефактов |
| `check-ac-matrix.py` | валидация `ac-matrix.json` и AC evidence: ссылки на методы, expected, дубликаты (фазы source/result) |
| `run-phpunit.py` | парные PHPUnit-тесты задачи в контейнере приложения (PHP 7.1, PHPUnit 4.8, `tests/phpunit.xml`) |
| `qa-lint.py` | обязательный ESLint patch-max изменённых `.js`/`.vue` на хосте или в docker `node:22` |
| `qa-manifest.py` | fingerprints входов прогона (код, тесты, требования, skills) и проверка stale run |
| `db-isolation.py` | выполнение явных `QA_DB_RESET_CMD`/`QA_DB_CLEANUP_CMD` для задач с `db_isolation: required` (фазы before/after) |
| `resolve-neighbors.py` | разрешение и валидация обязательных соседних флоу (`required_neighbors` из `ac-matrix.json`) |
| `compare-runs.py` | сравнение прогона с предыдущим: идентичность тестов и AC, статусы, сигнал регрессии |
| `llm-review.py` | опциональный LLM-разбор доказательств прогона; никогда не перекрывает гейты |
| `make-report.py` | сборка единого формального `report.md` прогона из артефактов run-dir |
| `record-history.py` | дозапись итога прогона в `test-runs/history.jsonl` и `test-history.jsonl` |
| `test-batch.sh` | последовательный прогон списка задач (check-tests + task-test + gates, общий summary) |
| `migrate-task-tests.py` | разовый перенос Cest в папки задач |
| `lib.sh` | автодетект окружения, общий для `.sh` |

`lib.sh` инкапсулирует то, что раньше приходилось помнить: хост без PHP 8.2+,
два порта WebDriver (9515 против 4444), сеть Selenium, `host-resolver-rules`.
Подробности всё равно в [browser-setup.md](browser-setup.md).

Раннер **не поднимает** стенд и chromedriver. Если их нет, падает с
инструкцией, что запустить.

---

## Храповик легаси-селекторов

[`_map/selectors-legacy.txt`](../archive/qa/_map/selectors-legacy.txt) — Cest, написанные
до правила «селекторы только в Page». Они не блокируют G10, но и не
забываются: `check-selectors.py` ругается, если файл из списка уже почищен
и запись пора убрать.

Список может только сокращаться. Добавлять в него новые файлы нельзя.

---

## Порядок работы по задаче

1. `prepare-plan` — план правок
2. реализация
3. `prepare-task-test` — тест из Page/Step, заполнить `test.md`
4. `check-tests.sh` — быстрая проверка
5. `task-test.sh {N}` — прогон
6. `browser-verify` слой 2 — Playwright на то, что не покрыто
7. `gates.py {N}` — готово или нет
8. красный гейт — вернуться к шагу 3 или 2

---

## Известные проблемы и ограничения

### П-1: Реестр `data-test` не видит динамические имена
- Симптом: `check-selectors.py` не ругается на опечатку в вычисляемом атрибуте
- Причина: `:data-test="'prefix-' + id"` фиксируется только префиксом
- Решение: для таких элементов проверять наличие явно в Page через `seeElement`
- Файлы: [scripts/collect-data-test.py](../../.agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py)

### П-2: Симлинки задач и docker-маунт
- Симптом: прогон зелёный, но тестов задачи 0
- Причина: при монтировании только `.doc/codeception` симлинк
  `../../../../tasks/{N}/tests` уходит за пределы маунта
- Решение: монтировать `.doc` целиком в `/doc`, workdir `/doc/codeception`
- Файлы: [scripts/lib.sh](../../.agents/skills/task-router/children/testing-router/children/test-task/scripts/lib.sh), [scripts/check-tests-load.php](../../.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests-load.php)

### П-3: Acceptance пишет в живую dev-БД
- Симптом: duplicate PK, испорченные данные стенда, 500 на главной
- Причина: `populate/cleanup: false`, общая база `gb_copydev5`
- Решение: upsert в фикстурах, тестовые тарифы `visible=0`, гейт G8 после прогона
- Файлы: [browser-setup.md](browser-setup.md) П-8, П-9,
  cicd.md §3.6 (`../architecture/cicd.md#36-данные-acceptance-на-dev-стенде-гигиена`; missing in kit)

---

## Связи

- [index.md](index.md) — реестр UI-флоу и конвенция селекторов
- [browser-setup.md](browser-setup.md) — Chrome, chromedriver, Playwright на WSL
- [fragments.md](fragments.md) — каталог Page, Step и фрагментов актора
- [`../tests.md`](../harnes/tests.md) — канон: чек-лист §7, стандарт отчёта §8
- `testanalyze/test-system-plan.md` (удалён) — план, по которому система собрана
- [`prepare-task-test`](../../.agents/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md) — сборка теста
- [`browser-verify`](../../.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md) — прогон и отчёт
- [`test-task`](../../.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md) — оркестратор

---

## История изменений

- 2026-09-15: система собрана; тесты перенесены в папки задач, добавлены
  слои Page/Step, гейты, раннер и валидаторы селекторов
- 2026-09-22: гейт G13. Таблица веток в test.md обязана закрыть каждый R из Decomposition. Канон: [testaudit.md §9](../harnes/testaudit.md#9-когда-проверять-и-что-считать-веткой)
- 2026-11-05: ссылки на `prepare-task-test`, `browser-verify` и `test-task` переведены на иерархию `.agents/skills/task-router/children/testing-router/children/`.
- 2026-09-26: сверка с фактическим состоянием скриптов: заголовок "Четыре команды"
  (в блоке 4 команды), гейт G12 добавлен в таблицу (машинный AC, lint, PHPUnit,
  DB и hash-контроль, `gates.py`), таблица скриптов дополнена 11 отсутствовавшими
  скриптами раннера (теперь все 27)

## Машинный контракт запуска

`task-test.sh` не запускает acceptance-тесты без `ac-matrix.json`. Матрица содержит каждый AC-ID, ссылку на реальный метод и измеримый expected. Тест должен записать evidence через `AcceptanceTester::recordAcceptanceCriterion()`.

Запуск также выполняет `qa-lint.py`, `run-phpunit.py` для серверных правок, hash-манифест `qa-manifest.py`, проверку `check-ac-matrix.py` и обязательные соседние задачи из `required_neighbors`.

Для изоляции dev DB задаются явные команды окружения:

```bash
export QA_DB_RESET_CMD='... безопасный reset/fixture для выделенного test DB ...'
export QA_DB_CLEANUP_CMD='... cleanup только выделенного test DB ...'
```

Без этих команд задача с `db_isolation: required` блокируется. Runner не выполняет сгенерированный SQL и не пишет в live DB сам.

Значения `true`, `:`, `echo` и `/bin/true` также блокируются как no-op,
потому что они не дают изоляции.

Для migration и unit fixtures можно создать отдельную базу без данных:

```bash
QA_SOURCE_DB=gb_copydev5 bash .doc/qa/scripts/disposable-db.sh create 2078_manual
# передайте QA_DB_NAME из вывода в DB_DATABASE/DB_NAME runner-а
bash .doc/qa/scripts/disposable-db.sh drop 2078_manual
```

Скрипт отказывается использовать `gb_copydev5`. Browser acceptance нельзя
считать изолированным только после создания базы: приложение и Codeception
должны быть запущены с этой базой, иначе browser phase блокируется.

### Fingerprint и stale run

Каждый run сохраняет `run-meta.json`/`manifest.json` с hash кода, тестов,
требований, skills и среды. После изменения source, task matrix, плана,
QA skill или environment старый run считается stale. G12 показывает конкретные
изменившиеся fingerprint fields, поэтому не нужно повторять browser прогон,
если менялись только отчёт или metadata.

### Самопроверка harness

После изменений в `.doc/qa/scripts` запускайте:

```bash
python3 .doc/qa/scripts/harness-selftest.py
```

Команда проверяет компиляцию runner scripts и что duplicate AC evidence не
принимается валидатором. Она не требует Docker, БД или браузера.
