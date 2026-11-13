# Скрипт: `.agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, remove_skill]
-->

## Суть
Удаляет скил из канона харнеса (`.agents/skills/`), всех зеркал (`.codex/skills/`, `.qoder/skills/`, `.qwen/skills/`, `.kilo/skills/`), документации (`.doc/harnes/skills/{name}.md`, `.doc/harnes/skills/README.md`, `.doc/harnes/index.md`, `.doc/harnes/state/02-skills.md`), реестра компонентов (`.agents/skills/harness-router/children/improvement/scripts/component_registry.json`), родительского роутера (skill.json родителя). Создаёт бэкап в `.doc/skil_data/harness-core/removed/{timestamp}/{env}/{id}/`. Собирает ссылки на скил в кодовой базе (SKILL.md, docs, state, registry, rules, mcp) и зависимости (skill.json других скилов). Блокирует удаление, если скил используется как зависимость (если не `--force`). Запускает `rebuild-routers.py --write`, `sync-agent-views.sh`, валидаторы (`validate_skills.py`, `validate_registry.py`, `rebuild-routers.py --check`).

## Когда запускать
- При команде «удали скил», «убери скил из харнеса», «удали локальный скил», «почисти ссылки на скил».
- После рефакторинга/объединения скилов.
- Агент запускает с `--yes --json` для автоматизации.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --name |  | string | да |  | Имя скила или relative id (в каноне или view) |
| --dry-run |  | flag | нет |  | Вывести план без записи |
| --yes |  | flag | нет |  | Применить без интерактивного подтверждения |
| --force |  | flag | нет |  | Удалить даже если скил используется как зависимость |
| --no-backup |  | flag | нет |  | Не сохранять бэкап удалённого скила |
| --no-sync |  | flag | нет |  | Пропустить sync-agent-views.sh |
| --no-validate |  | flag | нет |  | Пропустить валидаторы после удаления |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (или dry-run) | Продолжить работу |
| 1 | Ошибки (зависимости без --force, sync/validate failed, отмена) | Исправить и повторить |
| 2 | Скил не найден или неоднозначный | Проверить --name |

## Что читает и что пишет
**Читает:**
- Канон: `.agents/skills/{name}/` (SKILL.md для имени)
- View-среды: `.codex/skills/`, `.qoder/skills/`, `.qwen/skills/`, `.kilo/skills/`
- Документация: `.doc/harnes/skills/{name}.md`, `.doc/harnes/skills/README.md`, `.doc/harnes/index.md`, `.doc/harnes/state/02-skills.md`
- Реестр: `.agents/skills/harness-router/children/improvement/scripts/component_registry.json`
- Родительский skill.json (если скил в children/)
- Поиск ссылок: `.agents/skills/`, `.cursor/rules/`, `.doc/harnes/`, `.doc/qa/`, `AGENTS.md`, `.cursor/mcp.json`, `.cursor/mcp.jsonc`, `component_registry.json`

**Пишет:**
- Удаляет директории скила из канона и view.
- Удаляет карточку `.doc/harnes/skills/{name}.md`.
- Чистит строки в `.doc/harnes/skills/README.md`, `.doc/harnes/index.md`, `.doc/harnes/state/02-skills.md` (удаляет секцию 5 если пуста).
- Удаляет запись из `component_registry.json` (и каскадно dependent компоненты).
- Обновляет родительский skill.json (children[]).
- Бэкап: `.doc/skil_data/harness-core/removed/{timestamp}/{env}/{id}/`
- Запускает `rebuild-routers.py --write`, `sync-agent-views.sh`, валидаторы.

## Побочные эффекты
- Удаляет файлы скила из всех сред.
- Меняет документацию, реестр, роутеры.
- Запускает синхронизацию и валидацию.

## Окружение и зависимости
- Python 3.7+ (argparse, datetime, json, re, shutil, subprocess, sys, pathlib, dataclasses).
- `bash` для `sync-agent-views.sh`.
- `rebuild-routers.py`, `validate_skills.py`, `validate_registry.py` (подпроцессы).

## Примеры
```bash
# Удалить скил с подтверждением
python3 .agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py --root . --name my-skill

# Без подтверждения, с JSON
python3 .agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py --root . --name my-skill --yes --json

# Force (если есть зависимости)
python3 .agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py --root . --name my-skill --force --yes

# Dry-run
python3 .agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py --root . --name my-skill --dry-run

# Без бэкапа и синка
python3 .agents/skills/harness-router/children/remove-skill/scripts/remove_skill.py --root . --name my-skill --yes --no-backup --no-sync
```

Пример JSON-вывода:
```json
{
  "status": "ok",
  "skill": {"id": "my-skill", "name": "my-skill", "env": "agents", "path": ".agents/skills/my-skill"},
  "removed": [
    "backup:.doc/skil_data/harness-core/removed/20261107T103000Z/agents/my-skill",
    "delete:.agents/skills/my-skill",
    "delete:.codex/skills/my-skill",
    "delete:.doc/harnes/skills/my-skill.md",
    "lines:.doc/harnes/skills/README.md:1",
    "lines:.doc/harnes/index.md:1",
    "lines:.doc/harnes/state/02-skills.md:2",
    "section:.doc/harnes/state/02-skills.md:5",
    "registry",
    "parent-router"
  ],
  "references": [
    {"path": ".agents/skills/harness-router/SKILL.md", "line": 45, "kind": "router", "text": "`my-skill`"},
    {"path": ".doc/harnes/state/02-skills.md", "line": 12, "kind": "state", "text": "| my-skill | [my-skill](../skills/my-skill.md) | ..."}
  ],
  "unresolved": [
    {"path": ".agents/skills/harness-router/SKILL.md", "line": 45, "kind": "router", "text": "`my-skill`"}
  ],
  "errors": []
}
```

## Ограничения
- Не удаляет пакетные скилы (из baseline kit-manifest.json) — только локальные (canon_local, view_local, conflict).
- `--force` обходит проверку зависимостей, но не каскадно удаляет зависимые скилы — они останутся с битыми зависимостями.
- Поиск ссылок — строковый (regex по имени/id), может дать false positive/negative.
- Не чистит `.doc/skil_data/{skill}/` — данные скила остаются (ручная чистка при необходимости).
- `sync-agent-views.sh` перестраивает зеркала; если скил был в view — исчезнет оттуда.

## Связи
- Вызывается: агент по команде «удали скил», `harness-router` → `remove-skill`
- Зависит от: `rebuild-routers.py`, `sync-agent-views.sh`, валидаторов improvement
- Результат использует: синхронизированные среды, чистые индексы, реестр

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)