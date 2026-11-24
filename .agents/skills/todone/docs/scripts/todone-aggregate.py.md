# Скрипт: `tcheck aggregate`

<!-- meta
type: script
status: actual
updated: 2026-11-18
related: [../../SKILL.md]
tags: [harness, script, aggregate]
argv: passthrough
-->

## Суть
Обертка для `tcheck aggregate`: обновляет каталог агрегата в `.todone/` и пишет `aggregate.json`. Используется как узел в цепочках.

## Когда запускать
По требованию `tcheck aggregate` или в качестве стартовой процедуры в проекте для сборки агрегата.

## Аргументы
Общие флаги: `--root` (проект). Без других флаг.

## Коды выхода
- 0: успех
- 1: ошибка агрегата (ошибок нет)
- 3: требуется участие человека

## Что читает и что пишет
Читает: `<root>/.todone/` (очередь, роли, tools, types, flows, schemas, templates). Пишет: `<root>/.todone/aggregate.json`.

## Побочные эффекты
Пересчитывает агрегат при изменении типов/потоков/схем.

## Окружение и зависимости
`TODONE_ROOT`. Требует Python 3.8+.

## Примеры
```bash
python3 .agents/skills/todone/scripts/todone-aggregate.py
```

## Ограничения
Не обновляет каталоги в других местах (например, в поставке). Агрегат только в `<root>/.todone/`.

## Связи
Вызывается из `tcheck aggregate` (список команд). Процедуры агрегата: `docs/18-aggregation.md`.

## История изменений
- 2026-11-18: документация заполнена агентом
