# Браузер для тестов: Chrome, chromedriver, Playwright MCP (WSL)

<!-- meta
type: config
status: actual
updated: 2026-11-07
related: [index.md, ../harnes/tests.md, ../codeception/README.md]
tags: [qa, e2e, chrome, chromedriver, playwright, wsl, codeception]
-->

---

## Суть

На WSL без `sudo apt` для Google Chrome поставлен **Chrome for Testing** +
matching **ChromeDriver**, плюс wrapper для Playwright MCP по пути
`/opt/google/chrome/chrome`. Это нужно слою 1 (Codeception Acceptance) и
слою 2 (Playwright MCP headed). Без этого `browser-verify` падает с
"chrome not found" / "chromedriver не запущен".

Каноническая инструкция по установке и запуску - этот файл.
Краткие ссылки: [codeception/README.md](../../.tools/codeception/README.md),
[qa/index.md](index.md), [tests.md](../harnes/tests.md).

---

## Что установлено (WSL, без системного apt Google Chrome)

| Компонент | Путь / как |
|---|---|
| Chrome for Testing | `~/.local/chrome-for-testing/chrome-linux64/chrome` |
| ChromeDriver (та же major-версия) | `~/.local/chrome-for-testing/chromedriver-linux64/chromedriver` |
| Wrapper с `LD_LIBRARY_PATH` | `~/.local/chrome-for-testing/chrome-wrap.sh` |
| Старт chromedriver `:9515` | [start-chromedriver-wsl.sh](../../.agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh) |
| Shared libs (из `.deb` без install) | `~/.local/chrome-deps/root/...` |
| Путь для Playwright channel `chrome` | `/opt/google/chrome/chrome` (shell-wrapper на chrome-for-testing) |
| Опционально: Selenium Grid в Docker | контейнер `selenium/standalone-chrome`, порт `4444` (env Codeception `chromedriver.yml`) |

Версия на стенде (пример): Chrome / ChromeDriver **151.0.7922.34**
(брать пару с [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/)).

Источник: zip с Chrome for Testing + chromedriver, распаковка в
`~/.local/chrome-for-testing/`. Зависимости `.so` (nspr, nss, asound, …) -
`apt-get download` + `dpkg-deb -x` в `~/.local/chrome-deps/` (passwordless
`sudo` не требуется). После распаковки zip: `chmod +x` на `chrome`,
`chrome_crashpad_handler`, `*.so`, `chromedriver`.

`/opt/google/chrome/chrome` создан через Docker root-mount на хостовый `/opt`
(локальный `sudo` без TTY недоступен). Содержимое - скрипт, который выставляет
`LD_LIBRARY_PATH` и `exec` на chrome-for-testing.

---

## Быстрая проверка "всё живо"

```bash
# Chrome
~/.local/chrome-for-testing/chrome-wrap.sh --version
/opt/google/chrome/chrome --version

# Chromedriver (после старта) — правильный path: /wd/hub/status
curl -sS http://127.0.0.1:9515/wd/hub/status
# ожидаем "ready": true

# Опционально Selenium Docker
curl -sS http://127.0.0.1:4444/status
# ожидаем "ready": true

# Стенд приложения
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8030/
```

### AI / sandbox: ложный "стенд недоступен" (обязательно)

Cursor agent часто гоняет Shell в **sandbox**, где `curl`/`ss` к
`127.0.0.1:8030` и `:9515` дают HTTP `000` / connection refused, хотя у
пользователя в браузере `http://localhost:8030/...` уже открывается.

**Запрещено** писать пользователю "стенд лёг" / "chromedriver недоступен",
опираясь только на такой ответ из sandbox.

Порядок:

1. Повторить проверку **вне sandbox** (`required_permissions: ["all"]`):
   `curl` на `8030/`, `9515/wd/hub/status`, при сомнении `ss -ltn | grep -E '8030|9515'`.
2. Только после `HTTP 200` / `"ready":true` (или явного отказа вне sandbox)
   формулировать статус стенда.
3. Если пользователь пишет, что UI открывается, а агент видит `000` —
   верить пользователю и перепроверить с `all`, не спорить и не поднимать
   стенд "с нуля" без спроса.
4. Chromedriver нужен только для Codeception WebDriver. Ручной Chrome и
   Playwright MCP headed — это не доказательство, что `:9515` мёртв, и
   наоборот: живой UI на `:8030` не заменяет chromedriver для `task-test.sh`.
5. **Бинарник ≠ процесс.** Если
   `~/.local/chrome-for-testing/chromedriver-linux64/chromedriver` executable,
   а `curl :9515/wd/hub/status` не отвечает - писать "chromedriver не запущен",
   **не** "chromedriver нет / не установлен". Лечение - команда старта ниже.
   Инцидент CT-2607: агент путал закрытый порт с отсутствием драйвера.

---

## Запуск chromedriver (слой 1, порт 9515) — видимое окно

Из корня репо (агентам: всегда с `required_permissions: ["all"]`):

```bash
bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh
```

Скрипт сам выставляет `LD_LIBRARY_PATH` (без него сырой `chromedriver` падает
на `libnspr4.so`), `DISPLAY=:0` при WSLg, `--port=9515 --url-base=/wd/hub
--allowed-origins=*` (нужно docker-раннеру Codeception; раннер подключается к
`127.0.0.1:9515` через `docker run --network host`). Chrome открывается **headed** - окно на экране
Windows. `--headless` в args suite и в этом скрипте запрещён.

Скилы: [test-task](../../.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md#chromedriver-бинарник-vs-процесс),
[browser-verify](../../.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md) (§ Chromedriver перед слоем 1).

Пауза между шагами теста (чтобы успевать смотреть клики):

```bash
# в .tools/codeception/.env или в окружении прогона
QA_VISIBLE_DELAY=0.3
```

По умолчанию `QA_VISIBLE_DELAY=0`: пауза выключена. Пауза 0.3-0.4с на каждый
шаг добавляла около 20с к одному тесту. Хелпер: `Tests\Support\Helper\VisibleBrowser`.

Раннер `task-test.sh` предпочитает порт 9515 (окно на экране) порту 4444
(Selenium в Docker — смотреть только через noVNC `:7900`).

Или вручную:

```bash
export LD_LIBRARY_PATH="$HOME/.local/chrome-deps/root/usr/lib/x86_64-linux-gnu:$HOME/.local/chrome-deps/root/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$HOME/.local/chrome-for-testing/chromedriver-linux64/chromedriver" \
  --port=9515 --whitelisted-ips= --url-base=/wd/hub
```

Лог: `~/.local/chrome-for-testing/chromedriver-9515.log`.

### `.doc/codeception/.env` (WSL / docker-dev)

| Переменная | Типичное значение на этом стенде |
|---|---|
| `CHROMEDRIVER_HOST` | `127.0.0.1` |
| `CHROMEDRIVER_PORT` | `9515` |
| `CHROMEDRIVER_APP_URL` | `http://127.0.0.1:8030/` (не `copytrust.test`, если хост не резолвится в WSL) |
| `CHROMEDRIVER_CHROME_BINARY` | `/home/<user>/.local/chrome-for-testing/chrome-wrap.sh` |
| MySQL | как у стенда (`127.0.0.1:8031` для `.tools/docker-dev`) |

Шаблон: [`.env.dist`](../../.tools/codeception/.env.dist).

### Запуск Codeception

Стенд поднят (`.tools/docker-dev` или `.tools/docker-test`), chromedriver на `:9515`:

```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh <N> --phase browser --group <group>
```

Примеры групп: `account-signin`, `item-draft`, `task-2466` (см. [qa/index.md](index.md)).

**Env `chromedriver`:** файл
[`tests/_envs/chromedriver.yml`](../../.tools/codeception/tests/_envs/chromedriver.yml)
переключает WebDriver на `127.0.0.1:4444` (Selenium standalone). Если крутится
только классический chromedriver на `9515` - либо подними Selenium на `4444`,
либо гоняй suite **без** `--env chromedriver` (тогда порт берётся из `.env` =
`9515`).

### Selenium Docker вместо локального chromedriver

```bash
docker start selenium-chrome-test
# или: docker run -d --name selenium-chrome-test -p 4444:4444 -p 7900:7900 --shm-size=2g selenium/standalone-chrome:4.21.0
```

VNC/noVNC: порт `7900`. Для Codeception: `--env chromedriver` (порт 4444).
`CHROMEDRIVER_CHROME_BINARY` в Grid обычно не нужен (chrome внутри контейнера).

### Изолированный Codeception runner (docker-dev + Selenium)

Сайт на `8030` крутится в `copytrust-dev-php-apache` (PHP 7.4.33). Codeception
всегда запускается отдельно в `copytrust-codecept:8.3` (PHP 8.3), даже если на
хосте установлен другой PHP. Раннер не запускает PHP сайта и не меняет его версию.

PHPUnit 4.8.36 остаётся на PHP 7.4 в приложении: legacy bootstrap `tests/maket.php`
не запускается в PHP 8.3. Операционная точка входа: [tests.md §5.1](../harnes/tests.md#51-слой-0-phpunit-универсальный-канон-запуска).

Канон прогона задачи: `bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N}`.
Раннер всегда использует `copytrust-codecept:8.3` и автоматически собирает образ из `.doc/qa/docker/Dockerfile`.
Вспомогательные скрипты лежат в `scripts/` скила `test-task`; каталога `.doc/qa/scripts` нет.

**Проверка:**

```bash
which php          # версия на хосте не влияет на Codeception runner
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8030/   # 200/302 - стенд жив
```

**Ручной fallback: suite через Selenium + закреплённый runner:**

```bash
docker start selenium-chrome-test

docker run --rm --network container:selenium-chrome-test \
  -e CHROMEDRIVER_HOST=127.0.0.1 -e CHROMEDRIVER_PORT=4444 \
  -v "$PWD:/app" -w /app/.tools/codeception copytrust-codecept:8.3 \
  vendor/bin/codecept run Acceptance TariffDeleteCest --env chromedriver \
  -o 'modules: config: WebDriver: capabilities: goog:chromeOptions: args: ["--no-sandbox", "--disable-gpu", "--remote-allow-origins=*", "--host-resolver-rules=MAP localhost 172.17.0.1"]'
```

(из корня репо; для другого Cest заменить имя класса.)

**`.env` для этого режима** (дополнительно к таблице выше):

| Переменная | Значение | Зачем |
|---|---|---|
| `MYSQL_HOST` | `172.17.0.1` | MySQL `:8031` с docker bridge, не `127.0.0.1` из контейнера |
| `CHROMEDRIVER_PORT` | `4444` | Selenium Grid |
| `CHROMEDRIVER_APP_URL` | `http://localhost:8030/` | htaccess whitelist; chrome внутри Selenium резолвит `localhost` → хост |

`host-resolver-rules` обязателен: прямой заход на `172.17.0.1:8030` ломает redirect
в `.htaccess` (`ERR_INVALID_REDIRECT`).

Канон тестов в git: `tools/codeception/`; рабочий vendor - `.doc/codeception/`.
Рабочий контур текущей проверки находится в `.doc/codeception/`. Изменение локального окружения не требует править отслеживаемый `tools/codeception/`.

---

## Playwright MCP (слой 2)

Конфиг: [`.cursor/mcp.json`](../../.cursor/mcp.json) → сервер `playwright`.

| Env | Назначение |
|---|---|
| `PLAYWRIGHT_MCP_EXECUTABLE_PATH` | `~/.local/chrome-for-testing/chrome-wrap.sh` |
| `CHROME_PATH` | тот же wrapper |
| `LD_LIBRARY_PATH` | `~/.local/chrome-deps/root/usr/lib/x86_64-linux-gnu:...` |

Канал по умолчанию ищет `/opt/google/chrome/chrome` - wrapper там уже стоит.

После правки `mcp.json`: Reload MCP / перезапуск Cursor, иначе процесс
останется со старым env.

Браузер **headed** (видимый). Флаг `--headless` в args MCP не добавлять.

Dev-вход под клиентом (без пароля, только стенд):

```
http://127.0.0.1:8030/.doc/codeception/scripts/dev-login.php?as=client&id=<clientId>
```

Dev-вход в админку (без SmartCaptcha POST-формы, только dev/test):

```
http://127.0.0.1:8030/.doc/codeception/scripts/dev-login.php?as=admin
```

Скрипт ставит cookie `login`/`pass` с `path=/` (как `admin/index.php` после успешного
входа). Капча проверяется только при POST логина/пароля - см. `admin/index.php`.
`AcceptanceTester::loginAsAdmin()` вызывает этот URL перед `/admin/`.

Затем UI, например `/order/main` (клиент) или `/admin/m_tariff.php` (админ).

Если после пересборки JS счётчики Vue остались `0`: сбросить кеш профиля
Playwright (`~/.cache/ms-playwright/mcp-chrome-*/Default/Cache`) и hard reload.
См. ниже про webpack.

---

## После правок фронта (store/service в basepack)

Store/service (`scripts/stores/module/*`, `scripts/services/*`) попадают в
браузер через `frontend/dist/basepack.js`, не напрямую с диска.

```bash
npm run dev    # или npm run prod
# Smarty compile/cache после правок .tpl:
find templates_c cache -type f -delete   # из корня репо на стенде
```

Без пересборки `basepack` UI может показывать старый store (например
`Не оплачено (0)` при живом API `unpaidCount>0`).
Подробнее: architecture/frontend.md (`../architecture/frontend.md`; missing in kit) §сборка.

---

## Ассеты и кеш перед сбросом

Если правка `.tpl`/CSS/JS не видна на странице, сначала установи, что именно загрузил браузер: `document.styleSheets[].href` для CSS, `script.src` для JS, текущий DOM и `getComputedStyle` целевого элемента. Сверь URL ассета с путём редактируемого файла и сборкой из frontend.md (`../architecture/frontend.md`; missing in kit); наличие правки на диске не означает, что страница использует этот файл. Если файл загружен, но правило не действует, проверь приоритет селекторов и кеш-версию. Только после этого выбирай пересборку, hard reload либо очистку Smarty-кеша, если подтверждено, что проблема именно в них.

В задаче #2596 статическая страница брала стили из `frontend/dist/styles.css`, а правки находились в `styles/css/style.css`, который на странице не загружался. Это был mismatch ассетов, а не подтверждённый дефект Smarty-кеша.

---

## Типичные ошибки

| Симптом | Что сделать |
|---|---|
| `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome` | Проверить wrapper `/opt/google/chrome/chrome --version`; env в `mcp.json`; Reload MCP |
| `libnspr4.so: cannot open shared object file` | Выставить `LD_LIBRARY_PATH` на `~/.local/chrome-deps/...` или звать через `chrome-wrap.sh` |
| `chrome_crashpad_handler: Permission denied` | `chmod +x ~/.local/chrome-for-testing/chrome-linux64/chrome*` |
| Codeception не коннектится к WebDriver | `curl :9515/wd/hub/status` или `:4444/status`; сверить порт `.env` vs `--env chromedriver` |
| `Could not resolve host: copytrust.test` | В `.env` поставить `CHROMEDRIVER_APP_URL=http://127.0.0.1:8030/` |
| UI 0 при API > 0 после правки Order store | `npm run dev` + clear Smarty + clear Chrome cache Playwright |
| «неправильный защитный код» на `/admin/` | POST-логин требует Yandex SmartCaptcha; для Cest - `dev-login.php?as=admin` |
| `invalid cookie domain` в WebDriver | `setCookie` до первого успешного `amOnPage` на домен APP_URL; предпочтительно dev-login |
| `Duplicate entry` в Db модуле | dev-БД уже содержит фикстуры; upsert в `AcceptanceTester`, не слепой `haveInDatabase` |
| HTTP 500 на `/` из Selenium | корень может падать; для admin-login открывать `dev-login.php` или `/admin/index.php` |

---

## Связи

- [qa/index.md](index.md) - слои проверки, реестр флоу
- [../codeception/README.md](../../.tools/codeception/README.md) - composer, `.env`, запуск suite
- [../tests.md](../harnes/tests.md) - план развития тестовой системы
- [../../.cursor/README.md](../../.cursor/README.md) §playwright - инструменты MCP
- ../../.codex/skills/task-router/children/testing-router/children/browser-verify/SKILL.md (`../../.codex/skills/task-router/children/testing-router/children/browser-verify/SKILL.md`; missing in kit) - порядок browser-verify
- ../architecture/frontend.md (`../architecture/frontend.md`; missing in kit) - webpack / basepack

---

## Известные проблемы и ограничения

### П-1: Нет passwordless sudo на WSL
- Симптом: `apt install google-chrome-stable` / symlink в `/opt` через sudo падают
- Решение: Chrome for Testing в `~/.local` + libs через `apt-get download`;
  `/opt/google/chrome` через docker root-mount
- Файлы: пути в таблице выше

### П-2: Два порта WebDriver (9515 vs 4444)
- Симптом: `--env chromedriver` идёт на 4444, а локальный драйвер слушает 9515
- Решение: либо Selenium на 4444, либо suite без этого env при работе с 9515
- Файлы: `tests/_envs/chromedriver.yml`, `.env`

### П-4: Нет PHP CLI на WSL при живом docker-dev
- Симптом: `which php` пусто; «сайт же работает»
- Причина: PHP сайта находится в контейнере Apache (7.4); Codeception 5 требует PHP 8.2+
- Решение: запускать `task-test.sh`, который использует `copytrust-codecept:8.3`; установка PHP на хост для проверки не нужна
- Файлы: cicd.md §3.2 (`../architecture/cicd.md#32-wsl-и-docker-dev-php-сайта--php-для-codeception`; missing in kit)

### П-5: Selenium в Docker не достаёт до APP на хосте
- Симптом: chrome error page, connection refused
- Решение: `--network container:selenium-chrome-test`; `CHROMEDRIVER_APP_URL=http://localhost:8030/`; chrome arg `--host-resolver-rules=MAP localhost 172.17.0.1`
 - Файлы: `.doc/codeception/.env`, команда в § «Изолированный Codeception runner» выше

### П-6: MySQL из контейнера codecept
- Симптом: PDO connection refused к `127.0.0.1:8031`
- Решение: `MYSQL_HOST=172.17.0.1` (docker bridge к порту MySQL на хосте)
- Файлы: `.doc/codeception/.env`

### П-7: SmartCaptcha на входе в админку
- Симптом: «Был введён неправильный защитный код!» после submit формы
- Причина: `admin/index.php` вызывает `SmartCaptchaService` только при POST
- Решение: `dev-login.php?as=admin` или cookie login (без POST); не патчить капчу в прод-коде
- Файлы: `.doc/codeception/scripts/dev-login.php`, `AcceptanceTester::loginAsAdmin()`

### П-8: Фикстуры vs живая dev-БД
- Симптом: duplicate PK (`ct_country` 268, `ct_user` 1, `ct_tariff` 7)
- Решение: `grabNumRecords` + `updateInDatabase` в хелперах; тестовые тарифы 900x+
- Файлы: `tools/codeception/tests/Support/AcceptanceTester.php`

### П-9: Тестовые тарифы ломают главную `/`
- Симптом: HTTP 500 на `/`, admin работает; `Call to a member function getBase() on null` в `TariffController::getShortData`
- Причина: Cest создал тарифы с `visible=1` и uac, но без `tariff2service`; главная рендерит все видимые тарифы
- Решение: в хелперах `visible=0`; `_after` cleanup; после прогона проверить `curl :8030/` (см. cicd.md §3.6 (`../architecture/cicd.md#36-данные-acceptance-на-dev-стенде-гигиена`; missing in kit))
- Задача: CT-2428

---

## История изменений

- 2026-11-07: зафиксирован основной стенд PHP 7.4 на 8030, запуск скриптов из скилов и подключение локального ChromeDriver через host network. Браузерный прогон 2070: 10/10; общий вердикт остаётся отрицательным из-за других проверок.
- 2026-11-24: Codeception закреплён на PHP 8.3 в отдельном Docker runner; PHP хоста больше не выбирает runtime тестов.
- 2026-11-05: локальный стенд и синхронизация Codeception переведены на `.tools/` после переноса `tools/` в `.tools/`.
- 2026-11-05: ссылки на `test-task` и `browser-verify` переведены на `.agents/skills/task-router/children/testing-router/children/`; Codex-ссылка ведёт в иерархическое зеркало.
- 2026-09-25: перед очисткой кеша добавлена проверка реально загруженных CSS/JS и computed styles по аудиту задачи #2596
- 2026-09-15: §WSL - ссылка на cicd.md §3.2 (карта PHP); канон `task-test.sh` / `copytrust-codecept:8.3`; apt php-cli не нужен
- 2026-08-12: WSL без host PHP, Selenium+php:8.3-cli, dev-login admin, П-4..П-9 (CT-2428)
- 2026-07-17: документ создан по факту установки Chrome for Testing + chromedriver
  на WSL (browser-verify CT-2061 и соседние задачи)
