# Скрипт: `.agents/skills/harness-router/children/mcp-audit/scripts/scan-usage.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, scan-usage]
-->

## Суть
Находит, где имена MCP-серверов (из `.cursor/mcp.json` → `mcpServers`) используются по всему харнесу. Сканирует корни: `.cursor/`, `.codex/`, `.kilo/`, `.qoder/`, `.qwen/`, `.agents/`, `.doc/harnes/mcp/`. Ищет в текстовых файлах (JSON, TOML, YAML, MD, JS/TS, PY, SH, PS1). Выводит JSON: `{servers: {server_name: [sorted_unique_file_paths]}}`. Используется для аудита: найти неиспользуемые серверы, серверы, прописанные в view но не в каноне, и наоборот.

## Когда запускать
- При аудите MCP (`mcp-audit` скил): «проверь MCP», «аудит MCP».
- После добавления/удаления сервера в `.cursor/mcp.json`.
- При миграции харнеса для проверки полноты переноса MCP.
- Агент запускает для понимания распространённости сервера перед удалением/переименованием.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | Продолжить работу |

## Что читает и что пишет
**Читает:**
- `.cursor/mcp.json` — список серверов (ключи mcpServers)
- Файлы в сканируемых корнях (рекурсивно) с расширениями: .json, .jsonc, .toml, .yaml, .yml, .md, .mdc, .js, .mjs, .ts, .py, .sh, .ps1

**Пишет:**
- JSON в stdout: `{servers: {server_name: [file_paths...]}}`

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.7+ (argparse, json, sys, pathlib).
- Нет внешних зависимостей.

## Примеры
```bash
python3 .agents/skills/harness-router/children/mcp-audit/scripts/scan-usage.py --root .
```

Пример вывода:
```json
{
  "servers": {
    "codebase-memory-mcp": [
      ".cursor/mcp.json",
      ".cursor/mcp.env",
      ".agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh",
      ".codex/mcp.json",
      ".kilo/kilo.jsonc",
      ".agents/skills/codebase-memory-mcp/SKILL.md",
      ".doc/harnes/mcp/codebase-memory-mcp.md"
    ],
    "serena": [
      ".cursor/mcp.json",
      ".codex/mcp.json",
      ".kilo/kilo.jsonc",
      ".agents/skills/serena/SKILL.md"
    ],
    "mysql": [
      ".cursor/mcp.json",
      ".cursor/mcp.env",
      ".codex/mcp.json"
    ],
    "graphify": [
      ".cursor/mcp.json",
      ".doc/harnes/mcp/graphify.md"
    ],
    "sourcegraph": [],
    "xdebug": []
  }
}
```

## Ограничения
- Простой строковый поиск (`name in text`) — может дать ложные срабатывания (подстроки в комментариях, других именах).
- Не проверяет семантическое использование (enabled/disabled, реальные вызовы).
- Не сканирует бинарные файлы, node_modules, vendor, .git.
- Только текстовые расширения из списка TEXT.

## Связи
- Вызывается: `mcp-audit` скил, агент вручную
- Зависит от: `.cursor/mcp.json`, структуры харнеса
- Результат используется: аудит непокрытых/лишних серверов, проверка синхронизации view

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)