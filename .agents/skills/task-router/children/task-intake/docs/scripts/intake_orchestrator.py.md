# Скрипт: `.agents/skills/task-router/children/task-intake/scripts/intake_orchestrator.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md, ../scripts/intake_state.py, ../../gototask/scripts/gototask.ps1, ../../task-diff/scripts/task-diff.ps1]
tags: [harness, script, task-intake, orchestrator, pipeline]
-->

## Суть
Оркестратор детерминированной части `task-intake`: объединяет preflight state (`intake_state.py`), Jira экспорт (`gototask.ps1 export-task`), tracker ingest (`jsondoc.py ingest-tracker`), и diff генерацию (`task-diff.ps1`) в один вызов. Каждый шаг пропускается, если артефакт уже свежий (по mtime). Не пишет документацию, бизнес-правила, отчёты и не переключает ветку. Возвращает один компактный JSON с выполненными шагами, ошибками, предупреждениями, состоянием и `next_action` для решения агента.

## Когда запускать
Первый шаг при работе с новой/устаревшей задачей. Запускает агент вручную или автоматизация. Если не запустить — нужно вызывать export/diff/ingest-tracker по отдельности и следить за свежестью артефактов.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--root` | | string | нет | `.` | Корень проекта |
| `--task` | | string | **да** | | Номер задачи (только цифры) |
| `--force` | | flag | нет | | Запустить export и diff даже если артефакты есть и свежие |
| `--skip-export` | | flag | нет | | Пропустить Jira экспорт |
| `--skip-diff` | | flag | нет | | Пропустить diff генерацию |
| `--no-network` | | flag | нет | | Передать `-SkipFetch` в `task-diff.ps1` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: `status: "ok"`, нет errors | Разобрать `steps`, `state`, `next_action` |
| 1 | Ошибка шага или identity gate (`status: "error"`) | Прочитать `errors` и `state.identity`, устранить причину |
| 2 | Ошибка аргументов: task не цифры, root не найден | Исправить вызов |

## Что читает и что пишет
**Читает (через `intake_state.py`):**
- `.doc/tasks/{N}/task.md`, `task.json`, `doc.md`, `diff.md`, `diff.files.md`, `plan.md`
- Git refs (`git for-each-ref`) для веток задачи
- `task-identity.py` для identity gate

**Пишет (через под-скрипты):**
- `gototask.ps1 export-task` → `.doc/tasks/{N}/task.md` и снимок трекера без переключения ветки
- `jsondoc.py ingest-tracker` → `.doc/tasks/{N}/task.json`
- `task-diff.ps1` → `.doc/tasks/{N}/diff.md`, `diff.files.md`

**Stdout (всегда):** JSON:
```json
{
  "status": "ok|error",
  "task": "2538",
  "steps": [
    {"name": "export", "status": "ok|skipped|failed", "exit": 0, "tail": "..."},
    {"name": "ingest-tracker", "status": "ok|skipped|failed", "exit": 0, "tail": "..."},
    {"name": "diff", "status": "ok|skipped|failed", "exit": 0, "tail": "..."}
  ],
  "errors": ["export failed"],
  "warnings": ["legacy_without_diff", "architecture_md_is_generated"],
  "state": { ... intake_state payload ... },
  "next_action": "fetch|diff|doc|verify"
}
```

### Логика пропуска шагов
- `export` нужен если: `--force` ИЛИ `next_action == "fetch"` ИЛИ нет `task.md`
- `ingest-tracker` после export если: есть `task.md` И нет `task.json` И есть `tracker.json`
- `diff` нужен если: `--force` ИЛИ нет `diff.md` ИЛИ `diff_vs_task == "stale"` ИЛИ `next_action in ("fetch", "diff")`

### Предупреждения (warnings)
| Код | Условие |
|---|---|
| `legacy_without_diff` | есть legacy номера задач, но нет `diff.md` |
| `architecture_md_is_generated` | architecture/*.md сгенерированы (edit_route != "direct") |

## Побочные эффекты
- `export`: сетевой запрос к Jira, без переключения или слияния ветки
- `ingest-tracker`: пишет `task.json`
- `diff`: `git log`/`diff`, пишет `diff.md`, `diff.files.md`
- Сетевые запросы: `git fetch origin` (в gototask и task-diff)

## Окружение и зависимости
- Python 3.8+
- PowerShell (`pwsh`/`powershell`) для `gototask.ps1`, `task-diff.ps1`
- `jsondoc.py` (`.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py`)
- `intake_state.py` (внутренний импорт)
- Git в PATH

## Примеры
```bash
# Полный прогон для задачи 2538
python .agents/skills/task-router/children/task-intake/scripts/intake_orchestrator.py --root . --task 2538

# Принудительно пересобрать export и diff
python .../intake_orchestrator.py --root . --task 2538 --force

# Только diff (export уже есть)
python .../intake_orchestrator.py --root . --task 2538 --skip-export

# Без сети (только локальные refs)
python .../intake_orchestrator.py --root . --task 2538 --no-network
```

## Ограничения
- Не пишет `doc.md`, `plan.md`, бизнес-правила, отчёты — это следующие этапы intake
- Не переключает ветку к задаче
- Требует PowerShell и gototask/task-diff скрипты
- `--no-network` передаётся только в `task-diff`; `gototask export-task` всегда делает `git fetch`
- `ingest-tracker` запускается только если `tracker.json` есть (создаётся gototask при export)

## Связи
- Вызывается: агент вручную, автоматизация intake
- Зависит от: `intake_state.py`, `gototask.ps1`, `task-diff.ps1`, `jsondoc.py`
- Результат потребляет: агент (читает `next_action` для следующего шага)
- Связанные: `intake_state.py`, `doc_sections.py` (следующий шаг после diff), `intake_analysis.py`

## История изменений
- 2026-11-09: ошибки и неполнота identity gate останавливают проход до построения diff.
- 2026-11-07: полная документация заполнена агентом на основе кода
