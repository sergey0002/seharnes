# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, map-project]
-->

## Суть
Строит полную карту проекта для документации и обновляет производные артефакты индексации. Создаёт `.doc/architecture/_map/` с метриками по типам файлов: дерево каталогов (`tree.txt`), PHP-метрики (LOC, классы, функции, scope), procedural PHP (0 классов), JS/TS метрики, TPL/CSS метрики, списки файлов по типам, роуты и конфиги, hot-files.txt (топ-50 активных за 90 дней по git). В конце автоматически запускает `generate-doc-index.ps1` и `generate-file-registry.ps1` (в тихом режиме).

## Когда запускать
- Первый запуск индексации проекта (bootstrap documentation).
- После крупных структурных изменений (новые модули, рефакторинг).
- Периодически для обновления метрик и hot-files.
- Агент вызывает перед началом пакетной индексации (project-doc indexing).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -RelativePath | | string | да | | Относительный путь для ограничения сканирования конкретной папкой |
| -ClassPattern | | string | нет | '' | Регулярка для поиска классов (переопределяет дефолтную) |
| -FunctionPattern | | string | нет | '' | Регулярка для поиска функций/методов (переопределяет дефолтную) |

## Коды выхода
Скрипт не возвращает явные коды выхода (всегда 0 при успехе, исключение при ошибке).

## Что читает и что пишет
**Читает:**
- Все файлы проекта через `Get-ProjectFiles` (PHP, Vue, JS/TS, TPL, CSS, SQL, конфиги)
- `git log --since=90d --name-only` — для hot-files.txt

**Пишет (в `.doc/architecture/_map/`):**
- `tree.txt` — дерево каталогов (до глубины 6)
- `php-metrics.txt` — `loc<TAB>classes<TAB>functions<TAB>scope<TAB>path`
- `procedural-php-files.txt` — `loc<TAB>scope<TAB>path` (файлы с 0 классов)
- `js-metrics.txt` — `loc<TAB>functions<TAB>scope<TAB>path`
- `tpl-metrics.txt` — `loc<TAB>scope<TAB>path`
- `css-metrics.txt` — `loc<TAB>classes<TAB>scope<TAB>path`
- `js-files.txt`, `vue-files.txt`, `tpl-files.txt`, `css-files.txt` — списки путей
- `hot-files.txt` — `count<TAB>path` (топ-50 за 90 дней)
- `doc-index.tsv` — через `generate-doc-index.ps1 -Quiet`
- `file-registry.tsv` — через `generate-file-registry.ps1 -Quiet`

## Побочные эффекты
- Создаёт/перезаписывает все файлы в `.doc/architecture/_map/`.
- Создаёт директорию `_map` при необходимости.

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-ProjectFiles`, `Get-RelativePath`, `Read-TextFile`, `Write-Utf8File`, `Test-GitAvailable`, `Normalize-RelativePath`.
- `git` — для hot-files.txt (опционально, если нет — пишется 'git unavailable').
- `robocopy`/`rsync`/`Copy-Item` — не используются (только чтение).

## Примеры
```powershell
# Полное сканирование
powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1 -RelativePath "."

# Сканирование только PHP модуля
powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1 -RelativePath "lib/Objects/Payment"

# С кастомными паттернами
powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1 -RelativePath "." -ClassPattern "class\s+\w+" -FunctionPattern "function\s+\w+"
```

Вывод:
```
Building project map...
Map done: .doc/architecture/_map/
  PHP files: 2145
  Vue components: 342
  JS/TS files: 567
  TPL files: 189
  CSS files: 78
  SQL files: 23
  Procedural PHP (0 classes): 412
```

## Ограничения
- Scope определяется эвристикой: `scripts/plugins/`, `admin/scripts/plugins/`, `vendor/`, `node_modules/`, `dompdf/`, `phone-codes/`, `*.min.js`, `*.min.css`, `*.bundle.js` → `vendor`; остальное → `app`.
- Регулярки для классов/функций PHP/JS/TS/CSS — упрощённые, могут пропускать edge cases.
- Не сканирует vendor/, node_modules/, .git, кэш, минифицированные файлы.
- `hot-files.txt` требует git; без git приоритезация в `get-indexing-batch.ps1` не работает.

## Связи
- Вызывается: агент при bootstrap/переиндексации, вручную командой «проанализируй карту проекта»
- Зависит от: `_lib.ps1`, структуры проекта
- Результат используется: `get-indexing-batch.ps1` (реестр + hot-files), агентами для метрик и навигации

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
- 2026-11-07: добавлены параметры -RelativePath, -ClassPattern, -FunctionPattern в таблицу аргументов