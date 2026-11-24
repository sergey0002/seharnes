# Потоки как настраиваемые процессы

## 1. Что в framework называется process

В разговоре процесс — это маршрут работы. В runtime-сущность называется **flow**:

```text
flow.json       определение маршрута и зависимостей
instruction.md  человеческая процедура этого маршрута
index.json      состояние конкретного запуска: flow, step, run, item и revision в строках
 task.json      факты обычных записей, созданных для шагов
artifact        большой результат шага
```

Номера `T-001`, `T-002` не записываются в `flow.json`: они выдаются очередью при конкретном запуске.

## 2. Где хранится определение

Встроенные preset находятся в поставке:

```text
todone/flows/<flow-id>/flow.json
todone/flows/<flow-id>/instruction.md
```

Для проектного переопределения runtime также читает:

```text
<root>/.todone/flows/<flow-id>/flow.json
<root>/.todone/flows/<flow-id>/instruction.md
```

Если в project overlay есть тот же `flow-id`, он целиком заменяет встроенное определение. Это не отдельная очередь и не отдельный state-файл. В `tcheck flows show` instruction берётся из фактической папки выбранного определения.

Пример:

```bash
tcheck flows list --root <root>
tcheck flows show issue-delivery --root <root>
ttask flow start --flow issue-delivery --from T-001 --queue site --root <root> --by lead
ttask flow state T-001 --flow issue-delivery --queue site --root <root>
```

## 3. Два разных уровня данных

### Определение процесса

`flow.json` объявляет логические шаги:

- `id` и `type` записи;
- `input_from` — prerequisite шаги;
- `output`/`outputs` — имена фактов, которые следующий шаг должен увидеть через extra, refs, artifacts или handoff;
- executor, режим и уровень;
- `parallel`/`optional`;
- `gate_out`;
- `requires` — условие вида `from + field + equals`;
- `decision_tree` — основной детерминированный selector: узлы читают объявленные поля и ведут только по allowlisted routes;
- `routes` — compatibility-словарь результата → следующего шага для старых FLOW-2 definitions; если есть `decision_tree`, он имеет приоритет;
- `fan_out` — источник списка элементов, их идентификатор, тип, заголовок и `join`.

### Конкретный запуск

`ttask flow start` создаёт обычные записи со статусом `draft`. Связи сохраняются через `parent`, `depends_on`, `refs` и строки индекса `flow`/`flow_step`. Для конкретного запуска и повторяемых шагов индекс дополнительно хранит `flow_run`, `flow_item` и `flow_revision`. Статус автоматически не меняется: человек переводит draft в `ready`, затем исполнитель берёт запись через `claim`.

```text
flow.json       → что должно произойти
index.json      → какой шаг уже существует и в каком статусе
T-NNN/task.json → содержание этого шага
```

## 4. Исполняемый preset `issue-delivery`

В поставке есть preset, который следует последовательному маршруту:

```text
intake
  ↓
research
  ↓
test-prep
  ↓
planning
  ↓
plan-audit
  ↓
implementation
  ↓
documentation
  ↓
test-fix
  ↓
final-testing
```

Это не Jira-specific маршрут. Входом может быть любая исходная запись; Jira остаётся только одним из вариантов `mirror`.

Ключевое отличие от `jira-fix`/`jira-feature`: `planning` зависит одновременно от закрытых `research` и `test-prep`. Поэтому план не создаётся на основании одного сырого текста.

## 5. Как runtime открывает следующий шаг

Наличие записи prerequisite и её завершение — разные факты:

```text
record exists       ≠       record is closed
```

`FlowState` теперь разделяет `existing` и `closed`:

1. если prerequisite только `draft`/`ready`/`in_progress`, следующий шаг не создаётся;
2. после `closed` проверяется, что prerequisite оставил каждый объявленный output;
3. только после этого создаётся следующий черновик;
4. `requires` дополнительно проверяет значение поля, например `plan-audit.extra.verdict == approved`.

Если prerequisite не оставил output, возвращается `FLOW_OUTPUT_MISSING`. Если условие аудита не выполнено, возвращается `FLOW_CONDITION_UNMET`; статус записи сам не меняется.

## 6. Ветвление как decision tree

Для нового маршрута ветка объявляется через `DECISION-TREE-1` на шаге. Каждый узел содержит `field` и объект `routes`; runtime читает только значение закрытой записи, проходит дерево через общий `branch_decision_tree` и получает terminal target. Свободный target из ответа исполнителя не принимается.

```text
closed record.extra.verdict
        ↓
DECISION-TREE-1 / verdict
  approved        → implementation
  changes_required → planning.revision
  blocked         → human-decision
```

Дерево детерминировано, versioned и проверяется до запуска. Если `decision_tree` отсутствует, старое поле `routes` поддерживается как compatibility fallback; при наличии обоих источником истины является дерево. `step.revision` — специальный объявленный target: он создаёт новую revision обычной записи, а не меняет старый `task.json`.

## 7. План и `plan-audit`

`planning` в этом preset — отдельная запись, но не потому, что любой план обязан быть задачей. Отдельная запись нужна для отдельного статуса, executor, refs, handoff и независимого аудита.

Тип `planning` сохраняет структурированные обязательные поля `approach`, `changes`, `outcome`, `check`. Большой результат — artifact, например:

```text
T-005/task.json
T-005/artifacts/plan.md
```

`plan.md` не является источником состояния. Источники разделены:

- `task.json` — поля, AC, refs, artifacts, comments, status;
- artifact — большой текст или manifest;
- `index.json` — состояние маршрута;
- `flow.json` — определение процесса.

`plan-audit` — read-only тип. Он требует `verdict`:

- `approved` — условие `implementation` выполнено;
- `changes_required` — route создаёт новую revision записи `planning`, после её закрытия создаётся повторный аудит;
- `blocked` — требуется решение человека, implementation не создаётся.

Аудитор не редактирует план и не создаёт implementation-задачи. Большой результат сохраняется, например, в `artifacts/audit.json`, а handoff сообщает следующий маршрут. Revision — новая обычная запись, а не перезапись старого `task.json`; status/gate-переходов автоматически нет.

## 8. Test-prep и финальный прогон

`test-prep` идёт после `research` и до `planning`/implementation. Он оставляет тексты или manifest тестов, связь с `AC-N` и handoff. Это контракт будущей проверки, не evidence зелёного прогона.

`final-testing` запускает заявленные команды после реализации и оставляет:

- команду;
- stdout/stderr и код возврата;
- evidence artifact;
- verdict по каждому исходному `AC-N`;
- handoff/remaining risks.

Только этот факт может подтверждать зелёный или красный результат. Наличие `artifacts/tests.json` от `test-prep` само по себе не означает, что тест выполнен.

## 9. Implementation slices и fan-in

`planning.extra.slice_list` — данные, а не путь к файлу. Каждый элемент должен
содержать `slice_id`, `type`, `title`, `scope`, `depends_on`, `ac`, `tests` и
`done_when`. В preset он объявлен источником `implementation.fan_out`:

```json
{
  "items_from": ["planning", "slice_list"],
  "item_id": "slice_id",
  "task_type_from": "type",
  "title_from": "title",
  "join": "all_closed"
}
```

Runtime создаёт на каждый элемент обычный `T-*` с `parent` и `depends_on`.
Координаты `flow_run`, `flow_item` и `flow_revision` остаются производными
полями `index.json`; в `task.json` не появляется скрытый state. Если элементов
больше `max_batch`, следующий вызов создаёт оставшиеся по их `flow_item`.

`all_closed` — fan-in: downstream шаг, например `documentation`, доступен
только после закрытия всех элементов текущей revision и проверки их outputs.
Подготовленный `slice_list` сам по себе не является evidence и не закрывает
implementation.

## 10. Почему это не один большой Markdown-план

Обычный Markdown удобен для чтения, но сам не проверяет:

- что research действительно закрыт до planning;
- что все refs и handoff оставлены;
- что audit approved;
- что следующий шаг не создан преждевременно;
- что итоговый тест имеет evidence.

Flow даёт маршрут и отрицательные пути, task даёт состояние конкретной работы, artifact хранит большой результат, а refs связывают дома без копирования текста.

## 11. Проверка поставки

```bash
python3 -m unittest discover -s todone/tests
python3 todone/scripts/tcheck.py selftest
python3 todone/scripts/tcheck.py doctor --root todone/examples/v6-project --all --strict
python3 todone/scripts/tcheck.py flows show issue-delivery --json
```

Структурные сравнения с OpenSpec и Spec Kit, включая ограничения token benchmark, находятся вне runtime-документации: `bench/workflow-benchmark.md`.
