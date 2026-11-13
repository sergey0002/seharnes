# Скрипт: `.agents/skills/harness-router/children/improvement/scripts/runtime_registration.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, runtime_registration]
-->

## Суть
Проверяет регистрацию компонента в каноне (file parity) и best-effort runtime registration отдельно. Читает `component_registry.json`, для компонента проверяет наличие всех `required_files` на диске. Runtime-проверка: если переданы `--config` пути, проверяет их существование; если не переданы — сообщает, что runtime discovery API не вызывался. Не вызывает сами MCP-серверы — только проверяет наличие конфиг-файлов. Возвращает JSON-отчёт с file_parity (passed/failed) и runtime_registration (n/a/fallback + reason).

## Когда запускать
- В `validate_registry.py` как часть полной валидации реестра компонентов.
- При аудите MCP-серверов и компонентов харнеса.
- Агент может вызвать для проверки конкретного компонента перед использованием.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --component |  | string | да |  | Имя компонента (ключ в component_registry.json) |
| --root |  | Path | да |  | Корень проекта |
| --config |  | Path | нет | [] | Пути к конфиг-файлам для runtime-проверки (повторяемый) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | file_parity passed, runtime n/a или passed | Компонент зарегистрирован корректно |
| 1 | file_parity failed (есть missing required_files) | Добавить недостающие файлы или исправить реестр |
| 2 | Неизвестный компонент | Проверить --component |

## Что читает и что пишет
**Читает:**
- `.agents/skills/harness-router/children/improvement/scripts/component_registry.json` — реестр компонентов
- Файлы из `required_files` компонента (проверка существования)
- `--config` пути (проверка существования)

**Пишет:**
- JSON-отчёт в stdout: `{status, component, file_parity, runtime_registration}`

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.7+ (argparse, json, pathlib).
- Нет внешних зависимостей.

## Примеры
```bash
# Проверка компонента с runtime конфигами
python3 .agents/skills/harness-router/children/improvement/scripts/runtime_registration.py \
  --root . \
  --component codebase-memory-mcp \
  --config .cursor/mcp.json \
  --config .codex/mcp.json
```

Пример вывода (успех):
```json
{
  "status": "passed",
  "component": "codebase-memory-mcp",
  "file_parity": {"status": "passed", "missing": []},
  "runtime_registration": {
    "status": "n/a",
    "checked": [".cursor/mcp.json", ".codex/mcp.json"],
    "existing": [".cursor/mcp.json", ".codex/mcp.json"],
    "reason": "configuration exists; no runtime discovery API was invoked"
  }
}
```

Пример вывода (missing files):
```json
{
  "status": "failed",
  "component": "my-skill",
  "file_parity": {"status": "failed", "missing": [".agents/skills/my-skill/README.md"]},
  "runtime_registration": {"status": "n/a", "reason": "no environment-specific config paths supplied"}
}
```

## Ограничения
- Не вызывает реальные MCP-серверы — только проверяет наличие конфиг-файлов.
- Runtime registration считается "n/a" если конфиги есть, но API не вызывался; "fallback" если конфиги переданы но не существуют.
- Зависит от актуальности `component_registry.json` (обновляется `add_skill.py`, `remove_skill.py`, `validate_registry.py`).

## Связи
- Вызывается: `validate_registry.py`, агент вручную, `mcp-audit` (опционально)
- Зависит от: `component_registry.json`, структуры проекта
- Результат используется: валидация реестра, аудит компонентов

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)