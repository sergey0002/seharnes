# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, get-indexing-batch]
-->

## Суть
Выдаёт батч неиндексированных файлов из `file-registry.tsv` для обработки агентом (документированием в архитектуре). Сортирует по директориям, чтобы файлы одного модуля попадали в один батч. Автоматически исключает явный шум (plugins/, *.min.js, *.bundle.js, vendor/, node_modules/) и приоритизирует файлы из `hot-files.txt` (топ-50 активных за 90 дней по git). Сохраняет список батча в `.doc/architecture/_map/current-batch.txt`.

## Когда запускать
- При пакетной индексации проекта (project-doc indexing): агент вызывает в цикле, получает батч, документирует файлы, запускает снова.
- Командой «продолжи индексацию» / «continue indexing».
- Для мониторинга прогресса: `-Status`.
- Для фокуса на типе файлов: `-Kind php` (или js, vue, css, tpl, sql, config).
- Для параллельных агентов: `-Skip N` чтобы пропустить первые N файлов.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Count |  | int | нет | 10 | Количество файлов в батче |
| -Skip |  | int | нет | 0 | Пропустить первые N файлов (параллельные агенты) |
| -Kind |  | string | нет | '' | Фильтр по типу: php, js, vue, css, tpl, sql, config |
| -Status |  | switch | нет |  | Показать только статистику, не выдавать батч |
| -NoHotPriority |  | switch | нет |  | Отключить приоритезацию по hot-files.txt |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех, батч выдан или статус показан | Продолжить работу |
| 1 | Реестр пуст или не найден | Запустить map-project.ps1 сначала |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/_map/file-registry.tsv` — реестр покрытия
- `.doc/architecture/_map/hot-files.txt` — топ активных файлов (git log 90 дней)

**Пишет:**
- `.doc/architecture/_map/current-batch.txt` — список путей текущего батча (по одному на строку)

## Побочные эффекты
- Создаёт/перезаписывает `current-batch.txt`.
- Авто-фильтр шума выводит предупреждение о исключённых файлах (но не меняет реестр — используйте `mark-noise.ps1` для постоянного исключения).

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-RegistryFilePath`, `Get-ProjectFiles`, `Normalize-RelativePath`, `Write-Utf8File`, `Test-GitAvailable`.
- `git` — для генерации `hot-files.txt` (если нет, приоритет отключается).

## Примеры
```powershell
# Статус прогресса
powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status

# Базовый батч (10 файлов)
powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 10

# Только PHP файлы, батч 30
powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 30 -Kind php

# Пропустить 10 для второго агента
powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 10 -Skip 10

# Без hot-приоритета
powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -NoHotPriority
```

Вывод батча:
```
  === Очередь индексации (10 из 1247 ожидающих) ===
  Покрытие: 34.8% (1247/3580)
  
  - lib/Objects/Order/OrderService.php [php] (lib/Objects/Order) 🔥
  - lib/Objects/Order/OrderController.php [php] (lib/Objects/Order) 🔥
  - lib/Objects/Payment/PaymentService.php [php] (lib/Objects/Payment) 🔥
  ...
  
  Список сохранен в .doc\architecture\_map\current-batch.txt
```

## Ограничения
- Работает только со статусом `not_indexed` (исключает `indexed`, `noise`, `deleted`, `manual`).
- Авто-фильтр шума не меняет реестр — файлы просто пропускаются в батче.
- `hot-files.txt` создаётся `map-project.ps1`; если нет — приоритет не работает.
- Сортировка: hot-rank → директория (модуль вместе).

## Связи
- Вызывается: агент при индексации (project-doc indexing), вручную
- Зависит от: `map-project.ps1` (реестр + hot-files), `generate-file-registry.ps1`
- Результат используется: агент документирует файлы из батча, `mark-noise.ps1` для постоянного исключения шума

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)