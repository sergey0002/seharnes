# Сроки, оценки и аренда записи

Срок и владелец — поля записи, а быстрый список этих значений — строки индекса.
Отдельной сущности lease нет: аренда выражается через `owner`, `status`,
`started_at` и реплику в ленте.

## Поля времени и планирования

| Поле | Формат/смысл | Кто меняет |
|---|---|---|
| `due` | `ГГГГ-ММ-ДД`; сравнивается с текущей UTC-датой | `ttask new --due`, `ttask set --due` |
| `estimate_h` | число часов | `ttask set --estimate` |
| `owner` | имя человека/роли | `claim`, `unclaim`, `set --owner` |
| `started_at` | ISO-время первого входа в работу | `claim` или `status in_progress` |
| `blocked_reason` | причина блокировки | `status blocked --reason` |
| `release` | непустая метка релиза или null | `new/set`, фильтры |
| `priority` | целое для порядка | `new/set`, `sort` |
| `phase` | свободная стадия сортировки/отбора | `new/set` |

## Взять работу

```bash
tqueue next --queue site --count 1
ttask claim T-001 --queue site --by alice
```

Если `owner` пуст, `claim` ставит его в `alice`. Если запись `draft` или `ready`,
статус становится `in_progress`, а `started_at` получает текущую метку. В ленте
появляется human-реплика. Если запись уже принадлежит другому, команда не
перетирает владельца, а возвращает `ASK_USER` с командой `unclaim`.

`--owner` позволяет отделить владельца от аудитора:

```bash
ttask claim T-001 --owner bot-developer --by lead
```

Освобождение:

```bash
ttask unclaim T-001 --by alice
```

Владелец обнуляется, старая аренда остаётся в ленте. Сама запись не возвращается
автоматически в `ready`; при необходимости это делается `ttask status`.

## Статусы исполнения

```bash
ttask status T-001 --status blocked \
  --reason «ждём внешний контракт» --by alice
ttask status T-001 --status parked \
  --reason «вернуться после релиза» --by alice
ttask status T-001 --status ready --by lead
```

Причина `blocked` пишется в `blocked_reason` и в комментарий; причина parked — в
комментарий. Никаких `NOTES.md` или отдельного объекта заметки нет.

## Доска и сроки

```bash
tqueue board --queue site
tqueue list --queue site --overdue
tqueue gantt --queue site
tqueue gantt --queue site --release v1
```

`board` печатает пять блоков: в работе, следующие кандидаты, заблокированные,
отложенные и горящие сроки. `gantt` печатает только строки с `due`, сортируя их
по дате. Просроченная запись — это `due < today` и статус не `closed`/`cancelled`.

## Правила конкуренции

- `claim` не является блокировкой файла ОС; это явное состояние в JSON.
- Перед началом исполнитель проверяет `owner` и не перехватывает чужую запись
  без решения владельца.
- Массовая смена нескольких записей делается через `ttask batch` и сначала
  проверяется `--dry-run`.
- При конфликте или неопределённости CLI выдаёт `ASK_USER`, а не выбирает за
  человека.
