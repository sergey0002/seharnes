# MCP: php-deps-mcp

<!-- meta
type: config
status: actual
updated: 2026-11-11
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md]
tags: [harness, mcp, php, dependencies]
-->

---

## Суть

Граф зависимостей и вызовов PHP: phpcallgraph и phpda. Нужен для blast radius после codegraph и перед рефакторингом общих компонентов.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/php-deps-mcp.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | тот же `.tools/mcp-servers/php-toolchain/server.js` |
| Режим | `MCP_PHP_TOOLCHAIN_MODE=php-deps` |
| Окружение | `MCP_WORKSPACE` в `mcp.json`; `PHP_BIN` из `mcp.env` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: bash ${workspaceFolder}/.tools/scripts/node-mcp.sh ${workspaceFolder}/.tools/mcp-servers/php-toolchain/server.js` |
| Переменные окружения | `MCP_PHP_TOOLCHAIN_MODE`, `MCP_WORKSPACE`, `PHP_BIN` |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

- `phpcallgraph_generate`: `sourcePath`, `outputFile`, `format` (`svg`, `png`, `dot`), `ignorePattern`.
- `phpda_analyze`: `configFile`, по умолчанию `phpda.xml`.

---

## Правила использования

1. Для blast radius после codegraph.
2. Перед рефакторингом shared-компонента.
3. Для визуализации зависимостей модуля.

---

## Установка и перенос

- Установка: `.tools/mcp-servers/php-toolchain` (каталог `.tools` вне git), `node-mcp.sh`, `PHP_BIN`; phpcallgraph PHAR и phpda ставятся в toolchain.
- Перенос: скопировать toolchain и запись `php-deps-mcp`; проверить `MCP_WORKSPACE`, `PHP_BIN` и наличие `phpda.xml`.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=php-deps-mcp`.

## Несколько проектов

- stdio-сервер на каждый проект; `MCP_WORKSPACE` задает корень.
- `phpda.xml` и `vendor/` берутся из проекта; один процесс не анализирует два проекта.
- Артефакты графов складывать в рабочий каталог проекта, не в `.doc`.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - маршрут blast radius
- [Планирование](../../../../../.doc/harnes/state/08-plan-contour.md) - лестница исследования

---

## Известные проблемы и ограничения

- Симптом: phpda не запускается.
  Причина: нет `phpda.xml` или конфиг указывает на неверный путь.
  Решение: создать конфиг в корне или передать `configFile`.

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-11: php-toolchain перенесён из `.cursor/mcp-servers` в `.tools/mcp-servers`; конфиги сред и перенос kit обновлены, копии в зеркалах `.codex` и `.agents` удалены.
