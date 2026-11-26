# Запуск автотестов

Полная инструкция по Chrome / chromedriver / Playwright на WSL:
**[`.doc/qa/browser-setup.md`](../../.doc/qa/browser-setup.md)**.

**Порядок проведения тестов** (PHPUnit → Codeception → проверка после прогона):
**cicd.md §3.5 (`../../.doc/architecture/cicd.md#35-как-проводить-проверку-порядок-работ`; missing in kit)**.

## Подготовка
0. Для установки зависимостей нужен Composer. Сам Codeception запускается в
   Docker-образе `copytrust-codecept:8.3`; PHP хоста не выбирает runtime тестов.
1. Установить зависимости для codeception:
   - `cd .tools/codeception`
   - `composer install`
2. Скопировать и отредактировать `.tools/codeception/.env.dist` в `.tools/codeception/.env`
   - необходимо указать url (IP адрес) и порт для запущенных тестового сервера и БД.
     В зависимости от места запуска тестов (командная строка Windows, WSL и т.п.) нужно указать правильный url и порт.
     Важно не перепутать с url сервера и БД для разработки.
   - WSL + `tools/docker-dev`: часто `CHROMEDRIVER_APP_URL=http://127.0.0.1:8030/`,
     `CHROMEDRIVER_HOST=127.0.0.1`, `CHROMEDRIVER_PORT=9515`,
     `CHROMEDRIVER_CHROME_BINARY=$HOME/.local/chrome-for-testing/chrome-wrap.sh`
     (детали в [browser-setup.md](../../.doc/qa/browser-setup.md)).
3. Запустить тестовый сервер и БД через docker из папки `tools/docker-test`
   (или использовать уже поднятый `tools/docker-dev` на `:8030` / MySQL `:8031`).

## Локально через chromedriver (WSL)

1. Chrome for Testing + chromedriver - см. [browser-setup.md](../../.doc/qa/browser-setup.md)
   (пути `~/.local/chrome-for-testing/`, libs в `~/.local/chrome-deps/`).
2. Старт драйвера на `:9515`:

```bash
bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh
```

   Альтернатива: Selenium Grid Docker на `:4444` (`docker start selenium-chrome-test`)
   и запуск с `--env chromedriver` (этот env жёстко ставит порт 4444).

3. Из корня проекта:

```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh <N> \
  --phase browser --group <group>
```

Команда запускает закреплённый PHP 8.3 runner. Прямой запуск `php vendor/bin/codecept` на хосте не используется.

Без Selenium на 4444 можно опустить `--env chromedriver` и использовать порт
`9515` из `.env` (см. П-2 в browser-setup).

## WSL с локальным Chromedriver (docker-dev)

Codeception всегда работает в Docker-образе `copytrust-codecept:8.3`, а браузер
подключается к локальному Chromedriver на `:9515`. Полная схема и `.env`:
[browser-setup.md: изолированный Codeception runner](../../.doc/qa/browser-setup.md).

Канон тестов в git: `tools/codeception/`. Локальный vendor: `.tools/codeception/`.
После прогона на dev: `curl :8030/` должен быть 200 (см. cicd §3.6 (`../../.doc/architecture/cicd.md#36-данные-acceptance-на-dev-стенде-гигиена`; missing in kit)).

## Windows (классический путь)

1. Скачать и распаковать chrome for testing и соответствующую версию chromedriver
   (https://googlechromelabs.github.io/chrome-for-testing/)
2. Запустить chromedriver:
   `chromedriver --port=9515 --whitelisted-ips= --url-base=/wd/hub`
3. В `.env` указать `CHROMEDRIVER_CHROME_BINARY` на `chrome.exe`
4. Запуск suite как выше.
