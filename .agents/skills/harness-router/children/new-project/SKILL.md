---
name: new-project
description: >-
  Переносит или обновляет kit харнеса в целевом проекте режимами install, update
  и mirror. Применять по запросам перенести харнес, экспортировать kit, обновить
  kit, повторный перенос kit, clean install harness, new-project.
---

# new-project

Перенос kit харнеса в целевой проект и повторное обновление. Точка входа одна:
`scripts/export_kit.py`, она же вызывается `harness_cli.py export` и
`harness_transfer.py export`. Отдельного PowerShell-движка больше нет.

Состав kit задаёт `harness-core/assets/kit.json`. Включённость сред задаёт
`harness-core/assets/environments.json`, и её читает только шаг развёртывания
представлений в целевом проекте. Экспорт копирует эталоны канона и не копирует
сгенерированные представления сред: их создаёт `sync-agent-views.sh` уже в Target.

## Когда применять

- первый перенос харнеса в существующий проект;
- нужно обновить kit в уже перенесённом проекте;
- нужен точный kit без локальных файлов проекта;
- нужно понять, что будет перезаписано и что останется локальным.

## Вход

- абсолютный путь Source и Target;
- профиль `core`, `developer` или `project`;
- режим `install`, `update` или `mirror`.

## Режимы

| Режим | Поведение |
|---|---|
| `install` | Первый перенос. Существующий файл не перезаписывается. `mcp.json` и `AGENTS.md` сливаются структурно: серверы Target сохраняются. |
| `update` | Обновляет kit-файлы поверх установленного харнеса, локальные файлы вне kit сохраняет. |
| `mirror` | Точный kit: удаляет файлы kit, которых нет в источнике, после backup. |

Дополнительно `export` принимает `--exclude PATH` (не копировать путь или префикс) и
`--keep PATH` (путь принадлежит Target, не перезаписывать и не удалять). Оба флага
повторяемые. Ими исключают тяжёлые архивы и сохраняют локальные файлы Target.

## Профили

| Профиль | Состав |
|---|---|
| `core` | Runtime-скилы, правила, harness-инструменты и панель; без трекера и task-скилов. |
| `developer` | Полный kit: Jira, ветки, PHP, Docker, e2e. |
| `project` | Полный kit и данные приложения. |

Перед записью Core проверяет декларации политик Source установленным reader и
останавливается при `POLICY_MISSING` или `TRUSTED_GATE_WEAKENING`.

## Шаги

1. Предпросмотр без записи:

```bash
python3 .agents/skills/harness-router/children/new-project/scripts/export_kit.py \
  --source . --target /path/to/project --profile developer --mode install --dry-run
```

2. Перенос:

```bash
python3 .agents/skills/harness-router/children/new-project/scripts/export_kit.py \
  --source . --target /path/to/project --profile developer --mode install
```

Через CLI харнеса: `harness_cli.py export --target <path> --profile Full|Core`.

3. Проверить отчёт и маркер:

```text
.doc/.rebase-report.md
.doc/.rebase-report.json
.doc/.rebase-conflicts.json
.doc/.rebase-preserved.txt
.doc/.rebase-kit.json
EXPORT_NEXT_STEPS.md
```

4. Открыть `EXPORT_NEXT_STEPS.md` в Target и выполнить настройку проекта.
5. Проверить готовность без записи:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py \
  --root . --check
```

## Выход

- kit в Target по составу `kit.json`;
- backup перезаписанных файлов в `.doc/.rebase-backup/{stamp}/`;
- представления включённых сред, собранные `sync-agent-views.sh --local-only`;
- отчёт, маркер и список файлов Target вне kit;
- `EXPORT_NEXT_STEPS.md`.

## Ограничения

- Секреты и `*.local.*` не копируются; `mcp.env` создаётся из `mcp.env.example`.
- `install` не перезаписывает существующие файлы.
- `mirror` удаляет только путь kit, отсутствующий в источнике, после backup.
- DSH не входит в kit: среда отключена, файлы отсутствуют в `kit.json`.
- Абсолютные пути Source переписываются на Target; CodePrism отключается заглушкой.

## Read-only предпросмотр и сверка

`scripts/harness_transfer.py` — отдельный движок для явно выбранных путей и
локального bare-хранилища Git. Команды `fetch`, `inventory`, `plan`, `verify`,
`approve`, `apply`, `rollback`, `render`, `compact`, `adopt` и `export` работают
без сети, кроме `fetch`. `export` в этом движке вызывает тот же `export_kit.py`,
поэтому состав совпадает с `harness_cli.py export`.

- `fetch` получает ref в `refs/harness/source`; встроенный пароль в URL отклоняется.
- `plan` строит предпросмотр с решениями по конфликтам.
- `apply` пишет выбранные файлы через backup, журнал и verify; receipt пишется последним.
- `rollback` восстанавливает активный журнальный прогон.
- `render` пересобирает generated views доверенными генераторами.

## История изменений

- 2026-11-25: PowerShell-движок `rebase_project.ps1` и обёртки удалены. Экспорт идёт через `export_kit.py` по составу `kit.json`; предпросмотр и перенос используют один walker. Добавлен режим `mirror`. DSH исключён из kit.

## Связанные документы

`export_kit.py`, `profile_manifest.py`, `kit_selection.py`, `kit_adapt.py`,
`transfer_modes.py`, `harness_transfer.py`. Канон процедуры:
`.doc/rebase_project.md`.
