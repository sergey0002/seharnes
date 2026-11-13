---
name: test-task
description: >-
  Оркестратор проверки задачи: «тестируй задачу», «тестируй задачу N», test the task.
  Resolve TASK_ID → impact по diff.files.md + qa/index → если нет Task Cest /
  test.md — prepare-task-test (спросить если неоднозначно) → browser-verify
  (Codeception -g task-N / flow, затем Playwright только на строки веток без метода)
  → отчёт test-runs по .doc/harnes/tests.md §8. login-as-user если в task.md конкретный
  clientId. По мере реализации: «проверь этап R» гоняет только S этого R.
  Канон веток: .doc/harnes/testaudit.md §9.
  Очистка старых прогонов: «очисти старые тесты», «удали старые прогоны».
  Use when the user says очисти старые тесты, удали старые прогоны, cleanup old test runs.
  Не путать с prepare-plan (план) и browser-verify alone (только прогон).
---

# Test Task — оркестратор «тестируй задачу»

Один вход для пользователя. Сам **не** пишет логику теста и **не** дублирует
прогон: вызывает существующие скилы по правилам ниже.

Канон полноты: [`.doc/harnes/testaudit.md`](../../../.doc/harnes/testaudit.md) §9.
Готовность определяется таблицей веток, а не только зелёным Cest.
Порядок прогона (сначала свежие правки, потом полное покрытие) -
правило [test-priority](../../../.cursor/rules/test-priority.mdc).

Два режима. Определение ветки и слоёв не копировать, оно в §9.

```
проверь этап R3          сразу после патча этого R
  → прочитать S этого R в plan.md ## Decomposition
  → прогнать только этот S (один метод PHPUnit или один метод Cest)
  → отметить строку в test.md ## Ветки логики
  → соседей, весь Cest и Playwright не гонять
  → gates.py на этом шаге не финиш

тестируй задачу [N]      конец реализации
  → 0. Resolve N + Read task/diff/plan Decomposition
  → 1. Таблица веток: каждый R/S и развилки диффа без S
  → 2. Нет Cest на браузерные строки? prepare-task-test
  → 3. browser-verify: Codeception task-{N}, Playwright только строки без метода
  → 4. Отчёт test-runs §8
  → 5. gates.py N, в том числе G13
```

Финальный ответ пользователю: "готово" только если в `## Ветки логики` нет `open` и `partial` и `gates.py` зелёный.
Зелёный Cest при дыре в таблице веток = не готово. В ответе список дыр, не "тесты прошли".

Перед подготовкой и прогоном оркестратор собирает требования из task.md,
актуальных комментариев, plan.md и последних сообщений пользователя.
Допусловия пользователя помечаются `user-extra` и сохраняются в test.md.
При конфликте требований или неподтверждённой свежести Jira задача не готова.

---

## Шаг 0 — Обязательное чтение

1. [`.doc/harnes/tests.md`](../../../.doc/harnes/tests.md) - принципы, §7 чек-лист, §8 отчёт
2. [`.doc/qa/index.md`](../../../.doc/qa/index.md) - реестр флоу (не сканировать все flows)
3. Скилы (по необходимости, не заранее целиком):
   - [`prepare-task-test`](../prepare-task-test/SKILL.md)
   - [`browser-verify`](../browser-verify/SKILL.md)
   - [`login-as-user`](../login-as-user/SKILL.md)

---

## Шаг 1 — Resolve TASK_ID

| Источник | Как |
|---|---|
| Сообщение | `#2606`, `CT-2606`, «тестируй задачу 2606» |
| Контекст | открытый `.doc/tasks/{N}/`, ветка `bugfixes/#N` / `features/#N` |
| Неясно | AskQuestion: какой номер задачи |

Прочитать целиком: `task.md`, `diff.files.md` (если нет - сказать и спросить,
нужен ли `task-diff` / достаточно ли ручного списка файлов).
Опционально: `plan.md` Verification / per-patch scenarios - вход для чеклиста §7.

---

## Шаг 2 — Impact mapping (как browser-verify шаг 1)

Сопоставить `diff.files.md` с таблицей «Флоу» в `qa/index.md`.

Вывод перед действиями (без эмодзи, стиль text-style):

```
Область проверки задачи {N}:
- Флоу: […]
- Task Cest: есть путь … (@group task-{N}) | нет
- test.md: есть | нет
- Codeception группы к прогону: task-{N}, {flow-groups…}
- Playwright дыры: […] | нет
- Вход: loginAsClient | loginAsClientById({id}) из task.md
- Стенд / chromedriver: OK | нужно поднять (не поднимать без спроса)
- Оценка длительности: без паузы между шагами; пауза включается QA_VISIBLE_DELAY=0.3 и даёт ~шагов * 0.3с
```

Если нет пересечения с UI-флоу - сообщить и спросить, продолжать ли (только
PHPUnit / отказ). Не выдумывать флоу.

Нет flow-документа при явном UI-изменении - Index Gate (как в browser-verify):
предложить создать `qa/flows/{name}.md`, не создавать без подтверждения.

---

## Шаг 3 — Нужен ли конструктор теста

Режим «проверь этап R» этот шаг пропускает, если метод S уже есть. Нет метода на этот S: дописать только его, не весь Cest.

Перед решением "метод есть" сверяется цель: S/AC текущего стейджа должен иметь
свой метод с литералом цели. Метод соседней ветки через тот же handler целью
не считается. Нет метода цели - дописать, даже если Cest зеленый.

| Условие | Действие |
|---|---|
| Нет `Task/{N}_*Cest.php` и пользователь сказал только «тестируй» | AskQuestion: «Cest нет. Собрать тест (prepare-task-test), потом прогнать?» Да / Только Playwright / Отмена |
| Пользователь сказал «подготовь тест и прогони» / «тестируй с нуля» | Сразу `prepare-task-test`, без лишнего вопроса |
| Cest есть, `test.md` устарел относительно diff | Обновить `test.md` точечно (prepare-task-test правила), затем прогон |
| Cest есть и актуален по файлам, но incident/AC называет элемент без своего метода | Дописать метод на этот элемент (prepare-task-test правила), затем прогон |
| Cest есть и актуален | Сразу шаг 4 |

При вызове `prepare-task-test` - **следовать его SKILL.md целиком** (фрагменты,
чек-лист §7 в test.md, без правок templates/).

Если в `task.md` есть конкретный `clientId` бага - в Cest использовать
`loginAsClientById` / скил `login-as-user`, не подменять id=1 молча.

---

## Шаг 4 — Прогон (`browser-verify`)

Режим «проверь этап R»: одна команда на метод S (`--filter` PHPUnit или один метод Cest). `task-test.sh` целиком, соседи и Playwright здесь не запускать.

Конец реализации: следовать [`browser-verify/SKILL.md`](../browser-verify/SKILL.md). Playwright только для строк таблицы без метода.

**Перед `task-test.sh` - блок Chromedriver ниже (обязательно).** Без живого
`:9515` слой 1 не стартует; путать "бинарник есть" и "процесс слушает" нельзя.

Версию PHP сайта проверяй внутри контейнера приложения. Версия PHP раннера
Codeception не доказывает версию сайта. Скрипты скила вызывают соседние файлы
из собственного `scripts/`; `.doc/qa/` содержит данные и документы, а не копии этих скриптов.
Для Docker-раннера локальный WebDriver должен быть доступен из выбранной сети,
проверки порта только с хоста недостаточно. Прямой запуск Cest без
`QA_AC_RESULTS_FILE` не заменяет `task-test.sh`: результаты AC не будут записаны.

1. Быстрая проверка без браузера: `bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh` и `bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N} --phase preflight`.
   Если preflight красный (ошибки ac-matrix, DB isolation или синтаксиса) — не запускать браузерный слой до устранения блокеров.
2. Предусловия стенда и WebDriver - см. секцию
   [Chromedriver: бинарник vs процесс](#chromedriver-бинарник-vs-процесс).
   Стенд (`:8030`) без спроса не поднимать. Chromedriver: сначала диагностика,
   потом AskQuestion на старт (или сразу старт, если пользователь уже сказал
   "есть chromedriver" / "подними" / "гоняй").
   **Не путать sandbox с мёртвым стендом:** HTTP `000` на `:8030`/`:9515`
   из sandbox не доказательство. Перед "стенд недоступен" - curl/ss с
   `required_permissions: ["all"]` (см. [browser-setup.md AI/sandbox](../../../.doc/qa/browser-setup.md#ai--sandbox-ложный-стенд-недоступен-обязательно)).
3. Слой 1: `bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N}` плюс отдельные запуски
   с `--group {flow}` для соседних флоу. Раннер сам выбирает хостовый PHP
   или docker и нужный порт WebDriver. Команду прогона тоже гонять с
   правами, достаточными для Docker/localhost (обычно `all`), иначе
   precheck/раннер снова увидит "порт мёртв".
4. Вердикт брать из `verdict.json`, не из чтения лога. Падение Cest =
   регрессия: разобрать до слоя 2 (баг кода vs устаревший тест).
5. Слой 2: Playwright только на непокрытые ветки / если Cest нет и пользователь
   выбрал «только Playwright».
6. Отчёт §8 в `.doc/tasks/{N}/test-runs/{RUN_DIR}/report.md`.
7. Строка в истории `test.md`; flow-доки - только при реальном расхождении (П-N).

---

## Chromedriver: бинарник vs процесс

На этом стенде (WSL) **ChromeDriver уже установлен**. Типичная ошибка агента:
увидеть закрытый порт `:9515` и написать пользователю "chromedriver нет".
Это неверно.

| Что | Как проверить | Значение |
|---|---|---|
| Бинарник | `test -x "$HOME/.local/chrome-for-testing/chromedriver-linux64/chromedriver"` | установлен / нет |
| Процесс (сессия) | `curl -fsS http://127.0.0.1:9515/wd/hub/status` с `required_permissions: ["all"]` → `"ready": true` | запущен / не запущен |
| Chrome | `$HOME/.local/chrome-for-testing/chrome-wrap.sh --version` | headed-браузер для окна |

**Запрещённые формулировки**, если бинарник на месте, а порт молчит:

- "chromedriver нет"
- "chromedriver не установлен"
- "нет драйвера"

**Правильно:** "chromedriver не запущен на `:9515`. Поднять видимый Chrome командой ниже?"

### Старт (видимое окно на экране)

Из корня репо, **вне sandbox** (`required_permissions: ["all"]`):

```bash
bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh
```

Скрипт:

- ставит `DISPLAY=:0` (WSLg), без `--headless`;
- поднимает драйвер на `:9515` с `--url-base=/wd/hub`;
- пишет лог `~/.local/chrome-for-testing/chromedriver-9515.log`;
- проверяет `ready: true` сам.

Альтернатива (тот же эффект): `~/.local/chrome-for-testing/start-chromedriver.sh`
(канон для агента - `start-chromedriver-wsl.sh` из репо).

После старта в impact-блоке писать:

```
- Стенд / chromedriver: :8030 OK; :9515 ready (headed via start-chromedriver-wsl.sh)
```

### Когда поднимать без повторного спора

| Ситуация | Действие |
|---|---|
| Пользователь: "тестируй задачу", бинарник есть, `:9515` закрыт | AskQuestion: поднять `start-chromedriver-wsl.sh`? |
| Пользователь: "есть chromedriver" / "подними" / "гоняй" / подтвердил AskQuestion | Сразу `start-chromedriver-wsl.sh`, потом `task-test.sh` |
| `:9515` уже `ready: true` | Не перезапускать без нужды, сразу прогон |
| Бинарника реально нет (`test -x` fail) | Ссылка на [browser-setup.md](../../../.doc/qa/browser-setup.md), не выдумывать путь |

Selenium Docker (`:4444` / noVNC `:7900`) - запасной путь, не путать с headed
окном на хосте. Раннер предпочитает `:9515`.

Детали и `.env`: [browser-setup.md § Запуск chromedriver](../../../.doc/qa/browser-setup.md#запуск-chromedriver-слой-1-порт-9515--видимое-окно).

---

## Шаг 6 — Гейты готовности

```bash
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py {N}
```

Для списка задач релиза используется последовательный воспроизводимый прогон:

```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh 15 16 17
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh --file .doc/tasks/release.tasks
```

Batch отдельно выполняет check, прогон и gates для каждого номера, сохраняет
общий summary и возвращает ошибку, если хотя бы одна задача не готова.

Это и есть ответ на вопрос «можно отдавать тимлиду и ручному тестировщику».
Красный блокирующий гейт - задача не готова, независимо от того, что прогон
зелёный. Чинить причину, а не подгонять тест под гейт.

---

## Шаг 7 — Отчёт в чат

```
test-task: задача #{N}
Режим: этап R / конец
Ветки: закрыто X, open/partial Y
Готово: да только если Y = 0 и gates.py зелёный
Cest: [путь]
PHPUnit: [файлы tests/lib | нет]
Слой 1: verdict.json green да/нет
Слой 2 Playwright: только строки без метода | пропущен
Дыры: [B-id и почему | нет]
Отчёт: .doc/tasks/{N}/test-runs/…
Гейты: ГОТОВО | НЕ ГОТОВО (красные: …)
```

Флак (таймаут логина, чужая строка журнала, модалка не того типа) не лечится повторным полным `task-test.sh`.
Один раз `--filter` упавшего метода. Второй раз тот же assert красный: это баг или тест, не "ещё прогон".

Не реализовывать фикс продукта, пока пользователь явно не попросил.

---

## Этого скила нет и не делать

- **«тестируй все задачи» / прогон всего Acceptance suite «заодно»** - нет оркестратора
  и нет CI на Codeception ([cicd.md](../../../.doc/architecture/cicd.md): Acceptance только локально).
  Весь suite пишет в живую dev-БД (`populate/cleanup: false`) - полный прогон без
  явной просьбы запрещён (риск порчи стенда, см. cicd §3.6).
- Если пользователь **явно** просит полный Acceptance: одна команда Codeception
  (канон команд: `.tools/codeception/README.md` / cicd §3.5), **не** этот скил,
  **не** Playwright на каждый Cest, без автоподнятия стенда. После прогона -
  curl home/admin (гигиена БД).
- Playwright-прогоны **не** заменяют сохранённый Cest: слой 2 - дыры одной задачи.

## Где тесты лежат (повторный прогон)

| Что | Где | Повтор |
|---|---|---|
| Тест задачи | `.doc/tasks/{N}/tests/{Slug}Cest.php` | да, `task-test.sh {N}` |
| Тест флоу | `.tools/codeception/tests/Acceptance/*Cest.php` | да, `task-test.sh {N} --group {flow}` |
| Селекторы экранов | `.tools/codeception/tests/Support/Page/` | переиспользуется всеми тестами |
| Бизнес-шаги | `.tools/codeception/tests/Support/Step/` | то же |
| Вход, фикстуры, `checkpoint()` | `AcceptanceTester` + [fragments.md](../../../.doc/qa/fragments.md) | `$I->devLoginAsClient(1)` и т.д. |
| Прогон и вердикт | `.doc/tasks/{N}/test-runs/{дата}_{группа}/` | артефакт, не тест |
| Playwright MCP | нет файла-теста | не повторно без агента |

Тесты задач **в git не идут**: `.doc/` исключён локально. Codeception видит
их через симлинк `tests/Acceptance/Task/{N}`, его ставит генератор.

То, что уже лежит в `tools/codeception/` и отслеживается git, остаётся как
есть - это заморожено. Новые тесты туда не добавлять, копировать между
копиями тоже не нужно.

Ручной повтор одной группы, если нужен без раннера (локальный chromedriver `:9515`,
без `--env` - раннер сам предпочитает 9515):

```bash
docker run --rm --network host \
  -e QA_AC_RESULTS_FILE=/app/.doc/tasks/{N}/test-runs/{RUN_DIR}/ac-results.json \
  -v "$PWD:/app" -w /app/.tools/codeception copytrust-codecept:8.3 \
  vendor/bin/codecept run Acceptance -g task-{N} -o "WebDriver: host: 127.0.0.1" -o "WebDriver: port: 9515"
```

Вариант с `--env chromedriver` (Selenium `:4444`, смотреть через noVNC `:7900`) - только
когда локальный `:9515` недоступен. Монтировать надо корень проекта целиком, а не
`.tools/codeception`: иначе симлинки задач уходят за пределы маунта и Codeception
молча находит 0 тестов.

Прямой запуск требует существующего каталога прогона и `QA_AC_RESULTS_FILE`.
Для полного отчёта, манифеста и вердикта используй `task-test.sh`.

## Очистка старых прогонов

Старые каталоги `.doc/tasks/{N}/test-runs/` удаляет служебный скрипт:

```bash
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/cleanup-test-runs.py --days 14
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/cleanup-test-runs.py --days 14 --apply
```

По умолчанию это dry-run: скрипт печатает кандидатов и ничего не удаляет.
`--apply` удаляет каталоги старше `--days` (по умолчанию 14). `--task N`
ограничивает одной задачей. `--include-files` добавляет файлы верхнего уровня
`test-runs/`.

Дата прогона берётся из содержимого: `report.md`, затем `verdict.json`,
`manifest.json`, `history-entry.json`, `ac-source.json`. Если даты в файлах нет,
используется дата из имени каталога. mtime не используется. Каталог без даты
пропускается и попадает в отчёт `undated`.

Прогон, на который ссылается `doc.md`, `test.md`, `plan.md`, `task.json`, `diff.md`
или `reports/` задачи, по умолчанию защищён и попадает в `protected`.
`--ignore-reports` снимает защиту.

## Hard rules

- «тестируй задачу» = этот скил, не прямой прыжок в Playwright «по привычке»
- «тестируй все задачи» ≠ этот скил; полный suite только по явной просьбе, не по умолчанию
- Не править `templates/` / продуктовый UI ради селекторов
- Не гонять весь Acceptance suite - только `-g` по impact
- Не поднимать стенд/selenium без спроса
- Не объявлять "chromedriver нет", если бинарник в
  `~/.local/chrome-for-testing/chromedriver-linux64/` на месте: порт закрыт =
  "не запущен", лечится `bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh`
- Не объявлять стенд/chromedriver недоступными по sandbox-`curl` (`000`);
  только после проверки с `all` или явного отказа раннера вне sandbox
- После фраз пользователя "есть chromedriver" / "подними драйвер" - стартовать
  скрипт и продолжать прогон, не спорить и не спрашивать второй раз
- Не пропускать §7/§8 (молчание категории = ошибка скила)
- Не путать с `prepare-plan` (план) и `task-doc` (документация после merge)
- Не вызывать методы из fragments.md, которых нет в коде - сверять через
  `check-tests.sh`, а не на глаз
- Не объявлять задачу готовой без `gates.py` и без таблицы веток без `open`/`partial`.
- Зелёный Cest не закрывает дыру. В чат писать список непокрытых веток.
- Флак: один `--filter` метода. Не гонять весь suite повторно, чтобы "дождаться зелёного".
- Не кликать в Playwright ветку, у которой уже есть метод PHPUnit или Cest.
- Серверную ветку без экрана не отдавать в Playwright: это `tests/lib`.
- В режиме этапа не гонять соседние флоу, весь Cest и Playwright.
- Не использовать старый verdict после изменения требований, плана, кода или теста.
- Не считать Playwright-only достаточным для стабильного сценария задачи.
- Не подгонять тест под зелёный гейт

---

## Связи

- [`.doc/harnes/tests.md`](../../../.doc/harnes/tests.md) - канон §7/§8
- [`.doc/qa/index.md`](../../../.doc/qa/index.md)
- [`prepare-task-test`](../prepare-task-test/SKILL.md)
- [`browser-verify`](../browser-verify/SKILL.md)
- [`login-as-user`](../login-as-user/SKILL.md)
- [`prepare-plan`](../prepare-plan/SKILL.md) - Verification checklist → после implement этот скил
- [cicd.md §3.5](../../../.doc/architecture/cicd.md#35-как-проводить-проверку-порядок-работ)

## Обязательные машинные проверки

Перед браузерным прогоном `task-test.sh` обязан последовательно:

1. проверить `.doc/tasks/{N}/ac-matrix.json`: метод AC есть в Cest или в `tests/`;
2. запустить `.agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py` по изменённым PHP/JS/Vue и тестам;
3. запустить PHPUnit, если изменён серверный код;
4. выполнить настроенные `QA_DB_RESET_CMD` и `QA_DB_CLEANUP_CMD` для задач с `db_isolation: required`;
5. после Codeception: браузерный AC в `ac-results.json`, PHPUnit-AC закрывается `phpunit.json` = passed, плюс hash-манифест и `required_neighbors`.

Отсутствующий AC-result, evidence, lint, PHPUnit, cleanup или соседний flow блокирует verdict. Нельзя заменить эти проверки наличием метода или строкой в `test.md`.
