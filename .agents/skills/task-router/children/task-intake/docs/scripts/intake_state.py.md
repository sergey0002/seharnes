# Скрипт: `.agents/skills/task-router/children/task-intake/scripts/intake_state.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md, ../../../documentation-router/children/project-doc/scripts/task-identity.py]
tags: [harness, script, task-intake, intake-state, preflight]
-->

## Суть
Компактный preflight для `task-intake`: читает папку задачи, git refs, identity gate (`task-identity.py`) и свежесть артефактов, печатает один маленький JSON. Не пишет файлы проекта. Агент использует `next_action` чтобы решить какой intake шаг запустить (`fetch` → `diff` → `doc` → `verify`), вместо нескольких отдельных shell-вызовов. Также предоставляет режим проверки одного пути записи (`--path`) для определения edit_route (прямая правка vs JSONdoc apply).

## Когда запускать
В начале работы с задачей для получения полной картины. Вызывается из `intake_orchestrator.py` (импорт `build_state`) и можно вызвать вручную для диагностики. Если не запустить — агент не знает какие артефакты есть, свежи ли они, и какие ветки задачи существуют.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--path` | | string | нет | | Проверить один планируемый путь записи (edit_route) |
| `--root` | | string | нет | `.` | Корень проекта |
| `--task` | | string | нет* | | Номер задачи (только цифры). Обязателен если нет `--path` |

*Один из `--path` или `--task` обязателен.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: JSON на stdout | Разобрать `state` / `path_route` |
| 1 | (не используется) | — |
| 2 | Ошибка: task не цифры, root не найден, path outside root | Исправить вызов |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/task.md`, `task.json`, `doc.md`, `diff.md`, `diff.files.md`, `plan.md` — наличие и mtime
- Git refs: `git for-each-ref refs/heads refs/remotes` — локальные и remote ветки
- `task-identity.py` — identity gate (если есть task.md)
- `.doc/architecture/*.md` — generated markers для edit_route
- `.doc/tasks/{N}/reports/change-report/report.html` — наличие HTML отчёта
- `.doc/tasks/{N}/dialogs/index.json` — наличие dialogs index

**Пишет:** только JSON на stdout. Файлы не создаёт.

## Режимы работы

### 1. `--task` (основной) — полный state задачи
Выходной JSON:
```json
{
  "status": "ok",
  "task": "2538",
  "files": {"task.md": true, "task.json": false, "doc.md": false, "diff.md": false, "diff.files.md": false, "plan.md": false},
  "legacy": ["1234"],
  "identity": {"status": "ok|mismatch|incomplete|error|unavailable", "exit": 0, "checks": [], "warnings": []},
  "branches": {
    "exact": ["bugfixes/#2538"],
    "legacy_exact": ["bugfixes/#1234"],
    "variants": ["bugfixes/#2538_for5606"]
  },
  "freshness": {"diff_vs_task": "missing|stale|fresh", "doc_vs_diff": "missing|stale|fresh"},
  "artifacts": {"report_html": false, "dialogs_index": false},
  "generated_views": {
    "architecture_md": {"generated": 15, "total": 20},
    "task_doc_md": {"generated": 5},
    "edit_route": "jsondoc_apply|mixed_check_path|direct"
  },
  "next_action": "fetch|diff|doc|verify"
}
```

#### Логика `next_action`
1. Нет `task.md` или `task.json` → `"fetch"`
2. Нет `diff.md` ИЛИ `diff_vs_task == "stale"` → `"diff"`
3. Нет `doc.md` ИЛИ `doc_vs_diff == "stale"` → `"doc"`
4. Иначе → `"verify"`

#### `edit_route` значения
- `"jsondoc_apply"` — все architecture/*.md сгенерированы (маркер в первых 200 байтах)
- `"mixed_check_path"` — часть сгенерирована, часть нет
- `"direct"` — ничего не сгенерировано, править напрямую

### 2. `--path` — проверка пути записи
Аргументы: `--path <relative_path> --root <root> --task <task>`
Выходной JSON:
```json
{
  "path": ".doc/architecture/items.md",
  "exists": true,
  "generated": true,
  "edit_route": "jsondoc_apply",
  "status": "ok"
}
```
Если путь сгенерирован (маркер `generated from architecture:` или `generated from task:`) → `edit_route: "jsondoc_apply"`.
Если `.doc/architecture/*.md` не generated → `edit_route: "direct_after_check"`.
Иначе → `edit_route: "direct"`.

## Побочные эффекты
Нет (read-only). Только `git for-each-ref` и чтение файлов.

## Окружение и зависимости
- Python 3.8+
- `task-identity.py` (`.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py`) — опционально
- Git в PATH
- Стандартная библиотека: `argparse`, `json`, `re`, `subprocess`, `pathlib`, `sys`

## Примеры
```bash
# Полный state задачи 2538
python .agents/skills/task-router/children/task-intake/scripts/intake_state.py --root . --task 2538

# Проверить путь записи
python .../intake_state.py --root . --task 2538 --path .doc/architecture/items.md

# Только task (без path) — ошибка если task не задан
python .../intake_state.py --root . --path .doc/tasks/2538/doc.md
```

## Ограничения
- Не проверяет семантическую корректность содержимого файлов — только наличие/мtime/маркеры
- `freshness` сравнивает только mtime (не содержимое) — может дать false stale при touch
- `generated_views` проверяет только первые 200 байт на маркер
- `identity` gate опционален — если `task-identity.py` нет, статус `unavailable`
- Не делает сетевых запросов (только локальный git)

## Связи
- Вызывается: `intake_orchestrator.py` (импорт `build_state`), вручную для диагностики
- Зависит от: `task-identity.py`, git refs, структуры `.doc/tasks/{N}/`
- Результат потребляет: `intake_orchestrator.py` (`next_action`), агент (ручной preflight)
- Связанные: `intake_orchestrator.py`, `doc_sections.py`, `intake_analysis.py`, `task-identity.py`

## История изменений
- 2026-11-09: добавлены состояния неполной проверки и подробности identity gate.
- 2026-11-07: полная документация заполнена агентом на основе кода
