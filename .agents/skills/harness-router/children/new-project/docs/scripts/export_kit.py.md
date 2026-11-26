# Скрипт: `export_kit.py`

<!-- meta
type: script
status: actual
updated: 2026-11-25
related: [../../SKILL.md, ../kit_selection.py, ../kit_adapt.py]
tags: [harness, export, kit, migration]
-->

## Суть

Копирует kit харнеса из исходного проекта в целевой по одному предикату состава:
файлы берутся из `assets/kit.json` через `kit_selection`, поэтому предпросмотр и
фактический перенос всегда совпадают. Генерация представлений сред выполняется в
целевом проекте, а не копированием исходных каталогов.

## Когда запускать

При переносе харнеса в новый проект, обновлении уже установленного kit или точном
зеркалировании состава. Запускается через `harness_cli.py export` или
`harness_transfer.py export`.

## Аргументы

| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `--source` | путь | нет | `.` | Корень проекта-источника. |
| `--target` | путь | да | нет | Каталог проекта-цели; создаётся при отсутствии. |
| `--profile` | `core`/`developer`/`project` | нет | `developer` | Состав kit. |
| `--mode` | `install`/`update`/`mirror` | нет | `install` | Режим записи. |
| `--project-name` | строка | нет | имя папки Target | Имя проекта для Serena и `GRAPHITI_GROUP_ID`. |
| `--skip-runtime-deps` | флаг | нет | выключен | Не копировать `node_modules` и `vendor` инструментов. |
| `--skip-tools` | флаг | нет | выключен | Не копировать каталог `.tools`. |
| `--exclude` | путь | нет | пусто | Не копировать путь или префикс; повторяемый. |
| `--keep` | путь | нет | пусто | Путь принадлежит Target, не перезаписывать и не удалять; повторяемый. |
| `--dry-run` | флаг | нет | выключен | Только посчитать состав, без записи. |
| `--json` | флаг | нет | выключен | Печатать результат JSON (вывод всегда JSON). |

## Коды выхода

| Код | Значение |
|---|---|
| 0 | Перенос выполнен, must-check пройден, или это `--dry-run`. |
| 2 | Ошибка переноса или must-check нашёл пропуски. |

## Что читает и что пишет

- Читает: `assets/kit.json`, `assets/environments.json`, файлы Source по профилю.
- Пишет в Target: выбранные файлы kit, `.doc/.rebase-kit.json`, `.doc/.rebase-report.md`,
  `.doc/.rebase-conflicts.json`, `.doc/.rebase-preserved.txt`, `EXPORT_NEXT_STEPS.md`.
- Backup перезаписанных файлов: `.doc/.rebase-backup/{stamp}/`.

## Режимы

| Режим | Поведение |
|---|---|
| `install` | Не перезаписывает существующие файлы; MCP и `AGENTS.md` сливаются структурно. |
| `update` | Обновляет kit-файлы, локальные файлы вне kit сохраняет. |
| `mirror` | Удаляет kit-файлы, которых нет в источнике, после backup. |

## Побочные эффекты

- Создаёт каталоги `.doc/architecture/_map`, `.doc/tasks/_map`, `.doc/qa/reports`.
- Создаёт `mcp.env` из `mcp.env.example` с именем проекта в `GRAPHITI_GROUP_ID`.
- Переписывает абсолютные пути Source на Target, гасит CodePrism и чистит токены.
- Запускает `sync-agent-views.sh --local-only` в Target.

## Ограничения

- Core перед записью проверяет декларации политик Source установленным reader.
- `mirror` удаляет только путь, отсутствующий в источнике, и только после backup.
- Секреты и `*.local.*` не копируются.

## Окружение и зависимости

Python 3.8+ и `bash` для шага развёртывания представлений. Модули:
`kit_selection`, `kit_adapt`, `transfer_modes`, `transfer_merge`, `transfer_plan`
и установленный reader `canon_paths.py` из `harness-core/scripts`.

## Примеры

```bash
python3 .agents/skills/harness-router/children/new-project/scripts/export_kit.py \
  --source . --target /path/to/project --profile developer --mode install --dry-run

python3 .agents/skills/harness-router/children/new-project/scripts/export_kit.py \
  --source . --target /path/to/project --profile core --mode update
```

## Связи

- Состав: `lib/kit_selection.py`.
- Адаптации: `lib/kit_adapt.py`.
- Режимы: `lib/transfer_modes.py`.
- Вызывающие: `harness_cli.py export`, `harness_transfer.py export`.

## История изменений

- 2026-11-25: скрипт добавлен как единственная точка переноса; заменил `rebase_project.ps1`.
