# Скрипт: `.agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, get-verify-batch]
-->

## Суть
Управляет очередью сверки архитектурных документов с кодом (doc-verify). Реестр хранится в `.doc/architecture/_map/verify-registry.tsv` с полями: путь, статус (pending/verified/skipped), дата сверки, число issues, число code-refs, заметки. По умолчанию выдаёт батч из 1 документа для полной сверки. Поддерживает инициализацию очереди, сброс, отметку stale-документов (код изменился после updated), выбор конкретного раздела для пересверки.

## Когда запускать
- На старте doc-verify: `-Init` для инициализации/синхронизации очереди.
- Перед каждым шагом сверки: без аргументов (или `-Count 1`) для получения следующего документа.
- Для мониторинга прогресса: `-Status`.
- Для ручной пересверки конкретного документа: `-Section payments.md`.
- После крупных правок кода: `-ResetStale` чтобы вернуть в pending документы, чьи code-refs изменились.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Count |  | int | нет | 1 | Сколько документов выдать в батче |
| -Skip |  | int | нет | 0 | Пропустить первые N pending (для параллельных агентов) |
| -Status |  | switch | нет |  | Только показать прогресс-бар, не выдавать батч |
| -Init |  | switch | нет |  | Пересобрать очередь по текущим architecture/*.md; новые = pending, сохраняет verified/skipped |
| -Reset |  | switch | нет |  | Все документы снова pending (полная повторная сверка) |
| -ResetStale |  | switch | нет |  | Пометить pending те docs, у которых код из backtick-ссылок менялся после meta.updated |
| -Section |  | string | нет | '' | Выдать конкретный файл (имя или путь architecture/foo.md), даже если уже verified |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех, батч выдан или статус показан | Продолжить работу |
| 1 | Документ не найден в очереди (при -Section) | Запустить -Init сначала |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/*.md` — все архитектурные документы (кроме `_map/`, `_*`, `index.md`, `_priority.md`)
- `.doc/architecture/_map/verify-registry.tsv` — реестр сверки
- `.doc/architecture/_map/doc-index.tsv` — для получения бизнес-ключей

**Пишет:**
- `.doc/architecture/_map/verify-registry.tsv` — обновлённый реестр (при -Init, -Reset, -ResetStale)
- `.doc/architecture/_map/current-verify-batch.txt` — список путей текущего батча (для передачи агенту)

## Побочные эффекты
- Обновляет `verify-registry.tsv` при `-Init`, `-Reset`, `-ResetStale`.
- Создаёт `current-verify-batch.txt` с путями батча.

## Окружение и зависимости
- Использует `_lib.ps1` из `project-doc/scripts/`: `Get-ArchitectureDocs`, `Get-DocCodeRefs`, `Get-DocMeta`, `Get-DocFirstHeading`, `Normalize-RelativePath`, `Read-TextFile`, `Write-Utf8File`, `Test-GitAvailable`.
- `git` — для `-ResetStale` (проверка изменений кода после даты updated).

## Примеры
```powershell
# Инициализация очереди (первый запуск или после добавления новых docs)
powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Init

# Только прогресс
powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Status

# Получить 1 документ для сверки
powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Count 1

# Пересверить конкретный документ
powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Section payments.md

# Вернуть в pending stale-документы
powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -ResetStale
```

Пример вывода `-Status`:
```
  Прогресс сверки docs <-> код:
  ████████████░░░░░░░░░░░░░░░░ 42.5% (17/40)
  verified: 17 | pending: 23 | skipped: 0 | total: 40
```

Пример вывода батча:
```
  === Очередь сверки (1 док.) ===
  Прогресс: 42.5% (17/40), pending: 23
  
  - orders.md  [pending]  refs=12  updated=2026-10-15
    H1: Заказы: бизнес-логика и API
    code: lib/Objects/Order/OrderService.php, lib/Objects/Order/OrderController.php, ...
  
  Список: .doc/architecture/_map/current-verify-batch.txt
  После сверки: mark-verify-done.ps1 -Path "orders.md" -Issues N
```

## Ограничения
- `index.md` и `_priority.md` исключены из сверки (навигация/приоритеты, не бизнес-доки).
- При `-Init`/`-Reset`/`-ResetStale` без `-Count`/`-Section` выводит только статус и выходит (код 0).
- Сортировка pending: сначала документы с меньшим числом code-refs (быстрее обработать).
- `-ResetStale` требует git и корректное поле `updated:` в meta документе.

## Связи
- Вызывается: `doc-verify` (шаги 1, 5), агент вручную
- Зависит от: `map-project.ps1` (создаёт `_map/`), `generate-doc-index.ps1`
- Результат используется: `mark-verify-done.ps1`, агент сверяет документ из батча

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)