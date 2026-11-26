# Скрипт: `workspace-mcp.py`

<!-- meta
type: script
status: actual
updated: 2026-11-24
related: [../../SKILL.md, setup-workspace.py.md, workspace-gate.py.md]
tags: [harness, workspace, mcp, acp]
-->

## Суть

Запускает один из трёх локальных stdio MCP серверов из cwd текущей сессии и закрепляет за ним TARGET. Нужен ACP и другим клиентам, которые передают только имя сервера, а не полный argv.

## Когда запускать

Из определения MCP каталога Kandev или другого клиента: `command=python3`, `args` содержат этот скрипт, `--server` и имя. Клиент сам выбирает cwd сессии, wrapper не ищет родительский репозиторий и не уходит в SOURCE.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--server` | Одно из трёх имён: `git`, `phpstan-mcp`, `php-deps-mcp`. Другие имена отклоняет `argparse`. |
| `--loaded-env` | Служебный флаг второго прохода: окружение уже загружено shell wrapper. |

## Коды выхода

`0` - процесс заменён MCP сервером; `2` - неизвестное имя сервера отклонил `argparse`; `78` - wrapper не принадлежит cwd, gate отказал, сервер выключен или не stdio.

## Что читает и что пишет

Читает `.omp/mcp.json`, `.cursor/mcp.env`, `.tools/scripts/run-with-mcp-env.sh` и `.workspace-ready.json` через gate. Ничего не пишет: stdout остаётся протоколу MCP, файлы сессии создаёт сам сервер.

Порядок:

1. `cwd` сессии разрешается в физический корень TARGET.
2. Скрипт проверяет, что физически лежит в этом TARGET.
3. `workspace-gate.py` подтверждает готовность копии.
4. Из `.omp/mcp.json` берётся включённая запись stdio выбранного сервера.
5. Если argv начинается с `bash <wrapper>`, wrapper один раз загружает `.cursor/mcp.env`.
6. `MCP_ENV_FILE` удаляется, `MCP_WORKSPACE` принудительно равен TARGET, затем идёт `execvpe` сервера.

## Побочные эффекты

Загружает env-файл через существующий shell wrapper и заменяет процесс. Env-файл и секреты не печатает. Sync, индексацию и правку секретов не выполняет.

## Окружение и зависимости

Python 3, `workspace-gate.py`, `.omp/mcp.json` с включённым stdio сервером и существующий `.tools/scripts/run-with-mcp-env.sh` для серверов с env-файлом. Обычный stdout и stderr нужны протоколу.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/workspace-mcp.py --server phpstan-mcp
```

## Ограничения

Не выбирает SOURCE и не ищет ближайший родительский репозиторий. Не запускает выключенный сервер и не добавляет режим совместимости с общим PHP toolchain. HTTP серверы, база, Jira и сетевые индексы остаются общими ресурсами.

## Связи

Проверяет копию через [workspace-gate.py](workspace-gate.py.md), читает проекцию `.omp/mcp.json` из [generate-omp-config.py](generate-omp-config.py.md), использует PHP root guard из `.tools/mcp-servers/php-toolchain/lib/resolve-php.js`.

## История изменений

- 2026-11-24: создан cwd-разрешающий wrapper ACP для трёх локальных серверов.
