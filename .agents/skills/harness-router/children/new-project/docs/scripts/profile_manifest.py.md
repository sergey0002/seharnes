# Скрипт: `profile_manifest.py`

<!-- meta
type: script
status: actual
updated: 2026-11-13
related: [../../SKILL.md]
tags: [harness, export, profile, manifest]
-->

## Суть

Строит read-only карту файлов профиля из `kit.json`. Developer и Project берут полный kit, Core оставляет runtime-скилы, runtime-правила, harness-инструменты и панель, а task/tracker-контент исключает.

## Когда запускать

Для dry-run экспорта и для проверки состава Core без записи в Target. Полный PowerShell-экспорт пока использует собственный шаг копирования.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--root` | Корень Source. |
| `--profile` | `core`, `developer` или `project`. |
| `--json` | Печатать JSON; вывод всегда JSON. |

## Коды выхода

`0` - карта построена; `2` - ошибка чтения kit или неверный профиль.

## Что читает и что пишет

Читает `kit.json` и файлы Source. Ничего не пишет.

## Побочные эффекты

Нет. Hash считается по содержимому файлов, но файлы не меняются.

## Окружение и зависимости

Python 3. Использует `harness-core/scripts/lib/manifest.py` и `assets/kit.json`.

## Примеры

```sh
python3 .agents/skills/harness-router/children/new-project/scripts/profile_manifest.py --root . --profile core
```

## Ограничения

Core-фильтр повторяет список runtime-скилов и правил из `rebase_project.ps1`; при изменении этого списка нужно обновить оба места до перевода фактического экспорта на Python. Project пока совпадает с Developer по составу kit. Скрипт не копирует файлы и не меняет Git.

## Связи

Используется `harness_cli.py export --dry-run`. Связан с `kit.json`, `canon-paths.yaml` и `rebase_project.ps1`.

## История изменений

- 2026-11-13: добавлен профильный manifest для dry-run Core/Developer/Project.
