# Постановка задачи через диалог

## Назначение

Триггер **«постановка задачи»** переводит разговор в bounded intake mode.
Skill отвечает, что готов собирать требования, и дальше выбирает следующий
уточняющий вопрос по текущему gap, риску и scope. Он не подменяет reasoning
фиксированной анкетой и не превращает обычное обсуждение в нормативный факт.

В runtime durable draft имеет контракт `INTAKE-1`; read-only аудит имеет
`TASK-AUDIT-1`. Их валидирует общий dispatcher `tcheck schema --file`.

## Два слоя состояния

| Слой | Где хранится | Что означает |
|---|---|---|
| conversational draft | `<root>/.todone/intake/<session>/draft.json` | продолжение intake между сообщениями |
| event history | `<root>/.todone/intake/<session>/events.jsonl` | append-only audit trail операций draft |
| captured input | `<root>/.todone/intake/<session>/inputs/` | копия принятого файла/screenshot |
| operational draft task | queue `data/T-NNN-intake/task.json` | создаётся только при явном persist/write intent |
| typed task | queue `data/T-NNN-<type>/task.json` | создаётся только финализацией |
| audit child | queue `data/T-NNN-plan-audit/task.json` | read-only verdict, findings и handoff |

Внутри `INTAKE-1` отдельно лежат `observed`, `requested`, `proposed`,
`accepted`, `unknown`, `evidence`, `decision` и provenance. Proposed option не
становится accepted без явного ответа пользователя. `history` — аудит операций,
а не источник требований; source text/file/screenshot хранится с digest и
reference.

## CLI для durable draft

CLI не имитирует естественную фразу; он даёт deterministic transport для
explicit write intents и acceptance checks:

```bash
# начать session; по умолчанию только persistent conversational draft
python3 todone/scripts/tcheck.py intake start \
  --root /project --queue site --title «Экспорт отчёта» --by alice

# создать operational intake task только явным opt-in
python3 todone/scripts/tcheck.py intake start \
  --root /project --queue site --title «Экспорт отчёта» \
  --persist --by alice

# продолжить draft после следующего сообщения
python3 todone/scripts/tcheck.py intake list --root /project
python3 todone/scripts/tcheck.py intake show \
  --root /project --session <session-id>

# вход из сообщения, файла или screenshot с provenance
python3 todone/scripts/tcheck.py intake capture \
  --root /project --session <session-id> --text «Нужен CSV» \
  --source conversation:message-3 --source-kind message --by alice
python3 todone/scripts/tcheck.py intake capture \
  --root /project --session <session-id> --file /tmp/screenshot.png \
  --by alice
```

`capture --file` копирует bytes в `inputs/`, сохраняет SHA-256, исходный path,
stored reference и source kind (`file`/`screenshot`). Неизвестный media type не
становится текстом молча.

## Последовательные уточнения

```bash
python3 todone/scripts/tcheck.py intake ask \
  --root /project --session <session-id> \
  --question «Какой формат нужен?» --choices csv,json \
  --default csv --on-decline ask_again --on-disabled ask_again --by alice
python3 todone/scripts/tcheck.py intake answer \
  --root /project --session <session-id> \
  --question-id Q-001 --value csv --by alice
```

`INTAKE-1` разрешает только один `open` question. `choices`, `default`,
`on_decline` и `on_disabled` передаются из active flow definition. Ответ
`--disabled` фиксирует только outcome этого шага и не меняет workspace policy.

Если вариантов несколько, skill показывает их плюсы/минусы как `proposed`
options. Принятие варианта — отдельное decision-событие; best practice не
становится правилом workspace автоматически.

## «Зафиксируй в задаче»

Это явный write intent. Он принимает только подтверждённый факт:

```bash
python3 todone/scripts/tcheck.py intake fix \
  --root /project --session <session-id> \
  --text «Целевая команда сохраняет CSV» \
  --source conversation:message-7 --source-kind message --by alice
```

Запись получает `status=accepted`, provenance и history event. Если session ещё
нет, skill сначала спрашивает, создавать ли draft; он не выбирает случайную
queue и не пишет прямо в чужую task.

## «Сформулируй задачу» / «Собери задачу»

Перед финализацией skill показывает:

- problem, goals, scope и context;
- acceptance и verify;
- accepted decisions и rejected/proposed variants;
- remaining questions и risks;
- refs, evidence и documentation impact;
- явный verdict `ready` либо `blocked`.

Только explicit finalize создаёт typed task:

```bash
python3 todone/scripts/tcheck.py intake finalize \
  --root /project --queue site --session <session-id> \
  --title «Экспорт отчёта» --type feature \
  --problem «Пользователь не может скачать отчёт» \
  --goals «Дать download в CSV» \
  --acceptance «Команда создаёт валидный CSV» \
  --verify «python3 -m unittest discover tests» --by alice
```

Команда требует problem, acceptance и verify, переносит bounded fields в TASK,
кладёт `artifacts/intake.json`, добавляет queue ref на operational draft и
handoff с verdict/remaining risks. Открытые вопросы блокируют создание; флаг
`--allow-open` — отдельное явное принятие remaining risks, а не автоматическое
закрытие gaps.

## Аудит задачи

```bash
python3 todone/scripts/tcheck.py intake audit \
  --root /project --queue site --session <session-id> \
  --task T-014 --by reviewer
```

Аудит не меняет target task. Он проверяет:

- TASK/type/gates и completeness acceptance/verify;
- dependencies, parent и queue refs;
- существование file/doc/symbol refs;
- duplicate candidates в queue;
- bounded code/doc checks, provenance и source fingerprint;
- remaining questions и risks.

Результат `TASK-AUDIT-1` обязан содержать `verdict`: `approved`,
`changes_required` или `blocked`, полный `findings`, `remaining_questions` и
`remaining_risks`. Для durable handoff создаётся child `plan-audit` с
`artifacts/audit.json`; исходная задача при этом остаётся неизменной.

## Границы

- `tcheck intake` — local persistence/audit; conversational model всё ещё
  отвечает за смысл, порядок уточнений и human confirmation.
- `ttask` остаётся source-of-truth для typed task; `draft.json` не подменяет
  `task.json`.
- Jira mirror остаётся readonly; переход `mirror → intake → typed task` всегда
  explicit.
- Scanner и `todoc_scan` не подключаются к intake и не менялись.
