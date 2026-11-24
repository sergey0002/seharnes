# Жизненный цикл работы

В `todone` нет скрытого перехода от идеи к закрытию. Каждый переход оставляет
либо поле записи, либо реплику, либо указатель/артефакт, либо строку индекса.
Поэтому человек может восстановить, что произошло и что делать дальше.

## 1. Найти контур

```bash
tqueue find --root <root>
tqueue find --root <root> --scan
```

`find` читает `<root>/.todone/queues.json`. `--scan` дополнительно ищет каталоги
`<root>/tasks/*`, которые ещё не внесены в реестр. Если очередь одна, остальные
команды могут разрешить её без `--queue`; если очередей несколько, алиас нужно
назвать явно.

Создание:

```bash
tqueue init site --root <root>
# нестандартный каталог
tqueue init site --root <root> --path <absolute-or-relative-path>
```

Создаётся индекс очереди, но папка `data/` появляется только при первой записи.
JSON-файлы реестра и индекса не редактируются вручную.

## 2. Принять сырой вход или создать работу

### Обычная работа

```bash
ttask new «Добавить кнопку запуска» --type feature --queue site --root <root>
```

Создаётся `T-NNN`, каталог `data/T-NNN-feature/`, `task.json` и строка индекса.
Начальный статус по умолчанию `draft`; тип берётся из `tcheck types list`.

### Внешний вход

```bash
ttask new «Jira PROJ-7» --from-file jira.json \
  --source-system jira --source-id PROJ-7 --queue site --by intake-bot
```

или локальный текст через `--from-text`. Такая команда создаёт запись типа
`mirror`, помещает весь вход в `source.raw`, назначает `revision: 1` и печатает
команду дочерней `intake`. Команда формализации не выполняется автоматически.

Повторный импорт делается через:

```bash
tcheck import jira --file jira.json --queue site --by intake-bot
```

Импорт обновляет raw и revision, добавляет только новые внешние комментарии и
печатает дочерние команды только для новых предметов. Сеть и API-клиент в этой
поставке отсутствуют: импорт читает локальный файл.

## 3. Формализовать

Работа с зеркалом идёт в дочерней записи:

```bash
ttask new «Формализовать PROJ-7» --type intake --parent T-001 \
  --queue site --by analyst
```

В дочернюю запись заносятся пробелы, допущения, refs и предлагаемый рабочий
ребёнок. Факты из зеркала не копируются механически: связь с родителем —
`parent`/`refs(kind=queue)`.

## 4. Заполнить проверяемую запись

```bash
ttask set T-002 --problem «...» --change-kind feature \
  --goals «...» --acceptance «...» --acceptance «...» \
  --in-scope «...» --verify «python3 -m unittest ...» --by analyst
```

Повторяемые флаги строят адресуемые элементы (`G-1`, `AC-1`, `V-1` и т. д.).
Дополнительные поля типа передаются повторяемым `--extra name=value`. Не нужно
вписывать тело другой записи: для этого используется `ttask ref add` или
`ttask link`.

## 5. Разложить потоком, если нужен маршрут

```bash
tcheck flows show jira-feature --root <root>
ttask flow start --flow jira-feature --from T-001 --queue site --by lead
```

Для последовательного исследования, подготовки тестов, плана и аудита используй
исполняемый preset:

```bash
tcheck flows show issue-delivery --root <root>
ttask flow start --flow issue-delivery --from T-001 --queue site --by lead
```

Его порядок — `intake → research → test-prep → planning → plan-audit →
implementation fan-out → documentation → test-fix → final-testing`. В нём
planning объявляет `input_from: [research, test-prep]`; наличие черновика ещё не
открывает следующий шаг — prerequisite должен быть закрыт и оставить заявленные
outputs.

Поток создаёт черновики доступных шагов порцией не больше `max_batch`. Черновики
не становятся `ready` и не берутся автоматически. Человек публикует их:

```bash
ttask status T-002 --status ready --by lead
```

Состояние потока видно так:

```bash
ttask flow state T-001 --flow jira-feature
ttask flow next T-002
```

Поток не создаёт отдельную очередь состояния и не правит зеркало. `flow`,
`flow_step`, `flow_run`, `flow_item` и `flow_revision` лежат в строках
`index.json`; записи шагов — обычные `task.json`. `flow_item` различает slices,
а `flow_revision` — повторный план/аудит. Если следующий шаг не видит заявленный
результат предыдущего, появляется `FLOW_OUTPUT_MISSING`. Для FLOW-2-условия,
например `plan-audit.extra.verdict == approved`, невыполненная ветка даёт
`FLOW_CONDITION_UNMET`; статусы автоматически не меняются.

Flow можно целиком переопределить на уровне проекта: тот же id в
`<root>/.todone/flows/<id>/` перекрывает встроенный `todone/flows/<id>/`.
Подробности процесса `issue-delivery`, план-аудит и границы implementation slices
описаны в [отдельной главе](16-workflows-and-process.md).

## 6. Взять и выполнить

```bash
tqueue next --queue site
ttask claim T-002 --queue site --by developer
```

`claim` записывает `owner`, а для `draft`/`ready` переводит запись в
`in_progress` и заполняет `started_at`. Занятая другим владельцем запись не
перехватывается молча.

Исполнитель читает целиком или запрашивает узкий режим:

```bash
ttask show T-002 --mode full
ttask show T-002 --mode handoff --last 3
ttask pack T-002 --agent developer --mode handoff --last 3
```

Пакет субагенту запечатан: общий бриф, инструкция типа, тело задачи, выбранный
срез ленты, refs, artifacts и возвратный контракт. Субагент ничего не наследует
из разговора родителя.

## 7. Оставить доказательства

```bash
ttask ref add T-002 --kind file --path scripts/app.py \
  --note «основная точка изменения» --by developer
ttask artifact add T-002 --kind report --path artifacts/result.json \
  --note «полный результат исполнителя» --by developer
ttask evidence T-002 --kind tests --path artifacts/test.log \
  --note «полный stdout тестов» --by tester
```

Файл артефакта должен уже существовать внутри папки записи и не может выйти из
неё через абсолютный путь или `..`. Указатель обязан иметь пояснение. Содержимое
файла не копируется в `task.json`.

## 8. Отчёт и закрытие

```bash
ttask report-skeleton T-002 --by developer
# заполнить report.json в папке T-002-feature
ttask close T-002 --report report.json --verdict met --by developer
```

Закрытие проверяет гейты типа: tests/evidence, handoff, refs, reproduce, docs,
вердикт по `AC-N` и сам отчёт. `--verdict` заполняет пустые статусы критериев,
но не заменяет свидетельство, отчёт или требуемый handoff. При красном гейте
статус не меняется, отчёт остаётся для исправления.

Открытые записи можно закрыть в `cancelled` через `ttask status`; закрытую запись
можно вернуть в `in_progress` с обязательной причиной:

```bash
ttask reopen T-002 --reason «вернулось замечание ревью» --by lead
```

## 9. Проверить весь проект

```bash
tcheck validate T-002 --strict --queue site --root <root>
tcheck doctor --root <root> --all --strict
tcheck selftest --root <root>
```

`validate` проверяет выбранные записи, `doctor` — очереди, типы, потоки, роли,
tools, прозу и покрытие кодов действиями, `selftest` — саму поставку.
