---
name: todone
description: Управляет локальными очередями, JSON-записями, типами, потоками, доказательствами и отчётами через три точки входа.
---

# `todone` — маршрутизатор навыка

## Назначение

`todone` управляет локальными очередями, JSON-записями, типами, потоками,
доказательствами и отчётами через три точки входа. Используй этот файл как
маршрутизатор, а подробности открывай в `docs/` и `references/child-skills/`.

## Неснимаемые инварианты

1. Одна запись — одна папка `data/T-NNN-тип/` и один `task.json`.
2. `task.json` — единственный дом фактов записи; `index.json` — производная строка
   ссылок, мета и состояния потока без тела.
3. `id` (`T-NNN`) и `kind` неизменны после создания; продолжение/смена формы —
   новая дочерняя запись с `--parent`.
4. Внешний вход — `mirror`; `source.raw` хранится дословно, зеркало меняется
   только импортом. Служебная работа идёт в дочерней `intake`.
5. Факт не копируется между записями: используй `refs` с `kind: queue` или
   `ttask link`.
6. Поток — определение шагов в `flows/`; его записи обычны, `flow`, `flow_step`,
   `flow_run`, `flow_item` и `flow_revision` живут в строках индекса; отдельного
   state-файла нет. `routes` и `fan_out` только создают/блокируют обычные записи;
   status автоматически не меняется.
7. `parked` — отложенное состояние; сущности заметки нет.
8. Режимы чтения выбирают состав, но не обрезают выбранный текст. Размеры
   печатаются в знаках и байтах; большой контекст получает производный `digest.md`.
9. JSON и конфиги меняются через CLI, атомарно, с `.bak`; Markdown используется
   для процедур, инструкций, справочников и digest.
10. При недостатке входа, красном гейте, readonly-зеркале или битой связи нужно
    остановиться и вернуть код с готовым действием.

## Маршрутизация по намерению

| Намерение | Точка входа | Процедура | Первый вызов |
|---|---|---|---|
| найти/создать очередь, список, доска, порядок | `tqueue` | `references/child-skills/01`, `02` | `tqueue find` |
| создать/читать запись | `ttask` | `references/child-skills/03`, `06` | `ttask new <заголовок> --type <тип>` |
| постановка задачи через диалог | `ttask` + skill | `references/child-skills/14`, `types/intake` | `постановка задачи` |
| править поля, статус, владельца | `ttask` | `references/child-skills/07` | `ttask set <id> --by <имя>` |
| вести ленту решений | `ttask` | `references/child-skills/05`, `12` | `ttask comment list <id>` |
| разложить работу потоком | `ttask` | `references/child-skills/04` | `ttask flow start --flow <имя> --from <id>` |
| refs, artifacts, evidence, links | `ttask` | `references/child-skills/08` | `ttask show <id>` |
| пакет субагенту | `ttask` | `references/child-skills/11` | `ttask pack <id>` |
| типы, схемы, роли, tools, импорт | `tcheck` | `references/child-skills/09`, `10` | `tcheck doctor --all` |
| задокументировать явно | `ttask` + `tcheck docs` | `docs/04`, `18` | `ttask document --by <имя>` |
| проверить documentation workspace/catalog | `tcheck docs` | `docs/04`, `17`, `18` | `tcheck docs check --root <root>` |
| собрать autodoc bundle/HTML/audit | `tcheck autodoc` | `docs/20-autodoc` | `tcheck autodoc generate --root <root> --audit` |
| найти причину отказа | `tcheck` | `docs/05`, `12` | `tcheck doctor --all --strict` |

## Карта поставки

- `scripts/tqueue.py`, `scripts/ttask.py`, `scripts/tcheck.py` — тонкие точки входа;
- `scripts/tdcore/` — схема, ошибки, запись, хранилище, индекс, очередь, типы,
  проверки, поток, links, digest, brief, report, роли, tools, local aggregate,
  importer, autodoc bundle/HTML/audit и CLI;
- `assets/types/<имя>/type.json` — данные типа; `instruction.md` — рабочая инструкция;
  `agents/` — sealed return contracts; `checks/` и `profile.py` — расширения;
- `assets/flows/<имя>/flow.json` и `instruction.md` — встроенные определения маршрутов; проектный override живёт в `<root>/.todone/flows/<имя>/`;
- `assets/templates/*.json` — стартовые формы, не runtime-данные;
- `assets/examples/v6-project/` — чистый project-level fixture;
- `tests/` — приёмочные проверки.

Полная карта с назначением каждого файла: `docs/13-file-map.md`.
Подробное объяснение сущностей и layout: `docs/01-overview.md`, `03-data-model.md`,
`08-queues.md`. Полная справка CLI: `docs/04-cli.md`.

## Общий контракт CLI

Каждая команда понимает `--root`, `--queue`, `--json`, `--fields`, `--quiet`,
`--limit`, `--by`. Обычный вывод заканчивается `state-line`; ошибка имеет форму
`[CODE] предмет: проблема → действие → команда`; JSON — один объект. Коды
возврата: `0` успех, `1` находки/ошибка контроля, `3` нужен человек/вход.

## Границы

Локальный импорт Jira/OpenSpec/Spec Kit реализован из файла. Jira snapshot
дополнительно получает `JIRA-MIRROR-1` projection и completeness artifacts.
Рекурсивный aggregate реализован как generated read-only catalog через
`tcheck aggregate`; `todoc_scan` и сетевой Jira API client отсутствуют.
Экспорт внешнего Jira workflow, миграция старого формата и обратная совместимость
не реализованы.
