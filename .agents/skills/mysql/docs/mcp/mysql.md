# MCP: mysql

<!-- meta
type: config
status: actual
updated: 2026-11-05
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md]
tags: [harness, mcp, db, stand]
-->

---

## Суть

Схема и данные dev-стенда через прокси. Схема читается `describe_table`, запросы `query`, изменения только `execute` и только с разрешения пользователя.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/mysql.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `run-with-mcp-env.sh` плюс `mysql-mcp-proxy.mjs` |
| Стенд | `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=8031` |
| База | `gb_copydev5` |
| Прокси | слушает `127.0.0.1:3306`, переводит на порт стенда |
| Секреты | `.cursor/mcp.env` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: bash /home/newuser/projects/copytrust/testdeploydocker/.tools/scripts/run-with-mcp-env.sh node` |
| Переменные окружения | `MYSQL_DATABASE`, `MYSQL_HOST`, `MYSQL_MCP_LISTEN_HOST`, `MYSQL_MCP_LISTEN_PORT`, `MYSQL_PORT`, `MYSQL_USER` |
| Учетная запись | `MYSQL_USER` равен `user`; пароль хранится в `MYSQL_PASSWORD` и не печатается |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

- `connect_db`, `list_tables`, `describe_table`, `query` в `alwaysAllow`.
- `mysql execute` только с явного разрешения пользователя.

---

## Правила использования

1. Схема только через `describe_table`, колонки не выдумывать.
2. `query` для чтения, `execute` после подтверждения.
3. DDL и миграции вручную, не через MCP.
4. Не запускать тяжелые выборки на стенде без необходимости.

---

## Установка и перенос

- Стенд: `copytrust-dev-php-apache-1` публикует приложение на `127.0.0.1:8030`, `copytrust-dev-mysql-1` публикует MySQL на `127.0.0.1:8031`. Состав стенда задает `tools/docker-test/compose.yaml`, образ базы лежит в `tools/docker-test/mysql/`.
- Приложение читает доступы из `.env` корня проекта: `DB_SERVER=mysql`, `DB_DATABASE=gb_copydev5`, `DB_SERVER_USERNAME=root`, пароль в `DB_SERVER_PASSWORD`. Внутри контейнера хост базы `mysql`, снаружи `127.0.0.1:8031`.
- MCP читает доступы из `.cursor/mcp.env`: `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=8031`, `MYSQL_USER=user`, `MYSQL_PASSWORD`, `MYSQL_DATABASE=gb_copydev5`. Значения `MYSQL_USER`, `MYSQL_PASSWORD` и `MYSQL_DATABASE` совпадают с переменными контейнера `copytrust-dev-mysql-1`.
- Аккаунт `user` создает образ MySQL при первом старте. На базе `gb_copydev5` он имеет SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX, TRIGGER и другие права. Аккаунт `root` из `.env` нужен приложению, MCP его не использует.
- Запуск: `run-with-mcp-env.sh` читает `.cursor/mcp.env`, затем `mysql-mcp-proxy.mjs` поднимает relay `127.0.0.1:3306` на `127.0.0.1:8031` и запускает `@f4ww4z/mcp-mysql-server` через `npx`. Relay нужен потому, что `connect_db` upstream не принимает порт.
- Перенос: скопировать `.tools/scripts/mysql-mcp-proxy.mjs` и `.cursor/mcp.env`, изменить `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE` под новый стенд, затем выполнить `sync-agent-views.sh` и parity-проверку.

---

## Несколько проектов

- stdio-сервер запускается на каждый проект отдельно; стенд и база задаются в `.cursor/mcp.env` проекта.
- Один клиент проекта держит relay `127.0.0.1:3306`. Остальные клиенты того же проекта получают `EADDRINUSE`, пишут `assuming relay is already active` и переиспользуют этот relay.
- Второй проект нельзя разделить только сменой `MYSQL_MCP_LISTEN_PORT`: upstream `connect_db` не принимает порт и всегда подключается к 3306. Проекты разделяются loopback-адресом в `MYSQL_MCP_LISTEN_HOST`, например `127.0.0.2`: relay второго проекта слушает `127.0.0.2:3306`.
- Не направлять сервер на чужой стенд и не выполнять `execute` без разрешения.

---

## Проверка

- `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=mysql`. Ответ `SKIP` нормален, когда relay 3306 уже держит другой клиент: smoke не запускает второй stdio-процесс.
- `connect_db` с `host=127.0.0.1` возвращает `Successfully connected to database`. Логин, пароль и база подставляются из `.cursor/mcp.env`.
- `list_tables` возвращает таблицы базы. На 2026-11-05: 116 таблиц.
- `describe_table` с `table=ct_order` возвращает колонки `id`, `clientId`, `orderStatusId` и остальные.
- `query` с `SELECT DATABASE() AS db, (SELECT COUNT(*) FROM ct_order) AS orders` возвращает `db=gb_copydev5`. На 2026-11-05: 1843 заказа, 9720 клиентов, 33 тарифа, 305 записей миграций.
- Приложение: `curl -s -o /dev/null -w '%{http_code}' http://localhost:8030/` возвращает 200, страница `/tariffs` тоже 200 без ошибок SQL.
- Доступы приложения проверяются из контейнера `copytrust-dev-php-apache-1`: PHP с `PDO` по значениям `.env` выполняет `SELECT COUNT(*) FROM ct_order` и получает число строк.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - маршрут по данным
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - порты и данные
- [Скрипты](../../../../../.doc/harnes/state/05-scripts.md) - прокси и обертка env

---

## Известные проблемы и ограничения

### П-1: Подключение не проходит

- Симптом: `connect_db` возвращает ошибку соединения.
- Причина: контейнер стенда не поднят или порт 8031 занят.
- Решение: поднять стенд и проверить `127.0.0.1:8031`.
- Файлы: `.tools/scripts/mysql-mcp-proxy.mjs`

### П-2: В ответе нет нужной колонки

- Симптом: `query` не возвращает ожидаемое поле.
- Причина: схему не читали через `describe_table`.
- Решение: сначала выполнить `describe_table`, затем запрос.
- Файлы: `.doc/harnes/mcp/mysql.md`

### П-3: Relay 3306 занят другим клиентом

- Симптом: в stderr `mysql-mcp-proxy: port 3306 is already in use, assuming relay is already active`, а `test-mcp-servers.mjs --only=mysql` отвечает `SKIP`.
- Причина: у каждого клиента свой stdio-процесс, relay на хосте один и слушает 3306.
- Ограничение: пока процесс-владелец жив, запросы идут через него. Если он завершится, процесс без своего relay не перебиндится до перезапуска клиента.
- Файлы: `.tools/scripts/mysql-mcp-proxy.mjs`

### П-4: Пароли приложения и MCP не совпадают

- Симптом: `DB_SERVER_PASSWORD` в `.env` отличается от `MYSQL_PASSWORD` в `.cursor/mcp.env`.
- Причина: приложение работает под `root`, MCP под `user`. Оба аккаунта существуют в контейнере базы и видят `gb_copydev5`.
- Решение: не копировать пароль `root` в `.cursor/mcp.env`; сверять `MYSQL_USER`, `MYSQL_PASSWORD` и `MYSQL_DATABASE` с переменными контейнера `copytrust-dev-mysql-1`.
- Файлы: `.env`, `.cursor/mcp.env`, `tools/docker-test/compose.yaml`

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-05: проверена рабочая связка стенда и MCP: контейнеры 8030 и 8031, доступы из `.env` и `.cursor/mcp.env`, relay 3306. Добавлены раздел проверки, ограничение общего relay и правило разделения проектов по loopback-адресу.
