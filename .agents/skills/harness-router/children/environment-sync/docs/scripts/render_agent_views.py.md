# Скрипт: `render_agent_views.py`

<!-- meta
type: script
status: actual
updated: 2026-11-13
related: [../../SKILL.md]
tags: [harness, sync, views, renderer]
-->

## Суть

Пересобирает project-local представления правил, скилов и MCP текущими доверенными генераторами. Заменяет Bash-оркестрацию для генерации views, не запуская скрипты из каталога, который рендерится.

## Когда запускать

После `harness_transfer.py apply` для authored-файлов и перед проверкой parity. Для чтения без записи использовать `--check`.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--root` | Существующий корень проекта, чьи views нужно собрать. |
| `--check` | Проверить views существующими `--check` режимами генераторов без записи. |

## Коды выхода

`0` - views собраны или проверка прошла; `2` - генератор отсутствует, упал или вернул ошибку.

## Что читает и что пишет

Читает `.cursor/rules`, `.agents/skills`, `.cursor/mcp.json`, `.dsh` и существующие настройки. В режиме записи меняет только generated views и `.agents/rules`; в режиме `--check` не пишет.

## Побочные эффекты

Запускает фиксированный список Python-генераторов из текущего установленного харнеса. Удаляет `__pycache__` и legacy `.kilo/mcp.json` после записи.

## Окружение и зависимости

Python 3. Нужны генераторы `generate-agent-configs.py`, `generate-codex-mcp.py`, `generate-mcp-config.py`, `generate-qoder-config.py`, `generate-qwen-config.py`, `generate-antigravity-rules.py` и `generate-dsh-config.py` в том же каталоге.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/render_agent_views.py --root . --check
python3 .agents/skills/harness-router/children/environment-sync/scripts/render_agent_views.py --root .
```

## Ограничения

Скрипт не выполняет pre-scan/adopt локальных Qoder-компонентов сверх preflight генератора, не копирует `mcp.env` в чужие домашние каталоги, не настраивает Docker и не публикует релиз. Qoder generator может отказать при неразобранном локальном компоненте; это ожидаемый `failed_preflight`. Windows-native входы вне области.

## Связи

Вызывается `harness_transfer.py render`. Дополняет `sync-agent-views.sh`, который остаётся полной синхронизацией с глобальными настройками и проверками parity.

## История изменений

- 2026-11-13: добавлен Python-renderer project-local views на текущих генераторах.
