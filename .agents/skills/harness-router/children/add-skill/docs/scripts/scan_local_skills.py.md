# Скрипт: `.agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, scan_local_skills]
-->

## Суть
Сканирует харнес и находит скилы, существующие вне пакетного baseline (`.doc/skil_data/harness-core/kit-manifest.json`). Сравнивает канон (`.agents/skills/`) и view-среды (`.codex/skills/`, `.qoder/skills/`, `.qwen/skills/`, `.kilo/skills/`) с baseline. Классифицирует скилы на категории: `canon_local` (в каноне, нет в пакете), `view_local` (только в одной view), `package_view` (в пакете, но не в каноне), `conflict` (один id в нескольких view с разными файлами), `package_modified` (в каноне, но изменён относительно пакета), `mirror_drift` (view отличается от канона), `name_collision` (разные id с одинаковым именем), `missing` (в пакете, но нет на диске). Может писать baseline из текущего канона (`--write-baseline`).

## Когда запускать
- Перед установкой локальных скилов (`add_skill.py` использует его отчёт).
- После миграции харнеса для аудита локальных компонентов.
- При команде «найди локальные скилы», «скилы вне пакета».
- В CI для контроля дрифта зеркал.
- Агент запускает с `--json` для программного разбора.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --baseline |  | string | нет | `.doc/skil_data/harness-core/kit-manifest.json` | Путь к baseline манифесту |
| --write-baseline |  | flag | нет |  | Записать baseline из текущего канона |
| --include-generated |  | flag | нет |  | Включить Qwen rule-* скилы (сгенерированные) |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (включая --write-baseline) | Продолжить работу |

## Что читает и что пишет
**Читает:**
- `.agents/skills/` — канон (рекурсивно ищет SKILL.md)
- `.codex/skills/`, `.qoder/skills/`, `.qwen/skills/`, `.kilo/skills/` — view-среды
- Baseline: `.doc/skil_data/harness-core/kit-manifest.json` (или --baseline)

**Пишет:**
- Baseline JSON (при `--write-baseline`): `{schema: 1, generated_at, source: "canon", skills: {id: {name, digest}}}`
- JSON-отчёт в stdout (при `--json`) или человекочитаемый текст.

## Побочные эффекты
- Записывает baseline файл при `--write-baseline`.

## Окружение и зависимости
- Python 3.7+ (argparse, datetime, hashlib, json, os, sys, tempfile, pathlib, dataclasses, collections.Counter).
- Нет внешних зависимостей.

## Примеры
```bash
# Сканирование с человекочитаемым выводом
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --root .

# JSON для автоматизации
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --root . --json

# Записать baseline из текущего канона
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --root . --write-baseline

# Своя baseline
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --root . --baseline /path/to/manifest.json
```

Пример человекочитаемого вывода:
```
Проверка скилов вне пакета
  канон: 42 скилов
  манифест пакета: .doc/skil_data/harness-core/kit-manifest.json
  в каноне, нет в пакете: 3
  только в среде: 2
  пакетные скилы вне канона: 1
  конфликт версий: 1
  изменены относительно пакета: 0
  зеркала расходятся с каноном: 2
  имя занято другим скилом: 0
  нет на диске: 0
  canon_local: my-skill (.agents/skills/my-skill)
  canon_local: custom-router (.agents/skills/harness-router/children/custom-router)
  view_local: codex-only-skill (codex)
  conflict: shared-skill (codex, qoder)
  установить: python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --name <name> --yes
  кандидаты: my-skill custom-router codex-only-skill
  конфликтующие версии требуют --from codex|qoder|qwen|kilo
```

Пример JSON-вывода (--json):
```json
{
  "status": "ok",
  "root": "/home/user/project",
  "baseline": {"path": "...", "exists": true, "skills": 39},
  "canonical": 42,
  "counts": {
    "canon_local": 3,
    "view_local": 2,
    "package_view": 1,
    "conflict": 1,
    "package_modified": 0,
    "mirror_drift": 2,
    "name_collision": 0,
    "missing": 0
  },
  "skills": {
    "canon_local": [{"id": "my-skill", "name": "my-skill", "env": "agents", "path": ".agents/skills/my-skill", "digest": "..."}],
    "view_local": [{"id": "codex-only", "name": "codex-only", "sources": [{"id": "codex-only", "name": "codex-only", "env": "codex", "path": ".codex/skills/codex-only", "digest": "..."}]}],
    "conflict": [{"id": "shared-skill", "name": "shared-skill", "sources": [...]}]
  },
  "installable": ["my-skill", "custom-router", "codex-only"],
  "errors": []
}
```

## Ограничения
- Baseline опционален: без него нельзя отличить `canon_local` от пакетных, и `package_view`/`missing` не определяются.
- SHA256 digest считается по всем текстовым файлам скила (исключая SKIP_PARTS и скрытые).
- Qwen rule-* скилы исключены по умолчанию (сгенерированные); `--include-generated` включает их.
- Не проверяет семантическую эквивалентность — только побайтовое совпадение файлов.

## Связи
- Вызывается: `add_skill.py` (внутри), `migration-review.py` (scan_skills), агент вручную
- Зависит от: структуры `.agents/skills/`, view-сред, baseline манифеста
- Результат используется: `add_skill.py --all`, `migration-review.py`, аудит харнеса

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)