# Скрипт: `.agents/skills/task-router/children/task-intake/scripts/intake_analysis.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/architecture/_map/file-registry.tsv]
tags: [harness, script, task-intake, intake-analysis, diff-scaffold]
-->

## Суть
Строит детерминированный скелетон (scaffold) для этапа анализа дифа задачи (`intake_analysis`). Парсит `diff.md`, `diff.files.md`, `task.md`, извлекает коммиты, список файлов, статистику строк, связывает файлы с реестром архитектуры (`.doc/architecture/_map/file-registry.tsv`), помечает исторические/удалённые файлы, флаги подозрительных коммитов (legacy tracker URL, чужой номер задачи, дата-выброс). Не пишет findings/decisions/requirements — оставляет пустые массивы для заполнения агентом, и выдаёт чек-лист обязательных действий. Результат — JSON scaffold для ручного или автоматического заполнения.

## Когда запускать
В начале `task-intake` после экспорта `task.md` и diff артефактов. Вызывается из `intake_orchestrator.py` (неявно через state) или вручную агентом для получения структуры перед анализом. Если не запустить — агент должен вручную парсить diff и проверять файлы.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--root` | | string | нет | `.` | Корень проекта |
| `--task` | | string | **да** | | Номер задачи (только цифры) |
| `--output` | | string | нет | `.doc/tasks/{N}/_jsondoc/work/intake-analysis.scaffold.json` | Куда записать scaffold |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: scaffold записан, summary на stdout | Разобрать `path`, `commits`, `files`, `suspicions` |
| 1 | (не используется) | — |
| 2 | Ошибка: task не цифры, root не найден, diff.files.md отсутствует | Исправить вызов |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/diff.files.md` — список файлов (All files, By commit)
- `.doc/tasks/{N}/diff.md` — полный diff (коммиты в "## Commits (index)", line stats)
- `.doc/tasks/{N}/task.md` — заголовок задачи (Created, Bitbucket, issue URL)
- `.doc/architecture/_map/file-registry.tsv` — реестр файлов (kind, domain, doc_refs, status)

**Пишет:**
- `--output` файл (или дефолтный) — scaffold JSON
- Stdout: summary JSON с `status: "ok"`, `task`, `path`, `commits`, `files`, `suspicions`, `historical`

## Структура scaffold (выходной JSON)
```json
{
  "status": "ok",
  "task": "2538",
  "task_created": "2026-11-01",
  "legacy": ["1234"],
  "commits": [
    {"sha": "abc123", "date": "...", "author": "...", "subject": "...", "flags": ["legacy_tracker_url"]}
  ],
  "files": [
    {
      "path": "lib/Objects/Item/ItemController.php",
      "state": "current|historical",
      "kind": "php",
      "domain": "items",
      "doc_refs": ["architecture/items.md#section"],
      "lines": {"added": 12, "removed": 3},
      "diff_range": {"start": 45, "end": 78},
      "commits": ["abc123"],
      "flags": ["not_in_file_registry"]
    }
  ],
  "suspicions": [
    {"type": "foreign_task_number", "scope": "commit", "ref": "abc123", "reason": "foreign_task_number: Fix for #9999"},
    {"type": "historical", "scope": "file", "ref": "old/path.php", "reason": "historical: old/path.php"}
  ],
  "findings": [],
  "decisions": [],
  "requirements": [],
  "checklist": [
    "Заполнить findings: symptom, cause, resolution только по коду и дифу.",
    "Заполнить decisions: context, choice, alternatives.",
    "Заполнить requirements: text, state и source_ids.",
    "Проверить каждый suspicion и либо объяснить связь, либо исключить.",
    "Не включать historical файлы в current scope без причины."
  ]
}
```

### Флаги коммитов
| Флаг | Условие |
|---|---|
| `legacy_tracker_url` | В subject есть `/issues/NNN` |
| `foreign_task_number` | В subject есть `#NNN` не текущей задачи и не из legacy |
| `date_outlier` | Дата коммита отличается от Created задачи > 730 дней |

### Флаги файлов
| Флаг | Условие |
|---|---|
| `historical` | Файл не существует в рабочем дереве |
| `not_in_file_registry` | Нет в `file-registry.tsv` |
| `deleted_in_file_registry` | В реестре status=deleted |

## Побочные эффекты
- Создаёт/перезаписывает scaffold файл
- Не меняет исходные артефакты задачи

## Окружение и зависимости
- Python 3.8+
- Стандартная библиотека: `argparse`, `json`, `re`, `datetime`, `pathlib`, `subprocess` (нет)
- Нет внешних зависимостей

## Примеры
```bash
# Базовый вызов (запишет в дефолтный путь)
python .agents/skills/task-router/children/task-intake/scripts/intake_analysis.py --root . --task 2538

# С указанием output
python .../intake_analysis.py --root . --task 2538 --output /tmp/scaffold.json
```

## Ограничения
- Не делает семантический анализ — только механическую структуру
- Не пишет `findings`/`decisions`/`requirements` — это работа агента
- `file-registry.tsv` должен быть актуален (пересобирается `map-project.ps1`)
- Парсинг `diff.files.md` зависит от формата `task-diff.ps1` (## All files, ## By commit)
- Парсинг коммитов из `diff.md` ищет секцию "## Commits (index)" с форматом `- sha | date | author | subject`

## Связи
- Вызывается: вручную агентом, `intake_orchestrator.py` (через state next_action)
- Зависит от: `diff.md`, `diff.files.md`, `task.md`, `file-registry.tsv`
- Результат потребляет: агент (заполняет findings/decisions), `doc_sections.py` (source_ids)
- Связанные: `intake_orchestrator.py`, `intake_state.py`, `task-diff.ps1`

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода