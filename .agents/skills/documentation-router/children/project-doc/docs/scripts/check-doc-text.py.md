# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-doc-text]
-->

## Суть
Валидатор текста `doc.md` задачи по правилам `task-doc` (стиль, структура, запрещённые символы). Проверяет: запрещённые символы (—, –, «, »), утечки `Array`, HTML-комментарии, размытые слова («как правило», «обычно» и т.д.), минимальную длину «Краткого описания», отсутствие кода в саммари, структуру «Подводных камней» и «Истории решений» (обязательны «Симптом» и «Решение»), ссылки на задачи в «Связанных задачах» (должны быть кликабельными), условия в «Покрытии условий» (не должны содержать код), формат записей в «Истории изменений» (дата в начале). Поддерживает baseline: проверяет только изменившиеся секции (по SHA256), позволяет зафиксировать актуальное состояние после ревью.

## Когда запускать
- При документировании задачи (task-doc режим B) — после записи `doc.md`.
- В CI/пре-коммите для задач с `doc.md`.
- При команде «проверь doc.md задачи N».
- Агент может запустить с `--write-baseline` после ручного ревью, чтобы зафиксировать текущее состояние как допустимое.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --task |  | string | нет |  | Номер задачи (читает `.doc/tasks/{N}/doc.md`) |
| --file |  | string | нет |  | Явный путь к doc.md (альтернатива --task) |
| --baseline |  | string | нет |  | Путь к baseline JSON (проверять только изменившиеся секции) |
| --write-baseline |  | string | нет |  | Путь для записи baseline после ревью (помечает все секции как актуальные) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Нет ошибок (warnings допускаются) | Успех |
| 1 | Найдены ошибки (forbidden chars, array leak, html comments, code в conditions) | Исправить doc.md |
| 2 | Файл не найден или невалидные аргументы | Проверить --task/--file |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/doc.md` — документ задачи
- Baseline JSON (при `--baseline`) — сохранённые хеши секций

**Пишет:**
- Baseline JSON (при `--write-baseline`) — структура: `{schema_version, task, sections: {section_title: sha256}}`
- JSON-отчёт в stdout: `{task, file, status, errors[], warnings[], baseline, checked_sections, skipped_sections}`

## Побочные эффекты
- Записывает baseline файл при `--write-baseline`.

## Окружение и зависимости
- Python 3.7+ (стандартная библиотека: argparse, hashlib, json, re, pathlib).
- Нет внешних зависимостей.

## Примеры
```bash
# Проверка doc.md задачи 2548
python3 .agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py --task 2548

# Проверка только изменившихся секций (baseline от предыдущего ревью)
python3 .agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py --task 2548 --baseline .doc/tasks/2548/_jsondoc/doc-text-baseline.json

# После ручного ревью: зафиксировать текущее состояние как baseline
python3 .agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py --task 2548 --write-baseline .doc/tasks/2548/_jsondoc/doc-text-baseline.json

# Явный файл
python3 .agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py --file .doc/tasks/2548/doc.md
```

Пример JSON-вывода при ошибках:
```json
{
  "task": "2548",
  "file": ".doc/tasks/2548/doc.md",
  "status": "failed",
  "errors": [
    {"code": "forbidden_char", "line": 45, "section": "Краткое описание", "snippet": "— это тире", "char": "—"},
    {"code": "condition_has_code", "line": 120, "section": "Покрытие условий", "snippet": "`OrderService::process()`", "condition": "`OrderService::process()`"}
  ],
  "warnings": [
    {"code": "vague_word", "value": "обычно", "line": 30, "section": "Подводные камни"}
  ],
  "baseline": ".doc/tasks/2548/_jsondoc/doc-text-baseline.json",
  "checked_sections": 8,
  "skipped_sections": 3
}
```

## Ограничения
- Парсит секции по заголовкам `## ` — не работает с нестандартной разметкой.
- Не проверяет семантическое качество текста, только синтаксические правила.
- Baseline работает по SHA256 тела секции — любое изменение (пробел, пунктуация) считается изменением.
- Не валидирует `task.md` или `plan.md` — только `doc.md`.

## Связи
- Вызывается: `task-doc` (режим B, после записи doc.md), агент вручную
- Зависит от: правил `task-doc` (SKILL.md), text-style.mdc
- Результат используется: блокировка завершения документирования при ошибках, baseline для инкрементальных проверок

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)