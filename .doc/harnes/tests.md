# Система тестирования CopyTrust (QA)

<!-- meta
type: index
status: actual
updated: 2026-11-10
related: [../doc_rules.md]
tags: [qa, e2e, codeception, tests]
-->

---

## Суть

Единый стандарт: **что** проверять по задаче, **чем** (фрагменты / Cest / Playwright),
**как** писать отчёт. Скилы читают этот файл; детали флоу - в qa/index.md в проекте Target.

> **AI:** команда пользователя «тестируй задачу» / «тестируй задачу N» → скил
> [`test-task`](../../.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md) (оркестратор).  
> Не сканируй все `flows/*.md` и не пиши Cest с нуля - сначала фрагменты и index.

Устройство тестовой системы (раскладка, слои Page/Step, гейты, скрипты):
qa/README.md в проекте Target. Здесь - канон чек-листа §7 и отчёта §8.

Команды проверки задачи:

```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh     # без браузера, секунды
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh {N}   # smarty clear + max-статика по патчу
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py --task {N} --run-dir .doc/tasks/{N}/test-runs/{RUN_DIR} # Слой 0: PHPUnit
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N}   # Слой 1: Codeception + verdict.json
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py {N}    # проверка гейтов готовности (G0-G13)
```

Готовность задачи определяют гейты, а не отчёт: зелёный прогон при красном
гейте означает, что проверка неполная. Локальная статика (PHPStan L8 + ESLint
patch-max по строкам патча) живёт в `.doc/` и в git не попадает; CI мягче
(`lint:basic`, PHPStan 0) - см. qa/README.md в проекте Target.

Порядок стенда и прогона: cicd.md §3.5 (проект Target),
qa/browser-setup.md в проекте Target
(агенту: не считать стенд мёртвым по sandbox-`curl` `000` - см. там § AI/sandbox).

---

## 1. Принципы

1. **Codeception первым** (0 токенов LLM на прогон) - если есть `@group` / Task Cest.
2. **Playwright MCP вторым** - только дыры покрытия; браузер всегда **headed**.
3. **Конструктор, не с нуля** - методы из qa/fragments.md в проекте Target, селекторы из `qa/flows/*.md`.
4. **Шаблоны не правим ради теста** - новый `data-test` только отдельной продуктовой задачей
   с явным решением пользователя (скилы verify/prepare не трогают `templates/`).
5. **Один отчёт на прогон** в `test-runs/{RUN_DIR}/report.md` (§8); в `test.md` / flow - только ссылка.
6. **Чек-лист §7 без молчания** - каждая категория: покрыто / не применимо + причина.

Статус реализации (кратко):

| Идея | Статус |
|---|---|
| Фрагменты входа / checkpoint / loginAsClientById | реализованы 2026-09-15 (до этого были только в доке) |
| Тесты задач в папках задач, вне git | есть: `.doc/tasks/{N}/tests/` |
| Слои переиспользования Page / Step | есть: `Support/Page/`, `Support/Step/` |
| Гейты готовности G0-G13 | есть: `qa/scripts/gates.py` |
| Реестр `data-test` и сверка селекторов | есть: `qa/scripts/check-selectors.py` |
| `tests.md` как канон чек-листа/отчёта | этот файл |
| Перевод `ItemDraftCest` на `DepositionSteps` | долг (fragments П-1) |
| Чистка сырых селекторов в 4 легаси-Cest | долг (`qa/_map/selectors-legacy.txt`) |

---

## 2. Вход под пользователем

| Способ | Когда |
|---|---|
| `AcceptanceTester::loginAsClient()` | обычный тест, client id=1 |
| `loginAsClientById($id)` / скил `login-as-user` | баг конкретного клиента из task.md |
| `dev-login.php?as=client&id=N` | ручной / Playwright без пароля клиента |

Только **dev/test** стенд (`.tools/docker-test` / docker-dev), никогда прод.
См. [login-as-user](../../.agents/skills/login-as-user/SKILL.md), admin.md (проект Target).

---

## 3. Тесты в папках задач

| Артефакт | Путь |
|---|---|
| Cest задачи | `.tools/codeception/tests/Acceptance/Task/{N}/{Slug}Cest.php` (`@group task-{N}`); `Task/{N}` - симлинк на `../../../../../.doc/tasks/{N}/tests`, имя файла без префикса номера (пример: `tasks/2612/tests/ArchiveRemoveCest.php`) |
| Описание теста | `.doc/tasks/{N}/test.md` |
| Отчёт прогона | `.doc/tasks/{N}/test-runs/{RUN_DIR}/report.md` (RUN_DIR вида `{дата}_{время}_{группа}`) |
| Браузерные доказательства | `.doc/tasks/{N}/test-runs/{дата}_{platform}-browser/` для скриншотов и отчёта `platform-browser-test` |
| Конвенция | [Task/README.md](../../.tools/codeception/tests/Acceptance/Task/README.md) |

Создаёт: скил `prepare-task-test`. Запускает и пишет отчёт: `browser-verify`.
Оркестрирует оба: `test-task` («тестируй задачу»).

### 3.1 Срок хранения прогонов

Прогоны старше 14 дней удаляет скрипт
`.agents/skills/task-router/children/testing-router/children/test-task/scripts/cleanup-test-runs.py`.
Дата прогона берётся из содержимого `report.md`, `verdict.json`, `manifest.json`,
`history-entry.json` или `ac-source.json`, затем из имени каталога. mtime не используется.
По умолчанию запуск только показывает кандидатов; удаление выполняется с `--apply`.
Прогон, на который ссылается отчёт или документ задачи, защищён и не удаляется.
Каталоги без даты скрипт не удаляет и выводит в отчёте `undated`.

---

## 4. Checkpoint на каждом значимом шаге

После клика / сабмита / смены шага wizard - `$I->checkpoint('label')`:
скрин, консоль, DOM-дельта, проверка error-modal / toasted.
Не только в конце теста. См. fragments.md в проекте Target.

---

## 5. Два слоя проверки

| Слой | Инструмент | Когда |
|---|---|---|
| 0 | PHPUnit `tests/lib/...Test.php` | результат в браузере не виден: флаги заголовка, env, формула, второй вход без экрана |
| 1 | Codeception Acceptance `-g task-{N}` / `-g {flow}` | экран или эффект в БД на стенде |
| 2 | Playwright MCP | нет метода PHPUnit и нет метода Cest на эту ветку |

Одна ветка живёт в одном слое. Cest не читает `lib/` (раннер монтирует только `.doc`).
Чек-лист §7 не заменяет таблицу веток.

### 5.1. Слой 0: PHPUnit (универсальный канон запуска)

PHPUnit версии 4.8.36 запускается под PHP 7.4 **только внутри Docker-контейнера приложения** `copytrust-dev-php-apache-1`.
На хосте (WSL2) `php-cli` намеренно отсутствует (ставить `apt install php*` на хост запрещено по `cicd.md §3.2`).
На PHP 7.4 PHPUnit 4.8.36 выводит `Deprecated: The each() function is deprecated` из `Getopt.php` и продолжает работу. Результат теста определяется кодом выхода и отчётом PHPUnit; предупреждение не означает успешный прогон.

#### Базовые параметры (константы окружения, не искать по диску):
* **Контейнер приложения:** `copytrust-dev-php-apache-1`
* **Рабочая директория (workdir) в контейнере:** `/var/www/html`
* **Точный путь к бинарнику:** `vendor/phpunit/phpunit/phpunit` (Внимание: бинарника `vendor/bin/phpunit` **нет**, поиск по нему выдаст ошибку).
* **Конфигурация:** `tests/phpunit.xml`
* **Bootstrap:** `tests/maket.php`
* **Хелперы:** `tests/TestHelper.php`
* **Расположение тестов:** директория `tests/` зеркалит структуру `lib/` (например, для `lib/src/Foo/Bar.php` тест находится в `tests/lib/src/Foo/BarTest.php`).

#### Готовые команды запуска (Copy-Paste):

**1. Автоматический раннер по задаче (рекомендуется для пайплайнов и проверки патча):**
```bash
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py --task {N} --run-dir .doc/tasks/{N}/test-runs/{RUN_DIR}
```
Скрипт автоматически находит изменённые серверные файлы задачи, вычисляет парные unit-тесты `tests/lib/...Test.php`, запускает PHPUnit в контейнере `copytrust-dev-php-apache-1` с флагом `--no-coverage` и сохраняет отчёты `phpunit.json`, `phpunit.log`, `phpunit-junit.xml`.

**2. Запуск отдельного тестового файла напрямую через Docker:**
```bash
docker exec -w /var/www/html copytrust-dev-php-apache-1 php vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml --no-coverage tests/path/to/FooTest.php
```

**3. Запуск конкретного тестового метода (`--filter`):**
```bash
docker exec -w /var/www/html copytrust-dev-php-apache-1 php vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml --no-coverage --filter testMethodName tests/path/to/FooTest.php
```

**4. Запуск всех unit-тестов проекта:**
```bash
docker exec -w /var/www/html copytrust-dev-php-apache-1 php vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml --no-coverage
```

**5. Запуск через хостовый транслятор путей:**
```bash
.tools/scripts/php-docker.sh vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml --no-coverage tests/path/to/FooTest.php
```
Скрипт транслирует пути хоста/WSL в контейнерный `/var/www/html` и запускает `docker exec`.

#### Частые проблемы и антипаттерны:
1. **`Could not open input file: vendor/bin/phpunit`** → Всегда указывать точный путь `vendor/phpunit/phpunit/phpunit`.
2. **`Fatal error: Declaration of Mock_...` / `PHP_CodeCoverage_Exception`** → Легаси-моки PHPUnit 4.8 не поддерживают генерацию coverage под PHP 7.1/Xdebug; **всегда** добавляйте `--no-coverage`.
3. **`Command 'php' not found` на хосте WSL** → Не ставьте `apt install php-cli`! Запускайте тесты через `docker exec ...` или `.tools/scripts/php-docker.sh`.

---

### 5.2. Слой 1: Codeception (канон запуска)

Контейнер раннера: `copytrust-codecept:8.3`. При PHP 8.2+ на хосте образ не нужен:
`php -d register_argc_argv=1 .tools/codeception/vendor/bin/codecept -c .tools/codeception/codeception.yml ...`.
Флаг `-d register_argc_argv=1` обязателен, иначе Codeception падает с `register_argc_argv must be set to On`; `task-test.sh` передаёт его сам.
Браузерная проверка: порт `9515` (chromedriver на хосте в WSLg — видимое окно) или порт `4444` (Selenium в Docker).
Стенд: `.tools/docker-dev` (`http://127.0.0.1:8030/`, PHP 7.4) или `.tools/docker-test` (`http://127.0.0.1:8230/`).

```bash
# Комплексный запуск теста задачи (Cest + preflight + отчет):
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N}

# Запуск конкретной группы acceptance-тестов или одного Cest (группа по умолчанию task-{N}):
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N} --phase browser --group task-{N}
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N} --phase browser --filter {Slug}Cest

# Быстрая проверка без браузера (селекторы и синтаксис Cest):
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh
```

---

### 5.3. Doctrine Migrations (канон запуска)

Все миграции накатываются внутри контейнера `copytrust-dev-php-apache-1`:
* **Применить все миграции:**
```bash
docker exec -w /var/www/html copytrust-dev-php-apache-1 php vendor/doctrine/migrations/bin/doctrine-migrations --no-interaction migrations:migrate --db-configuration=sql/migrations-db.php --configuration=sql/migrations.yml
```
* **Применить конкретную миграцию (Up):**
```bash
docker exec -w /var/www/html copytrust-dev-php-apache-1 php vendor/doctrine/migrations/bin/doctrine-migrations --no-interaction migrations:execute --up YYYYMMDDHHIISS --db-configuration=sql/migrations-db.php --configuration=sql/migrations.yml
```

---

### 5.4. Окружение Docker и WSL: критические правила для агентов

### 5.4.1. Основной стенд PHP 7.4

Стенд `.tools/docker-dev` работает на PHP 7.4:
- Образ: `copytrust-dev-php-apache:latest`, Dockerfile `.tools/docker-dev/php-apache/Dockerfile` (`php:7.4-apache`, расширения mbstring/gd/zip/intl/soap/sockets).
- Пересборка: `cd .tools/docker-dev && docker compose -f compose.yaml build php-apache && docker compose -f compose.yaml up -d --no-deps php-apache`.
- URL: `http://127.0.0.1:8030/`, контейнер `copytrust-dev-php-apache-1`, MySQL `copytrust-dev-mysql-1` на 8031.
- PHPStan запускается в этом же образе: `PHPSTAN_DOCKER_IMAGE=copytrust-dev-php-apache:latest`. Отдельный `copytrust-php74:local` не нужен.
- PHPUnit 4.8.36 работает в этом контейнере, см. §5.1.

Версия PHP на production этим изменением не подтверждена. Локальная пересборка не обновляет удалённую площадку.

### 5.4.2. Docker и подключение браузера

Локальный ChromeDriver слушает `127.0.0.1:9515`. На текущем WSL2 Docker-раннер подключается через `--network host`; `CHROMEDRIVER_HOST=127.0.0.1` задан в `.tools/codeception/.env`. Режим Selenium на `4444` сохраняет отдельную сетевую настройку.

1. **Docker-сокет в WSL2:**
   * Канонический путь: `/var/run/docker.sock` (симлинк на `/mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock`).
   * **СТРОГО ЗАПРЕЩЕНО:** запускать глобальный поиск по файловой системе `find / -name "docker.sock" 2>/dev/null` — это намертво вешает агентский терминал на 15+ минут!
   * Если Docker возвращает ошибку `permission denied while trying to connect to the docker API`:
     права выдаются мгновенно от root WSL без пароля:
     ```bash
     wsl.exe -u root -e chmod 666 /mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock
     ```
2. **Контекст Docker:** Всегда `default` (unix-сокет), не переключать на `desktop-linux`.
3. **Параметры стенда `.tools/docker-dev`:**
   * Apache/App: `http://127.0.0.1:8030/` (контейнер `copytrust-dev-php-apache-1`).
   * MySQL: порт хоста `8031` (порт `3306` внутри `copytrust-dev-mysql-1`), пользователь `user`, пароль `password`, база `gb_copydev5`.

---

## 5.5. Проверка самого харнеса

После правок скриптов `test-task` запускать офлайн-проверку:

```bash
PYTHONPYCACHEPREFIX=/tmp/kilo/qa-pycache TMPDIR=/tmp/kilo \
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selftest.py
```

Проверка охватывает синтаксис Python, расположение вспомогательных скриптов,
G0 при успешной и неуспешной статике, принятие единственного AC-результата,
отказ при дубле или отсутствии AC, а также шесть сценариев выбора образа PHPStan.
Docker в сценариях выбора образа подменяется тестовой командой: образы не удаляются
и не собираются. Проверка не обращается к БД, браузеру и внешним LLM API.

## 6. Связь с планом задачи

План (`prepare-plan`) обязан иметь **per-patch test scenario** и Verification checklist.
После каждого патча R сразу гоняется его сценарий S. В конце «тестируй задачу»
закрывает таблицу веток. Канон: [testaudit.md §9](testaudit.md#9-когда-проверять-и-что-считать-веткой).
Чек-лист §7 эту таблицу не заменяет.

---

## 7. Чек-лист полноты (13 категорий)

Обязателен в `.doc/tasks/{N}/test.md` и в каждом отчёте `test-runs/` (§8).
Молчание запрещено.

| # | Категория | Что значит |
|---|---|---|
| 1 | Happy path | основной сценарий задачи с точки зрения пользователя |
| 2 | Негативные сценарии | отказ / валидация / неверные данные |
| 3 | Серверные/глобальные ошибки | 5xx, error-modal, необработанный fail |
| 4 | Уведомления/сообщения | toasted / flash / текст на экране |
| 5 | Побочные эффекты в БД | `seeInDatabase` / отсутствие лишних записей |
| 6 | Консоль браузера | нет неожиданных JS errors (checkpoint / seeNoConsoleErrors) |
| 7 | Network | критичные XHR/ответы, если применимо к задаче |
| 8 | Скриншот шага | через checkpoint или явный screenshot |
| 9 | DOM-дельта | через checkpoint |
| 10 | Идемпотентность | повтор действия не ломает состояние (если применимо) |
| 11 | Права доступа | чужой клиент / без роли не видит |
| 12 | Состояние после reload | F5 сохраняет ожидаемое |
| 13 | Соседние флоу (регрессия) | OUT callers / соседний flow из qa/index |

**П8 (долг):** хрупкие селекторы и `$I->wait(N)` в старых Cest - не копировать в новые
фрагменты (см. fragments П-1).

**П9 (кодировка seed):** текстовые колонки с не-ASCII не писать через Db-модуль
без HEX-проверки (latin1-соединение портит UTF-8). После первой записи сверить
`HEX(col)`: кириллица UTF-8 начинается с `D0`/`D1`. Скриншоты проверять не только
на layout, но и на читаемость текста (кракозябры вместо кириллицы = баг seed).

---

## 8. Стандарт отчёта прогона

Файл:

```
.doc/tasks/{N}/test-runs/{YYYY-MM-DD}_{HHMMSS}_{group}/report.md
```

Каталог прогона создаёт `task-test.sh`, отчёт собирает `make-report.py` из `scripts/` скила `test-task`
из артефактов run-dir. Каталога `qa/reports` не существует.

Обязательные секции:

1. **meta** (`type: test-run`, task, status, updated, related)
2. **Окружение** (стенд URL, клиент/админ, браузер, selenium да/нет)
3. **Область** (флоу, Cest/группы, Playwright-сценарии)
4. **Чек-лист полноты** - таблица по всем 13 категориям §7
5. **Пошаговый журнал** (что сделали, что увидели)
6. **Найденные расхождения** (баг в коде vs устаревший тест/контракт)
7. **Не проверено** (явный список + почему)
8. **Вердикт** (passed / failed / partial)

В чат - короткая сводка + ссылка на файл. Не копировать отчёт в `test.md`.

---

## 9. Повторное использование и консоль

Мелкие куски: методы `AcceptanceTester` (каталог qa/fragments.md в проекте Target).
Перед вызовом сверить, что метод **есть в PHP** - таблица фрагментов может опережать код.

Крупные куски: Cest флоу (`ClientCest`, `ItemDraftCest`, `TariffDeleteCest`) и
`Task/{N}/{Slug}Cest.php` с `@group task-{N}`. Повтор: `codecept run … -g <group>`.

Канон в git: `tools/codeception/`. Рабочая копия: `.tools/codeception/`.
**Acceptance в GitVerse CI не гоняется** (cicd.md (проект Target)).

Нет команды скила «тестируй все задачи». Полный suite (`codecept run Acceptance`
без `-g`) - только явная просьба: пишет в живую dev-БД, без populate/cleanup.

---

## Скилы (кто что делает)

| Команда пользователя | Скил | Роль |
|---|---|---|
| тестируй задачу [N] | **test-task** | конец: инвентарь веток, прогон, гейты |
| проверь этап R | **test-task** | сразу после патча: только сценарий S этого R |
| подготовь тест задачи N | prepare-task-test | создать Cest + test.md |
| проверь через браузер / e2e | browser-verify | прогон + отчёт §8 |
| войди как клиент N | login-as-user | имперсонация на dev |
| тестируй все задачи | нет скила | не делать по умолчанию; см. §9 |

Для воспроизводимого последовательного прогона списка задач используйте
`bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh N1 N2 ...` или `--file tasks.txt`.
Канон требований и веток логики: [testaudit.md §9](testaudit.md#9-когда-проверять-и-что-считать-веткой).

---

## Связи

- qa/index.md в проекте Target - реестр флоу
- qa/fragments.md в проекте Target - библиотека AcceptanceTester
- qa/browser-setup.md в проекте Target - Chrome / chromedriver / WSL
- [codeception/README.md](../../.tools/codeception/README.md) - установка и запуск
- [state/25-codeception-tools-move-2026-11-11.md](./state/25-codeception-tools-move-2026-11-11.md) - перенос рабочей копии suite в `.tools` и хостовый запуск
- cicd.md §3.5 (проект Target)
- [`.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md`](../../.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md)

---

## История изменений

- 2026-11-11: добавлен скрипт очистки прогонов старше 14 дней `cleanup-test-runs.py`; дата берётся из содержимого прогона, dry-run по умолчанию.
- 2026-11-11: браузерные доказательства `platform-browser-test` перенесены из `.doc/skil_data/copytrust/browser-test/` в `.doc/tasks/{N}/test-runs/{дата}_{platform}-browser/`; путь проверяет `validate_structure.py`.
- 2026-11-10: рабочая копия Codeception перенесена из `.doc/codeception/` в `.tools/codeception/`; обновлены пути симлинков задач, скрипты, правила и документация харнеса.
- 2026-11-10: хостовый запуск Codeception починен без Docker-образа: раннер добавляет `-d register_argc_argv=1`, команда в README и в разделе 5.2 обновлена.
- 2026-11-07: уточнены подключение локального ChromeDriver и расположение скриптов внутри `test-task`; исправлены пути загрузчика Cest, G0, фильтра ESLint и конфигурации релиза. Добавлены офлайн-регрессии харнеса, удалена зависимость selftest от задачи 2078. На основном стенде PHP 7.4 браузерный прогон задачи 2070 дал 10/10, общий `green=false` из-за статики и PHPUnit. Отчёт: прогон 2070 в проекте Target.
- 2026-11-06: основной стенд `.tools/docker-dev` переведен на PHP 7.4 (образ `copytrust-dev-php-apache:latest`, Dockerfile в `.tools/docker-dev/php-apache/`); PHPStan работает в том же образе, отдельный `copytrust-php74:local` не нужен.
- 2026-11-05: локальный стенд переведён на `.tools/docker-dev` и `.tools/docker-test` после переноса `tools/` в `.tools/`.
- 2026-09-26: сверка с фактическим состоянием QA-скриптов: гейты G0-G13 (G12 и G13
  реализованы в `qa/scripts/gates.py`), путь Cest задачи через симлинк `Task/{N}/`,
  запуск групп через `task-test.sh` (скрипта `run-codeception.sh` не существует),
  фактический путь отчёта прогона `test-runs/{RUN_DIR}/report.md` (каталога
  `qa/reports` нет)
