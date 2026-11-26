# Скрипт: `setup-workspace.py`

<!-- meta
type: script
status: actual
updated: 2026-11-24
related: [../../SKILL.md, workspace-gate.py.md, workspace-mcp.py.md]
tags: [harness, workspace, copy, migration]
-->

## Суть

Создаёт самостоятельную локальную копию проекта: копирует дерево SOURCE в пустой TARGET, пересобирает конфиги включённых сред внутри TARGET и ставит маркер готовности. После копирования установка и предмет анализа совпадают: `install = subject = TARGET`.

## Когда запускать

Один раз для новой пустой папки, когда нужна независимая копия проекта, зависимостей и харнеса без общей установки. Повторный запуск в ту же папку запрещён: маркер начала или готовности останавливает setup.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--source` | Существующий физический каталог SOURCE. Может не быть Git-репозиторием. |
| `--target` | Существующий физический каталог TARGET: пустой или только с собственной `.git`. |

## Коды выхода

`0` - копия готова и `.workspace-ready.json` записан; `78` - setup отказал или упал на любом шаге. После `78` TARGET остаётся для разбора, автоматического удаления и повторов нет.

## Что читает и что пишет

Читает дерево SOURCE, `.cursor/mcp.json`, реестр сред. Пишет полную копию в TARGET, `.workspace-setup.started` перед копированием и `.workspace-ready.json` после успешной синхронизации и prelaunch gate.

Точные исключения копирования:

| Путь или тип | Причина |
|---|---|
| `.git` на любом уровне | Сохраняется Git metadata TARGET, вложенные репозитории не переносятся |
| `.tools/hermes`, `.tools/openhands`, `.tools/disk-scan` | Стороннее runtime-состояние с недоступными файлами |
| `.codegraph`, `.doc/web/state` | Живой индекс и состояние сервиса |
| `.workspace-setup.started`, `.workspace-ready.json` | Готовность SOURCE не переносится |
| `*.pid`, `*.pid.lock`, `*.runtime.lock`, `*.sock`, `*-wal`, `*-shm` | Процессные файлы |
| sockets, FIFO, devices | Не рабочие файлы проекта |

Lockfiles зависимостей `composer.lock`, `package-lock.json`, `yarn.lock` сохраняются. Симлинки переносятся только относительные и разрешающиеся внутри SOURCE. Абсолютная, внешняя, битая, циклическая ссылка или ссылка на исключённый путь останавливает setup до создания маркера начала.

## Побочные эффекты

Запускает `rsync` без `--delete`, `--checksum`, `-H`, `--link-dest` и `--copy-links`. Затем запускает `sync-agent-views.sh --local-only --strict --replace-managed-mcp` и `workspace-gate.py --prepare` физически из TARGET, не из SOURCE. Секреты копируются, но не печатаются в stdout и stderr.

## Окружение и зависимости

Python 3, `rsync`, `bash`, `python3`, `node` в `PATH`. Дочерние процессы получают `HARNESS_SYNC_NO_PROMPT=1` и `PYTHONDONTWRITEBYTECODE=1`. Git не вызывается.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/setup-workspace.py \
  --source /ABS_SOURCE --target "$PWD"
```

## Ограничения

Не обновляет существующую песочницу, не удаляет TARGET после ошибки, не создаёт общую установку и не настраивает клиентов. Не обещает атомарный снимок работающей базы: SOURCE должен быть неподвижен. Копирование не изолирует базу, контейнеры и сетевые индексы.

## Связи

Вызывает [workspace-gate.py](workspace-gate.py.md) в режиме `--prepare` и `sync-agent-views.sh` из копии. Runtime-доступ MCP к копии даёт [workspace-mcp.py](workspace-mcp.py.md).

## История изменений

- 2026-11-24: создан скрипт самостоятельной копии workspace по плану доработки миграции.
