# Скрипт: `.agents/skills/task-router/children/task-intake/scripts/doc_sections.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md, ../../../documentation-router/children/task-doc/scripts/jsondoc.py]
tags: [harness, script, task-intake, doc-sections, jsondoc]
-->

## Суть
Применяет разделы документации задачи (написанные агентом в одном JSON или Markdown с `##` заголовками) к `task.json` через JSONdoc envelope. Парсит входной файл, строит операции `upsert` для секций (сохраняя существующие `id`, `anchor`, порядок), дописывает `source_ids` (якоря на исходники), и опционально применяет (`--apply`), рендерит (`--apply` включает render), и финализирует (`--finalize`: пересобирает индекс задач, запускает `check-doc-text.py`, `validate-docs.ps1`, `task-identity.py`). Не пишет текст секций — только оборачивает в JSONdoc операции.

## Когда запускать
После того как агент подготовил JSON/Markdown с разделами для `doc.md` задачи. Вызывается из `task-intake` SKILL.md (шаг документации) или вручную. Если не запустить — разделы не попадут в `task.json` и не срендерятся в `doc.md`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--root` | | string | нет | `.` | Корень проекта |
| `--task` | | string | **да** | | Номер задачи (только цифры) |
| `--input` | | string | **да** | | Путь к файлу с разделами (JSON с ключом `sections` или Markdown с `##`) |
| `--apply` | | flag | нет | | Применить операции через `jsondoc.py apply` + `render` |
| `--finalize` | | flag | нет | | `--apply` + пересборка индекса задач + проверки документации |
| `--no-network` | | flag | нет | | Заглушка для симметрии с orchestrator |

## Входной формат (JSON)
```json
{
  "sections": {
    "Название секции": "Markdown тело",
    "Другая секция": {"body_markdown": "Markdown тело", "source_ids": ["task.md#anchor", "diff.md#L10-L20"]}
  }
}
```
или список:
```json
{
  "sections": [
    {"title": "Название", "body_markdown": "...", "source_ids": ["..."]},
    ...
  ]
}
```

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: `status: "planned"` (без apply) / `"applied"` / `"done"` (с finalize) | Разобрать JSON stdout: `sections`, `order`, `envelope`, `steps` |
| 1 | Ошибка применения/рендера/проверок (`status: "error"`) | Прочитать `errors` в `steps`, исправить |
| 2 | Ошибка аргументов: task не цифры, input не найден, task.json нет, дубликаты заголовков | Исправить вызов |

## Что читает и что пишет
**Читает:**
- `--input` файл (JSON или Markdown)
- `.doc/tasks/{N}/task.json` — текущий документ JSONdoc

**Пишет (при `--apply`/`--finalize`):**
- `.doc/tasks/{N}/_jsondoc/work/doc-sections-envelope.json` — envelope для jsondoc
- Через `jsondoc.py`: обновляет `task.json` (sections, section_order), рендерит `doc.md`
- При `--finalize`: запускает `build-tasks-index.ps1`, `check-doc-text.py`, `validate-docs.ps1`, `task-identity.py`
- При `--finalize` identity gate выполняется до изменения модели и рендера. Конфликт или неполные данные останавливают запись.

**Stdout (всегда):** JSON с полями:
```json
{
  "status": "planned|applied|done|error",
  "task": "2538",
  "sections": ["Секция 1", "Секция 2"],
  "order": ["s1", "s2", "s3"],
  "envelope": ".doc/tasks/2538/_jsondoc/work/doc-sections-envelope.json",
  "steps": [{"name": "apply", "status": "ok", "exit": 0, "tail": ""}, ...]
}
```

## Побочные эффекты
- При `--apply`/`--finalize`: меняет `task.json` и `doc.md` через JSONdoc
- При `--finalize`: пересобирает `.doc/tasks/index.md` и `_map/file-to-tasks.tsv`
- Сетевых запросов нет

## Окружение и зависимости
- Python 3.8+
- `jsondoc.py` (`.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py`)
- PowerShell (`pwsh`/`powershell`) для `build-tasks-index.ps1`, `validate-docs.ps1` (при `--finalize`)
- Стандартная библиотека: `argparse`, `json`, `re`, `hashlib`, `subprocess`, `pathlib`, `shutil`

## Примеры
```bash
# Только планирование (dry-run)
python .agents/skills/task-router/children/task-intake/scripts/doc_sections.py --root . --task 2538 --input sections.json

# Применить и срендерить
python .../doc_sections.py --root . --task 2538 --input sections.json --apply

# Полный цикл с финализацией
python .../doc_sections.py --root . --task 2538 --input sections.json --finalize
```

## Ограничения
- Не пишет текст секций — агент должен подготовить полный Markdown
- Не проверяет семантическую корректность содержания — только структуру JSONdoc
- Требует существующий `task.json` (создаётся `ingest-tracker` или вручную)
- Markdown парсинг — legacy fallback (только `##` заголовки, без вложенности)
- `--finalize` пропускает недоступные скрипты проверки (не фейлит, ставит `skipped`)

## Связи
- Вызывается: `task-intake` SKILL.md, вручную
- Зависит от: `jsondoc.py`, `task.json`, PowerShell скриптов проверки
- Результат потребляет: `task-doc` (рендер doc.md), `project-doc` (индекс задач)
- Связанные: `intake_orchestrator.py` (вызывает как шаг), `intake_state.py` (проверяет freshness)

## История изменений
- 2026-11-09: проверка идентичности перед записью при финализации.
- 2026-11-07: полная документация заполнена агентом на основе кода
