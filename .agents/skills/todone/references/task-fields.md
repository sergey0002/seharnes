# Поля записи TASK-6

## Идентичность и планирование

`id`, `kind`, `title`, `status`, `priority`, `phase`, `release`, `parent`,
`depends_on`, `parallelizable`, `module`, `owner`, `started_at`, `blocked_reason`,
`created_at`, `due`, `estimate_h`, `change_kind`.

`id` и `kind` неизменны; `parent` — связь, а не копия родителя. `status` допускает
`draft`, `ready`, `in_progress`, `blocked`, `parked`, `mirror`, `closed`,
`cancelled`. `due` — дата, `estimate_h` — часы, `priority` участвует в порядке.

## Элементы

`goals`, `acceptance`, `in_scope`, `out_of_scope`, `context`, `files_hint`, `steps`,
`verify`, `open_questions`, `notes` — массивы `{id,text}`. Префиксы адресов:
`G-N`, `AC-N`, `IN-N`, `OUT-N`, `CT-N`, `F-N`, `S-N`, `V-N`, `Q-N`, `N-N`.

Создание/перезапись массива делается повторяемым флагом:

```bash
ttask set T-001 --acceptance «AC смысл 1» --acceptance «AC смысл 2» --by lead
```

Тексты не измеряются квотой символов. Проверяется, что они непустые.

## Дополнительные дома

- `extra` — поля типа;
- `refs` — `REF-1`, адрес + обязательное пояснение;
- `artifacts` — `ARTEFACT-1`, путь файла + пояснение;
- `source` — объект контракта `SOURCE` (версия SRC-2), raw внешнего входа;
- `comments` — `COMMENT-1`, события и решения.

Ни один из этих массивов не является копией другой записи. Связь между записями
делается `ttask link`/`ref kind=queue`; результат ребёнка остаётся у ребёнка.
