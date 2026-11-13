# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/generate-doc-index.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-doc-index]
-->

## Суть
Генерирует лёгкий TSV-индекс архитектурных документов для агентов: `.doc/architecture/_map/doc-index.tsv`. Для каждого `.md` в `.doc/architecture/` (кроме `_map/`, `_*`) извлекает: относительный путь, H1-заголовок, meta.type, meta.status, meta.tags, meta.related, meta.updated, бизнес-ключ (первый тег или первая часть пути). Используется агентами для быстрой навигации и выбора релевантных документов без чтения полных файлов.

## Когда запускать
- После добавления/удаления/переименования архитектурных документов.
- При запуске `map-project.ps1` (вызывается автоматически в конце).
- Агент может вызвать вручную перед работой с архитектурой для получения списка документов.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Quiet |  | switch | нет |  | Подавить вывод в консоль |

## Коды выхода
Скрипт не возвращает явные коды выхода (всегда 0 при успехе).

## Что читает и что пишет
**Читает:**
- `.doc/architecture/*.md` — все архитектурные документы (через `Get-ArchitectureDocs`)
- Meta-блок каждого документа (`Get-DocMeta`)
- H1 заголовок (`Get-DocFirstHeading`)
- Бизнес-ключ (`Get-DocBusinessKey`)

**Пишет:**
- `.doc/architecture/_map/doc-index.tsv` — TSV с колонками: `doc_path<TAB>h1<TAB>type<TAB>status<TAB>tags<TAB>related<TAB>last_updated<TAB>business_key`

## Побочные эффекты
- Перезаписывает `doc-index.tsv` целиком.

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-ArchitectureDocs`, `Get-DocMeta`, `Get-DocFirstHeading`, `Get-DocBusinessKey`, `Get-RelativePath`, `Write-Utf8File`, `Normalize-RelativePath`.

## Примеры
```powershell
# Базовый запуск
powershell .agents/skills/documentation-router/children/project-doc/scripts/generate-doc-index.ps1

# Тихий режим (для вызова из map-project.ps1)
powershell .agents/skills/documentation-router/children/project-doc/scripts/generate-doc-index.ps1 -Quiet
```

Пример строки TSV:
```
orders.md	Заказы: бизнес-логика и API	architecture	actual	orders;payments	orders.md;payments.md	2026-10-15	orders
```

## Ограничения
- Обрабатывает только `.md` файлы в `.doc/architecture/` (рекурсивно, кроме `_map/`, `_*`).
- Не обновляет `index.md` — только TSV-индекс для машинного потребления.
- Бизнес-ключ — эвристика: первый тег или первая часть пути до `/`.

## Связи
- Вызывается: `map-project.ps1` (автоматически), агент вручную
- Зависит от: `_lib.ps1`, структуры `.doc/architecture/`
- Результат используется: агентами для навигации, `get-verify-batch.ps1` (business_key), `find-related-tasks.ps1` (JSONdoc путь)

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)