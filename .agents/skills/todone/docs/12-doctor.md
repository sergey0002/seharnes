# `tcheck doctor`: диагностика проекта

`doctor` — сводный read/check-проход. Он не является мигратором и не меняет
данные. Его задача — собрать находки с кодами, понятным действием и командой.

## Основные вызовы

```bash
# текущая/единственная очередь
tcheck doctor --queue site --root .
# все очереди из project-level registry
tcheck doctor --root . --all
# перед сдачей: предупреждения считаются ошибками
tcheck doctor --root . --all --strict
# добавить линт прозы явно
tcheck doctor --root . --all --strict --prose
```

`--all` перебирает очереди из `<root>/.todone/queues.json`. `--strict` переводит
warning в error. `--prose` включает проверку Markdown на HTML-комментарии,
символы нулевой ширины и опасные HTML/XML-вставки в заголовках; selftest и так
проверяет прозу поставки.

## Что проверяется

### Очередь и индекс

- JSON реестра, settings и index разбирается;
- ключи соответствуют QUEUES-1/INDEX-1/SETTINGS;
- строка индекса указывает на существующую папку и `task.json`;
- каждая папка с записью представлена строкой;
- мета строки совпадает с TASK-6;
- путь не ведёт за пределы queue-level `.todone`.

### Записи

`Validator` проверяет схему TASK-6, даты, id, статусы, массивы, refs, artifacts,
comments, source.raw, дополнительные поля типа и фактологические гейты.
Проверяется также stale digest и наличие файлов артефактов.

### Типы и потоки

`TypeIndex` проверяет JSON-плагин, поля, редактор, capabilities и гейты. Контракт
AGENT-1 проверяется `Brief` при `ttask pack` и отдельными приёмочными тестами.
`FlowIndex` проверяет FLOW-1/STEP-1: уникальные шаги, известные типы,
`input_from`, порядок, executor tier/mode, выходы и `max_batch`.

### Проектные роли и tools

`roles.json` проверяется по ROLE-1, неизвестная роль владельца даёт `ROLE_UNKNOWN`.
`tools.json` проверяется по TOOLS-1; capability, объявленная типом, но не
привязанная командой, даёт `CAPABILITY_UNBOUND`.

### Покрытие готовыми действиями

Коды, объявленные типами/проверками, объединяются с общей таблицей `HINTS`.
Для каждого кода должно существовать действие: либо hint, либо CLI-команда.

## Documentation workspace — отдельный check

Общий `doctor` не заменяет документационные команды. После
`tcheck docs init` документацию проверяют отдельно:

```bash
tcheck docs catalog --root <root>
tcheck docs check --root <root> --strict
tcheck docs stale --root <root>
```

Это сознательная граница: `doctor` диагностирует project/queue runtime, а
`DocumentationWorkspace.check()` — manifest, modules, sidecar claims, наличие
Markdown и source fingerprints одного docs workspace. Recursive aggregate —
отдельный explicit вызов `tcheck aggregate scan`; scanner и `todoc_scan` не
запускаются ни одним из этих вызовов.

## Как читать результат

Обычная строка выглядит так:

```text
[CODE] предмет: проблема → действие → команда
```

Завершение содержит число находок, ошибок, предупреждений, количество кодов с
готовым действием и `next`. В `--json` это поля `findings`, `summary`,
`next_actions`, `next`.

Пример безопасного цикла:

```bash
tcheck doctor --root . --all --json > /tmp/doctor.json
# исправить причины только через CLI
tqueue index-rebuild --queue site
ttask digest T-001 --queue site
tcheck validate --all --strict --queue site
tcheck doctor --root . --all --strict
```

## `validate`, `selftest` и doctor — не одно и то же

| Инструмент | Объект | Меняет данные |
|---|---|---:|
| `tcheck validate T-001` | записи и их типовые гейты | нет |
| `tcheck doctor` | проект, очереди, типы, потоки, роли, tools, проза | нет |
| `tcheck selftest` | команды, flags, типы, потоки, коды и проза самой поставки | нет |
| `tqueue index-rebuild` | только производный индекс | да, безопасно через CLI |
| `ttask digest` | производный `digest.md` и его artifact pointer | да |

## Готовое действие не означает автопочинку

Doctor специально не «чинит» неизвестный тип, не удаляет битый указатель и не
дописывает критерии за человека. Даже для `INDEX_MISMATCH` команда предлагает
`index-rebuild`, а для `TYPE_FIELD_MISSING` — реальный `ttask set`; решение
остаётся видимым и проверяемым.
