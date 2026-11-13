# MCP: git

<!-- meta
type: config
status: actual
updated: 2026-11-01
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md]
tags: [harness, mcp, git]
-->

---

## Суть

Локальные git-операции по репозиторию проекта: статус, история, диф, show и blame. Мутации требуют подтверждения и идут через скилы, не напрямую.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/git.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `uvx mcp-server-git --repository ${workspaceFolder}` |
| Репозиторий | корень проекта, `${workspaceFolder}` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: uvx mcp-server-git --repository` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

| Инструмент | Параметры | Зачем |
|---|---|---|
| `git_status` | `repo_path` | состояние рабочей копии |
| `git_log` | `repo_path`, `max_count`, `start_timestamp`, `end_timestamp` | история коммитов |
| `git_diff` | `repo_path`, `target`, `context_lines` | разница веток и коммитов |
| `git_diff_unstaged` / `git_diff_staged` | `repo_path`, `context_lines` | локальные правки |
| `git_show` | `repo_path`, `revision` | коммит или файл |
| `git_blame` | `repo_path`, `file_path` | автор строк |
| `git_branch` | `repo_path`, `branch_type`, `contains`, `not_contains` | список веток |
| `git_add` | `repo_path`, `files` | подготовить файлы |
| `git_commit` | `repo_path`, `message` | локальный коммит |
| `git_checkout` | `repo_path`, `branch_name` | переключение ветки |
| `git_create_branch` | `repo_path`, `branch_name`, `base_branch` | создать ветку |
| `git_reset` | `repo_path` | снять staged |

Чтение в `alwaysAllow`: `git_status`, `git_log`, `git_diff`, `git_show`,
`git_blame`. Мутации требуют подтверждения. Push через MCP не выполняется, для
него скил `send-to-git`.

---

## Правила использования

1. Чтение свободно, мутации только через скилы.
2. Ветка: `gototask`, артефакты: `task-diff`, commit и push: `send-to-git`.
3. Не коммитить локальный агентский setup (`.cursor/`, `.dsh/`, `.doc/`).

---

## Установка и перенос

- Установка: `uvx mcp-server-git --repository ${workspaceFolder}`; нужен `uv` и Python.
- Перенос: скопировать запись `git`; `--repository` указывает на корень git-репозитория, не на подкаталог.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=git`.

## Несколько проектов

- stdio-сервер запускается на каждый проект отдельно; один процесс видит только свой `--repository`.
- Не передавать путь другого проекта: операции и коммиты уйдут не туда.
- История и ветки у каждого проекта свои; глобального состояния нет.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - правила чтения и мутаций
- [Правило задач](../../../../../.cursor/rules/bitbucket-tasks.mdc) - ветки, коммиты, push
- [Скил отправки](../../../send-to-git/SKILL.md) - согласование и push

---

## Известные проблемы и ограничения

- Симптом: push из MCP не выполняется.
  Причина: `mcp-server-git` не содержит push.
  Решение: скил `send-to-git` и явная просьба пользователя.

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
