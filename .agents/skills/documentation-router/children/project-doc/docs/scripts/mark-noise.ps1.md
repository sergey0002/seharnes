# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, mark-noise]
-->

## Суть
Помечает указанные файлы как «шум» (status=noise) в `file-registry.tsv`, чтобы исключить их из очереди индексации (`get-indexing-batch.ps1`). Используется после авто-фильтра шума в `get-indexing-batch.ps1` для постоянного исключения файлов, которые агент считает нерелевантными для документирования (плагины, минифицированные файлы, vendor и т.д.).

## Когда запускать
- После получения батча через `get-indexing-batch.ps1`, если в батче попадаются файлы-шум.
- Агент вызывает автоматически при индексации: «помечай: mark-noise.ps1 -Paths "path1","path2"».
- Вручную для очистки реестра от известных шумовых путей.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Paths |  | string[] | да |  | Массив путей к файлам (относительных от корня проекта) |

## Коды выхода
Скрипт не возвращает явные коды выхода (всегда 0 при успехе).

## Что читает и что пишет
**Читает:**
- `.doc/architecture/_map/file-registry.tsv` — реестр покрытия

**Пишет:**
- `.doc/architecture/_map/file-registry.tsv` — обновлённый реестр (status=noise для указанных путей)

## Побочные эффекты
- Меняет статус файлов в реестре на `noise` (они перестают появляться в батчах).

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-RegistryFilePath`, `Normalize-RelativePath`, `Write-Utf8File`.

## Примеры
```powershell
# Исключить конкретные файлы из очереди навсегда
powershell .agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1 -Paths "lib/Plugins/OldPlugin/Plugin.php","scripts/plugins/legacy.min.js"

# Массив путей
powershell .agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1 -Paths @(
    "admin/scripts/plugins/SomePlugin/Plugin.php",
    "vendor/legacy/LegacyClass.php"
)
```

Вывод:
```
✅ Исключен из очереди: lib/Plugins/OldPlugin/Plugin.php
✅ Исключен из очереди: scripts/plugins/legacy.min.js
```

## Ограничения
- Работает только с точными путями из реестра (нормализует через `Normalize-RelativePath`).
- Не проверяет, существует ли файл физически — меняет статус в реестре по совпадению пути.
- Не отменяет noise-статус — для возврата нужно вручную редактировать TSV или перезапустить `generate-file-registry.ps1`.

## Связи
- Вызывается: агент при индексации (после `get-indexing-batch.ps1`), вручную
- Зависит от: `file-registry.tsv` (от `generate-file-registry.ps1` / `map-project.ps1`)
- Результат влияет: `get-indexing-batch.ps1` (noise файлы исключаются из pending)

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)