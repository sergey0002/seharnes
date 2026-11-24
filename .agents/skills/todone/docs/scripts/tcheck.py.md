# Скрипт: `tcheck`

<!-- meta
type: script
status: actual
updated: 2026-11-18
related: [../../SKILL.md]
tags: [harness, script, tcheck, validation, autodoc]
-->

## Суть
Точка входа для контроля и документации: типы/схемы/роли/tools, doctor, автодокументация, документация workspace/catalog. Делегирует в `tdcore.check_cli.CheckCli`.

## Когда запускать
При проверке конфигурации: `tcheck types`, `tcheck flows`, `tcheck schemas`, `tcheck roles`, `tcheck tools`, `tcheck doctor`. При автодокументации: `tcheck autodoc generate --root <root> [--audit]`. При проверке документации: `tcheck docs check --root <root>`.

## Аргументы
Общие флаги: `--root`, `--queue`, `--json`, `--fields`, `--quiet`, `--limit`, `--by`.
Подкоманды: `types` (list/show), `flows` (list/show), `schemas` (list/show), `roles` (list/show), `tools` (list/show), `doctor` (--all, --strict), `autodoc` (generate/regenerate), `docs` (init/check), `aggregate`, `selftest`.
Вложенные флаги у подкоманд (например `autodoc generate --root --html --json --audit`).

## Коды выхода
- 0: успех
- 1: находки/ошибка контроля
- 3: требуется человеческое вмешательство

## Что читает и что пишет
Читает: `assets/types/`, `assets/flows/`, `assets/schemas/`, `assets/templates/`, `<root>/.todone/`, `<root>/docs/`.
Пишет: при `autodoc generate` создает бандл JSON, HTML в `docs_html/`, audit JSON; при `docs init` создает `docs/manifest.json` и структуру WORKSPACE-1.

## Побочные эффекты
Генерирует артефакты автодокументации, может писать в `.todone/autodoc/`.

## Окружение и зависимости
`TODONE_ROOT`. Требует Python 3.8+, Node.js для Mermaid (опционально).

## Примеры
```bash
tcheck doctor --all
tcheck autodoc generate --root . --audit
tcheck docs check --root .
tcheck types show task --json
```

## Ограничения
Не управляет очередями/записями. Автодокументация требует Node.js для диаграмм.

## Связи
Вызывается из SKILL.md (намерения "типы/схемы/роли/tools", "собрать autodoc", "проверить documentation"). Процедуры: `references/child-skills/09-cli-protocol.md`, `10-types-stages-roles.md`, `docs/04-cli.md`, `docs/20-autodoc.md`.

## История изменений
- 2026-11-18: документация заполнена агентом
