# Быстрый старт

Ниже приведён минимальный рабочий путь для нового проекта. `<root>` — каталог
данных проекта, а `todone/` — каталог установленной поставки.

## 1. Создать проект и очередь

```bash
mkdir -p /tmp/my-project
python3 todone/scripts/tqueue.py init site \
  --root /tmp/my-project \
  --path /tmp/my-project/tasks/site
```

Проверить очередь:

```bash
python3 todone/scripts/tqueue.py find --root /tmp/my-project
python3 todone/scripts/tqueue.py summary \
  --root /tmp/my-project --queue site
```

## 2. Создать работу

```bash
python3 todone/scripts/ttask.py new "Проверить вход" \
  --type default --root /tmp/my-project --queue site --json
```

Команда возвращает `T-NNN`. Заполнить запись можно так:

```bash
python3 todone/scripts/ttask.py set T-001 \
  --root /tmp/my-project --queue site --by analyst \
  --problem "Нужно проверить новый вход" \
  --goals "получить проверяемый результат" \
  --acceptance "результат подтверждён тестом" \
  --verify "python3 -m unittest discover todone/tests"
```

Если id отличается, используй id из ответа `ttask new`.

## 3. Взять работу и оставить результат

```bash
python3 todone/scripts/ttask.py status T-001 \
  --status ready --root /tmp/my-project --queue site --by lead
python3 todone/scripts/tqueue.py next \
  --root /tmp/my-project --queue site
python3 todone/scripts/ttask.py claim T-001 \
  --root /tmp/my-project --queue site --by developer
```

Большой результат сохраняй внутри папки записи и регистрируй как artifact или
evidence. Факт в другой записи адресуй через `ref`/`link`, не копируй его.

```bash
python3 todone/scripts/ttask.py artifact add T-001 \
  --root /tmp/my-project --queue site \
  --kind tests --path artifacts/test.log --note "полный stdout" --by tester
python3 todone/scripts/ttask.py evidence T-001 \
  --root /tmp/my-project --queue site \
  --kind tests --path artifacts/test.log --note "результат тестов" --by tester
```

## 4. Закрыть запись

```bash
python3 todone/scripts/ttask.py report-skeleton T-001 \
  --root /tmp/my-project --queue site --by developer
# заполнить report.json в папке записи
python3 todone/scripts/ttask.py close T-001 \
  --root /tmp/my-project --queue site \
  --report report.json --verdict met --by developer
```

Закрытие не подменяет evidence и обязательные поля типа.

## 5. Запустить flow

Можно явно выбрать flow:

```bash
python3 todone/scripts/ttask.py flow start \
  --flow jira-fix --from T-001 \
  --root /tmp/my-project --queue site --by lead
```

Если `--flow` не указан, runtime выдаёт один `FLOW-CHOICE-1` selector с
allowlisted вариантами. Выбор передаётся явно:

```bash
python3 todone/scripts/ttask.py flow start \
  --from T-001 --choice jira-fix \
  --root /tmp/my-project --queue site --by lead
```

Рекомендация агента не считается выбором пользователя. Flow создаёт только
доступные черновики; статус `ready` и `claim` остаются явными действиями.

## 6. Подключить documentation workspace

```bash
python3 todone/scripts/tcheck.py docs init \
  --root /tmp/my-project --workspace-id my-project --product-id my-product
python3 todone/scripts/tcheck.py docs policy show --root /tmp/my-project
```

Создать документ явным intent:

```bash
python3 todone/scripts/ttask.py document \
  --root /tmp/my-project --by writer \
  --doc-key entity/order --kind entity \
  --content "# Order\n\nКаноническое описание Order."
```

`manual` запрещает автоматический путь, но оставляет этот явный вызов.
`disabled` запрещает и автоматический, и явный путь до повторного включения.

## 7. Проверить проект

```bash
python3 todone/scripts/tcheck.py validate \
  --root /tmp/my-project --queue site --all --strict
python3 todone/scripts/tcheck.py docs check --root /tmp/my-project
python3 todone/scripts/tcheck.py doctor \
  --root /tmp/my-project --all --strict
```

## 8. Постановка задачи через диалог

В Agent Mode используй триггер **«постановка задачи»**. Skill собирает требования
по одному вопросу, хранит подтверждённые факты отдельно от proposals и создаёт
`intake`-запись/итоговую typed task только после явной команды
«сформулируй задачу» или «собери задачу». Фраза «зафиксируй в задаче» пишет
только подтверждённый факт через CLI.

Подробный маршрут: [child-skills/14-task-intake.md](../child-skills/14-task-intake.md).

## 9. Агрегировать объявленные project roots

```bash
python3 todone/scripts/tcheck.py aggregate scan --root /tmp/my-project
python3 todone/scripts/tcheck.py aggregate status --root /tmp/my-project
python3 todone/scripts/tcheck.py aggregate verify --root /tmp/my-project
```

Для child workspace сначала добавь `.todone/workspace.json`; подробности — в
[агрегации](18-aggregation.md).

Если нужен структурированный результат для интеграции, добавляй `--json`.
