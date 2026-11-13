# Скрипт: `.agents/skills/harness-router/children/migration-review/scripts/review_migration.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, review_migration]
-->

## Суть
Обзор результата переноса харнеса в новый проект (или обновления существующего). Читает бэкап конфликтов (`.doc/.rebase-conflicts.json`, `.doc/.rebase-mcp-backup/cursor.mcp.json`), сканирует целевой проект на предмет локальных скилов (`scan_local_skills.py`), правил (`.cursor/rules/`, `.codex/rules/`, `.qoder/rules/`, `.qwen/rules/`) и MCP (сравнивает оригинальный и текущий `.cursor/mcp.json`). Формирует предложения: `install` (безопасно установить), `keep` (оставить kit-версию), `manual` (требует ручного слияния/решения). Поддерживает интерактивный режим, `--apply` (все безопасные), `--apply-skills/--apply-rules/--apply-mcp` (по типам), `--rm-backup` (удалить бэкап после проверки), `--report-only` (только отчёт). Запускает `sync-agent-views.sh` после применения.

## Когда запускать
- После `rebase_project.ps1` (миграция/обновление kit) — командой «обзор миграции», «проанализируй перенос», «установи локальные скилы после миграции».
- При повторном переносе (`update` mode) — для проверки правил без конфликтов скилов.
- Агент запускает с `--json` для программного разбора, `--apply --yes` для автоматического применения безопасных предложений.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --json |  | flag | нет |  | Машинный JSON-вывод |
| --interactive |  | flag | нет |  | Спросить перед применением безопасных предложений |
| --report-only |  | flag | нет |  | Не применять ничего, только отчёт |
| --apply |  | flag | нет |  | Применить все безопасные предложения (install) |
| --apply-skills |  | flag | нет |  | Применить безопасные skill-предложения |
| --apply-rules |  | flag | нет |  | Применить безопасные rule-предложения |
| --apply-mcp |  | flag | нет |  | Слить безопасные MCP-предложения |
| --rm-backup |  | flag | нет |  | Удалить бэкап миграции после ревью |
| --yes |  | flag | нет |  | Применить без интерактивного подтверждения |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | OK (нет ошибок, или --report-only) | Продолжить работу |
| 1 | Есть ошибки (partial status) | Исправить и повторить |

## Что читает и что пишет
**Читает:**
- `.doc/.rebase-conflicts.json` — отчёт конфликтов переноса (backup_dir, overwritten[], mode)
- `.doc/.rebase-kit.json` — маркер kit (mode: migrate/clean/update)
- `.doc/.rebase-mcp-backup/cursor.mcp.json` — оригинальный MCP конфиг
- `.cursor/mcp.json` — текущий MCP конфиг
- `scan_local_skills.py` — отчёт о локальных скилах
- `.cursor/rules/`, `.codex/rules/`, `.qoder/rules/`, `.qwen/rules/` — локальные правила
- `add_skill.py` — для установки скилов
- `sync-agent-views.sh` — для синхронизации после применения

**Пишет:**
- JSON-отчёт в stdout (или человекочитаемый текст)
- При `--apply`: устанавливает скилы (`add_skill.py`), копирует правила (`.cursor/rules/`), мержит MCP (`.cursor/mcp.json`), запускает `sync-agent-views.sh`
- При `--rm-backup`: удаляет `.doc/.rebase-backup/` и `.doc/.rebase-mcp-backup/`, обновляет `.doc/.rebase-conflicts.json` (backup_removed=true)

## Побочные эффекты
- Устанавливает скилы в канон (`.agents/skills/`).
- Копирует правила в `.cursor/rules/`.
- Мержит MCP конфиг.
- Запускает `sync-agent-views.sh` (обновляет зеркала).
- Удаляет бэкап миграции (при `--rm-backup`).

## Окружение и зависимости
- Python 3.7+ (argparse, datetime, json, re, shutil, subprocess, sys, pathlib, collections.Counter).
- `bash` для `sync-agent-views.sh`.
- `add_skill.py`, `scan_local_skills.py` (как подпроцессы/модули).

## Примеры
```bash
# Только отчёт (JSON)
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --json

# Интерактивный режим
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --interactive

# Применить все безопасные
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --apply --yes

# Только скилы
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --apply-skills --yes

# Удалить бэкап после проверки
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --rm-backup --yes
```

Пример JSON-вывода:
```json
{
  "status": "ok",
  "root": "/home/user/project",
  "mode": "migrate",
  "marker": {"mode": "migrate", "kit_version": "2026.11"},
  "backup": {
    "report": ".doc/.rebase-conflicts.json",
    "dir": ".doc/.rebase-backup/20261107T103000Z",
    "exists": true,
    "files": 45,
    "bytes": 1024000,
    "size": "1000.0 KB",
    "by_category": {"skill": 3, "rule": 12, "script": 5, "mcp": 2, "docs": 8, "other": 15},
    "mcp_dir": ".doc/.rebase-mcp-backup",
    "mcp_files": 1,
    "mcp_bytes": 2048,
    "mcp_size": "2.0 KB",
    "removed": false
  },
  "counts": {"skills": 5, "rules": 12, "mcp": 3, "manual": 2},
  "proposals": [
    {"kind": "skill", "name": "my-skill", "id": "my-skill", "env": "agents", "path": ".agents/skills/my-skill", "action": "install", "reason": "skill exists in canon but not in the package manifest"},
    {"kind": "rule", "name": "custom-rule", "source": ".qoder/rules/custom-rule.md", "target": ".cursor/rules/custom-rule.mdc", "action": "install", "reason": "local rule is not present in the canonical cursor rules"},
    {"kind": "mcp", "name": "legacy-mcp", "action": "install", "reason": "server exists in the original project config and is missing from the current canon"},
    {"kind": "skill", "name": "conflict-skill", "id": "conflict-skill", "env": "codex,qoder", "action": "manual", "reason": "the same skill exists in several views with different files"}
  ],
  "skill_scan": "ok",
  "applied": [],
  "backup_removed": [],
  "errors": []
}
```

## Ограничения
- `manual` предложения требуют ручного вмешательства (конфликты версий скилов, перезаписанные правила/скилы, MCP с разными настройками).
- `--apply` без `--yes` требует интерактивного терминала.
- Удаление бэкапа (`--rm-backup`) необратимо — только после полной проверки.
- Не обрабатывает `project-setup` (порты, индексы) — это отдельный этап (`onboard-project.py`).

## Связи
- Вызывается: агент по команде «обзор миграции», после `rebase_project.ps1`, `migration-review` скил
- Зависит от: `rebase_project.ps1` артефактов, `scan_local_skills.py`, `add_skill.py`, `sync-agent-views.sh`
- Результат используется: установка локальных компонентов, синхронизация сред, чистка бэкапа

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)