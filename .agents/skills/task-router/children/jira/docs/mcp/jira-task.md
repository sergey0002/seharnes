# MCP: jira-task

<!-- meta
type: config
status: actual
updated: 2026-11-01
related: [../../../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../../../.doc/harnes/state/04-mcp.md]
tags: [harness, mcp, tracker, jira]
-->

---

## Суть

Экспорт задачи Jira в `task.md` и список задач релиза. Вызывается скриптами скилов, вручную агентом не используется.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/jira-task.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `docker exec -i copytrust-dev-php-apache-1 php /var/www/html/.agents/skills/task-router/children/jira/scripts/server.php` |
| Контейнер | `copytrust-dev-php-apache-1` |
| Сервер | `.agents/skills/task-router/children/jira/scripts/server.php` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: docker exec -i` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

| Инструмент | Параметры | Зачем |
|---|---|---|
| `export_task_md` | `issue_id`: номер `2538`, ключ `CT-2538` или URL | записать `task.md` |
| `list_release_tasks` | `release_version`: `5.7.2` или `releases/5.7.2` | задачи релиза |

---

## Правила использования

1. Вызывают `gototask` и `task-intake`, не агент напрямую.
2. `task.md` автогенерируемый, руками не править; обновление повторным экспортом.
3. Секреты Jira в `.doc/skil_data/jira/config.env`; сервер получает путь через `JIRA_CONFIG_FILE`.

---

## Установка и перенос

- Установка: контейнер стенда с `.agents/skills/task-router/children/jira/scripts/server.php` и `config.env`; отдельный пакет не ставится.
- Перенос: скопировать `.doc/skil_data/jira`, заполнить `config.env`, проверить имя контейнера в `.cursor/mcp.json`.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=jira-task`.

## Несколько проектов

- Один контейнер и один `config.env` на проект; ключи Jira не общие.
- Сервер stdio поднимается в контейнере проекта; чужой контейнер не использовать.
- Для другого проекта меняется имя контейнера в конфиге и путь к серверу.

## Связи

- [Карта MCP](../../../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../../../.doc/harnes/state/04-mcp.md) - правила экспорта
- [Правило задач](../../../../../../../.cursor/rules/bitbucket-tasks.mdc) - порядок чтения задачи
- [Скил gototask](../../../gototask/SKILL.md) - переход к задаче

---

## Известные проблемы и ограничения

- Симптом: экспорт падает.
  Причина: контейнер стенда не запущен или нет `config.env`.
  Решение: поднять стенд, заполнить секреты.

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
