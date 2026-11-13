# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/generate-file-registry.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-file-registry]
-->

## Суть
Генерирует persistent registry покрытия файлов проекта документацией: `.doc/architecture/_map/file-registry.tsv`. Сканирует отслеживаемые файлы проекта (PHP, Vue, JS/TS, TPL, CSS, SQL, конфиги), сопоставляет их с backtick-ссылками в архитектурных документах, и для каждого файла записывает: путь, тип (kind), статус покрытия (indexed/not_indexed/manual/noise/deleted), домен (business_key первого документа), список ссылающихся документов, дату первого индексирования, дату последней проверки, источник статуса. Включает Safety Gate: не разрушает реестр, если найдено подозрительно мало файлов (<50% от существующего реестра) — защищает от запуска вне корня проекта.

## Когда запускать
- После `map-project.ps1` (вызывается автоматически в конце).
- После добавления/удаления архитектурных документов или изменении их backtick-ссылок.
- При команде «обнови реестр покрытия».
- Агент может вызвать для получения метрик покрытия.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Quiet |  | switch | нет |  | Подавить вывод в консоль |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (включая Safety Gate early exit) | Продолжить работу |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/*.md` — архитектурные документы (через `Get-ArchitectureDocs`, `Get-DocCodeRefs`, `Get-DocBusinessKey`)
- Файлы проекта: `Get-ProjectFiles` с расширениями php/phtml/tpl/vue/js/ts/css/scss/sass/less/sql + конфиги (composer.json, package.json, phpunit.xml, webpack.config.js/ts, .env.example)
- Существующий реестр `.doc/architecture/_map/file-registry.tsv` (для сохранения first_indexed, manual/noise статусов)

**Пишет:**
- `.doc/architecture/_map/file-registry.tsv` — TSV с колонками: `path<TAB>kind<TAB>status<TAB>domain<TAB>doc_refs<TAB>first_indexed<TAB>last_checked<TAB>source`

## Побочные эффекты
- Перезаписывает `file-registry.tsv` целиком.
- Добавляет записи для удалённых файлов со статусом `deleted` (история сохраняется).
- Safety Gate может прервать выполнение без записи (exit 0).

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-ProjectFiles`, `Get-ArchitectureDocs`, `Get-DocCodeRefs`, `Get-DocBusinessKey`, `Get-FileKind`, `Normalize-RelativePath`, `Read-TsvRows`, `Write-Utf8File`, `Get-RegistryFilePath`.
- `git` — для Safety Gate (опционально, проверка доступности).

## Примеры
```powershell
# Базовый запуск
powershell .agents/skills/documentation-router/children/project-doc/scripts/generate-file-registry.ps1

# Тихий режим
powershell .agents/skills/documentation-router/children/project-doc/scripts/generate-file-registry.ps1 -Quiet
```

Вывод:
```
✅ file-registry: .doc\architecture\_map\file-registry.tsv
   Покрытие: 1247/3580 (34.8%)
   Удаленных файлов (в истории): 23
```

Пример строки TSV:
```
lib/Objects/Order/OrderService.php	php	indexed	orders	orders.md;payments.md	2026-09-15	2026-11-07	merged
lib/Objects/Payment/Gateway.php	php	not_indexed			2026-11-07	map
```

## Ограничения
- Safety Gate: если в реестре уже >100 записей, а в текущем скане найдено <50% — скрипт выходит без записи (защита от запуска не в корне проекта).
- Backtick-ссылки с line numbers (`file.php:123`) нормализуются к `file.php`.
- Basename fallback работает только если в проекте нет коллизий имен (один файл с таким именем).
- Не индексирует vendor/, node_modules/, scripts/plugins/, *.min.js, *.bundle.js (фильтр в `map-project.ps1` и `get-indexing-batch.ps1`).

## Связи
- Вызывается: `map-project.ps1` (автоматически), агент вручную
- Зависит от: `_lib.ps1`, архитектурных документов с backtick-ссылками
- Результат используется: `get-indexing-batch.ps1` (очередь индексации), агентами для метрик покрытия

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)