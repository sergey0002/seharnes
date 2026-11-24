# Сформулировать запись

## Обычное создание

```bash
ttask new «Заголовок» --type planning --queue site --root <root>
```

Создаётся `T-NNN`, папка `data/T-NNN-planning/`, `task.json` и строка индекса.
Тип выбирается из `tcheck types list`; по умолчанию — `default`, статус — `draft`.
`--by` для обычного `new` не нужен, но нужен для правок и зеркала.

## Сырой вход

```bash
ttask new «Jira PROJ-1» --from-text «…» --source-system jira \
  --source-id PROJ-1 --queue site --by importer
ttask new «Jira PROJ-1» --from-file jira.json --source-system jira \
  --source-id PROJ-1 --queue site --by importer
```

Оба вызова создают `mirror`, хранят raw дословно и печатают команду дочерней
`intake`; дочерняя запись публикуется отдельным вызовом человека.

## Формулировка

Заполняй `problem`, повторяемые `--goals`, `--acceptance`, `--in-scope`,
`--out-of-scope`, `--context`, `--files-hint`, `--steps`, `--verify`,
`--open-questions`, `--notes`. Поля типа идут повторяемым `--extra имя=значение`.

```bash
ttask set T-001 --problem «…» --acceptance «…» \
  --acceptance «…» --verify «команда» --by lead
```

Не копируй чужой факт. Укажи `--parent` при продолжении и добавь `ref kind=queue`.
`id` и `kind` после создания не меняются.
