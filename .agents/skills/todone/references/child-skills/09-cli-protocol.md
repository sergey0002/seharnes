# Общий протокол CLI

## Точки входа

- `tqueue` — очередь как порядок;
- `ttask` — запись как работа;
- `tcheck` — контроль, схемы, типы, потоки, роли, tools, импорт.

## Общие флаги

`--root`, `--queue`, `--json`, `--fields`, `--quiet`, `--limit`, `--by` доступны
у каждой команды; полный help строится из того же объявления, что и parser.

## Вывод и ошибки

Обычный вывод: одна строка на объект и завершающая `состояние: … | next: …`.
Ошибка: `[CODE] предмет: что не так → чем лечить → команда`. `--json` печатает
один объект. Коды возврата: `0` успех, `1` находки/отказ контроля, `3` нужен
человек или обязательный вход.

## Состав

`tqueue`: `find`, `init`, `list`, `next`, `summary`, `done`, `sort`, `gantt`,
`board`, `index-rebuild`.

`ttask`: `new`, `show`, `pack`, `set`, `status`, `report-skeleton`, `close`,
`reopen`, `claim`, `unclaim`, `comment`, `ref`, `artifact`, `evidence`, `batch`,
`link`, `tree`, `digest`, `flow`.

`tcheck`: `doctor`, `validate`, `schema`, `selftest`, `types`, `flows`, `roles`,
`tools`, `import`.

Вложенные действия и локальные флаги печатаются только своей точкой входа:
`ttask comment --help`, `tcheck roles set --help`.
