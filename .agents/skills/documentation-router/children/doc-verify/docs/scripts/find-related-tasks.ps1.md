# Скрипт: `.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, find-related-tasks]
-->

## Суть
Ищет задачи `.doc/tasks/{N}/`, связанные с архитектурным документом. Используется на шаге V6 скила `doc-verify` для нахождения задач, которые нужно отразить в разделе «Связанные задачи» архитектурного документа. Скрипт учитывает прямые ссылки на документ в задаче, пересечение путей кода (backtick-ссылки в `doc.md`/`diff.files.md` с путями в архитектуре), упоминания имени файла и уже проставленные связи в самом архитектурном документе. Поддерживает быстрый путь через JSONdoc (`jsondoc.py related`) и fallback через файловый индекс `tasks/_map/file-to-tasks.tsv`.

## Когда запускать
Вызывается агентом на шаге V6 сверки документации (doc-verify) после чтения architecture-документа и перед записью раздела «Связанные задачи». Также можно запустить вручную для аудита связей doc ↔ task. Если не запустить — в архитектуре не будет обратных ссылок на задачи, нарушается требование doc-verify V6.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Doc |  | string | да |  | Имя документа: `orders.md` или путь `.doc/architecture/orders.md` |
| -Limit |  | int | нет | 8 | Сколько задач вывести (по score) |
| -Json |  | switch | нет |  | Вывести JSON вместо текста (для программного потребления) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех, задачи найдены или их нет | Продолжить работу |
| 1 | Документ не найден в `.doc/architecture/` | Прервать, проверить имя документа |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/{name}.md` или `.doc/architecture/{name}.json` — архитектурный документ
- `.doc/architecture/_map/doc-index.tsv` — индекс документов (для JSONdoc)
- `.doc/tasks/{N}/task.md`, `doc.md`, `plan.md`, `diff.files.md` — файлы задач
- `.doc/tasks/_map/file-to-tasks.tsv` — индекс файл → задачи (ускоряет поиск)

**Пишет:**
- Ничего (только вывод в stdout). JSON-режим выдаёт структуру для программного разбора.

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Требует `python3` и `jsondoc.py` для быстрого пути (опционально).
- Использует `_lib.ps1` из `project-doc/scripts/` для утилит `Get-DocCodeRefs`, `Normalize-RelativePath`, `Read-TextFile`, `Write-Utf8File`.
- `git` — опционально, для проверки `already-in-arch`.

## Примеры
```powershell
# Базовый запуск для документа orders.md
powershell .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc orders.md

# Увеличенный лимит, JSON-вывод
powershell .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc payments.md -Limit 12 -Json
```

Пример текстового вывода:
```
  Связанные задачи для orders (top 8 / candidates 23) [JSONdoc]:
  
  #1612  score=90  [doc.md,in-arch]  link→architecture/orders.md; code-overlap x3
         .doc/tasks/1612/task.md | doc.md
  #2548  score=40  [doc.md]  index-file→task (lib/Objects/Order/OrderService.php)
         .doc/tasks/2548/task.md | doc.md

  В doc-verify V6: ## Связанные задачи (score≥20) + П-N при баге; см. .doc/tasks/index.md
```

## Ограничения
- Не ищет связи через кодовую базу напрямую (только через backtick-пути в документах).
- JSONdoc-путь работает только если есть `.doc/architecture/{name}.json` и валидный `jsondoc.py`.
- Файловый индекс `tasks/_map/file-to-tasks.tsv` должен быть актуален (пересобирается `build-tasks-index.ps1 -AlsoTsv`).
- Score — эвристика, не гарантирует полноту; может пропустить задачи с косвенными связями.

## Связи
- Вызывается: `doc-verify` (шаг V6), агент вручную
- Зависит от: `build-tasks-index.ps1` (TSV-индекс), `jsondoc.py` (опционально)
- Результат используется: в разделе «Связанные задачи» architecture-документа, в `mark-verify-done.ps1`

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)