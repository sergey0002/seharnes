# Каталог `.tools`: окружения, серверы и системные утилиты

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ./05-scripts.md, ./11-dev-environment.md, ./25-codeception-tools-move-2026-11-11.md]
tags: [harness, tools, scripts, docker, tests]
-->

---

## Суть

`.tools` хранит локальные инструменты проекта: тестовый suite, Docker-окружения,
исходники собственных MCP-серверов и системные утилиты. Каталог не входит в
зеркала агентских сред и не коммитится. Скрипты MCP и инструментов лежат в
`scripts/` своих скилов, в `.tools/scripts` остаются только утилиты, не
принадлежащие одному скилу.

---

## 1. Состав каталога

| Путь | Роль |
|---|---|
| `.tools/codeception` | Рабочая копия Acceptance-suite: `tests`, `vendor`, `.env`, `codeception.yml`. Запуск и правила: [25-codeception-tools-move-2026-11-11.md](./25-codeception-tools-move-2026-11-11.md), [tests.md](../tests.md) |
| `.tools/docker-dev` | Основное dev-окружение: `php-apache`, `mysql`, `php7.1-cli`, `node-cli`. Порты задаёт `.tools/docker-dev/.env` |
| `.tools/docker-test` | Второй стенд для проверок, порты 8230 Apache, 8231 MySQL, 8232 SOAP из `.tools/docker-test/.env` |
| `.tools/mcp-servers/php-toolchain` | Исходник собственного MCP-сервера `server.js` в режимах `phpstan` и `php-deps`. Вызов: `.tools/scripts/node-mcp.sh` |
| `.tools/disk-scan` | Скрипты поиска занятого места на `C:` и в WSL2, README внутри каталога |
| `.tools/php85-scan` | Сканеры совместимости с PHP 8.5: `composer_matrix.py`, `deprecation-logger.php`, `deprecation_summary.py`, `fix_implicit_nullable.py`, `run.sh`, `scan.php` |
| `.tools/hermes` | Docker Compose окружение `nousresearch/hermes-agent` |
| `.tools/openhands` | Docker Compose окружение OpenHands, порт 3001 наружу в 3000 контейнера |
| `.tools/tasks` | Локальная символическая ссылка на `../.doc/tasks`; сами документы и данные задач остаются в `.doc/tasks`, ссылка не является частью kit |
| `.tools/scripts` | Системные утилиты харнеса, таблица ниже |

---

## 2. `.tools/scripts`

Документы скриптов лежат в
`.agents/skills/harness-router/children/harness-core/docs/scripts/tools/`.
Владелец документа - скил `harness-core`, по правилу
[`doc-script`](../../../.agents/skills/harness-router/children/doc-script/SKILL.md).

| Скрипт | Роль | Окружение |
|---|---|---|
| `mcp-shared-server.sh` | Поднимает общий HTTP-сервер из stdio MCP через `mcp-proxy`, слушает `127.0.0.1:<порт>` | `MCP_SHARED_*`, uv-кеш |
| `wait-for-ports.sh` | Ждёт TCP-порты перед стартом сервиса, таймаут `MCP_WAIT_TIMEOUT` | используется в `dsh-web.service` как `ExecStartPre` для порта 9131 |
| `node-mcp.sh`, `node-mcp.cmd` | Находит node для MCP php-toolchain и запускает переданную команду | `NODE_BIN`, `PATH`, `/mnt/c/Program Files/nodejs` |
| `php-docker.sh`, `php-docker.js`, `php-docker.ps1`, `php-docker.cmd` | Выполняет PHP в контейнере dev-стенда, переписывает пути проекта в `/var/www/html` | `DOCKER_PHP_CONTAINER`, по умолчанию `copytrust-dev-php-apache-1` |
| `mysql-mcp-proxy.mjs` | TCP-ретранслятор `127.0.0.1:3306` в опубликованный порт MySQL стенда | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_MCP_LISTEN_*` |
| `run-with-mcp-env.sh` | Загружает `MCP_ENV_FILE` или `.cursor/mcp.env` перед запуском команды; нужен Codex, где нет `envFile` | `MCP_ENV_FILE` |
| `multi-search.sh`, `multi-search.ps1` | Пакетный поиск N паттернов одним проходом rg или grep, JSON-lines. Правило [batch-calls](../../../.cursor/rules/batch-calls.mdc) | `--root`, `--pattern`, `--include` |
| `multi-exec.sh`, `multi-exec.ps1` | Пакетный запуск N команд и чтений с offset и limit, JSON-lines и `content_hash`. Правило [batch-calls](../../../.cursor/rules/batch-calls.mdc) | `--cmd`, `--read`, `--mode`, `--timeout` |

Поиск корня проекта. Скрипты, которым нужен корень, находят его подъёмом от своего
каталога до первого каталога с `.cursor` или `.git`. Поэтому они работают из
`.tools/scripts` и из `scripts/` скилов после переноса проекта.

---

## 3. Окружения и порты

| Стенд | Apache | MySQL | Примечание |
|---|---|---|---|
| `.tools/docker-dev` | `APACHE_PORT` из `.env` | `MYSQL_PORT` из `.env` | основная разработка, образ `copytrust-dev-php-apache` |
| `.tools/docker-test` | 8230 | 8231 | отдельный стенд для проверок, SOAP 8232 |

`mysql` MCP подключается к опубликованному порту MySQL через
`.tools/scripts/mysql-mcp-proxy.mjs`, потому что upstream MCP принимает host, но не
port.

---

## 4. Границы и правила

1. `.tools` исключён из git в `.git/info/exclude`, как `.cursor` и `.agents`.
2. `.tools` не копируется в `.agents`, `.codex`, `.kilo`, `.qoder` и `.qwen`;
   агентские среды получают только канон правил, скилов и MCP.
3. Секреты лежат в `.tools/*/.env` и `.cursor/mcp.env`, в документацию и чат не
   попадают.
4. Данные, кеши и результаты не кладутся в `.tools/scripts`; для временной работы
   используется `.doc/temp/`.
5. Перенос на другую машину: `.tools` входит в kit, если проект на него опирается.
   Экспорт MCP-стека складывает `.tools/scripts` в `config/scripts/tools/` и
   восстанавливает обратно.

---

## Связи

- [Скрипты контуров](./05-scripts.md) - карта скриптов по владельцам
- [Codeception в `.tools`](./25-codeception-tools-move-2026-11-11.md) - перенос suite и запуск
- [Тесты](../tests.md) - канон запуска тестов
- [MCP-стек](./15-mcp-stack.md) - порты, units, export и restore
- [Dev-окружение](./11-dev-environment.md) - WSL2, Docker и ограничения

---

## История изменений

- 2026-11-11: документ создан при переносе скриптов из `.cursor/scripts` в скилы и `.tools/scripts`.
