# Запуск автотестов

Полная инструкция по Chrome / chromedriver / Playwright на WSL:
**[`.doc/qa/browser-setup.md`](../../.doc/qa/browser-setup.md)**.

**Порядок проведения тестов** (PHPUnit → Codeception → проверка после прогона):
**[cicd.md §3.5](../../.doc/architecture/cicd.md#35-как-проводить-проверку-порядок-работ)**.

## Подготовка
0. Для локального запуска:
   - `Установить php 8.3: powershell -c "& ([ScriptBlock]::Create((irm 'https://www.php.net/include/download-instructions/windows.ps1'))) -Version 8.3"`
   - `Включить в php.ini extesnsion: curl, mbstring, openssl, zip, pdo_mysql`
   - `Установить composer https://getcomposer.org/Composer-Setup.exe`
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
php -d register_argc_argv=1 .tools/codeception/vendor/bin/codecept -c .tools/codeception/codeception.yml \
  run Acceptance --env chromedriver -g <group>
```

Флаг `-d register_argc_argv=1` обязателен: Codeception проверяет эту настройку и без неё падает с `register_argc_argv must be set to On`. Раннер `task-test.sh` уже передаёт флаг сам.

Без Selenium на 4444 можно опустить `--env chromedriver` и использовать порт
`9515` из `.env` (см. П-2 в browser-setup).

## WSL без PHP на хосте (docker-dev)

Если `which php` пусто, а стенд на `:8030` поднят в Docker - гоняй Codeception
из контейнера `php:8.3-cli` в сети Selenium. Полная команда и `.env`:
[browser-setup.md §WSL без PHP CLI](../../.doc/qa/browser-setup.md#wsl-без-php-cli-на-хосте-docker-dev--selenium).

Канон тестов в git: `tools/codeception/`. Локальный vendor: `.tools/codeception/`.
После прогона на dev: `curl :8030/` должен быть 200 (см. [cicd §3.6](../../.doc/architecture/cicd.md#36-данные-acceptance-на-dev-стенде-гигиена)).

## Windows (классический путь)

1. Скачать и распаковать chrome for testing и соответствующую версию chromedriver
   (https://googlechromelabs.github.io/chrome-for-testing/)
2. Запустить chromedriver:
   `chromedriver --port=9515 --whitelisted-ips= --url-base=/wd/hub`
3. В `.env` указать `CHROMEDRIVER_CHROME_BINARY` на `chrome.exe`
4. Запуск suite как выше.
