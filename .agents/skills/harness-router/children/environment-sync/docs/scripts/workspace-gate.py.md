# Скрипт: `workspace-gate.py`

<!-- meta
type: script
status: actual
updated: 2026-11-24
related: [../../SKILL.md, setup-workspace.py.md, workspace-mcp.py.md]
tags: [harness, workspace, gate, prelaunch]
-->

## Суть

Проверяет, что копия workspace готова к запуску, и при успехе заменяет процесс клиентом. Работает в двух режимах: `--prepare` для записи маркера во время setup и без флага для prelaunch проверки по маркеру.

## Когда запускать

В prefix выбранного профиля клиента перед каждым запуском и перезапуском, и один раз из `setup-workspace.py` с `--prepare`. Gate принадлежит копии, поэтому его запускают из TARGET, а не из SOURCE.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--prepare` | Проверить копию и пересобранные конфиги без маркера и затем выйти с `0`. Требует `--source` и не принимает команду. |
| `--source` | Физический путь SOURCE. Обязателен только вместе с `--prepare`. |
| `--` | Отделяет команду клиента. Всё после `--` gate выполняет через `os.execvp`. |
| `command` | Позиционный остаток после `--`: команда клиента и её аргументы. Без него gate только проверяет копию. |

## Коды выхода

`0` - проверки прошли, команда клиента (если была) запущена или заменена; `78` - проверка не прошла, клиент не запускается.

## Что читает и что пишет

Читает `.workspace-ready.json`, `.omp/mcp.json`, `.cursor/mcp.json`, входные точки и вывод `render_agent_views.py --check`. В режиме `--prepare` ничего не пишет. В prelaunch режиме ничего не пишет, только читает и запускает клиента.

Проверки:

1. Gate физически лежит в `cwd` по относительному пути своего скила.
2. Корневые каталоги `.agents`, `.cursor`, `.tools` не симлинки.
3. Входные точки `run-with-mcp-env.sh`, `node-mcp.sh`, `php-toolchain/server.js`, оба скрипта PHPStan не симлинки, существуют и разрешаются внутри TARGET.
4. `render_agent_views.py --check` подтверждает свежие представления всех включённых сред.
5. `.omp/mcp.json` совпадает с проекцией трёх серверов.
6. Ни одна включённая запись MCP не содержит путь SOURCE как отдельный сегмент пути.

## Побочные эффекты

Запускает `render_agent_views.py --check` и импортирует `generate-omp-config.py` из TARGET. В prelaunch режиме заменяет текущий процесс командой клиента через `os.execvp`. Глобальные настройки и HOME не меняет.

## Окружение и зависимости

Python 3, `render_agent_views.py`, `generate-omp-config.py` и включённый генератор `.omp` в той же установке. Нужен `.omp/mcp.json`: если omp выключат, gate откажет явно и не включит среду сам.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/workspace-gate.py --prepare --source /ABS_SOURCE
python3 .agents/skills/harness-router/children/environment-sync/scripts/workspace-gate.py -- omp acp
```

## Ограничения

Маркер не является границей безопасности против произвольного владельца TARGET. Копия без Git проходит gate, а Git MCP при вызове сообщает отсутствие репозитория. Проверка не доказывает работоспособность установленного binary клиента и не запускает модели.

## Связи

Вызывается [setup-workspace.py](setup-workspace.py.md) в режиме `--prepare`, [workspace-mcp.py](workspace-mcp.py.md) перед стартом MCP и prefix профиля клиента при запуске и перезапуске.

## История изменений

- 2026-11-24: создан prelaunch gate самостоятельной копии; путь SOURCE ищется как отдельный сегмент, чтобы соседняя папка с похожим именем не давала ложный отказ.
