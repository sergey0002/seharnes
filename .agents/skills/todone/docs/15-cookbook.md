# Рецепты: сквозные сценарии

Ниже команды показаны как рабочие последовательности. `<root>` — корень проекта;
если команды запускаются из него, `--root .` можно не повторять.

## Рецепт A. Пустой проект → обычная запись

```bash
mkdir -p /tmp/my-project
tqueue init site --root /tmp/my-project
ttask new «Добавить кнопку» --type feature \
  --root /tmp/my-project --queue site
ttask set T-001 --problem «Пользователю не виден запуск» \
  --change-kind feature \
  --goals «Кнопка запускает действие» \
  --acceptance «Команда запуска завершается кодом 0» \
  --acceptance «Документация описывает кнопку» \
  --in-scope «Экран настроек» \
  --out-of-scope «Новый API» \
  --verify «python3 -m unittest discover» \
  --by lead
ttask status T-001 --status ready --by lead
tqueue board --root /tmp/my-project --queue site
```

Почему так: создание отделено от публикации. В `draft` можно спокойно заполнить
контекст; `ready` — явное решение, что запись достаточно определена.

## Рецепт B. Взять, доказать, закрыть

```bash
ttask claim T-001 --root /tmp/my-project --queue site --by developer
# исполнитель меняет файлы проекта и создаёт лог в папке записи
mkdir -p /tmp/my-project/tasks/site/.todone/data/T-001-feature/artifacts
printf '0 tests passed\n' > /tmp/my-project/tasks/site/.todone/data/T-001-feature/artifacts/test.log
ttask evidence T-001 --root /tmp/my-project --queue site \
  --kind tests --path artifacts/test.log --note «прогон тестов» --by tester
ttask report-skeleton T-001 --root /tmp/my-project --queue site --by developer
# заполнить report.json: files_changed, verification, evidence и AC statuses
ttask close T-001 --root /tmp/my-project --queue site \
  --report report.json --verdict met --by developer
tcheck validate T-001 --root /tmp/my-project --queue site --strict
```

Для реального запуска файл evidence должен содержать фактический stdout/stderr и
код команды; пример выше показывает только адресацию.

## Рецепт C. Внешний Jira-файл и формализация

```bash
tqueue init site --root /tmp/my-project
cat > /tmp/jira.json <<'JSON'
{"id":"PROJ-7","fields":{"summary":"Экспорт","comment":{"comments":[{"id":"c1","body":"Нужен CSV"}]}}}
JSON
tcheck import jira --root /tmp/my-project --queue site \
  --file /tmp/jira.json --by importer
# из вывода взять T-001 и выполнить напечатанную команду
ttask new «Формализовать PROJ-7» --type intake --parent T-001 \
  --root /tmp/my-project --queue site --by analyst
ttask set T-002 --extra raw_gaps='не указан срок' \
  --extra assumptions='CSV остаётся локальным' \
  --extra draft_child='planning: план интеграции' --by analyst
```

Raw остаётся в `T-001/task.json`, а рассуждение живёт в `T-002/task.json`.
Повторный импорт того же `PROJ-7` увеличит revision, но не задублирует `c1`.

## Рецепт D. Поток Jira-fix

```bash
ttask flow start --flow jira-fix --from T-001 --batch 2 --by lead \
  --root /tmp/my-project --queue site
ttask flow state T-001 --flow jira-fix --root /tmp/my-project --queue site
ttask flow next T-002 --root /tmp/my-project --queue site
# каждый созданный черновик публикуется отдельно
ttask status T-002 --status ready --by lead --root /tmp/my-project --queue site
# после закрытия нужных шагов повторить start для оставшихся
```

Поток `jira-fix` создаёт `intake`, параллельные `research`, `planning`, `test-prep`,
затем `fix`, optional `code-review` и обязательный `testing`. В индексе строки
помечены `flow: jira-fix` и `flow_step: …`; отдельной очереди потока нет.

## Рецепт E. Большая запись и чтение по частям

```bash
ttask show T-001 --mode digest
ttask digest T-001
ttask digest T-001 --part body
ttask digest T-001 --part toc
ttask digest T-001 --part comments:10-20
ttask show T-001/C-17
ttask show T-001/AC-3
ttask tree T-001
```

`digest.md` — производный файл с телом, оглавлением и дословной лентой. После
любого `set`, `comment`, `ref` или `artifact` пересоздай его.

## Рецепт F. Массовая операция с откатом

`ops.json` — массив объектов операций, например:

```json
[
  {"op":"status","ids":["T-001","T-002"],"status":"parked","reason":"ждём релиз"},
  {"op":"set","ids":["T-001","T-002"],"phase":"later"}
]
```

```bash
ttask batch ops.json --dry-run --queue site --by lead
ttask batch ops.json --queue site --by lead
```

Сначала печатается план. При ошибке второй операции весь queue-level `.todone`
восстанавливается из резервной копии транзакции.

## Рецепт G. Передача субагенту

```bash
tcheck types show research
tcheck roles list
ttask pack T-003 --mode handoff --last 3 --agent researcher --queue site
```

Пакет содержит только нужный контекст и контракт возврата. Большой результат
агент пишет в объявленный artifact, а родитель принимает его и добавляет handoff.

## Рецепт H. Финальная проверка

```bash
python3 -m unittest discover todone/tests
python3 todone/scripts/tcheck.py selftest
python3 todone/scripts/tcheck.py doctor \
  --root todone/examples/v6-project --all --strict
```

Если менялись файлы поставки, добавь `tcheck doctor --prose`; если менялись
данные очереди, сначала `tcheck validate --all --strict`.
