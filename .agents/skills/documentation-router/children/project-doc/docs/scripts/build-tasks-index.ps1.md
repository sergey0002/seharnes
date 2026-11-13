# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, build-tasks-index]
-->

## Суть
Собирает `.doc/tasks/index.md` — единый индекс задач с двусторонними связями: «Задачи → файлы» и «Файлы → задачи». Источники на задачу: `task.md` (заголовок # Issue #N: ...), `diff.files.md` (блок ## All files), `doc.md` (backtick-пути к коду), наличие `doc.md` / `plan.md`. Если `task.md` нет, номер задачи в таблицах остается текстом, а ссылка ведет на `doc.md`, если он есть. Опционально генерирует TSV-индекс `.doc/tasks/_map/file-to-tasks.tsv` для быстрого поиска задач по файлу (используется `find-related-tasks.ps1`).

## Когда запускать
- После добавления/обновления задач в `.doc/tasks/`.
- После команды «задокументируй задачу» (task-doc режим B) — скрипт вызывается автоматически в шаге B4.5.
- При ручной правке `task.md`/`doc.md`/`diff.files.md` задач.
- При изменении структуры задач (новая задача, удалена задача).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -OutPath |  | string | нет | `.doc/tasks/index.md` | Куда писать индекс |
| -AlsoTsv |  | switch | нет |  | Дополнительно писать `.doc/tasks/_map/file-to-tasks.tsv` |

## Коды выхода
Скрипт не возвращает явные коды выхода (всегда 0 при успехе, исключение при ошибке IO).

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/task.md` — заголовок задачи
- `.doc/tasks/{N}/diff.files.md` — блок `## All files`
- `.doc/tasks/{N}/doc.md` — backtick-пути к коду (через `Get-DocCodeRefs`)
- `.doc/tasks/{N}/plan.md` — наличие плана

**Пишет:**
- `.doc/tasks/index.md` — Markdown-индекс с таблицами и мета-блоком
- `.doc/tasks/_map/file-to-tasks.tsv` (при `-AlsoTsv`) — TSV: `path<TAB>task_ids<TAB>titles`

## Побочные эффекты
- Перезаписывает `index.md` и `file-to-tasks.tsv` целиком.
- Создаёт директорию `_map` при необходимости.

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-ProjectFiles`, `Get-DocCodeRefs`, `Normalize-RelativePath`, `Read-TextFile`, `Write-Utf8File`.

## Примеры
```powershell
# Базовый запуск
powershell .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1

# С TSV для find-related-tasks
powershell .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv
```

Пример фрагмента `index.md`:
```markdown
# Индекс задач CopyTrust

<!-- meta
type: index
status: actual
updated: 2026-11-07
tags: [tasks, index, files]
-->

---

## Суть
Реестр задач `.doc/tasks/{N}/`: номер, название, наличие `task.md`/`doc.md`,
затронутые файлы кода. Для поиска «какой task трогал этот файл» и
для **doc-verify V6** (`find-related-tasks.ps1`).

> **Сгенерировано:** 2026-11-07 10:30 скриптом `build-tasks-index.ps1`. **Не править руками** — пересобери скриптом.

| Метрика | Значение |
|---|---|
| Задач в `.doc/tasks/` | 184 |
| С `doc.md` | 156 |
| С `diff.files.md` | 142 |
| Уникальных путей кода | 1247 |

## 1. Задачи → файлы

| # | Название | Артефакты | Файлов |
|---|---|---|---|
| [#1612](./1612/task.md) | Ошибка оплаты: неверный UIN | [task](./1612/task.md) · [doc](./1612/doc.md) · [diff.files](./1612/diff.files.md) | 12 |

### Детали по задачам (файлы)

#### #1612 — Ошибка оплаты: неверный UIN
- Документация: [doc.md](./1612/doc.md)
- `lib/Objects/Payment/PaymentService.php`
- `lib/Objects/Payment/PaymentController.php`

## 2. Файлы → задачи

| Файл | Задачи |
|---|---|
| `lib/Objects/Payment/PaymentService.php` | [#1612](./1612/task.md) ([doc](./1612/doc.md)), [#2548](./2548/task.md) |
```

## Ограничения
- Не читает `diff.md` (полный диф) — только `diff.files.md` (список путей).
- Из `doc.md` берёт только backtick-пути, не являющиеся `.md` и не в `.doc/`.
- Дубликаты путей убираются через HashSet.
- Заголовок задачи извлекается из первого `# Issue #N: ...` или первого `# ...` в `task.md`.

## Связи
- Вызывается: `task-doc` (шаг B4.5), агент вручную, `find-related-tasks.ps1` (читает TSV)
- Зависит от: `_lib.ps1`, структура `.doc/tasks/{N}/`
- Результат используется: doc-verify V6, поиск задач по файлу, навигация в панели

## История изменений
- 2026-11-11: при отсутствии `task.md` ссылки ведут на `doc.md` или остаются текстом; путь к `doc_rules.md` исправлен на `../harnes/doc_rules.md`.
- 2026-11-07: полная документация на основе кода (status: actual)